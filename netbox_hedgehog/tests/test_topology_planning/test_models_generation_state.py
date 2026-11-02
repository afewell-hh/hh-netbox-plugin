"""
Tests for GenerationState model.

Test categories:
- Basic CRUD operations
- Snapshot content
- is_dirty() method behavior
- Status field validation
- Model constraints (OneToOne relationship)
- TopologyPlan properties integration

Following TDD approach: Tests written BEFORE implementation.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    GenerationState,
    DeviceTypeExtension,
)
from dcim.models import DeviceType, Manufacturer

from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot


class GenerationStateModelTestCase(TestCase):
    """Test suite for GenerationState model"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods"""
        # Create manufacturer and device types
        cls.manufacturer = Manufacturer.objects.create(
            name="Test Manufacturer",
            slug="test-manufacturer"
        )

        cls.device_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model="Test Switch",
            slug="test-switch"
        )

        cls.device_type_ext = DeviceTypeExtension.objects.create(
            device_type=cls.device_type,
            native_speed=800,
            uplink_ports=16
        )

        # Create test plan
        cls.test_plan = TopologyPlan.objects.create(
            name="Test Plan"
        )

    # =========================================================================
    # 1. Basic CRUD Operations
    # =========================================================================

    def test_create_generation_state(self):
        """Test creating GenerationState"""
        plan = TopologyPlan.objects.create(name="New Plan")

        state = GenerationState.objects.create(
            plan=plan,
            device_count=100,
            interface_count=500,
            cable_count=400,
            snapshot={'test': 'data'},
            status='generated'
        )

        self.assertEqual(state.plan, plan)
        self.assertEqual(state.device_count, 100)
        self.assertEqual(state.interface_count, 500)
        self.assertEqual(state.cable_count, 400)
        self.assertEqual(state.snapshot, {'test': 'data'})
        self.assertEqual(state.status, 'generated')
        self.assertIsNotNone(state.generated_at)

    def test_str_representation(self):
        """Test __str__ returns readable format"""
        plan = TopologyPlan.objects.create(name="My Plan")

        state = GenerationState.objects.create(
            plan=plan,
            device_count=50,
            interface_count=200,
            cable_count=150,
            snapshot={},
            status='generated'
        )

        str_repr = str(state)
        self.assertIn("My Plan", str_repr)
        self.assertIn("50", str_repr)

    # =========================================================================
    # 2. Snapshot Content
    # =========================================================================

    def test_snapshot_contains_server_class_quantities(self):
        """Test snapshot captures server class quantities"""
        plan = TopologyPlan.objects.create(name="Plan")

        # Create server classes
        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        # Create snapshot
        snapshot = {
            'server_classes': [
                {
                    'server_class_id': 'gpu-b200',
                    'quantity': 96
                }
            ],
            'switch_classes': []
        }

        state = GenerationState.objects.create(
            plan=plan,
            device_count=96,
            interface_count=192,
            cable_count=192,
            snapshot=snapshot,
            status='generated'
        )

        self.assertIn('server_classes', state.snapshot)
        self.assertEqual(len(state.snapshot['server_classes']), 1)
        self.assertEqual(state.snapshot['server_classes'][0]['server_class_id'], 'gpu-b200')
        self.assertEqual(state.snapshot['server_classes'][0]['quantity'], 96)

    def test_snapshot_contains_switch_class_quantities(self):
        """Test snapshot captures switch class effective quantities"""
        plan = TopologyPlan.objects.create(name="Plan")

        # Create switch class
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-leaf",
            device_type_extension=self.device_type_ext,
            uplink_ports_per_switch=16
        )

        # Create snapshot
        snapshot = {
            'server_classes': [],
            'switch_classes': [
                {
                    'switch_class_id': 'fe-leaf',
                    'effective_quantity': 12
                }
            ]
        }

        state = GenerationState.objects.create(
            plan=plan,
            device_count=12,
            interface_count=768,
            cable_count=192,
            snapshot=snapshot,
            status='generated'
        )

        self.assertIn('switch_classes', state.snapshot)
        self.assertEqual(len(state.snapshot['switch_classes']), 1)
        self.assertEqual(state.snapshot['switch_classes'][0]['switch_class_id'], 'fe-leaf')
        self.assertEqual(state.snapshot['switch_classes'][0]['effective_quantity'], 12)

    # =========================================================================
    # 3. is_dirty() Method
    # =========================================================================

    def test_is_dirty_returns_false_when_unchanged(self):
        """Test is_dirty() returns False when plan hasn't changed"""
        plan = TopologyPlan.objects.create(name="Plan")

        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        server = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        # Capture real snapshot from current DB state
        snapshot = build_plan_snapshot(plan)

        state = GenerationState.objects.create(
            plan=plan,
            device_count=96,
            interface_count=192,
            cable_count=192,
            snapshot=snapshot,
            status='generated'
        )

        self.assertFalse(state.is_dirty())

    def test_is_dirty_returns_true_when_server_quantity_changed(self):
        """Test is_dirty() detects server quantity changes"""
        plan = TopologyPlan.objects.create(name="Plan")

        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        server = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        # Capture real snapshot before modification
        snapshot = build_plan_snapshot(plan)

        state = GenerationState.objects.create(
            plan=plan,
            device_count=96,
            interface_count=192,
            cable_count=192,
            snapshot=snapshot,
            status='generated'
        )

        # Change server quantity
        server.quantity = 128
        server.save()

        self.assertTrue(state.is_dirty())

    def test_is_dirty_returns_true_when_server_class_added(self):
        """Test is_dirty() detects new server classes"""
        plan = TopologyPlan.objects.create(name="Plan")

        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        # Create initial server
        PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        # Capture real snapshot before adding second class
        snapshot = build_plan_snapshot(plan)

        state = GenerationState.objects.create(
            plan=plan,
            device_count=96,
            interface_count=192,
            cable_count=192,
            snapshot=snapshot,
            status='generated'
        )

        # Add new server class
        PlanServerClass.objects.create(
            plan=plan,
            server_class_id="storage-a",
            quantity=32,
            server_device_type=server_dt
        )

        self.assertTrue(state.is_dirty())

    def test_is_dirty_returns_true_when_server_class_removed(self):
        """Test is_dirty() detects removed server classes"""
        plan = TopologyPlan.objects.create(name="Plan")

        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        # Create two server classes
        server1 = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        server2 = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="storage-a",
            quantity=32,
            server_device_type=server_dt
        )

        # Capture real snapshot before removing a class
        snapshot = build_plan_snapshot(plan)

        state = GenerationState.objects.create(
            plan=plan,
            device_count=128,
            interface_count=256,
            cable_count=256,
            snapshot=snapshot,
            status='generated'
        )

        # Remove one server class
        server2.delete()

        self.assertTrue(state.is_dirty())

    def test_is_dirty_returns_true_when_switch_quantity_changed(self):
        """Test is_dirty() detects switch quantity changes"""
        plan = TopologyPlan.objects.create(name="Plan")

        # Create switch class
        switch = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-leaf",
            device_type_extension=self.device_type_ext,
            uplink_ports_per_switch=16,
            override_quantity=12
        )

        # Capture real snapshot before modification
        snapshot = build_plan_snapshot(plan)

        state = GenerationState.objects.create(
            plan=plan,
            device_count=12,
            interface_count=768,
            cable_count=0,
            snapshot=snapshot,
            status='generated'
        )

        # Change switch quantity
        switch.override_quantity = 16
        switch.save()

        self.assertTrue(state.is_dirty())

    # =========================================================================
    # 4. Status Field Validation
    # =========================================================================

    def test_status_choices(self):
        """Test status accepts valid choices"""
        plan = TopologyPlan.objects.create(name="Plan")

        valid_statuses = ['generated', 'dirty']

        for status in valid_statuses:
            state = GenerationState.objects.create(
                plan=plan,
                device_count=0,
                interface_count=0,
                cable_count=0,
                snapshot={},
                status=status
            )
            self.assertEqual(state.status, status)
            state.delete()

    def test_status_invalid_choice(self):
        """Test status rejects invalid choice"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status='invalid'
        )

        with self.assertRaises(ValidationError):
            state.full_clean()

    # =========================================================================
    # 5. Model Constraints
    # =========================================================================

    def test_one_to_one_relationship_with_plan(self):
        """Test GenerationState has OneToOne relationship with TopologyPlan"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status='generated'
        )

        # Attempt to create duplicate state for same plan
        with self.assertRaises(IntegrityError):
            GenerationState.objects.create(
                plan=plan,
                device_count=0,
                interface_count=0,
                cable_count=0,
                snapshot={},
                status='generated'
            )

    def test_cascade_delete_when_plan_deleted(self):
        """Test generation state is deleted when plan is deleted"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status='generated'
        )

        state_id = state.pk
        self.assertEqual(GenerationState.objects.filter(pk=state_id).count(), 1)

        plan.delete()

        self.assertEqual(GenerationState.objects.filter(pk=state_id).count(), 0)

    # =========================================================================
    # 6. Count Validations
    # =========================================================================

    def test_device_count_non_negative(self):
        """Test device_count must be non-negative"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState(
            plan=plan,
            device_count=-1,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status='generated'
        )

        with self.assertRaises(ValidationError):
            state.full_clean()

    def test_interface_count_non_negative(self):
        """Test interface_count must be non-negative"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState(
            plan=plan,
            device_count=0,
            interface_count=-1,
            cable_count=0,
            snapshot={},
            status='generated'
        )

        with self.assertRaises(ValidationError):
            state.full_clean()

    def test_cable_count_non_negative(self):
        """Test cable_count must be non-negative"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=-1,
            snapshot={},
            status='generated'
        )

        with self.assertRaises(ValidationError):
            state.full_clean()


