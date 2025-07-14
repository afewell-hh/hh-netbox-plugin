# Generated to add GenericForeignKey support to HedgehogResource for linking to actual CRD objects

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('netbox_hedgehog', '0011_add_reconciliation_alert'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogresource',
            name='content_type',
            field=models.ForeignKey(blank=True, help_text='Content type of the linked CRD object', null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype'),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='object_id',
            field=models.PositiveIntegerField(blank=True, help_text='ID of the linked CRD object', null=True),
        ),
    ]