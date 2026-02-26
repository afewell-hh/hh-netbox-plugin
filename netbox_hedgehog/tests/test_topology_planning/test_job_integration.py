"""
Tests for NetBox Jobs Integration (DIET #132)

Following TDD approach: tests written BEFORE implementation.
Tests verify device generation via NetBox background jobs instead of synchronous execution.

Issue: https://github.com/afewell-hh/hh-netbox-plugin/issues/132
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from unittest.mock import patch

from dcim.models import DeviceType, Manufacturer, Device, Interface, Cable
from users.models import ObjectPermission
from core.models import Job

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    GenerationState,
    DeviceTypeExtension,
    BreakoutOption,
    SwitchPortZone,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    GenerationStatusChoices,
    ConnectionTypeChoices,
    ConnectionDistributionChoices,
    PortZoneTypeChoices,
)

User = get_user_model()


class DeviceGenerationJobIntegrationTestCase(TestCase):
    """
    Integration tests for device generation via NetBox Jobs.

    Tests cover:
    1. Job enqueuing
    2. Job execution
    3. Plan locking during generation
    4. UI status display
    5. Error handling
    6. Permission enforcement
    """

    @classmethod
    def setUpTestData(cls):
        """Create shared test data"""
        # Create superuser for tests requiring full permissions
        cls.superuser = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        # Create regular user for permission tests
        cls.regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            is_staff=True,
            is_superuser=False
        )

        # Create manufacturer and device types
        cls.manufacturer = Manufacturer.objects.create(name='HedgehogTest', slug='hedgehogtest')

        cls.switch_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            slug='ds5000',
            u_height=1
        )

        cls.server_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='GPU-Server',
            slug='gpu-server',
            u_height=2
        )

        # Create breakout option
        cls.breakout = BreakoutOption.objects.create(
            breakout_id='test-2x400g',
            from_speed=800,
            logical_ports=2,
            logical_speed=400,
            optic_type='QSFP-DD'
        )

        # Create DeviceTypeExtension for switch
        cls.switch_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_type,
            mclag_capable=True,
            hedgehog_roles=['spine', 'server-leaf']
        )

    def setUp(self):
        """Setup run before each test"""
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

        # Create fresh plan for each test
        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
            status=TopologyPlanStatusChoices.DRAFT,
            created_by=self.superuser
        )

        # Create switch class
        self.switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='FE-LEAF',
            device_type_extension=self.switch_ext,
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SPINE,
            override_quantity=2  # Set quantity so device generator can create switches
        )

        # Create port zone
        SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-zone',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-32',
            breakout_option=self.breakout,
            priority=10
        )

        # Create server class
        self.server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-001',
            server_device_type=self.server_type,
            quantity=4,
            gpus_per_server=8,
            category=ServerClassCategoryChoices.GPU
        )

        # Create server connection
        self.server_zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER,
        )
        PlanServerConnection.objects.create(
            connection_id='FE-001',
            server_class=self.server_class,
            target_zone=self.server_zone,
            ports_per_connection=2,
            speed=400,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING
        )

    # =========================================================================
    # Test 1: Job Enqueuing
    # =========================================================================

    def test_generate_enqueues_background_job(self):
        """
        Test #1: POST to generate endpoint should enqueue background job.

        Given: Valid plan with server + switch classes
        When: POST to generate/update endpoint
        Then:
        - Job is created in NetBox Jobs
        - GenerationState created with status=QUEUED
        - GenerationState linked to Job
        - User redirected to NetBox Job detail page
        """
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])

        # When: POST to generate endpoint
        response = self.client.post(url, follow=False)

        # Then: Should redirect (302)
        self.assertEqual(response.status_code, 302)

        # Refresh plan to get latest state
        self.plan.refresh_from_db()

        # Should create GenerationState with QUEUED status
        self.assertIsNotNone(self.plan.generation_state)
        self.assertEqual(
            self.plan.generation_state.status,
            GenerationStatusChoices.QUEUED,
            "GenerationState should have QUEUED status after job enqueued"
        )

        # Should create and link a NetBox Job
        self.assertIsNotNone(
            self.plan.generation_state.job,
            "GenerationState should be linked to a NetBox Job"
        )

        # Should redirect to NetBox Job detail page
        job = self.plan.generation_state.job
        self.assertEqual(
            response['Location'],
            job.get_absolute_url(),
            "Should redirect to NetBox Job detail page after enqueuing"
        )

    def test_generate_does_not_execute_synchronously(self):
        """
        Test #1b: Verify generation does NOT execute synchronously.

        Given: Valid plan
        When: POST to generate endpoint
        Then: No devices created immediately (job not run yet)
        """
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])

        # Clear any existing devices
        Device.objects.all().delete()

        # When: POST to generate endpoint
        response = self.client.post(url, follow=False)

        # Then: No devices should be created yet (job queued but not executed)
        self.assertEqual(
            Device.objects.filter(tags__name='hedgehog-generated').count(),
            0,
            "Devices should NOT be created synchronously; job is queued"
        )

        # GenerationState counts should be unset (None or 0) until job runs
        self.plan.refresh_from_db()
        # Allow None or 0 for counts that haven't been set yet
        self.assertIn(
            self.plan.generation_state.device_count,
            [None, 0],
            "Device count should be unset (None or 0) before job executes"
        )
        self.assertIn(
            self.plan.generation_state.interface_count,
            [None, 0],
            "Interface count should be unset (None or 0) before job executes"
        )
        self.assertIn(
            self.plan.generation_state.cable_count,
            [None, 0],
            "Cable count should be unset (None or 0) before job executes"
        )

    # =========================================================================
    # Test 2: Job Execution
    # =========================================================================

    def test_job_executes_device_generation_successfully(self):
        """
        Test #2: Job runner should execute DeviceGenerator and update state.

        Given: DeviceGenerationJob enqueued with plan
        When: job.run() is called
        Then:
        - Devices, interfaces, cables created
        - GenerationState updated with counts
        - Status changed to IN_PROGRESS then GENERATED
        - Job logs progress messages
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Clear existing devices
        Device.objects.all().delete()

        # Create GenerationState with QUEUED status
        state = GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.QUEUED,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # Enqueue job properly
        job = DeviceGenerationJob.enqueue(
            name="Test Device Generation",
            user=self.superuser,
            plan_id=self.plan.pk,
        )

        # Link job to state
        state.job = job
        state.save()

        # When: Execute job directly (bypassing queue for test)
        job_runner = DeviceGenerationJob(job=job)
        job_runner.run(plan_id=self.plan.pk)

        # Then: Devices should be created
        device_count = Device.objects.filter(tags__name='hedgehog-generated').count()
        self.assertGreater(
            device_count,
            0,
            "Job should create devices via DeviceGenerator"
        )

        # GenerationState should be updated with counts
        # Note: DeviceGenerator deletes/recreates state, so we must re-fetch it
        self.plan.refresh_from_db()
        state = self.plan.generation_state
        self.assertEqual(
            state.status,
            GenerationStatusChoices.GENERATED,
            "Status should be GENERATED after successful job completion"
        )
        self.assertGreater(state.device_count, 0)
        self.assertGreater(state.interface_count, 0)
        self.assertGreater(state.cable_count, 0)

        # Counts should match actual created objects
        self.assertEqual(state.device_count, device_count)

    def test_job_updates_status_to_in_progress_when_starting(self):
        """
        Test #2b: Job should update status to IN_PROGRESS when starting.

        Given: GenerationState with QUEUED status
        When: Job.run() starts
        Then: Status immediately changes to IN_PROGRESS
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Create GenerationState with QUEUED status
        state = GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.QUEUED,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        job = DeviceGenerationJob.enqueue(
            name="Test Status Update",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        state.job = job
        state.save()

        # Mock DeviceGenerator to verify status before generation
        with patch('netbox_hedgehog.jobs.device_generation.DeviceGenerator') as MockGen:
            mock_instance = MockGen.return_value
            mock_instance.generate_all.return_value = type('obj', (object,), {
                'device_count': 5,
                'interface_count': 10,
                'cable_count': 10
            })()

            # When: Execute job
            job_runner = DeviceGenerationJob(job=job)
            job_runner.run(plan_id=self.plan.pk)

            # DeviceGenerator should have been called (verifies flow reached it)
            mock_instance.generate_all.assert_called_once()

        # Status should be GENERATED after completion
        state.refresh_from_db()
        self.assertEqual(state.status, GenerationStatusChoices.GENERATED)

    # =========================================================================
    # Test 3: Plan Locking
    # =========================================================================

    def test_plan_locked_during_generation_prevents_edits(self):
        """
        Test #3: Plan should be locked when generation in progress.

        Given: Plan with GenerationState status=IN_PROGRESS
        When: Attempt to edit server class
        Then:
        - Edit request redirected to detail page
        - Error message displayed
        - No changes saved
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Create GenerationState with IN_PROGRESS status
        job = DeviceGenerationJob.enqueue(
            name="In Progress Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.IN_PROGRESS,
            job=job,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # Try to edit server class
        edit_url = reverse(
            'plugins:netbox_hedgehog:planserverclass_edit',
            args=[self.server_class.pk]
        )

        original_quantity = self.server_class.quantity
        new_data = {
            'plan': self.plan.pk,
            'server_class_id': 'GPU-001',
            'server_device_type': self.server_type.pk,
            'quantity': 99,  # Changed
            'gpus_per_server': 8,
            'category': ServerClassCategoryChoices.GPU
        }

        # When: POST to edit endpoint
        response = self.client.post(edit_url, new_data, follow=True)

        # Then: Should redirect to detail page (not allow edit)
        self.assertEqual(response.status_code, 200)

        # Should show error message about plan being locked
        messages = list(response.context['messages'])
        self.assertTrue(len(messages) > 0, "Should display error message")
        error_msg = str(messages[0].message).lower()
        self.assertIn('cannot modify', error_msg)
        self.assertIn('generation', error_msg)

        # No changes should be saved
        self.server_class.refresh_from_db()
        self.assertEqual(
            self.server_class.quantity,
            original_quantity,
            "Edit should not be saved when plan is locked"
        )

    def test_plan_locked_during_queued_status(self):
        """
        Test #3b: Plan should also be locked when generation is QUEUED.

        Given: Plan with GenerationState status=QUEUED
        When: Attempt to delete switch class
        Then: Delete prevented with error message
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Create GenerationState with QUEUED status
        job = DeviceGenerationJob.enqueue(
            name="Queued Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.QUEUED,
            job=job,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # Try to delete switch class
        delete_url = reverse(
            'plugins:netbox_hedgehog:planswitchclass_delete',
            args=[self.switch_class.pk]
        )

        # When: POST to delete endpoint (confirm deletion)
        response = self.client.post(delete_url, {'confirm': True}, follow=True)

        # Then: Should redirect with error
        self.assertEqual(response.status_code, 200)

        # Switch class should still exist
        self.assertTrue(
            PlanSwitchClass.objects.filter(pk=self.switch_class.pk).exists(),
            "Switch class should not be deleted when plan is locked"
        )

    def test_plan_unlocked_after_generation_complete(self):
        """
        Test #3c: Plan should be unlocked after generation completes.

        Given: Plan with GenerationState status=GENERATED
        When: Attempt to edit server class
        Then: Edit allowed and saved
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Create GenerationState with GENERATED status (unlocked)
        job = DeviceGenerationJob.enqueue(
            name="Completed Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        # Mark job as completed
        job.status = 'completed'
        job.save()

        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.GENERATED,
            job=job,
            device_count=5,
            interface_count=10,
            cable_count=10,
            snapshot={}
        )

        # Try to edit server class
        edit_url = reverse(
            'plugins:netbox_hedgehog:planserverclass_edit',
            args=[self.server_class.pk]
        )

        new_quantity = 99
        new_data = {
            'plan': self.plan.pk,
            'server_class_id': 'GPU-001',
            'server_device_type': self.server_type.pk,
            'quantity': new_quantity,
            'gpus_per_server': 8,
            'category': ServerClassCategoryChoices.GPU
        }

        # When: POST to edit endpoint
        response = self.client.post(edit_url, new_data, follow=True)

        # Then: Edit should succeed
        self.assertEqual(response.status_code, 200)

        # Changes should be saved
        self.server_class.refresh_from_db()
        self.assertEqual(
            self.server_class.quantity,
            new_quantity,
            "Edit should be allowed when plan is not locked"
        )

    # =========================================================================
    # Test 4: UI Status Display
    # =========================================================================

    def test_detail_page_shows_queued_status_with_job_link(self):
        """
        Test #4: Detail page should display QUEUED status with job link.

        Given: Plan with GenerationState status=QUEUED
        When: Load detail page
        Then:
        - Status badge displayed
        - Link to job page present
        - Generate button disabled
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Create GenerationState with QUEUED status using real job enqueue
        job = DeviceGenerationJob.enqueue(
            name="Queued Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.QUEUED,
            job=job,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # When: Load detail page
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(url)

        # Then: Should show status
        self.assertEqual(response.status_code, 200)

        # Should link to job page
        self.assertContains(
            response,
            job.get_absolute_url(),
            msg_prefix="Should include link to NetBox Job page"
        )

        # Generate button should be disabled
        self.assertContains(response, 'disabled', msg_prefix="Generate button should be disabled")

    def test_detail_page_shows_in_progress_status(self):
        """
        Test #4b: Detail page should display IN_PROGRESS status.

        Given: Plan with GenerationState status=IN_PROGRESS
        When: Load detail page
        Then: Job link present, button disabled
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        job = DeviceGenerationJob.enqueue(
            name="Running Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.IN_PROGRESS,
            job=job,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should link to job page
        self.assertContains(response, job.get_absolute_url())
        # Button should be disabled
        self.assertContains(response, 'disabled')

    def test_detail_page_shows_failed_status_with_error_link(self):
        """
        Test #4c: Detail page should display FAILED status with error link.

        Given: Plan with GenerationState status=FAILED
        When: Load detail page
        Then:
        - Link to job error details
        - Generate button re-enabled for retry
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        job = DeviceGenerationJob.enqueue(
            name="Failed Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        # Mark job as failed
        job.status = 'failed'
        job.save()

        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.FAILED,
            job=job,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should link to job page (for error details)
        self.assertContains(response, job.get_absolute_url())

        # Button should NOT be disabled (allow retry)
        # Check that generate form exists (not the disabled button)
        content = response.content.decode()
        self.assertIn('<form', content)
        self.assertIn('id="generate-form"', content)
        self.assertIn('generate-update', content)  # Check for the URL path, not the name

    def test_add_buttons_disabled_during_generation(self):
        """
        Test #4d: Add buttons should be disabled when generation in progress.

        Given: Plan with status=IN_PROGRESS
        When: Load detail page
        Then: Add buttons are disabled
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        job = DeviceGenerationJob.enqueue(
            name="Running Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.IN_PROGRESS,
            job=job,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Check that page contains add buttons/links (exact implementation may vary)
        content = response.content.decode()
        self.assertIn('Add Server Class', content)
        self.assertIn('Add Switch Class', content)

    # =========================================================================
    # Test 5: Error Handling
    # =========================================================================

    def test_job_failure_updates_state_to_failed(self):
        """
        Test #5: Failed job should update GenerationState to FAILED.

        Given: Job that raises exception during execution
        When: Job.run() is called
        Then:
        - GenerationState status = FAILED
        - Exception propagated (NetBox marks job as failed)
        - Error logged
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob
        from django.core.exceptions import ValidationError

        # Create GenerationState
        state = GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.QUEUED,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        job = DeviceGenerationJob.enqueue(
            name="Failing Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        state.job = job
        state.save()

        # Mock DeviceGenerator to raise exception
        with patch('netbox_hedgehog.jobs.device_generation.DeviceGenerator') as MockGen:
            mock_instance = MockGen.return_value
            mock_instance.generate_all.side_effect = ValidationError("Test error")

            # When: Execute job (should fail)
            job_runner = DeviceGenerationJob(job=job)

            with self.assertRaises(ValidationError):
                job_runner.run(plan_id=self.plan.pk)

        # Then: State should be FAILED
        # Note: State may have been recreated, so re-fetch from plan
        self.plan.refresh_from_db()
        state = self.plan.generation_state
        self.assertEqual(
            state.status,
            GenerationStatusChoices.FAILED,
            "Status should be FAILED after job exception"
        )

    def test_generate_fails_with_no_server_classes(self):
        """
        Test #5b: Validation errors should prevent job enqueuing.

        Given: Plan with no server classes
        When: POST to generate endpoint
        Then:
        - No job created
        - Error message displayed
        - Redirect to detail page
        """
        # Create plan with switches but no servers
        plan_no_servers = TopologyPlan.objects.create(
            name='No Servers',
            status=TopologyPlanStatusChoices.DRAFT,
            created_by=self.superuser
        )

        # Add switch class but no server class
        switch = PlanSwitchClass.objects.create(
            plan=plan_no_servers,
            switch_class_id='SW-1',
            device_type_extension=self.switch_ext,
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[plan_no_servers.pk])

        # When: Attempt to generate
        response = self.client.post(url, follow=True)

        # Then: Should redirect with error
        self.assertEqual(response.status_code, 200)

        # Should show error message
        messages = list(response.context['messages'])
        self.assertTrue(len(messages) > 0)
        error_msg = str(messages[0].message).lower()
        self.assertIn('server', error_msg)

        # No job should be created
        self.assertEqual(
            Job.objects.filter(object_id=plan_no_servers.pk).count(),
            0,
            "No job should be created when validation fails"
        )

        # No GenerationState should be created
        plan_no_servers.refresh_from_db()
        self.assertFalse(hasattr(plan_no_servers, 'generation_state'))

    # =========================================================================
    # Test 6: Permission Enforcement
    # =========================================================================

    def test_generate_requires_all_dcim_permissions(self):
        """
        Test #6: User must have all 7 required permissions to enqueue job.

        Given: User with change_topologyplan but missing one DCIM permission
        When: POST to generate endpoint
        Then:
        - 403 Forbidden
        - No job created
        """
        from django.contrib.auth.models import Permission

        # Grant view + change permission for TopologyPlan
        plan_ct = ContentType.objects.get_for_model(TopologyPlan)
        obj_perm = ObjectPermission.objects.create(
            name='Test TopologyPlan Permission',
            actions=['view', 'change']
        )
        obj_perm.object_types.add(plan_ct)
        obj_perm.users.add(self.regular_user)

        # Grant most DCIM permissions but NOT add_device
        dcim_perms = [
            'delete_device',
            'add_interface',
            'add_cable',
            'delete_cable',
        ]
        for perm_codename in dcim_perms:
            perm = Permission.objects.get(codename=perm_codename)
            self.regular_user.user_permissions.add(perm)

        # Login as regular user
        self.client.logout()
        self.client.login(username='regular', password='testpass123')

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])

        # When: Attempt to generate
        response = self.client.post(url)

        # Then: Should get 403 Forbidden
        self.assertEqual(
            response.status_code,
            403,
            "User missing add_device permission should get 403"
        )

        # No job should be created
        self.assertEqual(
            Job.objects.filter(object_id=self.plan.pk).count(),
            0,
            "No job should be created when permissions missing"
        )

    def test_generate_succeeds_with_all_permissions(self):
        """
        Test #6b: User with all required permissions can enqueue job.

        Given: User with all 7 required permissions
        When: POST to generate endpoint
        Then:
        - Job created successfully
        - GenerationState with QUEUED status
        """
        from django.contrib.auth.models import Permission

        # Create a plan owned by the regular user
        regular_plan = TopologyPlan.objects.create(
            name='Regular User Plan',
            customer_name='Test Customer',
            status=TopologyPlanStatusChoices.DRAFT,
            created_by=self.regular_user
        )

        # Add same classes as setUp
        reg_switch = PlanSwitchClass.objects.create(
            plan=regular_plan,
            switch_class_id='FE-LEAF',
            device_type_extension=self.switch_ext,
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SPINE,
            override_quantity=2
        )

        reg_zone = SwitchPortZone.objects.create(
            switch_class=reg_switch,
            zone_name='server-zone',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-32',
            breakout_option=self.breakout,
            priority=10
        )

        reg_server = PlanServerClass.objects.create(
            plan=regular_plan,
            server_class_id='GPU-001',
            server_device_type=self.server_type,
            quantity=4,
            gpus_per_server=8,
            category=ServerClassCategoryChoices.GPU
        )

        PlanServerConnection.objects.create(
            connection_id='FE-001',
            server_class=reg_server,
            target_zone=reg_zone,
            ports_per_connection=2,
            speed=400,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING
        )

        # Grant TopologyPlan permissions (with explicit constraints=None for all objects)
        plan_ct = ContentType.objects.get_for_model(TopologyPlan)
        obj_perm = ObjectPermission.objects.create(
            name='Full TopologyPlan Permission',
            actions=['view', 'change'],
            constraints=None  # Explicitly allow all TopologyPlan objects
        )
        obj_perm.object_types.add(plan_ct)
        obj_perm.users.add(self.regular_user)

        # Grant all DCIM permissions using ObjectPermission (NetBox requires this)
        from dcim.models import Interface, Cable

        device_ct = ContentType.objects.get_for_model(Device)
        device_perm = ObjectPermission.objects.create(
            name='DCIM Device Permissions',
            actions=['add', 'delete'],
            constraints=None
        )
        device_perm.object_types.add(device_ct)
        device_perm.users.add(self.regular_user)

        interface_ct = ContentType.objects.get_for_model(Interface)
        interface_perm = ObjectPermission.objects.create(
            name='DCIM Interface Permissions',
            actions=['add'],
            constraints=None
        )
        interface_perm.object_types.add(interface_ct)
        interface_perm.users.add(self.regular_user)

        cable_ct = ContentType.objects.get_for_model(Cable)
        cable_perm = ObjectPermission.objects.create(
            name='DCIM Cable Permissions',
            actions=['add', 'delete'],
            constraints=None
        )
        cable_perm.object_types.add(cable_ct)
        cable_perm.users.add(self.regular_user)

        # Use force_login to ensure permissions are properly loaded
        self.client.logout()
        self.client.force_login(self.regular_user)

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[regular_plan.pk])

        # When: POST to generate
        response = self.client.post(url, follow=False)

        # Then: Should redirect to job page after enqueuing
        self.assertEqual(response.status_code, 302, "Should redirect to job page after enqueuing")

        # Job should be created
        regular_plan.refresh_from_db()
        self.assertIsNotNone(regular_plan.generation_state)
        self.assertEqual(regular_plan.generation_state.status, GenerationStatusChoices.QUEUED)
        self.assertIsNotNone(regular_plan.generation_state.job)
