"""
Test-Driven Development for Drift Detection Feature

This test file defines the expected behavior BEFORE implementation.
These tests must pass for the drift detection feature to be considered complete.
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from netbox_hedgehog.models.fabric import HedgehogFabric


class DriftDetectionTDDTests(TestCase):
    """
    TDD Tests for Drift Detection Feature - Issue #53
    These tests define the REQUIRED behavior before implementation.
    """

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create test fabric with known drift
        self.test_fabric = HedgehogFabric.objects.create(
            name='Test_Fabric_With_Drift',
            description='Test fabric for drift detection',
            drift_count=2,
            drift_status='drift_detected'
        )
        
        # Create test fabric without drift
        self.clean_fabric = HedgehogFabric.objects.create(
            name='Clean_Test_Fabric',
            description='Test fabric without drift',
            drift_count=0,
            drift_status='in_sync'
        )

    def test_drift_detection_page_exists_and_accessible(self):
        """
        REQUIREMENT: Drift detection page must exist and be accessible
        URL: /plugins/hedgehog/drift-detection/
        """
        self.client.login(username='testuser', password='testpass123')
        
        # The URL must exist and return 200 (not 500 error)
        response = self.client.get('/plugins/hedgehog/drift-detection/')
        self.assertEqual(response.status_code, 200, "Drift detection page must be accessible without errors")
        
        # Must contain expected content
        self.assertContains(response, "Drift Detection Dashboard", msg_prefix="Page must have correct title")

    def test_dashboard_drift_metric_is_hyperlinked(self):
        """
        REQUIREMENT: Dashboard drift metric must be clickable link to drift detection page
        """
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/plugins/hedgehog/')
        self.assertEqual(response.status_code, 200)
        
        # Must contain hyperlink to drift detection page
        self.assertContains(
            response, 
            'href="/plugins/hedgehog/drift-detection/"',
            msg_prefix="Dashboard drift metric must be hyperlinked to drift detection page"
        )

    def test_dashboard_shows_correct_drift_total(self):
        """
        REQUIREMENT: Dashboard must show cumulative drift count across all fabrics
        Expected: 2 (from test_fabric) + 0 (from clean_fabric) = 2 total
        """
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/plugins/hedgehog/')
        self.assertEqual(response.status_code, 200)
        
        # Must show cumulative drift count of 2
        self.assertContains(
            response,
            '<h2>2</h2>',  # The drift metric value
            msg_prefix="Dashboard must show cumulative drift count of 2"
        )
        self.assertContains(
            response,
            'Drift Detected',
            msg_prefix="Dashboard must show 'Drift Detected' label"
        )

    def test_fabric_detail_drift_count_is_hyperlinked(self):
        """
        REQUIREMENT: Fabric detail page drift count must be clickable link
        """
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(f'/plugins/hedgehog/fabrics/{self.test_fabric.id}/')
        self.assertEqual(response.status_code, 200)
        
        # Drift count must be hyperlinked to filtered drift detection page
        expected_link = f'/plugins/hedgehog/drift-detection/fabric/{self.test_fabric.id}/'
        self.assertContains(
            response,
            f'href="{expected_link}"',
            msg_prefix="Fabric detail drift count must be hyperlinked to filtered drift detection page"
        )

    def test_navigation_bar_contains_drift_detection_link(self):
        """
        REQUIREMENT: Navigation bar must contain link to drift detection page
        """
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/plugins/hedgehog/')
        self.assertEqual(response.status_code, 200)
        
        # Navigation must contain drift detection link
        self.assertContains(
            response,
            '/plugins/hedgehog/drift-detection/',
            msg_prefix="Navigation bar must contain link to drift detection page"
        )

    def test_drift_detection_page_template_urls_are_correct(self):
        """
        REQUIREMENT: Drift detection page must not have URL namespace errors
        """
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/plugins/hedgehog/drift-detection/')
        self.assertEqual(response.status_code, 200, "Page must load without NoReverseMatch errors")
        
        # Must not contain server errors
        self.assertNotContains(
            response,
            "Server Error",
            msg_prefix="Drift detection page must not have server errors"
        )
        self.assertNotContains(
            response,
            "NoReverseMatch",
            msg_prefix="Drift detection page must not have URL namespace errors"
        )

    def test_drift_detection_page_shows_correct_data(self):
        """
        REQUIREMENT: Drift detection page must show correct drift statistics
        """
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/plugins/hedgehog/drift-detection/')
        self.assertEqual(response.status_code, 200)
        
        # Must show test fabric with drift
        self.assertContains(
            response,
            self.test_fabric.name,
            msg_prefix="Drift detection page must show fabric with drift"
        )

    def test_filtered_drift_detection_page_works(self):
        """
        REQUIREMENT: Fabric-filtered drift detection page must work
        """
        self.client.login(username='testuser', password='testpass123')
        
        url = f'/plugins/hedgehog/drift-detection/fabric/{self.test_fabric.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, "Filtered drift detection page must be accessible")

    def tearDown(self):
        """Clean up test data"""
        HedgehogFabric.objects.all().delete()
        User.objects.all().delete()


class DriftDetectionGUITests(TestCase):
    """
    GUI-specific tests for drift detection using proper testing tools
    These ensure the user experience works correctly
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='guitest',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.test_fabric = HedgehogFabric.objects.create(
            name='GUI_Test_Fabric',
            description='Fabric for GUI testing',
            drift_count=3,
            drift_status='drift_detected'
        )

    def test_clickable_dashboard_drift_metric(self):
        """Test that dashboard drift metric is actually clickable"""
        self.client.login(username='guitest', password='testpass123')
        
        response = self.client.get('/plugins/hedgehog/')
        self.assertEqual(response.status_code, 200)
        
        # Extract the drift metric link and test it
        content = response.content.decode('utf-8')
        self.assertIn('href="/plugins/hedgehog/drift-detection/"', content)
        
        # Follow the link to ensure it works
        drift_response = self.client.get('/plugins/hedgehog/drift-detection/')
        self.assertEqual(drift_response.status_code, 200)

    def test_clickable_fabric_drift_count(self):
        """Test that fabric drift count is actually clickable"""
        self.client.login(username='guitest', password='testpass123')
        
        response = self.client.get(f'/plugins/hedgehog/fabrics/{self.test_fabric.id}/')
        self.assertEqual(response.status_code, 200)
        
        # Test filtered drift detection link works
        filtered_url = f'/plugins/hedgehog/drift-detection/fabric/{self.test_fabric.id}/'
        filtered_response = self.client.get(filtered_url)
        self.assertEqual(filtered_response.status_code, 200)

    def tearDown(self):
        HedgehogFabric.objects.all().delete()
        User.objects.all().delete()


if __name__ == '__main__':
    pytest.main([__file__])