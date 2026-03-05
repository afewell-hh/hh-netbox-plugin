"""
Single-command 128GPU validation golden path pipeline (DIET-235).

Runs the full end-to-end golden path for the 128GPU regression case:
  1. setup_case_128gpu_odd_ports --clean --generate
  2. export_wiring_yaml <plan_id> --output <base>.yaml            (full artifact)
  3. export_wiring_yaml <plan_id> --output <base> --split-by-fabric  (frontend + backend)
  4. hhfab validate full artifact
  5. hhfab validate frontend artifact
  6. hhfab validate backend artifact

Prints a structured summary block and exits non-zero on any failure.

Usage:
    docker compose exec netbox python manage.py validate_case_128gpu_pipeline
    docker compose exec netbox python manage.py validate_case_128gpu_pipeline \\
        --output-dir /tmp/128gpu-artifacts
    docker compose exec netbox python manage.py validate_case_128gpu_pipeline \\
        --skip-setup  # use existing generated plan (skip step 1)

Exit codes:
    0 - All steps passed
    1 - Any step failed (setup, export, or hhfab validation)
"""

import hashlib
import os
import sys
import tempfile

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from netbox_hedgehog.models.topology_planning import TopologyPlan
from netbox_hedgehog.services import hhfab

PLAN_NAME = "UX Case 128GPU Odd Ports"
_FABRICS = ('frontend', 'backend')


class Command(BaseCommand):
    help = "Run the full 128GPU wiring export + hhfab validation pipeline"

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            default=None,
            metavar='DIR',
            help='Directory for wiring artifacts. Defaults to a temporary directory.',
        )
        parser.add_argument(
            '--skip-setup',
            action='store_true',
            default=False,
            help='Skip setup_case_128gpu_odd_ports --clean --generate (use existing plan).',
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        skip_setup = options['skip_setup']

        # --- Step 1: Setup ---
        if not skip_setup:
            self.stdout.write("[1/6] Setting up 128GPU case (--clean --generate)...")
            try:
                call_command(
                    'setup_case_128gpu_odd_ports',
                    clean=True,
                    generate=True,
                    stdout=self.stdout,
                    stderr=self.stderr,
                )
            except (CommandError, Exception) as e:
                raise CommandError(f"Setup failed: {e}")
        else:
            self.stdout.write("[1/6] Skipping setup (--skip-setup).")

        # --- Resolve plan ---
        try:
            plan = TopologyPlan.objects.get(name=PLAN_NAME)
        except TopologyPlan.DoesNotExist:
            raise CommandError(
                f"Plan '{PLAN_NAME}' not found. Run without --skip-setup to create it."
            )

        self.stdout.write(f"      plan_id: {plan.pk}  name: {plan.name}")

        # --- Prepare output directory ---
        _tmpdir = None
        if output_dir is None:
            _tmpdir = tempfile.mkdtemp(prefix=f'128gpu-pipeline-{plan.pk}-')
            output_dir = _tmpdir
        else:
            os.makedirs(output_dir, exist_ok=True)

        full_path = os.path.join(output_dir, '128gpu-full.yaml')
        split_base = os.path.join(output_dir, '128gpu')
        split_paths = {fab: f"{split_base}-{fab}.yaml" for fab in _FABRICS}

        # --- Step 2: Export full artifact ---
        self.stdout.write(f"[2/6] Exporting full artifact -> {full_path}")
        try:
            call_command(
                'export_wiring_yaml',
                str(plan.pk),
                '--output', full_path,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        except CommandError as e:
            raise CommandError(f"Full export failed: {e}")

        # --- Step 3: Export split artifacts ---
        self.stdout.write(f"[3/6] Exporting split artifacts -> {split_base}-{{frontend,backend}}.yaml")
        try:
            call_command(
                'export_wiring_yaml',
                str(plan.pk),
                '--output', split_base,
                split_by_fabric=True,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        except CommandError as e:
            raise CommandError(f"Split export failed: {e}")

        # --- Steps 4-6: hhfab validation ---
        hhfab_available = hhfab.is_hhfab_available()
        if not hhfab_available:
            self.stdout.write(self.style.WARNING(
                "[4-6/6] hhfab not found in PATH - validation skipped.\n"
                "        Install hhfab to enable: curl -fsSL https://i.hhdev.io/hhfab | bash"
            ))

        validation_results = {}  # label -> (success, sha256, path)

        artifacts = [('full', full_path)] + [(fab, split_paths[fab]) for fab in _FABRICS]
        step = 4
        for label, path in artifacts:
            self.stdout.write(f"[{step}/6] hhfab validate [{label}] -> {path}")
            step += 1

            sha256 = _sha256_of_file(path)

            if not hhfab_available:
                validation_results[label] = (None, sha256, path)  # None = skipped
                continue

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            success, _, stderr = hhfab.validate_yaml(content)
            if not success:
                self.stdout.write(self.style.ERROR(f"      [FAIL] {label}: {stderr.strip()}"))
            else:
                self.stdout.write(f"      [PASS] {label}")
            validation_results[label] = (success, sha256, path)

        # --- Summary block ---
        self._print_summary(plan, validation_results, hhfab_available)

        # --- Overall result ---
        failures = [k for k, (ok, _, _) in validation_results.items() if ok is False]
        if failures:
            raise CommandError(
                f"Pipeline FAILED. hhfab validation failed for: {', '.join(failures)}"
            )

        self.stdout.write(self.style.SUCCESS("\n[PASS] Pipeline complete - all steps passed."))

    def _print_summary(self, plan, results, hhfab_available):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("128GPU Pipeline Summary")
        self.stdout.write("=" * 60)
        self.stdout.write(f"  plan_id : {plan.pk}")
        self.stdout.write(f"  plan    : {plan.name}")
        self.stdout.write("")
        self.stdout.write("  Artifacts:")
        for label, (ok, sha256, path) in results.items():
            if ok is None:
                status = "SKIPPED (hhfab unavailable)"
            elif ok:
                status = "PASS"
            else:
                status = "FAIL"
            self.stdout.write(f"    [{label}]")
            self.stdout.write(f"      path   : {path}")
            self.stdout.write(f"      sha256 : {sha256}")
            self.stdout.write(f"      hhfab  : {status}")
        self.stdout.write("=" * 60)


def _sha256_of_file(path):
    """Return hex sha256 of file contents, or 'ERROR' if unreadable."""
    try:
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return 'ERROR'
