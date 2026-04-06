"""
Export plan-scoped BOM (Bill of Materials) from generated NetBox Module inventory.

Outputs a structured BOM aggregated by ModuleType across three sections:
  nic, server_transceiver, switch_transceiver

Switch-side DAC/ACC cable-assembly modules are suppressed from the BOM and
counted separately in the metadata for audit purposes.
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
from netbox_hedgehog.services.bom_export import get_plan_bom, render_bom_csv


class Command(BaseCommand):
    help = "Export plan-scoped Bill of Materials from generated NetBox Module inventory"

    def add_arguments(self, parser):
        parser.add_argument('plan_id', type=int, help="ID of the TopologyPlan to export")
        parser.add_argument(
            '--output', metavar='PATH',
            help="Destination file path (required for json/csv; ignored for table)",
        )
        parser.add_argument(
            '--format', dest='output_format', default='json',
            choices=['json', 'csv', 'table'],
            help="Output format: json (default), csv, or table (stdout only)",
        )

    def handle(self, *args, **options):
        plan = self._get_plan(options['plan_id'])
        self._require_generated(plan)

        fmt = options['output_format']
        bom = get_plan_bom(plan)
        exported_at = datetime.now(tz=timezone.utc).isoformat()

        if fmt == 'table':
            self._write_table(bom)
            return

        output_path = options.get('output')
        if not output_path:
            raise CommandError("--output is required for json and csv formats")
        output_path = os.path.abspath(output_path)
        output_dir = os.path.dirname(output_path)
        if not os.path.isdir(output_dir):
            raise CommandError(f"Output directory does not exist: {output_dir}")

        if fmt == 'json':
            content = self._build_json(bom, exported_at)
        else:
            content = render_bom_csv(bom)

        self._atomic_write(output_path, content)
        sha256 = hashlib.sha256(content.encode('utf-8')).hexdigest()
        self.stdout.write(f"\n[OK] BOM export complete: {output_path}")
        self.stdout.write(f"  plan_id:    {plan.pk}")
        self.stdout.write(f"  line_items: {len(bom.line_items)}")
        self.stdout.write(f"  suppressed: {bom.suppressed_switch_cable_assembly_count}")
        self.stdout.write(f"  sha256:     {sha256}")
        self.stdout.write(f"  bytes:      {len(content.encode('utf-8'))}")

    # -- format builders --

    def _build_json(self, bom, exported_at: str) -> str:
        doc = {
            'metadata': {
                'plan_id': bom.plan_id,
                'plan_name': bom.plan_name,
                'generated_at': bom.generated_at,
                'bom_exported_at': exported_at,
                'suppressed_switch_cable_assembly_count': bom.suppressed_switch_cable_assembly_count,
            },
            'bom': [
                {
                    'section': item.section,
                    'module_type_model': item.module_type_model,
                    'manufacturer': item.manufacturer,
                    'quantity': item.quantity,
                    'cage_type': item.cage_type,
                    'medium': item.medium,
                    'connector': item.connector,
                    'standard': item.standard,
                    'is_cable_assembly': item.is_cable_assembly,
                }
                for item in bom.line_items
            ],
        }
        return json.dumps(doc, indent=2) + '\n'

    def _write_table(self, bom):
        col = '{:<22}{:<36}{:<18}{:<6}{:<10}{:<8}{}\n'
        self.stdout.write(col.format(
            'Section', 'Model', 'Manufacturer', 'Qty', 'Cage', 'Medium', 'Cable?',
        ))
        self.stdout.write('-' * 100)
        for item in bom.line_items:
            self.stdout.write(col.format(
                item.section,
                item.module_type_model[:34],
                item.manufacturer[:16],
                str(item.quantity),
                item.cage_type or '',
                item.medium or '',
                'yes' if item.is_cable_assembly else 'no',
            ))
        self.stdout.write(
            f"\nSuppressed switch-side cable assembly modules (DAC/ACC): "
            f"{bom.suppressed_switch_cable_assembly_count}"
        )

    # -- gating and helpers --

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
                "No generation state found for this plan. "
                "Run device generation before exporting."
            ) from exc
        if state.status != GenerationStatusChoices.GENERATED:
            raise CommandError(
                f"Plan generation status is '{state.status}'. "
                "Status must be 'generated' before BOM export."
            )

    def _atomic_write(self, output_path: str, content: str) -> None:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(output_path), suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, output_path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
