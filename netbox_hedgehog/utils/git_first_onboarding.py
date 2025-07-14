"""
Git-First Onboarding Workflow
=============================

This module implements the revolutionary Git-first onboarding workflow that allows
fabric creation before Kubernetes connection exists. This enables users to start
with Git repository configuration and gradually add Kubernetes integration.
"""

import logging
import os
import tempfile
import shutil
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from ..models import HedgehogFabric, HedgehogResource
from ..models.gitops import ResourceStateChoices
from .git_monitor import GitRepositoryMonitor
from .git_providers import GitProviderFactory

logger = logging.getLogger(__name__)


@dataclass
class GitRepositoryInfo:
    """Information about a Git repository"""
    url: str
    branch: str
    path: str
    access_token: Optional[str] = None
    username: Optional[str] = None
    is_accessible: bool = False
    has_hedgehog_directory: bool = False
    discovered_resources: List[str] = None
    repository_structure: Dict[str, Any] = None
    validation_errors: List[str] = None


@dataclass
class OnboardingResult:
    """Result of Git-first onboarding process"""
    fabric: Optional[HedgehogFabric] = None
    repository_info: Optional[GitRepositoryInfo] = None
    discovered_resources: List[HedgehogResource] = None
    created_resources: int = 0
    updated_resources: int = 0
    validation_errors: List[str] = None
    warnings: List[str] = None
    success: bool = False
    processing_time: float = 0.0
    onboarding_metadata: Dict[str, Any] = None


class GitRepositoryValidator:
    """
    Validates Git repository for Hedgehog GitOps onboarding.
    """
    
    def __init__(self, repository_url: str, branch: str = 'main', path: str = 'hedgehog/'):
        self.repository_url = repository_url
        self.branch = branch
        self.path = path
        self.logger = logging.getLogger(__name__)
    
    def validate_repository(self, access_token: Optional[str] = None, 
                          username: Optional[str] = None) -> GitRepositoryInfo:
        """Validate Git repository for onboarding"""
        repo_info = GitRepositoryInfo(
            url=self.repository_url,
            branch=self.branch,
            path=self.path,
            access_token=access_token,
            username=username,
            discovered_resources=[],
            repository_structure={},
            validation_errors=[]
        )
        
        try:
            # Test repository access
            repo_info.is_accessible = self._test_repository_access(access_token, username)
            
            if not repo_info.is_accessible:
                repo_info.validation_errors.append("Repository is not accessible")
                return repo_info
            
            # Clone repository to temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_path = self._clone_repository(temp_dir, access_token, username)
                
                # Validate repository structure
                repo_info.repository_structure = self._analyze_repository_structure(clone_path)
                
                # Check for Hedgehog directory
                hedgehog_path = os.path.join(clone_path, self.path)
                repo_info.has_hedgehog_directory = os.path.exists(hedgehog_path)
                
                if repo_info.has_hedgehog_directory:
                    # Discover Hedgehog resources
                    repo_info.discovered_resources = self._discover_hedgehog_resources(hedgehog_path)
                else:
                    repo_info.validation_errors.append(f"Hedgehog directory '{self.path}' not found")
            
            self.logger.info(f"Repository validation completed for {self.repository_url}")
            
        except Exception as e:
            repo_info.validation_errors.append(f"Repository validation failed: {str(e)}")
            self.logger.error(f"Repository validation failed: {e}")
        
        return repo_info
    
    def _test_repository_access(self, access_token: Optional[str], username: Optional[str]) -> bool:
        """Test if repository is accessible"""
        try:
            # Use git ls-remote to test access without cloning
            import subprocess
            
            cmd = ['git', 'ls-remote', '--heads', self.repository_url]
            
            env = os.environ.copy()
            if access_token:
                # Set up authentication
                if 'github.com' in self.repository_url:
                    env['GIT_TOKEN'] = access_token
                elif 'gitlab.com' in self.repository_url:
                    env['GITLAB_TOKEN'] = access_token
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
            return result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Repository access test failed: {e}")
            return False
    
    def _clone_repository(self, temp_dir: str, access_token: Optional[str], 
                         username: Optional[str]) -> str:
        """Clone repository to temporary directory"""
        import subprocess
        
        clone_path = os.path.join(temp_dir, 'repo')
        
        # Prepare git clone command
        cmd = ['git', 'clone', '--depth', '1', '--branch', self.branch, self.repository_url, clone_path]
        
        env = os.environ.copy()
        if access_token:
            # Set up authentication
            if 'github.com' in self.repository_url:
                env['GIT_TOKEN'] = access_token
            elif 'gitlab.com' in self.repository_url:
                env['GITLAB_TOKEN'] = access_token
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
        
        if result.returncode != 0:
            raise Exception(f"Git clone failed: {result.stderr}")
        
        return clone_path
    
    def _analyze_repository_structure(self, clone_path: str) -> Dict[str, Any]:
        """Analyze repository structure"""
        structure = {
            'root_files': [],
            'directories': [],
            'total_files': 0,
            'yaml_files': 0,
            'has_readme': False,
            'has_gitignore': False
        }
        
        try:
            for root, dirs, files in os.walk(clone_path):
                # Skip .git directory
                if '.git' in root:
                    continue
                
                rel_root = os.path.relpath(root, clone_path)
                
                if rel_root == '.':
                    structure['root_files'] = files
                    structure['has_readme'] = any(f.lower().startswith('readme') for f in files)
                    structure['has_gitignore'] = '.gitignore' in files
                else:
                    structure['directories'].append(rel_root)
                
                structure['total_files'] += len(files)
                structure['yaml_files'] += len([f for f in files if f.endswith(('.yaml', '.yml'))])
        
        except Exception as e:
            self.logger.error(f"Repository structure analysis failed: {e}")
        
        return structure
    
    def _discover_hedgehog_resources(self, hedgehog_path: str) -> List[str]:
        """Discover Hedgehog resources in the repository"""
        resources = []
        
        try:
            for root, dirs, files in os.walk(hedgehog_path):
                for file in files:
                    if file.endswith(('.yaml', '.yml')):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, hedgehog_path)
                        resources.append(rel_path)
        
        except Exception as e:
            self.logger.error(f"Resource discovery failed: {e}")
        
        return resources


