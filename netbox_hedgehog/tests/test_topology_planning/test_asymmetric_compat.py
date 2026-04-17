"""
Phase 3 RED tests — asymmetric breakout transceiver compatibility (#443).

Approved asymmetric pair:
  Switch side: R4113-A9220-VR  (OSFP, Dual MPO-12, MMF, breakout_topology='2x400g')
  Server side: QSFP112-200GBASE-SR2 (QSFP112, MPO-12, MMF) — Generic placeholder

Physical path: the 800G OSFP112 2xVR4 optic exits via a Y-splitter (external to
NetBox) producing two 400G QSFP112 legs that connect to server-side 200G QSFP112 NICs.

Registry key (6-field directional tuple):
  ('OSFP', 'Dual MPO-12', 'MMF', '2x400g', 'QSFP112', 'MPO-12')

RED state rationale:
  A  -- transceiver_compat.py does not exist yet (ImportError on every A test)
  B1 -- save-time V4 cage_type check rejects OSFP vs QSFP112 unconditionally
  C1,C2 -- sweep flags cage_type, connector, standard mismatches for approved pair
  D  -- QSFP112-200GBASE-SR2 ModuleType not seeded yet (migration 0050 pending)
  E  -- ingest fails: unknown_reference (D) and/or save-time validation (B1)

Phase 4 GREEN will: create transceiver_compat.py, patch topology_plans.py and
device_generator.py, add migration 0050, update XOC-64 case files.

MMF medium note (isolated per spec 5):
  soc_storage_server_4x200 zone previously used OSFP-200G-DR4 (SMF). The approved
  switch optic R4113-A9220-VR is MMF. Both server-side QSFP112-200GBASE-SR2 and
  switch-side VR4 are MMF, so V5 medium check will PASS for the approved pair even
  without an exemption. Medium is NOT a differentiator between the old SMF path and
  the new MMF path; the change from SMF to MMF is a data correction, not a compat rule.
"""

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from dcim.models import (
    DeviceType, InterfaceTemplate, Manufacturer,
    ModuleType, ModuleTypeProfile, Site,
)

