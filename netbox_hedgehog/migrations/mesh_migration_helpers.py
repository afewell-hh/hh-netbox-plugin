"""
Migration helpers for DIET-317: explicit manual mesh topology mode.

This module is importable from test code to verify data migration logic.
The Migration class below is empty (no schema changes) — this file exists
so that rename_prefer_mesh() is importable from the migrations package
while remaining discoverable by Django's migration loader.
"""

from django.db import migrations


def rename_prefer_mesh():
    """
    Rename all PlanSwitchClass rows with topology_mode='prefer-mesh' to 'mesh'.

    Called by migration 0043 and available for test-level regression guards.
    """
    from netbox_hedgehog.models.topology_planning import PlanSwitchClass
    PlanSwitchClass.objects.filter(topology_mode='prefer-mesh').update(topology_mode='mesh')


class Migration(migrations.Migration):
    """Empty leaf migration; exists only to make the helpers module discoverable."""

    dependencies = [
        ('netbox_hedgehog', '0043_explicit_mesh_mode'),
    ]

    operations = []
