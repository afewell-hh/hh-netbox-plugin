# Generated migration for missing CRD models

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0005_add_cached_counts'),
        ('extras', '0098_webhook_custom_field_data_webhook_tags'),
    ]

    operations = [
        # IPv4Namespace
        migrations.CreateModel(
            name='IPv4Namespace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('name', models.CharField(help_text='Kubernetes resource name (must be DNS-1123 compliant)', max_length=253)),
                ('namespace', models.CharField(default='default', help_text='Kubernetes namespace for this resource', max_length=253)),
                ('spec', models.JSONField(help_text='CRD specification as JSON')),
                ('labels', models.JSONField(blank=True, default=dict, help_text='Kubernetes labels as JSON')),
                ('annotations', models.JSONField(blank=True, default=dict, help_text='Kubernetes annotations as JSON')),
                ('kubernetes_status', models.CharField(choices=[('unknown', 'Unknown'), ('pending', 'Pending'), ('applied', 'Applied'), ('live', 'Live'), ('error', 'Error'), ('deleting', 'Deleting')], default='unknown', help_text='Current status in Kubernetes', max_length=20)),
                ('kubernetes_uid', models.CharField(blank=True, help_text='Kubernetes resource UID', max_length=36)),
                ('kubernetes_resource_version', models.CharField(blank=True, help_text='Kubernetes resource version', max_length=50)),
                ('last_applied', models.DateTimeField(blank=True, help_text='When this CRD was last applied to Kubernetes', null=True)),
                ('last_synced', models.DateTimeField(blank=True, help_text='When this CRD was last synced from Kubernetes', null=True)),
                ('sync_error', models.TextField(blank=True, help_text='Last sync error message (if any)')),
                ('auto_sync', models.BooleanField(default=True, help_text='Enable automatic sync for this resource')),
                ('fabric', models.ForeignKey(help_text='Hedgehog fabric this CRD belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='ipv4namespace_set', to='netbox_hedgehog.hedgehogfabric')),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
            ],
            options={
                'verbose_name': 'IPv4 Namespace',
                'verbose_name_plural': 'IPv4 Namespaces',
                'ordering': ['fabric', 'namespace', 'name'],
                'unique_together': {('fabric', 'namespace', 'name')},
            },
        ),
        
        # ExternalAttachment
        migrations.CreateModel(
            name='ExternalAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('name', models.CharField(help_text='Kubernetes resource name (must be DNS-1123 compliant)', max_length=253)),
                ('namespace', models.CharField(default='default', help_text='Kubernetes namespace for this resource', max_length=253)),
                ('spec', models.JSONField(help_text='CRD specification as JSON')),
                ('labels', models.JSONField(blank=True, default=dict, help_text='Kubernetes labels as JSON')),
                ('annotations', models.JSONField(blank=True, default=dict, help_text='Kubernetes annotations as JSON')),
                ('kubernetes_status', models.CharField(choices=[('unknown', 'Unknown'), ('pending', 'Pending'), ('applied', 'Applied'), ('live', 'Live'), ('error', 'Error'), ('deleting', 'Deleting')], default='unknown', help_text='Current status in Kubernetes', max_length=20)),
                ('kubernetes_uid', models.CharField(blank=True, help_text='Kubernetes resource UID', max_length=36)),
                ('kubernetes_resource_version', models.CharField(blank=True, help_text='Kubernetes resource version', max_length=50)),
                ('last_applied', models.DateTimeField(blank=True, help_text='When this CRD was last applied to Kubernetes', null=True)),
                ('last_synced', models.DateTimeField(blank=True, help_text='When this CRD was last synced from Kubernetes', null=True)),
                ('sync_error', models.TextField(blank=True, help_text='Last sync error message (if any)')),
                ('auto_sync', models.BooleanField(default=True, help_text='Enable automatic sync for this resource')),
                ('fabric', models.ForeignKey(help_text='Hedgehog fabric this CRD belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='externalattachment_set', to='netbox_hedgehog.hedgehogfabric')),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
            ],
            options={
                'verbose_name': 'External Attachment',
                'verbose_name_plural': 'External Attachments',
                'ordering': ['fabric', 'namespace', 'name'],
                'unique_together': {('fabric', 'namespace', 'name')},
            },
        ),
        
        # ExternalPeering
        migrations.CreateModel(
            name='ExternalPeering',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('name', models.CharField(help_text='Kubernetes resource name (must be DNS-1123 compliant)', max_length=253)),
                ('namespace', models.CharField(default='default', help_text='Kubernetes namespace for this resource', max_length=253)),
                ('spec', models.JSONField(help_text='CRD specification as JSON')),
                ('labels', models.JSONField(blank=True, default=dict, help_text='Kubernetes labels as JSON')),
                ('annotations', models.JSONField(blank=True, default=dict, help_text='Kubernetes annotations as JSON')),
                ('kubernetes_status', models.CharField(choices=[('unknown', 'Unknown'), ('pending', 'Pending'), ('applied', 'Applied'), ('live', 'Live'), ('error', 'Error'), ('deleting', 'Deleting')], default='unknown', help_text='Current status in Kubernetes', max_length=20)),
                ('kubernetes_uid', models.CharField(blank=True, help_text='Kubernetes resource UID', max_length=36)),
                ('kubernetes_resource_version', models.CharField(blank=True, help_text='Kubernetes resource version', max_length=50)),
                ('last_applied', models.DateTimeField(blank=True, help_text='When this CRD was last applied to Kubernetes', null=True)),
                ('last_synced', models.DateTimeField(blank=True, help_text='When this CRD was last synced from Kubernetes', null=True)),
                ('sync_error', models.TextField(blank=True, help_text='Last sync error message (if any)')),
                ('auto_sync', models.BooleanField(default=True, help_text='Enable automatic sync for this resource')),
                ('fabric', models.ForeignKey(help_text='Hedgehog fabric this CRD belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='externalpeering_set', to='netbox_hedgehog.hedgehogfabric')),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
            ],
            options={
                'verbose_name': 'External Peering',
                'verbose_name_plural': 'External Peerings',
                'ordering': ['fabric', 'namespace', 'name'],
                'unique_together': {('fabric', 'namespace', 'name')},
            },
        ),
        
        # Server
        migrations.CreateModel(
            name='Server',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('name', models.CharField(help_text='Kubernetes resource name (must be DNS-1123 compliant)', max_length=253)),
                ('namespace', models.CharField(default='default', help_text='Kubernetes namespace for this resource', max_length=253)),
                ('spec', models.JSONField(help_text='CRD specification as JSON')),
                ('labels', models.JSONField(blank=True, default=dict, help_text='Kubernetes labels as JSON')),
                ('annotations', models.JSONField(blank=True, default=dict, help_text='Kubernetes annotations as JSON')),
                ('kubernetes_status', models.CharField(choices=[('unknown', 'Unknown'), ('pending', 'Pending'), ('applied', 'Applied'), ('live', 'Live'), ('error', 'Error'), ('deleting', 'Deleting')], default='unknown', help_text='Current status in Kubernetes', max_length=20)),
                ('kubernetes_uid', models.CharField(blank=True, help_text='Kubernetes resource UID', max_length=36)),
                ('kubernetes_resource_version', models.CharField(blank=True, help_text='Kubernetes resource version', max_length=50)),
                ('last_applied', models.DateTimeField(blank=True, help_text='When this CRD was last applied to Kubernetes', null=True)),
                ('last_synced', models.DateTimeField(blank=True, help_text='When this CRD was last synced from Kubernetes', null=True)),
                ('sync_error', models.TextField(blank=True, help_text='Last sync error message (if any)')),
                ('auto_sync', models.BooleanField(default=True, help_text='Enable automatic sync for this resource')),
                ('fabric', models.ForeignKey(help_text='Hedgehog fabric this CRD belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='server_set', to='netbox_hedgehog.hedgehogfabric')),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
            ],
            options={
                'verbose_name': 'Server',
                'verbose_name_plural': 'Servers',
                'ordering': ['fabric', 'namespace', 'name'],
                'unique_together': {('fabric', 'namespace', 'name')},
            },
        ),
        
        # SwitchGroup
        migrations.CreateModel(
            name='SwitchGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('name', models.CharField(help_text='Kubernetes resource name (must be DNS-1123 compliant)', max_length=253)),
                ('namespace', models.CharField(default='default', help_text='Kubernetes namespace for this resource', max_length=253)),
                ('spec', models.JSONField(help_text='CRD specification as JSON')),
                ('labels', models.JSONField(blank=True, default=dict, help_text='Kubernetes labels as JSON')),
                ('annotations', models.JSONField(blank=True, default=dict, help_text='Kubernetes annotations as JSON')),
                ('kubernetes_status', models.CharField(choices=[('unknown', 'Unknown'), ('pending', 'Pending'), ('applied', 'Applied'), ('live', 'Live'), ('error', 'Error'), ('deleting', 'Deleting')], default='unknown', help_text='Current status in Kubernetes', max_length=20)),
                ('kubernetes_uid', models.CharField(blank=True, help_text='Kubernetes resource UID', max_length=36)),
                ('kubernetes_resource_version', models.CharField(blank=True, help_text='Kubernetes resource version', max_length=50)),
                ('last_applied', models.DateTimeField(blank=True, help_text='When this CRD was last applied to Kubernetes', null=True)),
                ('last_synced', models.DateTimeField(blank=True, help_text='When this CRD was last synced from Kubernetes', null=True)),
                ('sync_error', models.TextField(blank=True, help_text='Last sync error message (if any)')),
                ('auto_sync', models.BooleanField(default=True, help_text='Enable automatic sync for this resource')),
                ('fabric', models.ForeignKey(help_text='Hedgehog fabric this CRD belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='switchgroup_set', to='netbox_hedgehog.hedgehogfabric')),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
            ],
            options={
                'verbose_name': 'Switch Group',
                'verbose_name_plural': 'Switch Groups',
                'ordering': ['fabric', 'namespace', 'name'],
                'unique_together': {('fabric', 'namespace', 'name')},
            },
        ),
    ]
