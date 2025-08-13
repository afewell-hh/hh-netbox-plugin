"""
Kubernetes API client mocks for London School TDD approach.
These mocks define the contracts and expected interactions with the K8s API.
"""

from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class MockK8sResponse:
    """Mock response from K8s API."""
    status_code: int
    data: Dict[str, Any]
    headers: Dict[str, str] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {'Content-Type': 'application/json'}


class K8sApiMockBuilder:
    """Builder for creating K8s API mocks with specific behaviors."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset mock builder to clean state."""
        self.connection_behavior = 'success'
        self.auth_behavior = 'success'
        self.api_responses = {}
        self.error_scenarios = {}
        self.timing_behavior = 'normal'
        return self
    
    def with_connection_timeout(self, timeout_seconds: float = 30.0):
        """Configure mock to simulate connection timeout."""
        self.connection_behavior = 'timeout'
        self.error_scenarios['timeout'] = timeout_seconds
        return self
    
    def with_connection_refused(self):
        """Configure mock to simulate connection refused."""
        self.connection_behavior = 'refused'
        return self
    
    def with_dns_failure(self):
        """Configure mock to simulate DNS resolution failure."""
        self.connection_behavior = 'dns_failure'
        return self
    
    def with_auth_failure(self, error_type: str = 'invalid_token'):
        """Configure mock to simulate authentication failure."""
        self.auth_behavior = 'failure'
        self.error_scenarios['auth_error'] = error_type
        return self
    
    def with_api_server_error(self, status_code: int = 500):
        """Configure mock to simulate API server error."""
        self.api_responses['error'] = MockK8sResponse(
            status_code=status_code,
            data={'error': f'API server error {status_code}'}
        )
        return self
    
    def with_crd_not_found(self):
        """Configure mock to simulate CRD not found."""
        self.api_responses['crd_not_found'] = MockK8sResponse(
            status_code=404,
            data={'error': 'Custom Resource Definition not found'}
        )
        return self
    
    def with_successful_sync(self, resource_count: int = 5):
        """Configure mock for successful sync scenario."""
        self.api_responses['list_crds'] = MockK8sResponse(
            status_code=200,
            data={
                'items': [
                    self._create_mock_crd(f'test-crd-{i}', 'VPC')
                    for i in range(resource_count)
                ]
            }
        )
        return self
    
    def with_slow_response(self, delay_seconds: float = 5.0):
        """Configure mock to simulate slow API responses."""
        self.timing_behavior = 'slow'
        self.error_scenarios['delay'] = delay_seconds
        return self
    
    def with_intermittent_failures(self, failure_rate: float = 0.3):
        """Configure mock to simulate intermittent failures."""
        self.timing_behavior = 'intermittent'
        self.error_scenarios['failure_rate'] = failure_rate
        return self
    
    def build(self) -> Mock:
        """Build the configured K8s API mock."""
        mock_client = Mock()
        
        # Configure connection behavior
        if self.connection_behavior == 'timeout':
            mock_client.connect.side_effect = ConnectionTimeoutError(
                f"Connection timeout after {self.error_scenarios.get('timeout', 30)}s"
            )
        elif self.connection_behavior == 'refused':
            mock_client.connect.side_effect = ConnectionRefusedError(
                "Connection refused by Kubernetes API server"
            )
        elif self.connection_behavior == 'dns_failure':
            mock_client.connect.side_effect = DNSResolutionError(
                "DNS resolution failed for Kubernetes server"
            )
        else:
            mock_client.connect.return_value = True
        
        # Configure authentication behavior
        if self.auth_behavior == 'failure':
            auth_error_type = self.error_scenarios.get('auth_error', 'invalid_token')
            if auth_error_type == 'invalid_token':
                mock_client.authenticate.side_effect = AuthenticationError(
                    "Invalid service account token"
                )
            elif auth_error_type == 'token_expired':
                mock_client.authenticate.side_effect = AuthenticationError(
                    "Service account token has expired"
                )
            elif auth_error_type == 'insufficient_permissions':
                mock_client.authenticate.side_effect = PermissionError(
                    "Insufficient RBAC permissions"
                )
        else:
            mock_client.authenticate.return_value = True
        
        # Configure API response behaviors
        self._configure_api_methods(mock_client)
        
        return mock_client
    
    def _create_mock_crd(self, name: str, kind: str) -> Dict[str, Any]:
        """Create a mock CRD object."""
        return {
            'apiVersion': 'hedgehog.githedgehog.com/v1alpha2',
            'kind': kind,
            'metadata': {
                'name': name,
                'namespace': 'default',
                'resourceVersion': '12345',
                'creationTimestamp': datetime.utcnow().isoformat() + 'Z',
                'labels': {'app': 'hedgehog'},
                'annotations': {'kubectl.kubernetes.io/last-applied-configuration': '{}'}
            },
            'spec': {
                'subnet': '10.0.0.0/24' if kind == 'VPC' else {},
                'description': f'Test {kind} resource'
            },
            'status': {
                'phase': 'Ready',
                'conditions': [
                    {
                        'type': 'Ready',
                        'status': 'True',
                        'lastTransitionTime': datetime.utcnow().isoformat() + 'Z',
                        'reason': 'ReconcileSuccess'
                    }
                ]
            }
        }
    
    def _configure_api_methods(self, mock_client: Mock):
        """Configure API method behaviors."""
        # List CRDs method
        if 'list_crds' in self.api_responses:
            response = self.api_responses['list_crds']
            mock_client.list_custom_resources.return_value = response
        elif 'crd_not_found' in self.api_responses:
            response = self.api_responses['crd_not_found']
            mock_client.list_custom_resources.side_effect = K8sApiError(
                response.status_code, response.data['error']
            )
        else:
            # Default successful response
            mock_client.list_custom_resources.return_value = MockK8sResponse(
                status_code=200,
                data={'items': []}
            )
        
        # Cluster info method
        mock_client.get_cluster_info.return_value = {
            'version': {'gitVersion': 'v1.29.0'},
            'serverAddressByClientCIDRs': [
                {'clientCIDR': '0.0.0.0/0', 'serverAddress': 'vlab-art.l.hhdev.io:6443'}
            ]
        }


