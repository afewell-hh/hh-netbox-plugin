# Manual migration for Issue #138 - Add server_interface_template field
# Generated manually to avoid Django's auto-generated AlterField operations
# which conflict with existing M2M field definitions.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0216_latitude_longitude_validators'),
        ('netbox_hedgehog', '0021_generationstate_job'),
    ]

    operations = [
        migrations.AddField(
            model_name='planserverconnection',
            name='server_interface_template',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='plan_server_connections',
                to='dcim.interfacetemplate',
                help_text="First server interface template for this connection. "
                          "If ports_per_connection > 1, subsequent interfaces will be used in order. "
                          "If not set and nic_slot is provided, uses legacy naming mode."
            ),
        ),
    ]
