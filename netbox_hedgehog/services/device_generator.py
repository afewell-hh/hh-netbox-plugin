"""
Device generation service for topology planning.

Creates NetBox Devices, Interfaces, and Cables from a TopologyPlan.
"""

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

    def __init__(self, plan: TopologyPlan, site: Site | None = None):
        self.plan = plan
        self.site = site or self._ensure_default_site()
        self.tag = self._ensure_default_tag()
        self.port_allocator = PortAllocatorV2()

        self._device_cache: dict[str, Device] = {}
        self._interface_cache: dict[tuple[int, str], Interface] = {}

    @transaction.atomic
    def generate_all(self) -> GenerationResult:
        """
        Generate devices, interfaces, and cables for the plan.
        """
        devices = []
        interfaces = []
        cables = []

        switch_devices = self._create_switch_devices(devices)
        server_devices = self._create_server_devices(devices)

        interfaces, cables = self._create_connections(
            switch_devices,
            server_devices,
        )

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

                    for port_index in range(connection_def.ports_per_connection):
                        switch_device = self._select_switch_instance(
                            switch_instances,
                            connection_def.distribution,
                            server_index,
                            port_index,
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
                        )

                        server_port_name = self._generate_server_port_name(
                            connection_def,
                            port_index,
                        )
                        server_interface = self._get_or_create_interface(
                            device=server_device,
                            name=server_port_name,
                            interfaces=interfaces,
                            custom_fields={
                                'hedgehog_plan_id': str(self.plan.pk),
                            },
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

        return interfaces, cables

    def _get_or_create_interface(
        self,
        device: Device,
        name: str,
        interfaces: list[Interface],
        custom_fields: dict,
    ) -> Interface:
        cache_key = (device.pk, name)
        if cache_key in self._interface_cache:
            return self._interface_cache[cache_key]

        interface = Interface(
            device=device,
            name=name,
            type=InterfaceTypeChoices.TYPE_OTHER,
            enabled=True,
        )
        interface.custom_field_data = custom_fields
        interface.save()
        interfaces.append(interface)
        self._interface_cache[cache_key] = interface
        return interface

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
            snapshot=self._build_snapshot(),
            status=GenerationStatusChoices.GENERATED,
        )
        state.save()

    def _build_snapshot(self) -> dict:
        snapshot = {
            'server_classes': [],
            'switch_classes': [],
        }

        for server_class in self.plan.server_classes.all():
            snapshot['server_classes'].append({
                'server_class_id': server_class.server_class_id,
                'quantity': server_class.quantity,
            })

        for switch_class in self.plan.switch_classes.all():
            snapshot['switch_classes'].append({
                'switch_class_id': switch_class.switch_class_id,
                'effective_quantity': switch_class.effective_quantity,
            })

        return snapshot

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

    def _select_switch_instance(
        self,
        switch_instances: list[Device],
        distribution: str,
        server_index: int,
        port_index: int,
    ) -> Device:
        if len(switch_instances) == 1:
            return switch_instances[0]

        if distribution == ConnectionDistributionChoices.ALTERNATING:
            return switch_instances[port_index % len(switch_instances)]
        if distribution == ConnectionDistributionChoices.SAME_SWITCH:
            return switch_instances[server_index % len(switch_instances)]
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
            base = connection_def.nic_slot.rstrip('f0123456789')
            return f"{base}f{port_idx}"

        conn_id = slugify(connection_def.connection_id)
        return f"port-{conn_id}-{port_idx}"
