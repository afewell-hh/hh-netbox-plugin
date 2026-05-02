"""
Migration 0051: Remove legacy flat transceiver fields from PlanServerConnection.

Removes cage_type, medium, connector, and standard — flat attributes that were
superseded by the transceiver_module_type FK in DIET-334 Stage 2.  The FK is
now the single authoritative writable field; cross-end compatibility is handled
by the review pane rule engine, not save-time validation.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0050_seed_qsfp112_200gbase_sr2'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='planserverconnection',
            name='cage_type',
        ),
        migrations.RemoveField(
            model_name='planserverconnection',
            name='medium',
        ),
        migrations.RemoveField(
            model_name='planserverconnection',
            name='connector',
        ),
        migrations.RemoveField(
            model_name='planserverconnection',
            name='standard',
        ),
    ]
