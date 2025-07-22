"""
Service Registry for Dependency Injection
Implements dependency injection container for clean architecture
"""

import logging
from typing import Dict, Type, TypeVar, Generic, Optional, Callable, Any

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ServiceRegistry:
    """
    Dependency injection container for services.
    
    Supports singleton and factory registration patterns.
    Enables clean architecture by allowing dependency injection.
    """
    
    def __init__(self):
        self._singletons: Dict[Type, object] = {}
        self._factories: Dict[Type, Callable] = {}
        self._instances: Dict[Type, object] = {}
    
    def register_singleton(self, interface: Type[T], implementation: T) -> None:
        """
        Register a singleton service implementation.
        
        Args:
            interface: The interface/abstract class
            implementation: The concrete implementation instance
        """
        self._singletons[interface] = implementation
        logger.debug(f"Registered singleton: {interface.__name__} -> {implementation.__class__.__name__}")
    
    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """
        Register a factory function for service creation.
        
        Args:
            interface: The interface/abstract class
            factory: Function that creates the implementation
        """
        self._factories[interface] = factory
        logger.debug(f"Registered factory: {interface.__name__}")
    
    def register_class(self, interface: Type[T], implementation_class: Type[T], singleton: bool = True) -> None:
        """
        Register a class to be instantiated on first access.
        
        Args:
            interface: The interface/abstract class
            implementation_class: The concrete implementation class
            singleton: Whether to use singleton pattern
        """
        if singleton:
            # Create factory that returns singleton instance
            def factory():
                if interface not in self._instances:
                    self._instances[interface] = implementation_class()
                return self._instances[interface]
            self.register_factory(interface, factory)
        else:
            # Create factory that returns new instance each time
            self.register_factory(interface, lambda: implementation_class())
        
        logger.debug(f"Registered class: {interface.__name__} -> {implementation_class.__name__} (singleton={singleton})")
    
    def get(self, interface: Type[T]) -> T:
        """
        Get service implementation for interface.
        
        Args:
            interface: The interface/abstract class to resolve
            
        Returns:
            The service implementation
            
        Raises:
            ValueError: If no implementation is registered
        """
        # Check singletons first
        if interface in self._singletons:
            return self._singletons[interface]
        
        # Check factories
        if interface in self._factories:
            return self._factories[interface]()
        
        # Try to get by exact class match
        for registered_interface, instance in self._singletons.items():
            if registered_interface == interface or isinstance(instance, interface):
                return instance
        
        raise ValueError(f"No implementation registered for {interface.__name__}")
    
    def has(self, interface: Type[T]) -> bool:
        """
        Check if an implementation is registered for the interface.
        
        Args:
            interface: The interface to check
            
        Returns:
            True if implementation exists, False otherwise
        """
        return (interface in self._singletons or 
                interface in self._factories or
                any(isinstance(instance, interface) for instance in self._singletons.values()))
    
    def clear(self) -> None:
        """Clear all registrations (mainly for testing)."""
        self._singletons.clear()
        self._factories.clear()
        self._instances.clear()
        logger.debug("Service registry cleared")
    
    def list_registrations(self) -> Dict[str, str]:
        """
        Get list of all registrations for debugging.
        
        Returns:
            Dictionary mapping interface names to implementation names
        """
        registrations = {}
        
        # Add singletons
        for interface, implementation in self._singletons.items():
            registrations[interface.__name__] = f"{implementation.__class__.__name__} (singleton)"
        
        # Add factories
        for interface in self._factories.keys():
            registrations[interface.__name__] = "Factory"
        
        return registrations


# Global registry instance
registry = ServiceRegistry()


