# NetBox plugin configuration for Hedgehog plugin

PLUGINS = [
    "netbox_hedgehog",
]

PLUGINS_CONFIG = {
    "netbox_hedgehog": {
        # Kubernetes configuration (optional - uses default kubeconfig if not specified)
        "kubernetes_config_file": None,
        
        # Sync settings
        "sync_interval": 300,  # seconds
        "enable_webhooks": True,
        "max_concurrent_syncs": 5,
        
        # Development settings
        "debug_mode": True,
    }
}