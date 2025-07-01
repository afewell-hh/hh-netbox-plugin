# Generated migration for adding connection_error field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0003_add_status_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='connection_error',
            field=models.TextField(
                blank=True,
                help_text='Last connection error message (if any)'
            ),
        ),
    ]