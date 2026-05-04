"""dump_plan_status: write DB-authoritative status block into a YAML case file."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Write the current DB-authoritative status block into a YAML case file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--case", dest="case", required=True,
            help="yaml_case_id to look up the plan",
        )
        parser.add_argument(
            "--file", dest="file", default=None,
            help="Path to the YAML file to update (required unless --dry-run with no file)",
        )
        parser.add_argument(
            "--dry-run", dest="dry_run", action="store_true", default=False,
            help="Print the new status block without modifying the file",
        )

    def handle(self, *args, **options):
        import yaml

        from netbox_hedgehog.models.topology_planning import GenerationState, TopologyPlan

        case_id = options["case"]
        file_path = options.get("file")
        dry_run = options.get("dry_run", False)

        plan = TopologyPlan.objects.filter(
            custom_field_data__managed_by="yaml",
            custom_field_data__yaml_case_id=case_id,
        ).first()
        if plan is None:
            raise CommandError(f"No YAML-managed plan found with yaml_case_id='{case_id}'")

        # Build status block from DB
        try:
            gs = GenerationState.objects.get(plan=plan)
            generation_status = {
                "status": gs.status,
                "device_count": gs.device_count,
                "interface_count": gs.interface_count,
                "cable_count": gs.cable_count,
                "generated_at": gs.generated_at.isoformat() if gs.generated_at else None,
            }
        except GenerationState.DoesNotExist:
            generation_status = None

        status_block = {"generation": generation_status}

        if dry_run:
            self.stdout.write(yaml.dump({"status": status_block}, default_flow_style=False))
            return

        if not file_path:
            self.stdout.write(yaml.dump({"status": status_block}, default_flow_style=False))
            return

        with open(file_path) as f:
            case_data = yaml.safe_load(f)

        if not isinstance(case_data, dict):
            raise CommandError(f"File '{file_path}' does not contain a YAML mapping")

        case_data["status"] = status_block

        with open(file_path, "w") as f:
            yaml.dump(case_data, f, default_flow_style=False, allow_unicode=True)

        self.stdout.write(f"Written status for plan '{plan.name}' to '{file_path}'")
