"""
Migration 0030: NIC Modeling Clean Break (DIET-173 Phase 5).

This migration implements a clean-break schema update for NIC modeling:
1. Validates no legacy data exists (fails if nic_module_type=None)
2. Adds port_index field (IntegerField, default=0)
3. Makes nic_module_type required (null=False, blank=False)
4. Removes nic_slot field
5. Removes server_interface_template field

This is a BREAKING CHANGE. Users must ensure all PlanServerConnection
objects have nic_module_type set before running this migration.

To prepare for this migration, run:
  python manage.py reset_diet_data --all --no-input

Or update existing connections manually to set nic_module_type.
"""

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


def validate_no_legacy_data(apps, schema_editor):
    """
    Validate no legacy data exists before clean break.

    Fails with clear error message if any PlanServerConnection
    has nic_module_type=None (legacy data).
    """
    PlanServerConnection = apps.get_model('netbox_hedgehog', 'PlanServerConnection')

    legacy_count = PlanServerConnection.objects.filter(nic_module_type__isnull=True).count()

    if legacy_count > 0:
        raise ValueError(
            f"\n\n"
            f"===== MIGRATION BLOCKED: Legacy Data Detected =====\n"
            f"Found {legacy_count} PlanServerConnection(s) with nic_module_type=None.\n"
            f"\n"
            f"This migration requires all connections to have nic_module_type set.\n"
            f"\n"
            f"To fix this, run ONE of the following:\n"
            f"\n"
            f"  Option 1 - Reset all DIET data (recommended):\n"
            f"    python manage.py reset_diet_data --all --no-input\n"
            f"\n"
            f"  Option 2 - Update connections manually in the UI/API\n"
            f"\n"
            f"After fixing, re-run migrations.\n"
            f"==================================================\n"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '__latest__'),
        ('netbox_hedgehog', '0029_seed_nic_module_types'),
    ]

    operations = [
        # Step 1: Validate no legacy data exists
        migrations.RunPython(
            validate_no_legacy_data,
            reverse_code=migrations.RunPython.noop
        ),

        # Step 2: Add port_index field (nullable first, for existing rows)
        migrations.AddField(
            model_name='planserverconnection',
            name='port_index',
            field=models.IntegerField(
                default=0,
                validators=[django.core.validators.MinValueValidator(0)],
                help_text='Zero-based port index on the NIC (e.g., 0 for first port, 1 for second port)'
            ),
        ),

        # Step 3: Make nic_module_type required (remove null=True, blank=True)
        migrations.AlterField(
            model_name='planserverconnection',
            name='nic_module_type',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='plan_server_connections',
                to='dcim.moduletype',
                help_text='NIC module type (e.g., BlueField-3 BF3220, ConnectX-7)'
            ),
        ),

        # Step 4: Remove nic_slot field (legacy)
        migrations.RemoveField(
            model_name='planserverconnection',
            name='nic_slot',
        ),

        # Step 5: Remove server_interface_template field (legacy)
        migrations.RemoveField(
            model_name='planserverconnection',
            name='server_interface_template',
        ),
    ]
