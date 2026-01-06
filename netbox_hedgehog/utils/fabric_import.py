"""
Fabric profile import utilities (DIET-144).

Provides parsing and import capabilities for Hedgehog Fabric switch profiles.
"""

import re
import requests
from typing import Dict, List, Any, Optional
from django.core.exceptions import ValidationError
from django.db import transaction

from dcim.models import DeviceType, Manufacturer, InterfaceTemplate
from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension,
    BreakoutOption,
)


class FabricProfileGoParser:
    """
    Parser for Hedgehog Fabric switch profiles defined in Go source files.

    This is a temporary regex-based parser that will be replaced when fabric
    provides a JSON snapshot exporter (see follow-up issue).

    Actual Go structure (pkg/ctrl/switchprofile/):
    var DeviceName = wiringapi.SwitchProfile{
        ObjectMeta: kmetav1.ObjectMeta{Name: "device-name"},
        Spec: wiringapi.SwitchProfileSpec{
            DisplayName: "Manufacturer ModelName",
            Features: wiringapi.SwitchProfileFeatures{MCLAG: true/false, ...},
            Ports: map[string]wiringapi.SwitchProfilePort{
                "E1/1": {NOSName: "1/1", Label: "1", Profile: "OSFP-800G", ...},
                ...
            },
            PortProfiles: map[string]wiringapi.SwitchProfilePortProfile{
                "OSFP-800G": {
                    Breakout: &wiringapi.SwitchProfilePortProfileBreakout{
                        Default: "1x800G",
                        Supported: map[string]...{"1x800G": {...}, ...},
                    },
                },
                ...
            },
        },
    }
    """

    def __init__(self):
        """Initialize the parser."""
        pass

    def parse_profile_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a fabric profile from a local Go source file.

        Args:
            file_path: Path to the .go profile file

        Returns:
            Dictionary with parsed profile data (same format as parse_profile_from_url)

        Raises:
            FileNotFoundError: If file doesn't exist
            ValidationError: If parsing fails or required fields missing
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            go_source = f.read()

        return self._parse_go_source(go_source)

    def parse_profile_from_url(self, url: str) -> Dict[str, Any]:
        """
        Fetch and parse a fabric profile from a GitHub URL.

        Args:
            url: GitHub raw content URL for the .go profile file

        Returns:
            Dictionary with parsed profile data:
            {
                "object_meta": {"name": "device-model"},
                "spec": {
                    "display_name": "Manufacturer ModelName",
                    "ports": {"E1/1": {...}, "E1/2": {...}, ...},
                    "port_profiles": {
                        "OSFP-800G": {
                            "breakout": {
                                "default": "1x800G",
                                "supported": {"1x800g": {...}, ...}
                            }
                        },
                        ...
                    },
                    "features": {"MCLAG": True/False, ...}
                }
            }

        Raises:
            requests.HTTPError: If URL fetch fails
            ValidationError: If parsing fails or required fields missing
        """
        # Fetch the Go source file
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        go_source = response.text

        # Parse the Go source
        return self._parse_go_source(go_source)

    def _parse_go_source(self, go_source: str) -> Dict[str, Any]:
        """
        Parse Go source code to extract profile data.

        Args:
            go_source: Raw Go source code content

        Returns:
            Parsed profile dictionary

        Raises:
            ValidationError: If parsing fails or required fields missing
        """
        result = {
            "object_meta": {},
            "spec": {
                "ports": {},
                "port_profiles": {},
                "features": {}
            }
        }

        # Extract ObjectMeta.Name
        # Pattern: ObjectMeta: kmetav1.ObjectMeta{Name: "device-name"}
        # OR: ObjectMeta: kmetav1.ObjectMeta{Name: meta.SwitchProfileVS}
        name_match = re.search(
            r'ObjectMeta:\s*kmetav1\.ObjectMeta\s*\{\s*Name:\s*"([^"]+)"',
            go_source
        )
        if name_match:
            result["object_meta"]["name"] = name_match.group(1)
        else:
            # Try matching constant reference pattern (e.g., meta.SwitchProfileVS)
            const_name_match = re.search(
                r'ObjectMeta:\s*kmetav1\.ObjectMeta\s*\{\s*Name:\s*meta\.(\w+)',
                go_source
            )
            if const_name_match:
                # Convert constant name to lowercase with hyphens (e.g., SwitchProfileVS -> vs)
                const_name = const_name_match.group(1)
                # For VS, just use "vs"
                if const_name == "SwitchProfileVS" or const_name.endswith("VS"):
                    result["object_meta"]["name"] = "vs"
                else:
                    # Fallback: convert CamelCase to kebab-case
                    result["object_meta"]["name"] = const_name.lower()
            else:
                raise ValidationError("Could not extract ObjectMeta.Name from profile")

        # Extract Spec.DisplayName
        display_name_match = re.search(r'DisplayName:\s*"([^"]+)"', go_source)
        if display_name_match:
            result["spec"]["display_name"] = display_name_match.group(1)
        else:
            raise ValidationError("Could not extract Spec.DisplayName from profile")

        # Extract Ports
        result["spec"]["ports"] = self._parse_ports(go_source)

        # Extract PortProfiles
        result["spec"]["port_profiles"] = self._parse_port_profiles(go_source)

        # Extract Features (MCLAG, etc.)
        result["spec"]["features"] = self._parse_features(go_source)

        # Validate required fields
        self._validate_parsed_data(result)

        return result

    def _parse_ports(self, go_source: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract port definitions from Go source.

        Args:
            go_source: Raw Go source code

        Returns:
            Dictionary of port name to port data: {"E1/1": {...}, "E1/2": {...}, ...}
        """
        ports = {}

        # Simpler approach: just find all "E1/N": {...} patterns in the entire file
        # Since we only want E1/ ports, this avoids complex block extraction
        # Pattern: "E1/N": {NOSName: "...", Label: "...", Profile: "...", ...}
        port_pattern = re.compile(
            r'"(E1/\d+)":\s*\{([^}]+)\}',
            re.MULTILINE
        )

        for match in port_pattern.finditer(go_source):
            port_key = match.group(1)
            port_content = match.group(2)

            # Extract port fields
            port_data = {}

            # Extract NOSName
            nos_name_match = re.search(r'NOSName:\s*"([^"]+)"', port_content)
            if nos_name_match:
                port_data["nos_name"] = nos_name_match.group(1)

            # Extract Label
            label_match = re.search(r'Label:\s*"([^"]+)"', port_content)
            if label_match:
                port_data["label"] = label_match.group(1)

            # Extract Profile
            profile_match = re.search(r'Profile:\s*"([^"]+)"', port_content)
            if profile_match:
                port_data["profile"] = profile_match.group(1)

            ports[port_key] = port_data

        if not ports:
            raise ValidationError("No E1/N ports found in profile")

        return ports

    def _parse_port_profiles(self, go_source: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract port profile definitions from Go source.

        Args:
            go_source: Raw Go source code

        Returns:
            Dictionary of profile name to profile data:
            {
                "OSFP-800G": {
                    "breakout": {
                        "default": "1x800G",
                        "supported": {"1x800g": {...}, "2x400g": {...}, ...}
                    }
                },
                "SFP28-25G": {
                    "speed": {
                        "default": "25G",
                        "supported": ["1G", "10G", "25G"]
                    }
                },
                ...
            }
        """
        port_profiles = {}

        # Find the PortProfiles map block
        # Pattern: PortProfiles: map[string]wiringapi.SwitchProfilePortProfile{...}
        profiles_block_match = re.search(
            r'PortProfiles:\s*map\[string\]wiringapi\.SwitchProfilePortProfile\s*\{(.+?)\n\s*\},?\s*\n\s*Pipelines',
            go_source,
            re.DOTALL
        )

        if not profiles_block_match:
            # Try alternative ending pattern
            profiles_block_match = re.search(
                r'PortProfiles:\s*map\[string\]wiringapi\.SwitchProfilePortProfile\s*\{(.+)$',
                go_source,
                re.DOTALL
            )

        if not profiles_block_match:
            # PortProfiles might be optional
            return port_profiles

        profiles_block = profiles_block_match.group(1)

        # Extract individual port profile entries
        # Pattern: "ProfileName": {...} where ProfileName contains hyphens (OSFP-800G, SFP28-25G)
        # This avoids matching breakout modes like "1x800G" which don't have hyphens

        # Find profile names - look for quoted strings with hyphens followed by :\s*{
        # This distinguishes profile names (SFP28-25G, OSFP-800G) from breakout modes (1x800G)
        profile_name_pattern = re.compile(r'"([^"]*-[^"]*)":\s*\{')
        profile_names = profile_name_pattern.findall(profiles_block)

        for profile_name in profile_names:
            # Extract the profile block for this name
            # This is tricky because the block might contain nested {...}
            # Use a more sophisticated approach

            # Find the start of this profile
            profile_start = profiles_block.find(f'"{profile_name}":')
            if profile_start == -1:
                continue

            # Find the matching closing brace
            # Count braces to find the matching close
            brace_count = 0
            start_brace = profiles_block.find('{', profile_start)
            if start_brace == -1:
                continue

            profile_end = start_brace
            for i in range(start_brace, len(profiles_block)):
                if profiles_block[i] == '{':
                    brace_count += 1
                elif profiles_block[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        profile_end = i
                        break

            profile_content = profiles_block[start_brace:profile_end+1]

            # Parse the profile content
            profile_data = {}

            # Check if it has Breakout
            if 'Breakout:' in profile_content:
                breakout_data = self._parse_breakout(profile_content)
                if breakout_data:
                    profile_data["breakout"] = breakout_data

            # Check if it has Speed
            if 'Speed:' in profile_content:
                speed_data = self._parse_speed(profile_content)
                if speed_data:
                    profile_data["speed"] = speed_data

            if profile_data:
                port_profiles[profile_name] = profile_data

        return port_profiles

    def _parse_breakout(self, profile_content: str) -> Optional[Dict[str, Any]]:
        """
        Parse breakout configuration from a port profile.

        Args:
            profile_content: Content of a PortProfile block

        Returns:
            Breakout data:
            {
                "default": "1x800G",
                "supported": {"1x800g": {...}, "2x400g": {...}, ...}
            }
        """
        breakout_data = {}

        # Extract Default
        default_match = re.search(r'Default:\s*"([^"]+)"', profile_content)
        if default_match:
            breakout_data["default"] = default_match.group(1)

        # Extract Supported map using brace counting (more reliable than regex)
        # Pattern: Supported: map[string]wiringapi.SwitchProfilePortProfileBreakoutMode{...}
        supported_start = profile_content.find('Supported:')
        if supported_start != -1:
            # Find the opening brace for the Supported map
            map_start = profile_content.find('{', supported_start)
            if map_start != -1:
                # Count braces to find matching close
                brace_count = 0
                map_end = map_start
                for i in range(map_start, len(profile_content)):
                    if profile_content[i] == '{':
                        brace_count += 1
                    elif profile_content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            map_end = i
                            break

                supported_block = profile_content[map_start+1:map_end]
                supported_modes = {}

                # Extract mode entries
                # Pattern: "ModeID": {Offsets: []string{"0", "4"}}
                mode_pattern = re.compile(r'"([^"]+)":\s*\{([^}]+)\}')

                for mode_match in mode_pattern.finditer(supported_block):
                    mode_id = mode_match.group(1).lower()  # Normalize to lowercase
                    mode_content = mode_match.group(2)

                    # Extract Offsets
                    offsets_match = re.search(r'Offsets:\s*\[\]string\{([^}]*)\}', mode_content)
                    offsets = []
                    if offsets_match:
                        offsets_str = offsets_match.group(1)
                        # Extract quoted strings
                        offsets = re.findall(r'"([^"]+)"', offsets_str)

                    supported_modes[mode_id] = {"offsets": offsets}

                if supported_modes:
                    breakout_data["supported"] = supported_modes

        return breakout_data if breakout_data else None

    def _parse_speed(self, profile_content: str) -> Optional[Dict[str, Any]]:
        """
        Parse speed configuration from a port profile.

        Args:
            profile_content: Content of a PortProfile block

        Returns:
            Speed data:
            {
                "default": "25G",
                "supported": ["1G", "10G", "25G"]
            }
        """
        speed_data = {}

        # Extract Default
        default_match = re.search(r'Default:\s*"([^"]+)"', profile_content)
        if default_match:
            speed_data["default"] = default_match.group(1)

        # Extract Supported list
        # Pattern: Supported: []string{"1G", "10G", "25G"}
        supported_match = re.search(r'Supported:\s*\[\]string\s*\{([^}]+)\}', profile_content)
        if supported_match:
            supported_str = supported_match.group(1)
            # Extract quoted strings
            supported_list = re.findall(r'"([^"]+)"', supported_str)
            speed_data["supported"] = supported_list

        return speed_data if speed_data else None

    def _parse_features(self, go_source: str) -> Dict[str, bool]:
        """
        Extract feature flags from Go source.

        Args:
            go_source: Raw Go source code

        Returns:
            Dictionary of features: {"MCLAG": True/False, ...}
        """
        features = {}

        # Find Features block
        # Pattern: Features: wiringapi.SwitchProfileFeatures{MCLAG: true, ...}
        features_match = re.search(
            r'Features:\s*wiringapi\.SwitchProfileFeatures\s*\{([^}]+)\}',
            go_source
        )

        if features_match:
            features_block = features_match.group(1)

            # Extract MCLAG
            mclag_match = re.search(r'MCLAG:\s*(true|false)', features_block)
            if mclag_match:
                features["MCLAG"] = mclag_match.group(1) == "true"

            # Extract other features if needed
            # ESLAG, ACLs, L2VNI, L3VNI, RoCE, etc.
            # For now, just MCLAG is required

        # Default MCLAG to False if not found
        if "MCLAG" not in features:
            features["MCLAG"] = False

        return features

    def _validate_parsed_data(self, data: Dict[str, Any]) -> None:
        """
        Validate that all required fields are present in parsed data.

        Args:
            data: Parsed profile dictionary

        Raises:
            ValidationError: If required fields are missing
        """
        # Required top-level keys
        if "object_meta" not in data:
            raise ValidationError("Missing object_meta in parsed data")
        if "spec" not in data:
            raise ValidationError("Missing spec in parsed data")

        # Required ObjectMeta fields
        if "name" not in data["object_meta"]:
            raise ValidationError("Missing object_meta.name in parsed data")

        # Required Spec fields
        if "display_name" not in data["spec"]:
            raise ValidationError("Missing spec.display_name in parsed data")
        if "ports" not in data["spec"]:
            raise ValidationError("Missing spec.ports in parsed data")
        if "port_profiles" not in data["spec"]:
            raise ValidationError("Missing spec.port_profiles in parsed data")
        if "features" not in data["spec"]:
            raise ValidationError("Missing spec.features in parsed data")

        # Validate ports is not empty
        if not data["spec"]["ports"]:
            raise ValidationError("spec.ports is empty - no ports found")


class FabricProfileImporter:
    """
    Import service for Hedgehog Fabric switch profiles into NetBox.

    Creates/updates DeviceType, DeviceTypeExtension, InterfaceTemplate, and BreakoutOption
    records from parsed fabric profile data.

    CRITICAL GUARDRAILS:
    - Only fills missing/empty fields on existing DeviceTypeExtension
    - Never overwrites non-empty values
    - InterfaceTemplates: E1/x naming, data-plane ports only (skip management)
    - Breakouts: normalize to lowercase, create only if missing
    - native_speed: derive from primary data-plane port profile
    - uplink_ports: leave null (deprecated)
    """

    # Manufacturer name mapping (DisplayName prefix → Manufacturer name)
    MANUFACTURER_MAP = {
        "Celestica": "Celestica",
        "Dell": "Dell",
        "NVIDIA": "NVIDIA",
        "Edgecore": "Edgecore",
        "Edge-Core": "Edgecore",  # Normalize
        "Supermicro": "Supermicro",
        "Virtual": "Hedgehog",  # Virtual switches → Hedgehog vendor
        "Hedgehog": "Hedgehog",
    }

    # Speed → NetBox interface type mapping
    SPEED_TO_INTERFACE_TYPE = {
        800: "800gbase-x-qsfpdd",
        400: "400gbase-x-qsfpdd",
        200: "200gbase-x-qsfp56",
        100: "100gbase-x-qsfp28",
        50: "50gbase-x-sfp56",
        40: "40gbase-x-qsfpp",
        25: "25gbase-x-sfp28",
        10: "10gbase-x-sfpp",
        2.5: "2.5gbase-t",  # Copper (EPS203)
        1: "1000base-x-sfp",
    }

    def extract_manufacturer(self, display_name: str) -> str:
        """
        Extract manufacturer name from DisplayName.

        Args:
            display_name: Profile DisplayName (e.g., "Celestica DS5000")

        Returns:
            Normalized manufacturer name

        Raises:
            ValidationError: If manufacturer cannot be determined
        """
        for prefix, manufacturer in self.MANUFACTURER_MAP.items():
            if display_name.startswith(prefix):
                return manufacturer

        raise ValidationError(f"Unknown manufacturer in DisplayName: {display_name}")

    def derive_native_speed(self, port_profiles: Dict[str, Any]) -> int:
        """
        Derive native_speed from primary data-plane port profile.

        Rules:
        - Use highest speed from Breakout profiles (preferred)
        - Fall back to Speed profiles if no Breakout profiles exist
        - Ignore management/low-speed ports

        Args:
            port_profiles: PortProfiles dict from parsed profile

        Returns:
            Native speed in Gbps

        Raises:
            ValidationError: If no valid port profiles found
        """
        speeds = []

        for profile_name, profile_data in port_profiles.items():
            # Check for Breakout profile (preferred)
            if "breakout" in profile_data:
                breakout = profile_data["breakout"]
                default_mode = breakout.get("default", "")
                if default_mode:
                    # Parse default mode: "1x800G" → 800
                    match = re.match(r'(\d+)x(\d+)[Gg]', default_mode)
                    if match:
                        speed = int(match.group(2))
                        speeds.append(speed)

            # Check for Speed profile (fallback)
            elif "speed" in profile_data:
                speed_config = profile_data["speed"]
                default_speed = speed_config.get("default", "")
                if default_speed:
                    # Parse speed: "25G" → 25
                    match = re.match(r'(\d+)[Gg]', default_speed)
                    if match:
                        speed = int(match.group(1))
                        speeds.append(speed)

        if not speeds:
            raise ValidationError("No valid port profiles found to derive native_speed")

        # Return highest speed
        return max(speeds)

    def derive_supported_breakouts(self, port_profiles: Dict[str, Any]) -> List[str]:
        """
        Extract and normalize supported breakout mode strings.

        Args:
            port_profiles: PortProfiles dict from parsed profile

        Returns:
            List of normalized breakout mode strings (e.g., ["1x800g", "2x400g"])
        """
        breakout_modes = set()

        for profile_name, profile_data in port_profiles.items():
            if "breakout" in profile_data:
                breakout = profile_data["breakout"]
                supported = breakout.get("supported", {})

                # Add all supported mode names (already normalized to lowercase by parser)
                for mode_name in supported.keys():
                    breakout_modes.add(mode_name)

        # Return sorted list for consistent ordering
        return sorted(breakout_modes)

    def parse_breakout_mode_name(self, mode_name: str) -> Dict[str, int]:
        """
        Parse breakout mode name to extract fields.

        Args:
            mode_name: Breakout mode string (e.g., "4x200g")

        Returns:
            Dict with from_speed, logical_ports, logical_speed

        Examples:
            "1x800g" → {from_speed: 800, logical_ports: 1, logical_speed: 800}
            "4x200g" → {from_speed: 800, logical_ports: 4, logical_speed: 200}
        """
        match = re.match(r'(\d+)x(\d+)[Gg]', mode_name)
        if not match:
            raise ValidationError(f"Invalid breakout mode name: {mode_name}")

        logical_ports = int(match.group(1))
        logical_speed = int(match.group(2))
        from_speed = logical_ports * logical_speed

        return {
            "from_speed": from_speed,
            "logical_ports": logical_ports,
            "logical_speed": logical_speed,
        }

    @transaction.atomic
    def create_or_update_extension(
        self,
        device_type: DeviceType,
        parsed_data: Dict[str, Any]
    ) -> DeviceTypeExtension:
        """
        Create or update DeviceTypeExtension with derived fields.

        CRITICAL: Only updates fields that are currently empty/null/default.
        Never overwrites existing non-empty values.

        Args:
            device_type: NetBox DeviceType instance
            parsed_data: Parsed profile data from FabricProfileGoParser

        Returns:
            DeviceTypeExtension instance
        """
        spec = parsed_data["spec"]
        port_profiles = spec.get("port_profiles", {})
        features = spec.get("features", {})

        # Derive values from parsed data
        native_speed = self.derive_native_speed(port_profiles)
        supported_breakouts = self.derive_supported_breakouts(port_profiles)
        mclag_capable = features.get("MCLAG", False)

        # Get or create extension
        ext, created = DeviceTypeExtension.objects.get_or_create(
            device_type=device_type
        )

        # Only update fields that are empty/null/default
        # This preserves user modifications

        if not ext.supported_breakouts:  # Empty list
            ext.supported_breakouts = supported_breakouts

        if ext.native_speed is None:
            ext.native_speed = native_speed

        # Boolean: only update if False (default) - don't downgrade True → False
        if not ext.mclag_capable and mclag_capable:
            ext.mclag_capable = True

        # uplink_ports: leave null (deprecated field)
        # Do not set this field

        # hedgehog_roles: leave empty for now (not in minimal spec)
        # Can be added in future enhancement

        ext.save()
        return ext

    def create_interface_templates(
        self,
        device_type: DeviceType,
        parsed_ports: Dict[str, Any],
        port_profiles: Dict[str, Any]
    ) -> None:
        """
        Create InterfaceTemplates from parsed ports.

        Rules:
        - Only create for data-plane ports (skip management ports)
        - Use E1/N naming from fabric
        - Map port profile → NetBox interface type

        Args:
            device_type: NetBox DeviceType instance
            parsed_ports: Ports dict from parsed profile
            port_profiles: PortProfiles dict from parsed profile
        """
        for port_name, port_config in parsed_ports.items():
            # Skip management ports (M1, eth0, mgmt0)
            if port_name.startswith("M") or port_name in ["eth0", "mgmt0"]:
                continue

            # Get port profile
            profile_name = port_config.get("profile")
            if not profile_name or profile_name not in port_profiles:
                continue

            profile = port_profiles[profile_name]

            # Determine speed for interface type mapping
            speed = self._get_port_speed(profile)
            if not speed:
                continue

            # Map to NetBox interface type
            interface_type = self.SPEED_TO_INTERFACE_TYPE.get(speed)
            if not interface_type:
                # Unknown speed - skip
                continue

            # Create or update interface template
            InterfaceTemplate.objects.get_or_create(
                device_type=device_type,
                name=port_name,  # Already in E1/N format
                defaults={"type": interface_type}
            )

    def _get_port_speed(self, port_profile: Dict[str, Any]) -> Optional[int]:
        """
        Extract port speed from port profile.

        Args:
            port_profile: Single port profile dict

        Returns:
            Speed in Gbps, or None if cannot determine
        """
        # Check Breakout profile
        if "breakout" in port_profile:
            default_mode = port_profile["breakout"].get("default", "")
            if default_mode:
                match = re.match(r'(\d+)x(\d+)[Gg]', default_mode)
                if match:
                    return int(match.group(2))

        # Check Speed profile
        if "speed" in port_profile:
            default_speed = port_profile["speed"].get("default", "")
            if default_speed:
                match = re.match(r'(\d+(?:\.\d+)?)[Gg]', default_speed)
                if match:
                    return int(float(match.group(1)))

        return None

    def create_breakout_options(self, port_profiles: Dict[str, Any]) -> None:
        """
        Create BreakoutOption records from breakout modes.

        Uses get_or_create() to avoid duplicates.

        Args:
            port_profiles: PortProfiles dict from parsed profile
        """
        for profile_name, profile_data in port_profiles.items():
            if "breakout" not in profile_data:
                continue

            breakout = profile_data["breakout"]
            supported = breakout.get("supported", {})

            for mode_name in supported.keys():
                # Parse mode name
                parsed = self.parse_breakout_mode_name(mode_name)

                # Infer optic type from from_speed
                optic_type = self._infer_optic_type(parsed["from_speed"])

                # Create if doesn't exist
                BreakoutOption.objects.get_or_create(
                    breakout_id=mode_name,
                    defaults={
                        "from_speed": parsed["from_speed"],
                        "logical_ports": parsed["logical_ports"],
                        "logical_speed": parsed["logical_speed"],
                        "optic_type": optic_type,
                    }
                )

    def _infer_optic_type(self, from_speed: int) -> str:
        """
        Infer optic type from native speed.

        Args:
            from_speed: Native port speed in Gbps

        Returns:
            Optic type string
        """
        if from_speed >= 800:
            return "QSFP-DD"
        elif from_speed >= 400:
            return "QSFP-DD"
        elif from_speed >= 100:
            return "QSFP28"
        elif from_speed >= 40:
            return "QSFP+"
        else:
            return "SFP28"
