"""
Event Processor Service
Processes Kubernetes CRD events and updates database models
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone

from django.db import transaction
from django.apps import apps

from ...domain.interfaces.kubernetes_watch_interface import (
    EventProcessorInterface, CRDEvent, EventType
)
from ...domain.interfaces.event_service_interface import (
    EventServiceInterface, EventCategory, EventPriority
)
from ..service_registry import get_service

logger = logging.getLogger(__name__)


class EventProcessorService(EventProcessorInterface):
    """
    Service for processing Kubernetes CRD events and updating database models.
    Implements business logic for handling CRD lifecycle events.
    """
    
    # Mapping of Kubernetes kinds to NetBox model names
    KIND_TO_MODEL = {
        'VPC': 'VPC',
        'External': 'External',
        'ExternalAttachment': 'ExternalAttachment',
        'ExternalPeering': 'ExternalPeering',
        'IPv4Namespace': 'IPv4Namespace',
        'VPCAttachment': 'VPCAttachment',
        'VPCPeering': 'VPCPeering',
        'Connection': 'Connection',
        'Server': 'Server',
        'Switch': 'Switch',
        'SwitchGroup': 'SwitchGroup',
        'VLANNamespace': 'VLANNamespace',
    }
    
    def __init__(self):
        self._event_filters: Dict[int, List[Callable[[CRDEvent], bool]]] = {}
        self._processing_stats = {
            'total_processed': 0,
            'by_event_type': {event_type.value: 0 for event_type in EventType},
            'by_kind': {kind: 0 for kind in self.KIND_TO_MODEL.keys()},
            'errors': 0,
            'last_processed': None
        }
        self._event_service: Optional[EventServiceInterface] = None
    
    def set_event_service(self, event_service: EventServiceInterface):
        """Set the event service for publishing notifications"""
        self._event_service = event_service
    
    async def process_crd_event(self, event: CRDEvent) -> bool:
        """Process a single CRD event"""
        try:
            logger.debug(f"Processing {event.event_type.value} event for {event.identifier}")
            
            # Apply event filters
            if not self._should_process_event(event):
                logger.debug(f"Event filtered out: {event.identifier}")
                return True
            
            # Process based on event type
            success = False
            if event.event_type == EventType.ADDED:
                success = await self._handle_crd_created(event)
            elif event.event_type == EventType.MODIFIED:
                success = await self._handle_crd_updated(event)
            elif event.event_type == EventType.DELETED:
                success = await self._handle_crd_deleted(event)
            elif event.event_type == EventType.ERROR:
                success = await self._handle_crd_error(event)
            else:
                logger.debug(f"Ignoring event type: {event.event_type.value}")
                return True
            
            # Update statistics
            self._update_processing_stats(event, success)
            
            # Publish processing result
            if self._event_service and success:
                await self._publish_processing_event(event, success)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to process CRD event {event.identifier}: {e}")
            self._processing_stats['errors'] += 1
            return False
    
    async def batch_process_events(self, events: List[CRDEvent]) -> Dict[str, int]:
        """Process multiple events in batch"""
        results = {
            'processed': 0,
            'errors': 0,
            'filtered': 0,
            'created': 0,
            'updated': 0,
            'deleted': 0
        }
        
        logger.info(f"Batch processing {len(events)} events")
        
        # Group events by fabric for better database performance
        events_by_fabric = {}
        for event in events:
            if event.fabric_id not in events_by_fabric:
                events_by_fabric[event.fabric_id] = []
            events_by_fabric[event.fabric_id].append(event)
        
        # Process each fabric's events in a transaction
        for fabric_id, fabric_events in events_by_fabric.items():
            try:
                with transaction.atomic():
                    for event in fabric_events:
                        success = await self.process_crd_event(event)
                        if success:
                            results['processed'] += 1
                            if event.event_type == EventType.ADDED:
                                results['created'] += 1
                            elif event.event_type == EventType.MODIFIED:
                                results['updated'] += 1
                            elif event.event_type == EventType.DELETED:
                                results['deleted'] += 1
                        else:
                            results['errors'] += 1
                            
            except Exception as e:
                logger.error(f"Batch processing failed for fabric {fabric_id}: {e}")
                results['errors'] += len(fabric_events)
        
        logger.info(f"Batch processing completed: {results}")
        return results
    
    def register_event_filter(self, fabric_id: int, filter_func: Callable[[CRDEvent], bool]) -> None:
        """Register event filter for a fabric"""
        if fabric_id not in self._event_filters:
            self._event_filters[fabric_id] = []
        self._event_filters[fabric_id].append(filter_func)
        logger.debug(f"Registered event filter for fabric {fabric_id}")
    
    async def get_processing_stats(self, fabric_id: Optional[int] = None) -> Dict[str, Any]:
        """Get event processing statistics"""
        stats = self._processing_stats.copy()
        
        if fabric_id is not None:
            # Filter stats for specific fabric (would need fabric-specific tracking)
            # For now, return global stats
            pass
        
        return stats
    
    async def _handle_crd_created(self, event: CRDEvent) -> bool:
        """Handle CRD creation event"""
        try:
            model_class = self._get_model_class(event.kind)
            if not model_class:
                logger.warning(f"No model found for CRD kind: {event.kind}")
                return False
            
            # Get fabric model
            fabric = await self._get_fabric(event.fabric_id)
            if not fabric:
                logger.error(f"Fabric {event.fabric_id} not found")
                return False
            
            # Prepare CRD data
            crd_data = self._prepare_crd_data(event, fabric)
            
            # Check if CRD already exists (handle race conditions)
            existing_crd = model_class.objects.filter(
                fabric=fabric,
                name=event.name,
                namespace=event.namespace
            ).first()
            
            if existing_crd:
                logger.info(f"CRD {event.identifier} already exists, updating instead")
                return await self._update_crd(existing_crd, event, crd_data)
            
            # Create new CRD
            crd = model_class.objects.create(**crd_data)
            logger.info(f"Created CRD {event.identifier} (ID: {crd.pk})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle CRD creation for {event.identifier}: {e}")
            return False
    
    async def _handle_crd_updated(self, event: CRDEvent) -> bool:
        """Handle CRD update event"""
        try:
            model_class = self._get_model_class(event.kind)
            if not model_class:
                return False
            
            # Get fabric model
            fabric = await self._get_fabric(event.fabric_id)
            if not fabric:
                return False
            
            # Find existing CRD
            crd = model_class.objects.filter(
                fabric=fabric,
                name=event.name,
                namespace=event.namespace
            ).first()
            
            if not crd:
                logger.warning(f"CRD {event.identifier} not found for update, creating instead")
                return await self._handle_crd_created(event)
            
            # Prepare update data
            crd_data = self._prepare_crd_data(event, fabric)
            
            return await self._update_crd(crd, event, crd_data)
            
        except Exception as e:
            logger.error(f"Failed to handle CRD update for {event.identifier}: {e}")
            return False
    
    async def _handle_crd_deleted(self, event: CRDEvent) -> bool:
        """Handle CRD deletion event"""
        try:
            model_class = self._get_model_class(event.kind)
            if not model_class:
                return False
            
            # Get fabric model
            fabric = await self._get_fabric(event.fabric_id)
            if not fabric:
                return False
            
            # Find and delete CRD
            deleted_count = model_class.objects.filter(
                fabric=fabric,
                name=event.name,
                namespace=event.namespace
            ).delete()[0]
            
            if deleted_count > 0:
                logger.info(f"Deleted CRD {event.identifier}")
                return True
            else:
                logger.warning(f"CRD {event.identifier} not found for deletion")
                return True  # Consider it successful since it's already gone
                
        except Exception as e:
            logger.error(f"Failed to handle CRD deletion for {event.identifier}: {e}")
            return False
    
    async def _handle_crd_error(self, event: CRDEvent) -> bool:
        """Handle CRD error event"""
        logger.error(f"Kubernetes error event for {event.identifier}: {event.crd_data}")
        
        # Publish error event
        if self._event_service:
            await self._event_service.publish_fabric_event(
                event.fabric_id,
                "crd_error",
                {
                    'kind': event.kind,
                    'name': event.name,
                    'namespace': event.namespace,
                    'error': event.crd_data
                },
                EventPriority.HIGH
            )
        
        return True
    
    def _get_model_class(self, kind: str):
        """Get Django model class for CRD kind"""
        try:
            model_name = self.KIND_TO_MODEL.get(kind)
            if not model_name:
                return None
            
            return apps.get_model('netbox_hedgehog', model_name)
            
        except Exception as e:
            logger.error(f"Failed to get model class for kind {kind}: {e}")
            return None
    
    async def _get_fabric(self, fabric_id: int):
        """Get fabric model by ID"""
        try:
            HedgehogFabric = apps.get_model('netbox_hedgehog', 'HedgehogFabric')
            return HedgehogFabric.objects.get(pk=fabric_id)
        except Exception as e:
            logger.error(f"Failed to get fabric {fabric_id}: {e}")
            return None
    
    def _prepare_crd_data(self, event: CRDEvent, fabric) -> Dict[str, Any]:
        """Prepare CRD data for database creation/update"""
        crd_data = {
            'fabric': fabric,
            'name': event.name,
            'namespace': event.namespace,
            'spec': event.crd_data.get('spec', {}),
            'labels': event.crd_data.get('metadata', {}).get('labels', {}),
            'annotations': event.crd_data.get('metadata', {}).get('annotations', {}),
        }
        
        # Add additional fields if they exist on the model
        metadata = event.crd_data.get('metadata', {})
        if 'uid' in metadata:
            crd_data['kubernetes_uid'] = metadata['uid']
        if 'resourceVersion' in metadata:
            crd_data['resource_version'] = metadata['resourceVersion']
        if 'creationTimestamp' in metadata:
            crd_data['creation_timestamp'] = metadata['creationTimestamp']
        
        # Add status if available
        if 'status' in event.crd_data:
            crd_data['status'] = event.crd_data['status']
        
        return crd_data
    
    async def _update_crd(self, crd, event: CRDEvent, crd_data: Dict[str, Any]) -> bool:
        """Update existing CRD model"""
        try:
            # Update fields
            for field, value in crd_data.items():
                if field != 'fabric':  # Don't update fabric field
                    setattr(crd, field, value)
            
            crd.save()
            logger.info(f"Updated CRD {event.identifier} (ID: {crd.pk})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update CRD {event.identifier}: {e}")
            return False
    
    def _should_process_event(self, event: CRDEvent) -> bool:
        """Check if event should be processed based on filters"""
        fabric_filters = self._event_filters.get(event.fabric_id, [])
        
        for filter_func in fabric_filters:
            try:
                if not filter_func(event):
                    return False
            except Exception as e:
                logger.error(f"Event filter failed: {e}")
                # Continue processing if filter fails
        
        return True
    
    def _update_processing_stats(self, event: CRDEvent, success: bool):
        """Update processing statistics"""
        self._processing_stats['total_processed'] += 1
        self._processing_stats['by_event_type'][event.event_type.value] += 1
        self._processing_stats['by_kind'][event.kind] = (
            self._processing_stats['by_kind'].get(event.kind, 0) + 1
        )
        if not success:
            self._processing_stats['errors'] += 1
        self._processing_stats['last_processed'] = datetime.now(timezone.utc).isoformat()
    
    async def _publish_processing_event(self, event: CRDEvent, success: bool):
        """Publish event processing notification"""
        if not self._event_service:
            return
        
        try:
            await self._event_service.publish_crd_event(
                event.fabric_id,
                event.kind,
                event.name,
                f"processed_{event.event_type.value.lower()}",
                {
                    'success': success,
                    'namespace': event.namespace,
                    'resource_version': event.resource_version,
                    'processing_timestamp': datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to publish processing event: {e}")