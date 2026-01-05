"""
Management command to seed DIET DeviceTypes and related objects.

This command creates the standard DIET DeviceTypes used for topology planning:
- DS5000 switch (64x800G)
- GPU-Server-FE (2x200G frontend)
- GPU-Server-FE-BE (2x200G frontend + 8x400G backend)
- Storage-Server-200G (2x200G)

Each DeviceType includes:
- InterfaceTemplates
- DeviceTypeExtension with native_speed, supported_breakouts, etc.

This command is idempotent - safe to run multiple times.

Usage:
    docker compose exec netbox python manage.py seed_diet_device_types
    docker compose exec netbox python manage.py seed_diet_device_types --clean

Reference:
    - Issue #124: Define CI testing strategy
    - Based on setup_case_128gpu_odd_ports.py
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from dcim.models import Manufacturer, DeviceType, InterfaceTemplate

from netbox_hedgehog.models.topology_planning import DeviceTypeExtension


class Command(BaseCommand):
    help = "Seed DIET DeviceTypes (DS5000 switch + 3 server types)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Remove existing DIET DeviceTypes before seeding",
        )

    def handle(self, *args, **options):
        if options["clean"]:
            self.stdout.write("🧹 Cleaning existing DIET DeviceTypes...")
            self._cleanup_device_types()

        self.stdout.write("📦 Seeding DIET DeviceTypes...")

        try:
            with transaction.atomic():
                # Create manufacturers
                celestica = self._ensure_manufacturer("Celestica", "celestica")
                generic = self._ensure_manufacturer("Generic", "generic")

                # Create DS5000 switch
                ds5000 = self._create_ds5000_switch(celestica)

                # Create server DeviceTypes
                gpu_fe = self._create_gpu_server_fe(generic)
                gpu_fe_be = self._create_gpu_server_fe_be(generic)
                storage = self._create_storage_server(generic)

                self.stdout.write(self.style.SUCCESS("\n✅ DIET DeviceTypes seeded successfully!"))
                self.stdout.write("\nCreated DeviceTypes:")
                self.stdout.write(f"  - {ds5000.manufacturer.name} {ds5000.model} ({ds5000.pk})")
                self.stdout.write(f"  - {gpu_fe.manufacturer.name} {gpu_fe.model} ({gpu_fe.pk})")
                self.stdout.write(f"  - {gpu_fe_be.manufacturer.name} {gpu_fe_be.model} ({gpu_fe_be.pk})")
                self.stdout.write(f"  - {storage.manufacturer.name} {storage.model} ({storage.pk})")

        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"❌ Error seeding DeviceTypes: {exc}"))
            raise

    def _cleanup_device_types(self) -> None:
        """Remove DIET seed DeviceTypes and their extensions."""
        device_type_models = [
            ("Celestica", "DS5000"),
            ("Generic", "GPU-Server-FE"),
            ("Generic", "GPU-Server-FE-BE"),
            ("Generic", "Storage-Server-200G"),
        ]

        deleted_count = 0
        for manufacturer_name, model in device_type_models:
            try:
                manufacturer = Manufacturer.objects.get(name=manufacturer_name)
                device_type = DeviceType.objects.filter(
                    manufacturer=manufacturer, model=model
                ).first()

                if device_type:
                    # Delete DeviceTypeExtension first (has FK to DeviceType)
                    DeviceTypeExtension.objects.filter(device_type=device_type).delete()

                    # Delete InterfaceTemplates
                    InterfaceTemplate.objects.filter(device_type=device_type).delete()

                    # Delete DeviceType
                    device_type.delete()
                    deleted_count += 1
                    self.stdout.write(f"  Deleted {manufacturer_name} {model}")
            except Manufacturer.DoesNotExist:
                continue

        if deleted_count == 0:
            self.stdout.write("  No DIET DeviceTypes found to delete")

    def _ensure_manufacturer(self, name: str, slug: str) -> Manufacturer:
        """Get or create manufacturer."""
        manufacturer, created = Manufacturer.objects.get_or_create(
            name=name,
            defaults={"slug": slug},
        )
        if created:
            self.stdout.write(f"  Created manufacturer: {name}")
        return manufacturer

    def _create_ds5000_switch(self, manufacturer: Manufacturer) -> DeviceType:
        """Create DS5000 switch DeviceType with 64x800G ports."""
        self.stdout.write("\n  Creating DS5000 switch...")

        device_type, created = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="DS5000",
            defaults={
                "slug": "ds5000",
                "u_height": 1,
                "is_full_depth": True,
            },
        )

        if created:
            self.stdout.write("    ✓ DS5000 DeviceType created")
        else:
            self.stdout.write("    ℹ DS5000 DeviceType already exists")

        # Create InterfaceTemplates (64x800G)
        existing_count = InterfaceTemplate.objects.filter(device_type=device_type).count()
        if existing_count == 0:
            for index in range(1, 65):
                InterfaceTemplate.objects.create(
                    device_type=device_type,
                    name=f"E1/{index}",  # Fixed: was Ethernet1/{index}
                    type="800gbase-x-qsfpdd",
                )
            self.stdout.write("    ✓ Created 64 InterfaceTemplates")
        else:
            self.stdout.write(f"    ℹ InterfaceTemplates already exist ({existing_count})")

        # Create DeviceTypeExtension
        ext, ext_created = DeviceTypeExtension.objects.get_or_create(
            device_type=device_type,
            defaults={
                "mclag_capable": False,
                "hedgehog_roles": ["spine", "server-leaf"],
                "supported_breakouts": ["1x800g", "2x400g", "4x200g", "8x100g"],
                "native_speed": 800,
                "uplink_ports": 32,  # Deprecated but kept for backward compatibility
                "notes": "Seeded by seed_diet_device_types command",
            },
        )

        if ext_created:
            self.stdout.write("    ✓ DeviceTypeExtension created")
        else:
            # Update if missing required fields
            updated_fields = []
            if ext.native_speed is None:
                ext.native_speed = 800
                updated_fields.append("native_speed")
            if not ext.supported_breakouts:
                ext.supported_breakouts = ["1x800g", "2x400g", "4x200g", "8x100g"]
                updated_fields.append("supported_breakouts")
            if not ext.hedgehog_roles:
                ext.hedgehog_roles = ["spine", "server-leaf"]
                updated_fields.append("hedgehog_roles")

            if updated_fields:
                ext.save(update_fields=updated_fields)
                self.stdout.write(f"    ✓ DeviceTypeExtension updated: {', '.join(updated_fields)}")
            else:
                self.stdout.write("    ℹ DeviceTypeExtension already configured")

        return device_type

    def _create_gpu_server_fe(self, manufacturer: Manufacturer) -> DeviceType:
        """Create GPU-Server-FE DeviceType (2x200G frontend only)."""
        self.stdout.write("\n  Creating GPU-Server-FE...")

        device_type, created = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="GPU-Server-FE",
            defaults={
                "slug": "gpu-server-fe",
                "u_height": 2,
                "is_full_depth": True,
            },
        )

        if created:
            self.stdout.write("    ✓ GPU-Server-FE DeviceType created")
        else:
            self.stdout.write("    ℹ GPU-Server-FE DeviceType already exists")

        # Create InterfaceTemplates
        self._ensure_interface_templates(
            device_type,
            [
                ("eth1", "200gbase-x-qsfp56"),
                ("eth2", "200gbase-x-qsfp56"),
            ],
        )

        return device_type

    def _create_gpu_server_fe_be(self, manufacturer: Manufacturer) -> DeviceType:
        """Create GPU-Server-FE-BE DeviceType (2x200G frontend + 8x400G backend)."""
        self.stdout.write("\n  Creating GPU-Server-FE-BE...")

        device_type, created = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="GPU-Server-FE-BE",
            defaults={
                "slug": "gpu-server-fe-be",
                "u_height": 2,
                "is_full_depth": True,
            },
        )

        if created:
            self.stdout.write("    ✓ GPU-Server-FE-BE DeviceType created")
        else:
            self.stdout.write("    ℹ GPU-Server-FE-BE DeviceType already exists")

        # Create InterfaceTemplates (2x200G FE + 8x400G BE)
        self._ensure_interface_templates(
            device_type,
            [
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
        )

        return device_type

    def _create_storage_server(self, manufacturer: Manufacturer) -> DeviceType:
        """Create Storage-Server-200G DeviceType (2x200G)."""
        self.stdout.write("\n  Creating Storage-Server-200G...")

        device_type, created = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="Storage-Server-200G",
            defaults={
                "slug": "storage-server-200g",
                "u_height": 2,
                "is_full_depth": True,
            },
        )

        if created:
            self.stdout.write("    ✓ Storage-Server-200G DeviceType created")
        else:
            self.stdout.write("    ℹ Storage-Server-200G DeviceType already exists")

        # Create InterfaceTemplates
        self._ensure_interface_templates(
            device_type,
            [
                ("eth1", "200gbase-x-qsfp56"),
                ("eth2", "200gbase-x-qsfp56"),
            ],
        )

        return device_type

    def _ensure_interface_templates(
        self, device_type: DeviceType, interface_specs: list[tuple[str, str]]
    ) -> None:
        """Create InterfaceTemplates if they don't exist."""
        existing_names = set(
            InterfaceTemplate.objects.filter(device_type=device_type).values_list(
                "name", flat=True
            )
        )

        created_count = 0
        for name, interface_type in interface_specs:
            if name not in existing_names:
                InterfaceTemplate.objects.create(
                    device_type=device_type,
                    name=name,
                    type=interface_type,
                )
                created_count += 1

        if created_count > 0:
            self.stdout.write(f"    ✓ Created {created_count} InterfaceTemplates")
        else:
            self.stdout.write(f"    ℹ InterfaceTemplates already exist ({len(interface_specs)})")
