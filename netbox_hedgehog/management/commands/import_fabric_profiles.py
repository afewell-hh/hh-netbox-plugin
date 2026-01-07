"""
Management command to import Hedgehog Fabric switch profiles into NetBox (DIET-144).

Usage:
    # Import all profiles from fabric repo (default: master branch)
    python manage.py import_fabric_profiles

    # Import from specific git reference
    python manage.py import_fabric_profiles --fabric-ref v1.0.0

    # Import from local directory
    python manage.py import_fabric_profiles --source-dir /path/to/fabric/switchprofile

    # Import specific profiles only
    python manage.py import_fabric_profiles --profiles celestica-ds5000,celestica-ds3000

    # Dry-run mode (show what would be imported)
    python manage.py import_fabric_profiles --dry-run
"""

from copy import deepcopy
from pathlib import Path
from typing import List, Dict, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dcim.models import DeviceType, Manufacturer
from netbox_hedgehog.models.topology_planning import DeviceTypeExtension
from netbox_hedgehog.utils.fabric_import import (
    FabricProfileGoParser,
    FabricProfileImporter,
)


class Command(BaseCommand):
    help = "Import Hedgehog Fabric switch profiles into NetBox"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fabric-ref",
            default="master",
            help="Fabric git reference (tag or commit SHA). Default: master"
        )
        parser.add_argument(
            "--source-dir",
            help="Import from local directory instead of GitHub"
        )
        parser.add_argument(
            "--profiles",
            help="Comma-separated list of profile names to import (default: all)"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without making changes"
        )

    def handle(self, *args, **options):
        fabric_ref = options["fabric_ref"]
        source_dir = options.get("source_dir")
        profiles_filter = options.get("profiles")
        dry_run = options["dry_run"]

        # Parse profile filter
        profile_names = None
        if profiles_filter:
            profile_names = [p.strip() for p in profiles_filter.split(",")]

        # Get profile files
        if source_dir:
            profile_files = self._load_local_profiles(source_dir)
        else:
            profile_files = self._fetch_github_profiles(fabric_ref)

        # Initialize parser and importer
        parser = FabricProfileGoParser()
        importer = FabricProfileImporter()

        alias_filename_map = {
            config.get("source_file"): profile_name
            for profile_name, config in importer.ALIAS_PROFILES.items()
            if config.get("source_file")
        }
        parsed_cache = {}

        # Track stats
        stats = {
            "processed": 0,
            "device_types_created": 0,
            "device_types_updated": 0,
            "device_types_skipped": 0,
            "extensions_created": 0,
            "extensions_updated": 0,
            "interface_templates_created": 0,
            "breakout_options_created": 0,
        }

        # Process each profile
        for profile_file in profile_files:
            try:
                if source_dir:
                    filename = Path(profile_file).name
                else:
                    filename, _ = profile_file

                alias_name = alias_filename_map.get(filename)

                if alias_name:
                    if profile_names and alias_name not in profile_names:
                        continue
                    parsed_data = self._build_alias_profile_data(
                        alias_name,
                        importer,
                        parsed_cache,
                        parser,
                        source_dir,
                        fabric_ref,
                    )
                    profile_name = alias_name
                else:
                    # Parse profile
                    if source_dir:
                        parsed_data = parser.parse_profile_from_file(profile_file)
                    else:
                        # profile_file is (filename, url) tuple
                        _, url = profile_file
                        parsed_data = parser.parse_profile_from_url(url)

                    profile_name = parsed_data["object_meta"]["name"]

                    # Filter by profile name if specified
                    if profile_names and profile_name not in profile_names:
                        continue

                    parsed_cache[profile_name] = parsed_data

                stats["processed"] += 1

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(f"[DRY RUN] Would import: {profile_name}")
                    )
                    display_name = parsed_data["spec"]["display_name"]
                    manufacturer = importer.extract_manufacturer(display_name)
                    self.stdout.write(f"  Manufacturer: {manufacturer}")
                    self.stdout.write(f"  Model: {profile_name}")
                    continue

                # Import the profile
                result = self._import_profile(parsed_data, importer)

                # Update stats
                if result["device_type_created"]:
                    stats["device_types_created"] += 1
                else:
                    stats["device_types_updated"] += 1

                if result["extension_created"]:
                    stats["extensions_created"] += 1
                else:
                    stats["extensions_updated"] += 1

                stats["interface_templates_created"] += result["interface_templates_created"]
                stats["breakout_options_created"] += result["breakout_options_created"]

                self.stdout.write(
                    self.style.SUCCESS(f"✓ Imported: {profile_name}")
                )

            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"✗ Failed to import {profile_file}: {e}")
                )
                if options["verbosity"] >= 2:
                    raise

        # Import virtual switch profiles (manual definitions)
        for profile_name, profile_config in importer.VIRTUAL_SWITCH_PROFILES.items():
            if profile_names and profile_name not in profile_names:
                continue

            parsed_data = self._build_virtual_profile_data(profile_name, profile_config)
            stats["processed"] += 1

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f"[DRY RUN] Would import: {profile_name}")
                )
                manufacturer = importer.extract_manufacturer(profile_config["display_name"])
                self.stdout.write(f"  Manufacturer: {manufacturer}")
                self.stdout.write(f"  Model: {profile_name}")
                continue

            result = self._import_profile(parsed_data, importer)
            if result["device_type_created"]:
                stats["device_types_created"] += 1
            else:
                stats["device_types_updated"] += 1

            if result["extension_created"]:
                stats["extensions_created"] += 1
            else:
                stats["extensions_updated"] += 1

            stats["interface_templates_created"] += result["interface_templates_created"]
            stats["breakout_options_created"] += result["breakout_options_created"]

            self.stdout.write(
                self.style.SUCCESS(f"✓ Imported: {profile_name}")
            )

        # Print summary
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made"))
        else:
            self.stdout.write(self.style.SUCCESS("Import Complete"))

        self.stdout.write(f"\nProfiles processed: {stats['processed']}")
        if not dry_run:
            self.stdout.write(f"Device types created: {stats['device_types_created']}")
            self.stdout.write(f"Device types updated: {stats['device_types_updated']}")
            self.stdout.write(f"Extensions created: {stats['extensions_created']}")
            self.stdout.write(f"Extensions updated: {stats['extensions_updated']}")
            self.stdout.write(f"Interface templates created: {stats['interface_templates_created']}")
            self.stdout.write(f"Breakout options created: {stats['breakout_options_created']}")
        self.stdout.write("=" * 60 + "\n")

    def _load_local_profiles(self, source_dir: str) -> List[str]:
        """
        Load profile files from local directory.

        Args:
            source_dir: Path to directory containing .go profile files

        Returns:
            List of file paths
        """
        source_path = Path(source_dir)
        if not source_path.exists() or not source_path.is_dir():
            raise CommandError(f"Source directory does not exist: {source_dir}")

        # Find all p_*.go files
        profile_files = list(source_path.glob("p_*.go"))

        if not profile_files:
            raise CommandError(f"No profile files (p_*.go) found in: {source_dir}")

        self.stdout.write(f"Found {len(profile_files)} profile(s) in {source_dir}")
        return [str(f) for f in profile_files]

    def _fetch_github_profiles(self, fabric_ref: str) -> List[tuple]:
        """
        Fetch profile file list from GitHub.

        NOTE: Virtual switch profiles (p_bcm_vs.go, p_clsp_vs.go) are intentionally
        excluded because they use dynamic references and cannot be parsed by the
        regex-based parser. These are imported separately with manual definitions.

        Args:
            fabric_ref: Git reference (tag or commit SHA)

        Returns:
            List of (filename, url) tuples
        """
        # Known hardware profile files (from fabric repo)
        # EXCLUDES virtual profiles: p_bcm_vs.go, p_clsp_vs.go
        PROFILE_FILES = [
            # BCM profiles (13 hardware profiles)
            "p_bcm_celestica_ds2000.go",
            "p_bcm_celestica_ds3000.go",
            "p_bcm_celestica_ds4000.go",
            "p_bcm_celestica_ds4101.go",
            "p_bcm_celestica_ds5000.go",
            "p_bcm_dell_s5232f_on.go",
            "p_bcm_dell_s5248f_on.go",
            "p_bcm_dell_z9332f_on.go",
            "p_bcm_edgecore_dcs203.go",
            "p_bcm_edgecore_dcs204.go",
            "p_bcm_edgecore_dcs501.go",
            "p_bcm_edgecore_eps203.go",
            "p_bcm_supermicro_sse_c4632.go",
            # CLSP profiles (5 hardware profiles)
            "p_clsp_celestica_ds2000.go",
            "p_clsp_celestica_ds3000.go",
            "p_clsp_celestica_ds4000.go",
            "p_clsp_celestica_ds4101.go",
            "p_clsp_celestica_ds5000.go",
        ]

        base_url = f"https://raw.githubusercontent.com/githedgehog/fabric/{fabric_ref}/pkg/ctrl/switchprofile"

        self.stdout.write(f"Fetching {len(PROFILE_FILES)} hardware profiles from fabric@{fabric_ref}")
        self.stdout.write("(Virtual switch profiles imported separately)")
        return [(f, f"{base_url}/{f}") for f in PROFILE_FILES]

    def _build_alias_profile_data(
        self,
        alias_name: str,
        importer: FabricProfileImporter,
        parsed_cache: Dict[str, Any],
        parser: FabricProfileGoParser,
        source_dir: str,
        fabric_ref: str,
    ) -> Dict[str, Any]:
        """
        Build parsed_data for alias profile by cloning the reference profile.
        """
        alias_config = importer.ALIAS_PROFILES[alias_name]
        reference_name = alias_config["reference"]
        reference_data = parsed_cache.get(reference_name)
        if not reference_data:
            reference_file = alias_config.get("reference_file")
            if not reference_file:
                raise CommandError(
                    f"Alias profile '{alias_name}' requires reference '{reference_name}' "
                    "to be imported first."
                )

            if source_dir:
                reference_path = Path(source_dir) / reference_file
                reference_data = parser.parse_profile_from_file(str(reference_path))
            else:
                base_url = (
                    f"https://raw.githubusercontent.com/githedgehog/fabric/"
                    f"{fabric_ref}/pkg/ctrl/switchprofile"
                )
                reference_url = f"{base_url}/{reference_file}"
                reference_data = parser.parse_profile_from_url(reference_url)

            parsed_cache[reference_name] = reference_data

        parsed_data = deepcopy(reference_data)
        parsed_data["object_meta"]["name"] = alias_name
        parsed_data["spec"]["display_name"] = alias_config["display_name"]
        return parsed_data

    def _build_virtual_profile_data(
        self,
        profile_name: str,
        profile_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build parsed_data for manually defined virtual switch profiles.
        """
        return {
            "object_meta": {"name": profile_name},
            "spec": {
                "display_name": profile_config["display_name"],
                "ports": profile_config["ports"],
                "port_profiles": profile_config["port_profiles"],
                "features": profile_config["features"],
            },
        }

    @transaction.atomic
    def _import_profile(
        self,
        parsed_data: Dict[str, Any],
        importer: FabricProfileImporter
    ) -> Dict[str, Any]:
        """
        Import a single profile into NetBox.

        Args:
            parsed_data: Parsed profile data from FabricProfileGoParser
            importer: FabricProfileImporter instance

        Returns:
            Dict with import results
        """
        spec = parsed_data["spec"]
        profile_name = parsed_data["object_meta"]["name"]

        # Extract manufacturer
        display_name = spec["display_name"]
        manufacturer_name = importer.extract_manufacturer(display_name)

        # Get or create manufacturer
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name=manufacturer_name,
            defaults={"slug": manufacturer_name.lower()}
        )

        # Get or create device type
        device_type, device_type_created = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model=profile_name,
            defaults={"slug": profile_name}
        )

        # Create or update extension (only fills empty fields)
        # Check if extension already exists to determine created vs updated
        extension_exists = DeviceTypeExtension.objects.filter(device_type=device_type).exists()
        extension = importer.create_or_update_extension(device_type, parsed_data)
        extension_created = not extension_exists

        # Create interface templates (only if missing)
        ports = spec.get("ports", {})
        port_profiles = spec.get("port_profiles", {})

        initial_template_count = device_type.interfacetemplates.count()
        importer.create_interface_templates(device_type, ports, port_profiles)
        final_template_count = device_type.interfacetemplates.count()
        interface_templates_created = final_template_count - initial_template_count

        # Create breakout options (only if missing)
        # Returns count of newly created options
        breakout_options_created = importer.create_breakout_options(port_profiles)

        return {
            "device_type_created": device_type_created,
            "extension_created": extension_created,
            "interface_templates_created": interface_templates_created,
            "breakout_options_created": breakout_options_created,
        }
