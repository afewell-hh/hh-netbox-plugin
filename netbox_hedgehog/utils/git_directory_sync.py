"""
Git Directory Synchronization Utility
Scans Git repository directories for Hedgehog CRs and syncs them to HNP database
"""

import os
import yaml
import tempfile
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import subprocess
from datetime import datetime

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class GitDirectorySync:
    """
    Handles synchronization between Git repository and HNP database.
    Scans Git directory for YAML files and creates/updates CR records.
    """
    
    # Mapping of Kubernetes kinds to HNP model classes
    KIND_TO_MODEL = {
        'VPC': 'vpc_api.VPC',
        'External': 'vpc_api.External',
        'ExternalAttachment': 'vpc_api.ExternalAttachment',
        'ExternalPeering': 'vpc_api.ExternalPeering',
        'IPv4Namespace': 'vpc_api.IPv4Namespace',
        'VPCAttachment': 'vpc_api.VPCAttachment',
        'VPCPeering': 'vpc_api.VPCPeering',
        'Connection': 'wiring_api.Connection',
        'Server': 'wiring_api.Server',
        'Switch': 'wiring_api.Switch',
        'SwitchGroup': 'wiring_api.SwitchGroup',
        'VLANNamespace': 'wiring_api.VLANNamespace',
    }
    
    def __init__(self, fabric):
        self.fabric = fabric
        self.stats = {
            'scanned': 0,
            'created': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }
        self.errors = []
        
    def sync_from_git(self) -> Dict[str, Any]:
        """
        Main sync method - clones/pulls repo and syncs all CRs
        """
        logger.info(f"Starting Git sync for fabric {self.fabric.name}")
        
        # Validate configuration
        if not self.fabric.git_repository and not self.fabric.git_repository_url:
            return {
                'success': False,
                'error': 'No Git repository configured for this fabric. Please configure Git repository in fabric settings.'
            }
            
        # Handle both new and legacy Git configuration
        if self.fabric.git_repository:
            git_repo = self.fabric.git_repository
            repo_url = git_repo.url
            branch = git_repo.default_branch or 'main'
            # Get credentials from encrypted storage
            try:
                credentials = git_repo.get_credentials()
                token = credentials.get('token') or credentials.get('access_token')
            except Exception as e:
                logger.warning(f"Failed to get credentials: {e}")
                token = None
        else:
            # Fall back to legacy fields
            repo_url = self.fabric.git_repository_url
            branch = self.fabric.git_branch or 'main'
            token = None  # Legacy didn't have token field
            
        if not repo_url:
            return {
                'success': False,
                'error': 'Git repository URL is not configured'
            }
            
        # Clone or update repository
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_path = Path(temp_dir) / 'repo'
                
                # Clone repository
                clone_result = self._clone_repository(
                    repo_url,
                    repo_path,
                    branch,
                    token
                )
                
                if not clone_result['success']:
                    return clone_result
                
                # Scan for YAML files
                gitops_path = repo_path / (self.fabric.gitops_directory or 'hedgehog')
                if not gitops_path.exists():
                    return {
                        'success': False,
                        'error': f'GitOps directory {gitops_path} not found in repository'
                    }
                
                # Process all YAML files
                self._process_directory(gitops_path)
                
                # Update fabric last sync time
                self.fabric.last_git_sync = timezone.now()
                if hasattr(self.fabric, 'sync_status'):
                    self.fabric.sync_status = 'synced' if self.stats['errors'] == 0 else 'error'
                self.fabric.save()
                
                success = self.stats['errors'] == 0
                message = f"Sync completed: {self.stats['created']} created, {self.stats['updated']} updated"
                if self.stats['errors'] > 0:
                    message += f", {self.stats['errors']} errors"
                
                logger.info(f"Git sync for fabric {self.fabric.name}: {message}")
                
                return {
                    'success': success,
                    'message': message,
                    'commit_sha': clone_result.get('commit_sha', 'unknown'),
                    'files_processed': self.stats['scanned'],
                    'resources_created': self.stats['created'],
                    'resources_updated': self.stats['updated'],
                    'errors': self.errors if self.stats['errors'] > 0 else [],
                    'warnings': [],
                    'sync_time': self.fabric.last_git_sync.isoformat() if self.fabric.last_git_sync else None
                }
                
        except Exception as e:
            logger.error(f"Git sync failed: {str(e)}")
            return {
                'success': False,
                'error': f'Git sync failed: {str(e)}'
            }
    
    def _clone_repository(self, url: str, path: Path, branch: str, token: Optional[str]) -> Dict[str, Any]:
        """Clone Git repository with authentication if needed"""
        try:
            # Add token to URL if provided
            if token and 'github.com' in url:
                # Format: https://token@github.com/user/repo.git
                url_parts = url.replace('https://', '').replace('http://', '')
                auth_url = f"https://{token}@{url_parts}"
            else:
                auth_url = url
                
            logger.info(f"Cloning repository {url} branch {branch}")
            
            # Clone repository
            cmd = ['git', 'clone', '--depth', '1', '--branch', branch, auth_url, str(path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                logger.error(f"Git clone failed: {result.stderr}")
                return {
                    'success': False,
                    'error': f'Git clone failed: {result.stderr.strip()}'
                }
            
            # Get the current commit SHA
            try:
                commit_cmd = ['git', '-C', str(path), 'rev-parse', 'HEAD']
                commit_result = subprocess.run(commit_cmd, capture_output=True, text=True, timeout=10)
                commit_sha = commit_result.stdout.strip() if commit_result.returncode == 0 else 'unknown'
            except Exception as e:
                logger.warning(f"Failed to get commit SHA: {e}")
                commit_sha = 'unknown'
                
            logger.info(f"Successfully cloned repository to {path}, commit: {commit_sha[:8]}")
            return {
                'success': True,
                'commit_sha': commit_sha
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Git clone operation timed out'
            }
        except Exception as e:
            logger.error(f"Failed to clone repository: {e}")
            return {
                'success': False,
                'error': f'Failed to clone repository: {str(e)}'
            }
    
    def _process_directory(self, directory: Path):
        """Recursively process all YAML files in directory"""
        for yaml_file in directory.rglob('*.yaml'):
            self._process_yaml_file(yaml_file)
        for yml_file in directory.rglob('*.yml'):
            self._process_yaml_file(yml_file)
    
    def _process_yaml_file(self, file_path: Path):
        """Process a single YAML file containing CRs"""
        self.stats['scanned'] += 1
        
        try:
            with open(file_path, 'r') as f:
                # Handle multi-document YAML files
                documents = list(yaml.safe_load_all(f))
                
            for doc in documents:
                if doc and isinstance(doc, dict):
                    self._process_cr_document(doc, file_path)
                    
        except Exception as e:
            self.stats['errors'] += 1
            self.errors.append(f"Error processing {file_path}: {str(e)}")
            logger.error(f"Failed to process YAML file {file_path}: {e}")
    
    def _calculate_git_file_path(self, file_path: Path) -> str:
        """
        Calculate the Git file path for a CRD from its full file system path.
        
        This creates a relative path from the repository root that can be used
        to identify the file within the Git repository.
        
        Args:
            file_path: Full Path object to the YAML file
            
        Returns:
            str: Relative path from Git repository root
        """
        try:
            # Convert to string for easier manipulation
            file_str = str(file_path)
            
            # Try to find a good reference point in the path
            # Look for common GitOps directory patterns
            path_parts = file_path.parts
            
            # Try to find the repository root or gitops directory
            repo_indicators = ['repo', 'hedgehog', 'gitops', 'fabric-1']
            start_index = None
            
            for i, part in enumerate(path_parts):
                if part in repo_indicators:
                    start_index = i + 1  # Start after the repo indicator
                    break
            
            if start_index is not None and start_index < len(path_parts):
                # Create relative path from the found starting point
                relative_parts = path_parts[start_index:]
                relative_path = '/'.join(relative_parts)
            else:
                # Fallback: use the filename and parent directory
                if len(path_parts) >= 2:
                    relative_path = f"{path_parts[-2]}/{path_parts[-1]}"
                else:
                    relative_path = path_parts[-1]
            
            logger.debug(f"Calculated git_file_path: {relative_path} from {file_path}")
            return relative_path
            
        except Exception as e:
            logger.warning(f"Failed to calculate git file path for {file_path}: {e}")
            # Ultimate fallback
            return file_path.name
    
    def _process_cr_document(self, doc: Dict[str, Any], file_path: Path):
        """Process a single CR document from YAML"""
        try:
            # Extract metadata
            kind = doc.get('kind')
            metadata = doc.get('metadata', {})
            name = metadata.get('name')
            namespace = metadata.get('namespace', 'default')
            
            if not kind or not name:
                self.stats['skipped'] += 1
                return
                
            # Check if this is a supported kind
            if kind not in self.KIND_TO_MODEL:
                self.stats['skipped'] += 1
                logger.debug(f"Skipping unsupported kind: {kind}")
                return
                
            # Get the model class
            model_path = self.KIND_TO_MODEL[kind]
            module_name, class_name = model_path.rsplit('.', 1)
            
            # Import the model
            from .. import models
            model_module = getattr(models, module_name)
            model_class = getattr(model_module, class_name)
            
            # Calculate proper git file path
            git_file_path = self._calculate_git_file_path(file_path)
            
            # Create or update the CR
            with transaction.atomic():
                # Debug logging for SwitchGroup specifically
                if kind == 'SwitchGroup':
                    logger.warning(f"[SYNC DEBUG] Processing SwitchGroup: {name}, namespace: {namespace}, fabric: {self.fabric.name}")
                
                cr, created = model_class.objects.update_or_create(
                    name=name,
                    fabric=self.fabric,
                    namespace=namespace,
                    defaults={
                        'spec': doc.get('spec', {}),
                        'raw_spec': doc.get('spec', {}),
                        'annotations': metadata.get('annotations', {}),
                        'labels': metadata.get('labels', {}),
                        'git_file_path': git_file_path,
                        'last_synced': timezone.now()
                    }
                )
                
                if created:
                    self.stats['created'] += 1
                    logger.info(f"Created {kind} '{name}' from {file_path}")
                    # Extra debug for SwitchGroup
                    if kind == 'SwitchGroup':
                        logger.warning(f"SwitchGroup CREATED: {name} (ID: {cr.pk}) in fabric {self.fabric.name}")
                else:
                    self.stats['updated'] += 1
                    logger.info(f"Updated {kind} '{name}' from {file_path}")
                    # Extra debug for SwitchGroup
                    if kind == 'SwitchGroup':
                        logger.warning(f"SwitchGroup UPDATED: {name} (ID: {cr.pk}) in fabric {self.fabric.name}")
                    
        except Exception as e:
            self.stats['errors'] += 1
            self.errors.append(f"Error processing CR in {file_path}: {str(e)}")
            logger.error(f"Failed to process CR document: {e}")


def sync_fabric_from_git(fabric) -> Dict[str, Any]:
    """
    Convenience function to sync a fabric from its Git repository
    """
    sync = GitDirectorySync(fabric)
    return sync.sync_from_git()