"""
Helpers for plan-scoped NetBox inventory export.

Exports are filtered by the generated-object custom field
``hedgehog_plan_id=<plan.pk>`` so multiple DIET plans can coexist in one local
NetBox instance without requiring a full inventory reset between runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from dcim.models import Cable, Device, Interface, Module


@dataclass(frozen=True)
class PlanInventory:
    devices: list[Device]
    interfaces: list[Interface]
    cables: list[Cable]
    modules: list[Module]


def get_plan_inventory(plan) -> PlanInventory:
    plan_id = str(plan.pk)

    devices = list(
        Device.objects.filter(
            custom_field_data__hedgehog_plan_id=plan_id,
        ).order_by("name", "pk")
    )

    interfaces = list(
        Interface.objects.filter(
            device__custom_field_data__hedgehog_plan_id=plan_id,
        ).select_related(
            "device",
            "module",
        ).order_by(
            "device__name",
            "name",
            "pk",
        )
    )

    cables = list(
        Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=plan_id,
        ).order_by("pk")
    )

    modules = list(
        Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=plan_id,
        ).select_related(
            "device",
            "module_type",
        ).order_by(
            "device__name",
            "module_type__model",
            "pk",
        )
    )

    return PlanInventory(
        devices=devices,
        interfaces=interfaces,
        cables=cables,
        modules=modules,
    )


def terminations_for_side(cable, side: str):
    attr = getattr(cable, f"{side}_terminations")
    return attr if isinstance(attr, list) else list(attr.all())


def serialize_device(device) -> dict:
    role = getattr(device.role, "slug", "")
    device_type = getattr(device.device_type, "model", "")
    manufacturer = getattr(getattr(device.device_type, "manufacturer", None), "name", "")
    site = getattr(device.site, "slug", "")
    tags = sorted(tag.slug for tag in device.tags.all())
    return {
        "id": device.pk,
        "name": device.name,
        "role": role,
        "device_type": device_type,
        "manufacturer": manufacturer,
        "site": site,
        "status": device.status,
        "tags": tags,
        "custom_field_data": device.custom_field_data or {},
    }


def serialize_module(module) -> dict:
    return {
        "id": module.pk,
        "device_id": module.device_id,
        "device_name": module.device.name,
        "module_type": getattr(module.module_type, "model", ""),
        "serial": module.serial,
        "asset_tag": module.asset_tag,
        "status": module.status,
        "custom_field_data": module.custom_field_data or {},
    }


def serialize_interface(interface) -> dict:
    return {
        "id": interface.pk,
        "device_id": interface.device_id,
        "device_name": interface.device.name,
        "module_id": interface.module_id,
        "module_type": getattr(getattr(interface.module, "module_type", None), "model", ""),
        "name": interface.name,
        "type": interface.type,
        "enabled": interface.enabled,
        "custom_field_data": interface.custom_field_data or {},
    }


def serialize_cable(cable) -> dict:
    a_terms = [serialize_termination(t) for t in terminations_for_side(cable, "a")]
    b_terms = [serialize_termination(t) for t in terminations_for_side(cable, "b")]
    return {
        "id": cable.pk,
        "status": cable.status,
        "type": cable.type,
        "a_terminations": a_terms,
        "b_terminations": b_terms,
        "custom_field_data": cable.custom_field_data or {},
    }


def serialize_termination(termination) -> dict:
    device = getattr(termination, "device", None)
    return {
        "id": termination.pk,
        "object_type": termination.__class__.__name__,
        "device_id": getattr(device, "pk", None),
        "device_name": getattr(device, "name", ""),
        "name": getattr(termination, "name", ""),
    }

