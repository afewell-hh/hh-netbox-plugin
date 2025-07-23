# Generated manually for remaining GitOps file management fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0018_add_gitops_file_management_fields'),
    ]

    operations = [
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