# Migration for DIET-309 review fixes:
# - Add leaf1_name and leaf2_name to PlanMeshLink (Finding 4)
# - Make PlanMeshLink.plan non-nullable (Finding 5)
#   Existing NULL rows are deleted first via RunPython.

import django.db.models.deletion
from django.db import migrations, models


def delete_orphan_mesh_links(apps, schema_editor):
    """Delete PlanMeshLink rows with null plan FK before making it non-nullable."""
    PlanMeshLink = apps.get_model('netbox_hedgehog', 'PlanMeshLink')
    PlanMeshLink.objects.filter(plan__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0040_mesh_link_nullable_plan'),
    ]

    operations = [
        # Step 1: remove orphan rows so we can safely make plan non-nullable
        migrations.RunPython(delete_orphan_mesh_links, migrations.RunPython.noop),

        # Step 2: make plan non-nullable
        migrations.AlterField(
            model_name='planmeshlink',
            name='plan',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='mesh_links',
                to='netbox_hedgehog.topologyplan',
            ),
        ),

        # Step 3: add leaf1_name
        migrations.AddField(
            model_name='planmeshlink',
            name='leaf1_name',
            field=models.CharField(
                blank=True,
                max_length=200,
                help_text='Physical switch name for leaf1',
            ),
        ),

        # Step 4: add leaf2_name
        migrations.AddField(
            model_name='planmeshlink',
            name='leaf2_name',
            field=models.CharField(
                blank=True,
                max_length=200,
                help_text='Physical switch name for leaf2',
            ),
        ),
    ]
