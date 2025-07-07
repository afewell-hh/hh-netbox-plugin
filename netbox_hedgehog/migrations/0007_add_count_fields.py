# Generated migration for adding count fields to HedgehogFabric

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0006_missing_crd_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='connections_count',
            field=models.PositiveIntegerField(default=0, help_text='Count of Connection CRDs'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='servers_count',
            field=models.PositiveIntegerField(default=0, help_text='Count of Server CRDs'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='switches_count',
            field=models.PositiveIntegerField(default=0, help_text='Count of Switch CRDs'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='vpcs_count',
            field=models.PositiveIntegerField(default=0, help_text='Count of VPC CRDs'),
        ),
    ]