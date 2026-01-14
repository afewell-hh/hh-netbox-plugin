"""
Device generation service for topology planning.

Creates NetBox Devices, Interfaces, and Cables from a TopologyPlan.
"""

import math
from dataclasses import dataclass
from typing import Iterable

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from dcim.choices import DeviceStatusChoices, InterfaceTypeChoices, SiteStatusChoices
from dcim.models import Cable, Device, DeviceRole, Interface, Site
from extras.models import Tag

from netbox_hedgehog.choices import (
    ConnectionDistributionChoices,
    DeviceCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortTypeChoices,
    PortZoneTypeChoices,
    GenerationStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    GenerationState,
    NamingTemplate,
    PlanServerConnection,
    PlanSwitchClass,
    TopologyPlan,
)
from netbox_hedgehog.services.port_allocator import PortAllocatorV2
from netbox_hedgehog.services.port_specification import PortSpecification
from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot


@dataclass(frozen=True)
class GenerationResult:
    device_count: int
    interface_count: int
    cable_count: int


class DeviceGenerator:
    """
    Generate NetBox devices/interfaces/cables from a TopologyPlan.
    """

    DEFAULT_SITE_NAME = "Hedgehog"
    DEFAULT_SITE_SLUG = "hedgehog"
    DEFAULT_TAG_SLUG = "hedgehog-generated"
    DEFAULT_ROLE_COLOR = "9e9e9e"

    def __init__(self, plan: TopologyPlan, site: Site | None = None, logger=None):
        self.plan = plan
        self.site = site or self._ensure_default_site()
        self.tag = self._ensure_default_tag()
        self.port_allocator = PortAllocatorV2()
        self.logger = logger

        self._device_cache: dict[str, Device] = {}
        self._interface_cache: dict[tuple[int, str], Interface] = {}
        self._rail_count_cache: dict[tuple[str, str], int] = {}  # (server_class_id, switch_class_id) -> total_rails

    def _cleanup_generated_objects(self) -> None:
        """
        Delete all previously generated objects for this plan.

        Deletes Cables first (to avoid termination protection issues), then
        Devices (which cascades to Interfaces). All deletions are scoped to
        this specific plan using hedgehog_plan_id.
        """
        from dcim.models import Cable

        # IMPORTANT: Delete cables FIRST before devices to avoid termination
        # protection issues in NetBox. Cables must be plan-scoped to avoid
        # deleting cables from other plans.
        cables_to_delete = Cable.objects.filter(
            tags__slug=self.DEFAULT_TAG_SLUG,
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        )
        cable_count = cables_to_delete.count()
        if cable_count > 0:
            cables_to_delete.delete()

        # Now delete devices for this plan (interfaces will cascade)
        devices_to_delete = Device.objects.filter(
            tags__slug=self.DEFAULT_TAG_SLUG,
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        )
        device_count = devices_to_delete.count()
        if device_count > 0:
            devices_to_delete.delete()

    @transaction.atomic
    def generate_all(self) -> GenerationResult:
        """
        Generate devices, interfaces, and cables for the plan.
        Deletes any previously generated objects before creating new ones.
        """
        # Milestone 1: Starting device generation
        if self.logger:
            self.logger.info(f"Starting device generation for plan: {self.plan.name}")

        # Milestone 2: Cleaning up old objects
        if self.logger:
            self.logger.info("Cleaning up previously generated objects")
        self._cleanup_generated_objects()

        devices = []
        interfaces = []
        cables = []

        # Milestone 3: Creating switch devices
        if self.logger:
            self.logger.info("Creating switch devices")
        switch_devices = self._create_switch_devices(devices)

        # Milestone 4: Creating server devices
        if self.logger:
            self.logger.info("Creating server devices")
        server_devices = self._create_server_devices(devices)

        # Milestone 5: Creating connections (interfaces and cables)
        if self.logger:
            self.logger.info("Creating connections (interfaces and cables)")
        interfaces, cables = self._create_connections(
            switch_devices,
            server_devices,
        )

        # Milestone 6: Tagging and finalizing
        if self.logger:
            self.logger.info("Tagging objects and finalizing generation")
        self._tag_objects(devices, interfaces, cables)
        self._upsert_generation_state(
            device_count=len(devices),
            interface_count=len(interfaces),
            cable_count=len(cables),
        )

        return GenerationResult(
            device_count=len(devices),
            interface_count=len(interfaces),
            cable_count=len(cables),
        )

    def _ensure_default_site(self) -> Site:
        site, _ = Site.objects.get_or_create(
            slug=self.DEFAULT_SITE_SLUG,
            defaults={
                'name': self.DEFAULT_SITE_NAME,
                'status': SiteStatusChoices.STATUS_ACTIVE,
            },
        )
        return site

    def _ensure_default_tag(self) -> Tag:
        tag, _ = Tag.objects.get_or_create(
            slug=self.DEFAULT_TAG_SLUG,
            defaults={
                'name': self.DEFAULT_TAG_SLUG,
                'color': self.DEFAULT_ROLE_COLOR,
            },
        )
        return tag

    def _ensure_role(self, slug: str) -> DeviceRole:
        role, _ = DeviceRole.objects.get_or_create(
            slug=slug,
            defaults={
                'name': slug.replace('-', ' ').title(),
                'color': self.DEFAULT_ROLE_COLOR,
            },
        )
        return role

    def _create_switch_devices(self, devices: list[Device]) -> dict[str, Device]:
        switch_devices: dict[str, Device] = {}

        for switch_class in self.plan.switch_classes.all():
            switch_role = self._resolve_switch_category(switch_class.hedgehog_role)
            role = self._ensure_role(switch_role)

            for index in range(switch_class.effective_quantity):
                name = self._render_device_name(
                    category=switch_role,
                    class_id=switch_class.switch_class_id,
                    index=index + 1,
                    fabric=switch_class.fabric or "",
                    role=switch_class.hedgehog_role or "",
                )
                device = Device(
                    name=name,
                    device_type=switch_class.device_type_extension.device_type,
                    role=role,
                    site=self.site,
                    status=DeviceStatusChoices.STATUS_PLANNED,
                )
                device.custom_field_data = {
                    'hedgehog_plan_id': str(self.plan.pk),
                    'hedgehog_class': switch_class.switch_class_id,
                    'hedgehog_fabric': switch_class.fabric or "",
                    'hedgehog_role': switch_class.hedgehog_role or "",
                    'boot_mac': self._generate_boot_mac(name),
                }
                device.save()
                devices.append(device)

                switch_devices[name] = device
                self._device_cache[name] = device

        return switch_devices

    def _create_server_devices(self, devices: list[Device]) -> dict[str, Device]:
        server_devices: dict[str, Device] = {}
        role = self._ensure_role(DeviceCategoryChoices.SERVER)

        for server_class in self.plan.server_classes.all():
            for index in range(server_class.quantity):
                name = self._render_device_name(
                    category=DeviceCategoryChoices.SERVER,
                    class_id=server_class.server_class_id,
                    index=index + 1,
                )
                device = Device(
                    name=name,
                    device_type=server_class.server_device_type,
                    role=role,
                    site=self.site,
                    status=DeviceStatusChoices.STATUS_PLANNED,
                )
                device.custom_field_data = {
                    'hedgehog_plan_id': str(self.plan.pk),
                    'hedgehog_class': server_class.server_class_id,
                }
                device.save()
                devices.append(device)

                server_devices[name] = device
                self._device_cache[name] = device

        return server_devices

    def _create_connections(
        self,
        switch_devices: dict[str, Device],
        server_devices: dict[str, Device],
    ) -> tuple[list[Interface], list[Cable]]:
        interfaces: list[Interface] = []
        cables: list[Cable] = []

        for server_class in self.plan.server_classes.all():
            for server_index in range(server_class.quantity):
                server_name = self._render_device_name(
                    category=DeviceCategoryChoices.SERVER,
                    class_id=server_class.server_class_id,
                    index=server_index + 1,
                )
                server_device = server_devices[server_name]

                for connection_def in server_class.connections.all():
                    switch_instances = self._get_switch_instances(
                        connection_def.target_switch_class,
                        switch_devices,
                    )
                    if not switch_instances:
                        raise ValidationError(
                            f"No switch instances available for {connection_def.target_switch_class.switch_class_id}."
                        )

                    zone = self._select_zone_for_connection(connection_def)

                    # Pre-calculate total_rails for rail-optimized connections
                    total_rails = None
                    if connection_def.distribution == ConnectionDistributionChoices.RAIL_OPTIMIZED:
                        total_rails = self._get_total_rails_for_target(
                            server_class,
                            connection_def.target_switch_class,
                        )

                    for port_index in range(connection_def.ports_per_connection):
                        switch_device = self._select_switch_instance(
                            switch_instances,
                            connection_def.distribution,
                            server_index,
                            port_index,
                            rail=connection_def.rail,
                            total_rails=total_rails,
                        )
                        switch_port = self.port_allocator.allocate(
                            switch_device.name,
                            zone,
                            1,
                        )[0]

                        switch_interface = self._get_or_create_interface(
                            device=switch_device,
                            name=switch_port.name,
                            interfaces=interfaces,
                            custom_fields={
                                'hedgehog_plan_id': str(self.plan.pk),
                                'hedgehog_zone': zone.zone_name,
                                'hedgehog_physical_port': switch_port.physical_port,
                                'hedgehog_breakout_index': switch_port.breakout_index,
                            },
                            interface_type=self._speed_to_interface_type(connection_def.speed),
                        )

                        # Use new interface assignment logic (Issue #138 fix)
                        server_interface = self._get_or_assign_server_interface(
                            device=server_device,
                            connection_def=connection_def,
                            port_index=port_index,
                            interfaces=interfaces,
                        )

                        cable = Cable(
                            a_terminations=[server_interface],
                            b_terminations=[switch_interface],
                        )
                        cable.custom_field_data = {
                            'hedgehog_plan_id': str(self.plan.pk),
                        }
                        cable.save()
                        cables.append(cable)

        fabric_interfaces, fabric_cables = self._create_fabric_connections(switch_devices)
        interfaces.extend(fabric_interfaces)
        cables.extend(fabric_cables)

        return interfaces, cables

    def _create_fabric_connections(
        self,
        switch_devices: dict[str, Device],
    ) -> tuple[list[Interface], list[Cable]]:
        interfaces: list[Interface] = []
        cables: list[Cable] = []

        if not switch_devices:
            return interfaces, cables

        switch_classes = {
            switch_class.switch_class_id: switch_class
            for switch_class in self.plan.switch_classes.all()
        }

        for fabric in (
            FabricTypeChoices.FRONTEND,
            FabricTypeChoices.BACKEND,
            FabricTypeChoices.OOB,
        ):
            leaves = [
                device
                for device in switch_devices.values()
                if device.custom_field_data.get('hedgehog_fabric') == fabric
                and device.custom_field_data.get('hedgehog_role')
                in (HedgehogRoleChoices.SERVER_LEAF, HedgehogRoleChoices.BORDER_LEAF)
            ]
            spines = [
                device
                for device in switch_devices.values()
                if device.custom_field_data.get('hedgehog_fabric') == fabric
                and device.custom_field_data.get('hedgehog_role') == HedgehogRoleChoices.SPINE
            ]

            if not leaves or not spines:
                continue

            leaves = sorted(leaves, key=lambda device: device.name)
            spines = sorted(spines, key=lambda device: device.name)

            for leaf in leaves:
                leaf_class = self._get_switch_class_for_device(leaf, switch_classes)
                uplink_zones = leaf_class.port_zones.filter(
                    zone_type=PortZoneTypeChoices.UPLINK
                ).order_by('priority', 'zone_name')

                if not uplink_zones.exists():
                    raise ValidationError(
                        f"Leaf switch class '{leaf_class.switch_class_id}' has no uplink zones defined."
                    )

                leaf_ports = self._allocate_ports_for_zones(leaf.name, uplink_zones)
                total_uplinks = len(leaf_ports)

                if total_uplinks == 0:
                    continue

                base = total_uplinks // len(spines)
                remainder = total_uplinks % len(spines)
                cursor = 0

                for spine_index, spine in enumerate(spines):
                    link_count = base + (1 if spine_index < remainder else 0)
                    if link_count == 0:
                        continue

                    spine_class = self._get_switch_class_for_device(spine, switch_classes)
                    fabric_zones = spine_class.port_zones.filter(
                        zone_type=PortZoneTypeChoices.FABRIC
                    ).order_by('priority', 'zone_name')

                    if not fabric_zones.exists():
                        raise ValidationError(
                            f"Spine switch class '{spine_class.switch_class_id}' has no fabric zones defined."
                        )

                    spine_ports = self._allocate_ports_for_zones(
                        spine.name,
                        fabric_zones,
                        count=link_count,
                    )

                    leaf_slice = leaf_ports[cursor:cursor + link_count]
                    cursor += link_count

                    for (leaf_zone, leaf_port), (spine_zone, spine_port) in zip(leaf_slice, spine_ports):
                        leaf_interface = self._get_or_create_interface(
                            device=leaf,
                            name=leaf_port.name,
                            interfaces=interfaces,
                            custom_fields={
                                'hedgehog_plan_id': str(self.plan.pk),
                                'hedgehog_zone': leaf_zone.zone_name,
                                'hedgehog_physical_port': leaf_port.physical_port,
                                'hedgehog_breakout_index': leaf_port.breakout_index,
                            },
                            interface_type=self._interface_type_for_zone(leaf_zone),
                        )

                        spine_interface = self._get_or_create_interface(
                            device=spine,
                            name=spine_port.name,
                            interfaces=interfaces,
                            custom_fields={
                                'hedgehog_plan_id': str(self.plan.pk),
                                'hedgehog_zone': spine_zone.zone_name,
                                'hedgehog_physical_port': spine_port.physical_port,
                                'hedgehog_breakout_index': spine_port.breakout_index,
                            },
                            interface_type=self._interface_type_for_zone(spine_zone),
                        )

                        cable = Cable(
                            a_terminations=[leaf_interface],
                            b_terminations=[spine_interface],
                        )
                        cable.custom_field_data = {
                            'hedgehog_plan_id': str(self.plan.pk),
                        }
                        cable.save()
                        cables.append(cable)

        return interfaces, cables

    def _get_switch_class_for_device(
        self,
        device: Device,
        switch_classes: dict[str, PlanSwitchClass],
    ) -> PlanSwitchClass:
        class_id = device.custom_field_data.get('hedgehog_class')
        switch_class = switch_classes.get(class_id)
        if not switch_class:
            raise ValidationError(
                f"Switch class '{class_id}' is missing for device '{device.name}'."
            )
        return switch_class

    def _allocate_ports_for_zones(self, switch_name, zones, count: int | None = None):
        allocated: list[tuple[object, object]] = []

        for zone in zones:
            zone_capacity = self._get_zone_logical_port_count(zone)
            if count is not None:
                remaining = count - len(allocated)
                if remaining <= 0:
                    break
                zone_capacity = min(zone_capacity, remaining)

            if zone_capacity <= 0:
                continue

            slots = self.port_allocator.allocate(switch_name, zone, zone_capacity)
            allocated.extend((zone, slot) for slot in slots)

        if count is not None and len(allocated) < count:
            raise ValidationError(
                f"Not enough ports available on switch '{switch_name}' to allocate {count} links."
            )

        return allocated

    @staticmethod
    def _get_zone_logical_port_count(zone) -> int:
        if not zone.breakout_option:
            raise ValidationError(
                f"SwitchPortZone '{zone.zone_name}' has no breakout_option defined."
            )

        port_list = PortSpecification(zone.port_spec).parse()
        logical_ports = zone.breakout_option.logical_ports or 1
        return len(port_list) * logical_ports

    def _interface_type_for_zone(self, zone) -> str:
        speed = None
        breakout = zone.breakout_option
        if breakout:
            speed = breakout.logical_speed or breakout.from_speed
        return self._speed_to_interface_type(speed or 0)

    def _get_or_create_interface(
        self,
        device: Device,
        name: str,
        interfaces: list[Interface],
        custom_fields: dict,
        interface_type: str = InterfaceTypeChoices.TYPE_OTHER,
    ) -> Interface:
        cache_key = (device.pk, name)
        if cache_key in self._interface_cache:
            return self._interface_cache[cache_key]

        existing = Interface.objects.filter(device=device, name=name).first()
        if existing:
            existing.custom_field_data = {
                **(existing.custom_field_data or {}),
                **custom_fields,
            }
            existing.save()
            self._interface_cache[cache_key] = existing
            return existing

        interface = Interface(
            device=device,
            name=name,
            type=interface_type,
            enabled=True,
        )
        interface.custom_field_data = custom_fields
        interface.save()
        interfaces.append(interface)
        self._interface_cache[cache_key] = interface
        return interface

    @staticmethod
    def _speed_to_interface_type(speed_gbps: int) -> str:
        """
        Map connection speed to NetBox interface type (Issue #138, AC#8).

        NOTE: This uses connection_def.speed, which is correct because the port
        allocator only allocates from zones where breakout logical_speed matches
        connection speed. This is a design invariant - if they diverge, port
        allocation will fail before we reach this point.

        Args:
            speed_gbps: Connection speed in Gbps (e.g., 800, 400, 200, 100, 40, 25, 10, 1)

        Returns:
            NetBox InterfaceTypeChoices constant
        """
        speed_map = {
            800: InterfaceTypeChoices.TYPE_800GE_QSFP_DD,
            400: InterfaceTypeChoices.TYPE_400GE_QSFP_DD,
            200: InterfaceTypeChoices.TYPE_200GE_QSFP56,
            100: InterfaceTypeChoices.TYPE_100GE_QSFP28,
            40: InterfaceTypeChoices.TYPE_40GE_QSFP_PLUS,
            25: InterfaceTypeChoices.TYPE_25GE_SFP28,
            10: InterfaceTypeChoices.TYPE_10GE_SFP_PLUS,
            1: InterfaceTypeChoices.TYPE_1GE_SFP,
        }
        return speed_map.get(speed_gbps, InterfaceTypeChoices.TYPE_OTHER)

    def _tag_objects(
        self,
        devices: Iterable[Device],
        interfaces: Iterable[Interface],
        cables: Iterable[Cable],
    ) -> None:
        for device in devices:
            device.tags.add(self.tag)
        for interface in interfaces:
            interface.tags.add(self.tag)
        for cable in cables:
            cable.tags.add(self.tag)

    def _upsert_generation_state(
        self,
        device_count: int,
        interface_count: int,
        cable_count: int,
    ) -> None:
        GenerationState.objects.filter(plan=self.plan).delete()
        state = GenerationState(
            plan=self.plan,
            device_count=device_count,
            interface_count=interface_count,
            cable_count=cable_count,
            snapshot=build_plan_snapshot(self.plan),
            status=GenerationStatusChoices.GENERATED,
        )
        state.save()

    def _render_device_name(
        self,
        category: str,
        class_id: str,
        index: int,
        fabric: str | None = None,
        role: str | None = None,
    ) -> str:
        template = self._get_naming_template(category)
        if template:
            context = {
                'site': self.site.slug,
                'class': class_id,
                'category': category,
                'fabric': fabric or "",
                'role': role or "",
                'rack': 0,
                'index': index,
            }
            return template.render(context)

        if category == DeviceCategoryChoices.SERVER:
            return f"{slugify(class_id)}-{index:03d}"

        return f"{slugify(class_id)}-{index:02d}"

    def _get_naming_template(self, category: str) -> NamingTemplate | None:
        return (
            NamingTemplate.objects.filter(plan=self.plan, device_category=category).first()
            or NamingTemplate.objects.filter(plan__isnull=True, device_category=category).first()
        )

    def _resolve_switch_category(self, hedgehog_role: str | None) -> str:
        if hedgehog_role == HedgehogRoleChoices.SPINE:
            return DeviceCategoryChoices.SPINE
        if hedgehog_role == HedgehogRoleChoices.BORDER_LEAF:
            return DeviceCategoryChoices.BORDER
        if hedgehog_role == HedgehogRoleChoices.VIRTUAL:
            return DeviceCategoryChoices.OOB
        return DeviceCategoryChoices.LEAF

    def _get_switch_instances(
        self,
        switch_class: PlanSwitchClass,
        switch_devices: dict[str, Device],
    ) -> list[Device]:
        devices = []
        for index in range(switch_class.effective_quantity):
            name = self._render_device_name(
                category=self._resolve_switch_category(switch_class.hedgehog_role),
                class_id=switch_class.switch_class_id,
                index=index + 1,
                fabric=switch_class.fabric or "",
                role=switch_class.hedgehog_role or "",
            )
            if name in switch_devices:
                devices.append(switch_devices[name])
        return devices

    def _get_total_rails_for_target(
        self,
        server_class: 'PlanServerClass',
        target_switch_class: PlanSwitchClass,
    ) -> int:
        """
        Calculate total number of distinct rails for rail-optimized connections
        targeting a specific switch class.

        Results are cached by (server_class_id, switch_class_id) to avoid
        recomputation in loops.

        Args:
            server_class: Server class containing connections
            target_switch_class: Target switch class to filter by

        Returns:
            Number of distinct non-null rails (e.g., 8 for 8-rail backend)
        """
        cache_key = (server_class.server_class_id, target_switch_class.switch_class_id)

        if cache_key in self._rail_count_cache:
            return self._rail_count_cache[cache_key]

        # Get all rail-optimized connections for this target switch class
        rail_optimized_connections = server_class.connections.filter(
            distribution=ConnectionDistributionChoices.RAIL_OPTIMIZED,
            target_switch_class=target_switch_class,
            rail__isnull=False,
        )

        # Get distinct rail values
        distinct_rails = rail_optimized_connections.values_list('rail', flat=True).distinct()
        total_rails = len(distinct_rails)

        # Cache result
        self._rail_count_cache[cache_key] = total_rails

        return total_rails

    def _select_switch_instance(
        self,
        switch_instances: list[Device],
        distribution: str,
        server_index: int,
        port_index: int,
        rail: int | None = None,
        total_rails: int | None = None,
    ) -> Device:
        if len(switch_instances) == 1:
            return switch_instances[0]

        if distribution == ConnectionDistributionChoices.ALTERNATING:
            return switch_instances[port_index % len(switch_instances)]
        if distribution == ConnectionDistributionChoices.SAME_SWITCH:
            return switch_instances[server_index % len(switch_instances)]
        if distribution == ConnectionDistributionChoices.RAIL_OPTIMIZED:
            # Rail-optimized: all servers' NIC at position N connect to same switch(es)
            # Algorithm: rails_per_switch = ceil(total_rails / num_switches)
            #            switch_index = rail // rails_per_switch
            if rail is None:
                raise ValidationError(
                    "Rail number required for rail-optimized distribution"
                )
            if total_rails is None or total_rails == 0:
                raise ValidationError(
                    "Total rails required for rail-optimized distribution"
                )

            num_switches = len(switch_instances)
            rails_per_switch = math.ceil(total_rails / num_switches)
            switch_index = rail // rails_per_switch

            return switch_instances[switch_index]

        return switch_instances[server_index % len(switch_instances)]

    def _select_zone_for_connection(self, connection: PlanServerConnection):
        zone_type = self._map_zone_type(connection)
        zones = connection.target_switch_class.port_zones.filter(zone_type=zone_type).order_by('priority')

        if zones.exists():
            return zones.first()

        fallback = connection.target_switch_class.port_zones.order_by('priority').first()
        if fallback:
            return fallback

        raise ValidationError(
            f"No port zones defined for switch class {connection.target_switch_class.switch_class_id}."
        )

    def _map_zone_type(self, connection: PlanServerConnection) -> str:
        if connection.port_type == PortTypeChoices.IPMI:
            return PortZoneTypeChoices.OOB
        return PortZoneTypeChoices.SERVER

    def _generate_server_port_name(self, connection_def: PlanServerConnection, port_idx: int) -> str:
        if connection_def.nic_slot:
            import re

            # Preserve nic_slot uniqueness; only strip trailing f<digits> if present.
            match = re.match(r'^(.*)f\\d+$', connection_def.nic_slot)
            base = match.group(1) if match else connection_def.nic_slot
            return f"{base}f{port_idx}"

        conn_id = slugify(connection_def.connection_id)
        return f"port-{conn_id}-{port_idx}"

    def _get_or_assign_server_interface(
        self,
        device: Device,
        connection_def: PlanServerConnection,
        port_index: int,
        interfaces: list[Interface],
    ) -> Interface:
        """
        Get or assign server interface for connection (Issue #138 fix).

        If connection has server_interface_template, tries to use existing
        interfaces from device type. Otherwise falls back to creating new
        with legacy naming.

        Args:
            device: Server Device instance
            connection_def: PlanServerConnection configuration
            port_index: Index of port in connection (0-based)
            interfaces: List to append interface to if created

        Returns:
            Interface instance (existing or newly created)
        """
        from dcim.models import Interface

        if connection_def.server_interface_template:
            # Get interface sequence from template
            interface_sequence = connection_def._get_available_interface_sequence()

            if port_index < len(interface_sequence):
                # Get the Nth interface template from sequence
                target_template = interface_sequence[port_index]

                # Look for existing interface with matching name
                existing = Interface.objects.filter(
                    device=device,
                    name=target_template.name
                ).first()

                if existing:
                    # Found inherited interface - return it
                    # Cache it for future lookups
                    cache_key = (device.pk, existing.name)
                    self._interface_cache[cache_key] = existing
                    return existing
                else:
                    # Template exists but device doesn't have it yet
                    # This shouldn't happen if device properly inherits from DeviceType
                    # Create interface matching template
                    interface = Interface(
                        device=device,
                        name=target_template.name,
                        type=target_template.type,
                        enabled=True,
                    )
                    interface.custom_field_data = {
                        'hedgehog_plan_id': str(self.plan.pk),
                    }
                    interface.save()
                    interfaces.append(interface)
                    self._interface_cache[(device.pk, interface.name)] = interface
                    return interface

        # Fallback to legacy behavior (generate new interface name)
        server_port_name = self._generate_server_port_name(
            connection_def,
            port_index,
        )
        return self._get_or_create_interface(
            device=device,
            name=server_port_name,
            interfaces=interfaces,
            custom_fields={
                'hedgehog_plan_id': str(self.plan.pk),
            },
        )

    def _generate_boot_mac(self, device_name: str) -> str:
        """
        Generate deterministic boot MAC address for switch devices.

        Uses locally administered MAC address range (02:00:00:xx:xx:xx)
        with device name for determinism (stable across regenerations).

        Args:
            device_name: NetBox device name (ensures same device = same MAC)

        Returns:
            MAC address string in format "02:00:00:xx:xx:xx"
        """
        import hashlib

        # Hash device name for deterministic MAC generation
        # Using name ensures stability even if device ordering changes
        hash_bytes = hashlib.sha256(device_name.encode()).digest()

        # Locally administered MAC: bit 1 of first octet = 1 (0x02)
        # Unicast: bit 0 of first octet = 0
        mac_bytes = bytes([0x02]) + hash_bytes[1:6]

        return ':'.join(f'{b:02x}' for b in mac_bytes)
