"""
Git Sync Service
Business logic for Git synchronization operations following clean architecture
"""

import os
import yaml
import tempfile
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import subprocess
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from ...domain.interfaces.git_service_interface import GitServiceInterface, GitSyncResult, GitReference
from ...domain.interfaces.fabric_service_interface import FabricServiceInterface, SyncResult, FabricStats

logger = logging.getLogger(__name__)


class GitSyncService:
    """
    Service for Git synchronization operations.
    Implements business logic for syncing CRDs from Git repositories.
    """
    
    # Mapping of Kubernetes kinds to HNP model classes
    KIND_TO_MODEL = {
        'VPC': 'VPC',
        'External': 'External',
        'ExternalAttachment': 'ExternalAttachment',
        'ExternalPeering': 'ExternalPeering',
        'IPv4Namespace': 'IPv4Namespace',
        'VPCAttachment': 'VPCAttachment',
        'VPCPeering': 'VPCPeering',
        'Connection': 'Connection',
        'Server': 'Server',
        'Switch': 'Switch',
        'SwitchGroup': 'SwitchGroup',
        'VLANNamespace': 'VLANNamespace',
    }
    
    def __init__(self, git_service: Optional[GitServiceInterface] = None):
        """
        Initialize Git sync service.
        
        Args:
            git_service: Git service implementation (optional, can be injected later)
        """
        self.git_service = git_service
        self.stats = {
            'scanned': 0,
            'created': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }
    
    def sync_fabric_from_git(self, fabric) -> SyncResult:
        """
        Synchronize fabric CRDs from Git repository.
        
        Args:
            fabric: HedgehogFabric instance
            
        Returns:
            SyncResult with operation details
        """
        if not fabric.git_repository_url:
            return SyncResult(
                success=False,
                stats=FabricStats(
                    total_crds=0, active_crds=0, error_crds=0,
                    sync_status="not_configured", drift_count=0, last_sync=None
                ),
                errors=["Fabric has no Git repository configured"],
                details={}
            )
        
        try:
            with transaction.atomic():
                # Create temporary directory for cloning
                with tempfile.TemporaryDirectory(prefix=f"git_sync_{fabric.pk}_") as temp_dir:
                    repo_path = os.path.join(temp_dir, "repo")
                    
                    # Clone repository
                    git_ref = self._clone_repository(fabric, repo_path)
                    
                    # Find and process YAML files
                    yaml_files = self._find_yaml_files(repo_path, fabric.git_path or "")
                    manifests = self._parse_yaml_files(yaml_files)
                    
                    # Create/update CRDs
                    crd_results = self._process_manifests(fabric, manifests)
                    
                    # Update fabric sync status
                    fabric.last_git_sync = timezone.now()
                    if hasattr(fabric, 'desired_state_commit'):
                        fabric.desired_state_commit = git_ref.commit_sha
                    fabric.save(update_fields=['last_git_sync'])
                    
                    # Calculate final statistics
                    stats = self._calculate_fabric_stats(fabric)
                    
                    logger.info(f"Git sync completed for fabric {fabric.name}: {crd_results}")
                    
                    return SyncResult(
                        success=True,
                        stats=stats,
                        errors=[],
                        details={
                            'commit_sha': git_ref.commit_sha,
                            'files_processed': len(yaml_files),
                            'manifests_found': len(manifests),
                            **crd_results
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Git sync failed for fabric {fabric.name}: {e}")
            return SyncResult(
                success=False,
                stats=self._calculate_fabric_stats(fabric),
                errors=[str(e)],
                details={}
            )
    
    def _clone_repository(self, fabric, repo_path: str) -> GitReference:
        """Clone Git repository to local path."""
        if self.git_service:
            # Use injected Git service
            return self.git_service.clone_repository(
                fabric.git_repository_url,
                fabric.git_branch or 'main',
                repo_path,
                fabric.git_username,
                fabric.git_token
            )
        else:
            # Fallback to direct git operations (temporary)
            return self._direct_git_clone(fabric, repo_path)
    
    def _direct_git_clone(self, fabric, repo_path: str) -> GitReference:
        """Direct git clone implementation (fallback)."""
        try:
            # Simple git clone command
            cmd = ['git', 'clone', '-b', fabric.git_branch or 'main', 
                   fabric.git_repository_url, repo_path]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                raise Exception(f"Git clone failed: {result.stderr}")
            
            # Get latest commit
            commit_cmd = ['git', '-C', repo_path, 'rev-parse', 'HEAD']
            commit_result = subprocess.run(commit_cmd, capture_output=True, text=True)
            commit_sha = commit_result.stdout.strip()
            
            return GitReference(
                commit_sha=commit_sha,
                branch=fabric.git_branch or 'main',
                local_path=repo_path,
                repository_url=fabric.git_repository_url
            )
            
        except Exception as e:
            logger.error(f"Direct git clone failed: {e}")
            raise
    
    def _find_yaml_files(self, repo_path: str, git_path: str) -> List[str]:
        """Find YAML files in repository directory."""
        yaml_files = []
        search_dir = os.path.join(repo_path, git_path) if git_path else repo_path
        
        if not os.path.exists(search_dir):
            logger.warning(f"Git path {git_path} not found in repository")
            return []
        
        # Search for YAML files recursively
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file.endswith(('.yaml', '.yml')):
                    yaml_files.append(os.path.join(root, file))
        
        logger.info(f"Found {len(yaml_files)} YAML files in {search_dir}")
        return yaml_files
    
    def _parse_yaml_files(self, yaml_files: List[str]) -> List[Dict[str, Any]]:
        """Parse YAML files into manifests."""
        manifests = []
        
        for file_path in yaml_files:
            try:
                with open(file_path, 'r') as f:
                    # Handle multiple documents in single file
                    documents = yaml.safe_load_all(f)
                    for doc in documents:
                        if doc and isinstance(doc, dict):
                            # Add file path for tracking
                            doc['_file_path'] = file_path
                            manifests.append(doc)
                            
            except Exception as e:
                logger.error(f"Failed to parse YAML file {file_path}: {e}")
                continue
        
        logger.info(f"Parsed {len(manifests)} manifests from YAML files")
        return manifests
    
    def _process_manifests(self, fabric, manifests: List[Dict[str, Any]]) -> Dict[str, int]:
        """Process manifests and create/update CRDs."""
        results = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        for manifest in manifests:
            try:
                # Extract Kubernetes metadata
                kind = manifest.get('kind')
                metadata = manifest.get('metadata', {})
                name = metadata.get('name')
                namespace = metadata.get('namespace', 'default')
                
                if not kind or not name:
                    logger.warning(f"Skipping manifest missing kind or name: {manifest.get('_file_path', 'unknown')}")
                    results['skipped'] += 1
                    continue
                
                # Check if this is a Hedgehog CRD
                if kind not in self.KIND_TO_MODEL:
                    logger.debug(f"Skipping non-Hedgehog CRD: {kind}")
                    results['skipped'] += 1
                    continue
                
                # Create or update CRD
                if self._create_or_update_crd(fabric, kind, name, namespace, manifest):
                    # Check if it was created or updated by querying the model
                    results['created'] += 1  # Simplified - would need more logic to determine create vs update
                else:
                    results['errors'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to process manifest: {e}")
                results['errors'] += 1
        
        return results
    
    def _create_or_update_crd(self, fabric, kind: str, name: str, namespace: str, manifest: Dict[str, Any]) -> bool:
        """Create or update a specific CRD."""
        try:
            from django.apps import apps
            
            # Get the model class
            model_name = self.KIND_TO_MODEL.get(kind)
            if not model_name:
                return False
            
            model_class = apps.get_model('netbox_hedgehog', model_name)
            
            # Prepare CRD data
            crd_data = {
                'fabric': fabric,
                'name': name,
                'namespace': namespace,
                'spec': manifest.get('spec', {}),
                'labels': manifest.get('metadata', {}).get('labels', {}),
                'annotations': manifest.get('metadata', {}).get('annotations', {}),
            }
            
            # Add Git tracking fields if they exist
            if hasattr(model_class, 'git_file_path'):
                crd_data['git_file_path'] = manifest.get('_file_path', '')
            if hasattr(model_class, 'raw_spec'):
                crd_data['raw_spec'] = yaml.dump(manifest)
            
            # Create or update
            crd, created = model_class.objects.update_or_create(
                fabric=fabric,
                name=name,
                namespace=namespace,
                defaults=crd_data
            )
            
            if created:
                logger.info(f"Created {kind}/{name} in namespace {namespace}")
            else:
                logger.info(f"Updated {kind}/{name} in namespace {namespace}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create/update {kind}/{name}: {e}")
            return False
    
    def _calculate_fabric_stats(self, fabric) -> FabricStats:
        """Calculate current fabric statistics."""
        try:
            # Use fabric's existing methods if available
            total_crds = fabric.crd_count if hasattr(fabric, 'crd_count') else 0
            active_crds = fabric.active_crd_count if hasattr(fabric, 'active_crd_count') else 0
            error_crds = fabric.error_crd_count if hasattr(fabric, 'error_crd_count') else 0
            
            return FabricStats(
                total_crds=total_crds,
                active_crds=active_crds,
                error_crds=error_crds,
                sync_status=fabric.sync_status,
                drift_count=getattr(fabric, 'drift_count', 0),
                last_sync=fabric.last_git_sync.isoformat() if fabric.last_git_sync else None
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate fabric stats: {e}")
            return FabricStats(
                total_crds=0, active_crds=0, error_crds=0,
                sync_status="error", drift_count=0, last_sync=None
            )