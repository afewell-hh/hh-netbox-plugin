"""
Orphaned Resource Detection Algorithms
=====================================

This module provides algorithms for detecting orphaned resources in GitOps workflows.
Orphaned resources are resources that exist in the Kubernetes cluster but are not
tracked in the Git repository.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from dataclasses import dataclass
from ..models import HedgehogFabric, HedgehogResource, ReconciliationAlert
from ..models.reconciliation import AlertSeverityChoices, AlertStatusChoices
from .kubernetes import get_kubernetes_client
from .git_monitor import GitRepositoryMonitor

logger = logging.getLogger(__name__)


@dataclass
class OrphanedResourceInfo:
    """Information about an orphaned resource"""
    name: str
    namespace: str
    kind: str
    api_version: str
    resource_version: str
    spec: Dict
    status: Dict
    labels: Dict
    annotations: Dict
    creation_timestamp: datetime
    last_seen: datetime
    orphaned_duration: timedelta
    cluster_uid: str
    

@dataclass
class OrphanDetectionResult:
    """Result of orphaned resource detection"""
    fabric: HedgehogFabric
    total_cluster_resources: int
    total_git_resources: int
    orphaned_resources: List[OrphanedResourceInfo]
    orphaned_count: int
    detection_timestamp: datetime
    processing_time: float
    errors: List[str]
    warnings: List[str]


class OrphanedResourceDetector:
    """
    Detects orphaned resources by comparing cluster state with Git repository state.
    """
    
    def __init__(self, fabric: HedgehogFabric):
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
        self.supported_kinds = {
            'VPC', 'External', 'ExternalAttachment', 'ExternalPeering', 'IPv4Namespace',
            'VPCAttachment', 'VPCPeering', 'Connection', 'Server', 'Switch', 
            'SwitchGroup', 'VLANNamespace'
        }
    
    async def detect_orphaned_resources(self) -> OrphanDetectionResult:
        """
        Main method to detect orphaned resources.
        Returns detailed results about orphaned resources found.
        """
        start_time = timezone.now()
        result = OrphanDetectionResult(
            fabric=self.fabric,
            total_cluster_resources=0,
            total_git_resources=0,
            orphaned_resources=[],
            orphaned_count=0,
            detection_timestamp=start_time,
            processing_time=0.0,
            errors=[],
            warnings=[]
        )
        
        try:
            # Get cluster resources
            cluster_resources = await self._get_cluster_resources()
            result.total_cluster_resources = len(cluster_resources)
            
            # Get Git-tracked resources
            git_resources = await self._get_git_tracked_resources()
            result.total_git_resources = len(git_resources)
            
            # Find orphaned resources
            orphaned = self._find_orphaned_resources(cluster_resources, git_resources)
            result.orphaned_resources = orphaned
            result.orphaned_count = len(orphaned)
            
            # Calculate processing time
            end_time = timezone.now()
            result.processing_time = (end_time - start_time).total_seconds()
            
            self.logger.info(
                f"Orphaned resource detection completed. "
                f"Found {result.orphaned_count} orphaned resources out of "
                f"{result.total_cluster_resources} cluster resources"
            )
            
        except Exception as e:
            result.errors.append(f"Detection failed: {str(e)}")
            self.logger.error(f"Orphaned resource detection failed: {e}")
        
        return result
    
    async def _get_cluster_resources(self) -> Dict[str, OrphanedResourceInfo]:
        """Get all relevant resources from the Kubernetes cluster"""
        cluster_resources = {}
        
        try:
            # Get Kubernetes client for this fabric
            k8s_client = get_kubernetes_client(self.fabric.get_kubernetes_config())
            
            # Get all relevant CRDs
            for kind in self.supported_kinds:
                try:
                    resources = await self._get_resources_by_kind(k8s_client, kind)
                    cluster_resources.update(resources)
                except Exception as e:
                    self.logger.warning(f"Failed to get {kind} resources: {e}")
            
        except Exception as e:
            self.logger.error(f"Failed to get cluster resources: {e}")
            raise
        
        return cluster_resources
    
    async def _get_resources_by_kind(self, k8s_client, kind: str) -> Dict[str, OrphanedResourceInfo]:
        """Get resources of a specific kind from the cluster"""
        resources = {}
        
        try:
            # Map kind to API group and version
            api_mapping = {
                'VPC': ('vpc.githedgehog.com', 'v1beta1', 'vpcs'),
                'External': ('vpc.githedgehog.com', 'v1beta1', 'externals'),
                'ExternalAttachment': ('vpc.githedgehog.com', 'v1beta1', 'externalattachments'),
                'ExternalPeering': ('vpc.githedgehog.com', 'v1beta1', 'externalpeerings'),
                'IPv4Namespace': ('vpc.githedgehog.com', 'v1beta1', 'ipv4namespaces'),
                'VPCAttachment': ('vpc.githedgehog.com', 'v1beta1', 'vpcattachments'),
                'VPCPeering': ('vpc.githedgehog.com', 'v1beta1', 'vpcpeerings'),
                'Connection': ('wiring.githedgehog.com', 'v1beta1', 'connections'),
                'Server': ('wiring.githedgehog.com', 'v1beta1', 'servers'),
                'Switch': ('wiring.githedgehog.com', 'v1beta1', 'switches'),
                'SwitchGroup': ('wiring.githedgehog.com', 'v1beta1', 'switchgroups'),
                'VLANNamespace': ('wiring.githedgehog.com', 'v1beta1', 'vlannamespaces'),
            }
            
            if kind not in api_mapping:
                return resources
            
            group, version, plural = api_mapping[kind]
            
            # This is a placeholder - actual Kubernetes API call would be implemented here
            # For now, we'll use the existing data from HedgehogResource
            db_resources = HedgehogResource.objects.filter(
                fabric=self.fabric,
                kind=kind,
                actual_spec__isnull=False
            )
            
            for resource in db_resources:
                resource_key = f"{resource.namespace}/{kind}/{resource.name}"
                
                # Parse creation timestamp
                creation_timestamp = resource.first_seen or timezone.now()
                
                resources[resource_key] = OrphanedResourceInfo(
                    name=resource.name,
                    namespace=resource.namespace,
                    kind=kind,
                    api_version=f"{group}/{version}",
                    resource_version=resource.actual_resource_version or "unknown",
                    spec=resource.actual_spec or {},
                    status=resource.actual_status or {},
                    labels=resource.labels or {},
                    annotations=resource.annotations or {},
                    creation_timestamp=creation_timestamp,
                    last_seen=resource.actual_updated or timezone.now(),
                    orphaned_duration=timedelta(0),
                    cluster_uid=f"{resource.namespace}-{resource.name}-{kind}"
                )
        
        except Exception as e:
            self.logger.error(f"Failed to get {kind} resources: {e}")
            raise
        
        return resources
    
    async def _get_git_tracked_resources(self) -> Set[str]:
        """Get set of resources tracked in Git repository"""
        git_resources = set()
        
        try:
            # Get resources from database that have desired state (from Git)
            tracked_resources = HedgehogResource.objects.filter(
                fabric=self.fabric,
                desired_spec__isnull=False
            )
            
            for resource in tracked_resources:
                resource_key = f"{resource.namespace}/{resource.kind}/{resource.name}"
                git_resources.add(resource_key)
            
            self.logger.debug(f"Found {len(git_resources)} Git-tracked resources")
            
        except Exception as e:
            self.logger.error(f"Failed to get Git-tracked resources: {e}")
            raise
        
        return git_resources
    
    def _find_orphaned_resources(self, cluster_resources: Dict[str, OrphanedResourceInfo], 
                                git_resources: Set[str]) -> List[OrphanedResourceInfo]:
        """Find resources that exist in cluster but not in Git"""
        orphaned = []
        
        for resource_key, resource_info in cluster_resources.items():
            if resource_key not in git_resources:
                # Calculate orphaned duration
                resource_info.orphaned_duration = timezone.now() - resource_info.creation_timestamp
                orphaned.append(resource_info)
        
        # Sort by orphaned duration (longest orphaned first)
        orphaned.sort(key=lambda x: x.orphaned_duration, reverse=True)
        
        return orphaned
    
    def calculate_orphan_severity(self, resource_info: OrphanedResourceInfo) -> str:
        """Calculate severity level for orphaned resource"""
        # Critical: Long-running orphaned resources
        if resource_info.orphaned_duration > timedelta(days=7):
            return AlertSeverityChoices.CRITICAL
        
        # High: Medium-term orphaned resources
        if resource_info.orphaned_duration > timedelta(days=1):
            return AlertSeverityChoices.HIGH
        
        # Medium: Recently orphaned resources
        if resource_info.orphaned_duration > timedelta(hours=1):
            return AlertSeverityChoices.MEDIUM
        
        # Low: Very recent orphaned resources
        return AlertSeverityChoices.LOW
    
    async def create_orphaned_alerts(self, detection_result: OrphanDetectionResult) -> List[ReconciliationAlert]:
        """Create reconciliation alerts for orphaned resources"""
        alerts = []
        
        for resource_info in detection_result.orphaned_resources:
            try:
                # Check if alert already exists
                existing_alert = ReconciliationAlert.objects.filter(
                    fabric=self.fabric,
                    alert_type='orphaned_resource',
                    status__in=[AlertStatusChoices.ACTIVE, AlertStatusChoices.ACKNOWLEDGED],
                    alert_context__name=resource_info.name,
                    alert_context__namespace=resource_info.namespace,
                    alert_context__kind=resource_info.kind
                ).first()
                
                if existing_alert:
                    self.logger.debug(f"Alert already exists for orphaned resource: {resource_info.name}")
                    continue
                
                # Get or create HedgehogResource
                resource, created = HedgehogResource.objects.get_or_create(
                    fabric=self.fabric,
                    namespace=resource_info.namespace,
                    name=resource_info.name,
                    kind=resource_info.kind,
                    defaults={
                        'api_version': resource_info.api_version,
                        'actual_spec': resource_info.spec,
                        'actual_status': resource_info.status,
                        'actual_resource_version': resource_info.resource_version,
                        'actual_updated': resource_info.last_seen,
                        'labels': resource_info.labels,
                        'annotations': resource_info.annotations,
                        'resource_state': 'orphaned',
                        'drift_status': 'actual_only'
                    }
                )
                
                # Calculate severity
                severity = self.calculate_orphan_severity(resource_info)
                
                # Create alert
                alert = ReconciliationAlert.objects.create(
                    fabric=self.fabric,
                    resource=resource,
                    alert_type='orphaned_resource',
                    severity=severity,
                    title=f"Orphaned {resource_info.kind}: {resource_info.name}",
                    message=f"Resource {resource_info.kind}/{resource_info.name} exists in cluster but not in Git repository. "
                           f"Orphaned for {resource_info.orphaned_duration}.",
                    alert_context={
                        'name': resource_info.name,
                        'namespace': resource_info.namespace,
                        'kind': resource_info.kind,
                        'api_version': resource_info.api_version,
                        'creation_timestamp': resource_info.creation_timestamp.isoformat(),
                        'orphaned_duration_seconds': resource_info.orphaned_duration.total_seconds(),
                        'cluster_uid': resource_info.cluster_uid
                    },
                    drift_details={
                        'drift_type': 'orphaned',
                        'drift_score': 1.0,
                        'details': {
                            'message': 'Resource exists in cluster but not in Git',
                            'resource_spec': resource_info.spec,
                            'resource_status': resource_info.status
                        }
                    },
                    suggested_action='import_to_git'
                )
                
                alerts.append(alert)
                self.logger.info(f"Created orphaned resource alert: {alert.title}")
                
            except Exception as e:
                self.logger.error(f"Failed to create alert for orphaned resource {resource_info.name}: {e}")
        
        return alerts
    
    async def process_orphaned_resources(self) -> Dict:
        """Complete workflow for processing orphaned resources"""
        result = {
            'detection_result': None,
            'alerts_created': [],
            'processing_summary': {},
            'errors': []
        }
        
        try:
            # Detect orphaned resources
            detection_result = await self.detect_orphaned_resources()
            result['detection_result'] = detection_result
            
            # Create alerts for orphaned resources
            alerts = await self.create_orphaned_alerts(detection_result)
            result['alerts_created'] = alerts
            
            # Create processing summary
            result['processing_summary'] = {
                'total_cluster_resources': detection_result.total_cluster_resources,
                'total_git_resources': detection_result.total_git_resources,
                'orphaned_resources_found': detection_result.orphaned_count,
                'alerts_created': len(alerts),
                'processing_time': detection_result.processing_time,
                'fabric': self.fabric.name,
                'timestamp': detection_result.detection_timestamp.isoformat()
            }
            
            self.logger.info(
                f"Orphaned resource processing completed. "
                f"Found {detection_result.orphaned_count} orphaned resources, "
                f"created {len(alerts)} alerts"
            )
            
        except Exception as e:
            error_msg = f"Orphaned resource processing failed: {str(e)}"
            result['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return result


class OrphanedResourceManager:
    """
    Manager for handling orphaned resources across multiple fabrics.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def process_all_fabrics(self) -> Dict:
        """Process orphaned resources for all fabrics"""
        results = {}
        
        fabrics = HedgehogFabric.objects.filter(
            sync_enabled=True,
            git_repository_url__isnull=False
        )
        
        for fabric in fabrics:
            self.logger.info(f"Processing orphaned resources for fabric: {fabric.name}")
            
            try:
                detector = OrphanedResourceDetector(fabric)
                fabric_result = await detector.process_orphaned_resources()
                results[fabric.name] = fabric_result
                
            except Exception as e:
                self.logger.error(f"Failed to process fabric {fabric.name}: {e}")
                results[fabric.name] = {
                    'error': str(e),
                    'fabric': fabric.name
                }
        
        return results
    
    def get_orphaned_resource_stats(self, fabric: Optional[HedgehogFabric] = None) -> Dict:
        """Get statistics about orphaned resources"""
        queryset = ReconciliationAlert.objects.filter(
            alert_type='orphaned_resource',
            status__in=[AlertStatusChoices.ACTIVE, AlertStatusChoices.ACKNOWLEDGED]
        )
        
        if fabric:
            queryset = queryset.filter(fabric=fabric)
        
        stats = {
            'total_orphaned_alerts': queryset.count(),
            'by_severity': {},
            'by_kind': {},
            'by_fabric': {},
            'oldest_orphaned': None,
            'newest_orphaned': None
        }
        
        # Group by severity
        for severity in AlertSeverityChoices.CHOICES:
            stats['by_severity'][severity[0]] = queryset.filter(severity=severity[0]).count()
        
        # Group by resource kind
        for alert in queryset:
            kind = alert.resource.kind
            stats['by_kind'][kind] = stats['by_kind'].get(kind, 0) + 1
        
        # Group by fabric
        for alert in queryset:
            fabric_name = alert.fabric.name
            stats['by_fabric'][fabric_name] = stats['by_fabric'].get(fabric_name, 0) + 1
        
        # Get oldest and newest
        oldest = queryset.order_by('created').first()
        newest = queryset.order_by('-created').first()
        
        if oldest:
            stats['oldest_orphaned'] = {
                'resource': f"{oldest.resource.kind}/{oldest.resource.name}",
                'created': oldest.created.isoformat(),
                'fabric': oldest.fabric.name
            }
        
        if newest:
            stats['newest_orphaned'] = {
                'resource': f"{newest.resource.kind}/{newest.resource.name}",
                'created': newest.created.isoformat(),
                'fabric': newest.fabric.name
            }
        
        return stats
    
    def cleanup_resolved_orphaned_alerts(self, older_than_days: int = 30) -> int:
        """Clean up resolved orphaned alerts older than specified days"""
        cutoff_date = timezone.now() - timedelta(days=older_than_days)
        
        deleted_count = ReconciliationAlert.objects.filter(
            alert_type='orphaned_resource',
            status=AlertStatusChoices.RESOLVED,
            resolved_at__lt=cutoff_date
        ).delete()[0]
        
        self.logger.info(f"Cleaned up {deleted_count} resolved orphaned alerts older than {older_than_days} days")
        
        return deleted_count