"""
Django management command to set up test data for browser UX tests.

This creates topology plans with known configurations that browser tests
can use to validate the UI.

Usage:
    docker compose exec netbox python manage.py setup_ux_test_data

    # With cleanup flag to remove old test data first:
    docker compose exec netbox python manage.py setup_ux_test_data --clean
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from dcim.models import DeviceType, Manufacturer
from dcim.models import Cable, Device, Interface
from extras.models import Tag

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


class Command(BaseCommand):
    help = 'Set up test data for browser UX tests'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Remove existing UX test data before creating new data',
        )

    def handle(self, *args, **options):
        if options['clean']:
            self.stdout.write('🧹 Cleaning up existing UX test data...')
            self._cleanup_test_data()

        self.stdout.write('📦 Creating UX test data...')

        try:
            with transaction.atomic():
                # Create reference data
                manufacturer, breakout_option, device_ext = self._create_reference_data()

                # Create test plans
                plan1 = self._create_test_plan_1(manufacturer, breakout_option, device_ext)
                plan2 = self._create_test_plan_2(manufacturer, breakout_option, device_ext)
                empty_plan = self._create_empty_plan()

                # Pre-generate plan2 so we can test regeneration warning
                self.stdout.write('\n  Pre-generating Plan 2 for regeneration tests...')
                self._generate_plan(plan2)

                # Create limited-permission user for permission tests
                self.stdout.write('  Creating limited-permission user...')
                self._create_limited_user()

                self.stdout.write(self.style.SUCCESS('\n✅ Test data created successfully!'))
                self.stdout.write('\nCreated Plans:')
                self.stdout.write(f'  1. {plan1.name} (ID: {plan1.pk}) - Ready for generation')
                self.stdout.write(f'  2. {plan2.name} (ID: {plan2.pk}) - Pre-generated for regeneration tests')
                self.stdout.write(f'  3. {empty_plan.name} (ID: {empty_plan.pk}) - Empty plan for warnings')

                self.stdout.write('\nCreated Users:')
                self.stdout.write('  - admin / admin (superuser)')
                self.stdout.write('  - viewer / viewer (view-only permissions)')

                self.stdout.write('\n📝 Next steps:')
                self.stdout.write('  - Run browser tests: python3 -m pytest -v')
                self.stdout.write('  - Tests will use these plans and users to validate the UI')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error creating test data: {str(e)}'))
            raise

    def _cleanup_test_data(self):
        """Remove existing UX test data"""
        # Remove generated objects from prior UX test runs
        tag = Tag.objects.filter(slug='hedgehog-generated').first()
        if tag:
            Cable.objects.filter(tags=tag).delete()
            Device.objects.filter(tags=tag).delete()
            Interface.objects.filter(tags=tag).delete()

        # Delete in dependency order due to PROTECT on target_zone
        plans = TopologyPlan.objects.filter(name__startswith='UX Test Plan')
        PlanServerConnection.objects.filter(server_class__plan__in=plans).delete()
        SwitchPortZone.objects.filter(switch_class__plan__in=plans).delete()
        PlanSwitchClass.objects.filter(plan__in=plans).delete()
        PlanServerClass.objects.filter(plan__in=plans).delete()
        GenerationState.objects.filter(plan__in=plans).delete()
        deleted_count = plans.delete()[0]

        if deleted_count > 0:
            self.stdout.write(f'  Deleted {deleted_count} test plans')

        # Delete viewer user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        viewer_deleted = User.objects.filter(username='viewer').delete()[0]
        if viewer_deleted > 0:
            self.stdout.write(f'  Deleted viewer user')

        # Delete test site
        from dcim.models import Site
        site_deleted = Site.objects.filter(slug='ux-test-site').delete()[0]
        if site_deleted > 0:
            self.stdout.write(f'  Deleted test site')

    def _create_reference_data(self):
        """Create manufacturer, device types, extensions, breakout options"""
        self.stdout.write('  Creating reference data...')

        # Manufacturer
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name='UX Test Vendor',
            defaults={'slug': 'ux-test-vendor'}
        )

        # Switch DeviceType
        switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='UX-Test-Switch-800G',
            defaults={'slug': 'ux-test-switch-800g'}
        )

        # Server DeviceType
        server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='UX-Test-Server',
            defaults={'slug': 'ux-test-server'}
        )

        # Breakout option
        breakout_option, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g-ux-test',
            defaults={
                'from_speed': 800,
                'logical_ports': 4,
                'logical_speed': 200
            }
        )

        # Device type extension
        device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=switch_type,
            defaults={
                'native_speed': 800,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g'],
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf']
            }
        )

        self.stdout.write('    ✓ Reference data ready')
        return manufacturer, breakout_option, device_ext

    def _create_test_plan_1(self, manufacturer, breakout_option, device_ext):
        """Create primary test plan with servers and switches"""
        self.stdout.write('  Creating Test Plan 1 (primary)...')

        # Create plan
        plan = TopologyPlan.objects.create(
            name='UX Test Plan 1 - Generate Devices',
            description='Test plan for browser UX tests - validates Generate Devices workflow',
            status=TopologyPlanStatusChoices.DRAFT
        )

        # Get server device type
        server_type = DeviceType.objects.get(model='UX-Test-Server', manufacturer=manufacturer)

        # Create server class
        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='ux-test-servers',
            category=ServerClassCategoryChoices.GPU,
            quantity=3,  # 3 servers for testing
            gpus_per_server=8,
            server_device_type=server_type
        )

        # Create switch class
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='ux-test-frontend-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=device_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
            calculated_quantity=2,  # Will be recalculated
            override_quantity=None
        )

        # Create port zone
        server_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-60',
            breakout_option=breakout_option,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100
        )

        # Create connection
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='ux-test-frontend',
            connection_name='Frontend Connection',
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=server_zone,
            speed=200
        )

        self.stdout.write('    ✓ Test Plan 1 created')
        return plan

    def _create_test_plan_2(self, manufacturer, breakout_option, device_ext):
        """Create second test plan for multi-plan isolation testing"""
        self.stdout.write('  Creating Test Plan 2 (multi-plan)...')

        plan = TopologyPlan.objects.create(
            name='UX Test Plan 2 - Multi-Plan Isolation',
            description='Second plan to test that regenerating Plan 1 does not affect Plan 2',
            status=TopologyPlanStatusChoices.DRAFT
        )

        server_type = DeviceType.objects.get(model='UX-Test-Server', manufacturer=manufacturer)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='ux-test-servers-plan2',
            category=ServerClassCategoryChoices.INFRASTRUCTURE,
            quantity=2,
            server_device_type=server_type
        )

        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='ux-test-leaf-plan2',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=device_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
            calculated_quantity=1,
        )

        server_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-60',
            breakout_option=breakout_option,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100
        )

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='ux-test-conn-plan2',
            connection_name='Plan 2 Connection',
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_zone=server_zone,
            speed=200
        )

        self.stdout.write('    ✓ Test Plan 2 created')
        return plan

    def _create_empty_plan(self):
        """Create empty plan to test warning messages"""
        self.stdout.write('  Creating Empty Plan (for warnings)...')

        plan = TopologyPlan.objects.create(
            name='UX Test Plan 3 - Empty (Warnings)',
            description='Empty plan to test that preview shows warnings',
            status=TopologyPlanStatusChoices.DRAFT
        )

        self.stdout.write('    ✓ Empty Plan created')
        return plan

    def _generate_plan(self, plan):
        """Pre-generate devices for a plan to test regeneration warnings"""
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        from dcim.models import Site

        # Get or create a site for the generated devices
        site, _ = Site.objects.get_or_create(
            name='UX Test Site',
            defaults={'slug': 'ux-test-site'}
        )

        # Generate devices using the DeviceGenerator service
        generator = DeviceGenerator(plan, site)
        result = generator.generate_all()

        self.stdout.write(f'    ✓ Plan pre-generated ({result.device_count} devices, {result.cable_count} cables)')

    def _create_limited_user(self):
        """Create a user with view-only permissions for permission tests"""
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        User = get_user_model()

        # Delete existing viewer user if exists
        User.objects.filter(username='viewer').delete()

        # Create viewer user
        viewer = User.objects.create_user(
            username='viewer',
            email='viewer@example.com',
            password='viewer',
            is_staff=True,  # Need is_staff to access admin interface
            is_active=True
        )

        # Add view permissions for topology planning models
        content_type = ContentType.objects.get_for_model(TopologyPlan)
        view_permission = Permission.objects.get(
            content_type=content_type,
            codename='view_topologyplan'
        )
        viewer.user_permissions.add(view_permission)

        self.stdout.write('    ✓ Viewer user created (username: viewer, password: viewer)')