from netbox_hedgehog.choices import (
    AllocationStrategyChoices, ConnectionDistributionChoices,
    ConnectionTypeChoices, FabricClassChoices, FabricTypeChoices,
    GenerationStatusChoices, HedgehogRoleChoices, PortZoneTypeChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption, DeviceTypeExtension, GenerationState,
    PlanServerClass, PlanServerConnection, PlanServerNIC,
    PlanSwitchClass, SwitchPortZone, TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_asym_fixtures(cls):
    """Create shared fixtures for asymmetric-compat tests."""
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name='AsymTest-Mfg', defaults={'slug': 'asymtest-mfg'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='AsymTest-SRV', defaults={'slug': 'asymtest-srv'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='AsymTest-SW', defaults={'slug': 'asymtest-sw'}
    )
    for port_n in range(1, 5):
        InterfaceTemplate.objects.get_or_create(
            device_type=cls.switch_dt, name=f'E1/{port_n}',
            defaults={'type': '400gbase-x-osfp'},
        )
    cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=cls.switch_dt,
        defaults={
            'native_speed': 800, 'uplink_ports': 0,
            'supported_breakouts': ['2x400g'], 'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    cls.breakout_2x400g, _ = BreakoutOption.objects.get_or_create(
        breakout_id='2x400g',
        defaults={
            'from_speed': 800, 'logical_ports': 2,
            'logical_speed': 400, 'optic_type': 'QSFP-DD',
        },
    )
    # 1x sweep breakout: logical_ports=1 keeps port names as E1/N (no sub-index),
    # so ModuleBayTemplates from populate_transceiver_bays match the generator's bay lookup.
    cls.breakout_1x_sweep, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x800g-sweep',
        defaults={
            'from_speed': 800, 'logical_ports': 1,
            'logical_speed': 800, 'optic_type': 'QSFP-DD',
        },
    )
    cls.site, _ = Site.objects.get_or_create(
        name='AsymTest-Site', defaults={'slug': 'asymtest-site'}
    )
    cls.nic_mt = get_test_nic_module_type()
    # Switch-side transceiver: R4113-A9220-VR
    celestica, _ = Manufacturer.objects.get_or_create(
        name='Celestica', defaults={'slug': 'celestica'}
    )
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    cls.switch_xcvr_mt, _ = ModuleType.objects.get_or_create(
        manufacturer=celestica, model='R4113-A9220-VR',
        defaults={
            'profile': profile,
            'part_number': 'R4113-A9220-VR',
            'description': '800G OSFP112 2xVR4 (2xMPO12)',
            'attribute_data': {
                'cage_type': 'OSFP',
                'medium': 'MMF',
                'connector': 'Dual MPO-12',
                'standard': '800GBASE-2xVR4',
                'reach_class': 'VR',
                'lane_count': 8,
                'optical_lane_pattern': 'VR4',
                'breakout_topology': '2x400g',
                'wavelength_nm': 850,
                'host_serdes_gbps_per_lane': 100,
                'gearbox_present': False,
                'cable_assembly_type': 'none',
            },
        },
    )


def _make_asym_plan(cls, name_suffix, server_xcvr_mt, zone_xcvr_mt, breakout_option=None):
    """Build a minimal plan with given transceiver assignments.

    breakout_option defaults to cls.breakout_2x400g.
    Use cls.breakout_1x_sweep for sweep tests: logical_ports=1 keeps port
    names as E1/N (no sub-index) so ModuleBayTemplates match the bay lookup.
    """
    plan = TopologyPlan.objects.create(
        name=f'AsymPlan-{name_suffix}-{id(cls)}',
        status=TopologyPlanStatusChoices.DRAFT,
    )
    sc = PlanServerClass.objects.create(
        plan=plan, server_class_id='soc-storage',
        server_device_type=cls.server_dt, quantity=1,
    )
    sw = PlanSwitchClass.objects.create(
        plan=plan, switch_class_id='soc-leaf',
        fabric_name=FabricTypeChoices.BACKEND,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=cls.device_ext,
        uplink_ports_per_switch=0, mclag_pair=False,
        override_quantity=2, redundancy_type='eslag',
    )
    zone_kwargs = {}
    if zone_xcvr_mt is not None:
        zone_kwargs['transceiver_module_type'] = zone_xcvr_mt
    _breakout = breakout_option if breakout_option is not None else cls.breakout_2x400g
    zone = SwitchPortZone.objects.create(
        switch_class=sw, zone_name='soc-storage-downlinks',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-4',
        breakout_option=_breakout,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        **zone_kwargs,
    )
    nic = PlanServerNIC.objects.create(
        server_class=sc, nic_id='soc-nic', module_type=cls.nic_mt,
    )
    conn_kwargs = {}
    if server_xcvr_mt is not None:
        conn_kwargs['transceiver_module_type'] = server_xcvr_mt
    conn = PlanServerConnection.objects.create(
        server_class=sc, connection_id='soc-storage',
        nic=nic, port_index=0, ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        target_zone=zone, speed=400, port_type='data',
        **conn_kwargs,
    )
    return plan, sc, sw, zone, nic, conn


def _generate(plan):
    from netbox_hedgehog.services.device_generator import DeviceGenerator
    return DeviceGenerator(plan).generate_all()


def _cleanup(plan_id):
    from dcim.models import Cable, Device
    Device.objects.filter(custom_field_data__hedgehog_plan_id=str(plan_id)).delete()
    Cable.objects.filter(custom_field_data__hedgehog_plan_id=str(plan_id)).delete()


def _delete_plan(plan):
    PlanServerConnection.objects.filter(server_class__plan=plan).delete()
    plan.delete()


# ---------------------------------------------------------------------------
# Group A: Helper unit tests for transceiver_compat module
# All RED: transceiver_compat.py does not exist yet → ImportError
# ---------------------------------------------------------------------------

class AsymmetricCompatHelperTestCase(TestCase):
    """
    A1-A10: Assert transceiver_compat module, APPROVED_ASYMMETRIC_PAIRS constant,
    and is_approved_asymmetric_pair() helper behave as specified.

    All RED until transceiver_compat.py is created in Phase 4 GREEN.
    Imports are deferred inside each test method so each test gets its own
    ImportError rather than the whole class failing at collection time.
    """

    def test_module_is_importable(self):
        """A1: netbox_hedgehog.transceiver_compat must be importable."""
        try:
            import netbox_hedgehog.transceiver_compat  # noqa: F401
        except ImportError as e:
            self.fail(f"transceiver_compat module not importable: {e}")

    def test_approved_asymmetric_pairs_constant_exists(self):
        """A2: APPROVED_ASYMMETRIC_PAIRS must be a frozenset on the module."""
        try:
            from netbox_hedgehog.transceiver_compat import APPROVED_ASYMMETRIC_PAIRS
        except ImportError as e:
            self.fail(f"transceiver_compat not importable: {e}")
        self.assertIsInstance(
            APPROVED_ASYMMETRIC_PAIRS, frozenset,
            "APPROVED_ASYMMETRIC_PAIRS must be a frozenset",
        )

    def test_approved_pair_xoc64_soc_storage_is_registered(self):
        """A3: XOC-64 soc-storage pair is in APPROVED_ASYMMETRIC_PAIRS."""
        try:
            from netbox_hedgehog.transceiver_compat import APPROVED_ASYMMETRIC_PAIRS
        except ImportError as e:
            self.fail(f"transceiver_compat not importable: {e}")
        xoc64_key = ('OSFP', 'Dual MPO-12', 'MMF', '2x400g', 'QSFP112', 'MPO-12')
        self.assertIn(
            xoc64_key, APPROVED_ASYMMETRIC_PAIRS,
            "XOC-64 soc-storage 6-field directional tuple must be in APPROVED_ASYMMETRIC_PAIRS",
        )

    def test_is_approved_asymmetric_pair_function_exists(self):
        """A4: is_approved_asymmetric_pair must be callable."""
        try:
            from netbox_hedgehog.transceiver_compat import is_approved_asymmetric_pair
        except ImportError as e:
            self.fail(f"transceiver_compat not importable: {e}")
        self.assertTrue(callable(is_approved_asymmetric_pair))

    def test_approved_pair_returns_true(self):
        """A5: is_approved_asymmetric_pair returns True for the approved XOC-64 pair."""
        try:
            from netbox_hedgehog.transceiver_compat import is_approved_asymmetric_pair
        except ImportError as e:
            self.fail(f"transceiver_compat not importable: {e}")
        result = is_approved_asymmetric_pair(
            'OSFP', 'Dual MPO-12', 'MMF', '2x400g', 'QSFP112', 'MPO-12'
        )
        self.assertTrue(result, "Approved XOC-64 pair must return True")

    def test_reversed_pair_returns_false(self):
        """A6: Rule is directional — reversed args must return False."""
        try:
            from netbox_hedgehog.transceiver_compat import is_approved_asymmetric_pair
        except ImportError as e:
            self.fail(f"transceiver_compat not importable: {e}")
        result = is_approved_asymmetric_pair(
            'QSFP112', 'MPO-12', 'MMF', '1x', 'OSFP', 'Dual MPO-12'
        )
        self.assertFalse(result, "Reversed pair must NOT be approved (rule is directional)")

    def test_none_args_return_false(self):
        """A7: All-None args must return False (guard against missing attribute_data)."""
        try:
            from netbox_hedgehog.transceiver_compat import is_approved_asymmetric_pair
        except ImportError as e:
            self.fail(f"transceiver_compat not importable: {e}")
        result = is_approved_asymmetric_pair(None, None, None, None, None, None)
        self.assertFalse(result, "All-None args must return False")

    def test_partial_none_returns_false(self):
        """A8: Partial None args must return False."""
        try:
            from netbox_hedgehog.transceiver_compat import is_approved_asymmetric_pair
        except ImportError as e:
            self.fail(f"transceiver_compat not importable: {e}")
        result = is_approved_asymmetric_pair('OSFP', None, None, None, None, None)
        self.assertFalse(result, "Partial None args must return False")

    def test_unknown_combination_returns_false(self):
        """A9: Arbitrary non-registered combination returns False."""
        try:
            from netbox_hedgehog.transceiver_compat import is_approved_asymmetric_pair
        except ImportError as e:
            self.fail(f"transceiver_compat not importable: {e}")
        result = is_approved_asymmetric_pair(
            'QSFP28', 'LC', 'SMF', '1x', 'SFP+', 'LC'
        )
        self.assertFalse(result, "Unregistered combination must return False")

    def test_approved_pairs_is_immutable(self):
        """A10: APPROVED_ASYMMETRIC_PAIRS is a frozenset (immutable by type)."""
        try:
            from netbox_hedgehog.transceiver_compat import APPROVED_ASYMMETRIC_PAIRS
        except ImportError as e:
            self.fail(f"transceiver_compat not importable: {e}")
        self.assertIsInstance(
            APPROVED_ASYMMETRIC_PAIRS, frozenset,
            "APPROVED_ASYMMETRIC_PAIRS must be a frozenset (immutable)",
        )
        with self.assertRaises(AttributeError):
            APPROVED_ASYMMETRIC_PAIRS.add(('X', 'Y', 'Z', 'W', 'A', 'B'))


# ---------------------------------------------------------------------------
# Group B: Save-time validation tests
# B1 RED: V4 cage_type check rejects OSFP vs QSFP112 unconditionally (pre-GREEN)
# B2-B6 GREEN: regression guards that must remain passing after Phase 4
# ---------------------------------------------------------------------------

class AsymmetricSaveTimeValidationTestCase(TestCase):
    """
    B1-B6: Verify save-time _validate_transceiver_module_type() behavior for
    the approved asymmetric pair and for regression cases.
    """

    @classmethod
    def setUpTestData(cls):
        _make_asym_fixtures(cls)
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        # Inline server-side QSFP112 test MT (model distinct from D-group seed tests)
        generic, _ = Manufacturer.objects.get_or_create(
            name='Generic', defaults={'slug': 'generic'}
        )
        cls.server_xcvr_inline, _ = ModuleType.objects.get_or_create(
            manufacturer=generic, model='QSFP112-200GBASE-SR2-INLINE-TEST',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112',
                    'medium': 'MMF',
                    'connector': 'MPO-12',
                    'standard': '200GBASE-SR2',
                    'reach_class': 'SR',
                    'breakout_topology': '1x',
                },
            },
        )
        # Symmetric QSFP112 pair (both ends same) — for B2 regression
        cls.qsfp112_sym_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=generic, model='QSFP112-SYM-TEST',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112',
                    'medium': 'MMF',
                    'connector': 'MPO-12',
                    'standard': '200GBASE-SR2',
                    'reach_class': 'SR',
                },
            },
        )
        # SFP+ MT for B3 mismatch test
        cls.sfp_plus_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=generic, model='SFP-PLUS-TEST',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'SFP+',
                    'medium': 'MMF',
                    'connector': 'LC',
                    'standard': '10GBASE-SR',
                    'reach_class': 'SR',
                },
            },
        )
        # SMF variant for B4 medium mismatch
        cls.qsfp112_smf_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=generic, model='QSFP112-SMF-TEST',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112',
                    'medium': 'SMF',
                    'connector': 'MPO-12',
                    'standard': '200GBASE-DR4',
                    'reach_class': 'DR',
                },
            },
        )
        # QSFP28 LC MT for B5 connector mismatch
        cls.qsfp28_lc_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=generic, model='QSFP28-LC-TEST',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP28',
                    'medium': 'SMF',
                    'connector': 'LC',
                    'standard': '100GBASE-LR4',
                    'reach_class': 'LR',
                },
            },
        )
        cls.qsfp28_mpo_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=generic, model='QSFP28-MPO-TEST',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP28',
                    'medium': 'MMF',
                    'connector': 'MPO-12',
                    'standard': '100GBASE-SR4',
                    'reach_class': 'SR',
                },
            },
        )

    def _make_conn_with_xcvr(self, server_xcvr, zone_xcvr):
        """Create a minimal unsaved PlanServerConnection for full_clean testing."""
        plan = TopologyPlan.objects.create(
            name=f'BValidTest-{id(self)}',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu',
            server_device_type=self.server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.BACKEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        zone_kwargs = {}
        if zone_xcvr is not None:
            zone_kwargs['transceiver_module_type'] = zone_xcvr
        zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='b-test-zone',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-4',
            breakout_option=self.breakout_2x400g,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            **zone_kwargs,
        )
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id='b-nic', module_type=self.nic_mt,
        )
        conn_kwargs = {}
        if server_xcvr is not None:
            conn_kwargs['transceiver_module_type'] = server_xcvr
        conn = PlanServerConnection(
            server_class=sc, connection_id='b-conn',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=400, port_type='data',
            **conn_kwargs,
        )
        return conn, plan

    def tearDown(self):
        TopologyPlan.objects.filter(name__startswith='BValidTest-').delete()

    def test_approved_pair_passes_save_time_validation(self):
        """
        B1 RED: Approved pair (server=QSFP112, zone=OSFP/Dual-MPO-12) must pass
        full_clean() after Phase 4 adds the approved-pair gate.

        Currently RED: V4 cage_type check raises unconditionally when
        srv_cage (QSFP112) != zone_cage (OSFP). No approved-pair gate exists yet.
        """
        conn, plan = self._make_conn_with_xcvr(
            server_xcvr=self.server_xcvr_inline,
            zone_xcvr=self.switch_xcvr_mt,
        )
        try:
            conn.full_clean()
        except ValidationError as e:
            self.fail(
                f"Approved asymmetric pair must NOT raise ValidationError. "
                f"Currently blocked by: {e.message_dict}"
            )

    def test_symmetric_qsfp112_pair_passes_validation(self):
        """B2 GREEN: Symmetric QSFP112/MPO-12/MMF on both ends passes full_clean()."""
        conn, plan = self._make_conn_with_xcvr(
            server_xcvr=self.qsfp112_sym_mt,
            zone_xcvr=self.qsfp112_sym_mt,
        )
        try:
            conn.full_clean()
        except ValidationError as e:
            self.fail(f"Symmetric QSFP112 pair must pass: {e.message_dict}")

    def test_mismatched_cage_type_still_rejected(self):
        """B3 GREEN: Non-approved cage mismatch (SFP+ vs QSFP112) must still raise."""
        conn, plan = self._make_conn_with_xcvr(
            server_xcvr=self.sfp_plus_mt,
            zone_xcvr=self.qsfp112_sym_mt,
        )
        with self.assertRaises(ValidationError, msg="Non-approved cage mismatch must raise ValidationError"):
            conn.full_clean()

    def test_mismatched_medium_still_rejected(self):
        """B4 GREEN: Same cage different medium (MMF vs SMF QSFP112) must raise."""
        conn, plan = self._make_conn_with_xcvr(
            server_xcvr=self.qsfp112_sym_mt,   # MMF
            zone_xcvr=self.qsfp112_smf_mt,     # SMF
        )
        with self.assertRaises(ValidationError, msg="Medium mismatch must raise ValidationError"):
            conn.full_clean()

    def test_mismatched_connector_still_rejected(self):
        """B5 GREEN: Non-approved connector mismatch (LC vs MPO-12, both QSFP28) must raise."""
        conn, plan = self._make_conn_with_xcvr(
            server_xcvr=self.qsfp28_lc_mt,    # LC
            zone_xcvr=self.qsfp28_mpo_mt,     # MPO-12
        )
        with self.assertRaises(ValidationError, msg="Non-approved connector mismatch must raise ValidationError"):
            conn.full_clean()

    def test_no_transceiver_fks_passes_validation(self):
        """DIET-466: Both null → full_clean() raises ValidationError (transceiver required)."""
        conn, plan = self._make_conn_with_xcvr(
            server_xcvr=None,
            zone_xcvr=None,
        )
        with self.assertRaises(ValidationError) as ctx:
            conn.full_clean()
        # Must be the transceiver_module_type field that triggered the error
        self.assertIn('transceiver_module_type', ctx.exception.message_dict)


