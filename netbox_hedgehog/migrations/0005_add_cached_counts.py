# Generated migration for adding cached CRD count fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0004_add_connection_error'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='cached_crd_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Cached total count of CRDs (updated during sync)'
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='cached_vpc_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Cached VPC count (updated during sync)'
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='cached_connection_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Cached Connection count (updated during sync)'
            ),
        ),
    ]