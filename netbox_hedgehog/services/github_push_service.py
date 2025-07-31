"""
GitHub Push Service

Handles pushing directory structures and files to GitHub repositories.
Integrates with GitRepository credential system for authentication.
"""

import logging
import base64
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)


class GitHubPushService:
    """
    Service for pushing directory structures and files to GitHub repositories.
    
    Integrates with the existing GitRepository credential system to handle
    authentication and pushes directory structures created by GitOps initialization.
    """
    
    def __init__(self, git_repository):
        """
        Initialize with a GitRepository instance.
        
        Args:
            git_repository: GitRepository model instance with credentials
        """
        self.git_repository = git_repository
        self.github_api_base = None
        self.headers = {}
        self.repo_owner = None
        self.repo_name = None
        
        self._setup_github_config()
    
    def _setup_github_config(self):
        """Setup GitHub API configuration from repository URL"""
        try:
            url = self.git_repository.url
            
            # Parse GitHub repository URL
            if 'github.com' in url:
                # Extract owner/repo from URL like https://github.com/owner/repo.git
                if url.endswith('.git'):
                    url = url[:-4]
                
                parts = url.rstrip('/').split('/')
                self.repo_owner = parts[-2]
                self.repo_name = parts[-1]
                
                self.github_api_base = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"
                
                # Setup authentication headers
                credentials = self.git_repository.get_credentials()
                token = credentials.get('token') or credentials.get('access_token')
                
                if token:
                    self.headers = {
                        'Authorization': f'token {token}',
                        'Accept': 'application/vnd.github.v3+json',
                        'Content-Type': 'application/json'
                    }
                    logger.info(f"GitHub API configured for {self.repo_owner}/{self.repo_name}")
                else:
                    logger.error("No GitHub token found in credentials")
                    
            else:
                logger.error(f"Repository {url} is not a GitHub repository")
                
        except Exception as e:
            logger.error(f"Failed to setup GitHub configuration: {e}")
    
    def create_directory_structure(self, base_path: str, directories: List[str], 
                                 commit_message: str = None) -> Dict[str, Any]:
        """
        Create directory structure in GitHub repository by creating placeholder files.
        
        GitHub doesn't support empty directories, so we create .gitkeep files
        in each directory to establish the structure.
        
        Args:
            base_path: Base path in repository (e.g., "gitops/hedgehog/fabric-1")
            directories: List of directory names to create (e.g., ["raw", "managed", "unmanaged"])
            commit_message: Optional commit message
            
        Returns:
            Result dictionary with success status and details
        """
        if not self.github_api_base or not self.headers:
            return {
                'success': False,
                'error': 'GitHub API not properly configured'
            }
        
        commit_msg = commit_message or f"Initialize GitOps directory structure for {base_path}"
        
        try:
            created_files = []
            errors = []
            
            # Create each directory by adding a .gitkeep file
            for directory in directories:
                file_path = f"{base_path}/{directory}/.gitkeep"
                
                result = self._create_file(
                    file_path=file_path,
                    content="# This file ensures the directory is tracked by Git\n",
                    commit_message=f"{commit_msg} - {directory}/ directory"
                )
                
                if result['success']:
                    created_files.append(file_path)
                    logger.info(f"Created directory structure: {file_path}")
                else:
                    errors.append(f"Failed to create {file_path}: {result['error']}")
                    logger.error(f"Failed to create {file_path}: {result['error']}")
            
            # Also create any subdirectories in managed/
            if 'managed' in directories:
                managed_subdirs = [
                    'connections', 'servers', 'switches', 'switchgroups',
                    'vlannamespaces', 'vpcs', 'externals', 'externalattachments',
                    'externalpeerings', 'ipv4namespaces', 'vpcattachments', 'vpcpeerings'
                ]
                
                for subdir in managed_subdirs:
                    file_path = f"{base_path}/managed/{subdir}/.gitkeep"
                    
                    result = self._create_file(
                        file_path=file_path,
                        content=f"# Managed {subdir} CRDs directory\n",
                        commit_message=f"{commit_msg} - managed/{subdir}/ directory"
                    )
                    
                    if result['success']:
                        created_files.append(file_path)
                        logger.info(f"Created managed subdirectory: {file_path}")
                    else:
                        errors.append(f"Failed to create {file_path}: {result['error']}")
            
            success = len(errors) == 0
            
            return {
                'success': success,
                'message': f'Created {len(created_files)} directory placeholders' if success else f'Partial success: {len(created_files)} created, {len(errors)} errors',
                'created_files': created_files,
                'errors': errors,
                'repository_url': self.git_repository.url,
                'commit_author': 'Hedgehog NetBox Plugin'
            }
            
        except Exception as e:
            logger.error(f"Failed to create directory structure: {e}")
            return {
                'success': False,
                'error': str(e),
                'repository_url': self.git_repository.url
            }
    
    def _create_file(self, file_path: str, content: str, commit_message: str) -> Dict[str, Any]:
        """
        Create a single file in the GitHub repository.
        
        Args:
            file_path: Path to the file in the repository
            content: File content
            commit_message: Commit message
            
        Returns:
            Result dictionary
        """
        try:
            # Check if file already exists
            check_url = f"{self.github_api_base}/contents/{file_path}"
            check_response = requests.get(check_url, headers=self.headers)
            
            if check_response.status_code == 200:
                # File exists, we could update it, but for now we'll skip
                return {
                    'success': True,
                    'message': 'File already exists, skipped',
                    'file_path': file_path
                }
            
            # Encode content to base64
            content_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            
            # Create file payload
            payload = {
                'message': commit_message,
                'content': content_encoded,
                'author': {
                    'name': 'Hedgehog NetBox Plugin',
                    'email': 'hnp@hedgehog.githedgehog.com'
                },
                'committer': {
                    'name': 'Hedgehog NetBox Plugin',
                    'email': 'hnp@hedgehog.githedgehog.com'
                }
            }
            
            # Create the file
            create_url = f"{self.github_api_base}/contents/{file_path}"
            response = requests.put(create_url, headers=self.headers, json=payload)
            
            if response.status_code == 201:
                result_data = response.json()
                return {
                    'success': True,
                    'message': 'File created successfully',
                    'file_path': file_path,
                    'commit_sha': result_data.get('commit', {}).get('sha'),
                    'commit_url': result_data.get('commit', {}).get('html_url')
                }
            else:
                logger.error(f"GitHub API error creating {file_path}: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f'GitHub API error: {response.status_code} - {response.text}',
                    'file_path': file_path
                }
                
        except Exception as e:
            logger.error(f"Exception creating file {file_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'file_path': file_path
            }
    
    def create_manifest_files(self, base_path: str, fabric_name: str, fabric_id: int) -> Dict[str, Any]:
        """
        Create initial manifest files in the .hnp metadata directory.
        
        Args:
            base_path: Base path in repository
            fabric_name: Name of the fabric
            fabric_id: ID of the fabric
            
        Returns:
            Result dictionary
        """
        try:
            created_files = []
            errors = []
            
            # Create manifest.yaml
            manifest_content = {
                'version': '1.0',
                'fabric_name': fabric_name,
                'fabric_id': fabric_id,
                'structure_version': '1.0',
                'created_at': timezone.now().isoformat(),
                'created_by': 'Hedgehog NetBox Plugin',
                'directories': {
                    'raw': 'raw',
                    'managed': 'managed',
                    'unmanaged': 'unmanaged'
                },
                'crd_directories': [
                    'connections', 'servers', 'switches', 'switchgroups',
                    'vlannamespaces', 'vpcs', 'externals', 'externalattachments',
                    'externalpeerings', 'ipv4namespaces', 'vpcattachments', 'vpcpeerings'
                ],
                'archive_strategy': 'rename_with_extension',
                'gitops_initialized': True
            }
            
            manifest_yaml = "# HNP GitOps Manifest\n" + \
                           "# This file tracks the GitOps structure for this fabric\n\n" + \
                           json.dumps(manifest_content, indent=2)
            
            manifest_result = self._create_file(
                file_path=f"{base_path}/.hnp/manifest.yaml",
                content=manifest_yaml,
                commit_message=f"Create GitOps manifest for {fabric_name}"
            )
            
            if manifest_result['success']:
                created_files.append(f"{base_path}/.hnp/manifest.yaml")
            else:
                errors.append(f"Failed to create manifest: {manifest_result['error']}")
            
            # Create archive-log.yaml
            archive_log_content = {
                'version': '1.0',
                'created_at': timezone.now().isoformat(),
                'operations': [],
                'description': 'Log of archive operations performed during GitOps management'
            }
            
            archive_yaml = "# HNP Archive Log\n" + \
                          "# This file tracks file archiving operations\n\n" + \
                          json.dumps(archive_log_content, indent=2)
            
            archive_result = self._create_file(
                file_path=f"{base_path}/.hnp/archive-log.yaml",
                content=archive_yaml,
                commit_message=f"Create archive log for {fabric_name}"
            )
            
            if archive_result['success']:
                created_files.append(f"{base_path}/.hnp/archive-log.yaml")
            else:
                errors.append(f"Failed to create archive log: {archive_result['error']}")
            
            # Create README.md in the base path to document the structure
            readme_content = f"""# GitOps Directory Structure for {fabric_name}

This directory contains the GitOps file management structure for the Hedgehog fabric "{fabric_name}".

## Directory Structure

- **raw/**: Drop YAML files here for processing by HNP
- **managed/**: HNP-managed normalized files organized by CRD type
- **unmanaged/**: Files that exist in the repository but are not managed by HNP
- **.hnp/**: HNP metadata and configuration files

## How It Works

1. Drop your YAML files in the `raw/` directory
2. HNP will process them and create normalized files in `managed/`
3. Original files will be archived according to the configured strategy
4. HNP maintains metadata in the `.hnp/` directory

## Managed CRD Types

The `managed/` directory contains subdirectories for each supported CRD type:

{chr(10).join([f'- {crd}/' for crd in manifest_content['crd_directories']])}

## Generated

This structure was created by Hedgehog NetBox Plugin on {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}.
"""

            readme_result = self._create_file(
                file_path=f"{base_path}/README.md",
                content=readme_content,
                commit_message=f"Add GitOps documentation for {fabric_name}"
            )
            
            if readme_result['success']:
                created_files.append(f"{base_path}/README.md")
            else:
                errors.append(f"Failed to create README: {readme_result['error']}")
            
            success = len(errors) == 0
            
            return {
                'success': success,
                'message': f'Created {len(created_files)} manifest files' if success else f'Partial success: {len(created_files)} created, {len(errors)} errors',
                'created_files': created_files,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Failed to create manifest files: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to GitHub API.
        
        Returns:
            Result dictionary with connection status
        """
        if not self.github_api_base or not self.headers:
            return {
                'success': False,
                'error': 'GitHub API not configured'
            }
        
        try:
            # Test with a simple API call
            response = requests.get(self.github_api_base, headers=self.headers)
            
            if response.status_code == 200:
                repo_data = response.json()
                return {
                    'success': True,
                    'message': 'GitHub API connection successful',
                    'repository_name': repo_data.get('full_name'),
                    'private': repo_data.get('private'),
                    'default_branch': repo_data.get('default_branch'),
                    'permissions': repo_data.get('permissions', {})
                }
            else:
                return {
                    'success': False,
                    'error': f'GitHub API error: {response.status_code} - {response.text}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_repository_structure(self, path: str = "") -> Dict[str, Any]:
        """
        Get the current repository structure at a given path.
        
        Args:
            path: Repository path to examine
            
        Returns:
            Result dictionary with structure information
        """
        if not self.github_api_base or not self.headers:
            return {
                'success': False,
                'error': 'GitHub API not configured'
            }
        
        try:
            url = f"{self.github_api_base}/contents/{path}" if path else f"{self.github_api_base}/contents"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                contents = response.json()
                
                directories = []
                files = []
                
                for item in contents:
                    if item['type'] == 'dir':
                        directories.append(item['name'])
                    else:
                        files.append({
                            'name': item['name'],
                            'size': item['size'],
                            'sha': item['sha']
                        })
                
                return {
                    'success': True,
                    'path': path,
                    'directories': directories,
                    'files': files,
                    'total_items': len(contents)
                }
            else:
                return {
                    'success': False,
                    'error': f'GitHub API error: {response.status_code} - {response.text}',
                    'path': path
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'path': path
            }