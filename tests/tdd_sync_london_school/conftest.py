"""
Test configuration and fixtures for London School TDD sync testing.

This module provides comprehensive fixtures and test setup for mock-driven
behavior testing of sync functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import uuid
import json

# Django test imports
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings

# Plugin imports
from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.models.gitops import HedgehogResource
from netbox_hedgehog.utils.kubernetes import KubernetesClient
from netbox_hedgehog.tasks.sync_tasks import sync_fabric_task


User = get_user_model()


# =============================================================================
# MOCK CONTRACTS AND IMPLEMENTATIONS
# =============================================================================

class KubernetesClientContract:
    """
    Contract defining expected behavior of Kubernetes client.
    London School principle: Define contracts through mocks first.
    """
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Kubernetes cluster."""
        raise NotImplementedError("Contract method must be mocked")
    
    def apply_crd(self, crd_instance) -> Dict[str, Any]:
        """Apply CRD to cluster."""
        raise NotImplementedError("Contract method must be mocked")
    
    def fetch_crds_from_kubernetes(self) -> Dict[str, Any]:
        """Fetch CRDs from cluster."""
        raise NotImplementedError("Contract method must be mocked")


class MockKubernetesClient:
    """
    Mock implementation of Kubernetes client following London School patterns.
    Focuses on behavior verification rather than state testing.
    """
    
    def __init__(self, scenario: str = 'success'):
        self.scenario = scenario
        self.test_connection = Mock()
        self.apply_crd = Mock()
        self.fetch_crds_from_kubernetes = Mock()
        self._configure_scenario()
    
    def _configure_scenario(self):
        """Configure mock behavior based on test scenario."""
        if self.scenario == 'success':
            self._configure_success_scenario()
        elif self.scenario == 'connection_failure':
            self._configure_connection_failure()
        elif self.scenario == 'timeout':
            self._configure_timeout_scenario()
        elif self.scenario == 'authentication_error':
            self._configure_auth_error()
        else:
            raise ValueError(f"Unknown scenario: {self.scenario}")
    
    def _configure_success_scenario(self):
        """Configure mocks for successful operations."""
        self.test_connection.return_value = {
            'success': True,
            'cluster_version': 'v1.28.0',
            'platform': 'linux/amd64',
            'namespace_access': True,
            'message': 'Connection successful'
        }
        
        self.apply_crd.return_value = {
            'success': True,
            'operation': 'created',
            'uid': 'test-uid-123',
            'resource_version': '12345',
            'message': 'CRD created successfully'
        }
        
        self.fetch_crds_from_kubernetes.return_value = {
            'success': True,
            'resources': {
                'VPC': [
                    {
                        'metadata': {'name': 'test-vpc', 'namespace': 'default'},
                        'spec': {'subnet': '10.0.0.0/24'},
                        'status': {'phase': 'Ready'}
                    }
                ],
                'Connection': [
                    {
                        'metadata': {'name': 'test-conn', 'namespace': 'default'},
                        'spec': {'type': 'ethernet'},
                        'status': {'phase': 'Ready'}
                    }
                ]
            },
            'errors': []
        }
    
    def _configure_connection_failure(self):
        """Configure mocks for connection failures."""
        self.test_connection.return_value = {
            'success': False,
            'error': 'Connection refused: Unable to connect to cluster',
            'message': 'Connection failed'
        }
        
        # Other methods should raise exceptions on connection failure
        self.apply_crd.side_effect = ConnectionError("No connection to cluster")
        self.fetch_crds_from_kubernetes.side_effect = ConnectionError("No connection to cluster")
    
    def _configure_timeout_scenario(self):
        """Configure mocks for timeout scenarios."""
        self.test_connection.side_effect = TimeoutError("Connection timeout after 30 seconds")
        self.apply_crd.side_effect = TimeoutError("Apply operation timeout")
        self.fetch_crds_from_kubernetes.side_effect = TimeoutError("Fetch operation timeout")
    
    def _configure_auth_error(self):
        """Configure mocks for authentication errors."""
        auth_error = {
            'success': False,
            'error': 'Unauthorized: Invalid token or insufficient permissions',
            'message': 'Authentication failed'
        }
        
        self.test_connection.return_value = auth_error
        self.apply_crd.side_effect = PermissionError("Unauthorized")
        self.fetch_crds_from_kubernetes.side_effect = PermissionError("Unauthorized")


