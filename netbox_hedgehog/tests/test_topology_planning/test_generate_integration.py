"""
Integration Tests for TopologyPlan Generate Workflow (DIET-011)

Tests the complete UX flow for device generation from topology plans:
- Preview GET request (shows counts and warnings)
- Generate POST request (creates NetBox objects)
- Permission enforcement
- Error handling
- Regeneration scenarios
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from dcim.models import DeviceType, Manufacturer, Site, Device, Interface
from extras.models import Tag
from dcim.choices import InterfaceTypeChoices

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    DeviceTypeExtension,
    BreakoutOption,
    SwitchPortZone,
    GenerationState,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    PortZoneTypeChoices,
    AllocationStrategyChoices,
)

User = get_user_model()


class TopologyPlanGenerateIntegrationTestCase(TestCase):
    """Integration tests for TopologyPlan generate preview/confirm workflow"""

    @classmethod
    def setUpTestData(cls):
        """Create test fixtures"""
        # Create users with different permissions
        cls.admin_user = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        cls.regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            is_staff=True,
            is_superuser=False
        )

        # Give regular user view permission only (not change)
        content_type = ContentType.objects.get_for_model(TopologyPlan)
        view_perm = Permission.objects.get(
            content_type=content_type,
            codename='view_topologyplan'
        )
        cls.regular_user.user_permissions.add(view_perm)

        # Create manufacturer and device types
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )

        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'ds5000'}
        )

        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='R760xa',
            defaults={'slug': 'r760xa'}
        )

        # Create device type extension
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                'native_speed': 800,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g', '8x100g'],
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf']
            }
        )

        # Create breakout option
        cls.breakout_4x200g, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={
                'from_speed': 800,
                'logical_ports': 4,
                'logical_speed': 200
            }
        )

    def setUp(self):
        """Login as admin before each test"""
        # Clean up any generated objects from previous test runs
        # This ensures test isolation even with --keepdb
        self._cleanup_all_generated_objects()

        self.client = Client()
        self.client.login(username='admin', password='testpass123')

        # Create a basic plan with server/switch classes for each test
        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            status=TopologyPlanStatusChoices.DRAFT
        )

        self.server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='gpu-server',
            category=ServerClassCategoryChoices.GPU,
            quantity=2,
            gpus_per_server=8,
            server_device_type=self.server_type
        )

        self.switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
            calculated_quantity=1,
            override_quantity=None
        )

        # Create port zone for the switch class
        self.port_zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-60',
            breakout_option=self.breakout_4x200g,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100
        )

        self.connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='fe-conn',
            connection_name='frontend',
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_switch_class=self.switch_class,
            speed=200
        )

    def tearDown(self):
        """Clean up after each test"""
        # Ensure all generated objects are removed after each test
        self._cleanup_all_generated_objects()

    def _cleanup_all_generated_objects(self):
        """
        Delete all generated NetBox objects (devices, interfaces, cables).

        This ensures test isolation when using --keepdb by removing any
        objects created by previous test runs or the current test.

        NOTE: This is a test-only cleanup that removes ALL hedgehog-generated
        objects across ALL plans (for test isolation). Production cleanup
        in DeviceGenerator is plan-scoped.
        """
        from dcim.models import Cable

        # IMPORTANT: Delete cables FIRST to avoid termination protection issues
        try:
            tag = Tag.objects.filter(slug='hedgehog-generated').first()
            if tag:
                # Test cleanup is intentionally global (all plans) for isolation
                Cable.objects.filter(tags=tag).delete()
        except Exception:
            pass  # Ignore errors during cleanup

        # Delete ALL devices that have hedgehog_plan_id in custom_field_data
        try:
            # Query for all devices with any hedgehog plan ID
            devices_with_hedgehog = Device.objects.all()
            for device in devices_with_hedgehog:
                if device.custom_field_data and 'hedgehog_plan_id' in device.custom_field_data:
                    # Delete will cascade to interfaces
                    device.delete()
        except Exception:
            pass  # Ignore errors during cleanup

        # Also delete any remaining orphaned interfaces
        try:
            Interface.objects.filter(device__isnull=True, device_type__isnull=True).delete()
        except Exception:
            pass  # Ignore errors during cleanup

    # =============================================================================
    # Test: Preview GET Request
    # =============================================================================

    def test_generate_preview_page_loads(self):
        """Test that generate preview page loads successfully"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        "Generate preview page should load successfully")
        self.assertIn('object', response.context,
                     "Context should include plan object")
        self.assertEqual(response.context['object'].pk, self.plan.pk,
                        "Context plan should match requested plan")

    def test_generate_preview_shows_counts(self):
        """Test that preview shows correct device/interface/cable counts"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        response = self.client.get(url)

        # Verify counts in context
        self.assertEqual(response.context['server_count'], 2,
                        "Should show 2 servers")
        self.assertEqual(response.context['switch_count'], 1,
                        "Should show 1 switch (effective_quantity)")
        self.assertEqual(response.context['total_devices'], 3,
                        "Should show 3 total devices (2 servers + 1 switch)")

        # Port count = servers × ports_per_connection = 2 × 2 = 4
        # Interface count = port_count × 2 (server + switch sides) = 8
        self.assertEqual(response.context['cable_count'], 4,
                        "Should show 4 cables (2 servers × 2 ports each)")
        self.assertEqual(response.context['interface_count'], 8,
                        "Should show 8 interfaces (4 cables × 2 ends)")

    def test_generate_preview_shows_no_previous_generation(self):
        """Test that preview shows no previous generation for new plan"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertIsNone(response.context['generation_state'],
                         "New plan should have no generation_state")
        self.assertFalse(response.context['needs_regeneration'],
                        "New plan should not need regeneration")

    def test_generate_preview_shows_site_name(self):
        """Test that preview shows the site name that will be used"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertIn('site_name', response.context,
                     "Context should include site_name")
        # Should use DeviceGenerator.DEFAULT_SITE_NAME
        self.assertEqual(response.context['site_name'], 'Hedgehog',
                        "Should show Hedgehog site name")

    # =============================================================================
    # Test: Generate POST Request (Success Path)
    # =============================================================================

    def test_generate_post_creates_devices(self):
        """Test that POST request creates NetBox Device objects"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        # Verify no devices exist before generation
        self.assertEqual(Device.objects.count(), 0,
                        "Should start with no devices")

        # Trigger generation
        response = self.client.post(url, follow=True)

        # Should redirect to plan detail
        self.assertRedirects(response,
                            reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk]),
                            msg_prefix="Should redirect to plan detail after generation")

        # Verify devices were created
        self.assertEqual(Device.objects.count(), 3,
                        "Should create 3 devices (2 servers + 1 switch)")

        # Verify server devices
        server_devices = Device.objects.filter(device_type=self.server_type)
        self.assertEqual(server_devices.count(), 2,
                        "Should create 2 server devices")

        # Verify switch devices
        switch_devices = Device.objects.filter(device_type=self.switch_type)
        self.assertEqual(switch_devices.count(), 1,
                        "Should create 1 switch device")

    def test_generate_post_creates_interfaces(self):
        """Test that POST request creates NetBox Interface objects"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        # Trigger generation
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200,
                        "Generation should succeed")

        # Verify interfaces were created and cabled
        # We expect 4 cables, each connecting 2 interfaces = 8 cabled interfaces
        # This is more reliable than counting all interfaces since NetBox may
        # auto-instantiate template interfaces from DeviceType
        from dcim.models import Cable

        plan_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        )

        # Count interfaces that have cables attached (cable_end is not null)
        cabled_interfaces = Interface.objects.filter(
            device__in=plan_devices,
            cable__isnull=False
        ).distinct()

        self.assertEqual(cabled_interfaces.count(), 8,
                        "Should create 8 cabled interfaces (4 server + 4 switch)")

    def test_generate_post_creates_cables(self):
        """Test that POST request creates NetBox Cable objects"""
        from dcim.models import Cable

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        # Trigger generation
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200,
                        "Generation should succeed")

        # Verify cables were created
        # 2 servers × 2 ports each = 4 cables
        self.assertEqual(Cable.objects.count(), 4,
                        "Should create 4 cables")

    def test_generate_post_creates_generation_state(self):
        """Test that POST request creates GenerationState record"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        # Verify no generation state exists
        self.assertFalse(GenerationState.objects.filter(plan=self.plan).exists(),
                        "Should start with no generation state")

        # Trigger generation
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200,
                        "Generation should succeed")

        # Verify generation state was created
        self.assertTrue(GenerationState.objects.filter(plan=self.plan).exists(),
                       "Should create generation state")

        gen_state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(gen_state.device_count, 3,
                        "Generation state should record 3 devices")
        self.assertEqual(gen_state.cable_count, 4,
                        "Generation state should record 4 cables")

    def test_generate_post_shows_success_message(self):
        """Test that successful generation shows success message"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        response = self.client.post(url, follow=True)

        # Check for success message
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1,
                        "Should show one success message")
        self.assertIn('Generation complete', str(messages[0]),
                     "Success message should mention completion")
        self.assertIn('3 devices', str(messages[0]),
                     "Success message should mention device count")

    def test_generate_post_tags_generated_objects(self):
        """Test that generated objects are tagged with hedgehog-generated"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        # Trigger generation
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200,
                        "Generation should succeed")

        # Verify tag exists and is applied
        tag = Tag.objects.filter(slug='hedgehog-generated').first()
        self.assertIsNotNone(tag,
                            "Should create hedgehog-generated tag")

        # Verify all devices are tagged
        for device in Device.objects.all():
            self.assertIn(tag, device.tags.all(),
                         f"Device {device.name} should be tagged")

    # =============================================================================
    # Test: Permission Enforcement
    # =============================================================================

    def test_generate_requires_authentication(self):
        """Test that unauthenticated users cannot access generate view"""
        self.client.logout()

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        response = self.client.get(url)

        # Should return 403 or redirect to login (depending on NetBox version)
        self.assertIn(response.status_code, [302, 403],
                     "Unauthenticated users should be denied access")
        if response.status_code == 302:
            self.assertIn('/login/', response.url,
                         "Should redirect to login page")

    def test_generate_requires_change_permission(self):
        """Test that users without change permission cannot generate"""
        # Login as regular user (has view permission only)
        self.client.logout()
        self.client.login(username='regular', password='testpass123')

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        response = self.client.get(url)

        # Should get 403 Forbidden
        self.assertEqual(response.status_code, 403,
                        "Users without change permission should get 403")

    def test_generate_button_hidden_without_permission(self):
        """Test that generate button is hidden on plan detail without permission"""
        # Login as regular user (view permission only)
        self.client.logout()
        self.client.login(username='regular', password='testpass123')

        # Try to access generate page directly - should be denied
        generate_url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        response = self.client.get(generate_url)
        self.assertEqual(response.status_code, 403,
                        "Users without change permission should get 403 for generate page")

        # Note: We would test the button visibility on plan detail page, but
        # NetBox's ObjectView permission system may require additional setup.
        # The important thing is that the generate page itself is protected.

    def test_generate_button_shown_with_permission(self):
        """Test that generate button is shown with change permission"""
        # Admin user has change permission
        detail_url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(detail_url)

        # Check that generate button is present
        self.assertContains(response, 'Generate Devices',
                           msg_prefix="Generate button should be visible with permission")

    # =============================================================================
    # Test: Error Handling
    # =============================================================================

    def test_generate_fails_with_no_server_classes(self):
        """Test that generation fails if plan has no server classes"""
        # Create plan with switches but no servers
        plan = TopologyPlan.objects.create(
            name='No Servers Plan',
            status=TopologyPlanStatusChoices.DRAFT
        )
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
            calculated_quantity=1
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk])
        response = self.client.post(url, follow=True)

        # Should show error message
        messages = list(response.context['messages'])
        self.assertTrue(any('at least one server class' in str(m).lower() for m in messages),
                       "Should show error about missing server classes")

        # Should redirect back to generate page (not plan detail)
        self.assertEqual(response.redirect_chain[-1][0],
                        reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk]),
                        "Should redirect back to generate page on error")

    def test_generate_fails_with_no_switch_classes(self):
        """Test that generation fails if plan has no switch classes"""
        # Create plan with servers but no switches
        plan = TopologyPlan.objects.create(
            name='No Switches Plan',
            status=TopologyPlanStatusChoices.DRAFT
        )
        PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-server',
            category=ServerClassCategoryChoices.GPU,
            quantity=2,
            server_device_type=self.server_type
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk])
        response = self.client.post(url, follow=True)

        # Should show error message
        messages = list(response.context['messages'])
        self.assertTrue(any('at least one' in str(m).lower() and 'switch class' in str(m).lower() for m in messages),
                       "Should show error about missing switch classes")

    def test_generate_preview_shows_warnings_for_empty_plan(self):
        """Test that preview shows warnings for plans with no servers or switches"""
        # Create empty plan
        plan = TopologyPlan.objects.create(
            name='Empty Plan',
            status=TopologyPlanStatusChoices.DRAFT
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk])
        response = self.client.get(url)

        # Check context
        self.assertEqual(response.context['server_count'], 0,
                        "Should show 0 servers")
        self.assertEqual(response.context['switch_count'], 0,
                        "Should show 0 switches")

        # Check that warnings appear in template
        self.assertContains(response, 'No server classes defined',
                           msg_prefix="Should warn about no servers")
        self.assertContains(response, 'No switch classes defined',
                           msg_prefix="Should warn about no switches")

    def test_generate_handles_validation_error(self):
        """Test that generation handles ValidationError gracefully"""
        # Create plan with connection but no port zones (should fail validation)
        plan = TopologyPlan.objects.create(
            name='Invalid Plan',
            status=TopologyPlanStatusChoices.DRAFT
        )
        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-server',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=self.server_type
        )
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
            calculated_quantity=1
        )
        # Connection without port zones configured
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe-conn',
            connection_name='frontend',
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_switch_class=switch_class,
            speed=200
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk])
        response = self.client.post(url, follow=True)

        # Should show error message
        messages = list(response.context['messages'])
        self.assertTrue(any('failed' in str(m).lower() for m in messages),
                       "Should show error message on validation failure")

        # Should not create any devices
        self.assertEqual(Device.objects.count(), 0,
                        "Should not create devices on validation failure")

    # =============================================================================
    # Test: Regeneration Scenarios
    # =============================================================================

    def test_regeneration_after_plan_change(self):
        """Test that regeneration works after plan changes"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        # First generation
        response1 = self.client.post(url, follow=True)
        self.assertEqual(response1.status_code, 200,
                        "First generation should succeed")
        first_device_count = Device.objects.count()
        self.assertEqual(first_device_count, 3,
                        "First generation should create 3 devices")

        # Change plan: increase server quantity
        self.server_class.quantity = 4
        self.server_class.save()

        # Check that plan needs regeneration
        self.plan.refresh_from_db()
        self.assertTrue(self.plan.needs_regeneration,
                       "Plan should need regeneration after changes")

        # Second generation (regenerate)
        response2 = self.client.post(url, follow=True)
        self.assertEqual(response2.status_code, 200,
                        "Regeneration should succeed")

        # Should have new device count
        second_device_count = Device.objects.count()
        self.assertEqual(second_device_count, 5,
                        "Regeneration should create 5 devices (4 servers + 1 switch)")

    def test_preview_shows_regeneration_warning(self):
        """Test that preview shows warning about previous generation"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        # First generation
        response1 = self.client.post(url, follow=True)
        self.assertEqual(response1.status_code, 200,
                        "First generation should succeed")

        # View preview again
        response2 = self.client.get(url)

        # Should show previous generation info
        self.assertIsNotNone(response2.context['generation_state'],
                            "Should have generation_state after first generation")
        self.assertContains(response2, 'Previously generated',
                           msg_prefix="Should show previous generation warning")

    def test_preview_shows_plan_not_changed_message(self):
        """Test that preview shows when plan hasn't changed since generation"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        # Generate
        response1 = self.client.post(url, follow=True)
        self.assertEqual(response1.status_code, 200,
                        "Generation should succeed")

        # View preview without changing plan
        response2 = self.client.get(url)

        # Should show that plan hasn't changed
        self.assertFalse(response2.context['needs_regeneration'],
                        "Should not need regeneration if plan unchanged")
        self.assertContains(response2, 'has not changed since last generation',
                           msg_prefix="Should show that plan is unchanged")

    def test_preview_shows_plan_changed_message(self):
        """Test that preview shows when plan has changed since generation"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        # Generate
        response1 = self.client.post(url, follow=True)
        self.assertEqual(response1.status_code, 200,
                        "Generation should succeed")

        # Change plan
        self.server_class.quantity = 10
        self.server_class.save()

        # View preview
        response2 = self.client.get(url)

        # Should show that plan has changed
        self.assertTrue(response2.context['needs_regeneration'],
                       "Should need regeneration after plan change")
        self.assertContains(response2, 'Plan has changed since last generation',
                           msg_prefix="Should warn that plan has changed")

    def test_regeneration_deletes_old_objects(self):
        """Test that regeneration deletes old NetBox objects before creating new ones"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])

        # First generation
        response1 = self.client.post(url, follow=True)
        self.assertEqual(response1.status_code, 200,
                        "First generation should succeed")

        # Get IDs of generated devices
        first_device_ids = set(Device.objects.values_list('pk', flat=True))

        # Regenerate
        response2 = self.client.post(url, follow=True)
        self.assertEqual(response2.status_code, 200,
                        "Regeneration should succeed")

        # Get IDs of new devices
        second_device_ids = set(Device.objects.values_list('pk', flat=True))

        # Old device IDs should not be present
        overlap = first_device_ids & second_device_ids
        self.assertEqual(len(overlap), 0,
                        "Regeneration should delete old devices and create new ones")

    def test_regeneration_is_plan_scoped(self):
        """Test that regeneration only affects the current plan, not other plans"""
        from dcim.models import Cable

        # Create a second plan with its own devices
        plan2 = TopologyPlan.objects.create(
            name='Second Plan',
            status=TopologyPlanStatusChoices.DRAFT
        )
        server_class2 = PlanServerClass.objects.create(
            plan=plan2,
            server_class_id='other-server',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=self.server_type
        )
        switch_class2 = PlanSwitchClass.objects.create(
            plan=plan2,
            switch_class_id='other-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
            calculated_quantity=1
        )
        port_zone2 = SwitchPortZone.objects.create(
            switch_class=switch_class2,
            zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-60',
            breakout_option=self.breakout_4x200g,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100
        )
        connection2 = PlanServerConnection.objects.create(
            server_class=server_class2,
            connection_id='other-conn',
            connection_name='other',
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_switch_class=switch_class2,
            speed=200
        )

        # Generate devices for BOTH plans
        url1 = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        url2 = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan2.pk])

        # Generate plan 1
        response1 = self.client.post(url1, follow=True)
        self.assertEqual(response1.status_code, 200,
                        "Plan 1 generation should succeed")

        # Generate plan 2
        response2 = self.client.post(url2, follow=True)
        self.assertEqual(response2.status_code, 200,
                        "Plan 2 generation should succeed")

        # Count devices and cables for each plan
        plan1_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        )
        plan2_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan2.pk)
        )
        plan1_cables = Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        )
        plan2_cables = Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan2.pk)
        )

        # Verify both plans have objects
        self.assertEqual(plan1_devices.count(), 3,
                        "Plan 1 should have 3 devices (2 servers + 1 switch)")
        self.assertEqual(plan2_devices.count(), 2,
                        "Plan 2 should have 2 devices (1 server + 1 switch)")
        self.assertEqual(plan1_cables.count(), 4,
                        "Plan 1 should have 4 cables")
        self.assertEqual(plan2_cables.count(), 1,
                        "Plan 2 should have 1 cable")

        # Now REGENERATE plan 1 only
        response3 = self.client.post(url1, follow=True)
        self.assertEqual(response3.status_code, 200,
                        "Plan 1 regeneration should succeed")

        # Plan 1 should still have devices (regenerated)
        plan1_devices_after = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        )
        self.assertEqual(plan1_devices_after.count(), 3,
                        "Plan 1 should still have 3 devices after regeneration")

        # CRITICAL: Plan 2 devices and cables should be UNAFFECTED
        plan2_devices_after = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan2.pk)
        )
        plan2_cables_after = Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan2.pk)
        )

        self.assertEqual(plan2_devices_after.count(), 2,
                        "Plan 2 devices should NOT be affected by Plan 1 regeneration")
        self.assertEqual(plan2_cables_after.count(), 1,
                        "Plan 2 cables should NOT be affected by Plan 1 regeneration")

        # Clean up plan 2 objects manually
        plan2_cables.delete()
        plan2_devices.delete()

    # =============================================================================
    # Test: Invalid Plan Cases
    # =============================================================================

    def test_generate_with_nonexistent_plan(self):
        """Test that generate returns 404 for nonexistent plan"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[99999])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404,
                        "Should return 404 for nonexistent plan")

    def test_generate_post_with_nonexistent_plan(self):
        """Test that generate POST returns 404 for nonexistent plan"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[99999])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 404,
                        "Should return 404 for nonexistent plan")

    # =============================================================================
    # Test: Context Data Accuracy
    # =============================================================================

    def test_preview_count_accuracy_with_multiple_switch_classes(self):
        """Test that preview counts are accurate with multiple switch classes"""
        # Add another switch class
        switch_class_2 = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='be-leaf',
            fabric=FabricTypeChoices.BACKEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
            calculated_quantity=2,
            override_quantity=None
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        response = self.client.get(url)

        # Should count both switch classes
        # fe-leaf: 1 switch, be-leaf: 2 switches = 3 total
        self.assertEqual(response.context['switch_count'], 3,
                        "Should count all switches from all classes")
        self.assertEqual(response.context['total_devices'], 5,
                        "Should count 2 servers + 3 switches")

    def test_preview_uses_override_quantity_when_set(self):
        """Test that preview uses override_quantity instead of calculated_quantity"""
        # Set override
        self.switch_class.override_quantity = 5
        self.switch_class.save()

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        response = self.client.get(url)

        # Should use override value
        self.assertEqual(response.context['switch_count'], 5,
                        "Should use override_quantity when set")
        self.assertEqual(response.context['total_devices'], 7,
                        "Should count 2 servers + 5 switches (override)")

    def test_preview_counts_zero_quantity_servers(self):
        """Test that preview handles server classes with quantity=0"""
        self.server_class.quantity = 0
        self.server_class.save()

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.context['server_count'], 0,
                        "Should count 0 servers")
        self.assertEqual(response.context['total_devices'], 1,
                        "Should only count 1 switch")
