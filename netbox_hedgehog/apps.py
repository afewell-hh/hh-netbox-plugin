"""
Django App Configuration for Hedgehog NetBox Plugin
Configures the plugin and loads GitOps integration signals.
"""

from django.apps import AppConfig


class NetboxHedgehogConfig(AppConfig):
    """Django app configuration for the Hedgehog NetBox Plugin"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'netbox_hedgehog'
    label = 'netbox_hedgehog'
    verbose_name = 'Hedgehog NetBox Plugin'
    
    def ready(self):
        """
        Called when the app is ready.
        Minimal initialization to prevent circular imports.
        """
        try:
            # Log that plugin is loading
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Hedgehog NetBox Plugin: Loading with minimal initialization")
            
        except Exception as e:
            # Log error but don't prevent app from starting
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Hedgehog NetBox Plugin: Initialization warning: {e}")
            
        # Load any additional plugin initialization
        self._initialize_plugin()
    
    def _initialize_plugin(self):
        """Initialize plugin-specific functionality"""
        try:
            # Import signals to connect them to Django's signal system
            from . import signals
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Hedgehog NetBox Plugin: Signals connected and initialization complete")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Hedgehog NetBox Plugin: Initialization failed: {e}")