"""
Mock Fabric Fixtures for Testing

Provides pre-configured mock HedgehogFabric instances for various test scenarios.
"""

from unittest.mock import Mock
from django.utils import timezone

from netbox_hedgehog.models.fabric import HedgehogFabric


def create_basic_mock_fabric():
    """Create a basic mock fabric for simple tests."""
    fabric = Mock(spec=HedgehogFabric)
    fabric.id = 1
    fabric.name = 'basic-test-fabric'
    fabric.description = 'Basic test fabric for unit tests'
    fabric.kubernetes_namespace = 'default'
    fabric.gitops_initialized = False
    fabric.archive_strategy = 'rename_with_extension'
    fabric.raw_directory_path = ''
    fabric.managed_directory_path = ''
    fabric.save = Mock()
    return fabric


def create_production_mock_fabric():
    """Create a mock fabric simulating production environment."""
    fabric = Mock(spec=HedgehogFabric)
    fabric.id = 2
    fabric.name = 'production-fabric'
    fabric.description = 'Production fabric for integration tests'
    fabric.kubernetes_namespace = 'production'
    fabric.kubernetes_server = 'https://k8s-prod.company.com:6443'
    fabric.sync_enabled = True
    fabric.sync_interval = 300
    fabric.gitops_initialized = True
    fabric.archive_strategy = 'rename_with_extension'
    fabric.raw_directory_path = '/var/lib/hedgehog/fabrics/production-fabric/gitops/raw'
    fabric.managed_directory_path = '/var/lib/hedgehog/fabrics/production-fabric/gitops/managed'
    fabric.git_repository_url = 'https://github.com/company/hedgehog-configs.git'
    fabric.git_branch = 'main'
    fabric.gitops_directory = '/fabrics/production-fabric/gitops'
    fabric.save = Mock()
    return fabric


def create_development_mock_fabric():
    """Create a mock fabric for development environment."""
    fabric = Mock(spec=HedgehogFabric)
    fabric.id = 3
    fabric.name = 'dev-fabric'
    fabric.description = 'Development fabric for testing new features'
    fabric.kubernetes_namespace = 'development'
    fabric.kubernetes_server = 'https://k8s-dev.company.com:6443'
    fabric.sync_enabled = True
    fabric.sync_interval = 60  # More frequent sync for dev
    fabric.gitops_initialized = True
    fabric.archive_strategy = 'backup_with_timestamp'
    fabric.raw_directory_path = '/tmp/hedgehog/dev-fabric/raw'
    fabric.managed_directory_path = '/tmp/hedgehog/dev-fabric/managed'
    fabric.git_repository_url = 'https://github.com/company/hedgehog-dev-configs.git'
    fabric.git_branch = 'develop'
    fabric.gitops_directory = '/fabrics/dev-fabric/gitops'
    fabric.save = Mock()
    return fabric


def create_uninitialized_mock_fabric():
    """Create a mock fabric that hasn't been initialized yet."""
    fabric = Mock(spec=HedgehogFabric)
    fabric.id = 4
    fabric.name = 'uninitialized-fabric'
    fabric.description = 'Fabric that needs GitOps initialization'
    fabric.kubernetes_namespace = 'staging'
    fabric.gitops_initialized = False
    fabric.archive_strategy = 'rename_with_extension'
    fabric.raw_directory_path = None
    fabric.managed_directory_path = None
    fabric.git_repository_url = None
    fabric.git_branch = 'main'
    fabric.gitops_directory = '/'
    fabric.save = Mock()
    return fabric


def create_corrupted_mock_fabric():
    """Create a mock fabric with corrupted/inconsistent state."""
    fabric = Mock(spec=HedgehogFabric)
    fabric.id = 5
    fabric.name = 'corrupted-fabric'
    fabric.description = 'Fabric with corrupted state for error testing'
    fabric.kubernetes_namespace = 'test'
    fabric.gitops_initialized = True  # Claims to be initialized
    fabric.archive_strategy = 'rename_with_extension'
    # But has no actual paths
    fabric.raw_directory_path = '/nonexistent/path/raw'
    fabric.managed_directory_path = '/nonexistent/path/managed'
    fabric.git_repository_url = 'https://invalid-url-that-does-not-exist.com/repo.git'
    fabric.save = Mock()
    return fabric