# ---------------------------------------------------------------------------
# Group C: Sweep tests
# C1,C2 RED: sweep currently produces mismatches for the approved pair
# C3,C4 GREEN: non-approved pairs still produce structured mismatch entries
# ---------------------------------------------------------------------------

class AsymmetricCompatSweepTestCase(TestCase):
    """
    C1-C4: Verify _run_compatibility_sweep() behavior for approved and
    non-approved asymmetric pairs.
    """

    @classmethod
    def setUpTestData(cls):
        _make_asym_fixtures(cls)
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        generic, _ = Manufacturer.objects.get_or_create(
            name='Generic', defaults={'slug': 'generic'}
        )
        # Server-side inline QSFP112 for the approved pair
        cls.server_xcvr_inline, _ = ModuleType.objects.get_or_create(
            manufacturer=generic, model='QSFP112-200GBASE-SR2-SWEEP-TEST',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112',
                    'medium': 'MMF',
                    'connector': 'MPO-12',
                    'standard': '200GBASE-SR2',
                    'reach_class': 'SR',
                    'breakout_topology': '1x',
                },
            },
        )
        # Non-approved mismatch pair: QSFP28 vs QSFP-DD
        cls.qsfp28_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=generic, model='QSFP28-SWEEP-TEST',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP28',
                    'medium': 'MMF',
                    'connector': 'MPO-12',
                    'standard': '100GBASE-SR4',
                    'reach_class': 'SR',
                },
            },
        )
        cls.qsfp_dd_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=generic, model='QSFP-DD-SWEEP-TEST',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP-DD',
                    'medium': 'MMF',
                    'connector': 'MPO-12',
                    'standard': '400GBASE-SR4',
                    'reach_class': 'SR',
                },
            },
        )

    def tearDown(self):
        for p in list(TopologyPlan.objects.filter(name__startswith='AsymPlan-')):
            _cleanup(p.pk)
            _delete_plan(p)

    def test_approved_pair_sweep_does_not_produce_mismatch(self):
        """
        C1 RED: After Phase 4, approved pair must not appear in mismatch_report.

        Currently RED: sweep checks all _SWEEP_DIMS including cage_type, connector,
        and standard, which all differ between OSFP/Dual-MPO-12/800GBASE-2xVR4 and
        QSFP112/MPO-12/200GBASE-SR2. Sweep currently produces mismatches and sets
        status=FAILED for this approved pair.
        """
        plan, sc, sw, zone, nic, conn = _make_asym_plan(
            self, 'C1',
            server_xcvr_mt=self.server_xcvr_inline,
            zone_xcvr_mt=self.switch_xcvr_mt,
            breakout_option=self.breakout_1x_sweep,
        )
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs, "GenerationState must exist after generation")
        self.assertEqual(
            gs.status, GenerationStatusChoices.GENERATED,
            "Approved asymmetric pair must result in GENERATED status after Phase 4",
        )
        self.assertIsNone(
            gs.mismatch_report,
            "mismatch_report must be null for approved asymmetric pair",
        )

    def test_approved_pair_generation_succeeds_not_failed(self):
        """
        C2 RED: Approved pair must not result in FAILED generation status.

        Currently RED for same reason as C1.
        """
        plan, sc, sw, zone, nic, conn = _make_asym_plan(
            self, 'C2',
            server_xcvr_mt=self.server_xcvr_inline,
            zone_xcvr_mt=self.switch_xcvr_mt,
            breakout_option=self.breakout_1x_sweep,
        )
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertNotEqual(
            gs.status, GenerationStatusChoices.FAILED,
            "Approved asymmetric pair must NOT produce FAILED generation status",
        )

    def test_non_approved_asymmetric_pair_produces_mismatch_entries(self):
        """
        C3 GREEN: Non-approved cage mismatch (QSFP28 server vs QSFP-DD zone) must
        produce structured mismatch entries in mismatch_report.

        This verifies the sweep still catches genuinely incompatible pairs after
        Phase 4 adds the approved-pair gate.
        """
        plan, sc, sw, zone, nic, conn = _make_asym_plan(
            self, 'C3',
            server_xcvr_mt=self.qsfp28_mt,
            zone_xcvr_mt=self.qsfp_dd_mt,
            breakout_option=self.breakout_1x_sweep,
        )
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(
            gs.status, GenerationStatusChoices.FAILED,
            "Non-approved cage mismatch must produce FAILED status",
        )
        report = getattr(gs, 'mismatch_report', None)
        self.assertIsNotNone(report, "mismatch_report must be populated for non-approved pair")
        mismatches = report.get('mismatches', [])
        self.assertGreater(len(mismatches), 0, "mismatches list must be non-empty")
        entry = mismatches[0]
        self.assertIn('mismatch_type', entry, "Entry must have mismatch_type")
        self.assertIn('server_end', entry, "Entry must have server_end")
        self.assertIn('switch_end', entry, "Entry must have switch_end")

    def test_non_approved_sweep_entry_has_required_keys(self):
        """
        C4 GREEN: Mismatch entry dict structure is stable — all 6 required keys present.

        Regression guard: the dict schema must not change between Stage 2 and
        the asymmetric-compat Phase 4 patch.
        """
        plan, sc, sw, zone, nic, conn = _make_asym_plan(
            self, 'C4',
            server_xcvr_mt=self.qsfp28_mt,
            zone_xcvr_mt=self.qsfp_dd_mt,
            breakout_option=self.breakout_1x_sweep,
        )
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        report = getattr(gs, 'mismatch_report', None)
        self.assertIsNotNone(report)
        mismatches = report.get('mismatches', [])
        self.assertGreater(len(mismatches), 0)
        entry = mismatches[0]
        required_keys = {'connection_id', 'server_device', 'switch_port',
                         'mismatch_type', 'server_end', 'switch_end'}
        for key in required_keys:
            self.assertIn(key, entry, f"Mismatch entry must contain key '{key}'")


