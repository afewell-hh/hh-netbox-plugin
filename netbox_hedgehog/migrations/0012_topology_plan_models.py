# Generated manually for DIET-002 - Topology Plan Models (Review Fixes)
# Addresses review findings:
# - Remove duplicate created_at/updated_at (use NetBoxModel.created/last_updated)
# - Add ConnectionTypeChoices to hedgehog_conn_type
# - Make speed required (MinValueValidator(1))
# - Update get_absolute_url() names to *_detail convention

import django.core.validators
import django.db.models.deletion
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0216_latitude_longitude_validators'),
        ('extras', '0133_make_cf_minmax_decimal'),
        ('netbox_hedgehog', '0011_update_device_type_extension_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TopologyPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('name', models.CharField(help_text="Plan name (e.g., 'Cambium 2MW', '128-GPU Training Cluster')", max_length=200)),
                ('customer_name', models.CharField(blank=True, help_text='Customer or project name', max_length=200)),
                ('description', models.TextField(blank=True, help_text='Detailed description of the topology plan')),
                ('status', models.CharField(default='draft', help_text='Current status of the plan', max_length=50)),
                ('notes', models.TextField(blank=True, help_text='Additional notes about this plan')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this plan', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='topology_plans', to=settings.AUTH_USER_MODEL)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Topology Plan',
                'verbose_name_plural': 'Topology Plans',
                'ordering': ['-created'],
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='PlanSwitchClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('switch_class_id', models.CharField(help_text="Unique identifier for this switch class (e.g., 'fe-gpu-leaf')", max_length=100)),
                ('fabric', models.CharField(blank=True, help_text='Fabric type (Frontend, Backend, OOB)', max_length=50)),
                ('hedgehog_role', models.CharField(blank=True, help_text='Hedgehog role (spine, server-leaf, border-leaf, virtual)', max_length=50)),
                ('uplink_ports_per_switch', models.IntegerField(default=0, help_text='Number of ports reserved for uplinks (spine connections)', validators=[django.core.validators.MinValueValidator(0)])),
                ('mclag_pair', models.BooleanField(default=False, help_text='Whether switches are deployed in MCLAG pairs')),
                ('calculated_quantity', models.IntegerField(blank=True, editable=False, help_text='Automatically calculated switch quantity (computed by calc engine)', null=True)),
                ('override_quantity', models.IntegerField(blank=True, help_text='User override for switch quantity (leave blank to use calculated)', null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('notes', models.TextField(blank=True, help_text='Additional notes about this switch class')),
                ('device_type_extension', models.ForeignKey(help_text='DeviceTypeExtension with Hedgehog metadata for this switch model', on_delete=django.db.models.deletion.PROTECT, related_name='plan_switch_classes', to='netbox_hedgehog.devicetypeextension')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('plan', models.ForeignKey(help_text='Topology plan this switch class belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='switch_classes', to='netbox_hedgehog.topologyplan')),
            ],
            options={
                'verbose_name': 'Switch Class',
                'verbose_name_plural': 'Switch Classes',
                'ordering': ['plan', 'fabric', 'switch_class_id'],
                'unique_together': {('plan', 'switch_class_id')},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='PlanServerClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('server_class_id', models.CharField(help_text="Unique identifier for this server class (e.g., 'GPU-B200', 'INF-001')", max_length=100)),
                ('description', models.TextField(blank=True, help_text='Description of this server class')),
                ('category', models.CharField(blank=True, help_text='Server category (GPU, Storage, Infrastructure)', max_length=50)),
                ('quantity', models.IntegerField(help_text='Number of servers of this class (PRIMARY USER INPUT)', validators=[django.core.validators.MinValueValidator(1)])),
                ('gpus_per_server', models.IntegerField(default=0, help_text='Number of GPUs per server (for GPU server classes)', validators=[django.core.validators.MinValueValidator(0)])),
                ('notes', models.TextField(blank=True, help_text='Additional notes about this server class')),
                ('server_device_type', models.ForeignKey(help_text='NetBox DeviceType for this server model', on_delete=django.db.models.deletion.PROTECT, related_name='plan_server_classes', to='dcim.devicetype')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('plan', models.ForeignKey(help_text='Topology plan this server class belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='server_classes', to='netbox_hedgehog.topologyplan')),
            ],
            options={
                'verbose_name': 'Server Class',
                'verbose_name_plural': 'Server Classes',
                'ordering': ['plan', 'server_class_id'],
                'unique_together': {('plan', 'server_class_id')},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='PlanServerConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('connection_id', models.CharField(help_text="Unique connection identifier (e.g., 'FE-001', 'BE-RAIL-0')", max_length=100)),
                ('nic_slot', models.CharField(blank=True, help_text="NIC slot identifier (e.g., 'NIC1', 'enp1s0f0')", max_length=50)),
                ('connection_name', models.CharField(blank=True, help_text="Descriptive connection name (e.g., 'frontend', 'backend-rail-0')", max_length=100)),
                ('ports_per_connection', models.IntegerField(help_text='Number of ports used for this connection', validators=[django.core.validators.MinValueValidator(1)])),
                ('hedgehog_conn_type', models.CharField(default='unbundled', help_text='Hedgehog connection type (unbundled, bundled, mclag, eslag)', max_length=50)),
                ('distribution', models.CharField(blank=True, help_text='Port distribution strategy (same-switch, alternating, rail-optimized)', max_length=50)),
                ('speed', models.IntegerField(help_text='Connection speed in Gbps (e.g., 200 for 200G)', validators=[django.core.validators.MinValueValidator(1)])),
                ('rail', models.IntegerField(blank=True, help_text='Rail number for rail-optimized distribution (0-7 for 8-rail backend)', null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('port_type', models.CharField(blank=True, help_text='Port type (data, ipmi, pxe)', max_length=50)),
                ('nic_module_type', models.ForeignKey(blank=True, help_text='NIC module type (optional for MVP)', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='plan_server_connections', to='dcim.moduletype')),
                ('server_class', models.ForeignKey(help_text='Server class this connection belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='connections', to='netbox_hedgehog.planserverclass')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('target_switch_class', models.ForeignKey(help_text='Switch class this connection targets', on_delete=django.db.models.deletion.PROTECT, related_name='incoming_connections', to='netbox_hedgehog.planswitchclass')),
            ],
            options={
                'verbose_name': 'Server Connection',
                'verbose_name_plural': 'Server Connections',
                'ordering': ['server_class', 'connection_id'],
                'unique_together': {('server_class', 'connection_id')},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='PlanMCLAGDomain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('domain_id', models.CharField(help_text="Unique MCLAG domain identifier (e.g., 'MCLAG-001')", max_length=100)),
                ('peer_link_count', models.IntegerField(help_text='Number of peer links between switch pair', validators=[django.core.validators.MinValueValidator(1)])),
                ('session_link_count', models.IntegerField(help_text='Number of session links between switch pair', validators=[django.core.validators.MinValueValidator(1)])),
                ('peer_start_port', models.IntegerField(default=0, help_text='Starting port number for peer links', validators=[django.core.validators.MinValueValidator(0)])),
                ('session_start_port', models.IntegerField(default=0, help_text='Starting port number for session links', validators=[django.core.validators.MinValueValidator(0)])),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('switch_class', models.ForeignKey(help_text='Switch class this MCLAG domain applies to', on_delete=django.db.models.deletion.CASCADE, related_name='mclag_domains', to='netbox_hedgehog.planswitchclass')),
                ('plan', models.ForeignKey(help_text='Topology plan this MCLAG domain belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='mclag_domains', to='netbox_hedgehog.topologyplan')),
            ],
            options={
                'verbose_name': 'MCLAG Domain',
                'verbose_name_plural': 'MCLAG Domains',
                'ordering': ['plan', 'domain_id'],
                'unique_together': {('plan', 'domain_id')},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
    ]
