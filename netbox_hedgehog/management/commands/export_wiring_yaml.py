"""
Export wiring YAML for a topology plan to a deterministic file path (DIET-224).

Writes the complete Hedgehog wiring artifact, validates it parses as a complete
YAML document stream, and emits integrity metadata (sha256, byte size, line count).

Usage:
    docker compose exec netbox python manage.py export_wiring_yaml <plan_id> --output /path/to/wiring.yaml
    docker compose exec netbox python manage.py export_wiring_yaml 1 --output /tmp/plan-1.yaml

Exit codes:
    0 - Success
    1 - Plan not found, precondition failure, write error, or parse validation failure
"""

import hashlib
import os
import tempfile
from datetime import datetime, timezone

import yaml
from django.core.management.base import BaseCommand, CommandError

from netbox_hedgehog.choices import GenerationStatusChoices
from netbox_hedgehog.models.topology_planning import TopologyPlan
from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan


class Command(BaseCommand):
    help = "Export wiring YAML for a topology plan to a file with integrity metadata"

    def add_arguments(self, parser):
        parser.add_argument(
            'plan_id',
            type=int,
            help='ID of the TopologyPlan to export',
        )
        parser.add_argument(
            '--output',
            required=True,
            metavar='PATH',
            help='Destination file path for the exported YAML',
        )

    def handle(self, *args, **options):
        plan_id = options['plan_id']
        output_path = os.path.abspath(options['output'])

        # --- Fetch plan ---
        try:
            plan = TopologyPlan.objects.get(pk=plan_id)
        except TopologyPlan.DoesNotExist:
            raise CommandError(f"TopologyPlan with ID {plan_id} does not exist")

        self.stdout.write(f"Exporting wiring YAML for plan: {plan.name} (ID: {plan.pk})")

        # --- Precondition: generation must be complete ---
        try:
            generation_state = plan.generation_state
        except Exception:
            raise CommandError(
                "No generation state found for this plan. "
                "Run device generation before exporting."
            )

        if generation_state.status != GenerationStatusChoices.GENERATED:
            raise CommandError(
                f"Plan generation status is '{generation_state.status}'. "
                f"Device generation must complete (status=generated) before export."
            )

        # --- Generate YAML content ---
        try:
            yaml_content = generate_yaml_for_plan(plan)
        except Exception as e:
            raise CommandError(f"YAML generation failed: {e}")

        # --- Validate completeness: must parse as a full document stream ---
        try:
            documents = list(yaml.safe_load_all(yaml_content))
            doc_count = len([d for d in documents if d is not None])
        except yaml.YAMLError as e:
            raise CommandError(
                f"Generated YAML is not parseable as a complete document stream: {e}"
            )

        if doc_count == 0:
            raise CommandError(
                "Generated YAML contains no documents. "
                "Export aborted to prevent empty artifact."
            )

        # --- Compute integrity metadata ---
        content_bytes = yaml_content.encode('utf-8')
        sha256 = hashlib.sha256(content_bytes).hexdigest()
        byte_size = len(content_bytes)
        line_count = yaml_content.count('\n') + (1 if yaml_content else 0)
        timestamp = datetime.now(tz=timezone.utc).isoformat()

        # --- Write atomically: temp file in same dir + rename (prevents partial writes) ---
        output_dir = os.path.dirname(output_path)
        if not os.path.isdir(output_dir):
            raise CommandError(f"Output directory does not exist: {output_dir}")

        try:
            fd, tmp_path = tempfile.mkstemp(dir=output_dir, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(yaml_content)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, output_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as e:
            raise CommandError(f"Failed to write export file to {output_path}: {e}")

        # --- Verify written file re-reads and re-parses correctly ---
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                written_content = f.read()
            written_docs = list(yaml.safe_load_all(written_content))
            written_doc_count = len([d for d in written_docs if d is not None])
        except Exception as e:
            raise CommandError(f"Written file failed re-parse validation: {e}")

        if written_doc_count != doc_count:
            raise CommandError(
                f"Written file integrity failure: expected {doc_count} documents, "
                f"re-read yielded {written_doc_count}"
            )

        # --- Emit integrity metadata ---
        self.stdout.write("")
        self.stdout.write(f"[OK] Export complete: {output_path}")
        self.stdout.write(f"  plan_id:    {plan.pk}")
        self.stdout.write(f"  timestamp:  {timestamp}")
        self.stdout.write(f"  sha256:     {sha256}")
        self.stdout.write(f"  bytes:      {byte_size}")
        self.stdout.write(f"  lines:      {line_count}")
        self.stdout.write(f"  documents:  {doc_count}")