# Decorator for automatic service registration
def service(interface: Optional[Type] = None, singleton: bool = True):
    """
    Decorator for automatic service registration.
    
    Args:
        interface: The interface this service implements (optional)
        singleton: Whether to use singleton pattern
    
    Usage:
        @service(MyServiceInterface)
        class MyService:
            pass
        
        @service()  # Registers class as itself
        class UtilityService:
            pass
    """
    def decorator(cls):
        service_interface = interface if interface is not None else cls
        registry.register_class(service_interface, cls, singleton=singleton)
        return cls
    return decorator


# Context manager for temporary service registration (testing)
class TemporaryServiceRegistration:
    """Context manager for temporary service registration during testing."""
    
    def __init__(self, interface: Type[T], implementation: T):
        self.interface = interface
        self.implementation = implementation
        self.original_impl = None
        self.had_registration = False
    
    def __enter__(self):
        # Store original if exists
        if registry.has(self.interface):
            self.had_registration = True
            self.original_impl = registry.get(self.interface)
        
        # Register temporary implementation
        registry.register_singleton(self.interface, self.implementation)
        return self.implementation
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Remove temporary registration
        if self.interface in registry._singletons:
            del registry._singletons[self.interface]
        
        # Restore original if it existed
        if self.had_registration and self.original_impl:
            registry.register_singleton(self.interface, self.original_impl)


# Helper functions for common patterns
def get_service(interface: Type[T]) -> T:
    """Convenience function to get service from global registry."""
    return registry.get(interface)


def register_service(interface: Type[T], implementation: T, singleton: bool = True) -> None:
    """Convenience function to register service in global registry."""
    if singleton:
        registry.register_singleton(interface, implementation)
    else:
        registry.register_class(interface, type(implementation), singleton=False)


# Bootstrap function to initialize core services
def bootstrap_services():
    """
    Bootstrap core services for the application.
    Called during app startup to register default services.
    """
    try:
        # Import and register core services
        from ..services.state_service import StateTransitionService
        from .services.git_sync_service import GitSyncService
        from .services.kubernetes_watch_service import KubernetesWatchService
        from .services.event_processor_service import EventProcessorService
        from .services.event_service import EventService, WebSocketService
        
        # Import domain interfaces for registration
        from ..domain.interfaces.kubernetes_watch_interface import (
            KubernetesWatchInterface, EventProcessorInterface
        )
        from ..domain.interfaces.event_service_interface import (
            EventServiceInterface, WebSocketServiceInterface
        )
        
        # Register existing state service
        registry.register_singleton(StateTransitionService, StateTransitionService())
        
        # Register Git sync service
        registry.register_class(GitSyncService, GitSyncService, singleton=True)
        
        # Register real-time monitoring services
        registry.register_class(KubernetesWatchInterface, KubernetesWatchService, singleton=True)
        registry.register_class(EventProcessorInterface, EventProcessorService, singleton=True)
        registry.register_class(EventServiceInterface, EventService, singleton=True)
        registry.register_class(WebSocketServiceInterface, WebSocketService, singleton=True)
        
        # Set up service dependencies
        _setup_service_dependencies()
        
        logger.info("Core services and real-time monitoring services bootstrapped successfully")
        logger.debug(f"Registered services: {registry.list_registrations()}")
        
    except Exception as e:
        logger.error(f"Failed to bootstrap services: {e}")
        raise


def _setup_service_dependencies():
    """Set up dependencies between services"""
    try:
        # Get service instances
        k8s_watch_service = registry.get(KubernetesWatchInterface)
        event_processor = registry.get(EventProcessorInterface)
        event_service = registry.get(EventServiceInterface)
        
        # Set up dependencies
        k8s_watch_service.set_event_processor(event_processor)
        k8s_watch_service.set_event_service(event_service)
        event_processor.set_event_service(event_service)
        
        logger.info("Service dependencies configured successfully")
        
    except Exception as e:
        logger.error(f"Failed to set up service dependencies: {e}")
        raise


# Initialize services on module import
try:
    bootstrap_services()
except Exception as e:
    logger.warning(f"Service bootstrap failed during import: {e}")