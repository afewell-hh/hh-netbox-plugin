# Generated migration for scheduler_enabled field
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0022_fix_not_null_constraint_violations'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='scheduler_enabled',
            field=models.BooleanField(default=True, help_text='Enable fabric for enhanced periodic sync scheduling'),
        ),
    ]
