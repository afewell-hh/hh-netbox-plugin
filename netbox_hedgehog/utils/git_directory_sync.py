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
                self.fabric.last_sync = timezone.now()
                self.fabric.sync_status = 'synced' if self.stats['errors'] == 0 else 'error'
                self.fabric.save()
                
                return {
                    'success': True,
                    'message': f"Sync completed: {self.stats['created']} created, {self.stats['updated']} updated, {self.stats['errors']} errors",
                    'stats': self.stats,
                    'errors': self.errors
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
                
            # Clone repository
            cmd = ['git', 'clone', '--depth', '1', '--branch', branch, auth_url, str(path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f'Git clone failed: {result.stderr}'
                }
                
            return {'success': True}
            
        except Exception as e:
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
    
    def _process_cr_document(self, doc: Dict[str, Any], file_path: Path):
        """Process a single CR document from YAML"""
        try:
            # Extract metadata
            kind = doc.get('kind')
            metadata = doc.get('metadata', {})
            name = metadata.get('name')
            
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
            
            # Create or update the CR
            with transaction.atomic():
                cr, created = model_class.objects.update_or_create(
                    name=name,
                    fabric=self.fabric,
                    defaults={
                        'spec': doc.get('spec', {}),
                        'raw_spec': doc.get('spec', {}),
                        'annotations': metadata.get('annotations', {}),
                        'labels': metadata.get('labels', {}),
                        'git_file_path': str(file_path.relative_to(file_path.parent.parent.parent)),
                        'last_synced': timezone.now()
                    }
                )
                
                if created:
                    self.stats['created'] += 1
                    logger.info(f"Created {kind} '{name}' from {file_path}")
                else:
                    self.stats['updated'] += 1
                    logger.info(f"Updated {kind} '{name}' from {file_path}")
                    
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