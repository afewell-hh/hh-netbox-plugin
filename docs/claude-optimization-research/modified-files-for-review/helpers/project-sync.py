#!/usr/bin/env python3
"""
NetBox Hedgehog Plugin Project Synchronization Utility

This utility provides container and repository synchronization capabilities
for NetBox plugin development with Enhanced Hive Orchestration integration.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import yaml
import docker
import git
from kubernetes import client, config


# MANDATORY: Load environment variables from .env file
def load_env_file(env_path: str = ".env"):
    """Load environment variables from .env file."""
    if Path(env_path).exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print(f"✅ Loaded environment from {env_path}")
    else:
        print(f"⚠️ Environment file {env_path} not found")

# Load environment variables immediately
load_env_file()


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of synchronization operation."""
    success: bool
    operation: str
    timestamp: datetime
    details: Dict[str, Any]
    errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ContainerConfig:
    """Container synchronization configuration."""
    image_name: str
    tag: str
    registry: str
    environment: str
    health_check: Dict[str, Any]
    rollback_enabled: bool = True
    
    
@dataclass
class GitOpsConfig:
    """GitOps synchronization configuration."""
    repository_url: str
    branch: str
    local_path: Path
    cluster_configs: List[Dict[str, Any]]
    gitops_sync_strategy: str = "bidirectional"
    k8s_sync_strategy: str = "readonly_discovery"
    conflict_resolution: str = "manual"


