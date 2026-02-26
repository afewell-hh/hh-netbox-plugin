"""Apply YAML-defined DIET test cases."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from netbox_hedgehog.test_cases import runner
from netbox_hedgehog.test_cases.exceptions import (
    TestCaseError,
    TestCaseNotFoundError,
    TestCaseValidationError,
)
from netbox_hedgehog.models.topology_planning import (
    GenerationState,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)


class Command(BaseCommand):
    help = "Apply DIET test case(s) from YAML definitions"

    def add_arguments(self, parser):
        parser.add_argument("--case", help="Case ID to apply (e.g., ux_case_128gpu_odd_ports)")
        parser.add_argument("--all", action="store_true", help="Apply all discovered YAML cases")
        parser.add_argument("--list", action="store_true", help="List discovered YAML case IDs")
        parser.add_argument("--clean", action="store_true", help="Clean case-owned objects before apply")
        parser.add_argument("--prune", action="store_true", help="Prune case-owned objects not in YAML")
        parser.add_argument("--generate", action="store_true", help="Reserved for generation workflow")
        parser.add_argument("--report", action="store_true", help="Reserved for reporting workflow")
        parser.add_argument(
            "--require-reference",
            action="store_true",
            help="Strict mode: fail if referenced data is missing",
        )
        parser.add_argument("--dry-run", action="store_true", help="Validate only; do not persist")
        parser.add_argument("--verbose", action="store_true", help="Verbose output")

    def handle(self, *args, **options):
        case_id = options.get("case")
        apply_all = options.get("all")
        list_only = options.get("list")
        clean = options.get("clean", False)
        prune = options.get("prune", False)
        dry_run = options.get("dry_run", False)
        verbose = options.get("verbose", False)

        reference_mode = "require" if options.get("require_reference") else "ensure"
        self.stdout.write(f"Reference mode: {reference_mode}")

        if list_only:
            case_ids = runner.list_case_ids()
            for cid in case_ids:
                self.stdout.write(cid)
            return

        if bool(case_id) == bool(apply_all):
            raise CommandError("Specify exactly one of --case or --all (or use --list)")

        if dry_run:
            if case_id:
                runner.apply_case_id(
                    case_id,
                    clean=False,
                    prune=False,
                    reference_mode=reference_mode,
                )
                self.stdout.write(f"Dry run successful for case: {case_id}")
                self._delete_case_plans(case_id)
                return

            # --all dry-run
            for cid in runner.list_case_ids():
                runner.apply_case_id(
                    cid,
                    clean=False,
                    prune=False,
                    reference_mode=reference_mode,
                )
                self._delete_case_plans(cid)
            self.stdout.write("Dry run successful for all discovered cases")
            return

        try:
            if case_id:
                plan = runner.apply_case_id(
                    case_id,
                    clean=clean,
                    prune=prune,
                    reference_mode=reference_mode,
                )
                self.stdout.write(f"Applied case '{case_id}' -> plan '{plan.name}'")
                return

            applied = runner.apply_all_cases(
                clean=clean,
                prune=prune,
                reference_mode=reference_mode,
            )
            self.stdout.write(f"Applied {len(applied)} case(s)")
            if verbose:
                for cid, plan in applied:
                    self.stdout.write(f"- {cid} -> {plan.name}")
        except TestCaseNotFoundError as exc:
            raise CommandError(str(exc)) from exc
        except TestCaseValidationError as exc:
            raise CommandError(str(exc)) from exc
        except TestCaseError as exc:
            raise CommandError(str(exc)) from exc

    def _delete_case_plans(self, case_id: str) -> None:
        plans = TopologyPlan.objects.filter(
            custom_field_data__managed_by="yaml",
            custom_field_data__yaml_case_id=case_id,
        )
        for plan in plans:
            PlanServerConnection.objects.filter(server_class__plan=plan).delete()
            PlanServerConnection.objects.filter(target_switch_class__plan=plan).delete()
            SwitchPortZone.objects.filter(switch_class__plan=plan).delete()
            PlanSwitchClass.objects.filter(plan=plan).delete()
            PlanServerClass.objects.filter(plan=plan).delete()
            GenerationState.objects.filter(plan=plan).delete()
            plan.delete()
