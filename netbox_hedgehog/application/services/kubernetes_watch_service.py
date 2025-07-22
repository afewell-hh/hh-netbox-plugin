"""
Kubernetes Watch Service
Implementation of Kubernetes CRD monitoring for real-time updates
"""

import asyncio
import logging
import json
import ssl
import base64
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime, timezone
from urllib.parse import urlparse

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import aiohttp

from ...domain.interfaces.kubernetes_watch_interface import (
    KubernetesWatchInterface, EventProcessorInterface,
    EventType, CRDEvent, WatchStatus, FabricConnectionInfo,
    KubernetesError, WatchConnectionError
)
from ...domain.interfaces.event_service_interface import EventServiceInterface
from ..service_registry import registry, get_service

logger = logging.getLogger(__name__)


class KubernetesWatchService(KubernetesWatchInterface):
    """
    Service for monitoring Kubernetes CRD changes in real-time.
    Implements watch streams for Hedgehog fabric CRDs.
    """
    
    # Hedgehog CRD configuration
    HEDGEHOG_CRDS = {
        'VPC': {
            'group': 'vpc.githedgehog.com',
            'version': 'v1alpha2',
            'plural': 'vpcs'
        },
        'External': {
            'group': 'vpc.githedgehog.com', 
            'version': 'v1alpha2',
            'plural': 'externals'
        },
        'ExternalAttachment': {
            'group': 'vpc.githedgehog.com',
            'version': 'v1alpha2', 
            'plural': 'externalattachments'
        },
        'ExternalPeering': {
            'group': 'vpc.githedgehog.com',
            'version': 'v1alpha2',
            'plural': 'externalpeerings'
        },
        'IPv4Namespace': {
            'group': 'vpc.githedgehog.com',
            'version': 'v1alpha2',
            'plural': 'ipv4namespaces'
        },
        'VPCAttachment': {
            'group': 'vpc.githedgehog.com',
            'version': 'v1alpha2',
            'plural': 'vpcattachments'
        },
        'VPCPeering': {
            'group': 'vpc.githedgehog.com',
            'version': 'v1alpha2',
            'plural': 'vpcpeerings'
        },
        'Connection': {
            'group': 'wiring.githedgehog.com',
            'version': 'v1alpha2',
            'plural': 'connections'
        },
        'Server': {
            'group': 'wiring.githedgehog.com',
            'version': 'v1alpha2',
            'plural': 'servers'
        },
        'Switch': {
            'group': 'wiring.githedgehog.com',
            'version': 'v1alpha2',
            'plural': 'switches'
        },
        'SwitchGroup': {
            'group': 'wiring.githedgehog.com',
            'version': 'v1alpha2',
            'plural': 'switchgroups'
        },
        'VLANNamespace': {
            'group': 'wiring.githedgehog.com',
            'version': 'v1alpha2',
            'plural': 'vlannamespaces'
        }
    }
    
    def __init__(self):
        self._active_watches: Dict[int, Dict[str, Any]] = {}
        self._event_handlers: Dict[EventType, List] = {event_type: [] for event_type in EventType}
        self._watch_tasks: Dict[int, asyncio.Task] = {}
        self._event_processor: Optional[EventProcessorInterface] = None
        self._event_service: Optional[EventServiceInterface] = None
    
    def set_event_processor(self, processor: EventProcessorInterface):
        """Set the event processor service"""
        self._event_processor = processor
    
    def set_event_service(self, event_service: EventServiceInterface):
        """Set the event service for publishing events"""
        self._event_service = event_service
    
    async def start_fabric_watch(self, fabric_connection: FabricConnectionInfo) -> bool:
        """Start watching CRDs for a specific fabric"""
        try:
            if fabric_connection.fabric_id in self._active_watches:
                logger.info(f"Watch already active for fabric {fabric_connection.fabric_id}")
                return True
            
            # Validate connection
            validation_result = await self.validate_fabric_connection(fabric_connection)
            if not validation_result.get('valid', False):
                raise WatchConnectionError(f"Invalid fabric connection: {validation_result.get('error')}")
            
            # Create Kubernetes client configuration
            api_client = self._create_api_client(fabric_connection)
            
            # Initialize watch status
            watch_status = WatchStatus(
                is_active=True,
                fabric_id=fabric_connection.fabric_id,
                start_time=datetime.now(timezone.utc).isoformat(),
                last_event_time=None,
                event_count=0,
                errors=[],
                resource_version=""
            )
            
            self._active_watches[fabric_connection.fabric_id] = {
                'connection': fabric_connection,
                'status': watch_status,
                'api_client': api_client,
                'watch_objects': {}
            }
            
            # Start watch task
            watch_task = asyncio.create_task(
                self._watch_fabric_crds(fabric_connection.fabric_id)
            )
            self._watch_tasks[fabric_connection.fabric_id] = watch_task
            
            logger.info(f"Started Kubernetes watch for fabric {fabric_connection.fabric_id}")
            
            # Publish fabric watch started event
            if self._event_service:
                await self._event_service.publish_fabric_event(
                    fabric_connection.fabric_id,
                    "watch_started",
                    {"cluster_endpoint": fabric_connection.cluster_endpoint}
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start watch for fabric {fabric_connection.fabric_id}: {e}")
            raise WatchConnectionError(str(e))
    
    async def stop_fabric_watch(self, fabric_id: int) -> bool:
        """Stop watching CRDs for a specific fabric"""
        try:
            if fabric_id not in self._active_watches:
                logger.warning(f"No active watch for fabric {fabric_id}")
                return True
            
            # Cancel watch task
            if fabric_id in self._watch_tasks:
                self._watch_tasks[fabric_id].cancel()
                del self._watch_tasks[fabric_id]
            
            # Clean up watch resources
            watch_data = self._active_watches[fabric_id]
            for watch_obj in watch_data.get('watch_objects', {}).values():
                try:
                    watch_obj.stop()
                except Exception as e:
                    logger.warning(f"Error stopping watch object: {e}")
            
            # Remove from active watches
            del self._active_watches[fabric_id]
            
            logger.info(f"Stopped Kubernetes watch for fabric {fabric_id}")
            
            # Publish fabric watch stopped event
            if self._event_service:
                await self._event_service.publish_fabric_event(
                    fabric_id,
                    "watch_stopped",
                    {}
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop watch for fabric {fabric_id}: {e}")
            return False
    
    async def get_watch_status(self, fabric_id: int) -> Optional[WatchStatus]:
        """Get current watch status for a fabric"""
        if fabric_id not in self._active_watches:
            return None
        
        return self._active_watches[fabric_id]['status']
    
    async def list_fabric_crds(self, fabric_connection: FabricConnectionInfo) -> List[Dict[str, Any]]:
        """List current CRDs in fabric cluster"""
        try:
            api_client = self._create_api_client(fabric_connection)
            custom_api = client.CustomObjectsApi(api_client)
            
            all_crds = []
            
            for kind, crd_info in self.HEDGEHOG_CRDS.items():
                if kind not in fabric_connection.enabled_crds:
                    continue
                
                try:
                    # List CRDs of this type
                    response = custom_api.list_namespaced_custom_object(
                        group=crd_info['group'],
                        version=crd_info['version'],
                        namespace=fabric_connection.namespace,
                        plural=crd_info['plural']
                    )
                    
                    for item in response.get('items', []):
                        crd_data = {
                            'kind': kind,
                            'name': item['metadata']['name'],
                            'namespace': item['metadata']['namespace'],
                            'uid': item['metadata']['uid'],
                            'resource_version': item['metadata']['resourceVersion'],
                            'creation_timestamp': item['metadata']['creationTimestamp'],
                            'spec': item.get('spec', {}),
                            'status': item.get('status', {})
                        }
                        all_crds.append(crd_data)
                        
                except ApiException as e:
                    if e.status == 404:
                        logger.warning(f"CRD type {kind} not found in cluster")
                        continue
                    else:
                        raise
            
            logger.info(f"Listed {len(all_crds)} CRDs for fabric {fabric_connection.fabric_id}")
            return all_crds
            
        except Exception as e:
            logger.error(f"Failed to list CRDs for fabric {fabric_connection.fabric_id}: {e}")
            raise KubernetesError(str(e))
    
    async def watch_crd_stream(self, fabric_connection: FabricConnectionInfo) -> AsyncIterator[CRDEvent]:
        """Stream CRD events for a fabric"""
        try:
            api_client = self._create_api_client(fabric_connection)
            custom_api = client.CustomObjectsApi(api_client)
            
            for kind in fabric_connection.enabled_crds:
                if kind not in self.HEDGEHOG_CRDS:
                    continue
                
                crd_info = self.HEDGEHOG_CRDS[kind]
                
                # Create watch stream
                w = watch.Watch()
                
                try:
                    stream = w.stream(
                        custom_api.list_namespaced_custom_object,
                        group=crd_info['group'],
                        version=crd_info['version'],
                        namespace=fabric_connection.namespace,
                        plural=crd_info['plural'],
                        timeout_seconds=0  # Watch indefinitely
                    )
                    
                    for event in stream:
                        event_type = EventType(event['type'])
                        obj = event['object']
                        
                        crd_event = CRDEvent(
                            event_type=event_type,
                            crd_data=obj,
                            fabric_id=fabric_connection.fabric_id,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            resource_version=obj['metadata']['resourceVersion'],
                            namespace=obj['metadata']['namespace'],
                            name=obj['metadata']['name'],
                            kind=kind
                        )
                        
                        yield crd_event
                        
                except ApiException as e:
                    if e.status == 404:
                        logger.warning(f"CRD type {kind} not available for watching")
                        continue
                    else:
                        raise
                        
        except Exception as e:
            logger.error(f"Watch stream failed for fabric {fabric_connection.fabric_id}: {e}")
            raise KubernetesError(str(e))
    
    def register_event_handler(self, event_type: EventType, handler):
        """Register handler for specific event types"""
        self._event_handlers[event_type].append(handler)
        logger.debug(f"Registered event handler for {event_type.value}")
    
    async def validate_fabric_connection(self, fabric_connection: FabricConnectionInfo) -> Dict[str, Any]:
        """Validate fabric Kubernetes connection"""
        try:
            if not fabric_connection.is_valid:
                return {
                    'valid': False,
                    'error': 'Missing required connection parameters'
                }
            
            # Create API client and test connection
            api_client = self._create_api_client(fabric_connection)
            core_api = client.CoreV1Api(api_client)
            
            # Test with a simple API call
            namespaces = core_api.list_namespace(limit=1)
            
            return {
                'valid': True,
                'cluster_version': getattr(namespaces, 'api_version', 'unknown'),
                'accessible_namespaces': 1
            }
            
        except Exception as e:
            logger.error(f"Connection validation failed for fabric {fabric_connection.fabric_id}: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    async def get_cluster_info(self, fabric_connection: FabricConnectionInfo) -> Dict[str, Any]:
        """Get cluster information and health status"""
        try:
            api_client = self._create_api_client(fabric_connection)
            core_api = client.CoreV1Api(api_client)
            version_api = client.VersionApi(api_client)
            
            # Get cluster version
            version_info = version_api.get_code()
            
            # Get node information
            nodes = core_api.list_node()
            
            # Get namespace information
            namespaces = core_api.list_namespace()
            
            cluster_info = {
                'version': {
                    'kubernetes': version_info.git_version,
                    'platform': version_info.platform
                },
                'nodes': {
                    'total': len(nodes.items),
                    'ready': sum(1 for node in nodes.items 
                               if any(condition.type == 'Ready' and condition.status == 'True'
                                     for condition in node.status.conditions))
                },
                'namespaces': len(namespaces.items),
                'cluster_endpoint': fabric_connection.cluster_endpoint
            }
            
            return cluster_info
            
        except Exception as e:
            logger.error(f"Failed to get cluster info for fabric {fabric_connection.fabric_id}: {e}")
            raise KubernetesError(str(e))
    
    def _create_api_client(self, fabric_connection: FabricConnectionInfo) -> client.ApiClient:
        """Create Kubernetes API client from fabric connection"""
        try:
            # Create configuration
            configuration = client.Configuration()
            configuration.host = fabric_connection.cluster_endpoint
            
            if fabric_connection.token:
                configuration.api_key = {"authorization": f"Bearer {fabric_connection.token}"}
            
            if fabric_connection.ca_cert:
                # Write CA cert to temporary file for SSL verification
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
                    f.write(fabric_connection.ca_cert)
                    configuration.ssl_ca_cert = f.name
            else:
                # Disable SSL verification if no CA cert provided
                configuration.verify_ssl = False
            
            return client.ApiClient(configuration)
            
        except Exception as e:
            logger.error(f"Failed to create API client: {e}")
            raise KubernetesError(str(e))
    
    async def _watch_fabric_crds(self, fabric_id: int):
        """Internal method to watch CRDs for a fabric"""
        try:
            watch_data = self._active_watches[fabric_id]
            fabric_connection = watch_data['connection']
            
            logger.info(f"Starting CRD watch streams for fabric {fabric_id}")
            
            # Start watch stream
            async for event in self.watch_crd_stream(fabric_connection):
                # Update watch status
                watch_data['status'].last_event_time = event.timestamp
                watch_data['status'].event_count += 1
                
                # Process event with handlers
                for handler in self._event_handlers[event.event_type]:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error(f"Event handler failed: {e}")
                
                # Process with event processor if available
                if self._event_processor:
                    try:
                        await self._event_processor.process_crd_event(event)
                    except Exception as e:
                        logger.error(f"Event processor failed: {e}")
                        watch_data['status'].errors.append(str(e))
                
                # Publish to event service
                if self._event_service:
                    try:
                        await self._event_service.publish_crd_event(
                            fabric_id,
                            event.kind,
                            event.name,
                            event.event_type.value.lower(),
                            {
                                'namespace': event.namespace,
                                'resource_version': event.resource_version,
                                'spec': event.crd_data.get('spec', {}),
                                'status': event.crd_data.get('status', {})
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to publish event: {e}")
                        
        except asyncio.CancelledError:
            logger.info(f"Watch task cancelled for fabric {fabric_id}")
        except Exception as e:
            logger.error(f"Watch task failed for fabric {fabric_id}: {e}")
            if fabric_id in self._active_watches:
                self._active_watches[fabric_id]['status'].errors.append(str(e))
                self._active_watches[fabric_id]['status'].is_active = False