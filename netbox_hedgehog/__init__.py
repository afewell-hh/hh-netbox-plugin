try:
    from netbox.plugins import PluginConfig
except ModuleNotFoundError:
    # Django/NetBox not available - this is OK for browser UX tests
    # Browser tests run on HOST machine and connect via HTTP
    # They don't need Django imports, just the test code
    PluginConfig = object  # Dummy base class


def _seed_reference_data(sender, **kwargs):
    """
    Ensure repo-owned reference data exists after migrate.

    Runs the full load_diet_reference_data path, including the bundled
    Hedgehog switch-profile import.  That import reads only local files
    (netbox_hedgehog/fabric_profiles/) so it is deterministic, has no
    external network dependency, and is safe to run on every migrate.
    """
    from django.core.management import call_command

    call_command("load_diet_reference_data", verbosity=0)


class HedgehogPluginConfig(PluginConfig):
    name = 'netbox_hedgehog'
    verbose_name = 'Hedgehog Fabric Manager'
    description = 'Manage Hedgehog fabric CRDs with self-service catalog'
    version = '0.2.0'
    author = 'Hedgehog'
    author_email = 'support@hedgehog.cloud'
    base_url = 'hedgehog'
    required_settings = []
    default_settings = {
        'kubernetes_config_file': None,
        'sync_interval': 300,
        'enable_webhooks': True,
        'max_concurrent_syncs': 5,
        'interchange_import_limits': {
            'max_encoded_body_bytes': 10 * 1024 * 1024,
            'max_objects': 5000,
            'max_nesting_depth': 32,
            'max_operation_seconds': 30,
        },
    }
    caching_config = {
        'fabric_status': 60,  # Cache fabric status for 60 seconds
        'crd_schemas': 3600,  # Cache CRD schemas for 1 hour
    }

    def ready(self):
        # The paste-only interchange contract has a 10 MiB application limit.
        # Django otherwise rejects at its 2.5 MiB default before this plugin's
        # bounded reader can apply that configured limit.
        from django.conf import settings
        from django.db.models.signals import post_migrate

        settings.DATA_UPLOAD_MAX_MEMORY_SIZE = max(
            settings.DATA_UPLOAD_MAX_MEMORY_SIZE,
            self.default_settings['interchange_import_limits']['max_encoded_body_bytes'],
        )

        super_ready = getattr(super(), "ready", None)
        if callable(super_ready):
            super_ready()

        post_migrate.connect(
            _seed_reference_data,
            sender=self,
            dispatch_uid="netbox_hedgehog.seed_reference_data",
        )

config = HedgehogPluginConfig