class MockFabricService:
    """
    Mock service for fabric operations.
    London School principle: Mock collaborators to test interactions.
    """
    
    def __init__(self, fabric_state: str = 'valid'):
        self.fabric_state = fabric_state
        self.get_kubernetes_config = Mock()
        self.trigger_gitops_sync = Mock()
        self.needs_sync = Mock()
        self.update_sync_status = Mock()
        self._configure_fabric_state()
    
    def _configure_fabric_state(self):
        """Configure mock behavior based on fabric state."""
        if self.fabric_state == 'valid':
            self.get_kubernetes_config.return_value = {
                'host': 'https://test-cluster.example.com',
                'api_key': {'authorization': 'Bearer test-token'},
                'verify_ssl': True
            }
            
            self.trigger_gitops_sync.return_value = {
                'success': True,
                'message': 'GitOps sync completed',
                'files_processed': 5,
                'resources_created': 2,
                'resources_updated': 3
            }
            
            self.needs_sync.return_value = True
        
        elif self.fabric_state == 'invalid_config':
            self.get_kubernetes_config.return_value = None
            self.trigger_gitops_sync.side_effect = ValueError("Invalid fabric configuration")
            self.needs_sync.return_value = False
        
        elif self.fabric_state == 'sync_disabled':
            self.get_kubernetes_config.return_value = {
                'host': 'https://test-cluster.example.com',
                'api_key': {'authorization': 'Bearer test-token'},
                'verify_ssl': True
            }
            self.needs_sync.return_value = False  # Sync disabled
            self.trigger_gitops_sync.return_value = {
                'success': False,
                'error': 'Sync is disabled for this fabric'
            }


class MockAPIClient:
    """
    Mock API client for testing HTTP interactions.
    London School principle: Test request/response conversations.
    """
    
    def __init__(self, response_scenario: str = 'success'):
        self.response_scenario = response_scenario
        self.post = Mock()
        self.get = Mock()
        self._configure_responses()
    
    def _configure_responses(self):
        """Configure mock responses based on scenario."""
        if self.response_scenario == 'success':
            self.post.return_value = {
                'status_code': 200,
                'json': lambda: {
                    'success': True,
                    'result': {
                        'success': True,
                        'message': 'Sync completed successfully',
                        'fabric_id': 1,
                        'files_processed': 10,
                        'resources_created': 3,
                        'resources_updated': 7
                    }
                }
            }
        
        elif self.response_scenario == 'server_error':
            self.post.return_value = {
                'status_code': 500,
                'json': lambda: {
                    'success': False,
                    'error': 'Internal server error during sync'
                }
            }
        
        elif self.response_scenario == 'timeout':
            self.post.side_effect = TimeoutError("Request timeout")


# =============================================================================
# PYTEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_kubernetes_client_success():
    """Fixture providing successful Kubernetes client mock."""
    return MockKubernetesClient(scenario='success')


@pytest.fixture
def mock_kubernetes_client_failure():
    """Fixture providing failing Kubernetes client mock."""
    return MockKubernetesClient(scenario='connection_failure')


@pytest.fixture 
def mock_kubernetes_client_timeout():
    """Fixture providing timeout Kubernetes client mock."""
    return MockKubernetesClient(scenario='timeout')


@pytest.fixture
def mock_kubernetes_client_auth_error():
    """Fixture providing auth error Kubernetes client mock."""
    return MockKubernetesClient(scenario='authentication_error')


@pytest.fixture
def mock_fabric_service_valid():
    """Fixture providing valid fabric service mock."""
    return MockFabricService(fabric_state='valid')


@pytest.fixture
def mock_fabric_service_invalid():
    """Fixture providing invalid fabric service mock."""
    return MockFabricService(fabric_state='invalid_config')


@pytest.fixture
def mock_fabric_service_disabled():
    """Fixture providing disabled sync fabric service mock."""
    return MockFabricService(fabric_state='sync_disabled')


@pytest.fixture
def mock_api_client_success():
    """Fixture providing successful API client mock."""
    return MockAPIClient(response_scenario='success')


@pytest.fixture
def mock_api_client_error():
    """Fixture providing error API client mock."""
    return MockAPIClient(response_scenario='server_error')


@pytest.fixture
def mock_api_client_timeout():
    """Fixture providing timeout API client mock."""
    return MockAPIClient(response_scenario='timeout')


