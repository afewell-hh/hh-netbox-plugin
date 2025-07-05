from netbox.plugins import PluginConfig

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
    
    # Register API URL patterns
    @property
    def api_urlpatterns(self):
        from .api import urls as api_urls
        return api_urls.urlpatterns

config = HedgehogPluginConfig