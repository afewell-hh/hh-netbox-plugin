"""
Reference Data Models for Topology Planning (DIET Module)

Following Agent C's recommendation, these models leverage NetBox core models:
- Switch models → dcim.DeviceType
- Server models → dcim.DeviceType
- NIC models → dcim.ModuleType
- Port specifications → dcim.InterfaceTemplate

Custom models only where NetBox doesn't provide equivalent functionality:
- BreakoutOption: Breakout math and logical port mapping
- DeviceTypeExtension: Hedgehog-specific metadata for DeviceTypes
"""

from django.db import models
from django.urls import reverse
from django.core.validators import MinValueValidator
from netbox.models import NetBoxModel
from dcim.models import DeviceType


class BreakoutOption(NetBoxModel):
    """
    Breakout configuration for port speeds.

    NetBox doesn't model breakout math (how many logical ports at what speed
    you get from breaking out a physical port), so this stays as a custom model.

    Example: 800G port can breakout to:
    - 1x800G (no breakout)
    - 2x400G (2 logical ports)
    - 4x200G (4 logical ports)
    - 8x100G (8 logical ports)
    """

    breakout_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique breakout identifier (e.g., '2x400g', '4x200g')"
    )
    from_speed = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Native port speed in Gbps (e.g., 800 for 800G)"
    )
    logical_ports = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of logical ports after breakout (e.g., 4 for 4x200G)"
    )
    logical_speed = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Speed per logical port in Gbps (e.g., 200 for 4x200G)"
    )
    optic_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optic type for this breakout (e.g., 'QSFP-DD', 'QSFP28')"
    )

    class Meta:
        ordering = ['-from_speed', 'logical_ports']
        verbose_name = "Breakout Option"
        verbose_name_plural = "Breakout Options"

    def __str__(self):
        return f"{self.breakout_id} - {self.logical_ports}x{self.logical_speed}G (from {self.from_speed}G)"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:breakoutoption', args=[self.pk])


class DeviceTypeExtension(NetBoxModel):
    """
    Hedgehog-specific metadata for NetBox DeviceTypes.

    NetBox's DeviceType model doesn't include Hedgehog-specific fields like
    MCLAG capability or supported fabric roles. This extension model provides
    a one-to-one relationship to add that metadata.

    This is optional - only needed for DeviceTypes that will be used in
    Hedgehog topologies. Standard DeviceTypes work fine without it.
    """

    device_type = models.OneToOneField(
        DeviceType,
        on_delete=models.CASCADE,
        related_name='hedgehog_metadata',
        help_text="NetBox DeviceType this metadata applies to"
    )

    mclag_capable = models.BooleanField(
        default=False,
        help_text="Whether this device supports MCLAG (Multi-Chassis Link Aggregation)"
    )

    hedgehog_roles = models.JSONField(
        default=list,
        blank=True,
        help_text="List of supported Hedgehog roles: spine, server-leaf, border-leaf, virtual"
    )

    supported_breakouts = models.JSONField(
        default=list,
        blank=True,
        help_text="List of supported breakout IDs (e.g., ['1x800g', '2x400g', '4x200g']). Used by calc engine to select appropriate BreakoutOption."
    )

    native_speed = models.IntegerField(
        null=True,
        blank=True,
        help_text="Native port speed in Gbps (e.g., 800 for 800G). Used for fallback when no breakout matches."
    )

    uplink_ports = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="[DEPRECATED] Number of ports reserved for uplinks. "
                  "This field is unused in calculations. "
                  "Use PlanSwitchClass.uplink_ports_per_switch or "
                  "define SwitchPortZone with zone_type='uplink'. "
                  "Will be removed in v2.0."
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional Hedgehog-specific notes about this device type"
    )

    hedgehog_profile_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Hedgehog fabric switch profile name (e.g., 'celestica-ds5000', 'dell-s5248f-on'). "
                  "Imported from fabric profile metadata. Allows tracking the original profile source."
    )

    class Meta:
        verbose_name = "Device Type Extension (Hedgehog)"
        verbose_name_plural = "Device Type Extensions (Hedgehog)"

    def __str__(self):
        return f"Hedgehog metadata for {self.device_type}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:devicetypeextension', args=[self.pk])


# NOTE: SwitchModel, NICModel, and SwitchPortGroup are now replaced by:
#
# - Switch specifications → dcim.DeviceType (with Manufacturer)
# - NIC specifications → dcim.ModuleType or dcim.DeviceType
# - Port counts/speeds → dcim.InterfaceTemplate (on DeviceType)
# - Hedgehog-specific fields → DeviceTypeExtension (above)
#
# To use in planning models:
#   PlanSwitchClass.switch_device_type = ForeignKey(DeviceType)
#   PlanServerClass.server_device_type = ForeignKey(DeviceType)
#   PlanServerConnection.nic_module_type = ForeignKey(ModuleType)
#
# Benefits:
#   - No data duplication
#   - Leverage NetBox's device catalog
#   - Better integration with operational inventory
#   - Follows NetBox plugin best practices