@pytest.fixture
def test_user():
    """Create test user for authentication."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpassword'
    )


@pytest.fixture
def test_fabric(test_user):
    """
    Create test fabric with known configuration.
    London School principle: Use minimal setup focused on behavior under test.
    """
    return HedgehogFabric.objects.create(
        name='test-fabric',
        description='Test fabric for London School TDD',
        kubernetes_server='https://test-cluster.example.com',
        kubernetes_token='test-token-12345',
        kubernetes_namespace='default',
        sync_enabled=True,
        sync_interval=300,
        created_by=test_user
    )


@pytest.fixture
def test_fabric_no_config():
    """Create test fabric without Kubernetes configuration."""
    return HedgehogFabric.objects.create(
        name='unconfigured-fabric',
        description='Fabric without K8s config',
        sync_enabled=False
    )


@pytest.fixture
def mock_time():
    """
    Mock time for testing periodic sync behavior.
    London School principle: Control time to test timing-dependent interactions.
    """
    with patch('django.utils.timezone.now') as mock_now:
        base_time = timezone.now()
        mock_now.return_value = base_time
        yield mock_now


@pytest.fixture
def mock_celery_task():
    """
    Mock Celery task execution.
    London School principle: Mock infrastructure to focus on business logic.
    """
    with patch('netbox_hedgehog.tasks.sync_tasks.sync_fabric_task') as mock_task:
        mock_task.delay.return_value = Mock(id='test-task-123')
        yield mock_task


@pytest.fixture
def django_test_client():
    """Django test client for HTTP testing."""
    return Client()


# =============================================================================
# BEHAVIOR VERIFICATION HELPERS  
# =============================================================================

class BehaviorAssertion:
    """
    Helper class for London School behavior verification.
    Focuses on testing interactions and collaborations.
    """
    
    @staticmethod
    def assert_sync_workflow_executed(mock_client, mock_fabric):
        """Assert that sync workflow was executed with correct interactions."""
        # Verify the conversation between components
        mock_client.test_connection.assert_called_once()
        mock_fabric.get_kubernetes_config.assert_called_once()
        
        # Verify ordering of operations
        assert mock_client.test_connection.called
        assert mock_client.fetch_crds_from_kubernetes.called
    
    @staticmethod
    def assert_error_propagated_correctly(mock_client, mock_fabric, expected_error):
        """Assert that errors propagate correctly through the system."""
        # Verify error was caught and handled
        mock_fabric.update_sync_status.assert_called_with('error', expected_error)
    
    @staticmethod  
    def assert_api_contract_satisfied(mock_response, expected_fields):
        """Assert that API response satisfies expected contract."""
        response_data = mock_response.json()
        for field in expected_fields:
            assert field in response_data, f"Missing required field: {field}"
    
    @staticmethod
    def assert_timing_behavior_correct(mock_time, expected_intervals):
        """Assert that timing-dependent behavior works correctly."""
        call_times = [call[0][0] for call in mock_time.call_args_list]
        
        for i, expected_interval in enumerate(expected_intervals):
            if i > 0:
                actual_interval = call_times[i] - call_times[i-1]
                assert actual_interval.total_seconds() == expected_interval


@pytest.fixture
def behavior_assertion():
    """Fixture providing behavior assertion helper."""
    return BehaviorAssertion()


# =============================================================================
# CONTRACT VERIFICATION HELPERS
# =============================================================================

def verify_kubernetes_client_contract(client_instance):
    """
    Verify that a Kubernetes client implementation satisfies the contract.
    London School principle: Ensure mocks and real implementations are interchangeable.
    """
    # Test connection method exists and returns correct structure
    result = client_instance.test_connection()
    assert isinstance(result, dict)
    assert 'success' in result
    assert 'message' in result
    
    # Test apply_crd method exists
    assert hasattr(client_instance, 'apply_crd')
    assert callable(client_instance.apply_crd)
    
    # Test fetch_crds method exists  
    assert hasattr(client_instance, 'fetch_crds_from_kubernetes')
    assert callable(client_instance.fetch_crds_from_kubernetes)


def verify_fabric_service_contract(service_instance):
    """
    Verify that a fabric service implementation satisfies the contract.
    """
    # Test required methods exist
    assert hasattr(service_instance, 'get_kubernetes_config')
    assert hasattr(service_instance, 'trigger_gitops_sync') 
    assert hasattr(service_instance, 'needs_sync')
    
    # Test method signatures and return types
    config = service_instance.get_kubernetes_config()
    assert config is None or isinstance(config, dict)


# =============================================================================
# TEST SCENARIO BUILDERS
# =============================================================================

class SyncScenarioBuilder:
    """
    Builder for creating complex sync test scenarios.
    London School principle: Focus on interaction scenarios rather than object state.
    """
    
    def __init__(self):
        self.kubernetes_scenario = 'success'
        self.fabric_scenario = 'valid'
        self.api_scenario = 'success'
        self.timing_scenario = 'normal'
    
    def with_kubernetes_failure(self):
        """Configure scenario with Kubernetes failures."""
        self.kubernetes_scenario = 'connection_failure'
        return self
    
    def with_fabric_misconfiguration(self):
        """Configure scenario with fabric misconfiguration."""
        self.fabric_scenario = 'invalid_config'
        return self
    
    def with_api_timeout(self):
        """Configure scenario with API timeouts."""
        self.api_scenario = 'timeout'
        return self
    
    def with_timing_issues(self):
        """Configure scenario with timing problems.""" 
        self.timing_scenario = 'delayed'
        return self
    
    def build_mocks(self):
        """Build configured mocks for the scenario."""
        return {
            'kubernetes_client': MockKubernetesClient(self.kubernetes_scenario),
            'fabric_service': MockFabricService(self.fabric_scenario),
            'api_client': MockAPIClient(self.api_scenario)
        }


@pytest.fixture
def sync_scenario_builder():
    """Fixture providing sync scenario builder."""
    return SyncScenarioBuilder()