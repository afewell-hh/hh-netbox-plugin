# Manually written migration for DIET-309: make PlanMeshLink.plan nullable
# and PlanMeshLink.fabric_name blank.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0039_mesh_topology_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='planmeshlink',
            name='plan',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='mesh_links',
                to='netbox_hedgehog.topologyplan',
            ),
        ),
        migrations.AlterField(
            model_name='planmeshlink',
            name='fabric_name',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
