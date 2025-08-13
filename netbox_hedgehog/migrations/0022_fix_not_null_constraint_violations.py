# Generated manually to fix NOT NULL constraint violations
# Issue: HedgehogResource creation fails due to missing required fields added in migration 0021

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Fix NOT NULL constraint violations in HedgehogResource model.
    
    Migration 0021 added several fields as NOT NULL without defaults, causing
    constraint violations when existing code tries to create HedgehogResource records.
    
    This migration adds appropriate default values to prevent these violations.
    """

    dependencies = [
        ('netbox_hedgehog', '0021_bidirectional_sync_extensions'),
    ]

    operations = [
        # Add default values for critical fields that cause constraint violations
        migrations.RunSQL([
            # Critical fields added in migration 0021 that cause immediate failures
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN managed_file_path SET DEFAULT '';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN file_hash SET DEFAULT '';", 
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN sync_direction SET DEFAULT 'bidirectional';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN conflict_status SET DEFAULT 'none';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN conflict_details SET DEFAULT '{}';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN sync_metadata SET DEFAULT '{}';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN external_modifications SET DEFAULT '[]';",
            
            # Other fields that commonly cause issues during resource creation
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN actual_resource_version SET DEFAULT '';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN desired_commit SET DEFAULT '';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN desired_file_path SET DEFAULT '';", 
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN last_sync_error SET DEFAULT '';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN last_synced_commit SET DEFAULT '';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN state_change_reason SET DEFAULT '';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN drift_severity SET DEFAULT '';",
            
            # Numeric fields
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN dependency_score SET DEFAULT 0.0;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN drift_score SET DEFAULT 0.0;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN reconciliation_attempts SET DEFAULT 0;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN sync_attempts SET DEFAULT 0;",
            
            # JSON fields  
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN annotations SET DEFAULT '{}';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN custom_field_data SET DEFAULT '{}';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN drift_details SET DEFAULT '{}';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN labels SET DEFAULT '{}';",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN relationship_metadata SET DEFAULT '{}';",
            
            # Update any existing NULL values (in case any exist)
            # Note: This shouldn't be needed since fields are NOT NULL, but added for safety
            """
            UPDATE netbox_hedgehog_hedgehogresource SET 
                managed_file_path = '' WHERE managed_file_path IS NULL OR managed_file_path = '';
            """,
            """
            UPDATE netbox_hedgehog_hedgehogresource SET 
                file_hash = '' WHERE file_hash IS NULL OR file_hash = '';
            """,
            """
            UPDATE netbox_hedgehog_hedgehogresource SET 
                sync_direction = 'bidirectional' WHERE sync_direction IS NULL OR sync_direction = '';
            """,
            """
            UPDATE netbox_hedgehog_hedgehogresource SET 
                conflict_status = 'none' WHERE conflict_status IS NULL OR conflict_status = '';
            """,
        ], reverse_sql=[
            # Reverse SQL to remove defaults if migration needs to be rolled back
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN managed_file_path DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN file_hash DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN sync_direction DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN conflict_status DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN conflict_details DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN sync_metadata DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN external_modifications DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN actual_resource_version DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN desired_commit DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN desired_file_path DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehog_resource ALTER COLUMN last_sync_error DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN last_synced_commit DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN state_change_reason DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN drift_severity DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN dependency_score DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN drift_score DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN reconciliation_attempts DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN sync_attempts DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN annotations DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN custom_field_data DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN drift_details DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN labels DROP DEFAULT;",
            "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN relationship_metadata DROP DEFAULT;",
        ]),
        
        # Add comment to document the fix
        migrations.RunSQL([
            """
            COMMENT ON TABLE netbox_hedgehog_hedgehogresource IS 
            'HedgehogResource model with GitOps dual-state tracking. Migration 0022 added default values to prevent NOT NULL constraint violations during resource creation.';
            """
        ], reverse_sql=[
            "COMMENT ON TABLE netbox_hedgehog_hedgehogresource IS NULL;"
        ]),
    ]