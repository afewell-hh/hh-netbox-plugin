"""Migration 0031: Add nullable target_zone FK to PlanServerConnection."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0030_nic_modeling_clean_break'),
    ]

    operations = [
        migrations.AddField(
            model_name='planserverconnection',
            name='target_zone',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='server_connections',
                to='netbox_hedgehog.switchportzone',
                help_text='Switch port zone this connection targets',
            ),
        ),
    ]
