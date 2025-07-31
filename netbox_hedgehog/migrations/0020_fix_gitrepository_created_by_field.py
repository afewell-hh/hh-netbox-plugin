# Generated migration to fix GitRepository created_by field
# Addresses authentication issues by making created_by properly nullable

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0019_add_remaining_gitops_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Step 1: Remove the unique constraint that includes created_by
        migrations.RemoveConstraint(
            model_name='gitrepository',
            name='unique_git_repository_per_user',
        ),
        
        # Step 2: Update the created_by field to be properly nullable
        migrations.AlterField(
            model_name='gitrepository',
            name='created_by',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                to=settings.AUTH_USER_MODEL,
                help_text='User who added this repository'
            ),
        ),
        
        # Step 3: Add a new constraint without created_by dependency
        # Allow multiple users to add the same repository URL
        migrations.AddConstraint(
            model_name='gitrepository',
            constraint=models.UniqueConstraint(
                fields=['url', 'name'],
                name='unique_git_repository_url_name'
            ),
        ),
    ]