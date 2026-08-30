"""
Persisted locality report for rack-aware placement (DIET-607).

PlanLocalityRange is the durable, queryable source of truth for the
per-(rack, switch, zone) allocation-sequence ranges produced during generation.
It is written by DeviceGenerator inside the atomic generation transaction and
cleaned up (plan-scoped) on regeneration. It is a read-only artifact from the
user's perspective; the generator is the only writer.
"""

from django.db import models
from django.urls import reverse

from utilities.querysets import RestrictedQuerySet

from netbox_hedgehog.choices import ConnectionDistributionChoices


class PlanLocalityRange(models.Model):
    """One reported cell: an allocation-sequence range for a rack's servers on a
    single (switch, zone), with logical/physical projections and provenance.

    Plain ``models.Model`` per the #609 ADR (an ephemeral plugin-owned artifact,
    no tags/custom-fields/changelog churn). ``RestrictedQuerySet`` still provides
    NetBox ObjectPermission enforcement for the read-only UI/API.

    The cell key ``(plan, server_class, rack, switch, zone)`` is unique. All FKs
    use CASCADE so the row can never block deletion of a generated Rack/Device/
    zone (Device.rack is PROTECT; these rows hold no PROTECT targets).
    """

    objects = RestrictedQuerySet.as_manager()

    plan = models.ForeignKey(
        to='netbox_hedgehog.TopologyPlan',
        on_delete=models.CASCADE,
        related_name='locality_ranges',
    )
    server_class = models.ForeignKey(
        to='netbox_hedgehog.PlanServerClass',
        on_delete=models.CASCADE,
        related_name='locality_ranges',
    )
    rack = models.ForeignKey(
        to='dcim.Rack',
        on_delete=models.CASCADE,
        related_name='+',
        null=False,
        blank=False,
        help_text="Generated rack for this cell (always set in v1).",
    )
    switch = models.ForeignKey(
        to='dcim.Device',
        on_delete=models.CASCADE,
        related_name='+',
    )
    zone = models.ForeignKey(
        to='netbox_hedgehog.SwitchPortZone',
        on_delete=models.CASCADE,
        related_name='locality_ranges',
    )

    rack_index = models.PositiveIntegerField(
        help_text="0-based rack ordinal within the server class.",
    )
    distribution = models.CharField(
        max_length=32,
        choices=ConnectionDistributionChoices,
        help_text="Distribution that produced this cell.",
    )

    alloc_seq_start = models.PositiveIntegerField(
        help_text="First per-(switch,zone) allocation-cursor index (authoritative).",
    )
    alloc_seq_end = models.PositiveIntegerField(
        help_text="Last allocation-cursor index (inclusive).",
    )
    server_ordinal_start = models.PositiveIntegerField(
        help_text="First 0-based server_index contributing to this cell.",
    )
    server_ordinal_end = models.PositiveIntegerField(
        help_text="Last 0-based server_index (inclusive; clipped at quantity-1).",
    )

    logical_name_first = models.CharField(max_length=64)
    logical_name_last = models.CharField(max_length=64)
    logical_sequence = models.JSONField(
        default=list,
        help_text="Switch interface names in allocation order.",
    )
    physical_sequence = models.JSONField(
        default=list,
        help_text="Physical port numbers in allocation order, with breakout repeats.",
    )
    physical_ports_distinct = models.JSONField(
        default=list,
        help_text="Sorted distinct physical port numbers (display only).",
    )
    port_count = models.PositiveIntegerField(
        help_text="Number of logical ports in the cell.",
    )
    spans_boundary = models.BooleanField(
        default=False,
        help_text=(
            "Rack-level flag: the rack crosses a same-switch group or rail "
            "domain. Repeated on each affected cell; not a per-cell physical span."
        ),
    )

    class Meta:
        ordering = [
            'plan', 'server_class', 'rack_index', 'switch__name',
            'zone__priority', 'zone__zone_name', 'alloc_seq_start',
        ]
        unique_together = [
            ('plan', 'server_class', 'rack', 'switch', 'zone'),
        ]
        verbose_name = "Locality Range"
        verbose_name_plural = "Locality Ranges"

    def __str__(self):
        return (
            f"{self.server_class_id}/rack{self.rack_index} "
            f"{self.switch_id}:{self.zone_id} "
            f"[{self.alloc_seq_start}-{self.alloc_seq_end}]"
        )

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:planlocalityrange_list')