class TopologyPlanPropertiesTestCase(TestCase):
    """Test suite for TopologyPlan properties that interact with GenerationState"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods"""
        cls.manufacturer = Manufacturer.objects.create(
            name="Test Manufacturer",
            slug="test-manufacturer"
        )

    # =========================================================================
    # TopologyPlan Properties
    # =========================================================================

    def test_last_generated_at_returns_none_when_never_generated(self):
        """Test last_generated_at property returns None before generation"""
        plan = TopologyPlan.objects.create(name="Plan")

        self.assertIsNone(plan.last_generated_at)

    def test_last_generated_at_returns_timestamp_after_generation(self):
        """Test last_generated_at property returns correct timestamp"""
        plan = TopologyPlan.objects.create(name="Plan")

        before = timezone.now()
        state = GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status='generated'
        )
        after = timezone.now()

        # Refresh plan to get property
        plan.refresh_from_db()

        self.assertIsNotNone(plan.last_generated_at)
        self.assertGreaterEqual(plan.last_generated_at, before)
        self.assertLessEqual(plan.last_generated_at, after)

    def test_needs_regeneration_returns_false_when_never_generated(self):
        """Test needs_regeneration returns False before first generation"""
        plan = TopologyPlan.objects.create(name="Plan")

        self.assertFalse(plan.needs_regeneration)

    def test_needs_regeneration_returns_false_when_clean(self):
        """Test needs_regeneration returns False when not dirty"""
        plan = TopologyPlan.objects.create(name="Plan")

        GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot=build_plan_snapshot(plan),
            status='generated'
        )

        # Refresh plan to get property
        plan.refresh_from_db()

        self.assertFalse(plan.needs_regeneration)

    def test_needs_regeneration_returns_true_when_plan_changed(self):
        """Test needs_regeneration returns True when plan modified"""
        plan = TopologyPlan.objects.create(name="Plan")

        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        # Capture real snapshot before adding server class
        GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot=build_plan_snapshot(plan),
            status='generated'
        )

        # Add server class (modifies plan)
        PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        # Refresh plan to get property
        plan.refresh_from_db()

        self.assertTrue(plan.needs_regeneration)


