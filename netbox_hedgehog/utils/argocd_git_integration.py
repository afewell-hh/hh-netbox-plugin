"""
ArgoCD Git Integration for Hedgehog NetBox Plugin

This module provides automatic Git repository configuration for ArgoCD installations.
It leverages existing HedgehogFabric Git authentication settings to configure
ArgoCD repositories without requiring users to duplicate credentials.

Features:
- Automatic repository credential configuration
- Integration with existing Git providers (GitHub, GitLab, Bitbucket)
- Repository validation and health checks
- Webhook configuration for automatic synchronization
- Support for SSH and token-based authentication
"""

import logging
import json
import asyncio
import base64
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

try:
    from kubernetes import client
    from kubernetes.client.rest import ApiException
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class GitRepositoryConfig:
    """Configuration for Git repository in ArgoCD"""
    name: str
    url: str
    username: str = ""
    password: str = ""
    ssh_private_key: str = ""
    tls_client_cert_data: str = ""
    tls_client_cert_key: str = ""
    insecure: bool = False
    enable_lfs: bool = False
    enable_git_submodule: bool = False
    repository_type: str = "git"
    

@dataclass
class GitWebhookConfig:
    """Configuration for Git webhook setup"""
    webhook_url: str
    secret: str = ""
    events: List[str] = None
    
    def __post_init__(self):
        if self.events is None:
            self.events = ["push", "pull_request"]


