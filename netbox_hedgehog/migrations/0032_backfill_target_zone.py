"""Migration 0032: Backfill target_zone from target_switch_class + scoped snapshot reset."""

from django.db import migrations
from django.db.utils import DataError


def backfill_target_zone(apps, schema_editor):
    """
    Auto-resolve target_zone from target_switch_class for existing connections.

    Cases:
      A: exactly 1 zone of matching type  -> auto-assign
      B: >1 zones of matching type        -> halt with diagnostics
      C1: 0 of type, 1 total              -> warn+auto (use fallback)
      D: 0 zones total                    -> halt with diagnostics
    """
    PlanServerConnection = apps.get_model('netbox_hedgehog', 'PlanServerConnection')
    SwitchPortZone = apps.get_model('netbox_hedgehog', 'SwitchPortZone')

    errors = []
    for conn in PlanServerConnection.objects.filter(
        target_zone__isnull=True
    ).select_related('target_switch_class', 'server_class'):
        sw = conn.target_switch_class
        zone_type = 'oob' if conn.port_type == 'ipmi' else 'server'
        candidates = list(
            SwitchPortZone.objects.filter(
                switch_class=sw, zone_type=zone_type
            ).order_by('priority')
        )
        if len(candidates) == 1:
            conn.target_zone = candidates[0]
            conn.save(update_fields=['target_zone'])
        elif len(candidates) > 1:
            errors.append(
                f"AMBIGUOUS: {conn.server_class.server_class_id}/"
                f"{conn.connection_id} -> {sw.switch_class_id}: "
                f"candidates={[z.zone_name for z in candidates]}"
            )
        else:
            fallback = list(
                SwitchPortZone.objects.filter(switch_class=sw).order_by('priority')
            )
            if len(fallback) == 1:
                conn.target_zone = fallback[0]
                conn.save(update_fields=['target_zone'])
            else:
                reason = 'no zones' if not fallback else 'fallback ambiguous'
                errors.append(
                    f"UNRESOLVABLE: {conn.server_class.server_class_id}/"
                    f"{conn.connection_id} -> {sw.switch_class_id}: {reason}"
                )
    if errors:
        raise DataError(
            'Migration blocked: connections cannot be auto-resolved.\n'
            + '\n'.join(errors)
        )


def reset_affected_snapshots(apps, schema_editor):
    """Reset GenerationState snapshots for plans that have connections."""
    PlanServerConnection = apps.get_model('netbox_hedgehog', 'PlanServerConnection')
    GenerationState = apps.get_model('netbox_hedgehog', 'GenerationState')

    affected = (
        PlanServerConnection.objects
        .values_list('server_class__plan_id', flat=True)
        .distinct()
    )
    GenerationState.objects.filter(plan_id__in=affected).update(snapshot={})


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0031_add_target_zone_nullable'),
    ]

    operations = [
        migrations.RunPython(
            backfill_target_zone,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            reset_affected_snapshots,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
