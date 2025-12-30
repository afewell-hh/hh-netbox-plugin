"""
Generation state models for topology planning.

GenerationState tracks the state of NetBox object generation from a TopologyPlan.
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.urls import reverse

from netbox_hedgehog.choices import GenerationStatusChoices
from netbox_hedgehog.utils.snapshot_builder import (
    build_plan_snapshot,
    compare_snapshots,
)


class GenerationState(models.Model):
    """
    Tracks generation state for a TopologyPlan.

    Used to detect when a plan has been modified since objects were last generated,
    enabling reconciliation and re-generation workflows.
    """

    plan = models.OneToOneField(
        to='netbox_hedgehog.TopologyPlan',
        on_delete=models.CASCADE,
        related_name='generation_state',
        help_text="Topology plan this state belongs to"
    )

    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When generation occurred"
    )

    device_count = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Number of devices generated"
    )

    interface_count = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Number of interfaces generated"
    )

    cable_count = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Number of cables generated"
    )

    snapshot = models.JSONField(
        help_text="Plan state at generation time (for change detection)"
    )

    status = models.CharField(
        max_length=50,
        choices=GenerationStatusChoices,
        default=GenerationStatusChoices.GENERATED,
        help_text="Current generation status"
    )

    class Meta:
        verbose_name = "Generation State"
        verbose_name_plural = "Generation States"

    def __str__(self):
        """String representation"""
        return f"{self.plan.name} - {self.device_count} devices"

    def get_absolute_url(self):
        """Get absolute URL for this object"""
        return reverse('plugins:netbox_hedgehog:generationstate', args=[self.pk])

    def is_dirty(self) -> bool:
        """
        Check if plan has been modified since generation.

        Compares current plan state against snapshot saved at generation time.
        Detects changes to server classes, switch classes, connections, port
        zones, and MCLAG domains.

        Returns:
            bool: True if plan differs from snapshot, False otherwise

        Example:
            >>> state = GenerationState.objects.get(plan=plan)
            >>> state.is_dirty()
            False  # No changes since generation
            >>> plan.server_classes.first().quantity = 64
            >>> plan.server_classes.first().save()
            >>> state.is_dirty()
            True  # Quantity changed

        Note:
            Uses shared snapshot builder (netbox_hedgehog.utils.snapshot_builder)
            to ensure consistency with DeviceGenerator snapshot logic.
        """
        current = build_plan_snapshot(self.plan)
        return not compare_snapshots(current, self.snapshot)
