"""
Policy helpers for transceiver bay handling.

Virtual placeholder switch DeviceTypes and NIC ModuleTypes are used by
YAML-imported training/reference-architecture plans to model logical fabrics
without requiring full physical transceiver object instantiation in NetBox.
Creating one ModuleBay/Module per port/cage on these placeholders is
prohibitively slow and does not add operational value for those plans.
"""

from dcim.models import DeviceType, ModuleType


def is_virtual_placeholder_switch_device_type(device_type: DeviceType | None) -> bool:
    """
    Return True when *device_type* is a logical/placeholder virtual switch type.

    The current convention for these imported training assets is a DeviceType
    model string beginning with ``"Virtual "``. Keep the policy narrow and
    explicit so hardware-backed plans continue to enforce full switch-side
    transceiver bay modeling.
    """
    if device_type is None:
        return False
    model = (device_type.model or "").strip()
    return model.startswith("Virtual ")


def is_virtual_placeholder_module_type(module_type: ModuleType | None) -> bool:
    """Return True when *module_type* is a logical/placeholder virtual NIC type."""
    if module_type is None:
        return False
    model = (module_type.model or "").strip()
    return model.startswith("Virtual ")
