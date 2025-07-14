"""
Multi-Environment API Endpoints and UI Data Structures.

This module provides API endpoints and data structures specifically designed
for the Frontend Agent to build rich multi-environment GitOps interfaces.

Author: Git Operations Agent
Date: July 10, 2025
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import get_object_or_404

from ..models.fabric import HedgehogFabric
from .environment_manager import EnvironmentManager, EnvironmentManagerError

logger = logging.getLogger(__name__)


class EnvironmentAPIError(Exception):
    """Base exception for Environment API operations."""
    pass


class EnvironmentAPIView(View):
    """Base view for environment API endpoints."""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        """Handle CSRF exemption for API endpoints."""
        return super().dispatch(request, *args, **kwargs)
    
    def get_fabric(self, fabric_id: int) -> HedgehogFabric:
        """Get fabric instance with error handling."""
        try:
            return get_object_or_404(HedgehogFabric, pk=fabric_id)
        except Exception as e:
            logger.error(f"Failed to get fabric {fabric_id}: {e}")
            raise EnvironmentAPIError(f"Fabric not found: {fabric_id}")
    
    def create_error_response(self, message: str, status_code: int = 400) -> JsonResponse:
        """Create standardized error response."""
        return JsonResponse({
            'error': message,
            'timestamp': datetime.now().isoformat()
        }, status=status_code)
    
    def create_success_response(self, data: Dict[str, Any]) -> JsonResponse:
        """Create standardized success response."""
        response_data = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            **data
        }
        return JsonResponse(response_data)


class EnvironmentListView(EnvironmentAPIView):
    """API endpoint for listing environments."""
    
    def get(self, request, fabric_id: int):
        """
        Get list of environments for a fabric.
        
        Returns:
            JSON response with environment list and configurations
        """
        try:
            fabric = self.get_fabric(fabric_id)
            manager = EnvironmentManager(fabric)
            
            environments_data = {
                'environments': [],
                'fabric': {
                    'id': fabric.pk,
                    'name': fabric.name,
                    'repository_url': fabric.git_repository_url,
                    'primary_branch': fabric.git_branch or 'main'
                }
            }
            
            for env_name in manager.list_environments():
                config = manager.get_environment_config(env_name)
                if config:
                    env_data = {
                        'name': config.name,
                        'type': config.env_type.value,
                        'branch': config.branch,
                        'priority': config.priority,
                        'auto_sync': config.auto_sync,
                        'require_approval': config.require_approval,
                        'max_drift_threshold': config.max_drift_threshold,
                        'promotion_target': config.promotion_target
                    }
                    environments_data['environments'].append(env_data)
            
            return self.create_success_response(environments_data)
            
        except EnvironmentAPIError as e:
            return self.create_error_response(str(e))
        except Exception as e:
            logger.error(f"Environment list error for fabric {fabric_id}: {e}")
            return self.create_error_response("Internal server error", 500)


class EnvironmentHealthView(EnvironmentAPIView):
    """API endpoint for environment health status."""
    
    async def get_async(self, request, fabric_id: int, environment: str = None):
        """Get environment health data asynchronously."""
        try:
            fabric = self.get_fabric(fabric_id)
            manager = EnvironmentManager(fabric)
            
            if environment:
                # Get health for specific environment
                health = await manager.get_environment_health(environment)
                if not health:
                    return self.create_error_response(f"Environment '{environment}' not found", 404)
                
                return self.create_success_response({
                    'environment': health.to_dict()
                })
            else:
                # Get health for all environments
                health_data = await manager.get_all_environment_health()
                
                return self.create_success_response({
                    'environments': {
                        name: health.to_dict() 
                        for name, health in health_data.items()
                    }
                })
                
        except EnvironmentAPIError as e:
            return self.create_error_response(str(e))
        except Exception as e:
            logger.error(f"Environment health error: {e}")
            return self.create_error_response("Internal server error", 500)
    
    def get(self, request, fabric_id: int, environment: str = None):
        """Synchronous wrapper for async health endpoint."""
        return asyncio.run(self.get_async(request, fabric_id, environment))


class BranchComparisonView(EnvironmentAPIView):
    """API endpoint for branch comparisons."""
    
    async def get_async(self, request, fabric_id: int):
        """Get branch comparison data asynchronously."""
        try:
            fabric = self.get_fabric(fabric_id)
            manager = EnvironmentManager(fabric)
            
            base_env = request.GET.get('base')
            head_env = request.GET.get('head')
            force_refresh = request.GET.get('refresh', 'false').lower() == 'true'
            
            if not base_env or not head_env:
                return self.create_error_response("Both 'base' and 'head' parameters are required")
            
            comparison = await manager.compare_environment_branches(
                base_env, head_env, force_refresh
            )
            
            if not comparison:
                return self.create_error_response(f"Failed to compare {base_env} and {head_env}")
            
            return self.create_success_response({
                'comparison': comparison.to_dict()
            })
            
        except EnvironmentAPIError as e:
            return self.create_error_response(str(e))
        except Exception as e:
            logger.error(f"Branch comparison error: {e}")
            return self.create_error_response("Internal server error", 500)
    
    def get(self, request, fabric_id: int):
        """Synchronous wrapper for async comparison endpoint."""
        return asyncio.run(self.get_async(request, fabric_id))


class DriftDetectionView(EnvironmentAPIView):
    """API endpoint for cross-environment drift detection."""
    
    async def get_async(self, request, fabric_id: int):
        """Get drift detection results asynchronously."""
        try:
            fabric = self.get_fabric(fabric_id)
            manager = EnvironmentManager(fabric)
            
            drift_results = await manager.detect_cross_environment_drift()
            
            return self.create_success_response({
                'drift_detection': drift_results
            })
            
        except EnvironmentAPIError as e:
            return self.create_error_response(str(e))
        except Exception as e:
            logger.error(f"Drift detection error: {e}")
            return self.create_error_response("Internal server error", 500)
    
    def get(self, request, fabric_id: int):
        """Synchronous wrapper for async drift detection endpoint."""
        return asyncio.run(self.get_async(request, fabric_id))


class PromotionPlanView(EnvironmentAPIView):
    """API endpoint for promotion planning."""
    
    async def get_async(self, request, fabric_id: int):
        """Get promotion plan asynchronously."""
        try:
            fabric = self.get_fabric(fabric_id)
            manager = EnvironmentManager(fabric)
            
            source_env = request.GET.get('source')
            target_env = request.GET.get('target')
            
            if not source_env or not target_env:
                return self.create_error_response("Both 'source' and 'target' parameters are required")
            
            promotion_plan = await manager.create_promotion_plan(source_env, target_env)
            
            if not promotion_plan:
                return self.create_error_response(f"Failed to create promotion plan from {source_env} to {target_env}")
            
            return self.create_success_response({
                'promotion_plan': promotion_plan.to_dict()
            })
            
        except EnvironmentAPIError as e:
            return self.create_error_response(str(e))
        except Exception as e:
            logger.error(f"Promotion plan error: {e}")
            return self.create_error_response("Internal server error", 500)
    
    def get(self, request, fabric_id: int):
        """Synchronous wrapper for async promotion plan endpoint."""
        return asyncio.run(self.get_async(request, fabric_id))


class PipelineStatusView(EnvironmentAPIView):
    """API endpoint for pipeline status."""
    
    async def get_async(self, request, fabric_id: int):
        """Get pipeline status asynchronously."""
        try:
            fabric = self.get_fabric(fabric_id)
            manager = EnvironmentManager(fabric)
            
            pipeline_status = await manager.get_promotion_pipeline_status()
            
            return self.create_success_response({
                'pipeline': pipeline_status
            })
            
        except EnvironmentAPIError as e:
            return self.create_error_response(str(e))
        except Exception as e:
            logger.error(f"Pipeline status error: {e}")
            return self.create_error_response("Internal server error", 500)
    
    def get(self, request, fabric_id: int):
        """Synchronous wrapper for async pipeline status endpoint."""
        return asyncio.run(self.get_async(request, fabric_id))


class FrontendDataView(EnvironmentAPIView):
    """API endpoint for comprehensive Frontend Agent data."""
    
    async def get_async(self, request, fabric_id: int):
        """Get comprehensive frontend data asynchronously."""
        try:
            fabric = self.get_fabric(fabric_id)
            manager = EnvironmentManager(fabric)
            
            frontend_data = await manager.get_frontend_data()
            
            return self.create_success_response({
                'frontend_data': frontend_data
            })
            
        except EnvironmentAPIError as e:
            return self.create_error_response(str(e))
        except Exception as e:
            logger.error(f"Frontend data error: {e}")
            return self.create_error_response("Internal server error", 500)
    
    def get(self, request, fabric_id: int):
        """Synchronous wrapper for async frontend data endpoint."""
        return asyncio.run(self.get_async(request, fabric_id))


# UI Data Structure Generators

class UIDataGenerator:
    """Generates UI-specific data structures for Frontend Agent."""
    
    @staticmethod
    def generate_environment_dashboard_data(
        environments: Dict[str, Any],
        comparisons: Dict[str, Any],
        pipeline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate dashboard data for environment overview.
        
        Args:
            environments: Environment health data
            comparisons: Branch comparison data
            pipeline: Pipeline status data
            
        Returns:
            Dashboard-specific data structure
        """
        dashboard_data = {
            'overview': {
                'total_environments': len(environments),
                'healthy_environments': 0,
                'critical_environments': 0,
                'pending_promotions': len(pipeline.get('next_promotions', [])),
                'blocked_promotions': len(pipeline.get('blocked_promotions', []))
            },
            'environment_cards': [],
            'promotion_flow': [],
            'alerts': []
        }
        
        # Process environment cards
        for env_name, env_data in environments.items():
            health_score = env_data.get('health_score', 0)
            status = env_data.get('status', 'unknown')
            
            if status == 'healthy':
                dashboard_data['overview']['healthy_environments'] += 1
            elif status in ['error', 'drift_detected']:
                dashboard_data['overview']['critical_environments'] += 1
            
            card_data = {
                'name': env_name,
                'status': status,
                'health_score': health_score,
                'resource_count': env_data.get('resource_count', 0),
                'drift_count': env_data.get('drift_count', 0),
                'last_sync': env_data.get('last_sync'),
                'branch': env_data.get('branch'),
                'badge_color': UIDataGenerator._get_status_color(status),
                'icon': UIDataGenerator._get_environment_icon(env_name)
            }
            dashboard_data['environment_cards'].append(card_data)
        
        # Process promotion flow
        promotion_order = ['development', 'staging', 'production']
        for i, env_name in enumerate(promotion_order):
            if env_name in environments:
                flow_item = {
                    'environment': env_name,
                    'status': environments[env_name].get('status', 'unknown'),
                    'position': i,
                    'is_last': i == len(promotion_order) - 1
                }
                
                # Add connection to next environment
                if not flow_item['is_last'] and i + 1 < len(promotion_order):
                    next_env = promotion_order[i + 1]
                    comparison_key = f"{env_name}_to_{next_env}"
                    
                    if comparison_key in comparisons:
                        comp_data = comparisons[comparison_key]
                        flow_item['connection'] = {
                            'ahead_by': comp_data.get('ahead_by', 0),
                            'behind_by': comp_data.get('behind_by', 0),
                            'status': comp_data.get('status', 'unknown'),
                            'can_promote': comp_data.get('ahead_by', 0) > 0
                        }
                
                dashboard_data['promotion_flow'].append(flow_item)
        
        # Generate alerts
        dashboard_data['alerts'] = UIDataGenerator._generate_alerts(
            environments, comparisons, pipeline
        )
        
        return dashboard_data
    
    @staticmethod
    def generate_environment_detail_data(
        environment: str,
        env_data: Dict[str, Any],
        related_comparisons: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate detailed view data for a specific environment.
        
        Args:
            environment: Environment name
            env_data: Environment health data
            related_comparisons: Comparisons involving this environment
            
        Returns:
            Environment detail data structure
        """
        detail_data = {
            'environment': {
                'name': environment,
                'status': env_data.get('status', 'unknown'),
                'health_score': env_data.get('health_score', 0),
                'branch': env_data.get('branch'),
                'last_sync': env_data.get('last_sync'),
                'resource_count': env_data.get('resource_count', 0),
                'drift_count': env_data.get('drift_count', 0),
                'error_count': env_data.get('error_count', 0)
            },
            'metrics': {
                'sync_frequency': UIDataGenerator._calculate_sync_frequency(env_data),
                'drift_trend': UIDataGenerator._calculate_drift_trend(env_data),
                'uptime': UIDataGenerator._calculate_uptime(env_data)
            },
            'recent_activity': [],
            'branch_comparisons': related_comparisons,
            'recommendations': UIDataGenerator._generate_recommendations(env_data)
        }
        
        return detail_data
    
    @staticmethod
    def generate_promotion_workflow_data(
        promotion_plans: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate promotion workflow UI data.
        
        Args:
            promotion_plans: Promotion plan data
            
        Returns:
            Promotion workflow data structure
        """
        workflow_data = {
            'active_promotions': [],
            'pending_approvals': [],
            'completed_promotions': [],
            'workflow_status': 'idle'
        }
        
        for plan_key, plan_data in promotion_plans.items():
            promotion_item = {
                'id': plan_key,
                'source': plan_data.get('source_env'),
                'target': plan_data.get('target_env'),
                'status': plan_data.get('status'),
                'resources_count': len(plan_data.get('resources_to_promote', [])),
                'conflicts_count': len(plan_data.get('conflicts', [])),
                'approvals_required': plan_data.get('approvals_required', []),
                'estimated_duration': plan_data.get('estimated_duration'),
                'risk_assessment': plan_data.get('risk_assessment'),
                'created_at': plan_data.get('created_at'),
                'can_proceed': plan_data.get('promotion_ready', False)
            }
            
            status = plan_data.get('status', 'unknown')
            if status == 'in_progress':
                workflow_data['active_promotions'].append(promotion_item)
                workflow_data['workflow_status'] = 'active'
            elif status == 'blocked':
                if promotion_item['approvals_required']:
                    workflow_data['pending_approvals'].append(promotion_item)
                else:
                    workflow_data['active_promotions'].append(promotion_item)
            elif status == 'completed':
                workflow_data['completed_promotions'].append(promotion_item)
        
        return workflow_data
    
    @staticmethod
    def _get_status_color(status: str) -> str:
        """Get color for environment status."""
        color_map = {
            'healthy': 'green',
            'sync_needed': 'yellow',
            'drift_detected': 'orange',
            'error': 'red',
            'unknown': 'gray'
        }
        return color_map.get(status, 'gray')
    
    @staticmethod
    def _get_environment_icon(env_name: str) -> str:
        """Get icon for environment type."""
        icon_map = {
            'development': 'code',
            'staging': 'test-tube',
            'production': 'server',
            'feature': 'git-branch',
            'hotfix': 'fire'
        }
        return icon_map.get(env_name, 'circle')
    
    @staticmethod
    def _generate_alerts(
        environments: Dict[str, Any],
        comparisons: Dict[str, Any],
        pipeline: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate alerts for dashboard."""
        alerts = []
        
        # Check for environments with high drift
        for env_name, env_data in environments.items():
            drift_count = env_data.get('drift_count', 0)
            if drift_count > 5:
                alerts.append({
                    'type': 'warning',
                    'title': f'High drift in {env_name}',
                    'message': f'{drift_count} resources out of sync',
                    'action': f'sync_{env_name}',
                    'severity': 'medium'
                })
        
        # Check for blocked promotions
        blocked_promotions = pipeline.get('blocked_promotions', [])
        if blocked_promotions:
            alerts.append({
                'type': 'info',
                'title': 'Promotions blocked',
                'message': f'{len(blocked_promotions)} promotions require attention',
                'action': 'review_promotions',
                'severity': 'low'
            })
        
        return alerts
    
    @staticmethod
    def _calculate_sync_frequency(env_data: Dict[str, Any]) -> str:
        """Calculate sync frequency description."""
        last_sync = env_data.get('last_sync')
        if not last_sync:
            return 'Never synced'
        
        # This would calculate based on sync history
        return 'Daily'  # Placeholder
    
    @staticmethod
    def _calculate_drift_trend(env_data: Dict[str, Any]) -> str:
        """Calculate drift trend."""
        drift_count = env_data.get('drift_count', 0)
        if drift_count == 0:
            return 'stable'
        elif drift_count < 3:
            return 'improving'
        else:
            return 'increasing'
    
    @staticmethod
    def _calculate_uptime(env_data: Dict[str, Any]) -> float:
        """Calculate environment uptime percentage."""
        status = env_data.get('status', 'unknown')
        if status == 'healthy':
            return 99.9
        elif status in ['sync_needed', 'drift_detected']:
            return 95.0
        else:
            return 80.0
    
    @staticmethod
    def _generate_recommendations(env_data: Dict[str, Any]) -> List[str]:
        """Generate recommendations for environment."""
        recommendations = []
        
        drift_count = env_data.get('drift_count', 0)
        error_count = env_data.get('error_count', 0)
        
        if drift_count > 3:
            recommendations.append('Consider running a manual sync to reduce drift')
        
        if error_count > 0:
            recommendations.append('Review and resolve configuration errors')
        
        last_sync = env_data.get('last_sync')
        if not last_sync:
            recommendations.append('Enable automatic syncing for this environment')
        
        return recommendations