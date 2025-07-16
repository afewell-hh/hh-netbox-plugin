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
        Import and register signal handlers for GitOps integration.
        """
        try:
            # Import serializers MULTIPLE TIMES to ensure monkey patches stick
            from .api import serializers
            
            # Force a second import to ensure patches are definitely applied
            import importlib
            importlib.reload(serializers)
            
            # Import signals to register them
            from . import signals
            
            # Log that GitOps integration is active
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Hedgehog NetBox Plugin: GitOps integration signals loaded")
            logger.info("Hedgehog NetBox Plugin: Hyperlinked field monkey patches applied and reloaded")
            
        except Exception as e:
            # Log error but don't prevent app from starting
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Hedgehog NetBox Plugin: Failed to load GitOps signals: {e}")
            
        # Load any additional plugin initialization
        self._initialize_plugin()
    
    def _initialize_plugin(self):
        """Initialize plugin-specific functionality"""
        try:
            # Perform any additional plugin initialization here
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Hedgehog NetBox Plugin: Initialization complete")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Hedgehog NetBox Plugin: Initialization failed: {e}")