"""
UI integration tests for YAML export workflow (DIET-143).

Per AGENTS.md requirements, these tests validate UX-accurate
integration flows including permissions enforcement.
"""

import yaml
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from users.models import ObjectPermission

from netbox_hedgehog.models.topology_planning import TopologyPlan

User = get_user_model()


class YAMLExportUITestCase(TestCase):
    """UX-accurate integration tests for YAML export."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.superuser = User.objects.create_user(
            username='admin',
            is_staff=True,
            is_superuser=True
        )

    def setUp(self):
        """Create fresh plan and client for each test."""
        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
            created_by=self.superuser
        )
        self.client = Client()

    def test_yaml_export_view_loads_successfully(self):
        """Verify YAML export view returns 200 for authenticated user."""
        self.client.force_login(self.superuser)

        url = reverse('plugins:netbox_hedgehog:topologyplan_yaml_export', kwargs={'pk': self.plan.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/x-yaml')

    def test_yaml_export_requires_permission(self):
        """Verify 403 when user lacks view permission."""
        # Create user without permissions
        unprivileged_user = User.objects.create_user(username='unprivileged')
        self.client.force_login(unprivileged_user)

        url = reverse('plugins:netbox_hedgehog:topologyplan_yaml_export', kwargs={'pk': self.plan.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_yaml_export_succeeds_with_object_permission(self):
        """Verify 200 when user has ObjectPermission for TopologyPlan view."""
        # Create user and grant object-level permission
        user = User.objects.create_user(username='viewer')
        permission = ObjectPermission.objects.create(
            name='View Topology Plans',
            actions=['view']
        )
        permission.users.add(user)
        permission.object_types.add(ContentType.objects.get_for_model(TopologyPlan))

        self.client.force_login(user)
        url = reverse('plugins:netbox_hedgehog:topologyplan_yaml_export', kwargs={'pk': self.plan.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/x-yaml')

    def test_yaml_export_contains_valid_yaml(self):
        """Verify response body is valid YAML with expected CRD types."""
        self.client.force_login(self.superuser)

        url = reverse('plugins:netbox_hedgehog:topologyplan_yaml_export', kwargs={'pk': self.plan.pk})
        response = self.client.get(url)

        # Parse YAML
        docs = list(yaml.safe_load_all(response.content.decode('utf-8')))

        # Verify contains documents (at minimum: VLANNamespace, IPv4Namespace)
        self.assertGreater(len(docs), 0)

        # Verify expected kinds present
        kinds = {doc['kind'] for doc in docs if isinstance(doc, dict)}
        self.assertIn('VLANNamespace', kinds)
        self.assertIn('IPv4Namespace', kinds)
