"""Migration 0033: Make target_zone required and remove target_switch_class."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0032_backfill_target_zone'),
    ]

    operations = [
        migrations.AlterField(
            model_name='planserverconnection',
            name='target_zone',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='server_connections',
                to='netbox_hedgehog.switchportzone',
                help_text='Switch port zone this connection targets',
            ),
        ),
        migrations.RemoveField(
            model_name='planserverconnection',
            name='target_switch_class',
        ),
    ]
