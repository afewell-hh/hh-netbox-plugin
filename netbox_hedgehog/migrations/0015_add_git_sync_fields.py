# Generated manually for Git sync fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0014_implement_git_repository_separation'),
    ]

    operations = [
        # Add raw_spec field to all CRD models
        migrations.AddField(
            model_name='vpc',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='external',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='externalattachment',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='externalpeering',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='ipv4namespace',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='vpcattachment',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='vpcpeering',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='connection',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='server',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='switch',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='switchgroup',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        migrations.AddField(
            model_name='vlannamespace',
            name='raw_spec',
            field=models.JSONField(blank=True, default=dict, help_text='Raw spec from YAML file (preserves structure)'),
        ),
        
        # Add git_file_path field to all CRD models
        migrations.AddField(
            model_name='vpc',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='external',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='externalattachment',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='externalpeering',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='ipv4namespace',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='vpcattachment',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='vpcpeering',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='connection',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='server',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='switch',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='switchgroup',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
        migrations.AddField(
            model_name='vlannamespace',
            name='git_file_path',
            field=models.CharField(blank=True, help_text='Path to this resource in Git repository', max_length=500),
        ),
    ]