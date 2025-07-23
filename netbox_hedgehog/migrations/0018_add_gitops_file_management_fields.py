# Generated manually for GitOps file management system

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0017_performance_optimization_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='gitops_initialized',
            field=models.BooleanField(default=False, help_text='Whether GitOps file management structure has been initialized'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='archive_strategy',
            field=models.CharField(
                choices=[
                    ('rename_with_extension', 'Rename with .archived extension'),
                    ('move_to_archive_dir', 'Move to archive directory'),
                    ('backup_with_timestamp', 'Backup with timestamp'),
                    ('none', 'No archiving')
                ],
                default='rename_with_extension',
                help_text='Strategy for archiving original files during ingestion',
                max_length=30
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='raw_directory_path',
            field=models.CharField(
                blank=True,
                max_length=500,
                help_text='Full path to the raw/ directory where users drop files'
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='managed_directory_path',
            field=models.CharField(
                blank=True,
                max_length=500,
                help_text='Full path to the managed/ directory where HNP maintains normalized files'
            ),
        ),
    ]