"""
Regression coverage for the OPG-512 dedicated-fabrics generation blocker
(issues #598/#599).

Root cause: the ``alternating`` distribution in
``DeviceGenerator._select_switch_instance`` cycles the *intra-connection* port
axis (``range(ports_per_connection)``), not a per-server/per-connection counter.
For single-port connections ``port_index`` is always 0, so every such connection
lands on switch instance 0. In the dedicated-fabrics fixture this piled all 128
frontend links onto ``fe-leaf-1`` (capacity 64), exhausting the zone ~4 minutes
into an otherwise-linear generation run (everything inside one
``@transaction.atomic``, so nothing was ever committed — it looked like a hang).

These tests lock in two things:
  1. The distribution semantics that make ``alternating`` unsuitable for
     single-port fan-out across multiple leaves (documents *why* the fixture
     uses ``rail-optimized`` / ``same-switch`` instead).
  2. A fast, pre-write capacity preflight that fails in milliseconds with an
     actionable message instead of grinding for minutes and rolling back.
"""

from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from dcim.models import Device
from netbox_hedgehog.choices import ConnectionDistributionChoices
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.test_cases import runner
from netbox_hedgehog.utils.topology_calculations import update_plan_calculations

CASE_ID = "training_opg512_dual_plane_dedicated_fabrics"


class SelectSwitchInstanceSemanticsTests(TestCase):
    """Unit lock on the distribution behaviour that motivated the fixture fix."""

    def _gen(self):
        # __new__ avoids DB/site setup; _select_switch_instance is pure.
        return DeviceGenerator.__new__(DeviceGenerator)

    def test_alternating_single_port_always_selects_instance_zero(self):
        """
        With ports_per_connection==1, port_index is always 0, so ``alternating``
        degenerates to "always instance 0" regardless of server_index. This is
        exactly why single-port frontend/storage links must NOT use alternating
        to fan out across a leaf pair.
        """
        gen = self._gen()
        switches = ["leaf-1", "leaf-2"]
        picks = {
            gen._select_switch_instance(
                switches,
                ConnectionDistributionChoices.ALTERNATING,
                server_index=si,
                port_index=0,
            )
            for si in range(10)
        }
        self.assertEqual(picks, {"leaf-1"})

    def test_alternating_multi_port_spreads_within_connection(self):
        """A 2-port alternating connection DOES spread across the 2 instances."""
        gen = self._gen()
        switches = ["leaf-1", "leaf-2"]
        picks = [
            gen._select_switch_instance(
                switches,
                ConnectionDistributionChoices.ALTERNATING,
                server_index=0,
                port_index=pi,
            )
            for pi in range(2)
        ]
        self.assertEqual(picks, ["leaf-1", "leaf-2"])


class DedicatedFabricsCapacityPreflightTests(TestCase):
    """
    Integration coverage against the real dedicated-fabrics fixture.

    The preflight is pure arithmetic (no device writes), so these tests are fast
    — they never run full generation.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("load_diet_reference_data", stdout=StringIO(), stderr=StringIO())
        cls.plan = runner.apply_case_id(CASE_ID, clean=True)
        update_plan_calculations(cls.plan)

    def _generator(self):
        return DeviceGenerator(plan=self.plan)

    def test_corrected_fixture_uses_balanced_distributions(self):
        """Fixture contract: frontend/storage rail-optimized, x550 same-switch."""
        conns = {
            c.connection_id: c
            for sc in self.plan.server_classes.all()
            for c in sc.connections.all()
        }
        for cid in ("fe-bf3-0", "fe-bf3-1", "storage-bf3-0", "storage-bf3-1"):
            self.assertEqual(
                conns[cid].distribution,
                ConnectionDistributionChoices.RAIL_OPTIMIZED,
                f"{cid} must be rail-optimized to spread across the leaf pair",
            )
        self.assertEqual(
            conns["x550-mgmt"].distribution,
            ConnectionDistributionChoices.SAME_SWITCH,
        )

    def test_preflight_passes_for_corrected_fixture(self):
        """The corrected fixture must fit every zone exactly — no exception."""
        try:
            self._generator()._preflight_zone_capacity()
        except ValidationError as exc:  # pragma: no cover - failure path
            self.fail(f"preflight unexpectedly failed: {exc.messages}")

    def test_preflight_raises_fast_when_frontend_reverts_to_alternating(self):
        """
        Reproduce the #598 defect: flip the two frontend links back to the
        broken single-port ``alternating`` distribution and assert the preflight
        rejects it BEFORE any device is written, naming the exhausted zone.
        """
        for cid in ("fe-bf3-0", "fe-bf3-1"):
            conn = next(
                c
                for sc in self.plan.server_classes.all()
                for c in sc.connections.all()
                if c.connection_id == cid
            )
            conn.distribution = ConnectionDistributionChoices.ALTERNATING
            conn.rail = None
            conn.save()

        before = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).count()

        with self.assertRaises(ValidationError) as ctx:
            self._generator()._preflight_zone_capacity()

        joined = " ".join(ctx.exception.messages)
        self.assertIn("fe-server-ports", joined)

        after = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).count()
        self.assertEqual(before, after, "preflight must not write any devices")
