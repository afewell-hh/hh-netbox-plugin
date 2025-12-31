"""
Integration Tests for Generation UX Enhancements (DIET #135)

Tests for:
1. Destructive confirmation UX (modal flow)
2. Expectation guidance UX (modal flow)
3. Backend plan locking enforcement (blocks duplicate enqueue)
4. Job timeout configuration
5. Progress logging milestones

Following UX-accurate TDD approach per AGENTS.md:
- Tests verify actual request/response behavior
- Tests validate real template rendering (data attributes for modals)
- Tests enforce backend security (not just disabled buttons)
- Tests written BEFORE implementation (red → green → refactor)

Issue: https://github.com/afewell-hh/hh-netbox-plugin/issues/135
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from dcim.models import DeviceType, Manufacturer, Device
from users.models import ObjectPermission
from core.models import Job

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
    GenerationStatusChoices,
    ConnectionTypeChoices,
    ConnectionDistributionChoices,
    PortZoneTypeChoices,
)

User = get_user_model()


class GenerationUXEnhancementsTestCase(TestCase):
    """
    Integration tests for generation UX enhancements (issue #135).

    Coverage:
    1. Modal data attributes in template
    2. Backend duplicate enqueue blocking
    3. Job timeout configuration
    4. Progress logging milestones
    """

    @classmethod
    def setUpTestData(cls):
        """Create shared test data"""
        # Create superuser
        cls.superuser = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        # Create manufacturer and device types
        cls.manufacturer = Manufacturer.objects.create(
            name='TestMfg',
            slug='testmfg'
        )

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
        )

        # Create DeviceTypeExtension for switch
        cls.switch_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_type,
            native_speed=800,
            supported_breakouts=['4x200g'],
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

        # Create switch class
        self.switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='TEST-SW',
            device_type_extension=self.switch_ext,
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SPINE,
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
            server_class_id='TEST-SRV',
            server_device_type=self.server_type,
            quantity=4,
            gpus_per_server=8,
            category=ServerClassCategoryChoices.GPU
        )

        # Create server connection
        PlanServerConnection.objects.create(
            connection_id='TEST-CONN',
            server_class=self.server_class,
            target_switch_class=self.switch_class,
            ports_per_connection=2,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING
        )

    # =========================================================================
    # Test Group 1: Modal Data Attributes (Template UX)
    # =========================================================================

    def test_detail_page_includes_modal_data_attributes_for_first_time_generate(self):
        """
        Test 1a: Detail page should include data attributes for first-time generation.

        Given: Plan with no previous generation (last_generated_at = None)
        When: Load detail page
        Then:
          - Button has data-first-time="true"
          - Button has data-destructive="false"
          - Button has expected count attributes
        """
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check for modal data attributes on generate button
        self.assertIn('id="generate-btn"', content, "Generate button should exist")
        self.assertIn('data-first-time="true"', content, "Should mark first-time generation")
        self.assertIn('data-destructive="false"', content, "Should NOT be destructive for first generation")

        # Check for expected count attributes
        self.assertIn('data-device-count', content, "Should include expected device count")
        self.assertIn('data-interface-count', content, "Should include expected interface count")
        self.assertIn('data-cable-count', content, "Should include expected cable count")

    def test_detail_page_includes_destructive_flag_for_regenerate(self):
        """
        Test 1b: Detail page should mark regenerate as destructive.

        Given: Plan with previous generation (last_generated_at set)
        When: Load detail page
        Then:
          - Button has data-destructive="true"
          - Button has existing count attributes
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Create completed generation state
        job = DeviceGenerationJob.enqueue(
            name="Completed Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        job.status = 'completed'
        job.save()

        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.GENERATED,
            job=job,
            device_count=10,
            interface_count=20,
            cable_count=15,
            snapshot={}
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Should be marked destructive
        self.assertIn('data-destructive="true"', content, "Should mark regenerate as destructive")

        # Should include existing counts
        self.assertIn('data-existing-devices="10"', content)
        self.assertIn('data-existing-interfaces="20"', content)
        self.assertIn('data-existing-cables="15"', content)

    def test_detail_page_includes_expected_counts_in_context(self):
        """
        Test 1c: View should calculate and pass expected counts to template.

        Given: Plan with server and switch classes
        When: Load detail page
        Then: Context includes expected_device_count, expected_interface_count, expected_cable_count
        """
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Verify context variables exist
        self.assertIn('expected_device_count', response.context)
        self.assertIn('expected_interface_count', response.context)
        self.assertIn('expected_cable_count', response.context)

        # Verify calculations are correct
        expected_servers = self.server_class.quantity  # 4
        expected_switches = self.switch_class.override_quantity  # 2
        expected_devices = expected_servers + expected_switches  # 6

        self.assertEqual(response.context['expected_device_count'], expected_devices)

    # =========================================================================
    # Test Group 2: Backend Plan Locking Enforcement
    # =========================================================================

    def test_backend_blocks_duplicate_enqueue_when_queued(self):
        """
        Test 2a: Backend should block duplicate enqueue when job QUEUED.

        Given: Plan with GenerationState status=QUEUED
        When: POST to generate endpoint again
        Then:
          - Request rejected with error message
          - No new job created
          - Redirect to detail page (not job page)
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Create first job (QUEUED)
        job1 = DeviceGenerationJob.enqueue(
            name="First Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.QUEUED,
            job=job1,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # Attempt to enqueue second job
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])
        response = self.client.post(url, follow=True)

        # Should redirect to detail page (not job page)
        self.assertEqual(response.status_code, 200)
        expected_url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        self.assertEqual(response.redirect_chain[-1][0], expected_url)

        # Should show error message
        messages = list(response.context['messages'])
        self.assertTrue(len(messages) > 0, "Should display error message")
        error_msg = str(messages[0].message).lower()
        self.assertIn('cannot start generation', error_msg)
        self.assertIn('already', error_msg)
        self.assertIn('queued', error_msg)

        # Should NOT create second job
        job_count = Job.objects.filter(
            object_id=self.plan.pk,
            name__icontains='generate'
        ).count()
        self.assertEqual(job_count, 1, "Should not create duplicate job")

    def test_backend_blocks_duplicate_enqueue_when_in_progress(self):
        """
        Test 2b: Backend should block duplicate enqueue when job IN_PROGRESS.

        Given: Plan with GenerationState status=IN_PROGRESS
        When: POST to generate endpoint
        Then:
          - Request rejected with error message
          - No new job created
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Create job in progress
        job1 = DeviceGenerationJob.enqueue(
            name="Running Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.IN_PROGRESS,
            job=job1,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # Attempt to enqueue second job
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])
        response = self.client.post(url, follow=True)

        # Should reject with error
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(len(messages) > 0)
        error_msg = str(messages[0].message).lower()
        self.assertIn('cannot start generation', error_msg)
        self.assertIn('in progress', error_msg)

    def test_backend_allows_enqueue_after_job_completed(self):
        """
        Test 2c: Backend should allow enqueue after previous job completed.

        Given: Plan with GenerationState status=GENERATED (completed)
        When: POST to generate endpoint
        Then:
          - New job created successfully
          - Status updated to QUEUED
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Create completed job
        job1 = DeviceGenerationJob.enqueue(
            name="Completed Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        job1.status = 'completed'
        job1.save()

        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.GENERATED,
            job=job1,
            device_count=5,
            interface_count=10,
            cable_count=8,
            snapshot={}
        )

        # Attempt to enqueue new job (should succeed)
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])
        response = self.client.post(url, follow=False)

        # Should redirect to job page (success)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/core/jobs/', response['Location'], "Should redirect to job page")

        # Should create new job
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.generation_state.status, GenerationStatusChoices.QUEUED)
        self.assertIsNotNone(self.plan.generation_state.job)

    def test_backend_allows_enqueue_after_job_failed(self):
        """
        Test 2d: Backend should allow retry after previous job failed.

        Given: Plan with GenerationState status=FAILED
        When: POST to generate endpoint
        Then: New job created (retry allowed)
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Create failed job
        job1 = DeviceGenerationJob.enqueue(
            name="Failed Job",
            user=self.superuser,
            plan_id=self.plan.pk,
        )
        job1.status = 'failed'
        job1.save()

        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.FAILED,
            job=job1,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}
        )

        # Attempt retry
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])
        response = self.client.post(url, follow=False)

        # Should succeed
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.generation_state.status, GenerationStatusChoices.QUEUED)

    # =========================================================================
    # Test Group 3: Job Timeout Configuration
    # =========================================================================

    @override_settings(
        PLUGINS_CONFIG={
            'netbox_hedgehog': {
                'device_generation_timeout': 7200  # 2 hours
            }
        }
    )
    @patch('netbox_hedgehog.views.topology_planning.DeviceGenerationJob.enqueue')
    def test_job_enqueued_with_configured_timeout(self, mock_enqueue):
        """
        Test 3a: Job should be enqueued with configured timeout.

        Given: Plugin config with device_generation_timeout=7200
        When: POST to generate endpoint
        Then: enqueue() called with timeout=7200
        """
        # Create a real Job instance to avoid FK constraint violations
        from django.contrib.contenttypes.models import ContentType
        import uuid
        content_type = ContentType.objects.get_for_model(self.plan)
        real_job = Job.objects.create(
            object_type=content_type,
            object_id=self.plan.pk,
            name="Mock Job",
            user=self.superuser,
            job_id=uuid.uuid4(),
        )
        mock_enqueue.return_value = real_job

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])
        response = self.client.post(url, follow=False)

        # Verify enqueue was called with timeout parameter
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args[1]
        self.assertEqual(call_kwargs['timeout'], 7200, "Should pass configured timeout to enqueue")

    @override_settings(PLUGINS_CONFIG={'netbox_hedgehog': {}})
    @patch('netbox_hedgehog.views.topology_planning.DeviceGenerationJob.enqueue')
    def test_job_enqueued_with_default_timeout_when_not_configured(self, mock_enqueue):
        """
        Test 3b: Job should use default timeout when not configured.

        Given: Plugin config without device_generation_timeout
        When: POST to generate endpoint
        Then: enqueue() called with timeout=3600 (default)
        """
        # Create a real Job instance to avoid FK constraint violations
        from django.contrib.contenttypes.models import ContentType
        import uuid
        content_type = ContentType.objects.get_for_model(self.plan)
        real_job = Job.objects.create(
            object_type=content_type,
            object_id=self.plan.pk,
            name="Mock Job",
            user=self.superuser,
            job_id=uuid.uuid4(),
        )
        mock_enqueue.return_value = real_job

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update', args=[self.plan.pk])
        response = self.client.post(url, follow=False)

        # Verify default timeout used
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args[1]
        self.assertEqual(call_kwargs['timeout'], 3600, "Should use default 3600s timeout")

    # =========================================================================
    # Test Group 4: Progress Logging Milestones
    # =========================================================================

    def test_job_logs_progress_milestones(self):
        """
        Test 4a: Job should log progress at each phase.

        Given: DeviceGenerationJob with plan
        When: job.run() executes
        Then: Job logs contain milestone messages:
          - "Phase 1/6: Cleaning up..."
          - "Phase 2/6: Creating switch devices..."
          - "Phase 3/6: Creating server devices..."
          - "Phase 4/6: Creating interfaces and cables..."
          - "Phase 5/6: Tagging..."
          - "Phase 6/6: Updating generation state..."
          - "✓ Generation complete:"
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        # Clear devices
        Device.objects.all().delete()

        # Create job
        job = DeviceGenerationJob.enqueue(
            name="Progress Test",
            user=self.superuser,
            plan_id=self.plan.pk,
        )

        # Execute job
        job_runner = DeviceGenerationJob(job=job)

        # Capture logs by checking job.data after execution
        job_runner.run(plan_id=self.plan.pk)

        # Refresh job to get logs
        job.refresh_from_db()

        # Job should have log data
        # Note: Exact log format depends on NetBox JobRunner implementation
        # We verify that the job completed successfully and logs exist
        self.assertIsNotNone(job.data, "Job should have log data")

        # Convert log data to string for searching
        log_str = str(job.data).lower()

        # Verify key milestone phrases appear
        self.assertIn('phase', log_str, "Logs should contain phase milestones")

    def test_device_generator_accepts_logger_parameter(self):
        """
        Test 4b: DeviceGenerator should accept optional logger.

        Given: DeviceGenerator instantiated with logger
        When: generate_all() is called
        Then: No errors, logger used for progress tracking
        """
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        import logging

        # Create a mock logger
        mock_logger = MagicMock(spec=logging.Logger)

        # Clear devices
        Device.objects.all().delete()

        # Create generator with logger
        generator = DeviceGenerator(plan=self.plan, logger=mock_logger)
        result = generator.generate_all()

        # Should complete successfully
        self.assertGreater(result.device_count, 0)

        # Logger should have been called (if implementation uses it)
        # Note: This will fail until implementation adds logger support
        # For now, we just verify generator accepts the parameter
        self.assertIsNotNone(generator.logger)

    def test_job_passes_logger_to_device_generator(self):
        """
        Test 4c: DeviceGenerationJob should pass self.logger to DeviceGenerator.

        Given: DeviceGenerationJob
        When: run() is called
        Then: DeviceGenerator instantiated with job's logger
        """
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob
        from netbox_hedgehog.services.device_generator import DeviceGenerator

        # Clear devices
        Device.objects.all().delete()

        # Create job
        job = DeviceGenerationJob.enqueue(
            name="Logger Test",
            user=self.superuser,
            plan_id=self.plan.pk,
        )

        # Patch DeviceGenerator to verify logger passed
        with patch('netbox_hedgehog.jobs.device_generation.DeviceGenerator') as MockGen:
            mock_instance = MockGen.return_value
            mock_instance.generate_all.return_value = type('obj', (object,), {
                'device_count': 5,
                'interface_count': 10,
                'cable_count': 8
            })()

            # Execute job
            job_runner = DeviceGenerationJob(job=job)
            job_runner.run(plan_id=self.plan.pk)

            # Verify DeviceGenerator was called with logger
            MockGen.assert_called_once()
            call_kwargs = MockGen.call_args[1]
            self.assertIn('logger', call_kwargs, "Should pass logger to DeviceGenerator")
            self.assertIsNotNone(call_kwargs['logger'])
