"""
Export plan-scoped interface connections to CSV.

One row is emitted per generated cable tagged for the requested topology plan.
"""

from __future__ import annotations

import csv
import hashlib
import os
import tempfile

from django.core.management.base import BaseCommand, CommandError

from netbox_hedgehog.choices import GenerationStatusChoices
from netbox_hedgehog.models.topology_planning import TopologyPlan
from netbox_hedgehog.services.inventory_export import get_plan_inventory, terminations_for_side


class Command(BaseCommand):
    help = "Export plan-scoped interface connections to CSV"

    FIELDNAMES = [
        "plan_id",
        "cable_id",
        "status",
        "type",
        "zone",
        "a_device",
        "a_interface",
        "a_role",
        "b_device",
        "b_interface",
        "b_role",
    ]

    def add_arguments(self, parser):
        parser.add_argument("plan_id", type=int, help="ID of the TopologyPlan to export")
        parser.add_argument("--output", required=True, metavar="PATH", help="Destination CSV path")

    def handle(self, *args, **options):
        plan = self._get_plan(options["plan_id"])
        self._require_generated(plan)

        output_path = os.path.abspath(options["output"])
        output_dir = os.path.dirname(output_path)
        if not os.path.isdir(output_dir):
            raise CommandError(f"Output directory does not exist: {output_dir}")

        inventory = get_plan_inventory(plan)
        rows = [self._row_for_cable(plan.pk, cable) for cable in inventory.cables]

        fd, tmp_path = tempfile.mkstemp(dir=output_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
                writer.writeheader()
                writer.writerows(rows)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, output_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        with open(output_path, "rb") as handle:
            content = handle.read()
        sha256 = hashlib.sha256(content).hexdigest()

        self.stdout.write("")
        self.stdout.write(f"[OK] Export complete: {output_path}")
        self.stdout.write(f"  plan_id:    {plan.pk}")
        self.stdout.write(f"  sha256:     {sha256}")
        self.stdout.write(f"  bytes:      {len(content)}")
        self.stdout.write(f"  rows:       {len(rows)}")

    def _row_for_cable(self, plan_id: int, cable) -> dict:
        a_term = terminations_for_side(cable, "a")[0]
        b_term = terminations_for_side(cable, "b")[0]
        return {
            "plan_id": plan_id,
            "cable_id": cable.pk,
            "status": cable.status,
            "type": cable.type,
            "zone": (cable.custom_field_data or {}).get("hedgehog_zone", ""),
            "a_device": getattr(getattr(a_term, "device", None), "name", ""),
            "a_interface": getattr(a_term, "name", ""),
            "a_role": getattr(getattr(getattr(a_term, "device", None), "role", None), "slug", ""),
            "b_device": getattr(getattr(b_term, "device", None), "name", ""),
            "b_interface": getattr(b_term, "name", ""),
            "b_role": getattr(getattr(getattr(b_term, "device", None), "role", None), "slug", ""),
        }

    def _get_plan(self, plan_id: int):
        try:
            return TopologyPlan.objects.get(pk=plan_id)
        except TopologyPlan.DoesNotExist as exc:
            raise CommandError(f"TopologyPlan with ID {plan_id} does not exist") from exc

    def _require_generated(self, plan):
        try:
            state = plan.generation_state
        except Exception as exc:
            raise CommandError(
                "No generation state found for this plan. Run device generation before exporting."
            ) from exc

        if state.status != GenerationStatusChoices.GENERATED:
            raise CommandError(
                f"Plan generation status is '{state.status}'. "
                "Device generation must complete (status=generated) before export."
            )

