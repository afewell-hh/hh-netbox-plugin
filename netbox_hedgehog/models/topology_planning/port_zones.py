"""
Port zone models for topology planning.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel

from netbox_hedgehog.choices import AllocationStrategyChoices, PortZoneTypeChoices
from netbox_hedgehog.services.port_specification import PortSpecification

from .reference_data import BreakoutOption
from .topology_plans import PlanSwitchClass


class SwitchPortZone(NetBoxModel):
    """
    Defines a port allocation zone within a switch class.
    """

    switch_class = models.ForeignKey(
        PlanSwitchClass,
        on_delete=models.CASCADE,
        related_name='port_zones',
        help_text="Switch class this port zone belongs to",
    )

    zone_name = models.CharField(
        max_length=100,
        help_text="Zone name (e.g., 'server-ports', 'spine-uplinks')",
    )

    zone_type = models.CharField(
        max_length=50,
        choices=PortZoneTypeChoices,
        help_text="Port zone type",
    )

    port_spec = models.CharField(
        max_length=200,
        help_text="Port specification (e.g., '1-48', '1-32:2', '1,3,5')",
    )

    breakout_option = models.ForeignKey(
        BreakoutOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='port_zones',
        help_text="Breakout option for logical ports (optional)",
    )

    allocation_strategy = models.CharField(
        max_length=50,
        choices=AllocationStrategyChoices,
        default=AllocationStrategyChoices.SEQUENTIAL,
        help_text="Port allocation strategy",
    )

    allocation_order = models.JSONField(
        null=True,
        blank=True,
        help_text="Explicit allocation order when using custom strategy",
    )

    priority = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        help_text="Lower numbers allocate earlier",
    )

    class Meta:
        ordering = ['switch_class', 'priority', 'zone_name']
        unique_together = [['switch_class', 'zone_name']]
        verbose_name = "Switch Port Zone"
        verbose_name_plural = "Switch Port Zones"

    def __str__(self):
        return f"{self.switch_class.switch_class_id}/{self.zone_name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:switchportzone', args=[self.pk])

    def clean(self):
        super().clean()

        try:
            port_list = PortSpecification(self.port_spec).parse()
        except ValidationError as exc:
            raise ValidationError({'port_spec': exc.messages})

        if self.allocation_strategy == AllocationStrategyChoices.CUSTOM:
            if not self.allocation_order:
                raise ValidationError(
                    {'allocation_order': "Custom strategy requires allocation_order."}
                )

            if not isinstance(self.allocation_order, list):
                raise ValidationError(
                    {'allocation_order': "Allocation order must be a list."}
                )

            if len(self.allocation_order) != len(port_list):
                raise ValidationError(
                    {'allocation_order': "Allocation order must match port count."}
                )

            if len(set(self.allocation_order)) != len(self.allocation_order):
                raise ValidationError(
                    {'allocation_order': "Allocation order cannot contain duplicates."}
                )

            if set(self.allocation_order) != set(port_list):
                raise ValidationError(
                    {'allocation_order': "Allocation order must match port set."}
                )