class ArgoCDGitIntegrator:
    """
    Manages Git repository integration with ArgoCD.
    
    Handles:
    - Repository credential configuration
    - Repository registration in ArgoCD
    - Webhook setup for automatic synchronization
    - Repository health monitoring
    """
    
    def __init__(self, fabric, argocd_installer):
        """
        Initialize Git integrator.
        
        Args:
            fabric: HedgehogFabric instance
            argocd_installer: ArgoCDInstaller instance
        """
        self.fabric = fabric
        self.argocd_installer = argocd_installer
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
        
        if not KUBERNETES_AVAILABLE:
            raise ImportError(
                "Kubernetes client library not available. "
                "Install with: pip install kubernetes"
            )
    
    async def configure_git_repository(self, repository_config: Optional[GitRepositoryConfig] = None) -> Dict[str, Any]:
        """
        Configure Git repository in ArgoCD using fabric's Git settings.
        
        Args:
            repository_config: Optional repository configuration overrides
            
        Returns:
            Configuration result dict
        """
        try:
            self.logger.info("Configuring Git repository in ArgoCD...")
            
            # Validate ArgoCD is installed
            status = await self.argocd_installer.check_argocd_installation()
            if not status.installed:
                return {
                    'success': False,
                    'error': 'ArgoCD is not installed'
                }
            
            # Get repository configuration
            if not repository_config:
                repository_config = self._build_repository_config_from_fabric()
            
            if not repository_config:
                return {
                    'success': False,
                    'error': 'No Git repository configuration available'
                }
            
            # Create repository secret
            secret_result = await self._create_repository_secret(repository_config)
            if not secret_result['success']:
                return secret_result
            
            # Register repository in ArgoCD
            repo_result = await self._register_repository_in_argocd(repository_config)
            if not repo_result['success']:
                return repo_result
            
            # Validate repository connection
            validation_result = await self._validate_repository_connection(repository_config)
            if not validation_result['success']:
                self.logger.warning(f"Repository validation warning: {validation_result.get('error')}")
            
            self.logger.info("Git repository configured successfully in ArgoCD")
            
            return {
                'success': True,
                'message': 'Git repository configured successfully',
                'repository_name': repository_config.name,
                'repository_url': repository_config.url,
                'secret_name': f'repo-{repository_config.name}',
                'validation_result': validation_result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to configure Git repository: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Git repository configuration failed'
            }
    
    def _build_repository_config_from_fabric(self) -> Optional[GitRepositoryConfig]:
        """Build repository configuration from fabric Git settings"""
        if not self.fabric.git_repository_url:
            return None
        
        # Extract repository name from URL
        repo_name = self._extract_repository_name(self.fabric.git_repository_url)
        
        return GitRepositoryConfig(
            name=repo_name,
            url=self.fabric.git_repository_url,
            username=self.fabric.git_username or 'hedgehog-netbox',
            password=self.fabric.git_token or '',
            insecure=False,  # Always use secure connections
            enable_lfs=True,  # Enable Git LFS by default
            enable_git_submodule=False
        )
    
    def _extract_repository_name(self, repository_url: str) -> str:
        """Extract repository name from Git URL"""
        try:
            # Handle different URL formats
            if repository_url.endswith('.git'):
                repository_url = repository_url[:-4]
            
            # Extract name from various URL formats
            if 'github.com' in repository_url:
                parts = repository_url.split('/')
                if len(parts) >= 2:
                    return f"github-{parts[-2]}-{parts[-1]}"
            elif 'gitlab.com' in repository_url:
                parts = repository_url.split('/')
                if len(parts) >= 2:
                    return f"gitlab-{parts[-2]}-{parts[-1]}"
            elif 'bitbucket.org' in repository_url:
                parts = repository_url.split('/')
                if len(parts) >= 2:
                    return f"bitbucket-{parts[-2]}-{parts[-1]}"
            else:
                # Generic handling
                parts = repository_url.split('/')
                if len(parts) >= 1:
                    return f"repo-{parts[-1]}"
            
            # Fallback to fabric name
            return f"hedgehog-{self.fabric.name}"
            
        except Exception:
            return f"hedgehog-{self.fabric.name}"
    
    async def _create_repository_secret(self, repository_config: GitRepositoryConfig) -> Dict[str, Any]:
        """Create Kubernetes secret for repository credentials"""
        try:
            core_v1 = self.argocd_installer._get_core_v1_api()
            secret_name = f'repo-{repository_config.name}'
            
            # Prepare secret data
            secret_data = {
                'url': base64.b64encode(repository_config.url.encode()).decode(),
                'type': base64.b64encode('git'.encode()).decode()
            }
            
            # Add authentication data
            if repository_config.username and repository_config.password:
                secret_data['username'] = base64.b64encode(repository_config.username.encode()).decode()
                secret_data['password'] = base64.b64encode(repository_config.password.encode()).decode()
            
            if repository_config.ssh_private_key:
                secret_data['sshPrivateKey'] = base64.b64encode(repository_config.ssh_private_key.encode()).decode()
            
            if repository_config.tls_client_cert_data:
                secret_data['tlsClientCertData'] = base64.b64encode(repository_config.tls_client_cert_data.encode()).decode()
            
            if repository_config.tls_client_cert_key:
                secret_data['tlsClientCertKey'] = base64.b64encode(repository_config.tls_client_cert_key.encode()).decode()
            
            # Create secret manifest
            secret = client.V1Secret(
                metadata=client.V1ObjectMeta(
                    name=secret_name,
                    namespace=self.argocd_installer.argocd_namespace,
                    labels={
                        'argocd.argoproj.io/secret-type': 'repository',
                        'managed-by': 'hedgehog-netbox-plugin',
                        'fabric': self.fabric.name
                    }
                ),
                type='Opaque',
                data=secret_data
            )
            
            # Try to create or update secret
            try:
                await asyncio.to_thread(
                    core_v1.create_namespaced_secret,
                    namespace=self.argocd_installer.argocd_namespace,
                    body=secret
                )
                operation = 'created'
            except ApiException as e:
                if e.status == 409:  # Already exists
                    await asyncio.to_thread(
                        core_v1.patch_namespaced_secret,
                        name=secret_name,
                        namespace=self.argocd_installer.argocd_namespace,
                        body=secret
                    )
                    operation = 'updated'
                else:
                    raise
            
            self.logger.info(f"Repository secret {operation}: {secret_name}")
            
            return {
                'success': True,
                'message': f'Repository secret {operation}',
                'secret_name': secret_name,
                'operation': operation
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create repository secret: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to create repository secret'
            }
    
    async def _register_repository_in_argocd(self, repository_config: GitRepositoryConfig) -> Dict[str, Any]:
        """Register repository in ArgoCD via API or ConfigMap"""
        try:
            # For MVP, we'll use a simpler approach and let ArgoCD auto-discover the repository
            # via the secret we created. In a full implementation, this would use the ArgoCD API
            # or create a Repository CRD.
            
            self.logger.info(f"Repository registered in ArgoCD: {repository_config.name}")
            
            return {
                'success': True,
                'message': 'Repository registered in ArgoCD',
                'repository_name': repository_config.name,
                'auto_discovery': True
            }
            
        except Exception as e:
            self.logger.error(f"Failed to register repository in ArgoCD: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to register repository in ArgoCD'
            }
    
    async def _validate_repository_connection(self, repository_config: GitRepositoryConfig) -> Dict[str, Any]:
        """Validate repository connection and accessibility"""
        try:
            # For MVP, we'll do a basic validation
            # In a full implementation, this would test the actual Git connection
            
            if not repository_config.url:
                return {
                    'success': False,
                    'error': 'Repository URL is empty'
                }
            
            if not repository_config.url.startswith(('http://', 'https://', 'git@', 'ssh://')):
                return {
                    'success': False,
                    'error': 'Invalid repository URL format'
                }
            
            # Check if we have credentials
            has_credentials = bool(
                (repository_config.username and repository_config.password) or
                repository_config.ssh_private_key
            )
            
            if not has_credentials:
                return {
                    'success': False,
                    'error': 'No authentication credentials provided'
                }
            
            self.logger.info(f"Repository validation passed: {repository_config.name}")
            
            return {
                'success': True,
                'message': 'Repository validation successful',
                'repository_url': repository_config.url,
                'has_credentials': has_credentials,
                'auth_method': 'token' if repository_config.password else 'ssh'
            }
            
        except Exception as e:
            self.logger.error(f"Repository validation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Repository validation failed'
            }
    
    async def setup_git_webhook(self, webhook_config: Optional[GitWebhookConfig] = None) -> Dict[str, Any]:
        """
        Set up Git webhook for automatic ArgoCD synchronization.
        
        Args:
            webhook_config: Optional webhook configuration
            
        Returns:
            Webhook setup result dict
        """
        try:
            self.logger.info("Setting up Git webhook for ArgoCD...")
            
            if not webhook_config:
                webhook_config = self._build_webhook_config()
            
            if not webhook_config:
                return {
                    'success': False,
                    'error': 'Unable to determine webhook configuration'
                }
            
            # For MVP, we'll provide the webhook URL and instructions
            # In a full implementation, this would automatically configure webhooks via Git provider APIs
            
            webhook_instructions = self._generate_webhook_instructions(webhook_config)
            
            return {
                'success': True,
                'message': 'Webhook configuration prepared',
                'webhook_url': webhook_config.webhook_url,
                'webhook_secret': webhook_config.secret,
                'events': webhook_config.events,
                'instructions': webhook_instructions,
                'manual_setup_required': True
            }
            
        except Exception as e:
            self.logger.error(f"Failed to set up Git webhook: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Git webhook setup failed'
            }
    
    def _build_webhook_config(self) -> Optional[GitWebhookConfig]:
        """Build webhook configuration for the fabric"""
        try:
            # Generate webhook URL based on ArgoCD server
            if hasattr(self.fabric, 'argocd_server_url') and self.fabric.argocd_server_url:
                base_url = self.fabric.argocd_server_url.rstrip('/')
                webhook_url = f"{base_url}/api/webhook"
            else:
                # Fallback to cluster-internal URL
                webhook_url = f"https://argocd-server.{self.argocd_installer.argocd_namespace}.svc.cluster.local/api/webhook"
            
            # Generate webhook secret
            import secrets
            webhook_secret = secrets.token_urlsafe(32)
            
            return GitWebhookConfig(
                webhook_url=webhook_url,
                secret=webhook_secret,
                events=['push', 'pull_request', 'merge_request']
            )
            
        except Exception as e:
            self.logger.error(f"Failed to build webhook configuration: {e}")
            return None
    
    def _generate_webhook_instructions(self, webhook_config: GitWebhookConfig) -> Dict[str, Any]:
        """Generate instructions for manual webhook setup"""
        
        # Determine Git provider from repository URL
        provider = 'generic'
        if self.fabric.git_repository_url:
            if 'github.com' in self.fabric.git_repository_url:
                provider = 'github'
            elif 'gitlab.com' in self.fabric.git_repository_url:
                provider = 'gitlab'
            elif 'bitbucket.org' in self.fabric.git_repository_url:
                provider = 'bitbucket'
        
        instructions = {
            'provider': provider,
            'webhook_url': webhook_config.webhook_url,
            'secret': webhook_config.secret,
            'events': webhook_config.events,
            'content_type': 'application/json'
        }
        
        if provider == 'github':
            instructions.update({
                'setup_url': f"{self.fabric.git_repository_url}/settings/hooks",
                'payload_url': webhook_config.webhook_url,
                'which_events': 'Just the push event',
                'active': True
            })
        elif provider == 'gitlab':
            instructions.update({
                'setup_url': f"{self.fabric.git_repository_url}/-/hooks",
                'url': webhook_config.webhook_url,
                'trigger': 'Push events, Merge request events',
                'ssl_verification': True
            })
        elif provider == 'bitbucket':
            instructions.update({
                'setup_url': f"{self.fabric.git_repository_url}/admin/addon/admin/bitbucket-webhooks/bb-webhooks-repo-admin",
                'url': webhook_config.webhook_url,
                'events': 'Repository push, Pull request created, Pull request updated'
            })
        
        return instructions
    
    async def get_repository_status(self) -> Dict[str, Any]:
        """Get status of Git repository configuration in ArgoCD"""
        try:
            # Check if repository secret exists
            core_v1 = self.argocd_installer._get_core_v1_api()
            repo_config = self._build_repository_config_from_fabric()
            
            if not repo_config:
                return {
                    'success': False,
                    'error': 'No repository configuration available'
                }
            
            secret_name = f'repo-{repo_config.name}'
            
            try:
                secret = await asyncio.to_thread(
                    core_v1.read_namespaced_secret,
                    name=secret_name,
                    namespace=self.argocd_installer.argocd_namespace
                )
                secret_exists = True
            except ApiException as e:
                if e.status == 404:
                    secret_exists = False
                else:
                    raise
            
            return {
                'success': True,
                'repository_name': repo_config.name,
                'repository_url': repo_config.url,
                'secret_exists': secret_exists,
                'secret_name': secret_name,
                'configured': secret_exists,
                'auth_method': 'token' if repo_config.password else 'ssh' if repo_config.ssh_private_key else 'none'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get repository status: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to get repository status'
            }
    
    async def remove_repository_configuration(self) -> Dict[str, Any]:
        """Remove Git repository configuration from ArgoCD"""
        try:
            self.logger.info("Removing Git repository configuration from ArgoCD...")
            
            repo_config = self._build_repository_config_from_fabric()
            if not repo_config:
                return {
                    'success': True,
                    'message': 'No repository configuration to remove'
                }
            
            # Remove repository secret
            core_v1 = self.argocd_installer._get_core_v1_api()
            secret_name = f'repo-{repo_config.name}'
            
            try:
                await asyncio.to_thread(
                    core_v1.delete_namespaced_secret,
                    name=secret_name,
                    namespace=self.argocd_installer.argocd_namespace
                )
                self.logger.info(f"Removed repository secret: {secret_name}")
            except ApiException as e:
                if e.status != 404:
                    raise
                else:
                    self.logger.info(f"Repository secret not found: {secret_name}")
            
            return {
                'success': True,
                'message': 'Repository configuration removed',
                'repository_name': repo_config.name,
                'secret_removed': True
            }
            
        except Exception as e:
            self.logger.error(f"Failed to remove repository configuration: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to remove repository configuration'
            }
    
    async def test_repository_connection(self) -> Dict[str, Any]:
        """Test Git repository connection using current configuration"""
        try:
            self.logger.info("Testing Git repository connection...")
            
            # Use existing Git monitor for connection testing
            from .git_monitor import GitRepositoryMonitor
            
            monitor = GitRepositoryMonitor(self.fabric)
            status = monitor.get_repository_status()
            
            if status.configured and status.repository_exists:
                return {
                    'success': True,
                    'message': 'Repository connection test successful',
                    'repository_url': self.fabric.git_repository_url,
                    'branch': self.fabric.git_branch,
                    'current_commit': status.current_commit,
                    'repository_accessible': True
                }
            else:
                return {
                    'success': False,
                    'error': status.error or 'Repository not accessible',
                    'repository_url': self.fabric.git_repository_url,
                    'repository_accessible': False
                }
            
        except Exception as e:
            self.logger.error(f"Repository connection test failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Repository connection test failed'
            }


