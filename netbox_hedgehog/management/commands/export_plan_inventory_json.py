"""
Export plan-scoped NetBox inventory to JSON.

The export is filtered by ``hedgehog_plan_id`` so only objects generated for the
requested topology plan are included.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from netbox_hedgehog.choices import GenerationStatusChoices
from netbox_hedgehog.models.topology_planning import TopologyPlan
from netbox_hedgehog.services.inventory_export import (
    get_plan_inventory,
    serialize_cable,
    serialize_device,
    serialize_interface,
    serialize_module,
)


class Command(BaseCommand):
    help = "Export plan-scoped NetBox inventory to JSON"

    def add_arguments(self, parser):
        parser.add_argument("plan_id", type=int, help="ID of the TopologyPlan to export")
        parser.add_argument("--output", required=True, metavar="PATH", help="Destination JSON path")

    def handle(self, *args, **options):
        plan = self._get_plan(options["plan_id"])
        self._require_generated(plan)

        output_path = os.path.abspath(options["output"])
        output_dir = os.path.dirname(output_path)
        if not os.path.isdir(output_dir):
            raise CommandError(f"Output directory does not exist: {output_dir}")

        inventory = get_plan_inventory(plan)
        document = {
            "metadata": {
                "plan_id": plan.pk,
                "plan_name": plan.name,
                "generated_at": datetime.now(tz=timezone.utc).isoformat(),
                "counts": {
                    "devices": len(inventory.devices),
                    "modules": len(inventory.modules),
                    "interfaces": len(inventory.interfaces),
                    "cables": len(inventory.cables),
                },
            },
            "devices": [serialize_device(obj) for obj in inventory.devices],
            "modules": [serialize_module(obj) for obj in inventory.modules],
            "interfaces": [serialize_interface(obj) for obj in inventory.interfaces],
            "cables": [serialize_cable(obj) for obj in inventory.cables],
        }
        content = json.dumps(document, indent=2, sort_keys=True) + "\n"
        self._atomic_write(output_path, content)

        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        line_count = content.count("\n")
        self.stdout.write("")
        self.stdout.write(f"[OK] Export complete: {output_path}")
        self.stdout.write(f"  plan_id:    {plan.pk}")
        self.stdout.write(f"  sha256:     {sha256}")
        self.stdout.write(f"  bytes:      {len(content.encode('utf-8'))}")
        self.stdout.write(f"  lines:      {line_count}")
        self.stdout.write(f"  devices:    {len(inventory.devices)}")
        self.stdout.write(f"  modules:    {len(inventory.modules)}")
        self.stdout.write(f"  interfaces: {len(inventory.interfaces)}")
        self.stdout.write(f"  cables:     {len(inventory.cables)}")

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

    def _atomic_write(self, output_path: str, content: str) -> None:
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(output_path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, output_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

