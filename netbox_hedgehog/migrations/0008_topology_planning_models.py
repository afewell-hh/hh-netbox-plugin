# Generated manually (cleaned from auto-generated migration)
# Removes problematic AlterField operations, keeps only new DIET models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0216_latitude_longitude_validators'),  # NetBox core dependency for DeviceType FK
        ('netbox_hedgehog', '0007_add_count_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='BreakoutOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('breakout_id', models.CharField(help_text="Unique breakout identifier (e.g., '2x400g', '4x200g')", max_length=50, unique=True)),
                ('from_speed', models.IntegerField(help_text='Native port speed in Gbps (e.g., 800 for 800G)')),
                ('logical_ports', models.IntegerField(help_text='Number of logical ports after breakout (e.g., 4 for 4x200G)')),
                ('logical_speed', models.IntegerField(help_text='Speed per logical port in Gbps (e.g., 200 for 4x200G)')),
                ('optic_type', models.CharField(blank=True, help_text="Optic type for this breakout (e.g., 'QSFP-DD', 'QSFP28')", max_length=50)),
            ],
            options={
                'verbose_name': 'Breakout Option',
                'verbose_name_plural': 'Breakout Options',
                'ordering': ['-from_speed', 'logical_ports'],
            },
        ),
        migrations.CreateModel(
            name='DeviceTypeExtension',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('mclag_capable', models.BooleanField(default=False, help_text='Whether this device supports MCLAG (Multi-Chassis Link Aggregation)')),
                ('hedgehog_roles', models.JSONField(blank=True, default=list, help_text='List of supported Hedgehog roles: spine, server-leaf, border-leaf, virtual')),
                ('notes', models.TextField(blank=True, help_text='Additional Hedgehog-specific notes about this device type')),
                ('device_type', models.OneToOneField(help_text='NetBox DeviceType this metadata applies to', on_delete=django.db.models.deletion.CASCADE, related_name='hedgehog_metadata', to='dcim.devicetype')),
            ],
            options={
                'verbose_name': 'Device Type Extension (Hedgehog)',
                'verbose_name_plural': 'Device Type Extensions (Hedgehog)',
            },
        ),
    ]
