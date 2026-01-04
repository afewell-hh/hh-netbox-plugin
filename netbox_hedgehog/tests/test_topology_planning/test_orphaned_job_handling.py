"""
Integration Tests for Orphaned Job Handling (Issue #137)

Tests the orphaned job bug fix:
- When a user deletes a background job from NetBox Jobs page
- GenerationState becomes "orphaned" (status=QUEUED/IN_PROGRESS but job=None)
- System should auto-detect and recover from this state

Following UX-accurate TDD approach per AGENTS.md:
- Tests verify actual request/response behavior
- Tests validate real UI rendering
- Tests enforce defensive checks in views

Issue: https://github.com/afewell-hh/hh-netbox-plugin/issues/137
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from dcim.models import DeviceType, Manufacturer
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


class OrphanedJobHandlingTestCase(TestCase):
    """
    Integration tests for orphaned job detection and recovery.

    Orphaned job scenario:
    1. User starts device generation -> Job created, GenerationState.status=QUEUED
    2. User deletes job from NetBox Jobs page -> GenerationState.job becomes None
    3. Plan stuck: status=QUEUED/IN_PROGRESS but job=None
    4. System should detect and auto-recover
    """

    @classmethod
    def setUpTestData(cls):
        """Create shared test data"""
        # Create superuser for tests
        cls.superuser = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        # Create manufacturer and device types
        cls.manufacturer = Manufacturer.objects.create(name='TestCo', slug='testco')

        cls.switch_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='TestSwitch',
            slug='testswitch',
            u_height=1
        )

        cls.server_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='TestServer',
            slug='testserver',
            u_height=2
        )

        # Create breakout option
        cls.breakout = BreakoutOption.objects.create(
            breakout_id='test-4x200g',
            from_speed=800,
            logical_ports=4,
            logical_speed=200,
            optic_type='QSFP-DD'
        )

        # Create DeviceTypeExtension for switch
        cls.switch_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_type,
            mclag_capable=False,
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

        # Create switch class with fixed quantity (for simpler testing)
        self.switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='TEST-SWITCH',
            device_type_extension=self.switch_ext,
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            override_quantity=2
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
            server_class_id='TEST-SERVER',
            server_device_type=self.server_type,
            quantity=4,
            gpus_per_server=8,
            category=ServerClassCategoryChoices.GPU
        )

        # Create connection
        PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='TEST-CONN',
            target_switch_class=self.switch_class,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data'
        )

    # =========================================================================
    # Test 1: Detail View Shows Orphaned Job Warning
    # =========================================================================

    def test_detail_view_orphaned_job_shows_warning_badge(self):
        """
        Detail view should show "Job Deleted" warning when job is orphaned.

        Given: Plan with orphaned GenerationState (status=IN_PROGRESS, job=None)
        When: GET detail view
        Then:
        - Response contains "Job Deleted" badge
        - Response contains helpful message explaining the situation
        - Generate button is NOT disabled (enabled and clickable)
        """
        # Given: Create orphaned GenerationState
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.IN_PROGRESS,
            job=None,  # Orphaned!
            device_count=10,
            interface_count=50,
            cable_count=25,
            snapshot={}
        )

        # When: GET detail page
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(url)

        # Then: Should render successfully
        self.assertEqual(response.status_code, 200)

        # Should show "Job Deleted" badge in Device Generation status
        self.assertContains(response, 'Job Deleted', html=False)

        # Should show helpful message
        self.assertContains(
            response,
            'The background job was deleted',
            html=False
        )

        # Generate button should be enabled (NOT disabled)
        content = response.content.decode('utf-8')

        # Button label should say "Generate Devices" (first-time generation flow)
        # because there's no last_generated_at yet
        self.assertIn('Generate Devices', content)

        # Button should NOT have disabled attribute
        # Check that the actual button element doesn't have disabled
        self.assertNotIn('btn btn-warning mb-2" disabled', content,
                        "Generate button should not be disabled with orphaned job")

        # Button should have the trigger attributes for modal (not disabled)
        self.assertIn('data-bs-toggle="modal"', content,
                     "Generate button should have modal trigger when orphaned job exists")

        # Should show warning in actions section
        self.assertContains(response, 'Job Deleted:', html=False)
        self.assertContains(
            response,
            'Starting a new generation will reset the state',
            html=False
        )

    def test_detail_view_queued_orphaned_job_shows_warning(self):
        """
        Detail view should show warning for QUEUED orphaned job too.

        Given: Plan with orphaned GenerationState (status=QUEUED, job=None)
        When: GET detail view
        Then: Same warning behavior as IN_PROGRESS orphaned job
        """
        # Given: Create orphaned GenerationState with QUEUED status
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.QUEUED,
            job=None,  # Orphaned!
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # When: GET detail page
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(url)

        # Then: Should show orphaned job warning
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Job Deleted', html=False)
        self.assertContains(response, 'The background job was deleted', html=False)

    # =========================================================================
    # Test 2: POST with Orphaned Job Auto-Resets and Enqueues
    # =========================================================================

    def test_generate_update_with_orphaned_job_auto_resets_state(self):
        """
        POST to generate_update with orphaned job should auto-reset and enqueue.

        Given: Plan with orphaned GenerationState (status=IN_PROGRESS, job=None)
        When: POST to generate_update endpoint
        Then:
        - Warning message shown about previous job deletion
        - GenerationState.status reset from IN_PROGRESS to QUEUED
        - New job created
        - Redirects to new job detail page
        """
        # Given: Create orphaned GenerationState
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.IN_PROGRESS,
            job=None,  # Orphaned!
            device_count=10,
            interface_count=50,
            cable_count=25,
            snapshot={}
        )

        # When: POST to generate_update (follow redirect to see warning)
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])
        response = self.client.post(url, follow=True)

        # Then: Should eventually land on job page (after redirect chain)
        self.assertEqual(response.status_code, 200)

        # Should show warning message about previous job being deleted
        # The view shows this warning BEFORE redirecting to the job page
        # So we need to check the redirect chain for the message
        messages = list(response.context.get('messages', []))
        warning_found = False
        for msg in messages:
            if 'previous job was deleted' in str(msg.message).lower() or \
               'resetting generation state' in str(msg.message).lower():
                warning_found = True
                break

        self.assertTrue(
            warning_found,
            f"Should show warning about deleted job. Messages: {[str(m.message) for m in messages]}"
        )

        # GenerationState should be updated with new job and QUEUED status
        self.plan.refresh_from_db()
        self.assertTrue(hasattr(self.plan, 'generation_state'))

        state = self.plan.generation_state
        self.assertEqual(state.status, GenerationStatusChoices.QUEUED)
        self.assertIsNotNone(state.job, "New job should be created")

        # Verify the job exists
        job = state.job
        self.assertIsNotNone(job)
        self.assertIn(self.plan.name, job.name)

    def test_generate_update_with_queued_orphaned_job_creates_new_job(self):
        """
        POST to generate_update with QUEUED orphaned job should work too.

        Given: Plan with orphaned GenerationState (status=QUEUED, job=None)
        When: POST to generate_update endpoint
        Then: New job created, state updated
        """
        # Given: Create orphaned GenerationState with QUEUED status
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.QUEUED,
            job=None,  # Orphaned!
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # When: POST to generate_update
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])
        response = self.client.post(url, follow=False)

        # Then: Should create new job
        self.assertEqual(response.status_code, 302)

        self.plan.refresh_from_db()
        state = self.plan.generation_state
        self.assertIsNotNone(state.job, "New job should be created")
        self.assertEqual(state.status, GenerationStatusChoices.QUEUED)

    # =========================================================================
    # Test 3: POST Blocked When Valid Job Exists
    # =========================================================================

    def test_generate_update_blocked_when_valid_job_exists(self):
        """
        POST to generate_update should be blocked when valid job exists.

        Given: Plan with GenerationState (status=IN_PROGRESS, job=<valid Job>)
        When: POST to generate_update endpoint
        Then:
        - Request blocked (redirects back to detail page)
        - Error message shown
        - GenerationState unchanged
        - No new job created
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Given: Create GenerationState with VALID job
        existing_job = DeviceGenerationJob.enqueue(
            name="Existing Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )

        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.IN_PROGRESS,
            job=existing_job,  # Valid job!
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # When: POST to generate_update
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])
        response = self.client.post(url, follow=True)

        # Then: Should redirect back to detail page (blocked)
        self.assertEqual(response.status_code, 200)

        # Should be on detail page (not job page)
        self.assertTemplateUsed(response, 'netbox_hedgehog/topologyplan.html')

        # Should show error message
        messages = list(response.context['messages'])
        self.assertTrue(len(messages) > 0, "Should display error message")
        error_msg = str(messages[0].message).lower()
        self.assertIn('cannot start generation', error_msg)
        self.assertIn('in progress', error_msg)

        # GenerationState should be unchanged
        self.plan.refresh_from_db()
        state = self.plan.generation_state
        self.assertEqual(state.status, GenerationStatusChoices.IN_PROGRESS)
        self.assertEqual(state.job, existing_job)

        # Existing job should still be linked (not replaced with new job)
        self.assertIsNotNone(state.job, "Job should still exist")
        self.assertEqual(state.job.pk, existing_job.pk, "Job should not change")

    def test_generate_update_blocked_when_queued_with_valid_job(self):
        """
        POST blocked even when status=QUEUED if job is valid.

        Given: Plan with GenerationState (status=QUEUED, job=<valid Job>)
        When: POST to generate_update endpoint
        Then: Request blocked with error message
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Given: Create GenerationState with QUEUED status and VALID job
        existing_job = DeviceGenerationJob.enqueue(
            name="Queued Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )

        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.QUEUED,
            job=existing_job,  # Valid job!
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # When: POST to generate_update
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])
        response = self.client.post(url, follow=True)

        # Then: Should be blocked
        self.assertEqual(response.status_code, 200)

        messages = list(response.context['messages'])
        self.assertTrue(len(messages) > 0)
        error_msg = str(messages[0].message).lower()
        self.assertIn('cannot start generation', error_msg)
        self.assertIn('queued', error_msg)

    # =========================================================================
    # Test 4: Management Command Integration
    # =========================================================================

    def test_management_command_finds_orphaned_states(self):
        """
        Management command should find and reset orphaned states.

        Given: Plan with orphaned GenerationState
        When: Run reset_orphaned_generation_states command
        Then:
        - Orphaned state found
        - Status reset to FAILED
        - User can now start new generation
        """
        from django.core.management import call_command
        from io import StringIO

        # Given: Create orphaned GenerationState
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.IN_PROGRESS,
            job=None,  # Orphaned!
            device_count=10,
            interface_count=50,
            cable_count=25,
            snapshot={}
        )

        # When: Run management command
        out = StringIO()
        call_command('reset_orphaned_generation_states', '--no-input', stdout=out)
        output = out.getvalue()

        # Then: Should find and reset the orphaned state
        self.assertIn('Found 1 orphaned generation state', output)
        self.assertIn('Successfully reset 1 orphaned generation state', output)

        # State should be reset to FAILED
        self.plan.refresh_from_db()
        state = self.plan.generation_state
        self.assertEqual(state.status, GenerationStatusChoices.FAILED)
        self.assertIsNone(state.job)

    def test_management_command_skips_valid_states(self):
        """
        Management command should NOT reset states with valid jobs.

        Given: Plan with valid GenerationState (has job)
        When: Run reset_orphaned_generation_states command
        Then: State unchanged
        """
        from django.core.management import call_command
        from io import StringIO
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Given: Create valid GenerationState with job
        valid_job = DeviceGenerationJob.enqueue(
            name="Valid Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )

        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.IN_PROGRESS,
            job=valid_job,  # Valid job!
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # When: Run management command
        out = StringIO()
        call_command('reset_orphaned_generation_states', '--no-input', stdout=out)
        output = out.getvalue()

        # Then: Should find NO orphaned states
        self.assertIn('No orphaned generation states found', output)

        # State should be unchanged
        self.plan.refresh_from_db()
        state = self.plan.generation_state
        self.assertEqual(state.status, GenerationStatusChoices.IN_PROGRESS)
        self.assertEqual(state.job, valid_job)