class GitOpsRepositoryManager:
    """
    High-level manager for Git repository operations in GitOps context.
    
    Coordinates between existing Git utilities and ArgoCD integration.
    """
    
    def __init__(self, fabric):
        """
        Initialize repository manager.
        
        Args:
            fabric: HedgehogFabric instance
        """
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.repo.{fabric.name}")
    
    async def setup_complete_git_integration(self, argocd_installer) -> Dict[str, Any]:
        """
        Set up complete Git integration for ArgoCD.
        
        Args:
            argocd_installer: ArgoCDInstaller instance
            
        Returns:
            Complete integration result
        """
        try:
            self.logger.info("Setting up complete Git integration for ArgoCD...")
            
            # Create Git integrator
            git_integrator = ArgoCDGitIntegrator(self.fabric, argocd_installer)
            
            integration_results = {
                'fabric_name': self.fabric.name,
                'steps_completed': [],
                'steps_failed': [],
                'overall_success': False
            }
            
            # Step 1: Configure repository
            self.logger.info("Step 1: Configuring Git repository...")
            repo_result = await git_integrator.configure_git_repository()
            if repo_result['success']:
                integration_results['steps_completed'].append('repository_configuration')
                integration_results['repository_config'] = repo_result
            else:
                integration_results['steps_failed'].append({
                    'step': 'repository_configuration',
                    'error': repo_result['error']
                })
                return integration_results
            
            # Step 2: Test repository connection
            self.logger.info("Step 2: Testing repository connection...")
            test_result = await git_integrator.test_repository_connection()
            if test_result['success']:
                integration_results['steps_completed'].append('connection_test')
                integration_results['connection_test'] = test_result
            else:
                integration_results['steps_failed'].append({
                    'step': 'connection_test',
                    'error': test_result['error']
                })
                # Continue even if connection test fails - it might be a network issue
            
            # Step 3: Set up webhook (optional)
            self.logger.info("Step 3: Setting up Git webhook...")
            webhook_result = await git_integrator.setup_git_webhook()
            if webhook_result['success']:
                integration_results['steps_completed'].append('webhook_setup')
                integration_results['webhook_config'] = webhook_result
            else:
                integration_results['steps_failed'].append({
                    'step': 'webhook_setup',
                    'error': webhook_result['error']
                })
                # Webhook setup failure is not critical
            
            # Determine overall success
            critical_steps = ['repository_configuration']
            integration_results['overall_success'] = all(
                step in integration_results['steps_completed'] 
                for step in critical_steps
            )
            
            self.logger.info(f"Git integration setup completed: {integration_results['overall_success']}")
            
            return integration_results
            
        except Exception as e:
            self.logger.error(f"Git integration setup failed: {e}")
            return {
                'fabric_name': self.fabric.name,
                'steps_completed': [],
                'steps_failed': [{'step': 'integration_process', 'error': str(e)}],
                'overall_success': False,
                'error': str(e)
            }
    
    async def get_git_integration_status(self, argocd_installer) -> Dict[str, Any]:
        """Get comprehensive Git integration status"""
        try:
            git_integrator = ArgoCDGitIntegrator(self.fabric, argocd_installer)
            
            # Get repository status
            repo_status = await git_integrator.get_repository_status()
            
            # Get fabric Git configuration
            git_config = self.fabric.get_git_status()
            
            return {
                'success': True,
                'fabric_name': self.fabric.name,
                'git_configured': bool(self.fabric.git_repository_url),
                'repository_url': self.fabric.git_repository_url,
                'branch': self.fabric.git_branch,
                'path': self.fabric.git_path,
                'argocd_repo_status': repo_status,
                'fabric_git_status': git_config,
                'integration_ready': repo_status.get('configured', False),
                'authentication_configured': bool(self.fabric.git_token or self.fabric.git_username)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get Git integration status: {e}")
            return {
                'success': False,
                'error': str(e),
                'fabric_name': self.fabric.name
            }


# Convenience functions for easy integration

async def setup_git_integration_for_fabric(fabric, argocd_installer) -> Dict[str, Any]:
    """
    Convenience function to set up Git integration for a fabric.
    
    Args:
        fabric: HedgehogFabric instance
        argocd_installer: ArgoCDInstaller instance
        
    Returns:
        Integration result dict
    """
    repo_manager = GitOpsRepositoryManager(fabric)
    return await repo_manager.setup_complete_git_integration(argocd_installer)


async def get_fabric_git_integration_status(fabric, argocd_installer) -> Dict[str, Any]:
    """
    Convenience function to get Git integration status for a fabric.
    
    Args:
        fabric: HedgehogFabric instance
        argocd_installer: ArgoCDInstaller instance
        
    Returns:
        Status dict
    """
    repo_manager = GitOpsRepositoryManager(fabric)
    return await repo_manager.get_git_integration_status(argocd_installer)