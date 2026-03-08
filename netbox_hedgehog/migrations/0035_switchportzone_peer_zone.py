from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0034_fabrictype_expand_management_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='switchportzone',
            name='peer_zone',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='peer_zones',
                to='netbox_hedgehog.switchportzone',
                help_text=(
                    'Target zone on the managed switch that this zone uplinks to. '
                    'Used for surrogate-switch uplink generation (Option A explicit target). '
                    'Set on the oob-mgmt uplink zone to point at the fe-border-leaf oob zone.'
                ),
            ),
        ),
    ]
