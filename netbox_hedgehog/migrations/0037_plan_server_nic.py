"""
Migration 0037: Add PlanServerNIC model and nullable nic FK to PlanServerConnection.

Phase 1 of 2 (DIET-294):
- Creates the PlanServerNIC table with the standard NetBoxModel pattern
  (tags, custom_field_data with CustomFieldJSONEncoder, DeleteMixin base).
- Adds a nullable `nic` FK to PlanServerConnection.
- Runs backfill: one PlanServerNIC per existing PlanServerConnection,
  using connection_id as nic_id and nic_module_type as module_type.

Migration 0038 enforces NOT NULL and drops nic_module_type.
"""

import django.db.models.deletion
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


def backfill_plan_server_nics(apps, schema_editor):
    """
    Create one PlanServerNIC per existing PlanServerConnection.

    Uses connection_id as nic_id and nic_module_type as module_type.
    Then sets nic FK on each connection to the newly created NIC.

    This bridges the old connection-centric model to the NIC-first model.
    Two connections on the same server_class+nic_id pair reuse the same NIC.
    """
    PlanServerNIC = apps.get_model('netbox_hedgehog', 'PlanServerNIC')
    PlanServerConnection = apps.get_model('netbox_hedgehog', 'PlanServerConnection')

    for conn in PlanServerConnection.objects.select_related(
        'server_class', 'nic_module_type'
    ).all():
        if conn.nic_module_type_id is None:
            # Defensive: skip connections without a module_type
            continue

        # Use connection_id as nic_id for backfill.
        # NIC identity = server_class + connection_id (one card per connection).
        nic, _ = PlanServerNIC.objects.get_or_create(
            server_class=conn.server_class,
            nic_id=conn.connection_id,
            defaults={
                'module_type': conn.nic_module_type,
                'description': f'Backfilled from connection {conn.connection_id}',
                'custom_field_data': {},
            },
        )
        conn.nic = nic
        conn.save(update_fields=['nic'])


def remove_backfilled_nics(apps, schema_editor):
    """Reverse: remove all backfilled NICs."""
    PlanServerNIC = apps.get_model('netbox_hedgehog', 'PlanServerNIC')
    PlanServerNIC.objects.filter(
        description__startswith='Backfilled from connection '
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0001_initial'),
        ('extras', '0133_make_cf_minmax_decimal'),
        ('netbox_hedgehog', '0036_fabric_class_abstraction'),
    ]

    operations = [
        # 1. Create PlanServerNIC table with full NetBoxModel pattern.
        migrations.CreateModel(
            name='PlanServerNIC',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(
                    blank=True,
                    default=dict,
                    encoder=utilities.json.CustomFieldJSONEncoder,
                )),
                ('nic_id', models.CharField(
                    max_length=100,
                    help_text=(
                        "Unique NIC identifier within this server class "
                        "(e.g., 'nic-fe', 'nic-be-rail-0'). "
                        "Used as ModuleBay name and interface name prefix."
                    ),
                )),
                ('description', models.TextField(blank=True, help_text='Optional description')),
                ('server_class', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='nics',
                    to='netbox_hedgehog.planserverclass',
                    help_text='Server class this NIC belongs to',
                )),
                ('module_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='plan_server_nics',
                    to='dcim.moduletype',
                    help_text='NetBox ModuleType for this NIC',
                )),
                ('tags', taggit.managers.TaggableManager(
                    through='extras.TaggedItem',
                    to='extras.Tag',
                )),
            ],
            options={
                'verbose_name': 'Server NIC',
                'verbose_name_plural': 'Server NICs',
                'ordering': ['server_class', 'nic_id'],
                'unique_together': {('server_class', 'nic_id')},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),

        # 2. Add nullable nic FK to PlanServerConnection.
        migrations.AddField(
            model_name='planserverconnection',
            name='nic',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='connections',
                to='netbox_hedgehog.planservernic',
                help_text='Physical NIC card this connection uses',
            ),
        ),

        # 3. Backfill: one NIC per connection.
        migrations.RunPython(backfill_plan_server_nics, remove_backfilled_nics),
    ]
