# Generated for DIET-684's retained UI failure-audit contract.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0058_interchange_lifecycle_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='interchangeaudit',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