# ---------------------------------------------------------------------------
# Group D: Seed existence tests
# All RED: QSFP112-200GBASE-SR2 not seeded yet (migration 0050 pending)
# ---------------------------------------------------------------------------

class QSFP112SR2SeedTestCase(TestCase):
    """
    D1-D6: Verify QSFP112-200GBASE-SR2 placeholder ModuleType is seeded correctly.

    All RED until migration 0050 runs. These tests check the DB directly; they
    do not create any fixtures. The placeholder naming rule (Generic manufacturer,
    spec-descriptor model, description with 'placeholder' and 'replace') is
    asserted explicitly so the intent is machine-verifiable.
    """

    def _get_mt(self):
        return ModuleType.objects.filter(model='QSFP112-200GBASE-SR2').first()

    def test_qsfp112_200gbase_sr2_exists(self):
        """D1: QSFP112-200GBASE-SR2 ModuleType must exist after migration 0050."""
        mt = self._get_mt()
        self.assertIsNotNone(
            mt,
            "QSFP112-200GBASE-SR2 must be seeded by migration 0050",
        )

    def test_qsfp112_200gbase_sr2_manufacturer_is_generic(self):
        """D2: Manufacturer must be 'Generic' — placeholder rule."""
        mt = self._get_mt()
        self.assertIsNotNone(mt, "QSFP112-200GBASE-SR2 must be seeded first (D1)")
        self.assertEqual(
            mt.manufacturer.name, 'Generic',
            "QSFP112-200GBASE-SR2 manufacturer must be 'Generic' per placeholder naming rule",
        )

    def test_qsfp112_200gbase_sr2_description_identifies_as_placeholder(self):
        """D3: Description must contain 'placeholder' and 'replace' per naming rule."""
        mt = self._get_mt()
        self.assertIsNotNone(mt, "QSFP112-200GBASE-SR2 must be seeded first (D1)")
        desc = (mt.description or '').lower()
        self.assertIn(
            'placeholder', desc,
            "Description must include 'placeholder' to identify this as a generic stand-in",
        )
        self.assertIn(
            'replace', desc,
            "Description must include 'replace' to instruct operators to substitute a vendor SKU",
        )

    def test_qsfp112_200gbase_sr2_has_network_transceiver_profile(self):
        """D4: ModuleType must have the 'Network Transceiver' profile."""
        mt = self._get_mt()
        self.assertIsNotNone(mt, "QSFP112-200GBASE-SR2 must be seeded first (D1)")
        self.assertIsNotNone(mt.profile, "QSFP112-200GBASE-SR2 must have a profile")
        self.assertEqual(mt.profile.name, 'Network Transceiver')

    def test_qsfp112_200gbase_sr2_attribute_data(self):
        """D5: attribute_data must match spec: QSFP112, MMF, MPO-12, SR2, SR, 1x."""
        mt = self._get_mt()
        self.assertIsNotNone(mt, "QSFP112-200GBASE-SR2 must be seeded first (D1)")
        data = mt.attribute_data or {}
        self.assertEqual(data.get('cage_type'), 'QSFP112')
        self.assertEqual(data.get('medium'), 'MMF')
        self.assertEqual(data.get('connector'), 'MPO-12')
        self.assertEqual(data.get('standard'), '200GBASE-SR2')
        self.assertEqual(data.get('reach_class'), 'SR')
        self.assertEqual(data.get('breakout_topology'), '1x')

    def test_qsfp112_200gbase_sr2_has_no_interface_templates(self):
        """D6: Transceiver ModuleType must have zero InterfaceTemplates."""
        mt = self._get_mt()
        self.assertIsNotNone(mt, "QSFP112-200GBASE-SR2 must be seeded first (D1)")
        self.assertEqual(
            mt.interfacetemplates.count(), 0,
            "Transceiver ModuleType must not have InterfaceTemplates (optic, not NIC)",
        )


