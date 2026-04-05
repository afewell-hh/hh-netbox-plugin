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
    FabricClassChoices,
    ConnectionDistributionChoices,
    DeviceCategoryChoices,
    HedgehogRoleChoices,
    PortTypeChoices,
    PortZoneTypeChoices,
    GenerationStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    GenerationState,
    NamingTemplate,
    PlanServerConnection,
    PlanServerNIC,
    PlanSwitchClass,
    TopologyPlan,
)
from netbox_hedgehog.services.port_allocator import PortAllocatorV2
from netbox_hedgehog.services.port_specification import PortSpecification
from netbox_hedgehog.services._fabric_utils import _is_managed_device
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

        # Stage 2: missing-bay error accumulator.  Populated by
        # _create_nested_transceiver_module() and _create_switch_transceiver_module()
        # when a transceiver FK is set but the required ModuleBay is absent.
        self._bay_placement_errors: list = []

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

        # Milestone 5b: Creating mesh connections (explicit mesh fabrics)
        if self.logger:
            self.logger.info("Creating mesh connections (if any mesh-mode fabrics)")
        mesh_ifaces, mesh_cables = self._create_mesh_connections(self.plan, switch_devices)
        interfaces.extend(mesh_ifaces)
        cables.extend(mesh_cables)

        # Milestone 6: Tagging and finalizing
        if self.logger:
            self.logger.info("Tagging objects and finalizing generation")
        self._tag_objects(devices, interfaces, cables)

        # Milestone 7a: Bay-placement hard-fail check (Stage 2, #345).
        # If any transceiver FK was set but the required ModuleBay was absent,
        # generation must not succeed.  Collected by placement helpers above.
        if self._bay_placement_errors:
            self._upsert_generation_state(
                device_count=len(devices),
                interface_count=len(interfaces),
                cable_count=len(cables),
                status=GenerationStatusChoices.FAILED,
                mismatch_report={'bay_errors': self._bay_placement_errors},
            )
            return GenerationResult(
                device_count=len(devices),
                interface_count=len(interfaces),
                cable_count=len(cables),
            )

        # Milestone 7b: Post-generation pairwise transceiver compatibility sweep (Stage 2).
        # Runs after all objects are created; collects all mismatches before failing.
        mismatches = self._run_compatibility_sweep()
        if mismatches:
            self._upsert_generation_state(
                device_count=len(devices),
                interface_count=len(interfaces),
                cable_count=len(cables),
                status=GenerationStatusChoices.FAILED,
                mismatch_report={'mismatches': mismatches},
            )
            # Return result anyway so callers can inspect counts; status signals failure.
            return GenerationResult(
                device_count=len(devices),
                interface_count=len(interfaces),
                cable_count=len(cables),
            )

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
                    fabric=switch_class.fabric_name or "",
                    role=switch_class.hedgehog_role or "",
                )
                device = Device(
                    name=name,
                    device_type=switch_class.device_type_extension.device_type,
                    role=role,
                    site=self.site,
                    status=DeviceStatusChoices.STATUS_PLANNED,
                )
                custom_fields = {
                    'hedgehog_plan_id': str(self.plan.pk),
                    'hedgehog_class': switch_class.switch_class_id,
                    'hedgehog_fabric': switch_class.fabric_name or "",
                    'hedgehog_fabric_class': switch_class.fabric_class or "",
                    'hedgehog_role': switch_class.hedgehog_role or "",
                    'boot_mac': self._generate_boot_mac(name),
                }
                device.custom_field_data = custom_fields
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

                # Two-pass NIC-first generation (DIET-294):
                # Pass 1: create one Module per PlanServerNIC that has at least one connection.
                # NICs with no connections are skipped (no physical module installed).
                used_nic_pks = set(
                    server_class.connections.values_list('nic_id', flat=True).distinct()
                )
                nic_to_module: dict[int, object] = {}  # nic.pk → Module
                for nic_def in server_class.nics.select_related('module_type').filter(pk__in=used_nic_pks):
                    module = self._create_module_for_nic(
                        device=server_device,
                        nic_def=nic_def,
                    )
                    nic_to_module[nic_def.pk] = module

                # Pass 2: wire connections using the already-created modules.
                for connection_def in server_class.connections.select_related(
                    'nic', 'target_zone', 'target_zone__switch_class'
                ).all():
                    zone = connection_def.target_zone
                    switch_class = zone.switch_class
                    switch_instances = self._get_switch_instances(
                        switch_class,
                        switch_devices,
                    )
                    if not switch_instances:
                        raise ValidationError(
                            f"No switch instances available for {switch_class.switch_class_id}."
                        )

                    # Pre-calculate total_rails and servers_per_domain for rail-optimized connections
                    total_rails = None
                    servers_per_domain = None
                    if connection_def.distribution == ConnectionDistributionChoices.RAIL_OPTIMIZED:
                        total_rails = self._get_total_rails_for_target(
                            server_class,
                            zone,
                        )
                        num_sw = len(switch_instances)
                        if total_rails and num_sw >= total_rails:
                            # Domain-based: compute how many servers fit in one first-hop rail domain.
                            # Each domain has total_rails switches (one per rail); each switch serves
                            # zone_capacity / ports_per_connection servers for its rail.
                            zone_capacity = self.port_allocator.capacity_for_zone(zone)
                            ppc = connection_def.ports_per_connection or 1
                            servers_per_domain = max(1, zone_capacity // ppc)

                    module = nic_to_module.get(connection_def.nic_id)
                    if module is None:
                        raise ValidationError(
                            f"No Module found for NIC pk={connection_def.nic_id} "
                            f"on server device {server_device.name}. "
                            "Ensure Pass 1 created the module correctly."
                        )

                    # DIET-334 Stage 2: place server-side transceiver in nested NIC-port bay.
                    xcvr_module = self._create_nested_transceiver_module(
                        server_device, module, connection_def
                    )

                    # Build transceiver spec string for server-side interface custom field.
                    # Prefer FK attribute_data when available; fall back to flat fields.
                    # DEPRECATED: hedgehog_transceiver_spec will be removed in Stage 3 (#334).
                    # Stage 2: suppress write when a real transceiver Module was placed.
                    xcvr_mt = getattr(connection_def, 'transceiver_module_type', None)
                    if xcvr_module is None:
                        # No Module placed — build fallback spec from flat fields or FK attrs.
                        if xcvr_mt is not None:
                            _ad = xcvr_mt.attribute_data or {}
                            _xcvr_parts = [
                                _ad.get('cage_type', ''),
                                _ad.get('medium', ''),
                                _ad.get('standard', ''),
                                _ad.get('connector', ''),
                            ]
                        else:
                            _xcvr_parts = [
                                connection_def.cage_type,
                                connection_def.medium,
                                connection_def.connector,
                                connection_def.standard,
                            ]
                        transceiver_spec = ' | '.join(p for p in _xcvr_parts if p)
                    else:
                        # Transceiver Module placed — suppress legacy custom field write.
                        transceiver_spec = ''

                    for port_index in range(connection_def.ports_per_connection):
                        switch_device = self._select_switch_instance(
                            switch_instances,
                            connection_def.distribution,
                            server_index,
                            port_index,
                            rail=connection_def.rail,
                            total_rails=total_rails,
                            servers_per_domain=servers_per_domain,
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

                        # DIET-334 Stage 2: place switch-side transceiver Module.
                        self._create_switch_transceiver_module(
                            switch_device, switch_port.name, zone
                        )

                        # Get server interface from Module using port_index (DIET-294 NIC-first)
                        actual_port_index = connection_def.port_index + port_index
                        server_interface = self._get_module_interface_by_port_index(
                            device=server_device,
                            module=module,
                            port_index=actual_port_index,
                        )

                        # Write transceiver spec to server-side interface (DIET-294).
                        # Only set on server-side; switch-side must not have this field.
                        if transceiver_spec:
                            server_interface.custom_field_data = dict(
                                server_interface.custom_field_data or {}
                            )
                            server_interface.custom_field_data['hedgehog_transceiver_spec'] = transceiver_spec
                            server_interface.save(update_fields=['custom_field_data'])
                        # NOTE: server-side interfaces are NOT added to `interfaces` list.
                        # interface_count and hedgehog-generated tag are switch-side only.

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

        surr_interfaces, surr_cables = self._create_surrogate_uplink_connections(switch_devices)
        interfaces.extend(surr_interfaces)
        cables.extend(surr_cables)

        peer_interfaces, peer_cables = self._create_peer_zone_uplink_connections(switch_devices)
        interfaces.extend(peer_interfaces)
        cables.extend(peer_cables)

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

        for fabric in self._managed_fabric_names_from_plan():
            leaves = [
                device
                for device in switch_devices.values()
                if device.custom_field_data.get('hedgehog_fabric') == fabric
                and _is_managed_device(device)
                and device.custom_field_data.get('hedgehog_role')
                in (HedgehogRoleChoices.SERVER_LEAF, HedgehogRoleChoices.BORDER_LEAF)
            ]
            spines = [
                device
                for device in switch_devices.values()
                if device.custom_field_data.get('hedgehog_fabric') == fabric
                and _is_managed_device(device)
                and device.custom_field_data.get('hedgehog_role') == HedgehogRoleChoices.SPINE
            ]

            if not leaves or not spines:
                continue

            leaves = sorted(leaves, key=lambda device: device.name)
            spines = sorted(spines, key=lambda device: device.name)

            for leaf in leaves:
                leaf_class = self._get_switch_class_for_device(leaf, switch_classes)

                # Explicit standalone signal: uplink_ports_per_switch=0 means this leaf
                # has uplink-capable ports but intentionally has no spine connections
                # in the DIET model (e.g. a border/gateway leaf). Skip fabric wiring.
                if leaf_class.uplink_ports_per_switch == 0:
                    continue

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

    def _create_surrogate_uplink_connections(
        self,
        switch_devices: dict[str, Device],
    ) -> tuple[list[Interface], list[Cable]]:
        """
        Generate oob-zone cables between surrogate (oob-mgmt) switch instances
        and their target managed switch instances (DIET-254 Phase 5, Option A).

        For each surrogate switch class that has an oob-type zone with peer_zone set:
          - Each surrogate instance allocates all ports from the uplink zone.
          - Ports are connected to the peer managed switch instances in alternating order.
          - Cables are tagged hedgehog_zone='oob' so yaml_generator routes them as
            managed_switch<->surrogate unbundled Connection CRDs.

        This method is deterministic: surrogate and managed switch instances are
        sorted by name before connection assignment.
        """
        interfaces: list[Interface] = []
        cables: list[Cable] = []

        for switch_class in self.plan.switch_classes.all():
            if switch_class.fabric_class != FabricClassChoices.UNMANAGED:
                continue

            # Find oob-type uplink zones with an explicit peer_zone target (Option A)
            uplink_zones = list(
                switch_class.port_zones.filter(
                    zone_type=PortZoneTypeChoices.OOB,
                ).exclude(peer_zone=None).select_related('peer_zone__switch_class')
            )
            if not uplink_zones:
                continue

            # Sorted surrogate instances for determinism
            surrogate_devices = sorted(
                [
                    d for d in switch_devices.values()
                    if d.custom_field_data.get('hedgehog_class') == switch_class.switch_class_id
                ],
                key=lambda d: d.name,
            )
            if not surrogate_devices:
                continue

            for uplink_zone in uplink_zones:
                peer_zone = uplink_zone.peer_zone
                managed_class_id = peer_zone.switch_class.switch_class_id

                # Sorted managed switch instances for determinism
                managed_devices = sorted(
                    [
                        d for d in switch_devices.values()
                        if d.custom_field_data.get('hedgehog_class') == managed_class_id
                    ],
                    key=lambda d: d.name,
                )
                if not managed_devices:
                    raise ValidationError(
                        f"No managed switch instances found for '{managed_class_id}' "
                        f"(peer of surrogate '{switch_class.switch_class_id}')."
                    )

                num_managed = len(managed_devices)
                uplink_port_count = self._get_zone_logical_port_count(uplink_zone)

                for surrogate_device in surrogate_devices:
                    for port_idx in range(uplink_port_count):
                        # Alternate across managed switch instances
                        managed_device = managed_devices[port_idx % num_managed]

                        # Allocate one port from the surrogate's uplink zone
                        surr_port = self.port_allocator.allocate(
                            surrogate_device.name, uplink_zone, 1
                        )[0]

                        # Allocate one port from the managed switch's peer zone
                        mgmt_port = self.port_allocator.allocate(
                            managed_device.name, peer_zone, 1
                        )[0]

                        surr_iface = self._get_or_create_interface(
                            device=surrogate_device,
                            name=surr_port.name,
                            interfaces=interfaces,
                            custom_fields={
                                'hedgehog_plan_id': str(self.plan.pk),
                                'hedgehog_zone': uplink_zone.zone_name,
                                'hedgehog_physical_port': surr_port.physical_port,
                                'hedgehog_breakout_index': surr_port.breakout_index,
                            },
                            interface_type=self._interface_type_for_zone(uplink_zone),
                        )

                        mgmt_iface = self._get_or_create_interface(
                            device=managed_device,
                            name=mgmt_port.name,
                            interfaces=interfaces,
                            custom_fields={
                                'hedgehog_plan_id': str(self.plan.pk),
                                'hedgehog_zone': peer_zone.zone_name,
                                'hedgehog_physical_port': mgmt_port.physical_port,
                                'hedgehog_breakout_index': mgmt_port.breakout_index,
                            },
                            interface_type=self._interface_type_for_zone(peer_zone),
                        )

                        cable = Cable(
                            a_terminations=[surr_iface],
                            b_terminations=[mgmt_iface],
                        )
                        cable.custom_field_data = {
                            'hedgehog_plan_id': str(self.plan.pk),
                            'hedgehog_zone': 'oob',
                        }
                        cable.save()
                        cables.append(cable)

        return interfaces, cables

    def _create_peer_zone_uplink_connections(
        self,
        switch_devices: dict[str, Device],
    ) -> tuple[list[Interface], list[Cable]]:
        """
        Wire managed-fabric leaves to spine-tier devices via explicit peer_zone
        uplink targeting (DIET-271).

        Scope guard: only uplink-type zones (zone_type=UPLINK) on managed-fabric
        (frontend/backend) leaves that have peer_zone set. OOB zones are handled
        exclusively in _create_surrogate_uplink_connections() and are never
        touched here.

        uplink_ports_per_switch=0 guard: that guard lives in
        _create_fabric_connections() and controls the standard fabric wiring path
        only. This method runs independently — a leaf with
        uplink_ports_per_switch=0 and a peer_zone uplink zone receives no
        standard fabric cables and does receive peer_zone cables. This is the
        deterministic rule for fe-border-leaf.

        Distribution: same load-balanced base/remainder algorithm as
        _create_fabric_connections().
        """
        interfaces: list[Interface] = []
        cables: list[Cable] = []

        if not switch_devices:
            return interfaces, cables

        switch_classes = {
            sc.switch_class_id: sc
            for sc in self.plan.switch_classes.all()
        }

        for fabric in self._managed_fabric_names_from_plan():
            leaves = sorted(
                [
                    d for d in switch_devices.values()
                    if d.custom_field_data.get('hedgehog_fabric') == fabric
                    and _is_managed_device(d)
                    and d.custom_field_data.get('hedgehog_role')
                    in (HedgehogRoleChoices.SERVER_LEAF, HedgehogRoleChoices.BORDER_LEAF)
                ],
                key=lambda d: d.name,
            )

            for leaf in leaves:
                leaf_class = self._get_switch_class_for_device(leaf, switch_classes)

                # Only UPLINK zones with peer_zone set — never OOB zones
                peer_uplink_zones = list(
                    leaf_class.port_zones.filter(
                        zone_type=PortZoneTypeChoices.UPLINK,
                        peer_zone__isnull=False,
                    ).select_related('peer_zone__switch_class')
                    .order_by('priority', 'zone_name')
                )

                if not peer_uplink_zones:
                    continue

                for uplink_zone in peer_uplink_zones:
                    peer_zone = uplink_zone.peer_zone
                    target_class_id = peer_zone.switch_class.switch_class_id

                    target_devices = sorted(
                        [
                            d for d in switch_devices.values()
                            if d.custom_field_data.get('hedgehog_class') == target_class_id
                        ],
                        key=lambda d: d.name,
                    )

                    if not target_devices:
                        raise ValidationError(
                            f"No '{target_class_id}' devices found for peer_zone"
                            f" on zone '{uplink_zone.zone_name}' (leaf '{leaf.name}')."
                        )

                    leaf_ports = self._allocate_ports_for_zones(leaf.name, [uplink_zone])
                    total_uplinks = len(leaf_ports)

                    if total_uplinks == 0:
                        continue

                    base = total_uplinks // len(target_devices)
                    remainder = total_uplinks % len(target_devices)
                    cursor = 0

                    for t_idx, target_device in enumerate(target_devices):
                        link_count = base + (1 if t_idx < remainder else 0)
                        if link_count == 0:
                            continue

                        spine_ports = self.port_allocator.allocate(
                            target_device.name, peer_zone, link_count
                        )

                        leaf_slice = leaf_ports[cursor:cursor + link_count]
                        cursor += link_count

                        for (leaf_zone, leaf_port), spine_port in zip(leaf_slice, spine_ports):
                            leaf_iface = self._get_or_create_interface(
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
                            spine_iface = self._get_or_create_interface(
                                device=target_device,
                                name=spine_port.name,
                                interfaces=interfaces,
                                custom_fields={
                                    'hedgehog_plan_id': str(self.plan.pk),
                                    'hedgehog_zone': peer_zone.zone_name,
                                    'hedgehog_physical_port': spine_port.physical_port,
                                    'hedgehog_breakout_index': spine_port.breakout_index,
                                },
                                interface_type=self._interface_type_for_zone(peer_zone),
                            )
                            cable = Cable(
                                a_terminations=[leaf_iface],
                                b_terminations=[spine_iface],
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
            interfaces.append(existing)
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
        status: str = GenerationStatusChoices.GENERATED,
        mismatch_report=None,
    ) -> None:
        GenerationState.objects.filter(plan=self.plan).delete()
        state = GenerationState(
            plan=self.plan,
            device_count=device_count,
            interface_count=interface_count,
            cable_count=cable_count,
            snapshot=build_plan_snapshot(self.plan),
            status=status,
            mismatch_report=mismatch_report,
        )
        state.save()

    def _run_compatibility_sweep(self) -> list:
        """
        Stage 2: post-generation pairwise transceiver compatibility sweep.

        Iterates over all PlanServerConnections for this plan and compares
        cage_type and medium from both cable ends. Collects ALL mismatches
        before returning — aggregate-all-mismatches-then-fail per approved spec.

        Returns a list of mismatch dicts (empty list = all compatible).
        """
        from netbox_hedgehog.models.topology_planning import PlanServerConnection

        mismatches = []
        connections = PlanServerConnection.objects.filter(
            server_class__plan=self.plan
        ).select_related(
            'transceiver_module_type',
            'target_zone__transceiver_module_type',
            'server_class',
        )

        for conn in connections:
            server_mt = getattr(conn, 'transceiver_module_type', None)
            zone_mt = getattr(conn.target_zone, 'transceiver_module_type', None)
            if server_mt is None or zone_mt is None:
                continue

            s_attrs = server_mt.attribute_data or {}
            z_attrs = zone_mt.attribute_data or {}

            for dim in ('cage_type', 'medium'):
                s_val = s_attrs.get(dim)
                z_val = z_attrs.get(dim)
                if s_val and z_val and s_val != z_val:
                    mismatches.append({
                        'connection_id': conn.pk,
                        'server_device': str(conn.server_class.server_class_id),
                        'switch_port': conn.target_zone.zone_name,
                        'mismatch_type': dim,
                        'server_end': s_val,
                        'switch_end': z_val,
                    })

        return mismatches

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
                fabric=switch_class.fabric_name or "",
                role=switch_class.hedgehog_role or "",
            )
            if name in switch_devices:
                devices.append(switch_devices[name])
        return devices

    def _managed_fabric_names_from_plan(self) -> list[str]:
        return list(
            self.plan.switch_classes.filter(
                fabric_class=FabricClassChoices.MANAGED,
            ).exclude(
                fabric_name='',
            ).order_by(
                'fabric_name'
            ).values_list(
                'fabric_name',
                flat=True,
            ).distinct()
        )

    def _get_total_rails_for_target(
        self,
        server_class: 'PlanServerClass',
        target_zone,
    ) -> int:
        """
        Calculate total number of distinct rails for rail-optimized connections
        targeting a specific zone.

        Results are cached by (server_class_id, zone.pk) to avoid
        recomputation in loops.
        """
        cache_key = (server_class.server_class_id, target_zone.pk)

        if cache_key in self._rail_count_cache:
            return self._rail_count_cache[cache_key]

        rail_optimized_connections = server_class.connections.filter(
            distribution=ConnectionDistributionChoices.RAIL_OPTIMIZED,
            target_zone=target_zone,
            rail__isnull=False,
        )

        distinct_rails = rail_optimized_connections.values_list('rail', flat=True).distinct()
        total_rails = len(distinct_rails)

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
        servers_per_domain: int | None = None,
    ) -> Device:
        if len(switch_instances) == 1:
            return switch_instances[0]

        if distribution == ConnectionDistributionChoices.ALTERNATING:
            return switch_instances[port_index % len(switch_instances)]
        if distribution == ConnectionDistributionChoices.SAME_SWITCH:
            return switch_instances[server_index % len(switch_instances)]
        if distribution == ConnectionDistributionChoices.RAIL_OPTIMIZED:
            # Rail-optimized: all servers' NIC at position N connect to the same rail's switch.
            # Two sub-cases:
            #
            # A) num_switches < total_rails (capacity-sharing):
            #    Multiple rails are served by one switch. Map by:
            #        rails_per_switch = ceil(total_rails / num_switches)
            #        switch_index = rail // rails_per_switch
            #    server_index is irrelevant here (all servers share same mapping).
            #
            # B) num_switches >= total_rails (domain-based / repeated first-hop domains):
            #    Each domain has exactly total_rails switches (one per rail).
            #    Domains repeat when server demand exceeds one switch's capacity.
            #        domain_index = server_index // servers_per_domain
            #        switch_index = domain_index * total_rails + rail
            #    This ensures servers 0..N-1 use domain 0 and servers N..2N-1 use domain 1,
            #    each domain using the same rail→switch-within-domain mapping.
            if rail is None:
                raise ValidationError(
                    "Rail number required for rail-optimized distribution"
                )
            if total_rails is None or total_rails == 0:
                raise ValidationError(
                    "Total rails required for rail-optimized distribution"
                )

            num_switches = len(switch_instances)

            if num_switches >= total_rails:
                # Domain-based: repeated first-hop rail domains
                if servers_per_domain is None or servers_per_domain <= 0:
                    raise ValidationError(
                        "servers_per_domain required for rail-optimized distribution "
                        "when num_switches >= total_rails"
                    )
                domain_index = server_index // servers_per_domain
                switch_index = domain_index * total_rails + rail
            else:
                # Capacity-sharing: multiple rails map to one switch
                rails_per_switch = math.ceil(total_rails / num_switches)
                switch_index = rail // rails_per_switch

            # Safety clamp — should never fire for well-formed plans
            switch_index = min(switch_index, num_switches - 1)
            return switch_instances[switch_index]

        return switch_instances[server_index % len(switch_instances)]

    def _create_module_for_nic(
        self,
        device: Device,
        nic_def,
    ):
        """
        Create ModuleBay and Module for a PlanServerNIC (DIET-294 NIC-first).

        Creates a ModuleBay named after nic_def.nic_id and instantiates a Module
        with nic_def.module_type.  NetBox automatically creates Interfaces from
        the ModuleType's InterfaceTemplates.  Interfaces are prefixed with
        nic_id so names are globally unique on the device.

        Args:
            device: Server Device instance
            nic_def: PlanServerNIC instance

        Returns:
            Module instance (newly created or existing)
        """
        from dcim.models import ModuleBay, Module, Interface

        bay_name = nic_def.nic_id  # ModuleBay.name = nic_id (DIET-294)

        # get_or_create to be idempotent on regeneration
        module_bay, _ = ModuleBay.objects.get_or_create(
            device=device,
            name=bay_name,
            defaults={
                'label': f'NIC slot {nic_def.nic_id}',
            },
        )

        existing_module = Module.objects.filter(
            device=device,
            module_bay=module_bay,
        ).first()
        if existing_module:
            return existing_module

        module = Module(
            device=device,
            module_bay=module_bay,
            module_type=nic_def.module_type,
            serial=f"{device.name}-{nic_def.nic_id}",  # deterministic
            status='active',
        )
        module.custom_field_data = {
            'hedgehog_plan_id': str(self.plan.pk),
        }
        module.save()

        # Rename auto-created interfaces: prefix with nic_id for uniqueness.
        # "p0" → "nic-fe-p0", "port0" → "nic-be-rail-0-port0"
        for iface in Interface.objects.filter(device=device, module=module):
            iface.name = f"{nic_def.nic_id}-{iface.name}"
            iface.custom_field_data = dict(iface.custom_field_data or {})
            iface.custom_field_data.setdefault('hedgehog_transceiver_spec', '')
            iface.save()

        return module

    def _create_nested_transceiver_module(
        self,
        device: Device,
        nic_module,
        connection,
    ):
        """
        Stage 2: place transceiver Module in the nested port-cage bay inside the NIC Module.

        Object chain: device -> NIC module bay -> NIC Module -> cage-N bay -> transceiver Module.

        The cage-N ModuleBay is auto-instantiated by NetBox when the NIC Module is installed
        (driven by ModuleBayTemplate children on the NIC ModuleType, added by
        populate_transceiver_bays). If the nested bay is absent and the connection has a
        transceiver FK set, this is a hard error — generation will be marked FAILED (#345).

        Returns the created/existing transceiver Module, or None if FK is null.
        """
        xcvr_mt = getattr(connection, 'transceiver_module_type', None)
        if xcvr_mt is None:
            return None

        from dcim.models import ModuleBay, Module

        cage_name = f'cage-{connection.port_index}'
        nested_bay = ModuleBay.objects.filter(
            module=nic_module,
            name=cage_name,
        ).first()

        if nested_bay is None:
            self._bay_placement_errors.append({
                'error_type': 'missing_nested_bay',
                'device': device.name,
                'cage': cage_name,
                'connection_id': connection.pk,
                'hint': 'Run populate_transceiver_bays to add ModuleBayTemplates to NIC ModuleTypes.',
            })
            return None

        existing = Module.objects.filter(module_bay=nested_bay).first()
        if existing is not None:
            if existing.module_type_id == xcvr_mt.pk:
                return existing
            existing.delete()

        module = Module(
            device=device,
            module_bay=nested_bay,
            module_type=xcvr_mt,
            status='planned',
            serial=f'{device.name}-{cage_name}',
        )
        module.custom_field_data = {'hedgehog_plan_id': str(self.plan.pk)}
        module.save()
        return module

    def _create_switch_transceiver_module(
        self,
        device: Device,
        port_name: str,
        zone,
    ):
        """
        Stage 2: place transceiver Module in the switch port bay for a given port.

        The ModuleBay named `port_name` must already exist on the switch Device (auto-created
        from ModuleBayTemplate by NetBox when the device was created, after
        populate_transceiver_bays added the templates to the DeviceType). If the bay is
        absent and the zone has a transceiver FK set, this is a hard error — generation
        will be marked FAILED (#345).

        Returns the created/existing transceiver Module, or None if zone FK is null.
        """
        xcvr_mt = getattr(zone, 'transceiver_module_type', None)
        if xcvr_mt is None:
            return None

        from dcim.models import ModuleBay, Module

        bay = ModuleBay.objects.filter(device=device, name=port_name).first()
        if bay is None:
            self._bay_placement_errors.append({
                'error_type': 'missing_switch_bay',
                'device': device.name,
                'port': port_name,
                'zone': zone.zone_name,
                'hint': 'Run populate_transceiver_bays to add ModuleBayTemplates to switch DeviceTypes.',
            })
            return None

        existing = Module.objects.filter(device=device, module_bay=bay).first()
        if existing is not None:
            if existing.module_type_id == xcvr_mt.pk:
                return existing
            existing.delete()

        module = Module(
            device=device,
            module_bay=bay,
            module_type=xcvr_mt,
            status='planned',
            serial=f'{device.name}-{port_name}',
        )
        module.custom_field_data = {'hedgehog_plan_id': str(self.plan.pk)}
        module.save()
        return module

    def _get_module_interface_by_port_index(
        self,
        device: Device,
        module,
        port_index: int,
    ) -> 'Interface':
        """
        Get Module interface by port index (DIET-173 Phase 5).

        Retrieves the interface at the specified port_index from the Module.
        Interfaces are sorted by name (natural order) to ensure consistent
        zero-based indexing (p0=index 0, p1=index 1, etc.).

        Args:
            device: Server Device instance
            module: Module instance
            port_index: Zero-based port index

        Returns:
            Interface instance at port_index

        Raises:
            ValidationError: If port_index exceeds available interfaces
        """
        from dcim.models import Interface

        # Get all interfaces for this Module, sorted by name with natural ordering
        # Use Python sorting with natural key to handle multi-digit numbers correctly
        # (e.g., port1, port2, ..., port10, not port1, port10, port2)
        import re

        def natural_sort_key(iface):
            """Extract numeric parts for natural sorting (port1, port2, ..., port10)"""
            parts = re.split(r'(\d+)', iface.name)
            return [int(p) if p.isdigit() else p.lower() for p in parts]

        module_interfaces = sorted(
            Interface.objects.filter(
                device=device,
                module=module
            ),
            key=natural_sort_key
        )

        if not module_interfaces:
            raise ValidationError(
                f"No interfaces found for Module {module.module_type} on device {device.name}. "
                f"Module may not have instantiated interfaces yet."
            )

        if port_index >= len(module_interfaces):
            raise ValidationError(
                f"Port index {port_index} exceeds available interfaces (0-{len(module_interfaces) - 1}) "
                f"on Module {module.module_type}."
            )

        return module_interfaces[port_index]

    def _render_device_name_for_switch_class(self, switch_class, index: int) -> str:
        """Helper: render a device name for a given switch_class and 1-based index."""
        return self._render_device_name(
            category=self._resolve_switch_category(switch_class.hedgehog_role),
            class_id=switch_class.switch_class_id,
            index=index,
            fabric=switch_class.fabric_name or "",
            role=switch_class.hedgehog_role or "",
        )

    def _create_mesh_connections(self, plan, switch_devices: dict[str, Device]):
        """
        Allocate mesh links for all explicit mesh fabrics and create NetBox cables.

        Returns:
            tuple(list[Interface], list[Cable]) — mesh interfaces and cables created,
            for inclusion in the caller's tagging/counting/cleanup lifecycle.

        For each fabric where switch classes have topology_mode='mesh':
        1. Hard-validates that fabric switch total is 2 or 3.
        2. Hard-validates that each switch class has at least one MESH-type zone.
        3. Hard-validates that each MESH zone has enough ports (n_switches-1 per switch).
        4. Calls allocate_mesh_links() to get/update PlanMeshLink rows.
        5. For each PlanMeshLink, locates the two switch devices by name.
        6. Allocates one MESH-zone port from each device (no fallback).
        7. Creates a Cable between those interfaces.
        8. Stores the chosen port names back on the PlanMeshLink.
        """
        from netbox_hedgehog.utils.mesh_allocator import allocate_mesh_links
        from netbox_hedgehog.choices import TopologyModeChoices
        from netbox_hedgehog.services.port_specification import PortSpecification

        mesh_interfaces = []
        mesh_cables = []

        fabric_names = list(
            plan.switch_classes.filter(
                topology_mode=TopologyModeChoices.MESH,
            ).values_list('fabric_name', flat=True).distinct()
        )

        for fabric_name in fabric_names:
            mesh_classes = list(plan.switch_classes.filter(
                fabric_name=fabric_name,
                topology_mode=TopologyModeChoices.MESH,
            ))
            total_switches = sum(sc.effective_quantity for sc in mesh_classes)

            # Hard validation 1: fabric switch count must be 2 or 3
            if total_switches not in (2, 3):
                raise ValidationError(
                    f"Mesh fabric '{fabric_name}' has {total_switches} switches; "
                    f"mesh requires exactly 2 or 3."
                )

            ports_needed_per_switch = total_switches - 1  # 1 for 2-switch, 2 for 3-switch

            # Hard validation 2 & 3: each switch class must have a MESH zone with
            # enough ports to connect to all other mesh switches.
            for sc in mesh_classes:
                mesh_zones = list(sc.port_zones.filter(
                    zone_type=PortZoneTypeChoices.MESH
                ).order_by('priority', 'zone_name'))
                if not mesh_zones:
                    raise ValidationError(
                        f"Mesh switch class '{sc.switch_class_id}' in fabric '{fabric_name}' "
                        f"has no MESH-type port zones defined. "
                        f"Add a zone with zone_type=MESH before generating."
                    )
                total_mesh_ports = sum(
                    len(PortSpecification(z.port_spec).parse()) for z in mesh_zones
                )
                if total_mesh_ports < ports_needed_per_switch:
                    raise ValidationError(
                        f"Mesh switch class '{sc.switch_class_id}' in fabric '{fabric_name}' "
                        f"has only {total_mesh_ports} MESH zone port(s) but needs "
                        f"{ports_needed_per_switch} (for a {total_switches}-switch mesh)."
                    )

            mesh_links = allocate_mesh_links(
                plan,
                fabric_name,
                render_device_name_fn=self._render_device_name_for_switch_class,
            )

            for mesh_link in mesh_links:
                device_a = switch_devices.get(mesh_link.leaf1_name)
                device_b = switch_devices.get(mesh_link.leaf2_name)
                if device_a is None or device_b is None:
                    raise ValidationError(
                        f"Mesh link {mesh_link.leaf1_name}↔{mesh_link.leaf2_name}: "
                        f"one or both switch devices not found."
                    )

                switch_class_a = mesh_link.switch_class_a
                switch_class_b = mesh_link.switch_class_b

                def _pick_mesh_interface(device, switch_class):
                    """Allocate one port from a MESH zone; raises if none available."""
                    mesh_zones = list(switch_class.port_zones.filter(
                        zone_type=PortZoneTypeChoices.MESH
                    ).order_by('priority', 'zone_name')) if switch_class else []

                    if not mesh_zones:
                        raise ValidationError(
                            f"Device '{device.name}': switch class '{switch_class.switch_class_id}' "
                            f"has no MESH-type port zones."
                        )

                    ports = self._allocate_ports_for_zones(device.name, mesh_zones, count=1)
                    if not ports:
                        raise ValidationError(
                            f"Device '{device.name}': no available ports in MESH zones of "
                            f"switch class '{switch_class.switch_class_id}'. "
                            f"Add more ports to the MESH zone for this fabric size."
                        )

                    zone, port = ports[0]
                    return self._get_or_create_interface(
                        device=device,
                        name=port.name,
                        interfaces=mesh_interfaces,
                        custom_fields={
                            'hedgehog_plan_id': str(plan.pk),
                            'hedgehog_zone': zone.zone_name,
                            'hedgehog_physical_port': port.physical_port,
                            'hedgehog_breakout_index': port.breakout_index,
                        },
                        interface_type=self._interface_type_for_zone(zone),
                    )

                iface_a = _pick_mesh_interface(device_a, switch_class_a)
                iface_b = _pick_mesh_interface(device_b, switch_class_b)

                cable = Cable(
                    a_terminations=[iface_a],
                    b_terminations=[iface_b],
                )
                cable.custom_field_data = {
                    'hedgehog_plan_id': str(plan.pk),
                }
                cable.save()
                mesh_cables.append(cable)

                # Store chosen port names back on PlanMeshLink
                mesh_link.leaf1_port = iface_a.name
                mesh_link.leaf2_port = iface_b.name
                mesh_link.save(update_fields=['leaf1_port', 'leaf2_port'])

                if self.logger:
                    self.logger.info(
                        f"Mesh cable created: {mesh_link.leaf1_name}/{iface_a.name} ↔ "
                        f"{mesh_link.leaf2_name}/{iface_b.name}"
                    )

        return mesh_interfaces, mesh_cables

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
