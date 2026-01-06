"""
Fabric profile import utilities (DIET-144).

Provides parsing and import capabilities for Hedgehog Fabric switch profiles.
"""

import re
import requests
from typing import Dict, List, Any, Optional
from django.core.exceptions import ValidationError


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
