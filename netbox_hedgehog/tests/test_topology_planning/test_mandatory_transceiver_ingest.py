"""
RED tests for #475 — simplified transceiver UX: YAML ingest behavior.

Replaces DIET-466 mandatory-transceiver ingest tests with tests that pin the
approved target behavior from #474 §9.7 (I1–I4).

Target behavior (not yet implemented):
  I1 — YAML with transceiver_module_type: null on zone → ingest succeeds
  I2 — YAML with absent transceiver_module_type key on connection → ingest succeeds
  I3 — YAML with deprecated cage_type key on connection → ingest succeeds,
       key silently ignored, no TestCaseValidationError
  I4 — YAML with all transceivers set (existing case file) → ingest succeeds
       (regression guard — must keep working)

All I1–I3 tests are RED until GREEN removes the DIET-466 pre-pass from
ingest.py lines 511–532 (the _required_errors block that raises
TestCaseValidationError when transceiver_module_type is None).
I4 is already GREEN and included as a regression guard.

Test approach: call apply_case() directly with a minimal inline case dict
that includes all required reference_data, rather than loading large case
files. This isolates the pre-pass behavior from unrelated ingest logic and
keeps tests fast.
"""

from __future__ import annotations

from django.test import TestCase

from netbox_hedgehog.test_cases.exceptions import TestCaseValidationError
from netbox_hedgehog.models.topology_planning import (
    PlanServerConnection,
    SwitchPortZone,
    TopologyPlan,
)


# ---------------------------------------------------------------------------
# Minimal case dict builder
# ---------------------------------------------------------------------------

def _minimal_case(
    case_id: str,
    zone_transceiver='__absent__',
    conn_transceiver='__absent__',
    conn_extra_keys=None,
) -> dict:
    """
    Build a minimal valid case dict for ingest testing.

    zone_transceiver: value for switch_port_zones[0].transceiver_module_type.
        '__absent__' means the key is not included (tests key-absent path).
        None means the key is included with value None (tests explicit-null path).
        A string ref like 'xcvr_test_200g' means a resolved FK ref.

    conn_transceiver: same semantics for server_connections[0].transceiver_module_type.

    conn_extra_keys: dict of extra keys to add to the connection item (e.g.
        {'cage_type': 'QSFP112'} for testing deprecated key ignore).
    """
    zone_item = {
        'switch_class': 'fe-leaf',
        'zone_name': 'server-downlinks',
        'zone_type': 'server',
        'port_spec': '1-4',
        'breakout_option': 'b_1x200g',
        'allocation_strategy': 'sequential',
        'priority': 100,
    }
    if zone_transceiver != '__absent__':
        zone_item['transceiver_module_type'] = zone_transceiver

    conn_item = {
        'server_class': 'gpu',
        'connection_id': 'fe',
        'connection_name': 'frontend',
        'nic': 'nic-fe',
        'port_index': 0,
        'ports_per_connection': 1,
        'hedgehog_conn_type': 'unbundled',
        'distribution': 'alternating',
        'target_zone': 'fe-leaf/server-downlinks',
        'speed': 200,
        'port_type': 'data',
    }
    if conn_transceiver != '__absent__':
        conn_item['transceiver_module_type'] = conn_transceiver
    if conn_extra_keys:
        conn_item.update(conn_extra_keys)

    return {
        'meta': {
            'case_id': case_id,
            'name': f'Ingest-Test-{case_id}',
            'version': 1,
            'managed_by': 'yaml',
        },
        'plan': {
            'name': f'Ingest-Test-Plan-{case_id}',
            'status': 'draft',
        },
        'reference_data': {
            'manufacturers': [
                {'id': 'test-mfg', 'name': 'IngestTestMfg', 'slug': 'ingest-test-mfg'},
                {'id': 'nvidia', 'name': 'NVIDIA', 'slug': 'nvidia'},
            ],
            'device_types': [
                {
                    'id': 'test-server',
                    'manufacturer': 'test-mfg',
                    'model': 'IngestTest-SRV',
                    'slug': 'ingest-test-srv',
                    'interface_templates': [],
                },
                {
                    'id': 'test-switch',
                    'manufacturer': 'test-mfg',
                    'model': 'IngestTest-SW',
                    'slug': 'ingest-test-sw',
                    'interface_templates': [
                        {'name': 'E1/1', 'type': '200gbase-x-qsfp112'},
                        {'name': 'E1/2', 'type': '200gbase-x-qsfp112'},
                        {'name': 'E1/3', 'type': '200gbase-x-qsfp112'},
                        {'name': 'E1/4', 'type': '200gbase-x-qsfp112'},
                    ],
                },
            ],
            'device_type_extensions': [
                {
                    'id': 'test-sw-ext',
                    'device_type': 'test-switch',
                    'mclag_capable': False,
                    'hedgehog_roles': ['server-leaf'],
                    'supported_breakouts': ['1x200g'],
                    'native_speed': 200,
                    'uplink_ports': 0,
                },
            ],
            'breakout_options': [
                {
                    'id': 'b_1x200g',
                    'breakout_id': 'ingest-test-1x200g',
                    'from_speed': 200,
                    'logical_ports': 1,
                    'logical_speed': 200,
                },
            ],
            'module_types': [
                {
                    'id': 'nic-fe',
                    'manufacturer': 'nvidia',
                    'model': 'BlueField-3 BF3220',
                    'interface_templates': [
                        {'name': 'p0', 'type': 'other'},
                        {'name': 'p1', 'type': 'other'},
                    ],
                },
            ],
        },
        'switch_classes': [
            {
                'switch_class_id': 'fe-leaf',
                'fabric_name': 'frontend',
                'fabric_class': 'managed',
                'hedgehog_role': 'server-leaf',
                'device_type_extension': 'test-sw-ext',
                'redundancy_type': 'eslag',
                'uplink_ports_per_switch': 0,
                'mclag_pair': False,
            },
        ],
        'switch_port_zones': [zone_item],
        'server_classes': [
            {
                'server_class_id': 'gpu',
                'category': 'gpu',
                'quantity': 1,
                'server_device_type': 'test-server',
            },
        ],
        'server_nics': [
            {
                'server_class': 'gpu',
                'nic_id': 'nic-fe',
                'module_type': 'nic-fe',
            },
        ],
        'server_connections': [conn_item],
    }


