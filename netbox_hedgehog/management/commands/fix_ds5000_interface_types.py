"""
Management command to fix DS5000 interface types (DIET-148 backfill).

Corrects interface type for DS5000 variants from QSFP-DD to OSFP for 800G ports.
"""

from django.core.management.base import BaseCommand
from dcim.models import DeviceType, InterfaceTemplate


class Command(BaseCommand):
    help = "Fix interface types for DS5000 variants (DIET-148: OSFP vs QSFP-DD)"

    # Device types to fix
    DS5000_MODELS = ["DS5000", "celestica-ds5000", "celestica-ds5000-clsp"]

    # Interface type correction
    OLD_TYPE = "800gbase-x-qsfpdd"  # Wrong (QSFP-DD)
    NEW_TYPE = "800gbase-x-osfp"     # Correct (OSFP)

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making changes"
        )

    def handle(self, **options):
        dry_run = options["dry_run"]
        verbosity = options["verbosity"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE ==="))
            self.stdout.write("No changes will be made\n")

        # Find DS5000 variants
        device_types = DeviceType.objects.filter(model__in=self.DS5000_MODELS)

        if not device_types.exists():
            self.stdout.write(self.style.WARNING("No DS5000 device types found"))
            return

        total_updated = 0

        for dt in device_types:
            # Safety check: verify manufacturer is Celestica
            if dt.manufacturer.name != "Celestica":
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {dt.model}: unexpected manufacturer {dt.manufacturer.name}"
                    )
                )
                continue

            # Find interfaces with wrong type
            wrong_interfaces = dt.interfacetemplates.filter(type=self.OLD_TYPE)
            count = wrong_interfaces.count()

            if count == 0:
                if verbosity >= 2:
                    self.stdout.write(f"OK {dt.model}: already correct (no changes needed)")
                continue

            # Expected count: 64 ports per DS5000 variant
            if count != 64:
                self.stdout.write(
                    self.style.WARNING(
                        f"WARN {dt.model}: found {count} interfaces (expected 64)"
                    )
                )

            # Show what will change
            self.stdout.write(f"\n{dt.manufacturer.name} {dt.model}:")
            self.stdout.write(f"  Interfaces to update: {count}")
            self.stdout.write(f"  Change: {self.OLD_TYPE} -> {self.NEW_TYPE}")

            if dry_run:
                total_updated += count
                # Show sample interfaces
                samples = wrong_interfaces[:3]
                for iface in samples:
                    self.stdout.write(f"    - {iface.name}")
                if count > 3:
                    self.stdout.write(f"    - ... ({count - 3} more)")
            else:
                # Apply fix
                updated = wrong_interfaces.update(type=self.NEW_TYPE)
                total_updated += updated
                self.stdout.write(self.style.SUCCESS(f"  OK Updated {updated} interfaces"))

        # Summary
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN: Would update {total_updated} interfaces"))
            self.stdout.write("\nRun without --dry-run to apply changes")
        else:
            self.stdout.write(self.style.SUCCESS(f"OK Fixed {total_updated} interface types"))