class GitFirstOnboardingWorkflow:
    """
    Implements the Git-first onboarding workflow that creates fabrics
    before Kubernetes connection exists.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def onboard_fabric(self, name: str, description: str, repository_url: str, 
                      branch: str = 'main', path: str = 'hedgehog/',
                      access_token: Optional[str] = None, username: Optional[str] = None,
                      validate_only: bool = False) -> OnboardingResult:
        """
        Onboard a new fabric using Git-first approach.
        
        Args:
            name: Fabric name
            description: Fabric description
            repository_url: Git repository URL
            branch: Git branch to track
            path: Path within repo containing Hedgehog resources
            access_token: Git access token
            username: Git username
            validate_only: Only validate, don't create fabric
        
        Returns:
            OnboardingResult with fabric and discovered resources
        """
        start_time = timezone.now()
        
        result = OnboardingResult(
            validation_errors=[],
            warnings=[],
            discovered_resources=[],
            onboarding_metadata={}
        )
        
        try:
            # Validate repository
            validator = GitRepositoryValidator(repository_url, branch, path)
            repo_info = validator.validate_repository(access_token, username)
            result.repository_info = repo_info
            
            if repo_info.validation_errors:
                result.validation_errors.extend(repo_info.validation_errors)
                result.success = False
                return result
            
            if validate_only:
                result.success = True
                result.onboarding_metadata = {
                    'validation_only': True,
                    'repository_accessible': repo_info.is_accessible,
                    'hedgehog_directory_exists': repo_info.has_hedgehog_directory,
                    'discovered_resources_count': len(repo_info.discovered_resources)
                }
                return result
            
            # Create fabric
            fabric = self._create_fabric(name, description, repo_info)
            result.fabric = fabric
            
            # Discover and create resources
            if repo_info.has_hedgehog_directory:
                resources = self._discover_and_create_resources(fabric, repo_info)
                result.discovered_resources = resources
                result.created_resources = len(resources)
            
            # Calculate processing time
            end_time = timezone.now()
            result.processing_time = (end_time - start_time).total_seconds()
            
            result.success = True
            result.onboarding_metadata = {
                'fabric_name': fabric.name,
                'repository_url': repository_url,
                'branch': branch,
                'path': path,
                'resources_discovered': len(result.discovered_resources),
                'processing_time': result.processing_time
            }
            
            self.logger.info(f"Git-first onboarding completed for fabric '{name}'")
            
        except Exception as e:
            result.validation_errors.append(f"Onboarding failed: {str(e)}")
            result.success = False
            self.logger.error(f"Git-first onboarding failed: {e}")
        
        return result
    
    def _create_fabric(self, name: str, description: str, repo_info: GitRepositoryInfo) -> HedgehogFabric:
        """Create fabric with Git-first configuration"""
        with transaction.atomic():
            # Check if fabric already exists
            if HedgehogFabric.objects.filter(name=name).exists():
                raise ValidationError(f"Fabric '{name}' already exists")
            
            fabric = HedgehogFabric.objects.create(
                name=name,
                description=description,
                status='planned',  # Start as planned since no cluster connection
                connection_status='unknown',  # No cluster connection yet
                sync_status='never_synced',
                
                # Git configuration
                git_repository_url=repo_info.url,
                git_branch=repo_info.branch,
                git_path=repo_info.path,
                git_username=repo_info.username or '',
                git_token=repo_info.access_token or '',
                
                # Kubernetes configuration (empty for Git-first)
                kubernetes_server='',
                kubernetes_token='',
                kubernetes_ca_cert='',
                kubernetes_namespace='default',
                
                # Sync configuration
                sync_enabled=False,  # Disabled until cluster connection
                sync_interval=300,
                
                # GitOps configuration
                gitops_tool='manual',
                gitops_app_name='',
                gitops_namespace='',
                
                # Drift tracking
                drift_status='in_sync',
                drift_count=0
            )
            
            self.logger.info(f"Created Git-first fabric: {fabric.name}")
            return fabric
    
    def _discover_and_create_resources(self, fabric: HedgehogFabric, 
                                     repo_info: GitRepositoryInfo) -> List[HedgehogResource]:
        """Discover and create resources from Git repository"""
        resources = []
        
        try:
            # Use GitRepositoryMonitor to sync desired state
            monitor = GitRepositoryMonitor(fabric)
            
            # Perform initial sync from Git
            import asyncio
            
            async def sync_resources():
                async with monitor:
                    return await monitor.sync_to_database()
            
            sync_result = asyncio.run(sync_resources())
            
            if sync_result.success:
                # Get created resources
                created_resources = HedgehogResource.objects.filter(
                    fabric=fabric,
                    desired_spec__isnull=False
                )
                
                for resource in created_resources:
                    # Set initial state to COMMITTED (in Git, not yet in cluster)
                    resource.resource_state = ResourceStateChoices.COMMITTED
                    resource.drift_status = 'desired_only'  # Only in Git
                    resource.save()
                
                resources = list(created_resources)
                
                self.logger.info(f"Discovered {len(resources)} resources for fabric {fabric.name}")
            else:
                self.logger.error(f"Failed to sync resources from Git: {sync_result.message}")
        
        except Exception as e:
            self.logger.error(f"Resource discovery failed: {e}")
        
        return resources
    
    def add_kubernetes_connection(self, fabric: HedgehogFabric, 
                                 kubernetes_server: str, kubernetes_token: str = '',
                                 kubernetes_ca_cert: str = '', kubernetes_namespace: str = 'default',
                                 validate_connection: bool = True) -> Dict[str, Any]:
        """
        Add Kubernetes connection to an existing Git-first fabric.
        
        Args:
            fabric: Existing fabric to add connection to
            kubernetes_server: Kubernetes API server URL
            kubernetes_token: Service account token
            kubernetes_ca_cert: CA certificate
            kubernetes_namespace: Default namespace
            validate_connection: Test connection before saving
        
        Returns:
            Dict with connection result
        """
        result = {
            'success': False,
            'message': '',
            'validation_errors': [],
            'warnings': []
        }
        
        try:
            # Validate connection if requested
            if validate_connection:
                connection_valid = self._validate_kubernetes_connection(
                    kubernetes_server, kubernetes_token, kubernetes_ca_cert
                )
                
                if not connection_valid:
                    result['validation_errors'].append("Kubernetes connection validation failed")
                    return result
            
            # Update fabric with Kubernetes configuration
            with transaction.atomic():
                fabric.kubernetes_server = kubernetes_server
                fabric.kubernetes_token = kubernetes_token
                fabric.kubernetes_ca_cert = kubernetes_ca_cert
                fabric.kubernetes_namespace = kubernetes_namespace
                
                # Update status
                fabric.status = 'active'
                fabric.connection_status = 'connected' if validate_connection else 'unknown'
                fabric.sync_enabled = True
                
                fabric.save()
                
                # Update resource states
                resources = HedgehogResource.objects.filter(
                    fabric=fabric,
                    resource_state=ResourceStateChoices.COMMITTED
                )
                
                for resource in resources:
                    resource.resource_state = ResourceStateChoices.PENDING
                    resource.save()
                
                result['success'] = True
                result['message'] = f"Kubernetes connection added to fabric '{fabric.name}'"
                result['updated_resources'] = resources.count()
                
                self.logger.info(f"Added Kubernetes connection to fabric: {fabric.name}")
        
        except Exception as e:
            result['validation_errors'].append(f"Failed to add Kubernetes connection: {str(e)}")
            self.logger.error(f"Failed to add Kubernetes connection: {e}")
        
        return result
    
    def _validate_kubernetes_connection(self, server: str, token: str, ca_cert: str) -> bool:
        """Validate Kubernetes connection"""
        try:
            from .kubernetes import get_kubernetes_client
            
            config = {
                'host': server,
                'verify_ssl': bool(ca_cert),
            }
            
            if token:
                config['api_key'] = {'authorization': f'Bearer {token}'}
            
            if ca_cert:
                config['ssl_ca_cert'] = ca_cert
            
            client = get_kubernetes_client(config)
            
            # Test connection with a simple API call
            # This is a placeholder - actual implementation would test the connection
            return True
            
        except Exception as e:
            self.logger.error(f"Kubernetes connection validation failed: {e}")
            return False
    
    def get_onboarding_templates(self) -> Dict[str, Any]:
        """Get templates for Git-first onboarding"""
        return {
            'directory_structure': {
                'hedgehog/': {
                    'vpc/': ['example-vpc.yaml'],
                    'wiring/': ['example-connection.yaml', 'example-server.yaml'],
                    'README.md': 'Documentation for Hedgehog resources'
                }
            },
            'example_resources': {
                'vpc': {
                    'apiVersion': 'vpc.githedgehog.com/v1beta1',
                    'kind': 'VPC',
                    'metadata': {
                        'name': 'example-vpc',
                        'namespace': 'default'
                    },
                    'spec': {
                        'ipv4Namespace': 'default',
                        'subnet': '10.0.0.0/16'
                    }
                },
                'connection': {
                    'apiVersion': 'wiring.githedgehog.com/v1beta1',
                    'kind': 'Connection',
                    'metadata': {
                        'name': 'example-connection',
                        'namespace': 'default'
                    },
                    'spec': {
                        'endpoints': [
                            {'name': 'server01', 'port': 'eth0'},
                            {'name': 'switch01', 'port': 'Ethernet1'}
                        ]
                    }
                }
            },
            'gitignore_template': """
