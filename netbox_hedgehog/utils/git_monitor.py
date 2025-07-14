"""
Git Repository Monitor for Hedgehog NetBox Plugin GitOps functionality.

This module provides the GitRepositoryMonitor class that handles:
- Git repository cloning and updating
- YAML discovery and parsing for Hedgehog CRDs
- State synchronization with HedgehogResource model
- Integration with HedgehogFabric GitOps methods

Author: Git Operations Agent
Date: July 8, 2025
"""

import asyncio
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
import tempfile
import shutil
import json

from django.utils import timezone
from django.db import transaction

try:
    import git
    from git import Repo, GitCommandError
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from ..models.fabric import HedgehogFabric
from ..models.gitops import HedgehogResource

logger = logging.getLogger(__name__)


class GitRepositoryError(Exception):
    """Base exception for Git repository operations."""
    pass


class GitAuthenticationError(GitRepositoryError):
    """Authentication error with Git repository."""
    pass


class GitRepositoryNotFoundError(GitRepositoryError):
    """Git repository not found or inaccessible."""
    pass


class YAMLParsingError(GitRepositoryError):
    """Error parsing YAML files."""
    pass


class SyncResult:
    """Result object for synchronization operations."""
    
    def __init__(self):
        self.success = False
        self.message = ""
        self.commit_sha = ""
        self.files_processed = 0
        self.resources_created = 0
        self.resources_updated = 0
        self.errors = []
        self.warnings = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            'success': self.success,
            'message': self.message,
            'commit_sha': self.commit_sha,
            'files_processed': self.files_processed,
            'resources_created': self.resources_created,
            'resources_updated': self.resources_updated,
            'errors': self.errors,
            'warnings': self.warnings,
            'timestamp': timezone.now().isoformat()
        }


