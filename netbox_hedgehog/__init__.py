from netbox.plugins import PluginConfig

class HedgehogPluginConfig(PluginConfig):
    name = 'netbox_hedgehog'
    verbose_name = 'Hedgehog Fabric Manager'
    description = 'Manage Hedgehog fabric CRDs with GitOps integration'
    version = '0.2.0'  # Updated for MVP2 GitOps features
    author = 'Hedgehog'
    author_email = 'support@hedgehog.cloud'
    base_url = 'hedgehog'
    required_settings = []
    default_settings = {
        'kubernetes_config_file': None,
        'sync_interval': 300,
        'enable_webhooks': True,
        'max_concurrent_syncs': 5,
        # GitOps settings
        'enable_gitops': True,
        'gitops_auto_sync': True,
        'git_poll_interval': 60,
        'drift_detection_interval': 300,
    }
    caching_config = {
        'fabric_status': 60,  # Cache fabric status for 60 seconds
        'crd_schemas': 3600,  # Cache CRD schemas for 1 hour
        'git_status': 30,  # Cache Git status for 30 seconds
        'drift_analysis': 120,  # Cache drift analysis for 2 minutes
    }

config = HedgehogPluginConfig

# Configure Django app
default_app_config = 'netbox_hedgehog.apps.NetboxHedgehogConfig'