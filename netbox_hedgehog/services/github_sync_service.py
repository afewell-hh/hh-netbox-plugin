"""
GitHub Sync Service

Handles synchronization of CR changes from HNP GUI to GitHub repository.
Uses GitHub API directly for all operations - no local git required.

CRITICAL: This service fixes the core issue where CR changes in HNP GUI
were not being written back to GitHub YAML files.
"""

import os
import re
import logging
import yaml
import json
import base64
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)

# GitHub API tracing logger - for detailed execution tracing
api_logger = logging.getLogger(f"{__name__}.api_trace")
api_logger.setLevel(logging.DEBUG)


class GitHubSyncService:
    """
    Service to sync CR changes from HNP GUI to GitHub repository.
    
    This service:
    1. Uses GitHub API directly (no local git operations)
    2. Writes CR changes to managed/ directory in proper format
    3. Handles create, update, and delete operations
    4. Maintains proper commit history
    """
    
    def __init__(self, fabric):
        """
        Initialize GitHub sync service for a fabric.
        
        Args:
            fabric: HedgehogFabric instance with git configuration
        """
        self.fabric = fabric
        self.github_token = self._get_github_token()
        self.owner, self.repo = self._parse_github_url()
        self.api_base = f"https://api.github.com/repos/{self.owner}/{self.repo}"
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # CRD kind to directory mapping
        self.kind_to_directory = {
            'VPC': 'vpcs',
            'External': 'externals',
            'ExternalAttachment': 'externalattachments',
            'ExternalPeering': 'externalpeerings',
            'IPv4Namespace': 'ipv4namespaces',
            'VPCAttachment': 'vpcattachments',
            'VPCPeering': 'vpcpeerings',
            'Connection': 'connections',
            'Server': 'servers',
            'Switch': 'switches',
            'SwitchGroup': 'switchgroups',
            'VLANNamespace': 'vlannamespaces'
        }
        
        logger.info(f"Initialized GitHubSyncService for fabric {fabric.name} - repo: {self.owner}/{self.repo}")
    
    def sync_cr_to_github(self, cr_instance, operation: str = 'update', 
                         user: str = 'system', commit_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Sync a CR instance to GitHub repository.
        
        Args:
            cr_instance: The CR model instance to sync
            operation: 'create', 'update', or 'delete'
            user: Username for commit attribution
            commit_message: Optional custom commit message
            
        Returns:
            Dict with sync results including success status and commit SHA
        """
        api_logger.info(f"=== GITHUB API SYNC ENTRY ===")
        api_logger.info(f"CR Instance: {cr_instance.__class__.__name__} '{cr_instance.name}'")
        api_logger.info(f"Operation: {operation}")
        api_logger.info(f"User: {user}")
        api_logger.info(f"Repository: {self.owner}/{self.repo}")
        api_logger.info(f"Token present: {'YES' if self.github_token else 'NO'}")
        api_logger.info(f"Token starts with: {self.github_token[:8]}..." if self.github_token else 'NO TOKEN')
        
        try:
            logger.info(f"Starting GitHub sync for {cr_instance.__class__.__name__} {cr_instance.name} - operation: {operation}")
            
            if operation == 'delete':
                api_logger.info("Routing to DELETE operation")
                result = self._delete_cr_from_github(cr_instance, user, commit_message)
            else:
                api_logger.info(f"Routing to WRITE operation (create/update)")
                result = self._write_cr_to_github(cr_instance, operation, user, commit_message)
            
            api_logger.info(f"=== GITHUB API SYNC RESULT ===")
            api_logger.info(f"Success: {result.get('success', False)}")
            api_logger.info(f"Operation: {result.get('operation', 'unknown')}")
            if result.get('success'):
                api_logger.info(f"Commit SHA: {result.get('commit_sha', 'none')}")
                api_logger.info(f"File Path: {result.get('file_path', 'unknown')}")
            else:
                api_logger.error(f"Error: {result.get('error', 'unknown error')}")
            
            return result
                
        except Exception as e:
            api_logger.error(f"=== GITHUB API SYNC EXCEPTION ===")
            api_logger.error(f"Exception type: {type(e).__name__}")
            api_logger.error(f"Exception message: {str(e)}")
            logger.error(f"GitHub sync failed for {cr_instance.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'operation': operation
            }
    
    def _write_cr_to_github(self, cr_instance, operation: str, user: str, 
                           commit_message: Optional[str] = None) -> Dict[str, Any]:
        """Write (create or update) a CR to GitHub."""
        
        # Generate YAML content
        yaml_content = self._generate_yaml(cr_instance)
        
        # Determine file path in managed/ directory
        file_path = self._get_managed_file_path(cr_instance)
        
        # Check if file exists in GitHub
        existing_file = self._get_file_from_github(file_path)
        
        # Generate commit message
        if not commit_message:
            action = "Create" if not existing_file else "Update"
            commit_message = f"{action} {cr_instance.__class__.__name__}: {cr_instance.name}\n\n"
            commit_message += f"Updated via HNP GUI by {user}\n"
            commit_message += f"Timestamp: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        # Create or update file in GitHub
        if existing_file:
            result = self._update_file_in_github(
                file_path, 
                yaml_content, 
                commit_message,
                existing_file['sha']
            )
        else:
            result = self._create_file_in_github(
                file_path,
                yaml_content,
                commit_message
            )
        
        if result['success']:
            # Update CR with git metadata
            relative_path = self._get_relative_path(file_path)
            cr_instance.git_file_path = relative_path
            cr_instance.last_synced = timezone.now()
            cr_instance.save(update_fields=['git_file_path', 'last_synced'])
            
            logger.info(f"Successfully synced {cr_instance.name} to GitHub: {file_path}")
            
        return result
    
    def _delete_cr_from_github(self, cr_instance, user: str, 
                              commit_message: Optional[str] = None) -> Dict[str, Any]:
        """Delete a CR from GitHub."""
        
        # Get file path
        file_path = self._get_managed_file_path(cr_instance)
        
        # Check if file exists
        existing_file = self._get_file_from_github(file_path)
        
        if not existing_file:
            logger.warning(f"File not found in GitHub for deletion: {file_path}")
            return {
                'success': True,
                'message': 'File not found in GitHub (already deleted)',
                'operation': 'delete'
            }
        
        # Generate commit message
        if not commit_message:
            commit_message = f"Delete {cr_instance.__class__.__name__}: {cr_instance.name}\n\n"
            commit_message += f"Deleted via HNP GUI by {user}\n"
            commit_message += f"Timestamp: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        # Delete file from GitHub
        return self._delete_file_from_github(
            file_path,
            existing_file['sha'],
            commit_message
        )
    
    def _generate_yaml(self, cr_instance) -> str:
        """Generate YAML content from CR instance."""
        
        # Build Kubernetes manifest
        manifest = {
            'apiVersion': self._get_api_version(cr_instance),
            'kind': cr_instance.__class__.__name__,
            'metadata': {
                'name': cr_instance.name,
                'namespace': cr_instance.namespace or self.fabric.kubernetes_namespace or 'default',
                'annotations': {
                    'hnp.githedgehog.com/managed-by': 'hedgehog-netbox-plugin',
                    'hnp.githedgehog.com/fabric': self.fabric.name,
                    'hnp.githedgehog.com/last-synced': timezone.now().isoformat()
                }
            }
        }
        
        # Add labels if present
        if hasattr(cr_instance, 'labels') and cr_instance.labels:
            labels = cr_instance.labels
            if isinstance(labels, str):
                try:
                    labels = json.loads(labels)
                except:
                    labels = {}
            manifest['metadata']['labels'] = labels
        
        # Add spec if present
        if hasattr(cr_instance, 'spec') and cr_instance.spec:
            spec = cr_instance.spec
            if isinstance(spec, str):
                try:
                    spec = json.loads(spec)
                except:
                    spec = {}
            manifest['spec'] = spec
        
        # Convert to YAML with header
        yaml_content = f"# {cr_instance.__class__.__name__}: {cr_instance.name}\n"
        yaml_content += f"# Generated by HNP at {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        yaml_content += "---\n"
        yaml_content += yaml.dump(
            manifest,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120
        )
        
        return yaml_content
    
    def _get_api_version(self, cr_instance) -> str:
        """Get the appropriate API version for a CR type."""
        
        model_name = cr_instance.__class__.__name__
        
        # VPC API models
        vpc_models = ['VPC', 'External', 'ExternalAttachment', 'ExternalPeering',
                     'IPv4Namespace', 'VPCAttachment', 'VPCPeering']
        if model_name in vpc_models:
            return 'vpc.githedgehog.com/v1alpha2'
        
        # Wiring API models
        wiring_models = ['Connection', 'Server', 'Switch', 'SwitchGroup', 'VLANNamespace']
        if model_name in wiring_models:
            return 'wiring.githedgehog.com/v1alpha2'
        
        # Default
        return 'v1alpha2'
    
    def _get_managed_file_path(self, cr_instance) -> str:
        """Get the full file path for a CR in the managed directory."""
        
        # Get base path for fabric's GitOps directory
        gitops_path = self._get_gitops_base_path()
        
        # Get CRD type directory
        kind = cr_instance.__class__.__name__
        crd_dir = self.kind_to_directory.get(kind, kind.lower() + 's')
        
        # Generate filename
        namespace = cr_instance.namespace or self.fabric.kubernetes_namespace or 'default'
        if namespace != 'default':
            filename = f"{namespace}-{cr_instance.name}.yaml"
        else:
            filename = f"{cr_instance.name}.yaml"
        
        # Construct full path
        return f"{gitops_path}/managed/{crd_dir}/{filename}"
    
    def _get_gitops_base_path(self) -> str:
        """Get the base GitOps directory path in the repository."""
        
        # Check if fabric has explicit gitops_directory setting
        if hasattr(self.fabric, 'gitops_directory') and self.fabric.gitops_directory:
            path = self.fabric.gitops_directory.strip('/')
            return path
        
        # Default path structure
        return f"fabrics/{self.fabric.name.lower()}/gitops"
    
    def _get_relative_path(self, full_path: str) -> str:
        """Get relative path from GitOps base."""
        
        gitops_base = self._get_gitops_base_path()
        if full_path.startswith(gitops_base):
            return full_path[len(gitops_base):].lstrip('/')
        return full_path
    
    def _get_github_token(self) -> str:
        """Get GitHub token from fabric or environment."""
        
        # Try fabric's git repository first
        if hasattr(self.fabric, 'git_repository') and self.fabric.git_repository:
            if hasattr(self.fabric.git_repository, 'token') and self.fabric.git_repository.token:
                return self.fabric.git_repository.token
        
        # Try fabric's direct token
        if hasattr(self.fabric, 'git_token') and self.fabric.git_token:
            return self.fabric.git_token
        
        # Fall back to environment/settings
        token = os.environ.get('GITHUB_TOKEN') or getattr(settings, 'GITHUB_TOKEN', None)
        
        if not token:
            raise ValueError("No GitHub token found. Set GITHUB_TOKEN in environment or fabric configuration.")
        
        return token
    
    def _parse_github_url(self) -> Tuple[str, str]:
        """Parse GitHub owner and repo from URL."""
        
        url = None
        
        # Get URL from fabric
        if hasattr(self.fabric, 'git_repository') and self.fabric.git_repository:
            url = self.fabric.git_repository.url
        elif hasattr(self.fabric, 'git_repository_url'):
            url = self.fabric.git_repository_url
        
        if not url:
            raise ValueError("No GitHub repository URL configured for fabric")
        
        # Parse owner/repo from URL
        patterns = [
            r'github\.com[:/]([^/]+)/([^/\.]+)',
            r'github\.com/([^/]+)/([^/\.]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                owner, repo = match.groups()
                # Remove .git suffix if present
                repo = repo.replace('.git', '')
                return owner, repo
        
        raise ValueError(f"Could not parse GitHub owner/repo from URL: {url}")
    
    def _get_file_from_github(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file info from GitHub if it exists."""
        
        url = f"{self.api_base}/contents/{file_path}"
        
        api_logger.info(f"--- GET FILE FROM GITHUB ---")
        api_logger.info(f"URL: {url}")
        api_logger.info(f"Headers: Authorization: token {self.github_token[:8]}..., Accept: {self.headers.get('Accept')}")
        
        try:
            api_logger.info("Making HTTP GET request...")
            response = requests.get(url, headers=self.headers)
            api_logger.info(f"Response status: {response.status_code}")
            api_logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                api_logger.info("File found in GitHub")
                data = response.json()
                api_logger.info(f"File SHA: {data.get('sha', 'unknown')}")
                return data
            elif response.status_code == 404:
                api_logger.info("File not found in GitHub (404)")
                return None
            else:
                api_logger.warning(f"GitHub API returned {response.status_code}")
                api_logger.warning(f"Response text: {response.text[:500]}...")
                logger.warning(f"GitHub API returned {response.status_code} for {file_path}")
                return None
        except Exception as e:
            api_logger.error(f"Exception during GitHub file get: {type(e).__name__}: {e}")
            logger.error(f"Error getting file from GitHub: {e}")
            return None
    
    def _create_file_in_github(self, file_path: str, content: str, 
                              commit_message: str) -> Dict[str, Any]:
        """Create a new file in GitHub."""
        
        url = f"{self.api_base}/contents/{file_path}"
        
        # Encode content to base64
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        branch = self.fabric.git_branch or 'main'
        data = {
            'message': commit_message,
            'content': encoded_content,
            'branch': branch
        }
        
        api_logger.info(f"--- CREATE FILE IN GITHUB ---")
        api_logger.info(f"URL: {url}")
        api_logger.info(f"Branch: {branch}")
        api_logger.info(f"Commit message: {commit_message}")
        api_logger.info(f"Content length: {len(content)} chars")
        api_logger.info(f"Encoded content length: {len(encoded_content)} chars")
        
        try:
            api_logger.info("Making HTTP PUT request to create file...")
            response = requests.put(url, headers=self.headers, json=data)
            api_logger.info(f"Response status: {response.status_code}")
            api_logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                commit_sha = result.get('commit', {}).get('sha', 'unknown')
                api_logger.info(f"SUCCESS: File created with commit SHA: {commit_sha}")
                return {
                    'success': True,
                    'operation': 'create',
                    'file_path': file_path,
                    'commit_sha': commit_sha,
                    'message': f"Created file {file_path}"
                }
            else:
                api_logger.error(f"FAILED: GitHub API error {response.status_code}")
                api_logger.error(f"Error response: {response.text[:1000]}...")
                return {
                    'success': False,
                    'error': f"GitHub API error: {response.status_code} - {response.text}",
                    'operation': 'create'
                }
                
        except Exception as e:
            api_logger.error(f"EXCEPTION during file creation: {type(e).__name__}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operation': 'create'
            }
    
    def _update_file_in_github(self, file_path: str, content: str, 
                              commit_message: str, sha: str) -> Dict[str, Any]:
        """Update an existing file in GitHub."""
        
        url = f"{self.api_base}/contents/{file_path}"
        
        # Encode content to base64
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        data = {
            'message': commit_message,
            'content': encoded_content,
            'sha': sha,
            'branch': self.fabric.git_branch or 'main'
        }
        
        try:
            response = requests.put(url, headers=self.headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'operation': 'update',
                    'file_path': file_path,
                    'commit_sha': result['commit']['sha'],
                    'message': f"Updated file {file_path}"
                }
            else:
                return {
                    'success': False,
                    'error': f"GitHub API error: {response.status_code} - {response.text}",
                    'operation': 'update'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'operation': 'update'
            }
    
    def _delete_file_from_github(self, file_path: str, sha: str, 
                                commit_message: str) -> Dict[str, Any]:
        """Delete a file from GitHub."""
        
        url = f"{self.api_base}/contents/{file_path}"
        
        data = {
            'message': commit_message,
            'sha': sha,
            'branch': self.fabric.git_branch or 'main'
        }
        
        try:
            response = requests.delete(url, headers=self.headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'operation': 'delete',
                    'file_path': file_path,
                    'commit_sha': result['commit']['sha'],
                    'message': f"Deleted file {file_path}"
                }
            else:
                return {
                    'success': False,
                    'error': f"GitHub API error: {response.status_code} - {response.text}",
                    'operation': 'delete'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'operation': 'delete'
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test GitHub API connection and permissions."""
        
        try:
            # Test API access
            url = f"{self.api_base}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f"Cannot access repository: {response.status_code}"
                }
            
            repo_info = response.json()
            
            # Check permissions
            permissions = repo_info.get('permissions', {})
            can_push = permissions.get('push', False)
            
            if not can_push:
                return {
                    'success': False,
                    'error': 'Token does not have push permissions'
                }
            
            return {
                'success': True,
                'message': f"Successfully connected to {self.owner}/{self.repo}",
                'repo_name': repo_info.get('full_name'),
                'default_branch': repo_info.get('default_branch'),
                'permissions': permissions
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Connection test failed: {str(e)}"
            }