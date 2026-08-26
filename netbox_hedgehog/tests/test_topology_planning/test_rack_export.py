"""
DIET-611 Phase 3 RED tests — export behavior for rack placement.

Contract (#610 spec, section 10):
  * inventory serialize_device() gains additive rack / position / face keys
  * YAML wiring and generated cabling are UNCHANGED by rack placement
    (rack is provenance only; #607 non-goal to rewire)

References the final intended serializer keys which do NOT exist yet ->
expected to FAIL until Phase 4. No production code is added here.
"""

from django.test import TestCase

from dcim.models import Device

from netbox_hedgehog.tests.test_topology_planning.test_rack_placement import (
    _make_same_switch_plan,
    _plan_servers,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.services.inventory_export import serialize_device


class InventoryRackKeysTestCase(TestCase):

    def test_serialize_device_includes_rack_position_face_for_placed_server(self):
        plan, *_ = _make_same_switch_plan(
            'inv-placed', quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8, server_u_height=2,
        )
        DeviceGenerator(plan).generate_all()
        server = _plan_servers(plan).first()
        payload = serialize_device(server)

        self.assertIn('rack', payload)
        self.assertIn('position', payload)
        self.assertIn('face', payload)
        self.assertIsNotNone(payload['rack'],
                             'Placed server must serialize its rack')
        self.assertIsNotNone(payload['position'])

    def test_serialize_device_rack_keys_null_when_disabled(self):
        plan, *_ = _make_same_switch_plan(
            'inv-disabled', quantity=8, num_switches=1, place_in_racks=False,
        )
        DeviceGenerator(plan).generate_all()
        server = _plan_servers(plan).first()
        payload = serialize_device(server)

        # Additive keys still present, but null (compatibility contract).
        self.assertIn('rack', payload)
        self.assertIsNone(payload['rack'])
        self.assertIsNone(payload['position'])


class WiringUnchangedByRackTestCase(TestCase):
    """Rack placement must not rewire: interface/cable counts and server device
    names are identical to the no-rack generation of the same topology."""

    def _counts(self, plan):
        server_names = set(_plan_servers(plan).values_list('name', flat=True))
        from dcim.models import Interface, Cable
        iface = Interface.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk)).count()
        cable = Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)).count()
        return server_names, iface, cable

    def test_rack_placement_does_not_change_wiring(self):
        off_plan, *_ = _make_same_switch_plan(
            'wire-off', quantity=8, num_switches=2, place_in_racks=False,
        )
        DeviceGenerator(off_plan).generate_all()
        off_names, off_iface, off_cable = self._counts(off_plan)

        on_plan, *_ = _make_same_switch_plan(
            'wire-on', quantity=8, num_switches=2,
            place_in_racks=True, servers_per_rack=4,
        )
        DeviceGenerator(on_plan).generate_all()
        on_names, on_iface, on_cable = self._counts(on_plan)

        self.assertEqual(off_iface, on_iface,
                         'Rack placement must not change interface count')
        self.assertEqual(off_cable, on_cable,
                         'Rack placement must not change cable count')
        self.assertEqual(
            {n.rsplit('-', 1)[1] for n in off_names},
            {n.rsplit('-', 1)[1] for n in on_names},
            'Server device ordinals/names must be unchanged by rack placement',
        )
