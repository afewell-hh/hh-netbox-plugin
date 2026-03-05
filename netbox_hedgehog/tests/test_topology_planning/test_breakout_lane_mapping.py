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


def _make_zone(breakout_id, logical_ports, logical_speed, port_spec):
    """Return a mock SwitchPortZone with the given breakout_option."""
    bo = MagicMock()
    bo.breakout_id = breakout_id
    bo.logical_ports = logical_ports
    bo.logical_speed = logical_speed

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
