# Generated manually for DIET-132

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0020_make_uplink_ports_per_switch_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='generationstate',
            name='job',
            field=models.ForeignKey(
                blank=True,
                help_text='NetBox Job executing or that executed this generation',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='topology_generation',
                to='core.job'
            ),
        ),
    ]