# ---------------------------------------------------------------------------
# Group E: Ingest RED tests
# All RED: (a) QSFP112-200GBASE-SR2 not in DB → unknown_reference, or
#          (b) save-time validation rejects the pair even if MT exists
# ---------------------------------------------------------------------------

class AsymmetricIngestTestCase(TestCase):
    """
    E1-E2: Verify that the approved asymmetric pair can be ingested via apply_case.

    E1 RED: ingest fails because QSFP112-200GBASE-SR2 is not seeded (migration 0050
    pending) and/or save-time validation blocks the pair (V4 cage_type check).

    E2 RED: even when the Generic QSFP112 MT is pre-created manually, save-time
    validation still rejects the pair (V4 cage_type OSFP != QSFP112).
    """

    @classmethod
    def setUpTestData(cls):
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        # Pre-create the Celestica VR4 optic used as the switch-side zone transceiver
        celestica, _ = Manufacturer.objects.get_or_create(
            name='Celestica', defaults={'slug': 'celestica'}
        )
        cls.switch_xcvr_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=celestica, model='R4113-A9220-VR',
            defaults={
                'profile': profile,
                'part_number': 'R4113-A9220-VR',
                'description': '800G OSFP112 2xVR4 (2xMPO12)',
                'attribute_data': {
                    'cage_type': 'OSFP',
                    'medium': 'MMF',
                    'connector': 'Dual MPO-12',
                    'standard': '800GBASE-2xVR4',
                    'reach_class': 'VR',
                    'lane_count': 8,
                    'breakout_topology': '2x400g',
                    'wavelength_nm': 850,
                    'host_serdes_gbps_per_lane': 100,
                    'gearbox_present': False,
                    'cable_assembly_type': 'none',
                },
            },
        )
        # Pre-create the NIC module type with an interface template so full_clean passes.
        # full_clean() validates that the NIC's module_type has interface templates.
        ai_mfr, _ = Manufacturer.objects.get_or_create(
            name='AsymIngest-Mfg', defaults={'slug': 'asymingest-mfg'}
        )
        cls.nic_mt, created = ModuleType.objects.get_or_create(
            manufacturer=ai_mfr, model='AsymIngest-NIC',
        )
        if created or not cls.nic_mt.interfacetemplates.exists():
            InterfaceTemplate.objects.get_or_create(
                module_type=cls.nic_mt, name='p0',
                defaults={'type': '400gbase-x-osfp'},
            )

    def _base_case(self, case_id):
        """Minimal case dict with asymmetric transceiver assignments."""
        return {
            "meta": {
                "case_id": case_id,
                "name": f"Asymmetric Ingest Test {case_id}",
                "version": 1,
                "managed_by": "yaml",
            },
            "plan": {
                "name": f"AsymIngestPlan {case_id}",
                "status": "draft",
            },
            "reference_data": {
                "manufacturers": [
                    {"id": "mfr_celestica", "name": "Celestica", "slug": "celestica"},
                    {"id": "mfr_generic", "name": "Generic", "slug": "generic"},
                    {"id": "mfr_test", "name": "AsymIngest-Mfg", "slug": "asymingest-mfg"},
                ],
                "device_types": [
                    {
                        "id": "dt_sw",
                        "manufacturer": "mfr_test",
                        "model": "AsymIngest-SW",
                        "slug": "asymingest-sw",
                    },
                    {
                        "id": "dt_srv",
                        "manufacturer": "mfr_test",
                        "model": "AsymIngest-SRV",
                        "slug": "asymingest-srv",
                    },
                ],
                "device_type_extensions": [
                    {
                        "id": "dte_sw",
                        "device_type": "dt_sw",
                        "hedgehog_roles": ["server-leaf"],
                        "native_speed": 800,
                        "uplink_ports": 0,
                        "supported_breakouts": ["2x400g"],
                        "mclag_capable": False,
                    },
                ],
                "module_types": [
                    {
                        "id": "r4113_a9220_vr",
                        "manufacturer": "mfr_celestica",
                        "model": "R4113-A9220-VR",
                    },
                    {
                        "id": "qsfp112_sr2",
                        "manufacturer": "mfr_generic",
                        "model": "QSFP112-200GBASE-SR2",
                    },
                    {
                        "id": "nic_test",
                        "manufacturer": "mfr_test",
                        "model": "AsymIngest-NIC",
                    },
                ],
                "breakout_options": [
                    {
                        "id": "bo_2x400g",
                        "breakout_id": "2x400g",
                        "from_speed": 800,
                        "logical_ports": 2,
                        "logical_speed": 400,
                    },
                ],
            },
            "switch_classes": [
                {
                    "switch_class_id": "soc-leaf",
                    "fabric": "backend",
                    "hedgehog_role": "server-leaf",
                    "device_type_extension": "dte_sw",
                },
            ],
            "switch_port_zones": [
                {
                    "switch_class": "soc-leaf",
                    "zone_name": "soc-storage-downlinks",
                    "zone_type": "server",
                    "port_spec": "1-4",
                    "breakout_option": "bo_2x400g",
                    "allocation_strategy": "sequential",
                    "priority": 100,
                    "transceiver_module_type": "r4113_a9220_vr",
                },
            ],
            "server_classes": [
                {
                    "server_class_id": "soc-storage",
                    "server_device_type": "dt_srv",
                    "quantity": 1,
                    "gpus_per_server": 0,
                },
            ],
            "server_nics": [
                {
                    "server_class": "soc-storage",
                    "nic_id": "soc-nic",
                    "module_type": "nic_test",
                },
            ],
            "server_connections": [
                {
                    "server_class": "soc-storage",
                    "connection_id": "soc-storage-conn",
                    "connection_name": "soc storage",
                    "nic": "soc-nic",
                    "port_index": 0,
                    "ports_per_connection": 1,
                    "hedgehog_conn_type": "unbundled",
                    "distribution": "alternating",
                    "target_zone": "soc-leaf/soc-storage-downlinks",
                    "speed": 400,
                    "transceiver_module_type": "qsfp112_sr2",
                },
            ],
        }

    def test_approved_asymmetric_pair_ingests_without_error(self):
        """
        E1 RED: Ingesting a case with the approved asymmetric pair must succeed.

        Currently RED because:
        (a) QSFP112-200GBASE-SR2 is not in the DB (migration 0050 pending) →
            apply_case raises TestCaseValidationError(unknown_reference), or
        (b) if (a) is bypassed, save-time validation rejects cage_type mismatch.

        After Phase 4 GREEN: migration 0050 seeds the MT and topology_plans.py
        has the approved-pair gate, so apply_case must succeed without error.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case
        case = self._base_case("e1_full_ingest")
        try:
            apply_case(case, clean=True, reference_mode="ensure")
        except Exception as e:
            self.fail(
                f"Approved asymmetric pair must ingest without error. "
                f"Currently blocked by: {type(e).__name__}: {e}"
            )

    def test_ingest_succeeds_with_preexisting_seeded_mt(self):
        """
        E2 GREEN: When QSFP112-200GBASE-SR2 is explicitly present in the DB,
        apply_case succeeds for the approved asymmetric pair.

        This is a complementary regression guard to E1: E1 tests the normal path
        (migration 0050 seeds the MT); E2 tests that the same ingest also works when
        the MT is obtained via other seeding paths (e.g. load_diet_reference_data).

        Originally written as a RED test in Phase 3 to isolate the save-time V4
        cage_type validation as the specific blocker. After Phase 4 GREEN, the
        approved-pair gate in _validate_transceiver_module_type() removes that blocker,
        and this test correctly flips to GREEN.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        # Explicitly confirm QSFP112-200GBASE-SR2 is present (seeded by migration 0050)
        generic, _ = Manufacturer.objects.get_or_create(
            name='Generic', defaults={'slug': 'generic'}
        )
        self.assertTrue(
            ModuleType.objects.filter(
                manufacturer=generic, model='QSFP112-200GBASE-SR2'
            ).exists(),
            "QSFP112-200GBASE-SR2 must be present (migration 0050) for this test",
        )
        case = self._base_case("e2_seeded_regression")
        try:
            apply_case(case, clean=True, reference_mode="ensure")
        except Exception as e:
            self.fail(
                f"Ingest must succeed when QSFP112-200GBASE-SR2 is pre-seeded. "
                f"Got: {type(e).__name__}: {e}"
            )
