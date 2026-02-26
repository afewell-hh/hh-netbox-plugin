"""
Integration Tests for Unified Generate/Update Devices Action (DIET #127)

Tests the unified "Generate/Update Devices" workflow:
- Single action button replaces dual generate/recalculate buttons
- Auto-recalculate before generation
- Comprehensive sync status indicator (In Sync / Out of Sync / Not Generated)
- Permission enforcement via NetBox ObjectPermission (RBAC)
- Fail-fast on calculation errors
- Idempotent regeneration

Following UX-accurate TDD approach per CLAUDE.md:
- Tests verify actual request/response behavior
- Tests validate real UI rendering
- Tests enforce NetBox ObjectPermission RBAC (not just model permissions)
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from dcim.models import DeviceType, Manufacturer, Site, Device, Cable
from extras.models import Tag
from users.models import ObjectPermission

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


class UnifiedGenerateUpdateIntegrationTestCase(TestCase):
    """Integration tests for unified generate/update devices action"""

    @classmethod
    def setUpTestData(cls):
        """Create test fixtures"""
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

        # Create site for devices
        cls.site, _ = Site.objects.get_or_create(
            name='Test Site',
            defaults={'slug': 'test-site'}
        )

    def setUp(self):
        """Set up test user and clean environment before each test"""
        # Track plan IDs created in this test for scoped cleanup
        self.test_plan_ids = []
        self._cleanup_all_generated_objects()

        # Create superuser for main functionality tests
        # (ObjectPermission RBAC is tested separately in ObjectPermissionRBACTestCase)
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True  # Bypass ObjectPermission checks for functionality tests
        )

        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def tearDown(self):
        """Clean up after each test"""
        self._cleanup_all_generated_objects()
        # Note: TopologyPlan cleanup handled by Django test framework's transaction rollback

    def _cleanup_all_generated_objects(self):
        """
        Delete hedgehog-generated objects for plans created in this test.

        Scopes cleanup by test_plan_ids to avoid breaking other concurrent tests.
        Mirrors DeviceGenerator cleanup but scoped to this test's plans only.
        """
        # Only cleanup if we have plans to clean up
        if not hasattr(self, 'test_plan_ids') or not self.test_plan_ids:
            return

        tag_slug = 'hedgehog-generated'
        plan_id_strs = [str(pid) for pid in self.test_plan_ids]

        # Scope cleanup by BOTH tag AND plan ID (prevents global wipe)
        if Tag.objects.filter(slug=tag_slug).exists():
            # Delete cables for this test's plans only
            Cable.objects.filter(
                tags__slug=tag_slug,
                custom_field_data__hedgehog_plan_id__in=plan_id_strs
            ).delete()

            # Delete devices for this test's plans only
            Device.objects.filter(
                tags__slug=tag_slug,
                custom_field_data__hedgehog_plan_id__in=plan_id_strs
            ).delete()

        # Catch untagged objects for this test's plans (fallback)
        Device.objects.filter(
            custom_field_data__hedgehog_plan_id__in=plan_id_strs
        ).delete()

    def _create_valid_plan_with_classes(self):
        """
        Create a valid topology plan with server/switch classes and connections.

        Tracks plan ID for scoped cleanup.
        Returns plan ready for generation.
        """
        plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
            status=TopologyPlanStatusChoices.DRAFT
        )
        # Track for cleanup
        self.test_plan_ids.append(plan.pk)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-server',
            category=ServerClassCategoryChoices.GPU,
            quantity=2,
            gpus_per_server=8,
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
            calculated_quantity=None,  # Will be calculated
            override_quantity=None
        )

        # Create port zone
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-ports',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=self.breakout_4x200g,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100
        )

        # Create connection
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-downlinks',
            zone_type='server',
        )
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='FE-001',
            target_zone=zone,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data'
        )

        return plan

    def _create_invalid_plan(self):
        """
        Create a plan that will cause calculation errors.

        Missing required configuration (no port zones) triggers calc errors.
        Tracks plan ID for scoped cleanup.
        """
        plan = TopologyPlan.objects.create(
            name='Invalid Plan',
            status=TopologyPlanStatusChoices.DRAFT
        )
        # Track for cleanup
        self.test_plan_ids.append(plan.pk)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-server',
            category=ServerClassCategoryChoices.GPU,
            quantity=10,
            gpus_per_server=8,
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
            calculated_quantity=None,
            override_quantity=None
        )

        # Create connection but NO port zone (causes calc error)
        invalid_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-downlinks',
            zone_type='server',
        )
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='FE-001',
            target_zone=invalid_zone,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data'
        )

        return plan

    def _generate_devices(self, plan):
        """
        Helper to generate devices for a plan via unified endpoint.

        Returns response from POST request.
        """
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )
        return self.client.post(url, follow=True)

    def _create_plan_user(self, username, actions):
        """
        Create a non-superuser with TopologyPlan model + ObjectPermission.

        Args:
            username: Username for the new user
            actions: List of actions ('view', 'change') to grant
        """
        user = User.objects.create_user(
            username=username,
            password='testpass123',
            is_staff=True
        )

        perm_map = {
            'view': 'view_topologyplan',
            'change': 'change_topologyplan',
        }

        for action in actions:
            perm = Permission.objects.get(
                content_type__app_label='netbox_hedgehog',
                codename=perm_map[action]
            )
            user.user_permissions.add(perm)

        obj_perm = ObjectPermission.objects.create(
            name=f'{username} TopologyPlan',
            actions=actions
        )
        obj_perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        obj_perm.users.add(user)

        return user

    def _create_dcim_object_permission(self, user, action, model, name_suffix):
        """
        Create a DCIM ObjectPermission for a single action/model pair.

        Args:
            user: User to grant permission to
            action: Permission action ('add' or 'delete')
            model: Model class for permission scope
            name_suffix: Label to differentiate permission records
        """
        obj_perm = ObjectPermission.objects.create(
            name=f'{user.username} {name_suffix}',
            actions=[action]
        )
        obj_perm.object_types.add(ContentType.objects.get_for_model(model))
        obj_perm.users.add(user)
        return obj_perm

    # ========================================================================
    # Test: Initial Generation (Never Generated)
    # ========================================================================

    def test_initial_generation_creates_devices(self):
        """
        Test #1: First-time generation creates all devices and GenerationState.

        Given: Plan with server/switch classes, no prior generation
        When: POST to unified generate/update endpoint
        Then: Devices created, GenerationState created, plan in sync
        """
        # Given: Plan with server/switch classes, no prior generation
        plan = self._create_valid_plan_with_classes()
        self.assertIsNone(plan.last_generated_at)

        # When: POST to unified generate/update endpoint
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )
        response = self.client.post(url)

        # Then: Redirects to detail page
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/topology-plans/{plan.pk}/', response['Location'])

        # Then: Devices created
        devices = Device.objects.filter(
            tags__slug='hedgehog-generated',
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        )
        self.assertGreater(devices.count(), 0, "Should create at least one device")

        # Then: GenerationState created
        self.assertTrue(
            GenerationState.objects.filter(plan=plan).exists(),
            "GenerationState should be created"
        )

        # Then: Plan is in sync
        plan.refresh_from_db()
        self.assertIsNotNone(plan.last_generated_at, "Should have generation timestamp")
        self.assertFalse(plan.needs_regeneration, "Plan should be in sync after generation")

        # Then: Success message shown
        messages = list(response.wsgi_request._messages)
        self.assertTrue(
            any('Devices updated successfully' in str(m) for m in messages),
            "Should show success message"
        )

    # ========================================================================
    # Test: Update After Plan Change
    # ========================================================================

    def test_update_after_plan_change_regenerates_devices(self):
        """
        Test #2: Regeneration after plan modification updates devices.

        Given: Plan with generated devices, then modify server quantity
        When: POST to generate/update
        Then: Old devices deleted, new devices created, GenerationState updated
        """
        # Given: Plan with generated devices
        plan = self._create_valid_plan_with_classes()
        self._generate_devices(plan)

        original_device_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()

        # Given: Modify plan (change server quantity)
        server_class = plan.server_classes.first()
        original_quantity = server_class.quantity
        server_class.quantity = original_quantity + 10
        server_class.save()

        # Then: Plan shows out of sync
        plan.refresh_from_db()
        self.assertTrue(
            plan.needs_regeneration,
            "Plan should be out of sync after quantity change"
        )

        # When: Regenerate devices
        response = self._generate_devices(plan)

        # Then: Device count updated (more servers)
        new_device_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()
        self.assertGreater(
            new_device_count,
            original_device_count,
            "Device count should increase with more servers"
        )

        # Then: Plan is in sync again
        plan.refresh_from_db()
        self.assertFalse(
            plan.needs_regeneration,
            "Plan should be in sync after regeneration"
        )

    # ========================================================================
    # Test: Idempotent Regeneration
    # ========================================================================

    def test_idempotent_regeneration(self):
        """
        Test #3: Regenerating without plan changes is safe and idempotent.

        Given: Plan with generated devices, no modifications
        When: Regenerate again
        Then: Device count unchanged, plan still in sync
        """
        # Given: Plan with generated devices, no modifications
        plan = self._create_valid_plan_with_classes()
        self._generate_devices(plan)

        device_count_before = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()

        # When: Regenerate again without plan changes
        self._generate_devices(plan)

        # Then: Device count unchanged
        device_count_after = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()
        self.assertEqual(
            device_count_before,
            device_count_after,
            "Device count should remain the same on idempotent regeneration"
        )

        # Then: Plan still in sync
        plan.refresh_from_db()
        self.assertFalse(
            plan.needs_regeneration,
            "Plan should still be in sync after idempotent regeneration"
        )

    # ========================================================================
    # Test: Auto-Recalculate Before Generation
    # ========================================================================

    def test_auto_recalculate_before_generation(self):
        """
        Test #4: Generation automatically recalculates switch quantities.

        Given: Plan with calculated_quantity=None
        When: Generate devices
        Then: calculated_quantity populated, devices created based on calculations
        """
        # Given: Plan with calculated_quantity=None
        plan = self._create_valid_plan_with_classes()
        switch_class = plan.switch_classes.first()
        switch_class.calculated_quantity = None
        switch_class.save()

        # When: Generate devices (should auto-recalculate)
        self._generate_devices(plan)

        # Then: calculated_quantity populated
        switch_class.refresh_from_db()
        self.assertIsNotNone(
            switch_class.calculated_quantity,
            "Auto-recalculate should populate calculated_quantity"
        )
        self.assertGreater(
            switch_class.calculated_quantity,
            0,
            "Calculated quantity should be positive"
        )

        # Then: Devices created based on calculated quantities
        switch_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__hedgehog_class=switch_class.switch_class_id
        )
        self.assertEqual(
            switch_devices.count(),
            switch_class.calculated_quantity,
            "Device count should match calculated quantity"
        )

    # ========================================================================
    # Test: Abort on Calculation Errors
    # ========================================================================

    def test_abort_on_calculation_errors(self):
        """
        Test #5: Generation aborts if calculation errors occur (fail-fast).

        Given: Plan with invalid configuration (causes calc error)
        When: Attempt to generate devices
        Then: Error message shown, no devices created, no GenerationState
        """
        # Given: Plan with invalid configuration (causes calc error)
        plan = self._create_invalid_plan()

        # When: Attempt to generate devices
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )
        response = self.client.post(url, follow=True)

        # Then: Redirects to detail page (no generation)
        self.assertEqual(response.status_code, 200)

        # Then: Error message shown
        messages = list(response.wsgi_request._messages)
        self.assertTrue(
            any('Cannot generate devices due to calculation errors' in str(m)
                for m in messages),
            "Should show calculation error message"
        )

        # Then: No devices created
        devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        )
        self.assertEqual(
            devices.count(),
            0,
            "No devices should be created when calculation fails"
        )

        # Then: No GenerationState created
        self.assertFalse(
            GenerationState.objects.filter(plan=plan).exists(),
            "GenerationState should not be created on calc error"
        )

    # ========================================================================
    # Test: Sync Indicator - Not Generated
    # ========================================================================

    def test_sync_indicator_not_generated(self):
        """
        Test #6: Sync indicator shows 'Not Generated' for new plan.

        Given: New plan, never generated
        When: Load detail page
        Then: Shows "Not Generated" badge
        """
        # Given: New plan, never generated
        plan = self._create_valid_plan_with_classes()

        # When: Load detail page
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk}
        )
        response = self.client.get(url)

        # Then: Page loads successfully
        self.assertEqual(response.status_code, 200)

        # Then: Shows "Not Generated" badge
        self.assertContains(response, 'Not Generated')
        self.assertContains(response, 'mdi-help-circle')

    # ========================================================================
    # Test: Sync Indicator - In Sync
    # ========================================================================

    def test_sync_indicator_in_sync(self):
        """
        Test #7: Sync indicator shows 'In Sync' after generation.

        Given: Plan with generated devices, no changes
        When: Load detail page
        Then: Shows "In Sync" badge
        """
        # Given: Plan with generated devices, no changes
        plan = self._create_valid_plan_with_classes()
        self._generate_devices(plan)

        # When: Load detail page
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk}
        )
        response = self.client.get(url)

        # Then: Shows "In Sync" badge
        self.assertContains(response, 'In Sync')
        self.assertContains(response, 'mdi-check-circle')
        self.assertContains(response, 'badge-success')

    # ========================================================================
    # Test: Sync Indicator - Out of Sync
    # ========================================================================

    def test_sync_indicator_out_of_sync(self):
        """
        Test #8: Sync indicator shows 'Out of Sync' after plan modification.

        Given: Plan with generated devices, then modify quantity
        When: Load detail page
        Then: Shows "Out of Sync" badge
        """
        # Given: Plan with generated devices
        plan = self._create_valid_plan_with_classes()
        self._generate_devices(plan)

        # Given: Modify plan
        server_class = plan.server_classes.first()
        server_class.quantity += 5
        server_class.save()

        # When: Load detail page
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk}
        )
        response = self.client.get(url)

        # Then: Shows "Out of Sync" badge
        self.assertContains(response, 'Out of Sync')
        self.assertContains(response, 'mdi-alert')
        self.assertContains(response, 'badge-warning')
        self.assertContains(response, 'Plan has changed since generation')

    # ========================================================================
    # Test: Plan Metadata Change Does NOT Trigger Out of Sync
    # ========================================================================

    def test_plan_name_change_does_not_trigger_out_of_sync(self):
        """
        Test #9: Changing plan name/customer should NOT mark plan out of sync.

        Given: Plan with generated devices
        When: Change plan metadata (not generation-relevant)
        Then: Plan STILL in sync (metadata excluded from snapshot)
        """
        # Given: Plan with generated devices
        plan = self._create_valid_plan_with_classes()
        self._generate_devices(plan)

        # When: Change plan metadata (not generation-relevant)
        plan.name = "New Plan Name"
        plan.customer_name = "New Customer"
        plan.description = "New description"
        plan.save()

        # Then: Plan STILL in sync (metadata excluded from snapshot)
        plan.refresh_from_db()
        self.assertFalse(
            plan.needs_regeneration,
            "Metadata changes should NOT trigger out-of-sync"
        )

    # ========================================================================
    # Test: Connection Change Triggers Out of Sync
    # ========================================================================

    def test_connection_change_triggers_out_of_sync(self):
        """
        Test #10: Changing connection parameters should mark plan out of sync.

        Given: Plan with generated devices
        When: Change connection type (generation-relevant)
        Then: Plan is out of sync
        """
        # Given: Plan with generated devices
        plan = self._create_valid_plan_with_classes()
        self._generate_devices(plan)

        # When: Change connection type (generation-relevant)
        connection = plan.server_classes.first().connections.first()
        connection.hedgehog_conn_type = ConnectionTypeChoices.MCLAG
        connection.save()

        # Then: Plan is out of sync
        plan.refresh_from_db()
        self.assertTrue(
            plan.needs_regeneration,
            "Connection changes should trigger out-of-sync"
        )

    # ========================================================================
    # Test: Port Zone Change Triggers Out of Sync
    # ========================================================================

    def test_port_zone_change_triggers_out_of_sync(self):
        """
        Test #11: Changing port zone parameters should mark plan out of sync.

        Given: Plan with generated devices
        When: Change port zone configuration (generation-relevant)
        Then: Plan is out of sync
        """
        # Given: Plan with generated devices
        plan = self._create_valid_plan_with_classes()
        self._generate_devices(plan)

        # When: Change port zone spec (generation-relevant)
        switch_class = plan.switch_classes.first()
        port_zone = SwitchPortZone.objects.filter(switch_class=switch_class).first()
        port_zone.port_spec = '1-32'  # Change from '1-48'
        port_zone.save()

        # Then: Plan is out of sync
        plan.refresh_from_db()
        self.assertTrue(
            plan.needs_regeneration,
            "Port zone changes should trigger out-of-sync"
        )

    # ========================================================================
    # Test: Permission Denied - Parameterized
    # ========================================================================

    def test_permission_denied_for_each_required_perm(self):
        """
        Test #12: Each required permission must be present for generation.

        Tests each of the 6 required DCIM permissions individually.
        Missing any one permission should result in 403.
        """
        plan = self._create_valid_plan_with_classes()
        user = self._create_plan_user('perm_user', ['view', 'change'])
        client = Client()
        client.login(username='perm_user', password='testpass123')

        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )

        # List of required DCIM permissions (not including change_topologyplan)
        required_dcim_perms = [
            'add_device',
            'delete_device',
            'add_interface',
            'add_cable',
            'delete_cable',
        ]

        from dcim.models import Interface
        perm_map = {
            'add_device': ('add', Device),
            'delete_device': ('delete', Device),
            'add_interface': ('add', Interface),
            'add_cable': ('add', Cable),
            'delete_cable': ('delete', Cable),
        }

        dcim_obj_perms = {}
        for perm_codename, (action, model) in perm_map.items():
            dcim_obj_perms[perm_codename] = self._create_dcim_object_permission(
                user,
                action,
                model,
                perm_codename
            )

        for perm_codename in required_dcim_perms:
            with self.subTest(missing_permission=perm_codename):
                # Remove one permission
                dcim_obj_perms[perm_codename].delete()

                # Attempt to generate
                response = client.post(url)

                # Should be denied
                self.assertEqual(
                    response.status_code,
                    403,
                    f"Should return 403 without {perm_codename} permission"
                )

                # Restore permission for next iteration
                action, model = perm_map[perm_codename]
                dcim_obj_perms[perm_codename] = self._create_dcim_object_permission(
                    user,
                    action,
                    model,
                    f"{perm_codename}-restore"
                )

    # ========================================================================
    # Test: Button Disabled Without Permissions
    # ========================================================================

    def test_button_disabled_without_permissions(self):
        """
        Test #13: Generate button disabled for users without permissions.

        Given: User without dcim permissions
        When: Load detail page
        Then: Button is disabled with tooltip
        """
        plan = self._create_valid_plan_with_classes()
        user = self._create_plan_user('no_dcim', ['view', 'change'])
        client = Client()
        client.login(username='no_dcim', password='testpass123')

        # When: Load detail page
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk}
        )
        response = client.get(url)

        # Then: Button is disabled
        self.assertContains(response, 'disabled')
        self.assertContains(
            response,
            'Contact administrator for device management permissions'
        )

    # ========================================================================
    # Test: Error on Missing Server Classes
    # ========================================================================

    def test_error_no_server_classes(self):
        """
        Test #14: Error shown when plan has no server classes.

        Given: Plan with only switch classes (no servers)
        When: Attempt to generate
        Then: Error message shown, no devices created
        """
        # Given: Plan with only switch classes (no servers)
        plan = TopologyPlan.objects.create(
            name='No Servers Plan',
            status=TopologyPlanStatusChoices.DRAFT
        )
        self.test_plan_ids.append(plan.pk)

        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
            calculated_quantity=2
        )

        # When: Attempt to generate
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )
        response = self.client.post(url, follow=True)

        # Then: Error message shown
        messages = list(response.wsgi_request._messages)
        self.assertTrue(
            any('Cannot generate devices: plan requires at least one server class' in str(m)
                for m in messages),
            "Should show error about missing server classes"
        )

        # Then: No devices created
        devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        )
        self.assertEqual(devices.count(), 0)

    # ========================================================================
    # Test: Error on Missing Switch Classes
    # ========================================================================

    def test_error_no_switch_classes(self):
        """
        Test #15: Error shown when plan has no switch classes.

        Given: Plan with only server classes (no switches)
        When: Attempt to generate
        Then: Error message shown, no devices created
        """
        # Given: Plan with only server classes (no switches)
        plan = TopologyPlan.objects.create(
            name='No Switches Plan',
            status=TopologyPlanStatusChoices.DRAFT
        )
        self.test_plan_ids.append(plan.pk)

        PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-server',
            category=ServerClassCategoryChoices.GPU,
            quantity=10,
            gpus_per_server=8,
            server_device_type=self.server_type
        )

        # When: Attempt to generate
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )
        response = self.client.post(url, follow=True)

        # Then: Error message shown
        messages = list(response.wsgi_request._messages)
        self.assertTrue(
            any('Cannot generate devices: plan requires at least one' in str(m)
                for m in messages),
            "Should show error about missing switch classes"
        )

        # Then: No devices created
        devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        )
        self.assertEqual(devices.count(), 0)

    # ========================================================================
    # Test: Button Text Changes Based on State
    # ========================================================================

    def test_button_text_changes_based_on_state(self):
        """
        Test #16: Button text changes based on generation state.

        State transitions:
        - Never generated: "Generate Devices"
        - Generated + out of sync: "Update Devices"
        - Generated + in sync: "Regenerate Devices"
        """
        # Given: Never generated plan
        plan = self._create_valid_plan_with_classes()
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', kwargs={'pk': plan.pk})

        # Then: Shows "Generate Devices"
        response = self.client.get(url)
        self.assertContains(response, 'Generate Devices')

        # When: Generate devices
        self._generate_devices(plan)

        # Then: Shows "Regenerate Devices" (in sync)
        response = self.client.get(url)
        self.assertContains(response, 'Regenerate Devices')

        # When: Modify plan (out of sync)
        server_class = plan.server_classes.first()
        server_class.quantity += 5
        server_class.save()

        # Then: Shows "Update Devices"
        response = self.client.get(url)
        self.assertContains(response, 'Update Devices')


# ============================================================================
# NetBox ObjectPermission RBAC Tests
# ============================================================================


class ObjectPermissionRBACTestCase(TestCase):
    """
    Tests for NetBox ObjectPermission-based RBAC enforcement.

    Per AGENTS.md requirement: Enforce RBAC with NetBox ObjectPermission.
    These tests validate object-level permission grants/denials.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test fixtures"""
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

        cls.site, _ = Site.objects.get_or_create(
            name='Test Site',
            defaults={'slug': 'test-site'}
        )

    def setUp(self):
        """Set up clean environment before each test"""
        # Track plan IDs created in this test for scoped cleanup
        self.test_plan_ids = []
        self._cleanup_all_generated_objects()

    def tearDown(self):
        """Clean up after each test"""
        self._cleanup_all_generated_objects()
        # Note: TopologyPlan cleanup handled by Django test framework's transaction rollback

    def _cleanup_all_generated_objects(self):
        """
        Delete hedgehog-generated objects for plans created in this test.

        Scopes cleanup by test_plan_ids to avoid breaking other concurrent tests.
        Mirrors DeviceGenerator cleanup but scoped to this test's plans only.
        """
        # Only cleanup if we have plans to clean up
        if not hasattr(self, 'test_plan_ids') or not self.test_plan_ids:
            return

        tag_slug = 'hedgehog-generated'
        plan_id_strs = [str(pid) for pid in self.test_plan_ids]

        # Scope cleanup by BOTH tag AND plan ID (prevents global wipe)
        if Tag.objects.filter(slug=tag_slug).exists():
            # Delete cables for this test's plans only
            Cable.objects.filter(
                tags__slug=tag_slug,
                custom_field_data__hedgehog_plan_id__in=plan_id_strs
            ).delete()

            # Delete devices for this test's plans only
            Device.objects.filter(
                tags__slug=tag_slug,
                custom_field_data__hedgehog_plan_id__in=plan_id_strs
            ).delete()

        # Catch untagged objects for this test's plans (fallback)
        Device.objects.filter(
            custom_field_data__hedgehog_plan_id__in=plan_id_strs
        ).delete()

    def _grant_base_topologyplan_model_perms(self, user, actions):
        """
        Grant base TopologyPlan model permissions to user.

        In NetBox, ObjectPermission is additive to model permissions.
        Users need base model perms (view/change) before ObjectPermission applies.

        Args:
            user: User to grant permissions to
            actions: List of actions ('view', 'change', 'add', 'delete')
        """
        perm_map = {
            'view': 'view_topologyplan',
            'change': 'change_topologyplan',
            'add': 'add_topologyplan',
            'delete': 'delete_topologyplan',
        }

        for action in actions:
            codename = perm_map[action]
            perm = Permission.objects.get(
                content_type__app_label='netbox_hedgehog',
                codename=codename
            )
            user.user_permissions.add(perm)

    def _create_dcim_object_permission(self, user, action, model, name_suffix):
        """
        Create a DCIM ObjectPermission for a single action/model pair.

        Args:
            user: User to grant permission to
            action: Permission action ('add' or 'delete')
            model: Model class for permission scope
            name_suffix: Label to differentiate permission records
        """
        obj_perm = ObjectPermission.objects.create(
            name=f'{user.username} {name_suffix}',
            actions=[action]
        )
        obj_perm.object_types.add(ContentType.objects.get_for_model(model))
        obj_perm.users.add(user)
        return obj_perm

    def _create_valid_plan(self):
        """
        Create a valid topology plan for testing.

        Tracks plan ID for scoped cleanup.
        """
        plan = TopologyPlan.objects.create(
            name='RBAC Test Plan',
            customer_name='Test Customer',
            status=TopologyPlanStatusChoices.DRAFT
        )
        # Track for cleanup
        self.test_plan_ids.append(plan.pk)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-server',
            category=ServerClassCategoryChoices.GPU,
            quantity=2,
            gpus_per_server=8,
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
            calculated_quantity=None,
            override_quantity=None
        )

        view_only_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-ports',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=self.breakout_4x200g,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100
        )

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='FE-001',
            target_zone=view_only_zone,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data'
        )

        return plan

    def test_view_only_user_can_see_indicator_but_not_generate(self):
        """
        Test #17: User with view-only ObjectPermission can see sync indicator
        but cannot generate devices.

        Given: User with base model view permission + ObjectPermission view
        When: Load detail page
        Then: Sync indicator visible, generate button disabled
        When: Attempt POST
        Then: 403 permission denied

        Note: In NetBox, ObjectPermission is additive to model permissions.
        User needs base view_topologyplan model perm before ObjectPermission applies.
        """
        # Given: View-only user
        view_user = User.objects.create_user(
            username='view_only',
            password='testpass123',
            is_staff=True
        )

        # Grant base model view permission (required before ObjectPermission)
        self._grant_base_topologyplan_model_perms(view_user, ['view'])

        # Grant view-only ObjectPermission for TopologyPlan
        obj_perm = ObjectPermission.objects.create(
            name='View TopologyPlans',
            actions=['view']
        )
        obj_perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        obj_perm.users.add(view_user)

        client = Client()
        client.login(username='view_only', password='testpass123')

        plan = self._create_valid_plan()
        detail_url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk}
        )

        # When: Load detail page
        response = client.get(detail_url)

        # Then: Page loads (view permission granted)
        self.assertEqual(response.status_code, 200)

        # Then: Sync indicator visible
        self.assertContains(response, 'Device Generation')
        self.assertContains(response, 'Not Generated')

        # Then: Generate button disabled (no change permission)
        self.assertContains(response, 'disabled')

        # When: Attempt POST (despite disabled button)
        generate_url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )
        response = client.post(generate_url)

        # Then: 403 permission denied
        self.assertEqual(
            response.status_code,
            403,
            "View-only user should not be able to generate devices"
        )

    def test_generate_user_with_object_permission_can_generate(self):
        """
        Test #18: User with ObjectPermission granting change + DCIM perms
        can successfully generate devices.

        Given: User with base model permissions (view + change)
               + ObjectPermission (view + change)
               + DCIM model permissions
        When: POST to generate/update
        Then: Devices created successfully

        Note: In NetBox, ObjectPermission is additive to model permissions.
        User needs base view/change_topologyplan model perms before ObjectPermission applies.
        """
        # Given: Generate-capable user
        gen_user = User.objects.create_user(
            username='generator',
            password='testpass123',
            is_staff=True
        )

        plan = self._create_valid_plan()

        # Grant base model permissions (required before ObjectPermission)
        self._grant_base_topologyplan_model_perms(gen_user, ['view', 'change'])

        # Grant change ObjectPermission for TopologyPlan
        obj_perm = ObjectPermission.objects.create(
            name='Change TopologyPlans',
            actions=['view', 'change']
        )
        obj_perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        obj_perm.users.add(gen_user)

        # Grant required DCIM model permissions
        from dcim.models import Interface
        dcim_perm_map = {
            'dcim.add_device': ('add', Device),
            'dcim.delete_device': ('delete', Device),
            'dcim.add_interface': ('add', Interface),
            'dcim.add_cable': ('add', Cable),
            'dcim.delete_cable': ('delete', Cable),
        }
        for perm_name, (action, model) in dcim_perm_map.items():
            self._create_dcim_object_permission(gen_user, action, model, perm_name)

        # Clear permission caches after modifying permissions
        for cache_attr in ('_perm_cache', '_user_perm_cache', '_group_perm_cache', '_object_perm_cache'):
            if hasattr(gen_user, cache_attr):
                delattr(gen_user, cache_attr)

        gen_user = User.objects.get(pk=gen_user.pk)

        # Sanity check: ensure permissions are recognized before request
        self.assertTrue(
            gen_user.has_perm('netbox_hedgehog.change_topologyplan', plan),
            "Expected change_topologyplan permission for plan"
        )
        for perm_name in dcim_perm_map:
            self.assertTrue(
                gen_user.has_perm(perm_name),
                f"Expected {perm_name} permission"
            )

        # Use force_login to bypass authentication backend (ensures all permissions are loaded)
        client = Client()
        client.force_login(gen_user)

        generate_url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )

        # When: POST to generate/update
        response = client.post(generate_url)

        # Then: Redirects to detail (success)
        self.assertEqual(response.status_code, 302)

        # Then: Devices created
        devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        )
        self.assertGreater(
            devices.count(),
            0,
            "User with ObjectPermission should be able to generate devices"
        )

    def test_object_permission_without_dcim_perms_fails(self):
        """
        Test #19: User with ObjectPermission for TopologyPlan but missing
        DCIM permissions cannot generate.

        Given: User with base model permissions (view + change)
               + ObjectPermission (view + change)
               BUT missing DCIM model permissions
        When: Attempt to generate
        Then: 403 permission denied

        Note: This validates that TopologyPlan permissions alone are insufficient;
        DCIM device/cable permissions are also required.
        """
        # Given: User with TopologyPlan permissions only
        partial_user = User.objects.create_user(
            username='partial',
            password='testpass123',
            is_staff=True
        )

        # Grant base model permissions (required before ObjectPermission)
        self._grant_base_topologyplan_model_perms(partial_user, ['view', 'change'])

        # Grant change ObjectPermission for TopologyPlan
        obj_perm = ObjectPermission.objects.create(
            name='Change TopologyPlans Only',
            actions=['view', 'change']
        )
        obj_perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        obj_perm.users.add(partial_user)

        # Do NOT grant DCIM permissions (this is what we're testing)

        client = Client()
        client.login(username='partial', password='testpass123')

        plan = self._create_valid_plan()
        generate_url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )

        # When: Attempt to generate
        response = client.post(generate_url)

        # Then: 403 permission denied (missing DCIM perms)
        self.assertEqual(
            response.status_code,
            403,
            "Should deny without DCIM permissions even with TopologyPlan ObjectPermission"
        )
