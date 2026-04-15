"""
Management command to load DIET reference data (seed data).

This command is idempotent - safe to run multiple times.
It uses update_or_create to avoid duplicating records.

Usage:
    docker compose exec netbox python manage.py load_diet_reference_data

Reference:
    - Issue #85 (DIET-001): Database Models & Migrations – Reference Data Layer
    - PRD Issue #83: Breakout option specifications
"""

from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from dcim.models import DeviceType, InterfaceTemplate, Manufacturer

from netbox_hedgehog.models.topology_planning import BreakoutOption, DeviceTypeExtension


class Command(BaseCommand):
    help = 'Load DIET reference data (BreakoutOptions, bundled switch profiles, and static DeviceTypes)'

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-switch-profile-import",
            action="store_true",
            help="Skip bundled Hedgehog switch profile import",
        )

    def handle(self, *args, **options):
        """Load seed data for DIET reference data models"""

        self.stdout.write(self.style.WARNING('Loading DIET reference data...'))

        # Load BreakoutOption seed data
        breakout_count = self.load_breakout_options()
        imported_switch_profiles = self.import_bundled_switch_profiles(
            skip=options.get("skip_switch_profile_import", False)
        )
        management_switch_count = self.seed_management_switch_device_types()
        server_dt_count = self.seed_generic_server_device_types()

        self.stdout.write(self.style.SUCCESS(
            f'\nSuccessfully loaded DIET reference data:'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  - BreakoutOption: {breakout_count} records created/updated'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  - Switch profiles imported (bundled): {imported_switch_profiles}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  - Management switch types ensured: {management_switch_count}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  - Generic server DeviceTypes ensured: {server_dt_count}'
        ))

    @transaction.atomic
    def load_breakout_options(self):
        """
        Load BreakoutOption seed data.

        Based on PRD Issue #83, Appendix: Reference Data: Pre-populated Values.

        Returns:
            int: Number of BreakoutOption records created/updated
        """

        # Breakout configurations from PRD #83
        # Format: (breakout_id, from_speed, logical_ports, logical_speed, optic_type)
        breakout_data = [
            # 800G breakouts (QSFP-DD)
            ('1x800g', 800, 1, 800, 'QSFP-DD'),
            ('2x400g', 800, 2, 400, 'QSFP-DD'),
            ('4x200g', 800, 4, 200, 'QSFP-DD'),
            ('8x100g', 800, 8, 100, 'QSFP-DD'),

            # 400G breakouts (QSFP-DD)
            ('1x400g', 400, 1, 400, 'QSFP-DD'),
            ('2x200g', 400, 2, 200, 'QSFP-DD'),
            ('4x100g', 400, 4, 100, 'QSFP-DD'),

            # 100G breakouts (QSFP28)
            ('1x100g', 100, 1, 100, 'QSFP28'),
            ('1x40g', 100, 1, 40, 'QSFP28'),
            ('4x25g', 100, 4, 25, 'QSFP28'),
            ('4x10g', 100, 4, 10, 'QSFP28'),
            ('2x50g', 100, 2, 50, 'QSFP28'),

            # 1G (RJ45 / SFP)
            ('1x1g', 1, 1, 1, 'RJ45'),

            # 10G (SFP+)
            ('1x10g', 10, 1, 10, 'SFP+'),
        ]

        created_count = 0
        updated_count = 0

        for breakout_id, from_speed, logical_ports, logical_speed, optic_type in breakout_data:
            breakout, created = BreakoutOption.objects.update_or_create(
                breakout_id=breakout_id,
                defaults={
                    'from_speed': from_speed,
                    'logical_ports': logical_ports,
                    'logical_speed': logical_speed,
                    'optic_type': optic_type,
                }
            )

            if created:
                created_count += 1
                self.stdout.write(f'  Created: {breakout}')
            else:
                updated_count += 1
                self.stdout.write(f'  Updated: {breakout}')

        total_count = created_count + updated_count

        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(
                f'\nBreakoutOption: {created_count} created, {updated_count} updated'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'\nBreakoutOption: All {updated_count} records already exist (updated)'
            ))

        return total_count

    def import_bundled_switch_profiles(self, skip: bool = False) -> int:
        """
        Import baseline switch profiles from bundled profile files.

        Uses local files so this remains deterministic and available without
        external network access.
        """
        if skip:
            self.stdout.write(self.style.WARNING(
                'Skipping bundled switch profile import (--skip-switch-profile-import)'
            ))
            return 0

        profile_dir = Path(__file__).resolve().parents[2] / "fabric_profiles"
        if not profile_dir.exists():
            self.stdout.write(self.style.WARNING(
                f'Bundled profile directory missing: {profile_dir}'
            ))
            return 0

        before_exists = DeviceType.objects.filter(model="celestica-ds5000").exists()

        call_command(
            "import_fabric_profiles",
            source_dir=str(profile_dir),
            profiles="celestica-ds5000",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        after_exists = DeviceType.objects.filter(model="celestica-ds5000").exists()
        if after_exists and not before_exists:
            return 1
        if after_exists:
            return 1
        return 0

    @transaction.atomic
    def seed_management_switch_device_types(self) -> int:
        """
        Ensure static management switch DeviceTypes exist when no profile is available.

        Issue #189 requires celestica-es1000 for management fabrics.
        """
        celestica, _ = Manufacturer.objects.get_or_create(
            name="Celestica",
            defaults={"slug": "celestica"},
        )
        es1000, _ = DeviceType.objects.get_or_create(
            manufacturer=celestica,
            model="celestica-es1000",
            defaults={
                "slug": "celestica-es1000",
                "u_height": 1,
                "is_full_depth": False,
                "comments": "Management switch: 48x1G RJ45 + 4xSFP28 + mgmt0",
            },
        )
        DeviceTypeExtension.objects.get_or_create(
            device_type=es1000,
            defaults={
                "mclag_capable": False,
                "hedgehog_roles": [],
                "native_speed": 1,
                "supported_breakouts": ["1x1g", "1x10g"],
                "notes": "Static management switch seed from load_diet_reference_data",
            },
        )

        self._ensure_interfaces(es1000, [(f"eth{i}", "1000base-t") for i in range(1, 49)])
        self._ensure_interfaces(es1000, [(f"uplink{i}", "25gbase-x-sfp28") for i in range(1, 5)])
        self._ensure_interfaces(es1000, [("mgmt0", "1000base-t")])

        return 1

    @transaction.atomic
    def seed_generic_server_device_types(self) -> int:
        """
        Ensure the three generic planning-time server DeviceTypes exist.

        These DeviceTypes were previously seeded only by seed_diet_device_types
        (DIET-448).  Moving them here makes load_diet_reference_data the single
        canonical reset path for all repo-owned DeviceType seeds.

        - GPU-Server-FE:       2×200G frontend NICs
        - GPU-Server-FE-BE:    2×200G frontend + 8×400G backend NICs
        - Storage-Server-200G: 2×200G NICs
        """
        generic, _ = Manufacturer.objects.get_or_create(
            name="Generic",
            defaults={"slug": "generic"},
        )

        server_specs = [
            {
                "model": "GPU-Server-FE",
                "slug": "gpu-server-fe",
                "u_height": 2,
                "comments": "Generic GPU server with 2×200G frontend NICs",
                "interfaces": [
                    ("eth1", "200gbase-x-qsfp56"),
                    ("eth2", "200gbase-x-qsfp56"),
                ],
            },
            {
                "model": "GPU-Server-FE-BE",
                "slug": "gpu-server-fe-be",
                "u_height": 2,
                "comments": "Generic GPU server with 2×200G frontend + 8×400G backend NICs",
                "interfaces": [
                    ("eth1", "200gbase-x-qsfp56"),
                    ("eth2", "200gbase-x-qsfp56"),
                    ("cx7-1", "400gbase-x-qsfpdd"),
                    ("cx7-2", "400gbase-x-qsfpdd"),
                    ("cx7-3", "400gbase-x-qsfpdd"),
                    ("cx7-4", "400gbase-x-qsfpdd"),
                    ("cx7-5", "400gbase-x-qsfpdd"),
                    ("cx7-6", "400gbase-x-qsfpdd"),
                    ("cx7-7", "400gbase-x-qsfpdd"),
                    ("cx7-8", "400gbase-x-qsfpdd"),
                ],
            },
            {
                "model": "Storage-Server-200G",
                "slug": "storage-server-200g",
                "u_height": 2,
                "comments": "Generic storage server with 2×200G NICs",
                "interfaces": [
                    ("eth1", "200gbase-x-qsfp56"),
                    ("eth2", "200gbase-x-qsfp56"),
                ],
            },
        ]

        total = 0
        for spec in server_specs:
            dt, _ = DeviceType.objects.get_or_create(
                manufacturer=generic,
                model=spec["model"],
                defaults={
                    "slug": spec["slug"],
                    "u_height": spec["u_height"],
                    "is_full_depth": True,
                    "comments": spec["comments"],
                },
            )
            self._ensure_interfaces(dt, spec["interfaces"])
            total += 1

        return total

    def _ensure_interfaces(
        self, device_type: DeviceType, interface_specs: list[tuple[str, str]]
    ) -> None:
        """
        Create missing interface templates for a DeviceType.

        Unlike _ensure_module_type(), this helper intentionally does not prune
        or retype existing templates. It is used for static seeds where we only
        want to fill obvious gaps without rewriting any local operator
        customizations on the DeviceType.
        """
        existing = set(
            InterfaceTemplate.objects.filter(device_type=device_type).values_list("name", flat=True)
        )
        for name, interface_type in interface_specs:
            if name in existing:
                continue
            InterfaceTemplate.objects.create(
                device_type=device_type,
                name=name,
                type=interface_type,
            )
