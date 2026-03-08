"""
YAML Generation Service for Topology Plans (DIET-139)

This service generates Hedgehog wiring diagram YAML from NetBox inventory
(Devices, Interfaces, Cables) created by device generation.

IMPORTANT: This is an inventory-based export that reads actual NetBox objects,
NOT a plan-based generator. Port names come from Interface.name (authoritative).
"""

import re
from typing import Dict, Any, List
from collections import defaultdict
from django.core.exceptions import ValidationError

from dcim.models import Cable, Interface, Device

from ..models.topology_planning import TopologyPlan, DeviceTypeExtension
from ..choices import FabricTypeChoices


class YAMLGenerator:
    """
    Generates Hedgehog wiring YAML from NetBox inventory (DIET-139).

    This is an inventory-based generator that reads from:
    - Devices (for role detection)
    - Interfaces (for port names with breakout suffixes)
    - Cables (for connections)

    All created by DeviceGenerator and tagged with hedgehog_plan_id.
    """

    def __init__(self, plan: TopologyPlan, fabric: str = None):
        """
        Initialize the YAML generator for a specific plan.

        Args:
            plan: TopologyPlan instance to generate YAML for
            fabric: Optional fabric scope ('frontend' or 'backend'). When set,
                only CRDs for that fabric are emitted. When None, all managed
                fabrics (HEDGEHOG_MANAGED_SET) are included.
        """
        if fabric is not None and fabric not in FabricTypeChoices.HEDGEHOG_MANAGED_SET:
            raise ValueError(
                f"Invalid fabric '{fabric}'. Must be one of: "
                f"{sorted(FabricTypeChoices.HEDGEHOG_MANAGED_SET)}"
            )
        self.plan = plan
        self.fabric = fabric

    def generate(self) -> str:
        """
        Generate complete Hedgehog wiring YAML with all CRD types.

        CRD generation order matches Kubernetes/Hedgehog dependencies:
        1. Namespaces (VLANNamespace, IPv4Namespace)
        2. SwitchGroups (referenced by Switches)
        3. Switches (referenced by Connections)
        4. Servers (referenced by Connections)
        5. Connections (uses all above)

        Returns:
            YAML string containing all CRD types

        Raises:
            ValidationError: If cable topology or device configuration is invalid
        """
        import yaml

        # Step 1: Generate foundational CRDs
        vlannamespace_crds = self._generate_vlannamespaces()
        ipv4namespace_crds = self._generate_ipv4namespaces()

        # Step 2: Generate SwitchGroup CRDs (conditional)
        switchgroup_crds = self._generate_switchgroups()

        # Step 3: Generate device CRDs
        switch_crds = self._generate_switches()

        # Restrict Server CRDs: apply two-part filter.
        #
        # Surrogates (oob-mgmt fabric): always included — they appear as Server CRDs
        # by definition and don't require managed-switch connections to qualify.
        #
        # Regular servers (role='server'): constraint #3 — excluded from export if their
        # only connections are to surrogate/nonmanaged endpoints (DIET-254).
        # For fabric-scoped export: must connect to the target fabric.
        # For full-plan export: must connect to ANY managed fabric.
        surrogate_ids = set(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(self.plan.pk),
                custom_field_data__hedgehog_fabric__in=list(FabricTypeChoices.SURROGATE_ENDPOINT_SET),
            ).values_list('id', flat=True)
        )

        if self.fabric:
            effective_fabrics = [self.fabric]
        else:
            effective_fabrics = sorted(FabricTypeChoices.HEDGEHOG_MANAGED_SET)

        managed_switch_ids = set(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(self.plan.pk),
                custom_field_data__hedgehog_fabric__in=effective_fabrics,
            ).values_list('id', flat=True)
        )
        # Regular servers with at least one managed-switch connection.
        # _get_server_ids_for_fabric() also picks up surrogates cabled to those switches.
        connected_server_ids = self._get_server_ids_for_fabric(managed_switch_ids)
        if self.fabric:
            # Fabric-scoped: include only servers/surrogates connected to this fabric's switches.
            # Do NOT union global surrogate_ids — surrogates on other fabrics must be excluded.
            server_filter_ids = connected_server_ids
        else:
            # Full-plan: surrogates always included (constraint #3 / DIET-254);
            # regular servers need at least one managed-switch connection.
            server_filter_ids = surrogate_ids | (connected_server_ids - surrogate_ids)
        server_crds = self._generate_servers(filter_ids=server_filter_ids)

        # Step 4: Generate connection CRDs (existing logic, refactored)
        connection_crds = self._generate_connection_crds()

        # Step 5: Combine and order all documents
        documents = (
            sorted(vlannamespace_crds, key=lambda d: d['metadata']['name']) +
            sorted(ipv4namespace_crds, key=lambda d: d['metadata']['name']) +
            sorted(switchgroup_crds, key=lambda d: d['metadata']['name']) +
            sorted(switch_crds, key=lambda d: d['metadata']['name']) +
            sorted(server_crds, key=lambda d: d['metadata']['name']) +
            sorted(connection_crds, key=lambda d: d['metadata']['name'])
        )

        # Step 6: Build YAML with header
        # NOTE: hhfab validate is strict and treats '---' followed by comments as a document
        # For now, omit header comments to pass validation (can be added back after fixing hhfab parsing)
        header_comment = (
            f"# Generated by Hedgehog NetBox Plugin - Topology Planner (DIET-143)\n"
            f"# Plan: {self.plan.name}\n"
            f"# Customer: {self.plan.customer_name or 'N/A'}\n"
            f"# Source: NetBox Inventory (Devices, Interfaces, Cables)\n"
            f"# Total CRDs: {len(documents)}\n"
        )

        if not documents:
            return header_comment + "\n# No inventory found in NetBox for this plan\n"

        # Serialize each document separately with --- separator before each
        yaml_parts = []
        for doc in documents:
            yaml_str = yaml.dump(doc, default_flow_style=False, sort_keys=False)
            yaml_parts.append(f"---\n{yaml_str}")

        # Return documents without header comment (hhfab doesn't accept comments before CRDs)
        return "".join(yaml_parts)

    def _cable_to_link_data(self, cable: Cable) -> tuple:
        """
        Extract connection type and link data from a NetBox Cable (DIET-139).

        Args:
            cable: Cable instance from NetBox inventory

        Returns:
            Tuple of (connection_type, link_data_dict)
            - connection_type: 'unbundled' or 'fabric'
            - link_data_dict: Contains device/interface info for the link

        Raises:
            ValidationError: If cable has invalid topology
        """
        # Validate cable terminations (NetBox 4.x returns lists, not querysets)
        a_terminations = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
        b_terminations = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())

        # Check termination counts (single-termination only for MVP)
        if len(a_terminations) == 0 or len(b_terminations) == 0:
            raise ValidationError("Cable has missing terminations on one or both sides.")

        if len(a_terminations) > 1 or len(b_terminations) > 1:
            raise ValidationError(
                "Cable has multiple terminations on one side. Single-termination cables only."
            )

        # Check termination types (must be Interface objects)
        if not isinstance(a_terminations[0], Interface) or not isinstance(b_terminations[0], Interface):
            raise ValidationError("Cable terminations must be Interface objects.")

        iface_a = a_terminations[0]
        iface_b = b_terminations[0]

        # Get devices
        device_a = iface_a.device
        device_b = iface_b.device

        # Determine connection type and validate roles
        conn_type = self._determine_connection_type(device_a, device_b, cable.id)

        if conn_type == 'excluded':
            return ('excluded', {})

        if conn_type == 'unbundled':
            # Server-switch connection (server side is 'server' or 'surrogate' kind)
            if self._endpoint_kind(device_a) in ('server', 'surrogate'):
                server_device, server_iface = device_a, iface_a
                switch_device, switch_iface = device_b, iface_b
            else:
                server_device, server_iface = device_b, iface_b
                switch_device, switch_iface = device_a, iface_a

            return ('unbundled', {
                'server_device': server_device,
                'server_iface': server_iface,
                'switch_device': switch_device,
                'switch_iface': switch_iface,
            })

        elif conn_type == 'fabric':
            # Switch-switch connection (fabric)
            # Deterministic ordering: leaf/border before spine
            role_a = device_a.role.slug
            role_b = device_b.role.slug

            # Determine leaf vs spine
            if role_a in ('leaf', 'border') and role_b == 'spine':
                leaf_device, leaf_iface = device_a, iface_a
                spine_device, spine_iface = device_b, iface_b
            elif role_b in ('leaf', 'border') and role_a == 'spine':
                leaf_device, leaf_iface = device_b, iface_b
                spine_device, spine_iface = device_a, iface_a
            else:
                # Both same role - alphabetical by device name
                if device_a.name < device_b.name:
                    leaf_device, leaf_iface = device_a, iface_a
                    spine_device, spine_iface = device_b, iface_b
                else:
                    leaf_device, leaf_iface = device_b, iface_b
                    spine_device, spine_iface = device_a, iface_a

            return ('fabric', {
                'leaf_device': leaf_device,
                'leaf_iface': leaf_iface,
                'spine_device': spine_device,
                'spine_iface': spine_iface,
            })

        else:
            raise ValidationError(f"Unknown connection type: {conn_type}")

    def _create_unbundled_crd(self, link_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create unbundled Connection CRD from link data.

        Args:
            link_data: Dictionary with server_device, server_iface, switch_device, switch_iface

        Returns:
            Connection CRD dictionary
        """
        server_device = link_data['server_device']
        server_iface = link_data['server_iface']
        switch_device = link_data['switch_device']
        switch_iface = link_data['switch_iface']

        # Generate CRD name (based on real-world example: server-03-fe-nic-1--unbundled--leaf-01)
        # MUST include server interface name to ensure uniqueness when multiple ports connect to same switch
        crd_name = self._sanitize_name(
            f"{server_device.name}-{server_iface.name}--unbundled--{switch_device.name}"
        )

        return {
            'apiVersion': 'wiring.githedgehog.com/v1beta1',
            'kind': 'Connection',
            'metadata': {
                'name': crd_name,
                'namespace': 'default',
            },
            'spec': {
                'unbundled': {
                    'link': {
                        'server': {
                            'port': f"{server_device.name}/{server_iface.name}",
                        },
                        'switch': {
                            'port': f"{switch_device.name}/{switch_iface.name}",
                        },
                    },
                },
            },
        }

    def _create_fabric_crd(
        self,
        leaf_device: Device,
        spine_device: Device,
        links: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create fabric Connection CRD aggregating multiple links (DIET-139).

        Args:
            leaf_device: Leaf switch device
            spine_device: Spine switch device
            links: List of link_data dicts for this leaf-spine pair

        Returns:
            Connection CRD dictionary with aggregated fabric links

        Note:
            IP addresses (leaf.ip, spine.ip) are NOT included in the wiring diagram.
            Hedgehog's hhfab utility automatically injects IP addresses during the
            fabric build process. This is the standard workflow - HNP does not assign IPs.
        """
        # Generate CRD name (based on real-world example: spine-02--fabric--border-leaf-01)
        crd_name = self._sanitize_name(
            f"{spine_device.name}--fabric--{leaf_device.name}"
        )

        # Build fabric links array (one entry per cable)
        # NOTE: No IP addresses - hhfab injects them automatically during build
        fabric_links = []
        for link_data in links:
            fabric_links.append({
                'leaf': {
                    'port': f"{link_data['leaf_device'].name}/{link_data['leaf_iface'].name}",
                    # 'ip' field omitted - hhfab injects during build
                },
                'spine': {
                    'port': f"{link_data['spine_device'].name}/{link_data['spine_iface'].name}",
                    # 'ip' field omitted - hhfab injects during build
                },
            })

        return {
            'apiVersion': 'wiring.githedgehog.com/v1beta1',
            'kind': 'Connection',
            'metadata': {
                'name': crd_name,
                'namespace': 'default',
            },
            'spec': {
                'fabric': {
                    'links': fabric_links,
                },
            },
        }

    def _create_mclag_domain_crd(
        self,
        switch1_device: Device,
        switch2_device: Device,
        peer_links: List[Dict[str, Any]],
        session_links: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create MCLAG Domain Connection CRD from peer and session links (Issue #151).

        Args:
            switch1_device: First MCLAG peer switch
            switch2_device: Second MCLAG peer switch
            peer_links: List of link_data dicts for peer links
            session_links: List of link_data dicts for session links

        Returns:
            Connection CRD dictionary with mclagDomain spec
        """
        # Generate CRD name (format: switch1--mclag-domain--switch2)
        # Use alphabetical ordering for deterministic names
        if switch1_device.name < switch2_device.name:
            crd_name = self._sanitize_name(
                f"{switch1_device.name}--mclag-domain--{switch2_device.name}"
            )
        else:
            crd_name = self._sanitize_name(
                f"{switch2_device.name}--mclag-domain--{switch1_device.name}"
            )
            # Swap for consistency
            switch1_device, switch2_device = switch2_device, switch1_device

        # Build peer links array
        peer_links_list = []
        for link_data in peer_links:
            # Determine which interface belongs to which switch
            if link_data['device_a'] == switch1_device:
                port1 = f"{switch1_device.name}/{link_data['iface_a'].name}"
                port2 = f"{switch2_device.name}/{link_data['iface_b'].name}"
            else:
                port1 = f"{switch1_device.name}/{link_data['iface_b'].name}"
                port2 = f"{switch2_device.name}/{link_data['iface_a'].name}"

            peer_links_list.append({
                'switch1': {'port': port1},
                'switch2': {'port': port2}
            })

        # Build session links array
        session_links_list = []
        for link_data in session_links:
            # Determine which interface belongs to which switch
            if link_data['device_a'] == switch1_device:
                port1 = f"{switch1_device.name}/{link_data['iface_a'].name}"
                port2 = f"{switch2_device.name}/{link_data['iface_b'].name}"
            else:
                port1 = f"{switch1_device.name}/{link_data['iface_b'].name}"
                port2 = f"{switch2_device.name}/{link_data['iface_a'].name}"

            session_links_list.append({
                'switch1': {'port': port1},
                'switch2': {'port': port2}
            })

        return {
            'apiVersion': 'wiring.githedgehog.com/v1beta1',
            'kind': 'Connection',
            'metadata': {
                'name': crd_name,
                'namespace': 'default',
            },
            'spec': {
                'mclagDomain': {
                    'peerLinks': peer_links_list,
                    'sessionLinks': session_links_list
                }
            }
        }

    def _create_mclag_crd(
        self,
        server_device: Device,
        switch1_device: Device,
        switch2_device: Device,
        links: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create MCLAG Connection CRD for server with dual-homed MCLAG (Issue #151).

        Args:
            server_device: Server device
            switch1_device: First switch in MCLAG pair
            switch2_device: Second switch in MCLAG pair
            links: List of link_data dicts (must have exactly 2 links)

        Returns:
            Connection CRD dictionary with mclag spec
        """
        # Generate CRD name (format: server--mclag--switch1--switch2)
        # Use alphabetical ordering for switches
        if switch1_device.name < switch2_device.name:
            crd_name = self._sanitize_name(
                f"{server_device.name}--mclag--{switch1_device.name}--{switch2_device.name}"
            )
        else:
            crd_name = self._sanitize_name(
                f"{server_device.name}--mclag--{switch2_device.name}--{switch1_device.name}"
            )
            switch1_device, switch2_device = switch2_device, switch1_device

        # Build MCLAG links array
        mclag_links = []
        for link_data in links:
            server_iface = link_data['server_iface']
            switch_device = link_data['switch_device']
            switch_iface = link_data['switch_iface']

            mclag_links.append({
                'server': {
                    'port': f"{server_device.name}/{server_iface.name}"
                },
                'switch': {
                    'port': f"{switch_device.name}/{switch_iface.name}"
                }
            })

        return {
            'apiVersion': 'wiring.githedgehog.com/v1beta1',
            'kind': 'Connection',
            'metadata': {
                'name': crd_name,
                'namespace': 'default',
            },
            'spec': {
                'mclag': {
                    'links': mclag_links
                }
            }
        }

    def _create_eslag_crd(
        self,
        server_device: Device,
        links: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create ESLAG Connection CRD for server with ESLAG redundancy (Issue #151).

        Args:
            server_device: Server device
            links: List of link_data dicts (2-4 links to different switches)

        Returns:
            Connection CRD dictionary with eslag spec
        """
        # Collect unique switch devices from links
        switch_names = sorted(set(link_data['switch_device'].name for link_data in links))

        # Generate CRD name (format: server--eslag--switch1--switch2--...)
        crd_name = self._sanitize_name(
            f"{server_device.name}--eslag--{('--').join(switch_names)}"
        )

        # Build ESLAG links array
        eslag_links = []
        for link_data in links:
            server_iface = link_data['server_iface']
            switch_device = link_data['switch_device']
            switch_iface = link_data['switch_iface']

            eslag_links.append({
                'server': {
                    'port': f"{server_device.name}/{server_iface.name}"
                },
                'switch': {
                    'port': f"{switch_device.name}/{switch_iface.name}"
                }
            })

        return {
            'apiVersion': 'wiring.githedgehog.com/v1beta1',
            'kind': 'Connection',
            'metadata': {
                'name': crd_name,
                'namespace': 'default',
            },
            'spec': {
                'eslag': {
                    'links': eslag_links
                }
            }
        }

    def _create_bundled_crd(
        self,
        server_device: Device,
        switch_device: Device,
        links: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create Bundled Connection CRD for server with LACP bond to single switch (Issue #151).

        Args:
            server_device: Server device
            switch_device: Switch device
            links: List of link_data dicts (multiple links to same switch)

        Returns:
            Connection CRD dictionary with bundled spec
        """
        # Generate CRD name (format: server--bundled--switch)
        crd_name = self._sanitize_name(
            f"{server_device.name}--bundled--{switch_device.name}"
        )

        # Build bundled links array
        bundled_links = []
        for link_data in links:
            server_iface = link_data['server_iface']
            switch_iface = link_data['switch_iface']

            bundled_links.append({
                'server': {
                    'port': f"{server_device.name}/{server_iface.name}"
                },
                'switch': {
                    'port': f"{switch_device.name}/{switch_iface.name}"
                }
            })

        return {
            'apiVersion': 'wiring.githedgehog.com/v1beta1',
            'kind': 'Connection',
            'metadata': {
                'name': crd_name,
                'namespace': 'default',
            },
            'spec': {
                'bundled': {
                    'links': bundled_links
                }
            }
        }

    def _endpoint_kind(self, device: Device) -> str:
        """Classify a device endpoint for CRD routing (DIET-250).

        Returns:
            'managed_switch' - frontend/backend switch, appears in Switch CRDs
            'server'         - role='server' with no fabric, appears in Server CRDs
            'surrogate'      - oob-mgmt switch, appears as Server CRD surrogate
            'excluded'       - in-band-mgmt, network-mgmt, legacy-oob, or unrecognized
        """
        fabric = device.custom_field_data.get('hedgehog_fabric', '')
        if fabric in FabricTypeChoices.HEDGEHOG_MANAGED_SET:
            return 'managed_switch'
        if fabric in FabricTypeChoices.SURROGATE_ENDPOINT_SET:
            return 'surrogate'
        if not fabric and device.role.slug == 'server':
            return 'server'
        return 'excluded'

    def _determine_connection_type(self, device_a: Device, device_b: Device, cable_id: int) -> str:
        """
        Determine Hedgehog connection type from endpoint kinds (DIET-139, DIET-250).

        Args:
            device_a: First device
            device_b: Second device
            cable_id: Cable ID for logging

        Returns:
            'unbundled' for server↔managed_switch
            'fabric'    for managed_switch↔managed_switch
            'excluded'  for all other combinations (silent skip — no ValidationError)
        """
        kind_a = self._endpoint_kind(device_a)
        kind_b = self._endpoint_kind(device_b)

        # server/surrogate↔managed_switch → unbundled
        if kind_a in ('server', 'surrogate') and kind_b == 'managed_switch':
            return 'unbundled'
        if kind_b in ('server', 'surrogate') and kind_a == 'managed_switch':
            return 'unbundled'

        # managed_switch↔managed_switch → fabric
        if kind_a == 'managed_switch' and kind_b == 'managed_switch':
            return 'fabric'

        # Everything else (surrogate↔surrogate, server↔surrogate, server↔server, excluded) — silent skip
        return 'excluded'

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name to be DNS-label safe.

        DNS labels must:
        - Be lowercase
        - Contain only alphanumeric characters and hyphens
        - Start and end with alphanumeric characters
        - Be at most 63 characters long

        Args:
            name: Name to sanitize

        Returns:
            DNS-label safe name
        """
        # Convert to lowercase
        sanitized = name.lower()

        # Replace any non-alphanumeric (except hyphens) with hyphens
        sanitized = re.sub(r'[^a-z0-9-]', '-', sanitized)

        # Collapse multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)

        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')

        # Truncate to 63 characters
        if len(sanitized) > 63:
            sanitized = sanitized[:63].rstrip('-')

        return sanitized

    def _generate_unique_crd_name(self, device: Device, existing_names: set) -> str:
        """
        Generate unique DNS-1123 compliant name with collision avoidance.

        Strategy:
        1. Sanitize device name to DNS-1123 format
        2. If unique, use as-is
        3. If collision, append device PK for guaranteed uniqueness

        Args:
            device: NetBox Device object (need name and pk)
            existing_names: Set of already-used CRD names (mutated by this method)

        Returns:
            Unique DNS-1123 label (max 63 chars)

        Example:
            Device(name="Server_01", pk=123) → "server-01"
            Device(name="Server-01", pk=124) (collision) → "server-01-124"
        """
        sanitized = self._sanitize_name(device.name)

        # If unique, return as-is
        if sanitized not in existing_names:
            existing_names.add(sanitized)
            return sanitized

        # Collision detected - add device PK suffix for guaranteed uniqueness
        suffix = str(device.pk)
        unique_name = f"{sanitized}-{suffix}"

        # Truncate if needed (max 63 chars for DNS label)
        if len(unique_name) > 63:
            # Keep suffix intact, truncate base
            max_base = 63 - len(suffix) - 1  # -1 for hyphen
            unique_name = f"{sanitized[:max_base]}-{suffix}"

        existing_names.add(unique_name)
        return unique_name

    def _generate_port_configuration(self, switch_class: 'PlanSwitchClass') -> Dict[str, Dict[str, Any]]:
        """
        Generate portBreakouts for a switch class using hhfab-compatible key format.

        All ports (breakout and native) are represented in portBreakouts with
        'E1/<port>' keys, matching the hhfab wiring schema. portSpeeds and
        portAutoNegs are not emitted; hhfab derives speeds from portBreakouts.

        Args:
            switch_class: PlanSwitchClass instance

        Returns:
            Dict with keys: portBreakouts, portSpeeds, portAutoNegs
            (portSpeeds and portAutoNegs are always empty; retained for
            compatibility with the existing emit check in _generate_switches)

        Example output for fe-gpu-leaf (odd ports = 4x200G, even ports = 1x800G):
            {
                'portBreakouts': {'E1/1': '4x200g', 'E1/3': '4x200g', ...,
                                  'E1/2': '1x800G', 'E1/4': '1x800G', ...},
                'portSpeeds': {},
                'portAutoNegs': {}
            }
        """
        from ..models.topology_planning import SwitchPortZone

        port_breakouts = {}

        # Query all port zones for this switch class
        zones = SwitchPortZone.objects.filter(switch_class=switch_class).order_by('priority')

        for zone in zones:
            # Parse port_spec to get list of physical ports
            # Formats: "1-32", "1-63:2" (odds), "2-64:2" (evens)
            ports = self._parse_port_spec(zone.port_spec)

            if zone.breakout_option:
                # Normalise breakout_id to hhfab-canonical form: lowercase 'x', uppercase 'G'
                # e.g. "2x400g" → "2x400G", "4x200g" → "4x200G", "1x800g" → "1x800G"
                # hhfab profile matching is case-sensitive on the trailing 'G'.
                breakout_id = zone.breakout_option.breakout_id.replace('g', 'G')

                # All ports go into portBreakouts with 'E1/<port>' key.
                # 1x entries (native speed) use the same format as multi-lane breakouts.
                for port in ports:
                    port_breakouts[f"E1/{port}"] = breakout_id
            else:
                # No breakout_option configured: emit native speed as 1x<N>G.
                native_speed = switch_class.device_type_extension.native_speed
                for port in ports:
                    port_breakouts[f"E1/{port}"] = f"1x{native_speed}G"

        return {
            'portBreakouts': port_breakouts,
            'portSpeeds': {},
            'portAutoNegs': {}
        }

    def _parse_port_spec(self, port_spec: str) -> List[int]:
        """
        Parse port_spec string into list of port numbers.

        Formats:
        - "1-32" → [1, 2, 3, ..., 32]
        - "1-63:2" → [1, 3, 5, ..., 63] (odds)
        - "2-64:2" → [2, 4, 6, ..., 64] (evens)
        - "1,5,9-12" → [1, 5, 9, 10, 11, 12]

        Args:
            port_spec: Port specification string

        Returns:
            List of port numbers
        """
        ports = []

        # Split by comma for multiple ranges
        parts = port_spec.split(',')

        for part in parts:
            part = part.strip()

            # Check for range with step (e.g., "1-63:2")
            if ':' in part:
                range_part, step = part.split(':')
                step = int(step)
            else:
                range_part = part
                step = 1

            # Check for range (e.g., "1-32")
            if '-' in range_part:
                start, end = range_part.split('-')
                start, end = int(start), int(end)
                ports.extend(range(start, end + 1, step))
            else:
                # Single port
                ports.append(int(range_part))

        return sorted(ports)

    def _map_netbox_role_to_hedgehog(self, device: Device) -> str:
        """
        Map NetBox device role to Hedgehog switch role.

        Priority:
        1. If device.custom_field_data['hedgehog_role'] is set, use it
        2. Otherwise map from device.role.slug

        Args:
            device: NetBox Device object

        Returns:
            Hedgehog role name (spine, server-leaf, border-leaf, mixed-leaf, virtual-edge)
        """
        # First check if hedgehog_role is explicitly set in custom fields
        hedgehog_role = device.custom_field_data.get('hedgehog_role')
        if hedgehog_role:
            return hedgehog_role

        # Fall back to role slug mapping
        mapping = {
            'spine': 'spine',
            'leaf': 'server-leaf',
            'border': 'border-leaf',
        }
        return mapping.get(device.role.slug, 'server-leaf')

    def _generate_switches(self) -> List[Dict[str, Any]]:
        """
        Generate Switch CRDs from NetBox Devices with switch roles (Issue #151).

        Reads:
        - Device.name, Device.role
        - custom_field_data['boot_mac', 'hedgehog_class']
        - device_type.devicetypeextension.hedgehog_profile_name
        - PlanSwitchClass.groups, redundancy_type, redundancy_group

        Returns:
            List of Switch CRD dicts with spec: {role, profile, boot, groups, redundancy, ecmp}
        """
        from ..models.topology_planning import PlanSwitchClass

        switch_crds = []
        existing_names = set()

        # Filter by plan ID, presence of hedgehog_role, and Hedgehog-managed fabric only.
        # Management fabrics (oob-mgmt, in-band-mgmt, network-mgmt, legacy oob) are
        # tracked in NetBox for inventory purposes but excluded from wiring YAML export.
        # When self.fabric is set, restrict to that single fabric.
        effective_fabrics = [self.fabric] if self.fabric else sorted(FabricTypeChoices.HEDGEHOG_MANAGED_SET)
        switches = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric__in=effective_fabrics,
            custom_field_data__hedgehog_role__isnull=False
        ).exclude(
            custom_field_data__hedgehog_role=''
        ).select_related('device_type', 'role').order_by('id')

        for switch in switches:
            # Get unique CRD name (collision-safe)
            crd_name = self._generate_unique_crd_name(switch, existing_names)

            # Get profile name from device type extension
            try:
                device_type_ext = switch.device_type.hedgehog_metadata
                profile_name = device_type_ext.hedgehog_profile_name
                if not profile_name:
                    raise ValidationError(
                        f"Switch {switch.name} device type '{switch.device_type.model}' "
                        f"missing hedgehog_profile_name in DeviceTypeExtension"
                    )
            except DeviceTypeExtension.DoesNotExist:
                raise ValidationError(
                    f"Switch {switch.name} device type '{switch.device_type.model}' "
                    f"has no DeviceTypeExtension record"
                )

            # Get boot MAC from custom field
            boot_mac = switch.custom_field_data.get('boot_mac')
            if not boot_mac:
                raise ValidationError(
                    f"Switch {switch.name} missing boot_mac in custom_field_data"
                )

            # Build base spec
            spec = {
                'role': self._map_netbox_role_to_hedgehog(switch),
                'profile': profile_name,
                'boot': {
                    'mac': boot_mac
                }
            }

            # Add MCLAG/ESLAG fields (Issue #151)
            # Read hedgehog_class custom field to look up PlanSwitchClass
            hedgehog_class_id = switch.custom_field_data.get('hedgehog_class')
            if hedgehog_class_id:
                try:
                    switch_class = PlanSwitchClass.objects.get(
                        plan=self.plan,
                        switch_class_id=hedgehog_class_id
                    )

                    # Add groups field (if set)
                    if switch_class.groups:
                        spec['groups'] = switch_class.groups

                    # Add redundancy field (if redundancy_type is set)
                    if switch_class.redundancy_type:
                        spec['redundancy'] = {
                            'type': switch_class.redundancy_type
                        }
                        if switch_class.redundancy_group:
                            spec['redundancy']['group'] = switch_class.redundancy_group

                except PlanSwitchClass.DoesNotExist:
                    # hedgehog_class is set but doesn't match any PlanSwitchClass
                    # This is a data consistency error - log but continue
                    pass

            # Add port configuration fields (DIET-151)
            # Generate portBreakouts, portSpeeds, portAutoNegs from SwitchPortZone data
            if hedgehog_class_id:
                try:
                    switch_class = PlanSwitchClass.objects.get(
                        plan=self.plan,
                        switch_class_id=hedgehog_class_id
                    )
                    port_config = self._generate_port_configuration(switch_class)
                    if port_config['portBreakouts']:
                        spec['portBreakouts'] = port_config['portBreakouts']
                    if port_config['portSpeeds']:
                        spec['portSpeeds'] = port_config['portSpeeds']
                    if port_config['portAutoNegs']:
                        spec['portAutoNegs'] = port_config['portAutoNegs']
                except PlanSwitchClass.DoesNotExist:
                    pass

            # Add ecmp field (always empty dict per schema)
            spec['ecmp'] = {}

            # MVP: Omit VTEPIP (Phase 2: VPC integration)

            switch_crds.append({
                'apiVersion': 'wiring.githedgehog.com/v1beta1',
                'kind': 'Switch',
                'metadata': {
                    'name': crd_name,
                    'namespace': 'default'
                },
                'spec': spec
            })

        return switch_crds

    def _get_server_ids_for_fabric(self, managed_switch_ids: set) -> set:
        """Return the set of server device IDs connected to the given switch IDs via cables.

        Uses CableTermination to traverse cable endpoints without loading full Cable objects.
        A server is included if it has at least one cable whose opposite endpoint lands on
        one of the managed switches.

        Args:
            managed_switch_ids: set of Device PKs for the target-fabric switches

        Returns:
            set of Device PKs for servers with at least one connection to those switches
        """
        from django.contrib.contenttypes.models import ContentType
        from dcim.models import CableTermination

        interface_ct = ContentType.objects.get_for_model(Interface)

        # Interface IDs on the target-fabric switches
        switch_iface_ids = set(
            Interface.objects.filter(
                device_id__in=managed_switch_ids
            ).values_list('id', flat=True)
        )
        if not switch_iface_ids:
            return set()

        # Cable IDs where at least one end lands on a target-fabric switch interface
        cable_ids = set(
            CableTermination.objects.filter(
                termination_type=interface_ct,
                termination_id__in=switch_iface_ids,
            ).values_list('cable_id', flat=True)
        )
        if not cable_ids:
            return set()

        # Interface IDs on the OTHER ends of those cables (excluding the switch side)
        server_side_iface_ids = (
            CableTermination.objects.filter(
                cable_id__in=cable_ids,
                termination_type=interface_ct,
            ).exclude(
                termination_id__in=switch_iface_ids,
            ).values_list('termination_id', flat=True)
        )

        # Device IDs where endpoint is a regular server or an oob-mgmt surrogate
        from django.db.models import Q
        return set(
            Interface.objects.filter(
                id__in=server_side_iface_ids,
            ).filter(
                Q(device__role__slug='server') |
                Q(device__custom_field_data__hedgehog_fabric__in=list(FabricTypeChoices.SURROGATE_ENDPOINT_SET))
            ).values_list('device_id', flat=True)
        )

    def _generate_servers(self, filter_ids=None) -> List[Dict[str, Any]]:
        """
        Generate Server CRDs from NetBox Devices with server role (DIET-173 Phase 5).

        Includes Module metadata (NIC ModuleTypes with transceiver attributes)
        for visibility and documentation purposes.

        NOTE: Server CRD spec includes:
        - description (optional)
        - profile (optional, not used in MVP)
        Server interfaces are NOT included in Server CRD spec.
        Interfaces are referenced via Connection CRDs (unbundled/bundled/mclag).

        Reads:
        - Device.name, Device.comments

        Returns:
            List of Server CRD dicts with spec: {description}
        """
        server_crds = []
        existing_names = set()

        from django.db.models import Q
        servers = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
        ).filter(
            Q(role__slug='server') |
            Q(custom_field_data__hedgehog_fabric__in=list(FabricTypeChoices.SURROGATE_ENDPOINT_SET))
        )
        if filter_ids is not None:
            servers = servers.filter(id__in=filter_ids)
        servers = servers.order_by('id')

        for server in servers:
            # Get unique CRD name (collision-safe)
            crd_name = self._generate_unique_crd_name(server, existing_names)

            # Build spec with description
            spec = {}
            if server.comments:
                spec['description'] = server.comments

            server_crds.append({
                'apiVersion': 'wiring.githedgehog.com/v1beta1',
                'kind': 'Server',
                'metadata': {
                    'name': crd_name,
                    'namespace': 'default'
                },
                'spec': spec
            })

        return server_crds

    def _generate_connection_crds(self) -> List[Dict[str, Any]]:
        """
        Generate Connection CRDs from NetBox Cables with MCLAG/ESLAG/bundled support (Issue #151).

        Routes cables to appropriate CRD types based on hedgehog_zone classification:
        - 'peer' + 'session' → mclagDomain
        - 'server' → mclag/eslag/bundled (grouped by server)
        - fabric (switch↔switch, no zone) → fabric
        - unbundled (server↔switch, single link) → unbundled

        Returns:
            List of Connection CRD dicts (all types)
        """
        # Query cables from NetBox inventory (order by ID for determinism)
        cables = Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).order_by('id')

        # Build set of switch device IDs that are Hedgehog-managed (frontend/backend).
        # Cables that touch an unmanaged switch endpoint are excluded from Connection CRDs.
        # When self.fabric is set, restrict to that single fabric.
        effective_fabrics = [self.fabric] if self.fabric else sorted(FabricTypeChoices.HEDGEHOG_MANAGED_SET)
        _managed_switch_ids = set(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(self.plan.pk),
                custom_field_data__hedgehog_fabric__in=effective_fabrics,
            ).values_list('id', flat=True)
        )

        def _endpoint_is_allowed(device: Device) -> bool:
            """Return True if device may appear in a Connection CRD endpoint.

            Uses _endpoint_kind() as the single classification authority (DIET-250).
            - managed_switch: allowed only if in the scoped _managed_switch_ids set
            - server: always allowed
            - surrogate: always allowed (oob-mgmt devices emit as Server CRD surrogates)
            - excluded: never allowed
            """
            kind = self._endpoint_kind(device)
            if kind == 'managed_switch':
                return device.id in _managed_switch_ids
            return kind in ('server', 'surrogate')

        # Classify cables by zone and topology
        mclag_domain_links = defaultdict(lambda: {'peer': [], 'session': []})  # (sw1, sw2) -> {peer: [...], session: [...]}
        server_links = defaultdict(list)  # server_device -> [link_data]
        fabric_links_by_pair = defaultdict(list)  # (leaf, spine) -> [link_data]
        unbundled_crds = []

        for cable in cables:
            try:
                # Get cable terminations
                a_terminations = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
                b_terminations = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())

                if not a_terminations or not b_terminations:
                    continue

                iface_a = a_terminations[0]
                iface_b = b_terminations[0]
                device_a = iface_a.device
                device_b = iface_b.device

                # Skip cables that touch an unmanaged switch endpoint.
                # Servers are always allowed; peer/session/fabric-only cables between
                # managed switches are allowed; management-fabric cables are excluded.
                if not _endpoint_is_allowed(device_a) or not _endpoint_is_allowed(device_b):
                    continue

                # Get hedgehog_zone classification
                zone = cable.custom_field_data.get('hedgehog_zone', '').lower()

                # Route by zone
                if zone == 'peer':
                    # MCLAG domain peer link
                    switch_pair = tuple(sorted([device_a.name, device_b.name]))
                    mclag_domain_links[switch_pair]['peer'].append({
                        'device_a': device_a,
                        'device_b': device_b,
                        'iface_a': iface_a,
                        'iface_b': iface_b
                    })

                elif zone == 'session':
                    # MCLAG domain session link
                    switch_pair = tuple(sorted([device_a.name, device_b.name]))
                    mclag_domain_links[switch_pair]['session'].append({
                        'device_a': device_a,
                        'device_b': device_b,
                        'iface_a': iface_a,
                        'iface_b': iface_b
                    })

                elif zone == 'server':
                    # Server connection (mclag/eslag/bundled - determine later by grouping)
                    # Only handle regular server↔managed_switch; surrogate on zone='server' is excluded
                    kind_a = self._endpoint_kind(device_a)
                    kind_b = self._endpoint_kind(device_b)
                    if kind_a == 'server' and kind_b == 'managed_switch':
                        server_device, server_iface = device_a, iface_a
                        switch_device, switch_iface = device_b, iface_b
                    elif kind_b == 'server' and kind_a == 'managed_switch':
                        server_device, server_iface = device_b, iface_b
                        switch_device, switch_iface = device_a, iface_a
                    else:
                        continue  # surrogate on wrong zone, server↔surrogate, etc.

                    server_links[server_device].append({
                        'server_iface': server_iface,
                        'switch_device': switch_device,
                        'switch_iface': switch_iface
                    })

                elif zone == 'oob':
                    # OOB management connection: managed_switch↔surrogate → unbundled CRD
                    # surrogate↔surrogate and server↔surrogate are silently excluded
                    kind_a = self._endpoint_kind(device_a)
                    kind_b = self._endpoint_kind(device_b)
                    if kind_a == 'managed_switch' and kind_b == 'surrogate':
                        link_data = {
                            'server_device': device_b, 'server_iface': iface_b,
                            'switch_device': device_a, 'switch_iface': iface_a,
                        }
                    elif kind_b == 'managed_switch' and kind_a == 'surrogate':
                        link_data = {
                            'server_device': device_a, 'server_iface': iface_a,
                            'switch_device': device_b, 'switch_iface': iface_b,
                        }
                    else:
                        continue  # surrogate↔surrogate, server↔surrogate, etc.
                    unbundled_crds.append(self._create_unbundled_crd(link_data))

                else:
                    # No zone classification - use endpoint-kind-based detection
                    conn_type, link_data = self._cable_to_link_data(cable)

                    if conn_type == 'excluded':
                        continue
                    elif conn_type == 'unbundled':
                        unbundled_crds.append(self._create_unbundled_crd(link_data))
                    elif conn_type == 'fabric':
                        device_pair = (link_data['leaf_device'], link_data['spine_device'])
                        fabric_links_by_pair[device_pair].append(link_data)

            except ValidationError as e:
                raise ValidationError(f"Cable {cable.id}: {str(e)}")

        # Generate MCLAG domain CRDs
        mclag_domain_crds = []
        for switch_pair, links in mclag_domain_links.items():
            # Get switch devices by name (sorted alphabetically)
            switch1 = Device.objects.get(name=switch_pair[0])
            switch2 = Device.objects.get(name=switch_pair[1])

            mclag_domain_crds.append(self._create_mclag_domain_crd(
                switch1, switch2,
                links['peer'], links['session']
            ))

        # Generate server connection CRDs (mclag/eslag/bundled/unbundled)
        server_conn_crds = []
        for server_device, links in server_links.items():
            if len(links) == 1:
                # Single link → unbundled (should be rare with zone='server')
                link_data = links[0]
                crd_name = self._sanitize_name(
                    f"{server_device.name}--unbundled--{link_data['switch_device'].name}"
                )
                server_conn_crds.append({
                    'apiVersion': 'wiring.githedgehog.com/v1beta1',
                    'kind': 'Connection',
                    'metadata': {'name': crd_name, 'namespace': 'default'},
                    'spec': {
                        'unbundled': {
                            'link': {
                                'server': {'port': f"{server_device.name}/{link_data['server_iface'].name}"},
                                'switch': {'port': f"{link_data['switch_device'].name}/{link_data['switch_iface'].name}"}
                            }
                        }
                    }
                })

            elif len(links) == 2:
                # 2 links → check if same switch (bundled) or different switches (mclag)
                switch1 = links[0]['switch_device']
                switch2 = links[1]['switch_device']

                if switch1 == switch2:
                    # Same switch → bundled
                    server_conn_crds.append(self._create_bundled_crd(server_device, switch1, links))
                else:
                    # Different switches → mclag
                    server_conn_crds.append(self._create_mclag_crd(server_device, switch1, switch2, links))

            elif len(links) > 2:
                # 3+ links → check if same switch (bundled) or multiple switches (eslag)
                unique_switches = set(link['switch_device'] for link in links)

                if len(unique_switches) == 1:
                    # All same switch → bundled
                    server_conn_crds.append(self._create_bundled_crd(server_device, links[0]['switch_device'], links))
                else:
                    # Multiple switches → eslag
                    server_conn_crds.append(self._create_eslag_crd(server_device, links))

        # Generate fabric CRDs
        fabric_crds = []
        for (leaf_device, spine_device), links in fabric_links_by_pair.items():
            fabric_crds.append(self._create_fabric_crd(leaf_device, spine_device, links))

        return mclag_domain_crds + server_conn_crds + unbundled_crds + fabric_crds

    def _generate_vlannamespaces(self) -> List[Dict[str, Any]]:
        """
        Generate VLANNamespace CRDs for VLAN range allocation.

        MVP: Returns single "default" namespace with range 1000-2999.
        Future: Read from TopologyPlan.vlan_ranges or user configuration.

        Returns:
            List with one VLANNamespace CRD dict
        """
        return [{
            'apiVersion': 'wiring.githedgehog.com/v1beta1',
            'kind': 'VLANNamespace',
            'metadata': {
                'name': 'default',
                'namespace': 'default'
            },
            'spec': {
                'ranges': [
                    {'from': 1000, 'to': 2999}
                ]
            }
        }]

    def _generate_ipv4namespaces(self) -> List[Dict[str, Any]]:
        """
        Generate IPv4Namespace CRDs for IP subnet allocation.

        MVP: Returns single "default" namespace with 10.0.0.0/16 (matches production sample).
        Future: Read from TopologyPlan.ip_ranges or user configuration.

        Returns:
            List with one IPv4Namespace CRD dict
        """
        return [{
            'apiVersion': 'vpc.githedgehog.com/v1beta1',
            'kind': 'IPv4Namespace',
            'metadata': {
                'name': 'default',
                'namespace': 'default'
            },
            'spec': {
                'subnets': ['10.0.0.0/16']  # Match production sample
            }
        }]

    def _generate_switchgroups(self) -> List[Dict[str, Any]]:
        """
        Generate SwitchGroup CRDs for MCLAG/ESLAG redundancy groups (Issue #151).

        Reads:
        - PlanMCLAGDomain.switch_group_name

        Returns:
            List of SwitchGroup CRD dicts with empty spec: {}

        NOTE: Per authoritative Hedgehog schema, SwitchGroup has EMPTY spec (marker object only).
        Switch membership is tracked via Switch CRD spec.groups field, NOT in SwitchGroup.
        """
        from ..models.topology_planning import PlanMCLAGDomain

        switchgroup_crds = []

        # Query MCLAG domains for this plan
        domains = PlanMCLAGDomain.objects.filter(plan=self.plan).order_by('switch_group_name')

        for domain in domains:
            # Validate DNS-1123 compliance (should already be validated by model.clean())
            if not domain.switch_group_name:
                raise ValidationError(
                    f"PlanMCLAGDomain {domain.domain_id} missing switch_group_name"
                )

            switchgroup_crds.append({
                'apiVersion': 'wiring.githedgehog.com/v1beta1',
                'kind': 'SwitchGroup',
                'metadata': {
                    'name': domain.switch_group_name,
                    'namespace': 'default'
                },
                'spec': {}  # Empty spec per authoritative schema
            })

        return switchgroup_crds


def generate_yaml_for_plan(plan: TopologyPlan, fabric: str = None) -> str:
    """
    Convenience function to generate YAML for a topology plan (DIET-139).

    This function reads from NetBox inventory (Devices, Interfaces, Cables)
    created by DeviceGenerator, NOT from the plan's class/connection definitions.

    Args:
        plan: TopologyPlan instance
        fabric: Optional fabric scope ('frontend' or 'backend'). When set, only
            CRDs for that fabric are emitted. When None, all managed fabrics
            (HEDGEHOG_MANAGED_SET) are included.

    Returns:
        YAML string containing CRDs from NetBox inventory

    Raises:
        ValidationError: If cable topology is invalid
        ValueError: If fabric is not a valid managed fabric name
    """
    generator = YAMLGenerator(plan, fabric=fabric)
    return generator.generate()
