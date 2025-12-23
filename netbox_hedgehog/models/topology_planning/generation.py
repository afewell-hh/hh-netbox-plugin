"""
Generation state models for topology planning.

GenerationState tracks the state of NetBox object generation from a TopologyPlan.
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.urls import reverse

from netbox_hedgehog.choices import GenerationStatusChoices


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

    def is_dirty(self):
        """
        Check if plan has been modified since generation.

        Returns:
            bool: True if plan differs from snapshot, False otherwise
        """
        # Build current state snapshot
        current_snapshot = self._build_current_snapshot()

        # Compare server classes
        if not self._compare_server_classes(
            current_snapshot.get('server_classes', []),
            self.snapshot.get('server_classes', [])
        ):
            return True

        # Compare switch classes
        if not self._compare_switch_classes(
            current_snapshot.get('switch_classes', []),
            self.snapshot.get('switch_classes', [])
        ):
            return True

        return False

    def _build_current_snapshot(self):
        """Build snapshot of current plan state"""
        snapshot = {
            'server_classes': [],
            'switch_classes': []
        }

        # Capture server classes
        for server_class in self.plan.server_classes.all():
            snapshot['server_classes'].append({
                'server_class_id': server_class.server_class_id,
                'quantity': server_class.quantity
            })

        # Capture switch classes
        for switch_class in self.plan.switch_classes.all():
            snapshot['switch_classes'].append({
                'switch_class_id': switch_class.switch_class_id,
                'effective_quantity': switch_class.effective_quantity
            })

        return snapshot

    def _compare_server_classes(self, current, snapshot):
        """Compare server classes between current state and snapshot"""
        # Build lookup dicts
        current_dict = {
            sc['server_class_id']: sc['quantity']
            for sc in current
        }
        snapshot_dict = {
            sc['server_class_id']: sc['quantity']
            for sc in snapshot
        }

        # Compare
        return current_dict == snapshot_dict

    def _compare_switch_classes(self, current, snapshot):
        """Compare switch classes between current state and snapshot"""
        # Build lookup dicts
        current_dict = {
            sc['switch_class_id']: sc['effective_quantity']
            for sc in current
        }
        snapshot_dict = {
            sc['switch_class_id']: sc['effective_quantity']
            for sc in snapshot
        }

        # Compare
        return current_dict == snapshot_dict
