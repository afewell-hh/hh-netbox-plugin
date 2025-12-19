"""
Reference Data Models for Topology Planning (DIET Module)

These models store admin-managed reference data about network equipment:
- SwitchModel: Physical switch specifications
- SwitchPortGroup: Port groups on switches with breakout capabilities
- NICModel: Server NIC specifications
- BreakoutOption: Breakout configurations for port speeds

These are separate from operational CRD models and used for design-time planning.
"""

from django.db import models
from django.urls import reverse
from django.core.validators import MinValueValidator
from netbox.models import NetBoxModel


class SwitchModel(NetBoxModel):
    """
    Physical switch model specifications (reference data).

    Stores information about switch hardware that can be referenced when
    planning topologies. Admin-managed data shared across all topology plans.
    """

    model_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique switch model identifier (e.g., 'DS5000', 'SN5600')"
    )
    vendor = models.CharField(
        max_length=100,
        help_text="Vendor name (e.g., 'Celestica', 'NVIDIA', 'Arista')"
    )
    part_number = models.CharField(
        max_length=100,
        help_text="Manufacturer part number"
    )
    total_ports = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Total number of physical ports on this switch"
    )
    mclag_capable = models.BooleanField(
        default=False,
        help_text="Whether this switch supports MCLAG"
    )
    hedgehog_roles = models.JSONField(
        default=list,
        blank=True,
        help_text="List of supported Hedgehog roles: spine, server-leaf, border-leaf, virtual"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this switch model (e.g., throughput, special features)"
    )

    class Meta:
        ordering = ['vendor', 'model_id']
        verbose_name = "Switch Model"
        verbose_name_plural = "Switch Models"

    def __str__(self):
        return f"{self.vendor} {self.model_id}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:switchmodel', args=[self.pk])


class SwitchPortGroup(NetBoxModel):
    """
    Port group on a switch with breakout capabilities.

    Switches may have multiple port groups with different speeds and breakout
    options (e.g., 64x 800G QSFP-DD ports + 4x 10G SFP+ management ports).
    """

    switch_model = models.ForeignKey(
        SwitchModel,
        on_delete=models.CASCADE,
        related_name='port_groups',
        help_text="Switch model this port group belongs to"
    )
    group_name = models.CharField(
        max_length=100,
        help_text="Descriptive name for this port group (e.g., 'Primary QSFP-DD', 'Management SFP+')"
    )
    port_count = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of physical ports in this group"
    )
    native_speed = models.IntegerField(
        help_text="Native port speed in Gbps (e.g., 800 for 800G)"
    )
    supported_breakouts = models.CharField(
        max_length=200,
        help_text="Comma-separated breakout options (e.g., '1x800G,2x400G,4x200G')"
    )
    port_range = models.CharField(
        max_length=50,
        help_text="Port numbering range (e.g., 'E1/1-E1/64', '1-32')"
    )

    class Meta:
        ordering = ['switch_model', 'group_name']
        verbose_name = "Switch Port Group"
        verbose_name_plural = "Switch Port Groups"

    def __str__(self):
        return f"{self.switch_model.model_id} - {self.group_name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:switchportgroup', args=[self.pk])


class NICModel(NetBoxModel):
    """
    Server NIC (Network Interface Card) specifications (reference data).

    Stores information about server NICs that can be referenced when planning
    server connections in topologies.
    """

    model_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique NIC model identifier (e.g., 'CX7-2P-400G', 'BF3-2P-400G')"
    )
    vendor = models.CharField(
        max_length=100,
        help_text="Vendor name (e.g., 'NVIDIA', 'Intel', 'Broadcom')"
    )
    part_number = models.CharField(
        max_length=100,
        help_text="Manufacturer part number (e.g., 'MCX755106AS-HEAT')"
    )
    port_count = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of ports on this NIC (typically 1 or 2)"
    )
    port_speed = models.IntegerField(
        help_text="Speed per port in Gbps (e.g., 400 for 400G)"
    )
    port_type = models.CharField(
        max_length=50,
        help_text="Port connector type (e.g., 'QSFP112', 'QSFP56', 'OSFP', 'RJ45')"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this NIC model"
    )

    class Meta:
        ordering = ['vendor', 'model_id']
        verbose_name = "NIC Model"
        verbose_name_plural = "NIC Models"

    def __str__(self):
        return f"{self.vendor} {self.model_id}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:nicmodel', args=[self.pk])


class BreakoutOption(NetBoxModel):
    """
    Port breakout configuration option.

    Defines how a physical port can be broken out into multiple logical ports
    at lower speeds (e.g., 1x800G → 4x200G).
    """

    breakout_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique breakout identifier (e.g., '800g-4x200g', '100g-4x25g')"
    )
    from_speed = models.IntegerField(
        help_text="Native/source port speed in Gbps (e.g., 800)"
    )
    logical_ports = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of logical ports created by this breakout (e.g., 4)"
    )
    logical_speed = models.IntegerField(
        help_text="Speed per logical port in Gbps (e.g., 200)"
    )
    optic_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optic/connector type if different from native (e.g., 'QSFP-DD', 'QSFP56')"
    )

    class Meta:
        ordering = ['-from_speed', 'logical_ports']
        verbose_name = "Breakout Option"
        verbose_name_plural = "Breakout Options"

    def __str__(self):
        return f"{self.breakout_id} ({self.from_speed}G → {self.logical_ports}x{self.logical_speed}G)"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:breakoutoption', args=[self.pk])