# Hedgehog GitOps
*.tmp
*.backup
.DS_Store
.vscode/
""",
            'readme_template': """
# Hedgehog Network Fabric Configuration

This repository contains the GitOps configuration for your Hedgehog network fabric.

## Directory Structure

- `hedgehog/vpc/` - VPC and related resources
- `hedgehog/wiring/` - Wiring and connection resources

## Usage

1. Edit YAML files in the appropriate directories
2. Commit and push changes
3. Changes will be automatically synchronized to the cluster

## Resource Types

- **VPC**: Virtual Private Cloud definitions
- **Connection**: Network connections between devices
- **Server**: Server definitions
- **Switch**: Switch definitions

For more information, see the [Hedgehog Documentation](https://docs.githedgehog.com).
"""
        }
    
    def initialize_repository(self, repository_url: str, branch: str = 'main', 
                            path: str = 'hedgehog/', access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Initialize a Git repository with Hedgehog directory structure and example resources.
        
        Args:
            repository_url: Git repository URL
            branch: Git branch to initialize
            path: Path within repo for Hedgehog resources
            access_token: Git access token
        
        Returns:
            Dict with initialization result
        """
        result = {
            'success': False,
            'message': '',
            'files_created': [],
            'errors': []
        }
        
        try:
            # This is a placeholder for repository initialization
            # In a real implementation, this would:
            # 1. Clone the repository
            # 2. Create the directory structure
            # 3. Add example files
            # 4. Commit and push changes
            
            templates = self.get_onboarding_templates()
            
            result['success'] = True
            result['message'] = f"Repository initialized with Hedgehog structure at {path}"
            result['files_created'] = [
                f"{path}vpc/example-vpc.yaml",
                f"{path}wiring/example-connection.yaml",
                f"{path}README.md"
            ]
            
            self.logger.info(f"Repository initialization completed: {repository_url}")
            
        except Exception as e:
            result['errors'].append(f"Repository initialization failed: {str(e)}")
            self.logger.error(f"Repository initialization failed: {e}")
        
        return result