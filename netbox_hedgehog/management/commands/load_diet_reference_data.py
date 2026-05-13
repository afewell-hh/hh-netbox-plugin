"""
Management command to load DIET reference data (seed data).

# Canonical bootstrap command. See management/commands/README.md for the full
# command taxonomy and ownership boundaries.

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

from dcim.models import (
    DeviceType,
    InterfaceTemplate,
    Manufacturer,
    ModuleType,
    ModuleTypeProfile,
)

from netbox_hedgehog.models.topology_planning import BreakoutOption, DeviceTypeExtension
from netbox_hedgehog.seed_catalog import (
    NETWORK_TRANSCEIVER_PROFILE_SCHEMA,
    STATIC_NIC_MODULE_TYPES,
    STATIC_TRANSCEIVER_MODULE_TYPES,
)


class Command(BaseCommand):
    help = 'Load DIET reference data (breakouts, switch profiles, and static module inventory)'

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-switch-profile-import",
            action="store_true",
            help="Skip bundled Hedgehog switch profile import",
        )
        parser.add_argument(
            "--retire-legacy",
            action="store_true",
            help=(
                "Hard-delete retired DeviceTypes (celestica-ds5000-leaf/-spine) and all "
                "dependent plan data before seeding canonical ones.  NOT safe to run on "
                "shared environments — only pass this from reset_local_dev.sh or "
                "equivalent local-reset scripts."
            ),
        )

    def handle(self, *args, **options):
        """Load seed data for DIET reference data models"""

        self.stdout.write(self.style.WARNING('Loading DIET reference data...'))

        # Always purge the 4 forbidden legacy slugs from migration 0009.
        # These rows (ds5000, ds3000, sn5600, es1000-48) are never valid and
        # must not exist after any correct bootstrap, including backup-restore
        # scenarios where migration 0053 may have run before the restore.
        self._purge_forbidden_0009_slugs()

        # Remove retired legacy DeviceTypes only when explicitly requested.
        # retire_legacy_device_types() hard-deletes plan data; it must NOT run
        # unconditionally in a command described as "safe to run multiple times."
        retired_count = 0
        if options.get("retire_legacy"):
            retired_count = self.retire_legacy_device_types()

        # Load BreakoutOption seed data
        breakout_count = self.load_breakout_options()
        imported_switch_profiles = self.import_bundled_switch_profiles(
            skip=options.get("skip_switch_profile_import", False)
        )
        management_switch_count = self.seed_management_switch_device_types()
        server_dt_count = self.seed_generic_server_device_types()
        transceiver_profile = self.ensure_network_transceiver_profile()
        module_type_count = self.seed_static_module_inventory(transceiver_profile)

        self.stdout.write(self.style.SUCCESS(
            f'\nSuccessfully loaded DIET reference data:'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  - BreakoutOption: {breakout_count} records created/updated'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  - Switch profiles imported: {imported_switch_profiles}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  - Management switch types ensured: {management_switch_count}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  - Generic server DeviceTypes ensured: {server_dt_count}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  - Module inventory ensured: {module_type_count}'
        ))
        if retired_count:
            self.stdout.write(self.style.WARNING(
                f'  - Retired legacy DeviceTypes removed: {retired_count}'
            ))

    @transaction.atomic
    def _purge_forbidden_0009_slugs(self) -> None:
        """
        Unconditionally remove the 4 forbidden DeviceTypes created by migration 0009.

        These slugs must never exist after a correct bootstrap, including
        backup-restore scenarios where migration 0053 ran before the restore.
        Cascade order matches retire_legacy_device_types(); no-op when absent.
        """
        from netbox_hedgehog.models.topology_planning import (
            PlanServerConnection,
            PlanSwitchClass,
            SwitchPortZone,
        )

        # sn5600 is intentionally absent: neutral slug, not forbidden.
        FORBIDDEN_SLUGS = ['ds5000', 'ds3000', 'es1000-48']
        for slug in FORBIDDEN_SLUGS:
            try:
                dt = DeviceType.objects.get(slug=slug)
            except DeviceType.DoesNotExist:
                continue
            ext_qs = DeviceTypeExtension.objects.filter(device_type=dt)
            sc_qs = PlanSwitchClass.objects.filter(device_type_extension__in=ext_qs)
            zone_qs = SwitchPortZone.objects.filter(switch_class__in=sc_qs)
            PlanServerConnection.objects.filter(target_zone__in=zone_qs).delete()
            zone_qs.delete()
            sc_qs.delete()
            ext_qs.delete()
            dt.delete()

    @transaction.atomic
    def retire_legacy_device_types(self) -> int:
        """
        Remove all DeviceTypes that must not exist in a correct bootstrap.

        Belt-and-suspenders companion to migration 0053 for pre-0053 backup
        restore scenarios.  All five forbidden slugs and why they are retired:

          - celestica-ds5000-leaf  — retired clone; replaced by celestica-ds5000
          - celestica-ds5000-spine — retired clone; replaced by celestica-ds5000
          - ds5000                 — wrong slug; replaced by celestica-ds5000 (0009 stale)
          - ds3000                 — stale; requires --fabric-ref import (0009 stale)
          - es1000-48              — wrong manufacturer/slug; should be celestica-es1000 (0009 stale)

        sn5600 is intentionally absent: it is not currently required but
        must not be actively purged — it may be added when NVIDIA support lands.

        This method is safe to run on clean DBs (no-op) and on dirty dev
        environments that still carry the stale types.  Cascade order:
        Devices → PlanServerConnection → SwitchPortZone → PlanSwitchClass
        → DeviceTypeExtension → DeviceType.
        """
        from dcim.models import Device
        from netbox_hedgehog.models.topology_planning import (
            PlanServerConnection,
            PlanSwitchClass,
            SwitchPortZone,
        )

        RETIRED_SLUGS = [
            'celestica-ds5000-leaf',
            'celestica-ds5000-spine',
            'ds5000',
            'ds3000',
            'es1000-48',
        ]
        removed = 0

        for slug in RETIRED_SLUGS:
            try:
                dt = DeviceType.objects.get(slug=slug)
            except DeviceType.DoesNotExist:
                continue

            # Cascade: switch classes → zones + connections → extension
            ext_qs = DeviceTypeExtension.objects.filter(device_type=dt)
            sc_qs = PlanSwitchClass.objects.filter(device_type_extension__in=ext_qs)
            zone_qs = SwitchPortZone.objects.filter(switch_class__in=sc_qs)
            PlanServerConnection.objects.filter(target_zone__in=zone_qs).delete()
            zone_qs.delete()
            sc_qs.delete()
            ext_qs.delete()

            # Cascade: devices (and their cables)
            for dev in Device.objects.filter(device_type=dt):
                for iface in dev.interfaces.all():
                    if iface.cable:
                        iface.cable.delete()
            Device.objects.filter(device_type=dt).delete()

            dt.delete()
            self.stdout.write(self.style.WARNING(f'  Retired legacy DeviceType: {slug}'))
            removed += 1

        return removed

    @transaction.atomic
    def load_breakout_options(self):
        """
        Load BreakoutOption seed data.

        Based on PRD Issue #83, Appendix: Reference Data: Pre-populated Values.

        Returns:
            int: Number of BreakoutOption records created/updated
        """

        # Breakout configurations from PRD #83
        # Format: (breakout_id, from_speed, logical_ports, logical_speed)
        breakout_data = [
            # 800G breakouts
            ('1x800g', 800, 1, 800),
            ('2x400g', 800, 2, 400),
            ('4x200g', 800, 4, 200),
            ('8x100g', 800, 8, 100),

            # 400G breakouts
            ('1x400g', 400, 1, 400),
            ('2x200g', 400, 2, 200),
            ('4x100g', 400, 4, 100),

            # 100G breakouts
            ('1x100g', 100, 1, 100),
            ('1x40g', 100, 1, 40),
            ('4x25g', 100, 4, 25),
            ('4x10g', 100, 4, 10),
            ('2x50g', 100, 2, 50),

            # 1G
            ('1x1g', 1, 1, 1),

            # 10G
            ('1x10g', 10, 1, 10),
        ]

        created_count = 0
        updated_count = 0

        for breakout_id, from_speed, logical_ports, logical_speed in breakout_data:
            breakout, created = BreakoutOption.objects.update_or_create(
                breakout_id=breakout_id,
                defaults={
                    'from_speed': from_speed,
                    'logical_ports': logical_ports,
                    'logical_speed': logical_speed,
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

        before_count = DeviceType.objects.count()

        call_command(
            "import_fabric_profiles",
            source_dir=str(profile_dir),
            stdout=self.stdout,
            stderr=self.stderr,
        )

        after_count = DeviceType.objects.count()
        return after_count - before_count

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

    @transaction.atomic
    def ensure_network_transceiver_profile(self) -> ModuleTypeProfile:
        """
        Recreate the Network Transceiver profile after inventory purges.

        reset_local_dev.sh --purge-inventory deletes ModuleTypeProfile rows, so the
        reference-data command must be able to reconstruct the canonical schema.
        """
        profile, created = ModuleTypeProfile.objects.get_or_create(
            name="Network Transceiver",
            defaults={"schema": NETWORK_TRANSCEIVER_PROFILE_SCHEMA},
        )
        if not created and profile.schema != NETWORK_TRANSCEIVER_PROFILE_SCHEMA:
            profile.schema = NETWORK_TRANSCEIVER_PROFILE_SCHEMA
            profile.save(update_fields=["schema"])
        return profile

    @transaction.atomic
    def seed_static_module_inventory(self, transceiver_profile: ModuleTypeProfile) -> int:
        """
        Seed repo-owned ModuleType inventory used by DIET planning/BOM flows.

        This path is intentionally separate from dynamic Hedgehog switch-profile
        import. It covers static optics and NIC inventory that should be
        recreated on local resets without relying on migrations being rerun.
        """
        total = 0

        for spec in STATIC_TRANSCEIVER_MODULE_TYPES:
            self._ensure_module_type(
                spec=spec,
                profile=transceiver_profile,
                interface_specs=[],
            )
            total += 1

        for spec in STATIC_NIC_MODULE_TYPES:
            self._ensure_module_type(
                spec=spec,
                profile=None,
                interface_specs=spec["interface_templates"],
            )
            total += 1

        return total

    def _ensure_module_type(
        self,
        *,
        spec: dict,
        profile: ModuleTypeProfile | None,
        interface_specs: list[tuple[str, str]],
    ) -> ModuleType:
        """Create or update one ModuleType plus its InterfaceTemplates."""
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name=spec["manufacturer"],
            defaults={"slug": spec["manufacturer_slug"]},
        )
        module_type, _ = ModuleType.objects.update_or_create(
            manufacturer=manufacturer,
            model=spec["model"],
            defaults={
                "profile": profile,
                "part_number": spec.get("part_number", ""),
                "description": spec.get("description", ""),
                "comments": spec.get("comments", ""),
                "attribute_data": spec.get("attribute_data", {}),
            },
        )

        existing = InterfaceTemplate.objects.filter(module_type=module_type)
        if not interface_specs:
            if existing.exists():
                existing.delete()
            return module_type

        existing_by_name = {
            tpl.name: tpl for tpl in existing
        }
        desired_names = {name for name, _ in interface_specs}

        for name, interface_type in interface_specs:
            tpl = existing_by_name.get(name)
            if tpl is None:
                InterfaceTemplate.objects.create(
                    module_type=module_type,
                    name=name,
                    type=interface_type,
                )
                continue
            if tpl.type != interface_type:
                tpl.type = interface_type
                tpl.save(update_fields=["type"])

        stale_names = set(existing_by_name) - desired_names
        if stale_names:
            InterfaceTemplate.objects.filter(
                module_type=module_type,
                name__in=stale_names,
            ).delete()

        return module_type

    def _ensure_interfaces(
        self, device_type: DeviceType, interface_specs: list[tuple[str, str]]
    ) -> None:
        """
        Create missing interface templates for a DeviceType.

        Unlike _ensure_module_type(), this helper intentionally does not prune
        or retype existing templates. It is used for static management-switch
        seeds where we only want to fill obvious gaps without rewriting any
        local operator customizations on the DeviceType.
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
