try:
    from netbox.plugins import PluginConfig
except ModuleNotFoundError:
    # Django/NetBox not available - this is OK for browser UX tests
    # Browser tests run on HOST machine and connect via HTTP
    # They don't need Django imports, just the test code
    PluginConfig = object  # Dummy base class


class HedgehogPluginConfig(PluginConfig):
    name = 'netbox_hedgehog'
    verbose_name = 'Hedgehog Fabric Manager'
    description = 'Manage Hedgehog fabric CRDs with self-service catalog'
    version = '0.1.0'
    author = 'Hedgehog'
    author_email = 'support@hedgehog.cloud'
    base_url = 'hedgehog'
    required_settings = []
    default_settings = {
        'kubernetes_config_file': None,
        'sync_interval': 300,
        'enable_webhooks': True,
        'max_concurrent_syncs': 5,
    }
    caching_config = {
        'fabric_status': 60,  # Cache fabric status for 60 seconds
        'crd_schemas': 3600,  # Cache CRD schemas for 1 hour
    }

config = HedgehogPluginConfig