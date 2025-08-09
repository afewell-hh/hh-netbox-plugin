"""
Integration Coordinator Service
Coordinates integration between all Phase 3 components to ensure consistency
and proper workflow orchestration across the GitOps File Management System.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)


class IntegrationCoordinator:
    """
    Service for coordinating integration between Phase 3 components.
    
    Responsibilities:
    1. Ensure consistency across file operations, conflict resolution, and template generation
    2. Coordinate workflow sequences and dependencies
    3. Validate integration integrity
    4. Handle cross-component communication
    5. Provide unified error handling and recovery
    """
    
    def __init__(self):
        self.coordination_events = []
        self.active_workflows = {}
        self.component_statuses = {}
        
    def coordinate_phase3_integration(self, coordination_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Coordinate integration across all Phase 3 components.
        
        Args:
            coordination_data: Dict containing fabric, components, and ingestion results
            
        Returns:
            Dict with coordination results
        """
        start_time = timezone.now()
        
        result = {
            'events_processed': 0,
            'successful_coordinations': 0,
            'coordination_errors': 0,
            'validation_results': {},
            'recommendations': []
        }
        
        try:
            fabric = coordination_data.get('fabric')
            components = coordination_data.get('components', {})
            ingestion_result = coordination_data.get('ingestion_result', {})
            
            logger.info(f"🎯 Starting Phase 3 integration coordination for fabric {fabric.name if fabric else 'unknown'}")
            
            # Validate component availability
            validation_result = self._validate_component_availability(components)
            result['validation_results']['component_availability'] = validation_result
            result['events_processed'] += 1
            
            if validation_result['all_available']:
                result['successful_coordinations'] += 1
            else:
                result['coordination_errors'] += 1
                result['recommendations'].append("Some Phase 3 components are not available")
            
            # Validate integration consistency
            consistency_result = self._validate_integration_consistency(ingestion_result)
            result['validation_results']['integration_consistency'] = consistency_result
            result['events_processed'] += 1
            
            if consistency_result['consistent']:
                result['successful_coordinations'] += 1
            else:
                result['coordination_errors'] += 1
                result['recommendations'].extend(consistency_result.get('issues', []))
            
            # Generate integration recommendations
            recommendations = self._generate_integration_recommendations(coordination_data)
            result['recommendations'].extend(recommendations)
            result['events_processed'] += 1
            result['successful_coordinations'] += 1
            
            # Record coordination event
            self._record_coordination_event({
                'fabric_name': fabric.name if fabric else 'unknown',
                'timestamp': start_time,
                'duration': (timezone.now() - start_time).total_seconds(),
                'result': result,
                'success': result['coordination_errors'] == 0
            })
            
            logger.info(f"✅ Phase 3 integration coordination completed: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Phase 3 integration coordination failed: {str(e)}")
            result['coordination_errors'] += 1
            result['recommendations'].append(f"Coordination failed: {str(e)}")
            return result
    
    def _validate_component_availability(self, components: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that all required Phase 3 components are available."""
        required_components = ['file_manager', 'conflict_resolver', 'template_engine']
        available_components = []
        missing_components = []
        
        for component_name in required_components:
            component = components.get(component_name)
            if component is not None:
                available_components.append(component_name)
                logger.debug(f"✅ Component {component_name} is available")
            else:
                missing_components.append(component_name)
                logger.warning(f"⚠️  Component {component_name} is missing")
        
        return {
            'all_available': len(missing_components) == 0,
            'available_components': available_components,
            'missing_components': missing_components,
            'availability_ratio': len(available_components) / len(required_components)
        }
    
    def _validate_integration_consistency(self, ingestion_result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate consistency across integration results."""
        issues = []
        warnings = []
        
        try:
            phase3_data = ingestion_result.get('phase3_integration', {})
            
            # Check file operations consistency
            file_ops = phase3_data.get('file_operations', {})
            if file_ops.get('operations_failed', 0) > 0:
                issues.append(f"File operations had {file_ops.get('operations_failed', 0)} failures")
            
            # Check conflict resolution consistency
            conflicts = phase3_data.get('conflict_resolution', {})
            manual_review_count = conflicts.get('conflicts_requiring_manual_review', 0)
            if manual_review_count > 0:
                warnings.append(f"{manual_review_count} conflicts require manual review")
            
            # Check template generation consistency
            templates = phase3_data.get('template_generation', {})
            validation_errors = templates.get('template_validation_errors', 0)
            if validation_errors > 0:
                issues.append(f"Template generation had {validation_errors} validation errors")
            
            # Check performance consistency
            perf_data = ingestion_result.get('performance_metrics', {})
            total_time = perf_data.get('total_execution_time', 0)
            if total_time > 30:  # 30 second micro-task boundary
                warnings.append(f"Total execution time ({total_time:.2f}s) exceeds micro-task boundary")
            
            return {
                'consistent': len(issues) == 0,
                'issues': issues,
                'warnings': warnings,
                'validation_score': 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
            }
            
        except Exception as e:
            logger.error(f"Consistency validation failed: {str(e)}")
            return {
                'consistent': False,
                'issues': [f"Validation error: {str(e)}"],
                'warnings': [],
                'validation_score': 0.0
            }
    
    def _generate_integration_recommendations(self, coordination_data: Dict[str, Any]) -> List[str]:
        """Generate recommendations for improving integration."""
        recommendations = []
        
        try:
            ingestion_result = coordination_data.get('ingestion_result', {})
            components = coordination_data.get('components', {})
            
            # Performance recommendations
            perf_data = ingestion_result.get('performance_metrics', {})
            total_time = perf_data.get('total_execution_time', 0)
            
            if total_time > 25:
                recommendations.append("Consider optimizing slow operations to stay within micro-task boundary")
            
            file_ops_time = perf_data.get('file_operations_time', 0)
            if file_ops_time > total_time * 0.5:
                recommendations.append("File operations are taking significant time - consider optimization")
            
            # Conflict resolution recommendations
            phase3_data = ingestion_result.get('phase3_integration', {})
            conflicts = phase3_data.get('conflict_resolution', {})
            
            if conflicts.get('conflicts_detected', 0) > 5:
                recommendations.append("High number of conflicts detected - consider improving source file quality")
            
            if conflicts.get('conflicts_requiring_manual_review', 0) > 0:
                recommendations.append("Some conflicts require manual review - check conflict resolution rules")
            
            # Template generation recommendations
            templates = phase3_data.get('template_generation', {})
            if templates.get('template_validation_errors', 0) > 0:
                recommendations.append("Template validation errors found - review template schemas and data quality")
            
            # Integration health recommendations
            if not recommendations:
                recommendations.append("Integration is healthy - all Phase 3 components operating normally")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {str(e)}")
            return [f"Error generating recommendations: {str(e)}"]
    
    def _record_coordination_event(self, event: Dict[str, Any]):
        """Record a coordination event for audit and analysis."""
        try:
            self.coordination_events.append(event)
            
            # Keep only recent events (last 100)
            if len(self.coordination_events) > 100:
                self.coordination_events = self.coordination_events[-50:]
            
            logger.debug(f"Recorded coordination event: {event['fabric_name']} - {event['success']}")
            
        except Exception as e:
            logger.error(f"Failed to record coordination event: {str(e)}")
    
    def get_coordination_status(self) -> Dict[str, Any]:
        """Get current coordination status and metrics."""
        try:
            recent_events = self.coordination_events[-10:] if self.coordination_events else []
            
            successful_events = [e for e in recent_events if e.get('success', False)]
            failed_events = [e for e in recent_events if not e.get('success', True)]
            
            return {
                'total_events': len(self.coordination_events),
                'recent_events': len(recent_events),
                'success_rate': len(successful_events) / max(len(recent_events), 1),
                'average_duration': sum(e.get('duration', 0) for e in recent_events) / max(len(recent_events), 1),
                'active_workflows': len(self.active_workflows),
                'component_statuses': self.component_statuses,
                'last_event': recent_events[-1] if recent_events else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get coordination status: {str(e)}")
            return {
                'error': str(e),
                'total_events': 0,
                'success_rate': 0.0
            }
    
    def register_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> bool:
        """Register a new workflow for coordination tracking."""
        try:
            self.active_workflows[workflow_id] = {
                'started_at': timezone.now(),
                'data': workflow_data,
                'status': 'active'
            }
            
            logger.info(f"Registered workflow: {workflow_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register workflow {workflow_id}: {str(e)}")
            return False
    
    def complete_workflow(self, workflow_id: str, result: Dict[str, Any]) -> bool:
        """Mark a workflow as completed."""
        try:
            if workflow_id in self.active_workflows:
                self.active_workflows[workflow_id]['status'] = 'completed'
                self.active_workflows[workflow_id]['completed_at'] = timezone.now()
                self.active_workflows[workflow_id]['result'] = result
                
                logger.info(f"Completed workflow: {workflow_id}")
                return True
            else:
                logger.warning(f"Workflow not found for completion: {workflow_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to complete workflow {workflow_id}: {str(e)}")
            return False
    
    def cleanup_completed_workflows(self, max_age_hours: int = 24):
        """Clean up old completed workflows."""
        try:
            cutoff_time = timezone.now() - timezone.timedelta(hours=max_age_hours)
            workflows_to_remove = []
            
            for workflow_id, workflow_data in self.active_workflows.items():
                if (workflow_data.get('status') == 'completed' and 
                    workflow_data.get('completed_at', timezone.now()) < cutoff_time):
                    workflows_to_remove.append(workflow_id)
            
            for workflow_id in workflows_to_remove:
                del self.active_workflows[workflow_id]
            
            if workflows_to_remove:
                logger.info(f"Cleaned up {len(workflows_to_remove)} old workflows")
            
            return len(workflows_to_remove)
            
        except Exception as e:
            logger.error(f"Failed to cleanup workflows: {str(e)}")
            return 0