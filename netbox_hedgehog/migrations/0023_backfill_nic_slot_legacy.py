# Data migration for Issue #138 - Backfill nic_slot for legacy connections
# Sets nic_slot = connection_id for connections where both server_interface_template
# and nic_slot are NULL/empty to enable legacy naming mode.

from django.db import migrations


def backfill_nic_slot(apps, schema_editor):
    """
    Backfill nic_slot for connections with both fields NULL.

    This ensures existing connections work with the new validation that
    requires either server_interface_template OR nic_slot to be set.
    """
    PlanServerConnection = apps.get_model('netbox_hedgehog', 'PlanServerConnection')

    # Find connections with both fields NULL/empty
    connections_to_fix = PlanServerConnection.objects.filter(
        server_interface_template__isnull=True,
    ).filter(
        # Django treats empty string and NULL differently, check both
        nic_slot__isnull=True
    ) | PlanServerConnection.objects.filter(
        server_interface_template__isnull=True,
        nic_slot=''
    )

    count = 0
    for conn in connections_to_fix:
        conn.nic_slot = conn.connection_id
        conn.save(update_fields=['nic_slot'])
        count += 1

    if count > 0:
        print(f"  ✓ Backfilled nic_slot for {count} legacy connections")


def reverse_backfill(apps, schema_editor):
    """
    Reverse migration: clear nic_slot where it equals connection_id.

    This is a best-effort reversal - we can't distinguish between
    user-set values that happen to match connection_id and auto-filled ones.
    """
    PlanServerConnection = apps.get_model('netbox_hedgehog', 'PlanServerConnection')

    # Clear nic_slot where it matches connection_id (likely auto-filled)
    connections = PlanServerConnection.objects.filter(
        server_interface_template__isnull=True,
    )

    count = 0
    for conn in connections:
        if conn.nic_slot == conn.connection_id:
            conn.nic_slot = ''
            conn.save(update_fields=['nic_slot'])
            count += 1

    if count > 0:
        print(f"  ✓ Cleared nic_slot for {count} connections")


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0022_add_server_interface_template'),
    ]

    operations = [
        migrations.RunPython(backfill_nic_slot, reverse_backfill),
    ]
