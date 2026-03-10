"""
RED tests for Phase 3 (DIET-271): manual HHG mapping + FE border uplink breakout.

All tests in this file are expected to FAIL (RED) until Phase 4 GREEN
implementation is complete. Failure reasons are documented per test.

Parent epic: #267
Phase 3 issue: #271
Spec: #270

Test contract:
  - fe-spine switch class must have override_quantity: 4
  - fe-border-uplinks zone must have peer_zone: fe-spine/fe-spine-100G-downlinks
  - DeviceGenerator must produce 4 fe-spine instances
  - DeviceGenerator must produce 16 border uplink cables per border leaf
  - Spine-side endpoints of border uplinks use the fe-spine-100G-downlinks zone (port 64/b_8x100)
  - YAML export produces fabric Connection CRDs for border↔spine links
  - Existing surrogate (oob-mgmt) cable count is unaffected

Regression guards (PASS in both RED and GREEN):
  - T-GUARD-1: fe-border-leaf gets no cables via _create_fabric_connections() path
  - T-GUARD-2: surrogate oob cables count remains 8
"""

from io import StringIO

import yaml as pyyaml

from django.core.management import call_command
from django.test import TestCase, tag

from dcim.models import Cable, Device, Interface

from netbox_hedgehog.choices import FabricTypeChoices, HedgehogRoleChoices
from netbox_hedgehog.models.topology_planning import (
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan

PLAN_NAME = "UX Case 128GPU Odd Ports"


class BorderUplinksStructureTestCase(TestCase):
    """
    Fast structural tests (no generation). Verify YAML-level config before generation.

    Expected failures (RED state):
      - test_fe_spine_has_override_quantity_four: YAML missing override_quantity: 4
      - test_fe_border_uplinks_zone_has_peer_zone: YAML missing peer_zone on fe-border-uplinks
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_case_128gpu_odd_ports", "--clean", stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)

    # -------------------------------------------------------------------------
    # T-SPINE4-0: fe-spine switch class must have override_quantity: 4
    # Expected failure: YAML does not yet include override_quantity: 4
    # -------------------------------------------------------------------------

    def test_fe_spine_has_override_quantity_four(self):
        """fe-spine PlanSwitchClass must have override_quantity=4 after YAML ingest."""
        fe_spine = PlanSwitchClass.objects.filter(
            plan=self.plan,
            switch_class_id='fe-spine',
        ).first()
        self.assertIsNotNone(fe_spine, "fe-spine switch class must exist")
        self.assertEqual(
            fe_spine.override_quantity,
            4,
            f"fe-spine must have override_quantity=4 (got {fe_spine.override_quantity!r}). "
            "Add 'override_quantity: 4' to fe-spine in ux_case_128gpu_odd_ports.yaml",
        )

    # -------------------------------------------------------------------------
    # T-BUL-0: fe-border-uplinks zone must have peer_zone set
    # Expected failure: YAML does not yet have peer_zone on fe-border-uplinks
    # -------------------------------------------------------------------------

    def test_fe_border_uplinks_zone_has_peer_zone(self):
        """fe-border-uplinks zone must reference peer_zone: fe-spine/fe-spine-100G-downlinks."""
        zone = SwitchPortZone.objects.filter(
            switch_class__plan=self.plan,
            zone_name='fe-border-uplinks',
        ).select_related('peer_zone__switch_class').first()
        self.assertIsNotNone(zone, "fe-border-uplinks zone must exist")
        self.assertIsNotNone(
            zone.peer_zone,
            "fe-border-uplinks zone must have peer_zone set. "
            "Add 'peer_zone: fe-spine/fe-spine-100G-downlinks' to fe-border-uplinks in YAML",
        )
        self.assertEqual(
            zone.peer_zone.switch_class.switch_class_id,
            'fe-spine',
            "fe-border-uplinks peer_zone must target fe-spine switch class",
        )
        self.assertEqual(
            zone.peer_zone.zone_name,
            'fe-spine-100G-downlinks',
            "fe-border-uplinks peer_zone must target fe-spine-100G-downlinks zone",
        )


@tag('slow', 'regression')
class BorderUplinksGenerationTestCase(TestCase):
    """
    Slow generation tests. Require full 128GPU device generation.

    Expected failures (RED state):
      - T-SPINE4-1: generator produces 3 fe-spine instances (not 4)
      - T-BUL-1 through T-BUL-4: no border uplink cables exist yet

    Expected passes (regression guards):
      - T-GUARD-1: fe-border-leaf has no cables from _create_fabric_connections()
      - T-GUARD-2: oob surrogate uplink cable count unchanged at 8
    """

    @classmethod
    def setUpTestData(cls):
        call_command(
            "setup_case_128gpu_odd_ports", "--clean", "--generate", stdout=StringIO()
        )
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)
        cls.all_cables = list(
            Cable.objects.filter(
                custom_field_data__hedgehog_plan_id=str(cls.plan.pk)
            )
        )
        cls.border_leaf_ids = set(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(cls.plan.pk),
                custom_field_data__hedgehog_role=HedgehogRoleChoices.BORDER_LEAF,
            ).values_list('id', flat=True)
        )
        cls.spine_ids = set(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(cls.plan.pk),
                custom_field_data__hedgehog_fabric=FabricTypeChoices.FRONTEND,
                custom_field_data__hedgehog_role=HedgehogRoleChoices.SPINE,
            ).values_list('id', flat=True)
        )

    def _cables_between(self, device_id_set_a, device_id_set_b):
        """Return cables connecting any device in set A to any device in set B."""
        result = []
        for cable in self.all_cables:
            a_terms = (
                cable.a_terminations
                if isinstance(cable.a_terminations, list)
                else list(cable.a_terminations.all())
            )
            b_terms = (
                cable.b_terminations
                if isinstance(cable.b_terminations, list)
                else list(cable.b_terminations.all())
            )
            if not a_terms or not b_terms:
                continue
            a_dev_id = a_terms[0].device_id
            b_dev_id = b_terms[0].device_id
            if (a_dev_id in device_id_set_a and b_dev_id in device_id_set_b) or (
                b_dev_id in device_id_set_a and a_dev_id in device_id_set_b
            ):
                result.append(cable)
        return result

    # -------------------------------------------------------------------------
    # T-SPINE4-1: After generate, fe-spine instances == 4
    # Expected failure: override_quantity not in YAML → generator computes 3
    # -------------------------------------------------------------------------

    def test_fe_spine_quantity_is_four(self):
        """After ingest+generate, exactly 4 fe-spine switch instances must exist."""
        spine_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric=FabricTypeChoices.FRONTEND,
            custom_field_data__hedgehog_role=HedgehogRoleChoices.SPINE,
        ).count()
        self.assertEqual(
            spine_count,
            4,
            f"Expected 4 fe-spine instances (override_quantity=4 → effective_quantity=4), "
            f"got {spine_count}. Add 'override_quantity: 4' to fe-spine in YAML and implement "
            "_create_peer_zone_uplink_connections() in device_generator.py",
        )

    # -------------------------------------------------------------------------
    # T-BUL-1: fe-border-leaf-01 has exactly 16 uplink cables to fe-spine
    # Expected failure: 0 border uplink cables generated
    # -------------------------------------------------------------------------

    def test_border_leaf_01_has_sixteen_uplink_cables(self):
        """fe-border-leaf-01 must have 16 cables to fe-spine (4 per spine × 4 spines)."""
        border_01 = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            name='fe-border-leaf-01',
        ).first()
        self.assertIsNotNone(border_01, "fe-border-leaf-01 must exist")

        cables = self._cables_between({border_01.id}, self.spine_ids)
        self.assertEqual(
            len(cables),
            16,
            f"fe-border-leaf-01 must have 16 uplink cables to fe-spine "
            f"(4 per spine × 4 spines), got {len(cables)}",
        )

    # -------------------------------------------------------------------------
    # T-BUL-2: fe-border-leaf-02 has exactly 16 uplink cables to fe-spine
    # Expected failure: 0 border uplink cables generated
    # -------------------------------------------------------------------------

    def test_border_leaf_02_has_sixteen_uplink_cables(self):
        """fe-border-leaf-02 must have 16 cables to fe-spine (4 per spine × 4 spines)."""
        border_02 = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            name='fe-border-leaf-02',
        ).first()
        self.assertIsNotNone(border_02, "fe-border-leaf-02 must exist")

        cables = self._cables_between({border_02.id}, self.spine_ids)
        self.assertEqual(
            len(cables),
            16,
            f"fe-border-leaf-02 must have 16 uplink cables to fe-spine "
            f"(4 per spine × 4 spines), got {len(cables)}",
        )

    # -------------------------------------------------------------------------
    # T-BUL-3: Each fe-spine receives exactly 4 cables from each border leaf
    # Expected failure: 0 cables per spine
    # -------------------------------------------------------------------------

    def test_each_spine_receives_four_cables_from_each_border_leaf(self):
        """Each fe-spine must have exactly 4 cables from fe-border-leaf-01
        and exactly 4 cables from fe-border-leaf-02."""
        border_01 = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            name='fe-border-leaf-01',
        ).first()
        border_02 = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            name='fe-border-leaf-02',
        ).first()
        self.assertIsNotNone(border_01, "fe-border-leaf-01 must exist")
        self.assertIsNotNone(border_02, "fe-border-leaf-02 must exist")

        spine_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric=FabricTypeChoices.FRONTEND,
            custom_field_data__hedgehog_role=HedgehogRoleChoices.SPINE,
        )

        failures = []
        for spine in spine_devices:
            for border, border_name in [(border_01, 'fe-border-leaf-01'), (border_02, 'fe-border-leaf-02')]:
                count = len(self._cables_between({border.id}, {spine.id}))
                if count != 4:
                    failures.append(
                        f"{spine.name} ↔ {border_name}: expected 4 cables, got {count}"
                    )

        self.assertEqual(
            failures,
            [],
            "Border↔spine cable counts incorrect:\n" + "\n".join(failures),
        )

    # -------------------------------------------------------------------------
    # T-BUL-4: Spine-side interfaces of border uplinks use fe-spine-100G-downlinks zone
    # Expected failure: no border uplink cables → no such interfaces
    # -------------------------------------------------------------------------

    def test_border_uplinks_use_spine_100g_zone_port_64(self):
        """Spine-side interfaces from border uplinks must have hedgehog_zone=
        'fe-spine-100G-downlinks' and interface name starting with 'E1/64/'."""
        border_ids = set(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(self.plan.pk),
                custom_field_data__hedgehog_role=HedgehogRoleChoices.BORDER_LEAF,
            ).values_list('id', flat=True)
        )

        # Find all cables between border-leaf and fe-spine
        border_spine_cables = self._cables_between(border_ids, self.spine_ids)

        if not border_spine_cables:
            self.fail(
                "No border↔spine cables found. Expected 32 cables with spine-side "
                "interfaces in zone 'fe-spine-100G-downlinks' (port 64/b_8x100). "
                "Implement _create_peer_zone_uplink_connections() in device_generator.py",
            )

        # For each cable, find the spine-side interface and validate zone + name
        failures = []
        for cable in border_spine_cables:
            a_terms = (
                cable.a_terminations
                if isinstance(cable.a_terminations, list)
                else list(cable.a_terminations.all())
            )
            b_terms = (
                cable.b_terminations
                if isinstance(cable.b_terminations, list)
                else list(cable.b_terminations.all())
            )
            if not a_terms or not b_terms:
                continue

            a_iface = a_terms[0]
            b_iface = b_terms[0]

            # Identify the spine-side interface
            if a_iface.device_id in self.spine_ids:
                spine_iface = a_iface
            else:
                spine_iface = b_iface

            zone = spine_iface.custom_field_data.get('hedgehog_zone', '')
            if zone != 'fe-spine-100G-downlinks':
                failures.append(
                    f"Spine interface {spine_iface.device.name}/{spine_iface.name}: "
                    f"hedgehog_zone={zone!r} (expected 'fe-spine-100G-downlinks')"
                )
            if not spine_iface.name.startswith('E1/64/'):
                failures.append(
                    f"Spine interface {spine_iface.device.name}/{spine_iface.name}: "
                    f"name does not start with 'E1/64/' (expected port 64 breakout)"
                )

        self.assertEqual(
            failures,
            [],
            "Border↔spine cable spine-side interface validation failures:\n"
            + "\n".join(failures),
        )

    # -------------------------------------------------------------------------
    # T-GUARD-1: fe-border-leaf gets NO cables from _create_fabric_connections()
    # PASSES in RED and GREEN (uplink_ports_per_switch=0 guard fires)
    # -------------------------------------------------------------------------

    def test_border_leaf_gets_no_standard_fabric_cables(self):
        """fe-border-leaf must not receive cables via the standard fabric wiring path.
        uplink_ports_per_switch=0 guard fires in _create_fabric_connections(), meaning
        border-leaf↔spine cables via the FABRIC zone (fe-spine-downlinks) must be 0.
        This guard persists even after border uplinks are added via _create_peer_zone_uplink_connections().
        """
        # Find spine-side interfaces with fe-spine-downlinks zone (FABRIC zone)
        spine_fabric_iface_ids = set(
            Interface.objects.filter(
                device_id__in=self.spine_ids,
                custom_field_data__hedgehog_zone='fe-spine-downlinks',
            ).values_list('id', flat=True)
        )

        # Count cables between border-leaf and spine FABRIC zone interfaces
        fabric_border_cables = 0
        for cable in self.all_cables:
            a_terms = (
                cable.a_terminations
                if isinstance(cable.a_terminations, list)
                else list(cable.a_terminations.all())
            )
            b_terms = (
                cable.b_terminations
                if isinstance(cable.b_terminations, list)
                else list(cable.b_terminations.all())
            )
            if not a_terms or not b_terms:
                continue
            a_iface = a_terms[0]
            b_iface = b_terms[0]
            a_dev_id = a_iface.device_id
            b_dev_id = b_iface.device_id
            a_iface_id = a_iface.id
            b_iface_id = b_iface.id

            if (
                (a_dev_id in self.border_leaf_ids and b_iface_id in spine_fabric_iface_ids)
                or (b_dev_id in self.border_leaf_ids and a_iface_id in spine_fabric_iface_ids)
            ):
                fabric_border_cables += 1

        self.assertEqual(
            fabric_border_cables,
            0,
            f"fe-border-leaf must receive 0 cables via the fe-spine-downlinks FABRIC zone "
            f"(_create_fabric_connections guard). Got {fabric_border_cables}. "
            "The uplink_ports_per_switch=0 guard must fire for border-leaf in _create_fabric_connections().",
        )

    # -------------------------------------------------------------------------
    # T-GUARD-2: oob-mgmt surrogate uplink cables count remains 8
    # PASSES in RED and GREEN (new peer_zone method is disjoint from OOB path)
    # -------------------------------------------------------------------------

    def test_surrogate_oob_cables_unaffected(self):
        """Surrogate (oob-mgmt-leaf) uplink cables must still total 8.
        4 oob-mgmt-leaf instances × 2 uplinks each = 8 cables to fe-border-leaf.
        _create_peer_zone_uplink_connections() filters zone_type=UPLINK only —
        OOB zones are exclusively handled by _create_surrogate_uplink_connections()."""
        oob_ids = set(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(self.plan.pk),
                custom_field_data__hedgehog_fabric=FabricTypeChoices.OOB_MGMT,
            ).values_list('id', flat=True)
        )
        border_ids = set(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(self.plan.pk),
                name__startswith='fe-border-leaf-',
            ).values_list('id', flat=True)
        )

        oob_uplink_cables = []
        for cable in self.all_cables:
            a_terms = (
                cable.a_terminations
                if isinstance(cable.a_terminations, list)
                else list(cable.a_terminations.all())
            )
            b_terms = (
                cable.b_terminations
                if isinstance(cable.b_terminations, list)
                else list(cable.b_terminations.all())
            )
            if not a_terms or not b_terms:
                continue
            a_dev_id = a_terms[0].device_id
            b_dev_id = b_terms[0].device_id
            if (a_dev_id in oob_ids and b_dev_id in border_ids) or (
                b_dev_id in oob_ids and a_dev_id in border_ids
            ):
                oob_uplink_cables.append(cable)

        self.assertEqual(
            len(oob_uplink_cables),
            8,
            f"Surrogate oob uplink cables must remain 8 (4 switches × 2 uplinks). "
            f"Got {len(oob_uplink_cables)}. Regression in _create_surrogate_uplink_connections().",
        )


@tag('slow', 'regression')
class BorderUplinksExportTestCase(TestCase):
    """
    Slow export tests. Require generation + YAML export.

    Expected failures (RED state):
      - T-BUL-5: no border↔spine cables → no fabric Connection CRDs for these pairs
    """

    @classmethod
    def setUpTestData(cls):
        call_command(
            "setup_case_128gpu_odd_ports", "--clean", "--generate", stdout=StringIO()
        )
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)
        yaml_content = generate_yaml_for_plan(cls.plan)
        cls.documents = list(pyyaml.safe_load_all(yaml_content))
        cls.connection_crds = [d for d in cls.documents if d and d.get('kind') == 'Connection']
        # Fabric Connection CRDs have spec.fabric key
        cls.fabric_crds = [d for d in cls.connection_crds if 'fabric' in d.get('spec', {})]

    # -------------------------------------------------------------------------
    # T-BUL-5: Border↔spine connections appear as fabric Connection CRDs in YAML export
    # Expected failure: no border↔spine cables → no fabric CRDs for these pairs
    # -------------------------------------------------------------------------

    def test_border_uplinks_are_fabric_crds_in_yaml_export(self):
        """YAML export must contain fabric Connection CRDs for fe-border-leaf↔fe-spine links.
        Both endpoints have hedgehog_fabric=frontend → _endpoint_kind()='managed_switch'
        → _determine_connection_type()='fabric' → fabric CRD.
        Expected: 8 fabric CRDs (2 border leaves × 4 spines = 8 leaf-spine pairs,
        each with 4 links aggregated per CRD).
        """
        # Fabric CRD names for border↔spine follow: fe-spine-0X--fabric--fe-border-leaf-0X
        border_spine_fabric_crds = [
            d for d in self.fabric_crds
            if 'fe-border-leaf' in d.get('metadata', {}).get('name', '')
        ]
        self.assertEqual(
            len(border_spine_fabric_crds),
            8,
            f"Expected 8 fabric Connection CRDs for border↔spine links "
            f"(2 border-leaves × 4 spines = 8 CRDs, each with 4 links). "
            f"Got {len(border_spine_fabric_crds)}. "
            f"Implement _create_peer_zone_uplink_connections() and add peer_zone to YAML.",
        )

    def test_each_border_spine_fabric_crd_has_four_links(self):
        """Each border↔spine fabric CRD must aggregate exactly 4 links."""
        border_spine_fabric_crds = [
            d for d in self.fabric_crds
            if 'fe-border-leaf' in d.get('metadata', {}).get('name', '')
        ]
        if not border_spine_fabric_crds:
            self.skipTest("No border↔spine fabric CRDs found (expected RED failure in T-BUL-5)")

        failures = []
        for crd in border_spine_fabric_crds:
            links = crd.get('spec', {}).get('fabric', {}).get('links', [])
            if len(links) != 4:
                failures.append(
                    f"CRD '{crd['metadata']['name']}': expected 4 links, got {len(links)}"
                )
        self.assertEqual(
            failures,
            [],
            "Border↔spine fabric CRD link count failures:\n" + "\n".join(failures),
        )
