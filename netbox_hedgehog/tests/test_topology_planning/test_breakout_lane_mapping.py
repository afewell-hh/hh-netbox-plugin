"""
Unit tests for breakout lane mapping in yaml_generator (DIET-226).

These tests verify that _generate_port_configuration() emits hhfab-compatible
Switch CRD portBreakouts entries:
  - Key format: 'E1/<port>' (not bare port number)
  - Breakout mode: uppercase 'G' (e.g. '2x400G', '4x200G', '1x800G')
  - portSpeeds and portAutoNegs: not emitted (empty)

Root cause of the bug: bare port numbers ('1': '2x400g') were rejected by hhfab
with 'port 34 not found in switch profile'. The fix uses 'E1/<port>' keys and
uppercase G to match the hhfab switch profile schema.

## Invariants
- Unchanged: connection CRD port names (come from Interface.name, already E1/<port>/<lane>)
- Unchanged: port allocator naming (PortAllocatorV2 already uses E1/<port>/<lane>)
- Changed: Switch CRD portBreakouts key format and breakout mode capitalisation
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from netbox_hedgehog.services.yaml_generator import YAMLGenerator
from netbox_hedgehog.models.topology_planning import SwitchPortZone


def _make_gen():
    """Return a bare YAMLGenerator instance without a plan (for unit-testing helpers)."""
    return YAMLGenerator.__new__(YAMLGenerator)


def _make_zone(breakout_id, logical_ports, logical_speed, port_spec, from_speed=800):
    """Return a mock SwitchPortZone with the given breakout_option.

    from_speed must be set explicitly so the GREEN implementation of
    _generate_port_configuration() (which gates on from_speed < 100) receives a
    real integer rather than a MagicMock whose truthiness is non-deterministic.

    Default from_speed=800 keeps all existing high-speed tests correct after GREEN.
    Pass from_speed=25 (or another sub-100 value) to exercise the portSpeeds path.
    """
    bo = MagicMock()
    bo.breakout_id = breakout_id
    bo.logical_ports = logical_ports
    bo.logical_speed = logical_speed
    bo.from_speed = from_speed  # required for GREEN implementation's < 100 gate

    zone = MagicMock()
    zone.breakout_option = bo
    zone.port_spec = port_spec
    return zone


def _run_port_config(zones, native_speed=800):
    """Call _generate_port_configuration() with the given mock zones."""
    ext = MagicMock()
    ext.native_speed = native_speed
    sc = MagicMock()
    sc.device_type_extension = ext

    gen = _make_gen()
    with patch.object(SwitchPortZone, 'objects') as mock_qs:
        mock_qs.filter.return_value.order_by.return_value = zones
        return gen._generate_port_configuration(sc)


class BreakoutKeyFormatTestCase(TestCase):
    """portBreakouts keys must use 'E1/<port>' format, never bare port numbers."""

    def test_2x400g_uses_e1_prefix(self):
        result = _run_port_config([_make_zone('2x400g', 2, 400, '1-4')])
        pb = result['portBreakouts']
        self.assertIn('E1/1', pb)
        self.assertIn('E1/2', pb)
        self.assertIn('E1/3', pb)
        self.assertIn('E1/4', pb)

    def test_4x200g_uses_e1_prefix(self):
        result = _run_port_config([_make_zone('4x200g', 4, 200, '1-3')])
        pb = result['portBreakouts']
        self.assertIn('E1/1', pb)
        self.assertIn('E1/2', pb)
        self.assertIn('E1/3', pb)

    def test_1x800g_native_uses_e1_prefix(self):
        result = _run_port_config([_make_zone('1x800g', 1, 800, '33-36')])
        pb = result['portBreakouts']
        self.assertIn('E1/33', pb)
        self.assertIn('E1/34', pb)

    def test_no_bare_number_keys(self):
        result = _run_port_config([_make_zone('2x400g', 2, 400, '1-4')])
        pb = result['portBreakouts']
        for key in pb:
            self.assertTrue(key.startswith('E1/'),
                            f"portBreakouts key '{key}' must use E1/<port> format")


class BreakoutModeCapitalisationTestCase(TestCase):
    """Breakout mode values must use uppercase 'G' to match hhfab profile schema."""

    def test_2x400g_is_uppercase_g(self):
        result = _run_port_config([_make_zone('2x400g', 2, 400, '1-2')])
        pb = result['portBreakouts']
        self.assertEqual(pb.get('E1/1'), '2x400G')

    def test_4x200g_is_uppercase_g(self):
        result = _run_port_config([_make_zone('4x200g', 4, 200, '1-2')])
        pb = result['portBreakouts']
        self.assertEqual(pb.get('E1/1'), '4x200G')

    def test_1x800g_native_is_uppercase_g(self):
        result = _run_port_config([_make_zone('1x800g', 1, 800, '33-34')])
        pb = result['portBreakouts']
        self.assertEqual(pb.get('E1/33'), '1x800G')

    def test_no_lowercase_g_in_breakout_values(self):
        zones = [
            _make_zone('2x400g', 2, 400, '1-4'),
            _make_zone('1x800g', 1, 800, '33-36'),
        ]
        result = _run_port_config(zones)
        for key, value in result['portBreakouts'].items():
            self.assertFalse(value.endswith('g'),
                             f"portBreakouts['{key}'] = '{value}' must use uppercase G")


class PortSpeedsNotEmittedTestCase(TestCase):
    """portSpeeds and portAutoNegs must be empty (hhfab does not use them)."""

    def test_portSpeeds_empty_for_breakout_zone(self):
        result = _run_port_config([_make_zone('2x400g', 2, 400, '1-8')])
        self.assertEqual(result['portSpeeds'], {})

    def test_portAutoNegs_empty_for_breakout_zone(self):
        result = _run_port_config([_make_zone('4x200g', 4, 200, '1-8')])
        self.assertEqual(result['portAutoNegs'], {})

    def test_portSpeeds_empty_for_native_zone(self):
        result = _run_port_config([_make_zone('1x800g', 1, 800, '33-64')])
        self.assertEqual(result['portSpeeds'], {})

    def test_portSpeeds_empty_for_mixed_zones(self):
        zones = [
            _make_zone('4x200g', 4, 200, '1-63:2'),
            _make_zone('1x800g', 1, 800, '2-64:2'),
        ]
        result = _run_port_config(zones)
        self.assertEqual(result['portSpeeds'], {})
        self.assertEqual(result['portAutoNegs'], {})


class LowSpeedPortsEmitPortSpeedsTestCase(TestCase):
    """
    RED tests: sub-100G zones (from_speed < 100) must emit portSpeeds, not portBreakouts.

    These tests FAIL in the current state because _generate_port_configuration()
    unconditionally emits all breakout_option zones into portBreakouts regardless
    of from_speed.  After GREEN (Fix A), from_speed < 100 routes to portSpeeds.

    The _make_zone from_speed parameter update above is the prerequisite: without
    an explicit from_speed integer on the mock, the GREEN implementation's
    `if zone.breakout_option.from_speed < 100:` comparison would receive a
    MagicMock whose truthiness is non-deterministic, silently breaking the
    existing high-speed tests.
    """

    def test_1x25g_zone_absent_from_portBreakouts(self):
        """from_speed=25 (SFP28) zone must not appear in portBreakouts."""
        result = _run_port_config([_make_zone('1x25g', 1, 25, '1-24', from_speed=25)])
        pb = result['portBreakouts']
        for port_num in range(1, 25):
            self.assertNotIn(
                f'E1/{port_num}', pb,
                f"SFP28-25G port E1/{port_num} must not appear in portBreakouts "
                f"(from_speed=25 < 100 → portSpeeds). Currently FAILS."
            )

    def test_1x25g_zone_present_in_portSpeeds(self):
        """from_speed=25 (SFP28) zone must appear in portSpeeds."""
        result = _run_port_config([_make_zone('1x25g', 1, 25, '1-24', from_speed=25)])
        ps = result['portSpeeds']
        self.assertIn(
            'E1/1', ps,
            "SFP28-25G port E1/1 must appear in portSpeeds. "
            "Currently FAILS because portSpeeds is always {} in the broken generator."
        )

    def test_1x25g_portSpeeds_value_is_bare_speed_string(self):
        """portSpeeds value for a 25G zone must be '25G', not '1x25G'."""
        result = _run_port_config([_make_zone('1x25g', 1, 25, '1-3', from_speed=25)])
        ps = result['portSpeeds']
        # First check it's populated (will fail if portSpeeds empty)
        self.assertNotEqual(ps, {}, "portSpeeds must not be empty for from_speed=25 zone")
        for port_key in ('E1/1', 'E1/2', 'E1/3'):
            self.assertEqual(
                ps.get(port_key), '25G',
                f"portSpeeds['{port_key}'] must be '25G' (bare speed), "
                f"not '1x25G' (breakout notation). Got: {ps.get(port_key)!r}"
            )

    def test_1x10g_zone_present_in_portSpeeds(self):
        """from_speed=10 (SFP+) zone must also go to portSpeeds."""
        result = _run_port_config([_make_zone('1x10g', 1, 10, '1-8', from_speed=10)])
        ps = result['portSpeeds']
        self.assertIn('E1/1', ps,
                      "SFP+-10G port E1/1 must appear in portSpeeds (from_speed=10 < 100)")

    def test_mixed_low_and_high_speed_zones(self):
        """Low-speed zone → portSpeeds; high-speed zone → portBreakouts; no overlap."""
        zones = [
            _make_zone('1x25g', 1, 25, '1-8', from_speed=25),    # SFP28 → portSpeeds
            _make_zone('4x200g', 4, 200, '9-32', from_speed=800), # OSFP → portBreakouts
        ]
        result = _run_port_config(zones)
        ps = result['portSpeeds']
        pb = result['portBreakouts']
        # Low-speed ports 1-8 must be in portSpeeds only
        for n in range(1, 9):
            self.assertIn(f'E1/{n}', ps,
                          f"E1/{n} (from_speed=25) must be in portSpeeds")
            self.assertNotIn(f'E1/{n}', pb,
                             f"E1/{n} (from_speed=25) must not be in portBreakouts")
        # High-speed ports 9-32 must be in portBreakouts only
        for n in range(9, 33):
            self.assertIn(f'E1/{n}', pb,
                          f"E1/{n} (from_speed=800) must be in portBreakouts")
            self.assertNotIn(f'E1/{n}', ps,
                             f"E1/{n} (from_speed=800) must not be in portSpeeds")

    def test_high_speed_zones_unaffected_portSpeeds_stays_empty(self):
        """
        Regression guard: high-speed (from_speed=800) zones must NOT emit portSpeeds.

        This test is GREEN even in the RED state (portSpeeds is currently always empty).
        It anchors the correct behavior for the GREEN fix: from_speed >= 100 keeps
        portSpeeds empty and uses portBreakouts as before.
        """
        zones = [
            _make_zone('4x200g', 4, 200, '1-63:2', from_speed=800),
            _make_zone('1x800g', 1, 800, '2-64:2', from_speed=800),
        ]
        result = _run_port_config(zones)
        self.assertEqual(result['portSpeeds'], {},
                         "portSpeeds must remain empty for high-speed (from_speed=800) zones")


class OddEvenPortSpecTestCase(TestCase):
    """Port spec parsing with stride (:2) produces correct E1/<port> keys."""

    def test_odd_ports_1_to_63(self):
        result = _run_port_config([_make_zone('4x200g', 4, 200, '1-63:2')])
        pb = result['portBreakouts']
        expected_ports = list(range(1, 64, 2))  # 1,3,5,...,63
        for p in expected_ports:
            self.assertIn(f'E1/{p}', pb, f"E1/{p} must be in portBreakouts")
        # Even ports must NOT appear
        for p in range(2, 64, 2):
            self.assertNotIn(f'E1/{p}', pb, f"E1/{p} must not appear for odd-only spec")

    def test_even_ports_2_to_64(self):
        result = _run_port_config([_make_zone('1x800g', 1, 800, '2-64:2')])
        pb = result['portBreakouts']
        expected_ports = list(range(2, 65, 2))  # 2,4,6,...,64
        for p in expected_ports:
            self.assertIn(f'E1/{p}', pb, f"E1/{p} must be in portBreakouts")
