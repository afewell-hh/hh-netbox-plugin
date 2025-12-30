# Manual migration for operational model Meta cleanup
#
# This migration addresses Django/NetBox compatibility warnings for operational
# (CRD-sync) models. It removes obsolete Meta options and unique_together
# constraints that are no longer needed.
#
# EXCLUDES problematic AlterField operations on inherited NetBoxModel fields
# (tags, custom_field_data) which cause migration failures.
#
# Related: Issue #129

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0020_make_uplink_ports_per_switch_nullable'),
    ]

    operations = [
        # Clear obsolete Meta options for operational models
        migrations.AlterModelOptions(
            name='connection',
            options={},
        ),
        migrations.AlterModelOptions(
            name='external',
            options={},
        ),
        migrations.AlterModelOptions(
            name='externalattachment',
            options={},
        ),
        migrations.AlterModelOptions(
            name='externalpeering',
            options={},
        ),
        migrations.AlterModelOptions(
            name='ipv4namespace',
            options={},
        ),
        migrations.AlterModelOptions(
            name='server',
            options={},
        ),
        migrations.AlterModelOptions(
            name='switch',
            options={},
        ),
        migrations.AlterModelOptions(
            name='switchgroup',
            options={},
        ),
        migrations.AlterModelOptions(
            name='vlannamespace',
            options={},
        ),
        migrations.AlterModelOptions(
            name='vpc',
            options={},
        ),
        migrations.AlterModelOptions(
            name='vpcattachment',
            options={},
        ),
        migrations.AlterModelOptions(
            name='vpcpeering',
            options={},
        ),

        # Clear obsolete unique_together constraints
        migrations.AlterUniqueTogether(
            name='connection',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='external',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='externalattachment',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='externalpeering',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='ipv4namespace',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='server',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='switch',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='switchgroup',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='vlannamespace',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='vpc',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='vpcattachment',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='vpcpeering',
            unique_together=set(),
        ),
    ]