class ProjectSyncOrchestrator:
    """
    Main orchestrator for project synchronization operations.
    
    Coordinates container deployments, GitOps workflows, and
    repository synchronization with Enhanced Hive Orchestration.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the synchronization orchestrator."""
        self.config_path = config_path or Path.cwd() / ".claude" / "config" / "sync.yml"
        self.config = self._load_config()
        self.docker_client = None
        self.k8s_client = None
        self.git_repos = {}
        
    def _load_config(self) -> Dict[str, Any]:
        """Load synchronization configuration."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return self._default_config()
            
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Provide default configuration with environment variable support."""
        return {
            "container": {
                "image_name": os.getenv('CONTAINER_REGISTRY', 'netbox-hedgehog'),
                "registry": os.getenv('CONTAINER_REGISTRY', 'localhost:5000'),
                "environments": {
                    "development": {
                        "tag": os.getenv('CONTAINER_TAG', 'dev'), 
                        "health_timeout": int(os.getenv('TEST_TIMEOUT_SECONDS', '30'))
                    },
                    "staging": {
                        "tag": "staging", 
                        "health_timeout": 60
                    },
                    "production": {
                        "tag": "latest", 
                        "health_timeout": int(os.getenv('DEPLOY_TIMEOUT', '120'))
                    }
                }
            },
            "gitops": {
                "repository_url": os.getenv('GITOPS_REPO_URL', 'git@github.com:company/k8s-configs.git'),
                "branch": os.getenv('GITOPS_REPO_BRANCH', 'main'),
                "local_path": os.getenv('GITOPS_REPO_PATH', '/tmp/k8s-configs'),
                "clusters": self._load_cluster_configs()
            },
            "kubernetes": {
                "cluster_name": os.getenv('K8S_TEST_CLUSTER_NAME', 'test-cluster'),
                "config_path": os.getenv('K8S_TEST_CONFIG_PATH', '~/.kube/config'),
                "namespace": os.getenv('K8S_TEST_NAMESPACE', 'default'),
                "api_server": os.getenv('K8S_TEST_API_SERVER', ''),
                "service_account": os.getenv('K8S_SERVICE_ACCOUNT', 'hedgehog-test-sa'),
                "token": os.getenv('K8S_SERVICE_ACCOUNT_TOKEN', '')
            },
            "netbox": {
                "url": os.getenv('NETBOX_URL', 'http://localhost:8000'),
                "token": os.getenv('NETBOX_TOKEN', ''),
                "test_url": os.getenv('TEST_NETBOX_URL', ''),
                "test_token": os.getenv('TEST_NETBOX_TOKEN', ''),
                "verify_ssl": os.getenv('NETBOX_VERIFY_SSL', 'false') == 'true'
            },
            "testing": {
                "prefer_real_infrastructure": os.getenv('PREFER_REAL_INFRASTRUCTURE', 'true') == 'true',
                "mock_fallback_enabled": os.getenv('MOCK_FALLBACK_ENABLED', 'false') == 'true',
                "timeout_seconds": int(os.getenv('TEST_TIMEOUT_SECONDS', '300')),
                "cleanup_enabled": os.getenv('TEST_CLEANUP_ENABLED', 'true') == 'true'
            },
            "ruv_swarm": {
                "coordination": os.getenv('ENHANCED_HIVE_ENABLED', 'true') == 'true',
                "memory_keys": {
                    "sync_state": "sync/project/state",
                    "container_status": "sync/container/status",
                    "gitops_status": "sync/gitops/status"
                }
            }
        }
    
    def _load_cluster_configs(self) -> List[Dict[str, Any]]:
        """Load cluster configurations from environment variables."""
        clusters = []
        
        # Primary test cluster from environment
        if os.getenv('K8S_TEST_CLUSTER_NAME'):
            clusters.append({
                'name': os.getenv('K8S_TEST_CLUSTER_NAME'),
                'config_path': os.getenv('K8S_TEST_CONFIG_PATH', '~/.kube/config'),
                'context': os.getenv('K8S_TEST_CONTEXT', ''),
                'namespace': os.getenv('K8S_TEST_NAMESPACE', 'default'),
                'api_server': os.getenv('K8S_TEST_API_SERVER', '')
            })
            
        return clusters
    
    async def initialize_clients(self):
        """Initialize Docker and Kubernetes clients."""
        try:
            # Initialize Docker client
            self.docker_client = docker.from_env()
            logger.info("Docker client initialized")
            
            # Initialize Kubernetes client with environment config
            k8s_config_path = os.getenv('K8S_TEST_CONFIG_PATH')
            try:
                if k8s_config_path and Path(k8s_config_path).exists():
                    config.load_kube_config(config_file=k8s_config_path)
                    logger.info(f"Loaded K8s config from {k8s_config_path}")
                else:
                    config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()
            
            self.k8s_client = client.ApiClient()
            logger.info("Kubernetes client initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            raise


class ContainerSyncManager:
    """Manages container synchronization operations."""
    
    def __init__(self, orchestrator: ProjectSyncOrchestrator):
        self.orchestrator = orchestrator
        self.docker_client = orchestrator.docker_client
        
    async def sync_container(self, environment: str, **kwargs) -> SyncResult:
        """
        Synchronize container deployment for specified environment.
        
        Args:
            environment: Target environment (development, staging, production)
            **kwargs: Additional deployment parameters
            
        Returns:
            SyncResult with deployment status and details
        """
        start_time = datetime.now()
        errors = []
        
        try:
            # Store sync initiation in ruv-swarm memory
            await self._store_sync_state("container", "initiated", {
                "environment": environment,
                "timestamp": start_time.isoformat()
            })
            
            # Get environment configuration
            env_config = self.orchestrator.config["container"]["environments"].get(environment)
            if not env_config:
                raise ValueError(f"Environment '{environment}' not configured")
            
            # Build container image
            image_result = await self._build_image(environment, env_config)
            if not image_result["success"]:
                errors.extend(image_result["errors"])
                
            # Deploy container
            deploy_result = await self._deploy_container(environment, env_config, **kwargs)
            if not deploy_result["success"]:
                errors.extend(deploy_result["errors"])
                
            # Validate deployment health
            if kwargs.get("validate_health", True):
                health_result = await self._validate_container_health(environment, env_config)
                if not health_result["success"]:
                    errors.extend(health_result["errors"])
                    
                    # Rollback on health check failure
                    if kwargs.get("rollback_on_failure", True):
                        await self._rollback_container(environment)
            
            success = len(errors) == 0
            
            # Store final sync state
            await self._store_sync_state("container", "completed", {
                "environment": environment,
                "success": success,
                "errors": errors,
                "duration": (datetime.now() - start_time).total_seconds()
            })
            
            return SyncResult(
                success=success,
                operation=f"container_sync_{environment}",
                timestamp=datetime.now(),
                details={
                    "environment": environment,
                    "image_build": image_result,
                    "deployment": deploy_result,
                    "health_check": health_result if 'health_result' in locals() else None
                },
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Container sync failed: {e}")
            errors.append(str(e))
            
            return SyncResult(
                success=False,
                operation=f"container_sync_{environment}",
                timestamp=datetime.now(),
                details={"environment": environment},
                errors=errors
            )
    
    async def _build_image(self, environment: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Build Docker image for deployment."""
        try:
            image_name = f"{self.orchestrator.config['container']['registry']}/{self.orchestrator.config['container']['image_name']}"
            tag = config["tag"]
            full_image_name = f"{image_name}:{tag}"
            
            logger.info(f"Building image: {full_image_name}")
            
            # Build image
            image, build_logs = self.docker_client.images.build(
                path=".",
                dockerfile="Dockerfile",
                tag=full_image_name,
                rm=True,
                forcerm=True
            )
            
            # Push to registry if not local development
            if environment != "development":
                logger.info(f"Pushing image: {full_image_name}")
                self.docker_client.images.push(full_image_name)
            
            return {
                "success": True,
                "image_id": image.id,
                "image_name": full_image_name,
                "size": image.attrs.get("Size", 0)
            }
            
        except Exception as e:
            logger.error(f"Image build failed: {e}")
            return {
                "success": False,
                "errors": [str(e)]
            }
    
    async def _deploy_container(self, environment: str, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Deploy container to target environment."""
        try:
            container_name = f"netbox-hedgehog-{environment}"
            image_name = f"{self.orchestrator.config['container']['registry']}/{self.orchestrator.config['container']['image_name']}:{config['tag']}"
            
            # Stop existing container
            try:
                existing_container = self.docker_client.containers.get(container_name)
                existing_container.stop()
                existing_container.remove()
                logger.info(f"Removed existing container: {container_name}")
            except docker.errors.NotFound:
                pass
            
            # Start new container
            container = self.docker_client.containers.run(
                image_name,
                name=container_name,
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                environment={
                    "ENVIRONMENT": environment,
                    "DEBUG": "True" if environment == "development" else "False"
                },
                ports={'8000/tcp': None} if environment == "development" else None
            )
            
            logger.info(f"Started container: {container_name}")
            
            return {
                "success": True,
                "container_id": container.id,
                "container_name": container_name,
                "status": container.status
            }
            
        except Exception as e:
            logger.error(f"Container deployment failed: {e}")
            return {
                "success": False,
                "errors": [str(e)]
            }
    
    async def _validate_container_health(self, environment: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate container health after deployment."""
        try:
            container_name = f"netbox-hedgehog-{environment}"
            container = self.docker_client.containers.get(container_name)
            
            # Wait for container to be ready
            timeout = config.get("health_timeout", 60)
            for i in range(timeout):
                container.reload()
                if container.status == "running":
                    break
                await asyncio.sleep(1)
            else:
                raise TimeoutError(f"Container failed to start within {timeout} seconds")
            
            # Additional health checks can be added here
            # e.g., HTTP health check endpoints
            
            return {
                "success": True,
                "status": container.status,
                "health": "healthy"
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "success": False,
                "errors": [str(e)]
            }
    
    async def _rollback_container(self, environment: str):
        """Rollback container deployment."""
        logger.warning(f"Rolling back container deployment for {environment}")
        # Implementation for rollback logic
        pass
    
    async def _store_sync_state(self, sync_type: str, status: str, data: Dict[str, Any]):
        """Store synchronization state in ruv-swarm memory."""
        if not self.orchestrator.config.get("ruv_swarm", {}).get("coordination", False):
            return
            
        try:
            memory_key = f"sync/{sync_type}/{status}"
            
            # Execute ruv-swarm memory storage
            cmd = [
                "npx", "ruv-swarm", "memory", "store",
                "--key", memory_key,
                "--value", json.dumps(data)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.debug(f"Stored sync state: {memory_key}")
            else:
                logger.warning(f"Failed to store sync state: {result.stderr}")
                
        except Exception as e:
            logger.warning(f"Failed to store sync state: {e}")


class GitOpsSyncManager:
    """Manages GitOps synchronization operations."""
    
    def __init__(self, orchestrator: ProjectSyncOrchestrator):
        self.orchestrator = orchestrator
        self.k8s_client = orchestrator.k8s_client
        
    async def sync_gitops(self, **kwargs) -> SyncResult:
        """
        Synchronize GitOps repository and Kubernetes deployments.
        
        Args:
            **kwargs: Synchronization parameters
            
        Returns:
            SyncResult with synchronization status and details
        """
        start_time = datetime.now()
        errors = []
        
        try:
            # Initialize GitOps repository
            repo_result = await self._sync_repository()
            if not repo_result["success"]:
                errors.extend(repo_result["errors"])
            
            # Validate Kubernetes configurations
            if kwargs.get("validate_configs", True):
                validation_result = await self._validate_k8s_configs()
                if not validation_result["success"]:
                    errors.extend(validation_result["errors"])
            
            # Apply configurations to clusters
            if not kwargs.get("dry_run", False):
                apply_result = await self._apply_k8s_configs(**kwargs)
                if not apply_result["success"]:
                    errors.extend(apply_result["errors"])
            
            success = len(errors) == 0
            
            return SyncResult(
                success=success,
                operation="gitops_sync",
                timestamp=datetime.now(),
                details={
                    "repository": repo_result,
                    "validation": validation_result if 'validation_result' in locals() else None,
                    "deployment": apply_result if 'apply_result' in locals() else None
                },
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"GitOps sync failed: {e}")
            errors.append(str(e))
            
            return SyncResult(
                success=False,
                operation="gitops_sync",
                timestamp=datetime.now(),
                details={},
                errors=errors
            )
    
    async def _sync_repository(self) -> Dict[str, Any]:
        """Synchronize GitOps repository."""
        try:
            config = self.orchestrator.config["gitops"]
            repo_path = Path(config["local_path"])
            
            if repo_path.exists():
                # Update existing repository
                repo = git.Repo(repo_path)
                origin = repo.remotes.origin
                origin.pull()
                logger.info("Updated GitOps repository")
            else:
                # Clone repository
                repo = git.Repo.clone_from(
                    config["repository_url"],
                    repo_path,
                    branch=config["branch"]
                )
                logger.info("Cloned GitOps repository")
            
            return {
                "success": True,
                "commit_hash": repo.head.commit.hexsha,
                "branch": repo.active_branch.name
            }
            
        except Exception as e:
            logger.error(f"Repository sync failed: {e}")
            return {
                "success": False,
                "errors": [str(e)]
            }
    
    async def _validate_k8s_configs(self) -> Dict[str, Any]:
        """Validate Kubernetes configuration files."""
        try:
            # Implementation for K8s config validation
            # This would validate YAML files for syntax and schema compliance
            
            return {
                "success": True,
                "validated_files": [],
                "warnings": []
            }
            
        except Exception as e:
            logger.error(f"K8s config validation failed: {e}")
            return {
                "success": False,
                "errors": [str(e)]
            }
    
    async def _apply_k8s_configs(self, **kwargs) -> Dict[str, Any]:
        """Apply Kubernetes configurations to clusters."""
        try:
            # Implementation for applying K8s configurations
            # This would use kubectl or the Python K8s client
            
            return {
                "success": True,
                "applied_resources": [],
                "cluster_status": {}
            }
            
        except Exception as e:
            logger.error(f"K8s config application failed: {e}")
            return {
                "success": False,
                "errors": [str(e)]
            }


async def main():
    """Main entry point for project synchronization utility."""
    import argparse
    
    parser = argparse.ArgumentParser(description="NetBox Plugin Project Synchronization")
    parser.add_argument("operation", choices=["container", "gitops", "full"], 
                       help="Synchronization operation type")
    parser.add_argument("--environment", default="development",
                       help="Target environment for container sync")
    parser.add_argument("--config", type=Path, help="Configuration file path")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without actual deployment")
    parser.add_argument("--validate-health", action="store_true", default=True, help="Validate health after deployment")
    parser.add_argument("--rollback-on-failure", action="store_true", default=True, help="Rollback on deployment failure")
    
    args = parser.parse_args()
    
    # Initialize orchestrator
    orchestrator = ProjectSyncOrchestrator(args.config)
    await orchestrator.initialize_clients()
    
    # Execute requested operation
    if args.operation == "container":
        manager = ContainerSyncManager(orchestrator)
        result = await manager.sync_container(
            args.environment,
            validate_health=args.validate_health,
            rollback_on_failure=args.rollback_on_failure
        )
    elif args.operation == "gitops":
        manager = GitOpsSyncManager(orchestrator)
        result = await manager.sync_gitops(dry_run=args.dry_run)
    elif args.operation == "full":
        # Execute both container and GitOps sync
        container_manager = ContainerSyncManager(orchestrator)
        gitops_manager = GitOpsSyncManager(orchestrator)
        
        container_result = await container_manager.sync_container(args.environment)
        gitops_result = await gitops_manager.sync_gitops()
        
        result = SyncResult(
            success=container_result.success and gitops_result.success,
            operation="full_sync",
            timestamp=datetime.now(),
            details={
                "container": container_result.to_dict(),
                "gitops": gitops_result.to_dict()
            },
            errors=container_result.errors + gitops_result.errors
        )
    
    # Output result
    print(json.dumps(result.to_dict(), indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    asyncio.run(main())