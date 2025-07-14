# Generated migration for ReconciliationAlert model

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ('netbox_hedgehog', '0010_implement_six_state_management'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReconciliationAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('tags', models.ManyToManyField(blank=True, to='extras.tag')),
                ('alert_type', models.CharField(
                    choices=[
                        ('drift_detected', 'Drift Detected'),
                        ('orphaned_resource', 'Orphaned Resource'),
                        ('creation_pending', 'Creation Pending'),
                        ('deletion_pending', 'Deletion Pending'),
                        ('sync_failure', 'Sync Failure'),
                        ('validation_error', 'Validation Error'),
                        ('conflict_detected', 'Conflict Detected'),
                    ],
                    help_text='Type of reconciliation alert',
                    max_length=50
                )),
                ('severity', models.CharField(
                    choices=[
                        ('low', 'Low'),
                        ('medium', 'Medium'),
                        ('high', 'High'),
                        ('critical', 'Critical'),
                    ],
                    default='medium',
                    help_text='Alert severity level',
                    max_length=20
                )),
                ('status', models.CharField(
                    choices=[
                        ('active', 'Active'),
                        ('acknowledged', 'Acknowledged'),
                        ('resolved', 'Resolved'),
                        ('suppressed', 'Suppressed'),
                    ],
                    default='active',
                    help_text='Current alert status',
                    max_length=20
                )),
                ('title', models.CharField(help_text='Alert title', max_length=200)),
                ('message', models.TextField(help_text='Detailed alert message')),
                ('alert_context', models.JSONField(blank=True, default=dict, help_text='Additional context for the alert')),
                ('drift_details', models.JSONField(blank=True, default=dict, help_text='Drift analysis details')),
                ('suggested_action', models.CharField(
                    choices=[
                        ('import_to_git', 'Import to Git'),
                        ('delete_from_cluster', 'Delete from Cluster'),
                        ('update_git', 'Update Git'),
                        ('ignore', 'Ignore'),
                        ('manual_review', 'Manual Review'),
                    ],
                    default='manual_review',
                    help_text='Suggested resolution action',
                    max_length=30
                )),
                ('resolved_action', models.CharField(
                    blank=True,
                    choices=[
                        ('import_to_git', 'Import to Git'),
                        ('delete_from_cluster', 'Delete from Cluster'),
                        ('update_git', 'Update Git'),
                        ('ignore', 'Ignore'),
                        ('manual_review', 'Manual Review'),
                    ],
                    help_text='Action taken to resolve the alert',
                    max_length=30
                )),
                ('resolution_metadata', models.JSONField(blank=True, default=dict, help_text='Metadata about the resolution')),
                ('acknowledged_at', models.DateTimeField(blank=True, help_text='When alert was acknowledged', null=True)),
                ('resolved_at', models.DateTimeField(blank=True, help_text='When alert was resolved', null=True)),
                ('expires_at', models.DateTimeField(blank=True, help_text='When alert expires if not resolved', null=True)),
                ('queue_priority', models.PositiveIntegerField(default=100, help_text='Queue priority (lower numbers = higher priority)')),
                ('processing_attempts', models.PositiveIntegerField(default=0, help_text='Number of processing attempts')),
                ('last_processing_attempt', models.DateTimeField(blank=True, help_text='Last processing attempt timestamp', null=True)),
                ('processing_error', models.TextField(blank=True, help_text='Last processing error message')),
                ('batch_id', models.CharField(blank=True, help_text='Batch ID for grouped processing', max_length=100)),
                ('acknowledged_by', models.ForeignKey(
                    blank=True,
                    help_text='User who acknowledged this alert',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='acknowledged_alerts',
                    to=settings.AUTH_USER_MODEL
                )),
                ('created_by', models.ForeignKey(
                    blank=True,
                    help_text='User who created this alert',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_alerts',
                    to=settings.AUTH_USER_MODEL
                )),
                ('fabric', models.ForeignKey(
                    help_text='Hedgehog fabric this alert belongs to',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reconciliation_alerts',
                    to='netbox_hedgehog.hedgehogfabric'
                )),
                ('related_alerts', models.ManyToManyField(
                    blank=True,
                    help_text='Related alerts for batch processing',
                    related_name='_netbox_hedgehog_reconciliationalert_related_alerts_+',
                    to='netbox_hedgehog.reconciliationalert'
                )),
                ('resolved_by', models.ForeignKey(
                    blank=True,
                    help_text='User who resolved this alert',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='resolved_alerts',
                    to=settings.AUTH_USER_MODEL
                )),
                ('resource', models.ForeignKey(
                    help_text='Resource this alert is for',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reconciliation_alerts',
                    to='netbox_hedgehog.hedgehogresource'
                )),
            ],
            options={
                'verbose_name': 'Reconciliation Alert',
                'verbose_name_plural': 'Reconciliation Alerts',
                'ordering': ['-created', 'queue_priority'],
            },
        ),
        migrations.AddIndex(
            model_name='reconciliationalert',
            index=models.Index(fields=['fabric', 'status'], name='netbox_hedg_fabric_36e6f5_idx'),
        ),
        migrations.AddIndex(
            model_name='reconciliationalert',
            index=models.Index(fields=['resource', 'status'], name='netbox_hedg_resourc_72b9e0_idx'),
        ),
        migrations.AddIndex(
            model_name='reconciliationalert',
            index=models.Index(fields=['status', 'queue_priority'], name='netbox_hedg_status_f1c9ba_idx'),
        ),
        migrations.AddIndex(
            model_name='reconciliationalert',
            index=models.Index(fields=['alert_type', 'severity'], name='netbox_hedg_alert_t_f2e8d4_idx'),
        ),
        migrations.AddIndex(
            model_name='reconciliationalert',
            index=models.Index(fields=['created', 'status'], name='netbox_hedg_created_0e4b67_idx'),
        ),
        migrations.AddIndex(
            model_name='reconciliationalert',
            index=models.Index(fields=['expires_at'], name='netbox_hedg_expires_9b3a2c_idx'),
        ),
        migrations.AddIndex(
            model_name='reconciliationalert',
            index=models.Index(fields=['batch_id'], name='netbox_hedg_batch_i_8f5e1d_idx'),
        ),
        migrations.AddIndex(
            model_name='reconciliationalert',
            index=models.Index(fields=['fabric', 'alert_type', 'status'], name='netbox_hedg_fabric_87c4d9_idx'),
        ),
    ]