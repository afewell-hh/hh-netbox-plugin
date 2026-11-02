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

    @staticmethod
    def _switch(sid='leaf', **extra):
        data = dict(
            switch_class_id=sid, effective_quantity=2, device_type_extension_id=1,
            fabric='frontend', fabric_name='frontend', fabric_class='managed',
            hedgehog_role='server-leaf', uplink_ports_per_switch=None,
            mclag_pair=False, topology_mode='spine-leaf',
        )
        data.update(extra)
        return data

    @staticmethod
    def _conn(cid='c1', **extra):
        data = dict(
            connection_id=cid, server_class_id='gpu', target_zone_id='leaf:z1',
            ports_per_connection=1, hedgehog_conn_type='unbundled',
            distribution='alternating', speed=200, rail=None, port_type='data',
        )
        data.update(extra)
        return data

    @staticmethod
    def _zone(name='z1', switch='leaf', **extra):
        data = dict(
            switch_class_id=switch, zone_name=name, zone_type='server',
            port_spec='1-32', breakout_option_id=None,
            allocation_strategy='sequential', allocation_order=None, priority=100,
        )
        data.update(extra)
        return data

    @staticmethod
    def _mclag(did='m1', **extra):
        data = dict(
            domain_id=did, switch_class_id='leaf',
            peer_link_count=2, session_link_count=2,
        )
        data.update(extra)
        return data

    def _snap(self, servers=None, **overrides):
        snap = dict(
            server_classes=servers if servers is not None else [self._server('gpu')],
            switch_classes=[self._switch()],
            connections=[self._conn()],
            port_zones=[self._zone()],
            mclag_domains=[self._mclag()],
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

    def test_missing_current_historical_fields_are_incomplete(self):
        import copy
        for key in self.HISTORICAL:
            incomplete = self._snap()
            del incomplete['server_classes'][0][key]
            with self.subTest(key=key, side='current'):
                self.assertEqual(
                    self.classify(incomplete, self._snap()), 'snapshot_incomplete')
            with self.subTest(key=key, side='both'):
                self.assertEqual(
                    self.classify(incomplete, copy.deepcopy(incomplete)),
                    'snapshot_incomplete')

    def test_mclag_shared_domain_id_with_distinct_switches(self):
        import copy
        saved = self._snap(
            switch_classes=[self._switch(), self._switch(sid='leaf2')],
            mclag_domains=[self._mclag(), self._mclag(switch_class_id='leaf2')])
        current = copy.deepcopy(saved)
        self.assertEqual(self.classify(current, saved), 'in_sync')
        current['mclag_domains'][1]['peer_link_count'] += 1
        self.assertEqual(self.classify(current, saved), 'changed')
        current = copy.deepcopy(saved)
        current['server_classes'][0]['quantity'] += 1
        self.assertEqual(self.classify(current, saved), 'changed')

    def test_known_changes_alongside_missing_keys_are_changed(self):
        stripped = self._strip(self._snap())
        cases = dict(
            quantity=self._snap(servers=[self._server('gpu', qty=4)]),
            connection=self._snap(connections=[self._conn(speed=400)]),
            zone=self._snap(port_zones=[self._zone(allocation_order=3)]),
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

    # (section, record builder name) -> (required keys, identity builder kwargs)
    NONSERVER_REQUIRED = {
        'switch_classes': ('_switch', (
            'switch_class_id', 'effective_quantity', 'device_type_extension_id',
            'fabric', 'fabric_name', 'fabric_class', 'hedgehog_role',
            'uplink_ports_per_switch', 'mclag_pair', 'topology_mode')),
        'connections': ('_conn', (
            'connection_id', 'server_class_id', 'target_zone_id',
            'ports_per_connection', 'hedgehog_conn_type', 'distribution',
            'speed', 'rail', 'port_type')),
        'port_zones': ('_zone', (
            'switch_class_id', 'zone_name', 'zone_type', 'port_spec',
            'breakout_option_id', 'allocation_strategy', 'allocation_order',
            'priority')),
        'mclag_domains': ('_mclag', (
            'domain_id', 'switch_class_id', 'peer_link_count',
            'session_link_count')),
    }

    def _missing_field_snaps(self):
        """Yield (name, snapshot) with exactly one required field omitted."""
        import copy
        for section, (_builder, keys) in self.NONSERVER_REQUIRED.items():
            for key in keys:
                snap = self._snap()
                del snap[section][0][key]
                yield '%s.%s' % (section, key), snap
        for key in ('server_class_id', 'quantity', 'device_type_id', 'gpus_per_server'):
            snap = self._snap()
            del snap['server_classes'][0][key]
            yield 'server_classes.%s' % key, snap

    def test_every_missing_required_field_in_every_section_is_incomplete(self):
        import copy
        current = self._snap()
        for name, snap in self._missing_field_snaps():
            with self.subTest(name=name, role='saved'):
                self.assertEqual(self.classify(current, snap), 'snapshot_incomplete')
            with self.subTest(name=name, role='equal-malformed'):
                self.assertEqual(
                    self.classify(copy.deepcopy(snap), copy.deepcopy(snap)),
                    'snapshot_incomplete')
            with self.subTest(name=name, role='saved-and-historical-keys-omitted'):
                self.assertEqual(
                    self.classify(current, self._strip(snap)), 'snapshot_incomplete')

    def test_duplicate_identities_in_every_section_are_incomplete(self):
        import copy
        current = self._snap()
        cases = dict(
            servers=self._snap(servers=[self._server('gpu'), self._server('gpu')]),
            switches=self._snap(switch_classes=[self._switch(), self._switch()]),
            connections=self._snap(connections=[self._conn(), self._conn()]),
            zones=self._snap(port_zones=[self._zone(), self._zone()]),
            mclag=self._snap(mclag_domains=[self._mclag(), self._mclag()]),
        )
        for name, snap in cases.items():
            with self.subTest(name=name, role='saved'):
                self.assertEqual(self.classify(current, snap), 'snapshot_incomplete')
            with self.subTest(name=name, role='equal-duplicate'):
                self.assertEqual(
                    self.classify(copy.deepcopy(snap), copy.deepcopy(snap)),
                    'snapshot_incomplete')

    def test_non_string_or_empty_identities_in_every_section_are_incomplete(self):
        current = self._snap()
        cases = dict(
            switch_none=self._snap(switch_classes=[self._switch(sid=None)]),
            conn_empty=self._snap(connections=[self._conn(cid='')]),
            zone_none=self._snap(port_zones=[self._zone(name=None)]),
            mclag_int=self._snap(mclag_domains=[self._mclag(did=7)]),
        )
        for name, snap in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.classify(current, snap), 'snapshot_incomplete')

    def test_same_connection_id_on_different_server_classes_is_not_duplicate(self):
        # PlanServerConnection.Meta.unique_together is [server_class, connection_id]
        snap = self._snap(
            servers=[self._server('gpu'), self._server('storage')],
            connections=[
                self._conn(cid='FE-001'),
                self._conn(cid='FE-001', server_class_id='storage'),
            ],
        )
        self.assertEqual(self.classify(snap, snap), 'in_sync')

    def test_duplicate_composite_connection_identity_is_incomplete(self):
        import copy
        servers = [self._server('gpu'), self._server('storage')]
        snap = self._snap(
            servers=servers,
            connections=[
                self._conn(cid='FE-001', server_class_id='storage'),
                self._conn(cid='FE-001', server_class_id='storage'),
            ],
        )
        current = self._snap(servers=servers)
        self.assertEqual(self.classify(current, snap), 'snapshot_incomplete')
        self.assertEqual(
            self.classify(copy.deepcopy(snap), copy.deepcopy(snap)),
            'snapshot_incomplete')

    def test_same_zone_name_on_different_switches_is_not_duplicate(self):
        snap = self._snap(port_zones=[self._zone(), self._zone(switch='leaf2')])
        self.assertEqual(self.classify(snap, snap), 'in_sync')

    def test_complete_valid_nonserver_value_changes_remain_changed(self):
        saved = self._snap()
        cases = dict(
            switch_qty=self._snap(switch_classes=[self._switch(effective_quantity=4)]),
            switch_added=self._snap(switch_classes=[self._switch(), self._switch('spine')]),
            conn_speed=self._snap(connections=[self._conn(speed=800)]),
            conn_removed=self._snap(connections=[]),
            zone_spec=self._snap(port_zones=[self._zone(port_spec='1-16')]),
            mclag_links=self._snap(mclag_domains=[self._mclag(peer_link_count=4)]),
        )
        for name, current in cases.items():
            with self.subTest(name=name, saved='complete'):
                self.assertEqual(self.classify(current, saved), 'changed')
            with self.subTest(name=name, saved='historical-keys-omitted'):
                self.assertEqual(self.classify(current, self._strip(saved)), 'changed')

    def test_complete_equal_with_all_sections_is_in_sync(self):
        import copy
        snap = self._snap()
        self.assertEqual(self.classify(snap, copy.deepcopy(snap)), 'in_sync')

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
