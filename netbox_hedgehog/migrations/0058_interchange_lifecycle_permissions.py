from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('netbox_hedgehog', '0057_interchange_core')]
    operations = [migrations.AlterModelOptions(
        name='interchangedesignrevision',
        options={'permissions': (('approve_interchangedesignrevision', 'Can approve interchange design revision'),)},
    ), migrations.AlterModelOptions(
        name='interchangecatalogversion',
        options={'permissions': (
            ('publish_interchangecatalogversion', 'Can publish interchange catalog version'),
            ('deprecate_interchangecatalogversion', 'Can deprecate interchange catalog version'),
            ('withdraw_interchangecatalogversion', 'Can withdraw interchange catalog version'),
        )},
    )]