class GitStatus:
    """Status object for Git repository information."""
    
    def __init__(self):
        self.configured = False
        self.repository_exists = False
        self.current_commit = ""
        self.current_branch = ""
        self.remote_url = ""
        self.last_sync = None
        self.status = "unknown"
        self.error = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert status to dictionary for serialization."""
        return {
            'configured': self.configured,
            'repository_exists': self.repository_exists,
            'current_commit': self.current_commit,
            'current_branch': self.current_branch,
            'remote_url': self.remote_url,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'status': self.status,
            'error': self.error
        }


class GitRepositoryMonitor:
    """
    Monitors Git repositories for Hedgehog CRD definitions.
    
    This class provides async operations for:
    - Cloning and updating Git repositories
    - Discovering Hedgehog YAML files
    - Parsing and validating CRD definitions
    - Synchronizing desired state to HedgehogResource model
    - Tracking changes and commit history
    """
    
    # Supported Hedgehog CRD types and their API groups
    HEDGEHOG_CRD_TYPES = {
        # VPC API CRDs
        'VPC': 'vpc.githedgehog.com',
        'External': 'vpc.githedgehog.com',
        'ExternalAttachment': 'vpc.githedgehog.com',
        'ExternalPeering': 'vpc.githedgehog.com',
        'IPv4Namespace': 'vpc.githedgehog.com',
        'VPCAttachment': 'vpc.githedgehog.com',
        'VPCPeering': 'vpc.githedgehog.com',
        # Wiring API CRDs
        'Connection': 'wiring.githedgehog.com',
        'Server': 'wiring.githedgehog.com',
        'Switch': 'wiring.githedgehog.com',
        'SwitchGroup': 'wiring.githedgehog.com',
        'VLANNamespace': 'wiring.githedgehog.com',
    }
    
    def __init__(self, fabric: HedgehogFabric):
        """
        Initialize GitRepositoryMonitor for a specific fabric.
        
        Args:
            fabric: HedgehogFabric instance with Git configuration
        """
        if not GIT_AVAILABLE:
            raise ImportError(
                "GitPython is required for Git operations. "
                "Install with: pip install GitPython"
            )
        
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
        
        # Repository configuration
        self.repository_url = fabric.git_repository_url
        self.branch = fabric.git_branch or 'main'
        self.path = fabric.git_path or 'hedgehog/'
        self.username = fabric.git_username
        self.token = fabric.git_token
        
        # Local repository path
        self.repo_dir = None
        self.repo = None
        
        # Session for HTTP operations
        self.session = None
        
        # Validate configuration
        if not self.repository_url:
            raise ValueError("Git repository URL is required")
        
    
    async def __aenter__(self):
        """Async context manager entry."""
        if AIOHTTP_AVAILABLE:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        if self.session:
            await self.session.close()
        
        # Cleanup temporary repository if needed
        if self.repo_dir and Path(self.repo_dir).exists():
            try:
                shutil.rmtree(self.repo_dir)
                self.logger.debug(f"Cleaned up temporary repository: {self.repo_dir}")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup repository {self.repo_dir}: {e}")
    
    def _build_auth_url(self, url: str) -> str:
        """
        Build authenticated Git URL with credentials.
        
        Args:
            url: Original repository URL
            
        Returns:
            Authenticated URL for cloning/fetching
        """
        if not self.username or not self.token:
            return url
        
        # Handle HTTPS URLs
        if url.startswith('https://'):
            # Extract hostname and path
            url_parts = url[8:].split('/', 1)
            if len(url_parts) == 2:
                hostname, path = url_parts
                return f"https://{self.username}:{self.token}@{hostname}/{path}"
        
        # For other URL types, return as-is
        return url
    
    async def clone_or_update_repository(self) -> bool:
        """
        Clone new or update existing Git repository.
        
        Returns:
            True if operation succeeded, False otherwise
            
        Raises:
            GitRepositoryError: If clone/update fails
        """
        try:
            # Create temporary directory for repository
            if not self.repo_dir:
                self.repo_dir = tempfile.mkdtemp(prefix=f'hnp_git_{self.fabric.pk}_')
                self.logger.debug(f"Created temporary directory: {self.repo_dir}")
            
            repo_path = Path(self.repo_dir)
            
            if (repo_path / '.git').exists():
                # Repository exists, update it
                self.logger.info(f"Updating existing repository for fabric {self.fabric.name}")
                return await self._update_repository()
            else:
                # Clone new repository
                self.logger.info(f"Cloning repository for fabric {self.fabric.name}")
                return await self._clone_repository()
                
        except Exception as e:
            error_msg = f"Repository operation failed: {str(e)}"
            self.logger.error(error_msg)
            raise GitRepositoryError(error_msg) from e
    
    async def _clone_repository(self) -> bool:
        """
        Clone Git repository to local directory.
        
        Returns:
            True if clone succeeded
            
        Raises:
            GitRepositoryError: If clone fails
        """
        try:
            auth_url = self._build_auth_url(self.repository_url)
            
            # Clone repository in a thread to avoid blocking
            self.repo = await asyncio.to_thread(
                Repo.clone_from,
                auth_url,
                self.repo_dir,
                branch=self.branch,
                depth=1  # Shallow clone for efficiency
            )
            
            commit_sha = self.repo.head.commit.hexsha
            self.logger.info(f"Successfully cloned repository to {self.repo_dir}, commit: {commit_sha[:8]}")
            
            return True
            
        except GitCommandError as e:
            if "authentication failed" in str(e).lower():
                raise GitAuthenticationError(f"Authentication failed for repository {self.repository_url}")
            elif "not found" in str(e).lower():
                raise GitRepositoryNotFoundError(f"Repository not found: {self.repository_url}")
            else:
                raise GitRepositoryError(f"Git clone failed: {str(e)}")
        
        except Exception as e:
            raise GitRepositoryError(f"Unexpected error during clone: {str(e)}")
    
    async def _update_repository(self) -> bool:
        """
        Update existing Git repository.
        
        Returns:
            True if update succeeded
            
        Raises:
            GitRepositoryError: If update fails
        """
        try:
            self.repo = Repo(self.repo_dir)
            
            # Get current commit before update
            old_commit = self.repo.head.commit.hexsha
            
            # Fetch latest changes
            origin = self.repo.remotes.origin
            await asyncio.to_thread(origin.fetch)
            
            # Reset to latest commit on target branch
            target_ref = f"origin/{self.branch}"
            await asyncio.to_thread(self.repo.git.reset, '--hard', target_ref)
            
            new_commit = self.repo.head.commit.hexsha
            
            if old_commit != new_commit:
                self.logger.info(f"Updated repository from {old_commit[:8]} to {new_commit[:8]}")
            else:
                self.logger.debug("Repository already up to date")
            
            return True
            
        except GitCommandError as e:
            raise GitRepositoryError(f"Git update failed: {str(e)}")
        
        except Exception as e:
            raise GitRepositoryError(f"Unexpected error during update: {str(e)}")
    
    async def discover_yaml_files(self) -> List[Path]:
        """
        Find all YAML files in the repository that contain Hedgehog CRDs.
        
        Returns:
            List of Path objects for YAML files containing Hedgehog CRDs
        """
        if not self.repo_dir:
            raise GitRepositoryError("Repository not initialized")
        
        yaml_files = []
        search_path = Path(self.repo_dir) / self.path.strip('/')
        
        if not search_path.exists():
            self.logger.warning(f"Git path {self.path} does not exist in repository")
            return yaml_files
        
        self.logger.debug(f"Searching for YAML files in {search_path}")
        
        # Search for .yaml and .yml files
        for pattern in ['**/*.yaml', '**/*.yml']:
            for file_path in search_path.glob(pattern):
                if await self._is_hedgehog_yaml(file_path):
                    yaml_files.append(file_path)
                    self.logger.debug(f"Found Hedgehog YAML: {file_path.relative_to(search_path)}")
        
        self.logger.info(f"Discovered {len(yaml_files)} Hedgehog YAML files")
        return yaml_files
    
    async def _is_hedgehog_yaml(self, file_path: Path) -> bool:
        """
        Check if a YAML file contains Hedgehog CRDs.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            True if file contains Hedgehog CRDs
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse all YAML documents in the file
            try:
                documents = yaml.safe_load_all(content)
                for doc in documents:
                    if self._is_hedgehog_crd(doc):
                        return True
            except yaml.YAMLError as e:
                self.logger.warning(f"YAML parsing error in {file_path}: {e}")
                return False
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Error reading file {file_path}: {e}")
            return False
    
    def _is_hedgehog_crd(self, document: Any) -> bool:
        """
        Check if a YAML document is a Hedgehog CRD.
        
        Args:
            document: Parsed YAML document
            
        Returns:
            True if document is a Hedgehog CRD
        """
        if not isinstance(document, dict):
            return False
        
        api_version = document.get('apiVersion', '')
        kind = document.get('kind', '')
        
        # Check if it's a Hedgehog CRD type
        if kind in self.HEDGEHOG_CRD_TYPES:
            expected_api_group = self.HEDGEHOG_CRD_TYPES[kind]
            return expected_api_group in api_version
        
        return False
    
    async def parse_yaml_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Parse and validate a YAML file containing Hedgehog CRDs.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            List of validated CRD documents
            
        Raises:
            YAMLParsingError: If parsing or validation fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            documents = []
            relative_path = file_path.relative_to(Path(self.repo_dir))
            
            try:
                yaml_docs = yaml.safe_load_all(content)
                for doc in yaml_docs:
                    if self._is_hedgehog_crd(doc):
                        # Validate required fields
                        if not self._validate_crd_document(doc):
                            self.logger.warning(f"Invalid CRD document in {relative_path}")
                            continue
                        
                        documents.append(doc)
                        
            except yaml.YAMLError as e:
                raise YAMLParsingError(f"YAML parsing error in {relative_path}: {str(e)}")
            
            self.logger.debug(f"Parsed {len(documents)} CRD documents from {relative_path}")
            return documents
            
        except Exception as e:
            if isinstance(e, YAMLParsingError):
                raise
            raise YAMLParsingError(f"Error parsing {file_path}: {str(e)}")
    
    def _validate_crd_document(self, document: Dict[str, Any]) -> bool:
        """
        Validate a CRD document has required fields.
        
        Args:
            document: CRD document to validate
            
        Returns:
            True if document is valid
        """
        try:
            # Check required top-level fields
            required_fields = ['apiVersion', 'kind', 'metadata']
            for field in required_fields:
                if field not in document:
                    self.logger.warning(f"Missing required field: {field}")
                    return False
            
            # Check metadata fields
            metadata = document.get('metadata', {})
            if not isinstance(metadata, dict):
                self.logger.warning("metadata must be a dictionary")
                return False
            
            if not metadata.get('name'):
                self.logger.warning("metadata.name is required")
                return False
            
            # Validate name format (DNS-1123 compliant)
            name = metadata['name']
            if not self._is_valid_k8s_name(name):
                self.logger.warning(f"Invalid Kubernetes name: {name}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Document validation error: {e}")
            return False
    
    @staticmethod
    def _is_valid_k8s_name(name: str) -> bool:
        """
        Validate Kubernetes resource name (DNS-1123 compliant).
        
        Args:
            name: Name to validate
            
        Returns:
            True if name is valid
        """
        if not name or len(name) > 253:
            return False
        
        import re
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        return bool(re.match(pattern, name))
    
    def get_current_commit(self) -> str:
        """
        Get current commit SHA of the repository.
        
        Returns:
            Current commit SHA or empty string if not available
        """
        try:
            if self.repo:
                return self.repo.head.commit.hexsha
            return ""
        except Exception as e:
            self.logger.warning(f"Failed to get current commit: {e}")
            return ""
    
    async def sync_to_database(self) -> SyncResult:
        """
        Sync discovered resources to HedgehogResource model.
        
        This is the main synchronization method that:
        1. Clones/updates the Git repository
        2. Discovers Hedgehog YAML files
        3. Parses and validates CRD documents
        4. Updates HedgehogResource instances
        5. Triggers drift detection
        
        Returns:
            SyncResult object with operation details
        """
        result = SyncResult()
        
        try:
            # Step 1: Ensure repository is available
            self.logger.info(f"Starting Git sync for fabric {self.fabric.name}")
            
            if not await self.clone_or_update_repository():
                result.message = "Failed to clone or update repository"
                return result
            
            # Get current commit for tracking
            current_commit = self.get_current_commit()
            result.commit_sha = current_commit
            
            # Step 2: Discover YAML files
            yaml_files = await self.discover_yaml_files()
            if not yaml_files:
                result.success = True
                result.message = "No Hedgehog YAML files found in repository"
                return result
            
            # Step 3: Process each YAML file
            total_resources = 0
            created_count = 0
            updated_count = 0
            
            for yaml_file in yaml_files:
                try:
                    # Parse YAML file
                    documents = await self.parse_yaml_file(yaml_file)
                    result.files_processed += 1
                    
                    # Process each CRD document
                    for doc in documents:
                        created, updated = await self._sync_single_resource(
                            doc, yaml_file, current_commit
                        )
                        
                        if created:
                            created_count += 1
                        elif updated:
                            updated_count += 1
                        
                        total_resources += 1
                        
                except Exception as e:
                    error_msg = f"Error processing {yaml_file.name}: {str(e)}"
                    result.errors.append(error_msg)
                    self.logger.error(error_msg)
            
            # Step 4: Update fabric state
            await self._update_fabric_sync_state(current_commit)
            
            # Step 5: Trigger drift detection for fabric
            await self._trigger_fabric_drift_detection()
            
            # Prepare result
            result.success = len(result.errors) == 0
            result.resources_created = created_count
            result.resources_updated = updated_count
            
            if result.success:
                result.message = (
                    f"Successfully synced {total_resources} resources "
                    f"({created_count} created, {updated_count} updated) "
                    f"from {len(yaml_files)} YAML files"
                )
            else:
                result.message = (
                    f"Sync completed with {len(result.errors)} errors. "
                    f"Processed {total_resources} resources from {len(yaml_files)} files."
                )
            
            self.logger.info(result.message)
            
        except Exception as e:
            result.success = False
            result.message = f"Git sync failed: {str(e)}"
            result.errors.append(str(e))
            self.logger.error(result.message)
        
        return result
    
    async def _sync_single_resource(
        self, 
        document: Dict[str, Any], 
        yaml_file: Path, 
        commit_sha: str
    ) -> Tuple[bool, bool]:
        """
        Sync a single CRD resource to the database.
        
        Args:
            document: Parsed YAML document
            yaml_file: Source YAML file path
            commit_sha: Current Git commit SHA
            
        Returns:
            Tuple of (created, updated) booleans
        """
        try:
            # Extract resource information
            metadata = document.get('metadata', {})
            name = metadata.get('name')
            namespace = metadata.get('namespace', 'default')
            kind = document.get('kind')
            spec = document.get('spec', {})
            labels = metadata.get('labels', {})
            annotations = metadata.get('annotations', {})
            
            # Calculate relative file path
            relative_path = yaml_file.relative_to(Path(self.repo_dir))
            
            # Use atomic database transaction
            with transaction.atomic():
                # Get or create HedgehogResource
                resource, created = HedgehogResource.objects.get_or_create(
                    fabric=self.fabric,
                    namespace=namespace,
                    name=name,
                    kind=kind,
                    defaults={
                        'desired_spec': spec,
                        'desired_commit': commit_sha,
                        'desired_file_path': str(relative_path),
                        'desired_updated': timezone.now(),
                        'labels': labels,
                        'annotations': annotations
                    }
                )
                
                updated = False
                if not created:
                    # Update existing resource if spec has changed
                    if (resource.desired_spec != spec or 
                        resource.desired_commit != commit_sha):
                        
                        resource.desired_spec = spec
                        resource.desired_commit = commit_sha
                        resource.desired_file_path = str(relative_path)
                        resource.desired_updated = timezone.now()
                        resource.labels = labels
                        resource.annotations = annotations
                        resource.save(update_fields=[
                            'desired_spec', 'desired_commit', 'desired_file_path',
                            'desired_updated', 'labels', 'annotations'
                        ])
                        updated = True
                
                # Trigger drift detection for this resource
                if created or updated:
                    await asyncio.to_thread(resource.calculate_drift)
                
                self.logger.debug(
                    f"{'Created' if created else 'Updated' if updated else 'Unchanged'} "
                    f"{kind}/{name} in namespace {namespace}"
                )
                
                return created, updated
                
        except Exception as e:
            self.logger.error(f"Failed to sync resource {kind}/{name}: {e}")
            raise
    
    async def _update_fabric_sync_state(self, commit_sha: str) -> None:
        """
        Update fabric with current sync state.
        
        Args:
            commit_sha: Current Git commit SHA
        """
        try:
            # Use database update to avoid triggering change logs
            HedgehogFabric.objects.filter(pk=self.fabric.pk).update(
                desired_state_commit=commit_sha,
                last_git_sync=timezone.now()
            )
            
            # Refresh fabric instance
            self.fabric.refresh_from_db(fields=['desired_state_commit', 'last_git_sync'])
            
        except Exception as e:
            self.logger.error(f"Failed to update fabric sync state: {e}")
    
    async def _trigger_fabric_drift_detection(self) -> None:
        """
        Trigger drift detection for the entire fabric.
        
        This updates the fabric's drift_status and drift_count fields
        based on the current state of all HedgehogResource instances.
        """
        try:
            # Get all resources for this fabric
            resources = await asyncio.to_thread(
                list,
                HedgehogResource.objects.filter(fabric=self.fabric)
            )
            
            # Count resources with drift
            drift_count = 0
            for resource in resources:
                if resource.drift_status != 'in_sync':
                    drift_count += 1
            
            # Determine overall drift status
            if drift_count == 0:
                overall_status = 'in_sync'
            else:
                overall_status = 'drift_detected'
            
            # Update fabric drift information
            HedgehogFabric.objects.filter(pk=self.fabric.pk).update(
                drift_status=overall_status,
                drift_count=drift_count
            )
            
            # Refresh fabric instance
            self.fabric.refresh_from_db(fields=['drift_status', 'drift_count'])
            
            self.logger.debug(
                f"Updated fabric drift status: {overall_status} "
                f"({drift_count} resources with drift)"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update fabric drift status: {e}")
    
    def get_repository_status(self) -> GitStatus:
        """
        Get current repository status and health information.
        
        Returns:
            GitStatus object with current repository state
        """
        status = GitStatus()
        
        try:
            # Check if Git is configured
            status.configured = bool(self.repository_url)
            
            if not status.configured:
                status.status = "not_configured"
                return status
            
            # Check if repository exists locally
            if self.repo_dir and Path(self.repo_dir).exists():
                status.repository_exists = True
                
                if self.repo:
                    status.current_commit = self.get_current_commit()
                    status.current_branch = str(self.repo.active_branch)
                    status.remote_url = self.repository_url
                    status.status = "ready"
                else:
                    status.status = "not_initialized"
            else:
                status.status = "not_cloned"
            
            status.last_sync = self.fabric.last_git_sync
            
        except Exception as e:
            status.status = "error"
            status.error = str(e)
            self.logger.error(f"Error getting repository status: {e}")
        
        return status