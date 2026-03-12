"""Shared helpers for DIET fabric class compatibility."""

from __future__ import annotations

from netbox_hedgehog.choices import FabricClassChoices


_LEGACY_MANAGED_FABRIC_NAMES = frozenset({'frontend', 'backend'})
_LEGACY_SURROGATE_FABRIC_NAMES = frozenset({'oob-mgmt'})
_LEGACY_EXCLUDED_UNMANAGED_FABRIC_NAMES = frozenset({'oob', 'in-band-mgmt', 'network-mgmt'})


def _legacy_fabric_name_to_class(fabric_name: str | None) -> str:
    """Map pre-fabric-class names onto the new behavioral classes."""
    if fabric_name in _LEGACY_MANAGED_FABRIC_NAMES:
        return FabricClassChoices.MANAGED
    return FabricClassChoices.UNMANAGED


def _device_fabric_class(device) -> str:
    """Return the effective fabric class for a generated inventory device."""
    custom_field_data = getattr(device, "custom_field_data", {}) or {}
    fabric_class = custom_field_data.get("hedgehog_fabric_class")
    if fabric_class in (FabricClassChoices.MANAGED, FabricClassChoices.UNMANAGED):
        return fabric_class
    return _legacy_fabric_name_to_class(custom_field_data.get("hedgehog_fabric"))


def _has_explicit_fabric_class(device) -> bool:
    custom_field_data = getattr(device, "custom_field_data", {}) or {}
    return custom_field_data.get("hedgehog_fabric_class") in (
        FabricClassChoices.MANAGED,
        FabricClassChoices.UNMANAGED,
    )


def _is_managed_device(device) -> bool:
    return _device_fabric_class(device) == FabricClassChoices.MANAGED


def _is_unmanaged_device(device) -> bool:
    return _device_fabric_class(device) == FabricClassChoices.UNMANAGED


def _is_surrogate_device(device) -> bool:
    custom_field_data = getattr(device, "custom_field_data", {}) or {}
    fabric_name = custom_field_data.get("hedgehog_fabric")

    if _has_explicit_fabric_class(device):
        return _device_fabric_class(device) == FabricClassChoices.UNMANAGED and getattr(device.role, "slug", None) != "server"

    return fabric_name in _LEGACY_SURROGATE_FABRIC_NAMES and getattr(device.role, "slug", None) != "server"


def _is_legacy_managed_switch_without_fabric(device) -> bool:
    custom_field_data = getattr(device, "custom_field_data", {}) or {}
    if custom_field_data.get("hedgehog_fabric") or _has_explicit_fabric_class(device):
        return False
    return getattr(device.role, "slug", None) in {"leaf", "spine", "border"}
