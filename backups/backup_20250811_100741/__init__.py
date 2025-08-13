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
    
    # RQ queue configuration for periodic sync jobs
    queues = [
        'hedgehog_sync'  # Dedicated queue for fabric sync operations
    ]
    
    def ready(self):
        """
        Called when the plugin is ready.
        Import signals to register them with Django.
        """
        try:
            # Import signals to connect them to Django's signal system
            from . import signals
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Hedgehog NetBox Plugin: Signals connected and ready")
            
            # Bootstrap RQ-based periodic sync schedules
            self._bootstrap_sync_schedules(logger)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Hedgehog NetBox Plugin: Signal initialization failed: {e}")
        
        # Call parent ready method
        super().ready()

    def _bootstrap_sync_schedules(self, logger):
        """
        Bootstrap RQ-based periodic sync schedules for all fabrics.
        
        Args:
            logger: Logger instance for status reporting
        """
        try:
            # Import here to avoid circular dependencies during Django startup
            from .jobs.fabric_sync import FabricSyncScheduler
            
            logger.info("Hedgehog NetBox Plugin: Bootstrapping fabric sync schedules...")
            
            # Bootstrap all fabric sync schedules
            result = FabricSyncScheduler.bootstrap_all_fabric_schedules()
            
            if result['success']:
                logger.info(f"Hedgehog NetBox Plugin: Successfully bootstrapped sync schedules for "
                          f"{result['fabrics_scheduled']} fabrics")
                if result['errors'] > 0:
                    logger.warning(f"Hedgehog NetBox Plugin: {result['errors']} fabrics had scheduling errors")
            else:
                logger.error(f"Hedgehog NetBox Plugin: Failed to bootstrap sync schedules: {result.get('error', 'Unknown error')}")
                
        except ImportError as e:
            # RQ scheduler not available - this is expected in some environments
            logger.info(f"Hedgehog NetBox Plugin: RQ scheduler not available, skipping sync bootstrap: {e}")
        except Exception as e:
            logger.error(f"Hedgehog NetBox Plugin: Failed to bootstrap sync schedules: {e}")

config = HedgehogPluginConfig

# Configure Django app
default_app_config = 'netbox_hedgehog.apps.NetboxHedgehogConfig'