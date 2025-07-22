"""
Kubernetes Watch Service Interface
Abstract interface for Kubernetes CRD monitoring and real-time updates
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncIterator, Callable
from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    """Kubernetes watch event types"""
    ADDED = "ADDED"
    MODIFIED = "MODIFIED" 
    DELETED = "DELETED"
    ERROR = "ERROR"
    BOOKMARK = "BOOKMARK"


@dataclass
class CRDEvent:
    """Kubernetes CRD event data"""
    event_type: EventType
    crd_data: Dict[str, Any]
    fabric_id: int
    timestamp: str
    resource_version: str
    namespace: str
    name: str
    kind: str
    
    @property
    def identifier(self) -> str:
        """Unique identifier for this CRD"""
        return f"{self.kind}/{self.namespace}/{self.name}"


@dataclass
class WatchStatus:
    """Watch stream status"""
    is_active: bool
    fabric_id: int
    start_time: str
    last_event_time: Optional[str]
    event_count: int
    errors: List[str]
    resource_version: str


@dataclass
class FabricConnectionInfo:
    """Fabric Kubernetes connection information"""
    fabric_id: int
    cluster_endpoint: str
    token: Optional[str]
    ca_cert: Optional[str]
    namespace: str
    enabled_crds: List[str]
    
    @property
    def is_valid(self) -> bool:
        """Check if connection info is valid"""
        return bool(self.cluster_endpoint and (self.token or self.ca_cert))


class KubernetesWatchInterface(ABC):
    """Abstract interface for Kubernetes CRD monitoring"""
    
    @abstractmethod
    async def start_fabric_watch(self, fabric_connection: FabricConnectionInfo) -> bool:
        """
        Start watching CRDs for a specific fabric.
        
        Args:
            fabric_connection: Fabric connection configuration
            
        Returns:
            True if watch started successfully
            
        Raises:
            KubernetesError: If connection fails
        """
        pass
    
    @abstractmethod
    async def stop_fabric_watch(self, fabric_id: int) -> bool:
        """
        Stop watching CRDs for a specific fabric.
        
        Args:
            fabric_id: Fabric ID to stop watching
            
        Returns:
            True if watch stopped successfully
        """
        pass
    
    @abstractmethod
    async def get_watch_status(self, fabric_id: int) -> Optional[WatchStatus]:
        """
        Get current watch status for a fabric.
        
        Args:
            fabric_id: Fabric ID to check
            
        Returns:
            WatchStatus if fabric is being watched, None otherwise
        """
        pass
    
    @abstractmethod
    async def list_fabric_crds(self, fabric_connection: FabricConnectionInfo) -> List[Dict[str, Any]]:
        """
        List current CRDs in fabric cluster.
        
        Args:
            fabric_connection: Fabric connection configuration
            
        Returns:
            List of CRD dictionaries
            
        Raises:
            KubernetesError: If listing fails
        """
        pass
    
    @abstractmethod
    async def watch_crd_stream(self, fabric_connection: FabricConnectionInfo) -> AsyncIterator[CRDEvent]:
        """
        Stream CRD events for a fabric.
        
        Args:
            fabric_connection: Fabric connection configuration
            
        Yields:
            CRDEvent for each Kubernetes event
            
        Raises:
            KubernetesError: If watch stream fails
        """
        pass
    
    @abstractmethod
    def register_event_handler(self, event_type: EventType, handler: Callable[[CRDEvent], None]) -> None:
        """
        Register handler for specific event types.
        
        Args:
            event_type: Type of event to handle
            handler: Callback function for events
        """
        pass
    
    @abstractmethod
    async def validate_fabric_connection(self, fabric_connection: FabricConnectionInfo) -> Dict[str, Any]:
        """
        Validate fabric Kubernetes connection.
        
        Args:
            fabric_connection: Connection to validate
            
        Returns:
            Validation result with status and details
        """
        pass
    
    @abstractmethod
    async def get_cluster_info(self, fabric_connection: FabricConnectionInfo) -> Dict[str, Any]:
        """
        Get cluster information and health status.
        
        Args:
            fabric_connection: Fabric connection configuration
            
        Returns:
            Cluster information dictionary
            
        Raises:
            KubernetesError: If cluster info retrieval fails
        """
        pass


class EventProcessorInterface(ABC):
    """Abstract interface for processing CRD events"""
    
    @abstractmethod
    async def process_crd_event(self, event: CRDEvent) -> bool:
        """
        Process a single CRD event.
        
        Args:
            event: CRD event to process
            
        Returns:
            True if processed successfully
        """
        pass
    
    @abstractmethod
    async def batch_process_events(self, events: List[CRDEvent]) -> Dict[str, int]:
        """
        Process multiple events in batch.
        
        Args:
            events: List of CRD events
            
        Returns:
            Processing statistics
        """
        pass
    
    @abstractmethod
    def register_event_filter(self, fabric_id: int, filter_func: Callable[[CRDEvent], bool]) -> None:
        """
        Register event filter for a fabric.
        
        Args:
            fabric_id: Fabric ID
            filter_func: Function to filter events
        """
        pass
    
    @abstractmethod
    async def get_processing_stats(self, fabric_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get event processing statistics.
        
        Args:
            fabric_id: Specific fabric ID or None for all
            
        Returns:
            Processing statistics
        """
        pass


# Custom exceptions
class KubernetesError(Exception):
    """Base exception for Kubernetes operations"""
    pass


class WatchConnectionError(KubernetesError):
    """Exception for watch connection failures"""
    pass


class EventProcessingError(KubernetesError):
    """Exception for event processing failures"""
    pass