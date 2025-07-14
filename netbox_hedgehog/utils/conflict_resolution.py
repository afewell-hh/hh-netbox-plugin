"""
Conflict Resolution Workflows
============================

This module provides workflows for resolving conflicts between Git and cluster states
in GitOps deployments. It handles scenarios where automated reconciliation is not
possible and manual intervention is required.
"""

import logging
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from dataclasses import dataclass
from enum import Enum

from ..models import HedgehogFabric, HedgehogResource, ReconciliationAlert
from ..models.reconciliation import AlertSeverityChoices, AlertStatusChoices, ResolutionActionChoices
from ..models.gitops import ResourceStateChoices

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of conflicts that can occur"""
    SPEC_CONFLICT = "spec_conflict"
    STRUCTURAL_CONFLICT = "structural_conflict"
    VALIDATION_CONFLICT = "validation_conflict"
    DEPENDENCY_CONFLICT = "dependency_conflict"
    POLICY_CONFLICT = "policy_conflict"
    MERGE_CONFLICT = "merge_conflict"


@dataclass
class ConflictInfo:
    """Information about a specific conflict"""
    conflict_type: ConflictType
    field_path: str
    git_value: Any
    cluster_value: Any
    severity: str
    description: str
    resolution_options: List[str]
    automatic_resolution: bool
    metadata: Dict[str, Any]


@dataclass
class ConflictResolutionResult:
    """Result of conflict resolution"""
    resource: HedgehogResource
    conflicts_detected: List[ConflictInfo]
    conflicts_resolved: List[ConflictInfo]
    resolution_actions: List[str]
    resolution_metadata: Dict[str, Any]
    success: bool
    errors: List[str]
    warnings: List[str]


class ConflictAnalyzer:
    """
    Analyzes conflicts between Git and cluster states.
    """
    
    def __init__(self, resource: HedgehogResource):
        self.resource = resource
        self.logger = logging.getLogger(f"{__name__}.{resource.fabric.name}")
    
    def analyze_conflicts(self) -> List[ConflictInfo]:
        """Analyze conflicts between desired and actual states"""
        conflicts = []
        
        if not self.resource.has_desired_state or not self.resource.has_actual_state:
            return conflicts
        
        try:
            # Analyze spec conflicts
            spec_conflicts = self._analyze_spec_conflicts()
            conflicts.extend(spec_conflicts)
            
            # Analyze structural conflicts
            structural_conflicts = self._analyze_structural_conflicts()
            conflicts.extend(structural_conflicts)
            
            # Analyze validation conflicts
            validation_conflicts = self._analyze_validation_conflicts()
            conflicts.extend(validation_conflicts)
            
            # Analyze dependency conflicts
            dependency_conflicts = self._analyze_dependency_conflicts()
            conflicts.extend(dependency_conflicts)
            
            self.logger.debug(f"Analyzed {len(conflicts)} conflicts for resource {self.resource.name}")
            
        except Exception as e:
            self.logger.error(f"Conflict analysis failed for {self.resource.name}: {e}")
        
        return conflicts
    
    def _analyze_spec_conflicts(self) -> List[ConflictInfo]:
        """Analyze specification conflicts"""
        conflicts = []
        
        desired_spec = self.resource.desired_spec or {}
        actual_spec = self.resource.actual_spec or {}
        
        # Compare spec fields
        all_fields = set(desired_spec.keys()) | set(actual_spec.keys())
        
        for field in all_fields:
            desired_value = desired_spec.get(field)
            actual_value = actual_spec.get(field)
            
            if desired_value != actual_value:
                conflict_info = ConflictInfo(
                    conflict_type=ConflictType.SPEC_CONFLICT,
                    field_path=field,
                    git_value=desired_value,
                    cluster_value=actual_value,
                    severity=self._calculate_field_conflict_severity(field, desired_value, actual_value),
                    description=f"Field '{field}' differs between Git and cluster",
                    resolution_options=[
                        ResolutionActionChoices.UPDATE_GIT,
                        ResolutionActionChoices.IMPORT_TO_GIT,
                        ResolutionActionChoices.MANUAL_REVIEW
                    ],
                    automatic_resolution=self._is_automatically_resolvable(field),
                    metadata={
                        'field': field,
                        'desired_value': desired_value,
                        'actual_value': actual_value,
                        'resource_kind': self.resource.kind
                    }
                )
                conflicts.append(conflict_info)
        
        return conflicts
    
    def _analyze_structural_conflicts(self) -> List[ConflictInfo]:
        """Analyze structural conflicts (schema mismatches)"""
        conflicts = []
        
        # Check for structural differences in nested objects
        desired_spec = self.resource.desired_spec or {}
        actual_spec = self.resource.actual_spec or {}
        
        # Analyze nested structure conflicts
        nested_conflicts = self._analyze_nested_conflicts(desired_spec, actual_spec, "")
        conflicts.extend(nested_conflicts)
        
        return conflicts
    
    def _analyze_nested_conflicts(self, desired: Dict, actual: Dict, path: str) -> List[ConflictInfo]:
        """Recursively analyze nested conflicts"""
        conflicts = []
        
        all_keys = set(desired.keys()) | set(actual.keys())
        
        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            desired_value = desired.get(key)
            actual_value = actual.get(key)
            
            # Check if types match
            if type(desired_value) != type(actual_value):
                conflict_info = ConflictInfo(
                    conflict_type=ConflictType.STRUCTURAL_CONFLICT,
                    field_path=current_path,
                    git_value=desired_value,
                    cluster_value=actual_value,
                    severity=AlertSeverityChoices.HIGH,
                    description=f"Type mismatch at '{current_path}': Git has {type(desired_value)}, cluster has {type(actual_value)}",
                    resolution_options=[ResolutionActionChoices.MANUAL_REVIEW],
                    automatic_resolution=False,
                    metadata={
                        'conflict_type': 'type_mismatch',
                        'git_type': str(type(desired_value)),
                        'cluster_type': str(type(actual_value))
                    }
                )
                conflicts.append(conflict_info)
            
            # Recursively analyze nested dictionaries
            elif isinstance(desired_value, dict) and isinstance(actual_value, dict):
                nested_conflicts = self._analyze_nested_conflicts(desired_value, actual_value, current_path)
                conflicts.extend(nested_conflicts)
        
        return conflicts
    
    def _analyze_validation_conflicts(self) -> List[ConflictInfo]:
        """Analyze validation conflicts (CRD schema violations)"""
        conflicts = []
        
        # Check for CRD schema validation issues
        if self.resource.actual_status:
            conditions = self.resource.actual_status.get('conditions', [])
            
            for condition in conditions:
                if condition.get('type') == 'ValidationError':
                    conflict_info = ConflictInfo(
                        conflict_type=ConflictType.VALIDATION_CONFLICT,
                        field_path='spec',
                        git_value=self.resource.desired_spec,
                        cluster_value=condition.get('message', 'Unknown validation error'),
                        severity=AlertSeverityChoices.HIGH,
                        description=f"CRD validation error: {condition.get('message', 'Unknown error')}",
                        resolution_options=[
                            ResolutionActionChoices.UPDATE_GIT,
                            ResolutionActionChoices.MANUAL_REVIEW
                        ],
                        automatic_resolution=False,
                        metadata={
                            'validation_error': condition.get('message'),
                            'last_transition_time': condition.get('lastTransitionTime'),
                            'reason': condition.get('reason')
                        }
                    )
                    conflicts.append(conflict_info)
        
        return conflicts
    
    def _analyze_dependency_conflicts(self) -> List[ConflictInfo]:
        """Analyze dependency conflicts"""
        conflicts = []
        
        # Check for dependency-related conflicts
        dependent_resources = self.resource.dependent_resources.all()
        
        for dep_resource in dependent_resources:
            if dep_resource.drift_status != 'in_sync':
                conflict_info = ConflictInfo(
                    conflict_type=ConflictType.DEPENDENCY_CONFLICT,
                    field_path='dependencies',
                    git_value=f"depends_on:{dep_resource.name}",
                    cluster_value=f"dependency_drift:{dep_resource.drift_status}",
                    severity=AlertSeverityChoices.MEDIUM,
                    description=f"Dependency {dep_resource.name} has drift status: {dep_resource.drift_status}",
                    resolution_options=[
                        ResolutionActionChoices.MANUAL_REVIEW,
                        ResolutionActionChoices.IGNORE
                    ],
                    automatic_resolution=False,
                    metadata={
                        'dependency_name': dep_resource.name,
                        'dependency_kind': dep_resource.kind,
                        'dependency_drift_status': dep_resource.drift_status
                    }
                )
                conflicts.append(conflict_info)
        
        return conflicts
    
    def _calculate_field_conflict_severity(self, field: str, desired_value: Any, actual_value: Any) -> str:
        """Calculate severity level for a field conflict"""
        # Critical fields that should never differ
        critical_fields = {'name', 'namespace', 'kind', 'apiVersion'}
        
        if field in critical_fields:
            return AlertSeverityChoices.CRITICAL
        
        # High priority fields
        high_priority_fields = {'spec.type', 'spec.subnet', 'spec.vlan', 'spec.endpoints'}
        
        if field in high_priority_fields:
            return AlertSeverityChoices.HIGH
        
        # Check if the change is substantial
        if isinstance(desired_value, (dict, list)) and isinstance(actual_value, (dict, list)):
            if len(str(desired_value)) != len(str(actual_value)):
                return AlertSeverityChoices.MEDIUM
        
        # Default to low severity
        return AlertSeverityChoices.LOW
    
    def _is_automatically_resolvable(self, field: str) -> bool:
        """Check if a field conflict can be automatically resolved"""
        # Fields that should not be automatically resolved
        critical_fields = {'name', 'namespace', 'kind', 'apiVersion'}
        
        if field in critical_fields:
            return False
        
        # Fields that can be automatically resolved
        auto_resolvable_fields = {'metadata.labels', 'metadata.annotations'}
        
        return field in auto_resolvable_fields


class ConflictResolver:
    """
    Resolves conflicts between Git and cluster states.
    """
    
    def __init__(self, resource: HedgehogResource):
        self.resource = resource
        self.logger = logging.getLogger(f"{__name__}.{resource.fabric.name}")
    
    def resolve_conflicts(self, conflicts: List[ConflictInfo], 
                         resolution_strategy: str = 'manual') -> ConflictResolutionResult:
        """Resolve conflicts based on strategy"""
        result = ConflictResolutionResult(
            resource=self.resource,
            conflicts_detected=conflicts,
            conflicts_resolved=[],
            resolution_actions=[],
            resolution_metadata={},
            success=False,
            errors=[],
            warnings=[]
        )
        
        try:
            if resolution_strategy == 'automatic':
                result = self._resolve_automatically(conflicts, result)
            elif resolution_strategy == 'favor_git':
                result = self._resolve_favor_git(conflicts, result)
            elif resolution_strategy == 'favor_cluster':
                result = self._resolve_favor_cluster(conflicts, result)
            else:
                result = self._resolve_manual(conflicts, result)
            
            result.success = True
            self.logger.info(f"Resolved {len(result.conflicts_resolved)} conflicts for {self.resource.name}")
            
        except Exception as e:
            result.errors.append(str(e))
            self.logger.error(f"Conflict resolution failed for {self.resource.name}: {e}")
        
        return result
    
    def _resolve_automatically(self, conflicts: List[ConflictInfo], 
                             result: ConflictResolutionResult) -> ConflictResolutionResult:
        """Resolve conflicts automatically where possible"""
        for conflict in conflicts:
            if conflict.automatic_resolution:
                # Apply automatic resolution
                if conflict.conflict_type == ConflictType.SPEC_CONFLICT:
                    # For spec conflicts, favor the cluster state for metadata
                    if conflict.field_path.startswith('metadata.'):
                        result.conflicts_resolved.append(conflict)
                        result.resolution_actions.append(f"Auto-resolved {conflict.field_path}: favored cluster")
                    else:
                        result.warnings.append(f"Cannot auto-resolve spec conflict: {conflict.field_path}")
                else:
                    result.warnings.append(f"Cannot auto-resolve conflict type: {conflict.conflict_type}")
            else:
                result.warnings.append(f"Conflict requires manual resolution: {conflict.field_path}")
        
        return result
    
    def _resolve_favor_git(self, conflicts: List[ConflictInfo], 
                          result: ConflictResolutionResult) -> ConflictResolutionResult:
        """Resolve conflicts by favoring Git state"""
        for conflict in conflicts:
            if conflict.conflict_type == ConflictType.SPEC_CONFLICT:
                # Update cluster to match Git
                result.conflicts_resolved.append(conflict)
                result.resolution_actions.append(f"Favored Git for {conflict.field_path}")
            else:
                result.warnings.append(f"Cannot favor Git for conflict type: {conflict.conflict_type}")
        
        return result
    
    def _resolve_favor_cluster(self, conflicts: List[ConflictInfo], 
                             result: ConflictResolutionResult) -> ConflictResolutionResult:
        """Resolve conflicts by favoring cluster state"""
        for conflict in conflicts:
            if conflict.conflict_type == ConflictType.SPEC_CONFLICT:
                # Update Git to match cluster
                result.conflicts_resolved.append(conflict)
                result.resolution_actions.append(f"Favored cluster for {conflict.field_path}")
            else:
                result.warnings.append(f"Cannot favor cluster for conflict type: {conflict.conflict_type}")
        
        return result
    
    def _resolve_manual(self, conflicts: List[ConflictInfo], 
                       result: ConflictResolutionResult) -> ConflictResolutionResult:
        """Mark conflicts for manual resolution"""
        for conflict in conflicts:
            result.resolution_actions.append(f"Manual resolution required for {conflict.field_path}")
        
        return result


class ConflictWorkflowManager:
    """
    Manages conflict resolution workflows.
    """
    
    def __init__(self, fabric: HedgehogFabric):
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
    
    def process_conflicts(self, resource: HedgehogResource, 
                         resolution_strategy: str = 'manual') -> ConflictResolutionResult:
        """Process conflicts for a single resource"""
        try:
            # Analyze conflicts
            analyzer = ConflictAnalyzer(resource)
            conflicts = analyzer.analyze_conflicts()
            
            # Resolve conflicts
            resolver = ConflictResolver(resource)
            result = resolver.resolve_conflicts(conflicts, resolution_strategy)
            
            # Create alerts for unresolved conflicts
            self._create_conflict_alerts(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Conflict processing failed for {resource.name}: {e}")
            raise
    
    def _create_conflict_alerts(self, result: ConflictResolutionResult):
        """Create alerts for unresolved conflicts"""
        unresolved_conflicts = [
            c for c in result.conflicts_detected 
            if c not in result.conflicts_resolved
        ]
        
        if not unresolved_conflicts:
            return
        
        try:
            # Check if alert already exists
            existing_alert = ReconciliationAlert.objects.filter(
                fabric=self.fabric,
                resource=result.resource,
                alert_type='conflict_detected',
                status__in=[AlertStatusChoices.ACTIVE, AlertStatusChoices.ACKNOWLEDGED]
            ).first()
            
            if existing_alert:
                # Update existing alert
                existing_alert.message = f"Resource has {len(unresolved_conflicts)} unresolved conflicts"
                existing_alert.drift_details = {
                    'conflicts': [
                        {
                            'type': c.conflict_type.value,
                            'field': c.field_path,
                            'severity': c.severity,
                            'description': c.description
                        } for c in unresolved_conflicts
                    ]
                }
                existing_alert.save()
                self.logger.debug(f"Updated existing conflict alert for {result.resource.name}")
            else:
                # Create new alert
                severity = max(
                    [c.severity for c in unresolved_conflicts],
                    key=lambda s: ['low', 'medium', 'high', 'critical'].index(s)
                )
                
                alert = ReconciliationAlert.objects.create(
                    fabric=self.fabric,
                    resource=result.resource,
                    alert_type='conflict_detected',
                    severity=severity,
                    title=f"Conflicts detected: {result.resource.kind}/{result.resource.name}",
                    message=f"Resource has {len(unresolved_conflicts)} unresolved conflicts requiring manual resolution",
                    alert_context={
                        'conflicts_count': len(unresolved_conflicts),
                        'resource_kind': result.resource.kind,
                        'resource_name': result.resource.name
                    },
                    drift_details={
                        'conflicts': [
                            {
                                'type': c.conflict_type.value,
                                'field': c.field_path,
                                'severity': c.severity,
                                'description': c.description,
                                'git_value': str(c.git_value),
                                'cluster_value': str(c.cluster_value),
                                'resolution_options': c.resolution_options
                            } for c in unresolved_conflicts
                        ]
                    },
                    suggested_action=ResolutionActionChoices.MANUAL_REVIEW
                )
                
                self.logger.info(f"Created conflict alert for {result.resource.name}")
                
        except Exception as e:
            self.logger.error(f"Failed to create conflict alert for {result.resource.name}: {e}")
    
    def process_fabric_conflicts(self, resolution_strategy: str = 'manual') -> Dict:
        """Process conflicts for all resources in the fabric"""
        results = {
            'processed_resources': 0,
            'total_conflicts': 0,
            'resolved_conflicts': 0,
            'alerts_created': 0,
            'errors': [],
            'resource_results': {}
        }
        
        # Get resources with potential conflicts
        resources = HedgehogResource.objects.filter(
            fabric=self.fabric,
            drift_status__in=['spec_drift', 'desired_only', 'actual_only']
        )
        
        for resource in resources:
            try:
                result = self.process_conflicts(resource, resolution_strategy)
                
                results['processed_resources'] += 1
                results['total_conflicts'] += len(result.conflicts_detected)
                results['resolved_conflicts'] += len(result.conflicts_resolved)
                
                results['resource_results'][resource.name] = {
                    'conflicts_detected': len(result.conflicts_detected),
                    'conflicts_resolved': len(result.conflicts_resolved),
                    'success': result.success,
                    'actions': result.resolution_actions
                }
                
            except Exception as e:
                error_msg = f"Failed to process conflicts for {resource.name}: {e}"
                results['errors'].append(error_msg)
                self.logger.error(error_msg)
        
        return results
    
    def get_conflict_summary(self) -> Dict:
        """Get summary of conflicts in the fabric"""
        conflicts_query = ReconciliationAlert.objects.filter(
            fabric=self.fabric,
            alert_type='conflict_detected',
            status__in=[AlertStatusChoices.ACTIVE, AlertStatusChoices.ACKNOWLEDGED]
        )
        
        summary = {
            'total_conflicts': conflicts_query.count(),
            'by_severity': {},
            'by_resource_kind': {},
            'recent_conflicts': []
        }
        
        # Group by severity
        for severity in AlertSeverityChoices.CHOICES:
            summary['by_severity'][severity[0]] = conflicts_query.filter(severity=severity[0]).count()
        
        # Group by resource kind
        for alert in conflicts_query:
            kind = alert.resource.kind
            summary['by_resource_kind'][kind] = summary['by_resource_kind'].get(kind, 0) + 1
        
        # Get recent conflicts
        recent = conflicts_query.order_by('-created')[:10]
        summary['recent_conflicts'] = [
            {
                'resource': f"{alert.resource.kind}/{alert.resource.name}",
                'severity': alert.severity,
                'created': alert.created.isoformat(),
                'message': alert.message
            } for alert in recent
        ]
        
        return summary