def create_unicode_mock_fabric():
    """Create a mock fabric with Unicode characters in names."""
    fabric = Mock(spec=HedgehogFabric)
    fabric.id = 6
    fabric.name = 'unicode-fabric-测试-🦔'
    fabric.description = 'Fabric with Unicode: français, русский, 中文, 🌟'
    fabric.kubernetes_namespace = '测试-namespace'
    fabric.gitops_initialized = True
    fabric.archive_strategy = 'rename_with_extension'
    fabric.raw_directory_path = '/tmp/unicode-fabric-测试-🦔/raw'
    fabric.managed_directory_path = '/tmp/unicode-fabric-测试-🦔/managed'
    fabric.save = Mock()
    return fabric


def create_enterprise_mock_fabric():
    """Create a mock fabric simulating enterprise configuration."""
    fabric = Mock(spec=HedgehogFabric)
    fabric.id = 7
    fabric.name = 'enterprise-fabric'
    fabric.description = 'Enterprise-scale fabric with advanced features'
    fabric.kubernetes_namespace = 'enterprise-production'
    fabric.kubernetes_server = 'https://k8s-enterprise.company.com:6443'
    fabric.kubernetes_token = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...'  # Mock token
    
    # GitOps configuration
    fabric.gitops_initialized = True
    fabric.archive_strategy = 'move_to_archive_dir'
    fabric.raw_directory_path = '/enterprise/gitops/fabrics/enterprise-fabric/raw'
    fabric.managed_directory_path = '/enterprise/gitops/fabrics/enterprise-fabric/managed'
    
    # Git repository configuration
    fabric.git_repository_url = 'https://git.enterprise.com/infrastructure/hedgehog-configs.git'
    fabric.git_branch = 'production'
    fabric.gitops_directory = '/fabrics/enterprise-fabric'
    fabric.git_username = 'hedgehog-bot'
    fabric.git_token = 'ghp_enterprise_token_here'
    
    # ArgoCD integration
    fabric.gitops_tool = 'argocd'
    fabric.gitops_app_name = 'hedgehog-enterprise-fabric'
    fabric.gitops_namespace = 'argocd'
    fabric.argocd_installed = True
    fabric.argocd_server_url = 'https://argocd.enterprise.com'
    fabric.argocd_health_status = 'healthy'
    
    # Advanced settings
    fabric.auto_sync_enabled = True
    fabric.prune_enabled = True
    fabric.self_heal_enabled = True
    fabric.watch_enabled = True
    fabric.watch_status = 'active'
    
    # Performance settings
    fabric.sync_interval = 60
    fabric.watch_crd_types = ['VPC', 'External', 'Switch', 'Connection']
    
    # Cached counts for performance
    fabric.cached_crd_count = 1250
    fabric.cached_vpc_count = 45
    fabric.cached_connection_count = 320
    fabric.connections_count = 320
    fabric.servers_count = 180
    fabric.switches_count = 85
    fabric.vpcs_count = 45
    
    fabric.save = Mock()
    return fabric


def create_minimal_mock_fabric():
    """Create a minimal mock fabric with only required fields."""
    fabric = Mock(spec=HedgehogFabric)
    fabric.id = 8
    fabric.name = 'minimal-fabric'
    fabric.kubernetes_namespace = 'default'
    fabric.gitops_initialized = False
    fabric.save = Mock()
    
    # Set all other attributes to None or defaults
    for attr in ['description', 'kubernetes_server', 'kubernetes_token', 
                 'git_repository_url', 'git_branch', 'gitops_directory',
                 'raw_directory_path', 'managed_directory_path',
                 'archive_strategy']:
        setattr(fabric, attr, None)
    
    return fabric