class SnapshotSyncDisplayClassificationTests(TestCase):
    """Display-only classifier (#739): pure, never changes is_dirty()."""

    HISTORICAL = ('place_in_racks', 'servers_per_rack', 'membership_only')

    @staticmethod
    def _server(sid, qty=2, **extra):
        data = dict(
            server_class_id=sid, quantity=qty, device_type_id=1,
            gpus_per_server=8, place_in_racks=False,
            servers_per_rack=None, membership_only=False,
        )
        data.update(extra)
        return data

    def _snap(self, servers=None, **overrides):
        snap = dict(
            server_classes=servers if servers is not None else [self._server('gpu')],
            switch_classes=[dict(switch_class_id='leaf', effective_quantity=2)],
            connections=[dict(connection_id='c1', speed=200, rail=None)],
            port_zones=[dict(zone_name='z1', allocation_order=None)],
            mclag_domains=[],
        )
        snap.update(overrides)
        return snap

    def _strip(self, snap, keys=HISTORICAL):
        import copy
        out = copy.deepcopy(snap)
        for entry in out['server_classes']:
            for key in keys:
                entry.pop(key, None)
        return out

    def classify(self, current, saved):
        from netbox_hedgehog.models.topology_planning.generation import classify_snapshot_sync
        return classify_snapshot_sync(current, saved)

    def test_complete_equal_is_in_sync_and_order_insensitive(self):
        current = self._snap(servers=[self._server('a'), self._server('b')])
        saved = self._snap(servers=[self._server('b'), self._server('a')])
        self.assertEqual(self.classify(current, saved), 'in_sync')

    def test_three_missing_keys_is_incomplete(self):
        current = self._snap()
        self.assertEqual(self.classify(current, self._strip(current)), 'snapshot_incomplete')

    def test_partial_missing_keys_and_multiple_classes_incomplete(self):
        current = self._snap(servers=[self._server('a'), self._server('b')])
        saved = self._strip(current, keys=('servers_per_rack',))
        saved['server_classes'][1].pop('membership_only')
        self.assertEqual(self.classify(current, saved), 'snapshot_incomplete')

    def test_nondefault_current_value_for_missing_key_is_still_incomplete(self):
        current = self._snap(servers=[self._server(
            'gpu', place_in_racks=True, servers_per_rack=8, membership_only=True)])
        self.assertEqual(self.classify(current, self._strip(current)), 'snapshot_incomplete')

    def test_present_historical_key_with_different_value_is_changed(self):
        current = self._snap(servers=[self._server('gpu', place_in_racks=True)])
        self.assertEqual(self.classify(current, self._snap()), 'changed')

    def test_known_changes_alongside_missing_keys_are_changed(self):
        stripped = self._strip(self._snap())
        cases = dict(
            quantity=self._snap(servers=[self._server('gpu', qty=4)]),
            connection=self._snap(connections=[dict(connection_id='c1', speed=400, rail=None)]),
            zone=self._snap(port_zones=[dict(zone_name='z1', allocation_order=3)]),
            added_class=self._snap(servers=[self._server('gpu'), self._server('new')]),
        )
        for name, current in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.classify(current, stripped), 'changed')

    def test_removed_class_is_changed(self):
        saved = self._strip(self._snap(servers=[self._server('a'), self._server('b')]))
        current = self._snap(servers=[self._server('a')])
        self.assertEqual(self.classify(current, saved), 'changed')

    def test_none_and_zero_remain_distinct(self):
        current = self._snap(servers=[self._server('gpu', servers_per_rack=None)])
        saved = self._snap(servers=[self._server('gpu', servers_per_rack=0)])
        self.assertEqual(self.classify(current, saved), 'changed')

    def test_malformed_missing_or_duplicate_identities_never_in_sync(self):
        current = self._snap()
        malformed = dict(
            none=None, empty={}, string='bad',
            non_list=self._snap(server_classes='x'),
            non_dict_entry=self._snap(servers=['x']),
        )
        for name, saved in malformed.items():
            with self.subTest(name=name):
                self.assertEqual(self.classify(current, saved), 'snapshot_incomplete')
        dup = self._strip(self._snap(servers=[self._server('gpu'), self._server('gpu')]))
        self.assertEqual(self.classify(current, dup), 'snapshot_incomplete')
        no_id = self._snap(servers=[dict(quantity=2)])
        self.assertEqual(self.classify(current, no_id), 'snapshot_incomplete')

    def test_record_level_malformed_saved_evidence_is_incomplete_not_changed(self):
        current = self._snap()
        no_qty = self._snap(servers=[self._server('gpu')])
        del no_qty['server_classes'][0]['quantity']
        no_id = self._snap(servers=[self._server('gpu')])
        del no_id['server_classes'][0]['server_class_id']
        cases = dict(
            missing_quantity=no_qty,
            missing_server_class_id=no_id,
            duplicate_identity=self._snap(servers=[self._server('gpu'), self._server('gpu')]),
            none_connection=self._snap(connections=[None]),
            none_switch=self._snap(switch_classes=[None]),
            none_zone=self._snap(port_zones=[None]),
        )
        for name, saved in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.classify(current, saved), 'snapshot_incomplete')

    def test_identical_malformed_snapshots_are_never_in_sync(self):
        import copy
        no_qty = self._snap()
        del no_qty['server_classes'][0]['quantity']
        no_id = self._snap(servers=[dict(quantity=2)])
        cases = dict(
            missing_quantity=no_qty,
            missing_identity=no_id,
            duplicate=self._snap(servers=[self._server('gpu'), self._server('gpu')]),
            none_connection=self._snap(connections=[None]),
        )
        for name, snap in cases.items():
            with self.subTest(name=name):
                self.assertEqual(
                    self.classify(copy.deepcopy(snap), copy.deepcopy(snap)),
                    'snapshot_incomplete',
                )

    def test_malformed_current_evidence_is_incomplete(self):
        saved = self._snap()
        self.assertEqual(
            self.classify(self._snap(connections=[None]), saved), 'snapshot_incomplete')

    def test_classification_does_not_mutate_inputs(self):
        import copy
        current = self._snap()
        saved = self._strip(current)
        before = (copy.deepcopy(current), copy.deepcopy(saved))
        self.classify(current, saved)
        self.assertEqual((current, saved), before)

    def _plan_with_server(self, suffix):
        manufacturer = Manufacturer.objects.create(name='Sync Mfr ' + suffix, slug='sync-mfr-' + suffix)
        dt = DeviceType.objects.create(
            manufacturer=manufacturer, model='Sync Srv ' + suffix, slug='sync-srv-' + suffix)
        plan = TopologyPlan.objects.create(name='Sync Plan ' + suffix)
        PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu', quantity=2, server_device_type=dt)
        return plan

    def test_incomplete_state_remains_dirty_and_needs_regeneration(self):
        plan = self._plan_with_server('inc')
        saved = self._strip(build_plan_snapshot(plan))
        state = GenerationState.objects.create(
            plan=plan, device_count=1, interface_count=1, cable_count=1,
            snapshot=saved, status='generated')
        self.assertEqual(state.sync_display_state(), 'snapshot_incomplete')
        self.assertTrue(state.is_dirty())
        plan.refresh_from_db()
        self.assertTrue(plan.needs_regeneration)
        state.refresh_from_db()
        self.assertEqual(state.snapshot, saved)  # no backfill/persistence

    def test_complete_state_is_in_sync_and_clean(self):
        plan = self._plan_with_server('ok')
        state = GenerationState.objects.create(
            plan=plan, device_count=1, interface_count=1, cable_count=1,
            snapshot=build_plan_snapshot(plan), status='generated')
        self.assertEqual(state.sync_display_state(), 'in_sync')
        self.assertFalse(state.is_dirty())
