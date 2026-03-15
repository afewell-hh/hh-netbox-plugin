"""
Migration 0038: Finalize NIC-first model (DIET-294).

Phase 2 of 2:
- Pre-flight check: raise if any PlanServerConnection has nic=NULL.
- Add transceiver fields (cage_type, medium, connector, standard) to PlanServerConnection.
- Enforce nic NOT NULL on PlanServerConnection.
- Remove nic_module_type FK from PlanServerConnection.
- Add hedgehog_transceiver_spec custom field on dcim.Interface.
"""

import django.db.models.deletion
from django.db import migrations, models


def check_all_connections_have_nic(apps, schema_editor):
    """
    Pre-flight check: raise if any PlanServerConnection has nic=NULL.

    Migration 0037 backfilled NICs for all existing connections.
    If this check fails something went wrong in the backfill.
    Tag: DIET-294
    """
    PlanServerConnection = apps.get_model('netbox_hedgehog', 'PlanServerConnection')
    null_count = PlanServerConnection.objects.filter(nic__isnull=True).count()
    if null_count > 0:
        raise Exception(
            f"DIET-294 migration pre-flight failed: {null_count} PlanServerConnection "
            "row(s) still have nic=NULL after 0037 backfill. "
            "Run migration 0037 first and ensure all connections have a NIC assigned."
        )


def _noop(apps, schema_editor):
    pass


def add_transceiver_spec_custom_field(apps, schema_editor):
    """Add hedgehog_transceiver_spec custom field on dcim.Interface."""
    CustomField = apps.get_model('extras', 'CustomField')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Interface = apps.get_model('dcim', 'Interface')

    interface_ct = ContentType.objects.get_for_model(Interface)

    cf, created = CustomField.objects.get_or_create(
        name='hedgehog_transceiver_spec',
        defaults={
            'label': 'Hedgehog Transceiver Spec',
            'type': 'text',
            'description': 'Transceiver review spec (CAGE|MEDIUM|CONNECTOR|STD) on server interfaces.',
            'required': False,
            'weight': 110,
        },
    )
    cf.object_types.add(interface_ct)


def remove_transceiver_spec_custom_field(apps, schema_editor):
    CustomField = apps.get_model('extras', 'CustomField')
    CustomField.objects.filter(name='hedgehog_transceiver_spec').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0037_plan_server_nic'),
    ]

    operations = [
        # 1. Pre-flight: raise if nic=NULL exists (backfill must have completed in 0037).
        migrations.RunPython(check_all_connections_have_nic, _noop),

        # 2. Add transceiver review fields.
        migrations.AddField(
            model_name='planserverconnection',
            name='cage_type',
            field=models.CharField(
                max_length=20, blank=True, default='',
                choices=[
                    ('QSFP112', 'QSFP112'), ('OSFP', 'OSFP'), ('QSFP-DD', 'QSFP-DD'),
                    ('QSFP28', 'QSFP28'), ('SFP28', 'SFP28'), ('SFP+', 'SFP+'), ('RJ45', 'RJ45'),
                ],
                help_text='Transceiver cage/port form factor',
            ),
        ),
        migrations.AddField(
            model_name='planserverconnection',
            name='medium',
            field=models.CharField(
                max_length=10, blank=True, default='',
                choices=[
                    ('MMF', 'Multimode Fiber (MMF)'), ('SMF', 'Single-mode Fiber (SMF)'),
                    ('DAC', 'Direct-Attach Copper (DAC)'), ('ACC', 'Active Copper Cable (ACC)'),
                ],
                help_text='Physical transmission medium',
            ),
        ),
        migrations.AddField(
            model_name='planserverconnection',
            name='connector',
            field=models.CharField(
                max_length=10, blank=True, default='',
                choices=[
                    ('LC', 'LC Duplex'), ('MPO-12', 'MPO-12'), ('MPO-16', 'MPO-16'),
                    ('Direct', 'Direct Attach (no connector)'),
                ],
                help_text='Fiber connector type',
            ),
        ),
        migrations.AddField(
            model_name='planserverconnection',
            name='standard',
            field=models.CharField(
                max_length=50, blank=True, default='',
                help_text='Optical/electrical standard (e.g., 200GBASE-SR4)',
            ),
        ),

        # 3. Enforce nic NOT NULL.
        migrations.AlterField(
            model_name='planserverconnection',
            name='nic',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='connections',
                to='netbox_hedgehog.planservernic',
                help_text='Physical NIC card this connection uses (DIET-294 NIC-first model)',
            ),
        ),

        # 4. Remove nic_module_type.
        migrations.RemoveField(
            model_name='planserverconnection',
            name='nic_module_type',
        ),

        # 5. Add hedgehog_transceiver_spec custom field on Interface.
        migrations.RunPython(
            add_transceiver_spec_custom_field,
            remove_transceiver_spec_custom_field,
        ),
    ]