def create_performance_test_mock_fabric():
    """Create a mock fabric for performance testing with large counts."""
    fabric = Mock(spec=HedgehogFabric)
    fabric.id = 9
    fabric.name = 'performance-test-fabric'
    fabric.description = 'Large-scale fabric for performance testing'
    fabric.kubernetes_namespace = 'performance-test'
    fabric.gitops_initialized = True
    fabric.archive_strategy = 'rename_with_extension'
    fabric.raw_directory_path = '/perf/test/raw'
    fabric.managed_directory_path = '/perf/test/managed'
    
    # Large counts for performance testing
    fabric.cached_crd_count = 10000
    fabric.cached_vpc_count = 500
    fabric.cached_connection_count = 2500
    fabric.connections_count = 2500
    fabric.servers_count = 1000
    fabric.switches_count = 300
    fabric.vpcs_count = 500
    
    fabric.save = Mock()
    return fabric


def create_gitops_error_mock_fabric():
    """Create a mock fabric that simulates GitOps errors."""
    fabric = Mock(spec=HedgehogFabric)
    fabric.id = 10
    fabric.name = 'gitops-error-fabric'
    fabric.description = 'Fabric for testing error scenarios'
    fabric.kubernetes_namespace = 'error-test'
    fabric.gitops_initialized = True
    fabric.archive_strategy = 'rename_with_extension'
    fabric.raw_directory_path = '/error/test/raw'
    fabric.managed_directory_path = '/error/test/managed'
    
    # Simulate error states
    fabric.sync_status = 'error'
    fabric.connection_status = 'failed'
    fabric.sync_error = 'Failed to sync with Kubernetes API'
    fabric.connection_error = 'Connection timeout to k8s-error.test.com:6443'
    fabric.gitops_setup_status = 'error'
    fabric.gitops_setup_error = 'ArgoCD application sync failed'
    fabric.watch_status = 'error'
    fabric.watch_error_message = 'CRD watch connection lost'
    
    # Mock save to raise exception when called
    fabric.save = Mock(side_effect=Exception("Database connection error"))
    
    return fabric


# Fabric factory function
def create_mock_fabric(fabric_type='basic'):
    """
    Factory function to create different types of mock fabrics.
    
    Args:
        fabric_type: Type of fabric to create
                    ('basic', 'production', 'development', 'uninitialized', 
                     'corrupted', 'unicode', 'enterprise', 'minimal', 
                     'performance', 'error')
    
    Returns:
        Mock HedgehogFabric instance
    """
    fabric_types = {
        'basic': create_basic_mock_fabric,
        'production': create_production_mock_fabric,
        'development': create_development_mock_fabric,
        'uninitialized': create_uninitialized_mock_fabric,
        'corrupted': create_corrupted_mock_fabric,
        'unicode': create_unicode_mock_fabric,
        'enterprise': create_enterprise_mock_fabric,
        'minimal': create_minimal_mock_fabric,
        'performance': create_performance_test_mock_fabric,
        'error': create_gitops_error_mock_fabric,
    }
    
    if fabric_type not in fabric_types:
        raise ValueError(f"Unknown fabric type: {fabric_type}")
    
    return fabric_types[fabric_type]()


# Helper functions for common test scenarios
def create_fabric_with_paths(raw_path, managed_path, initialized=True):
    """Create a mock fabric with specific directory paths."""
    fabric = create_basic_mock_fabric()
    fabric.raw_directory_path = str(raw_path)
    fabric.managed_directory_path = str(managed_path)
    fabric.gitops_initialized = initialized
    return fabric


def create_fabric_with_git_config(git_url, git_branch='main', git_dir='/'):
    """Create a mock fabric with specific Git configuration."""
    fabric = create_basic_mock_fabric()
    fabric.git_repository_url = git_url
    fabric.git_branch = git_branch
    fabric.gitops_directory = git_dir
    return fabric


def create_fabric_with_k8s_config(k8s_server, k8s_namespace, k8s_token=None):
    """Create a mock fabric with specific Kubernetes configuration."""
    fabric = create_basic_mock_fabric()
    fabric.kubernetes_server = k8s_server
    fabric.kubernetes_namespace = k8s_namespace
    if k8s_token:
        fabric.kubernetes_token = k8s_token
    return fabric