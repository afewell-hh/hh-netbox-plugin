"""
Event Service Interface
Abstract interface for real-time event processing and distribution
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class EventPriority(Enum):
    """Event priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EventCategory(Enum):
    """Event categories for filtering and routing"""
    FABRIC_STATUS = "fabric_status"
    CRD_LIFECYCLE = "crd_lifecycle"
    GIT_SYNC = "git_sync"
    VALIDATION = "validation"
    SYSTEM = "system"
    USER_ACTION = "user_action"


@dataclass
class RealtimeEvent:
    """Real-time event data structure"""
    event_id: str
    event_type: str
    category: EventCategory
    priority: EventPriority
    timestamp: datetime
    fabric_id: Optional[int]
    user_id: Optional[int]
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'category': self.category.value,
            'priority': self.priority.value,
            'timestamp': self.timestamp.isoformat(),
            'fabric_id': self.fabric_id,
            'user_id': self.user_id,
            'data': self.data,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RealtimeEvent':
        """Create event from dictionary"""
        return cls(
            event_id=data['event_id'],
            event_type=data['event_type'],
            category=EventCategory(data['category']),
            priority=EventPriority(data['priority']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            fabric_id=data.get('fabric_id'),
            user_id=data.get('user_id'),
            data=data['data'],
            metadata=data['metadata']
        )


@dataclass
class EventSubscription:
    """Event subscription configuration"""
    subscriber_id: str
    event_types: List[str]
    categories: List[EventCategory]
    fabric_ids: Optional[List[int]]
    user_id: Optional[int]
    filter_func: Optional[Callable[[RealtimeEvent], bool]]
    callback: Callable[[RealtimeEvent], None]


@dataclass
class EventStats:
    """Event processing statistics"""
    total_events: int
    events_by_category: Dict[str, int]
    events_by_priority: Dict[str, int]
    processing_time_avg: float
    errors: int
    subscribers: int


class EventServiceInterface(ABC):
    """Abstract interface for real-time event service"""
    
    @abstractmethod
    async def publish_event(self, event: RealtimeEvent) -> bool:
        """
        Publish an event to all subscribers.
        
        Args:
            event: Event to publish
            
        Returns:
            True if event was published successfully
        """
        pass
    
    @abstractmethod
    async def publish_fabric_event(self, fabric_id: int, event_type: str, data: Dict[str, Any], 
                                  priority: EventPriority = EventPriority.NORMAL) -> bool:
        """
        Publish a fabric-specific event.
        
        Args:
            fabric_id: Fabric ID
            event_type: Type of event
            data: Event data
            priority: Event priority
            
        Returns:
            True if event was published
        """
        pass
    
    @abstractmethod
    async def publish_crd_event(self, fabric_id: int, crd_type: str, crd_name: str, 
                               event_type: str, data: Dict[str, Any]) -> bool:
        """
        Publish a CRD lifecycle event.
        
        Args:
            fabric_id: Fabric ID
            crd_type: CRD type/kind
            crd_name: CRD name
            event_type: Event type (created, updated, deleted)
            data: Event data
            
        Returns:
            True if event was published
        """
        pass
    
    @abstractmethod
    async def publish_sync_event(self, fabric_id: int, event_type: str, progress: int, 
                                message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Publish a Git sync progress event.
        
        Args:
            fabric_id: Fabric ID
            event_type: Event type (started, progress, completed, failed)
            progress: Progress percentage (0-100)
            message: Progress message
            data: Additional event data
            
        Returns:
            True if event was published
        """
        pass
    
    @abstractmethod
    def subscribe(self, subscription: EventSubscription) -> str:
        """
        Subscribe to events with filtering.
        
        Args:
            subscription: Subscription configuration
            
        Returns:
            Subscription ID
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscription_id: ID of subscription to remove
            
        Returns:
            True if unsubscribed successfully
        """
        pass
    
    @abstractmethod
    async def get_recent_events(self, fabric_id: Optional[int] = None, 
                               limit: int = 100, 
                               categories: Optional[List[EventCategory]] = None) -> List[RealtimeEvent]:
        """
        Get recent events with optional filtering.
        
        Args:
            fabric_id: Filter by fabric ID
            limit: Maximum number of events
            categories: Filter by event categories
            
        Returns:
            List of recent events
        """
        pass
    
    @abstractmethod
    async def get_event_stats(self, fabric_id: Optional[int] = None, 
                             since: Optional[datetime] = None) -> EventStats:
        """
        Get event processing statistics.
        
        Args:
            fabric_id: Filter by fabric ID
            since: Get stats since this timestamp
            
        Returns:
            Event statistics
        """
        pass
    
    @abstractmethod
    async def create_event_filter(self, fabric_id: int, 
                                 filter_config: Dict[str, Any]) -> str:
        """
        Create a reusable event filter.
        
        Args:
            fabric_id: Fabric ID
            filter_config: Filter configuration
            
        Returns:
            Filter ID
        """
        pass
    
    @abstractmethod
    async def broadcast_to_fabric_users(self, fabric_id: int, event: RealtimeEvent) -> int:
        """
        Broadcast event to all users with access to fabric.
        
        Args:
            fabric_id: Fabric ID
            event: Event to broadcast
            
        Returns:
            Number of users notified
        """
        pass


class WebSocketServiceInterface(ABC):
    """Abstract interface for WebSocket real-time communication"""
    
    @abstractmethod
    async def send_to_user(self, user_id: int, event: RealtimeEvent) -> bool:
        """
        Send event to specific user.
        
        Args:
            user_id: User ID
            event: Event to send
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    async def send_to_fabric_watchers(self, fabric_id: int, event: RealtimeEvent) -> int:
        """
        Send event to all users watching a fabric.
        
        Args:
            fabric_id: Fabric ID
            event: Event to send
            
        Returns:
            Number of connections notified
        """
        pass
    
    @abstractmethod
    async def broadcast_system_event(self, event: RealtimeEvent) -> int:
        """
        Broadcast system-wide event.
        
        Args:
            event: Event to broadcast
            
        Returns:
            Number of connections notified
        """
        pass
    
    @abstractmethod
    def get_active_connections(self, fabric_id: Optional[int] = None) -> int:
        """
        Get count of active WebSocket connections.
        
        Args:
            fabric_id: Filter by fabric ID
            
        Returns:
            Number of active connections
        """
        pass
    
    @abstractmethod
    async def validate_user_access(self, user_id: int, fabric_id: int) -> bool:
        """
        Validate user access to fabric events.
        
        Args:
            user_id: User ID
            fabric_id: Fabric ID
            
        Returns:
            True if user has access
        """
        pass