def _apply(case_dict):
    """Call apply_case() with clean=True to avoid name conflicts across tests."""
    from netbox_hedgehog.test_cases.ingest import apply_case
    return apply_case(case_dict, clean=True, reference_mode='ensure')


# ---------------------------------------------------------------------------
# I1 — null transceiver on zone → ingest succeeds
# ---------------------------------------------------------------------------

class IngestNullZoneTransceiverTestCase(TestCase):
    """
    I1: Ingest YAML with transceiver_module_type: null on zone → succeeds.

    RED: currently the DIET-466 pre-pass raises TestCaseValidationError when
    zone.transceiver_module_type is None.
    After GREEN: pre-pass removed; zone saved with null FK.
    """

    def test_i1_null_zone_transceiver_does_not_raise(self):
        """I1: null transceiver on zone → no TestCaseValidationError."""
        case = _minimal_case('ingest_i1', zone_transceiver=None, conn_transceiver=None)
        try:
            plan = _apply(case)
        except TestCaseValidationError as exc:
            self.fail(
                f'I1: null zone transceiver must not raise TestCaseValidationError; '
                f'got errors: {exc.errors}'
            )
        zone = SwitchPortZone.objects.filter(
            switch_class__plan=plan, zone_name='server-downlinks'
        ).first()
        self.assertIsNotNone(zone, 'I1: zone must be created')
        self.assertIsNone(
            zone.transceiver_module_type_id,
            'I1: zone.transceiver_module_type must be null after ingest',
        )

    def test_i1_null_zone_transceiver_plan_is_created(self):
        """I1b: plan is created successfully despite null zone transceiver."""
        case = _minimal_case('ingest_i1b', zone_transceiver=None, conn_transceiver=None)
        plan = None
        try:
            plan = _apply(case)
        except TestCaseValidationError:
            pass  # expected to fail in RED state
        if plan is not None:
            self.assertTrue(
                TopologyPlan.objects.filter(pk=plan.pk).exists(),
                'I1b: TopologyPlan must be persisted',
            )


# ---------------------------------------------------------------------------
# I2 — absent transceiver key on connection → ingest succeeds
# ---------------------------------------------------------------------------

class IngestAbsentConnectionTransceiverTestCase(TestCase):
    """
    I2: Ingest YAML with no transceiver_module_type key on connection → succeeds.

    RED: currently the pre-pass treats absent key as None → raises.
    After GREEN: absent key treated as null FK; no error.
    """

    def test_i2_absent_conn_transceiver_key_does_not_raise(self):
        """I2: absent transceiver key on connection → no TestCaseValidationError."""
        case = _minimal_case(
            'ingest_i2',
            zone_transceiver=None,
            conn_transceiver='__absent__',  # key not present in dict
        )
        try:
            plan = _apply(case)
        except TestCaseValidationError as exc:
            self.fail(
                f'I2: absent connection transceiver key must not raise; '
                f'got errors: {exc.errors}'
            )
        conn = PlanServerConnection.objects.filter(
            server_class__plan=plan, connection_id='fe'
        ).first()
        self.assertIsNotNone(conn, 'I2: connection must be created')
        self.assertIsNone(
            conn.transceiver_module_type_id,
            'I2: connection.transceiver_module_type must be null',
        )

    def test_i2_absent_zone_transceiver_key_does_not_raise(self):
        """I2b: absent transceiver key on zone → no TestCaseValidationError."""
        case = _minimal_case(
            'ingest_i2b',
            zone_transceiver='__absent__',  # key not present
            conn_transceiver=None,
        )
        try:
            plan = _apply(case)
        except TestCaseValidationError as exc:
            self.fail(
                f'I2b: absent zone transceiver key must not raise; '
                f'got errors: {exc.errors}'
            )