# Custom exception classes for K8s API mocking
class ConnectionTimeoutError(Exception):
    """Simulates connection timeout to K8s API."""
    pass


class ConnectionRefusedError(Exception):
    """Simulates connection refused by K8s API."""
    pass


class DNSResolutionError(Exception):
    """Simulates DNS resolution failure."""
    pass


class AuthenticationError(Exception):
    """Simulates authentication failure."""
    pass


class K8sApiError(Exception):
    """Generic K8s API error."""
    
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"K8s API error {status_code}: {message}")


# Pre-built mock scenarios for common testing patterns
class K8sMockScenarios:
    """Pre-built mock scenarios for common testing patterns."""
    
    @staticmethod
    def healthy_cluster() -> Mock:
        """Mock for a healthy, responsive K8s cluster."""
        return (K8sApiMockBuilder()
                .with_successful_sync(resource_count=10)
                .build())
    
    @staticmethod
    def network_timeout() -> Mock:
        """Mock for network timeout scenario."""
        return (K8sApiMockBuilder()
                .with_connection_timeout(30.0)
                .build())
    
    @staticmethod
    def authentication_failed() -> Mock:
        """Mock for authentication failure scenario."""
        return (K8sApiMockBuilder()
                .with_auth_failure('invalid_token')
                .build())
    
    @staticmethod
    def api_server_down() -> Mock:
        """Mock for API server error scenario."""
        return (K8sApiMockBuilder()
                .with_api_server_error(503)
                .build())
    
    @staticmethod
    def crds_not_installed() -> Mock:
        """Mock for missing CRDs scenario."""
        return (K8sApiMockBuilder()
                .with_crd_not_found()
                .build())
    
    @staticmethod
    def slow_cluster() -> Mock:
        """Mock for slow but functional cluster."""
        return (K8sApiMockBuilder()
                .with_successful_sync(resource_count=5)
                .with_slow_response(8.0)
                .build())
    
    @staticmethod
    def intermittent_failures() -> Mock:
        """Mock for cluster with intermittent failures."""
        return (K8sApiMockBuilder()
                .with_successful_sync(resource_count=3)
                .with_intermittent_failures(0.3)
                .build())


# Context managers for mock patching
@patch('netbox_hedgehog.utils.k8s_client.KubernetesClient')
def mock_k8s_client_patch(mock_class, behavior_builder: K8sApiMockBuilder = None):
    """Context manager for mocking K8s client with specific behavior."""
    if behavior_builder is None:
        behavior_builder = K8sApiMockBuilder()
    
    mock_instance = behavior_builder.build()
    mock_class.return_value = mock_instance
    
    return mock_instance


# Assertion helpers for verifying mock interactions
class K8sMockAssertions:
    """Helper class for asserting K8s mock interactions."""
    
    @staticmethod
    def assert_connection_attempted(mock_client: Mock):
        """Assert that connection to K8s was attempted."""
        assert mock_client.connect.called, "Expected K8s connection attempt"
    
    @staticmethod
    def assert_authentication_attempted(mock_client: Mock):
        """Assert that authentication was attempted."""
        assert mock_client.authenticate.called, "Expected K8s authentication attempt"
    
    @staticmethod
    def assert_crd_list_called(mock_client: Mock, crd_type: Optional[str] = None):
        """Assert that CRD listing was called."""
        assert mock_client.list_custom_resources.called, "Expected CRD list operation"
        
        if crd_type:
            call_args = mock_client.list_custom_resources.call_args
            assert crd_type in str(call_args), f"Expected {crd_type} in CRD list call"
    
    @staticmethod
    def assert_retry_with_backoff(mock_client: Mock, min_calls: int = 2):
        """Assert that retries were attempted with exponential backoff."""
        call_count = mock_client.connect.call_count
        assert call_count >= min_calls, (
            f"Expected at least {min_calls} retry attempts, got {call_count}"
        )
    
    @staticmethod
    def assert_no_retry_after_auth_failure(mock_client: Mock):
        """Assert that no retries occurred after authentication failure."""
        # Authentication failures should not trigger automatic retries
        assert mock_client.authenticate.call_count <= 1, (
            "Auth failures should not trigger automatic retries"
        )