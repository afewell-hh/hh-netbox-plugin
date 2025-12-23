# Generated manually to convert GenerationState from NetBoxModel to regular Model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0018_generation_state'),
    ]

    operations = [
        # Remove NetBoxModel fields from GenerationState
        migrations.RemoveField(
            model_name='generationstate',
            name='created',
        ),
        migrations.RemoveField(
            model_name='generationstate',
            name='last_updated',
        ),
        migrations.RemoveField(
            model_name='generationstate',
            name='custom_field_data',
        ),
        migrations.RemoveField(
            model_name='generationstate',
            name='tags',
        ),
    ]