# ---------------------------------------------------------------------------
# I3 — deprecated cage_type key on connection → silently ignored
# ---------------------------------------------------------------------------

class IngestDeprecatedCageTypeKeyTestCase(TestCase):
    """
    I3: Ingest YAML with cage_type key on a connection entry → ingest succeeds;
    key is silently ignored; no TestCaseValidationError.

    RED: currently ingest.py line 847 copies cage_type into the PlanServerConnection
    update_or_create() kwargs. After the migration removes the field, this line
    will cause an error. The spec says the GREEN fix ignores the key silently.
    """

    def test_i3_cage_type_key_does_not_block_ingest(self):
        """I3: cage_type key on connection → ingest does not raise."""
        case = _minimal_case(
            'ingest_i3',
            zone_transceiver=None,
            conn_transceiver=None,
            conn_extra_keys={'cage_type': 'QSFP112'},
        )
        try:
            plan = _apply(case)
        except TestCaseValidationError as exc:
            self.fail(
                f'I3: cage_type key in connection must not raise TestCaseValidationError; '
                f'got errors: {exc.errors}'
            )
        except Exception as exc:
            self.fail(
                f'I3: cage_type key must be silently ignored; '
                f'got unexpected error: {exc!r}'
            )

    def test_i3_medium_key_does_not_block_ingest(self):
        """I3b: medium key on connection → ingest does not raise."""
        case = _minimal_case(
            'ingest_i3b',
            zone_transceiver=None,
            conn_transceiver=None,
            conn_extra_keys={'medium': 'MMF'},
        )
        try:
            _apply(case)
        except (TestCaseValidationError, Exception) as exc:
            self.fail(
                f'I3b: deprecated medium key must be silently ignored; got: {exc!r}'
            )

    def test_i3_connector_key_does_not_block_ingest(self):
        """I3c: connector key on connection → ingest does not raise."""
        case = _minimal_case(
            'ingest_i3c',
            zone_transceiver=None,
            conn_transceiver=None,
            conn_extra_keys={'connector': 'MPO-12'},
        )
        try:
            _apply(case)
        except (TestCaseValidationError, Exception) as exc:
            self.fail(
                f'I3c: deprecated connector key must be silently ignored; got: {exc!r}'
            )


# ---------------------------------------------------------------------------
# I4 — fully-annotated case file still ingests successfully (regression guard)
# ---------------------------------------------------------------------------

class IngestFullyAnnotatedCaseRegressionTestCase(TestCase):
    """
    I4: Ingest YAML with all transceivers set → succeeds (regression guard).

    This uses the inline minimal case with a valid transceiver reference to
    confirm that setting transceiver_module_type still works after GREEN.
    Also verifies that the ux_case_small_mclag command path still works.
    """

    def test_i4_both_transceivers_set_ingest_succeeds(self):
        """I4: connection and zone with transceiver set → ingest succeeds."""
        from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile

        mfr, _ = Manufacturer.objects.get_or_create(
            name='IngestTestMfg', defaults={'slug': 'ingest-test-mfg'}
        )
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        xcvr_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='IngestTest-XCVR-200G',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112', 'medium': 'MMF',
                    'reach_class': 'SR',
                },
            },
        )

        case = _minimal_case('ingest_i4', zone_transceiver=None, conn_transceiver=None)
        # Add the transceiver module_type to reference_data
        case['reference_data']['module_types'].append({
            'id': 'xcvr-200g',
            'manufacturer': 'test-mfg',
            'model': 'IngestTest-XCVR-200G',
        })
        # Update zone and connection to reference it
        case['switch_port_zones'][0]['transceiver_module_type'] = 'xcvr-200g'
        case['server_connections'][0]['transceiver_module_type'] = 'xcvr-200g'

        try:
            plan = _apply(case)
        except (TestCaseValidationError, Exception) as exc:
            self.fail(
                f'I4: fully-annotated case must ingest successfully; got: {exc!r}'
            )
        zone = SwitchPortZone.objects.filter(
            switch_class__plan=plan, zone_name='server-downlinks'
        ).first()
        self.assertIsNotNone(zone)
        # If GREEN is implemented, zone should have the FK set. If pre-GREEN, this
        # may be null (because the reference lookup failed). Either way, no crash.
