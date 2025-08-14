"""
TDD Drift Detection Test Configuration

Pytest configuration and fixtures for TDD drift detection test suite.
Provides common test setup and utilities for all drift detection tests.
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth.models import User
from netbox_hedgehog.models.fabric import HedgehogFabric


@pytest.fixture
def authenticated_client():
    """
    Fixture providing authenticated Django test client
    
    Returns:
        tuple: (client, user) - Django test client and authenticated user
    """
    client = Client()
    user = User.objects.create_user(
        username='testuser',
        password='testpass123',
        is_staff=True,
        is_superuser=True
    )
    client.login(username='testuser', password='testpass123')
    return client, user


@pytest.fixture
def drift_fabric():
    """
    Fixture providing a fabric with drift for testing
    
    Returns:
        HedgehogFabric: Fabric with drift_count > 0 and drift_detected status
    """
    return HedgehogFabric.objects.create(
        name='Test_Drift_Fabric',
        description='Test fabric with drift for TDD testing',
        drift_count=3,
        drift_status='drift_detected'
    )


@pytest.fixture  
def clean_fabric():
    """
    Fixture providing a fabric without drift for testing
    
    Returns:
        HedgehogFabric: Fabric with drift_count = 0 and in_sync status
    """
    return HedgehogFabric.objects.create(
        name='Test_Clean_Fabric',
        description='Test fabric without drift for TDD testing',
        drift_count=0,
        drift_status='in_sync'
    )


@pytest.fixture
def multiple_fabric_environment():
    """
    Fixture providing multiple fabrics with various drift states
    
    Returns:
        dict: Dictionary with fabric categories (high_drift, low_drift, clean)
    """
    high_drift = HedgehogFabric.objects.create(
        name='High_Drift_Fabric',
        description='Fabric with high drift count',
        drift_count=5,
        drift_status='drift_detected'
    )
    
    low_drift = HedgehogFabric.objects.create(
        name='Low_Drift_Fabric', 
        description='Fabric with low drift count',
        drift_count=1,
        drift_status='drift_detected'
    )
    
    clean = HedgehogFabric.objects.create(
        name='Clean_Fabric',
        description='Fabric without drift',
        drift_count=0,
        drift_status='in_sync'
    )
    
    return {
        'high_drift': high_drift,
        'low_drift': low_drift,
        'clean': clean
    }


class DriftDetectionTestMixin:
    """
    Mixin class providing common test utilities for drift detection tests
    """
    
    def assert_drift_hyperlink_exists(self, response, fabric_id=None):
        """
        Assert that drift detection hyperlink exists in response
        
        Args:
            response: Django test response object
            fabric_id: Optional fabric ID for fabric-filtered links
        """
        if fabric_id:
            expected_url = f'/plugins/hedgehog/drift-detection/fabric/{fabric_id}/'
        else:
            expected_url = '/plugins/hedgehog/drift-detection/'
        
        self.assertContains(response, f'href="{expected_url}"',
                           msg_prefix=f"Response must contain hyperlink to {expected_url}")
    
    def assert_drift_count_displayed(self, response, expected_count):
        """
        Assert that specific drift count is displayed in response
        
        Args:
            response: Django test response object  
            expected_count: Expected drift count number
        """
        self.assertContains(response, f'<h2>{expected_count}</h2>',
                           msg_prefix=f"Response must display drift count of {expected_count}")
    
    def assert_fabric_appears_in_drift_list(self, response, fabric):
        """
        Assert that fabric appears in drift detection listing
        
        Args:
            response: Django test response object
            fabric: HedgehogFabric instance that should appear
        """
        self.assertContains(response, fabric.name,
                           msg_prefix=f"Drift detection page must show fabric {fabric.name}")
        self.assertContains(response, str(fabric.drift_count),
                           msg_prefix=f"Drift detection page must show drift count {fabric.drift_count}")
    
    def assert_page_has_proper_structure(self, response, required_elements):
        """
        Assert that page contains proper HTML structure elements
        
        Args:
            response: Django test response object
            required_elements: List of HTML elements that must be present
        """
        content = response.content.decode('utf-8').lower()
        
        for element in required_elements:
            self.assertIn(element.lower(), content,
                         f"Page must contain HTML element: {element}")


class DriftDetectionTestCase(TestCase, DriftDetectionTestMixin):
    """
    Base test case class for drift detection TDD tests
    
    Combines Django TestCase with drift detection test utilities
    """
    
    def setUp(self):
        """Common setup for all drift detection tests"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='drifttest',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
    
    def tearDown(self):
        """Common cleanup for all drift detection tests"""
        HedgehogFabric.objects.all().delete()
        User.objects.all().delete()
    
    def login(self):
        """Convenience method to log in test user"""
        return self.client.login(username='drifttest', password='testpass123')