"""
Drift Detection Dashboard View
Provides comprehensive drift analysis interface with industry-aligned drift definition
"""

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Avg
import logging

from ..models import HedgehogFabric, HedgehogResource

# Lazy import to avoid circular dependency during URL loading
# from ..utils.drift_detection import DriftAnalyzer, analyze_fabric_drift

logger = logging.getLogger(__name__)

# Import debugging removed - HedgehogResource import is now direct and reliable


class DriftDetectionDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main drift detection dashboard showing all drifted resources across fabrics
    """
    template_name = 'netbox_hedgehog/drift_detection_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        fabric_filter = self.request.GET.get('fabric')
        severity_filter = self.request.GET.get('severity')
        resource_type_filter = self.request.GET.get('resource_type')
        
        try:
            # Get all fabrics for filter dropdown
            context['all_fabrics'] = HedgehogFabric.objects.all().order_by('name')
            
            # HedgehogResource model always exists now - removed placeholder fallback
            
            # Build base queryset for drifted resources
            resources_query = HedgehogResource.objects.exclude(
                drift_status='in_sync'
            ).select_related('fabric')
            
            # Apply filters
            if fabric_filter:
                try:
                    fabric = HedgehogFabric.objects.get(pk=fabric_filter)
                    resources_query = resources_query.filter(fabric=fabric)
                    context['selected_fabric'] = fabric
                except HedgehogFabric.DoesNotExist:
                    pass
            
            if severity_filter:
                # Filter by severity based on drift score
                if severity_filter == 'critical':
                    resources_query = resources_query.filter(drift_score__gte=0.8)
                elif severity_filter == 'high':
                    resources_query = resources_query.filter(drift_score__gte=0.6, drift_score__lt=0.8)
                elif severity_filter == 'medium':
                    resources_query = resources_query.filter(drift_score__gte=0.3, drift_score__lt=0.6)
                elif severity_filter == 'low':
                    resources_query = resources_query.filter(drift_score__lt=0.3)
                context['selected_severity'] = severity_filter
            
            if resource_type_filter:
                resources_query = resources_query.filter(kind=resource_type_filter)
                context['selected_resource_type'] = resource_type_filter
            
            # Get drifted resources with pagination
            drifted_resources = resources_query.order_by('-drift_score', '-last_drift_check')[:100]
            
            # Process resources for display
            processed_resources = []
            for resource in drifted_resources:
                # Determine severity from drift score
                if resource.drift_score >= 0.8:
                    severity = 'critical'
                    severity_class = 'danger'
                elif resource.drift_score >= 0.6:
                    severity = 'high'
                    severity_class = 'warning'
                elif resource.drift_score >= 0.3:
                    severity = 'medium'  
                    severity_class = 'info'
                else:
                    severity = 'low'
                    severity_class = 'secondary'
                
                # Extract drift summary from details
                drift_summary = 'Configuration drift detected'
                if resource.drift_details and isinstance(resource.drift_details, dict):
                    drift_summary = resource.drift_details.get('summary', drift_summary)
                
                processed_resources.append({
                    'resource': resource,
                    'severity': severity,
                    'severity_class': severity_class,
                    'drift_summary': drift_summary,
                    'can_sync': resource.fabric and hasattr(resource.fabric, 'git_repository_url') and resource.fabric.git_repository_url,
                })
            
            context['drifted_resources'] = processed_resources
            
            # Calculate dashboard statistics
            total_resources = HedgehogResource.objects.count()
            drifted_count = HedgehogResource.objects.exclude(drift_status='in_sync').count()
            critical_drift_count = HedgehogResource.objects.filter(drift_score__gte=0.8).count()
            
            context['dashboard_stats'] = {
                'total_resources': total_resources,
                'drifted_count': drifted_count,
                'in_sync_count': total_resources - drifted_count,
                'critical_drift_count': critical_drift_count,
                'drift_percentage': (drifted_count / total_resources * 100) if total_resources > 0 else 0
            }
            
            # Get unique resource types for filter
            context['resource_types'] = HedgehogResource.objects.values_list('kind', flat=True).distinct().order_by('kind')
            
            # Filter options for template
            context['severity_options'] = [
                ('critical', 'Critical (≥80%)'),
                ('high', 'High (60-79%)'),
                ('medium', 'Medium (30-59%)'),
                ('low', 'Low (<30%)')
            ]
            
            # Add context for breadcrumbs and navigation
            context['page_title'] = 'Drift Detection Dashboard'
            context['show_filters'] = True
            
        except Exception as e:
            logger.error(f"Drift dashboard context error: {e}")
            context.update({
                'error': str(e),
                'drifted_resources': [],
                'dashboard_stats': {
                    'total_resources': 0,
                    'drifted_count': 0,
                    'in_sync_count': 0,
                    'critical_drift_count': 0,
                    'drift_percentage': 0
                }
            })
        
        return context

    def _get_placeholder_context(self):
        """DEPRECATED: Placeholder context method - no longer used since HedgehogResource always exists"""
        # Create demo data to show dashboard functionality
        demo_resources = [
            {
                'resource': type('', (), {
                    'id': 1,
                    'name': 'demo-vpc-001',
                    'kind': 'VPC',
                    'namespace': 'default',
                    'drift_score': 0.85,
                    'last_drift_check': timezone.now(),
                    'fabric': type('', (), {'name': 'Demo Fabric', 'id': 1})()
                })(),
                'severity': 'critical',
                'severity_class': 'danger',
                'drift_summary': 'Spec differences detected in network configuration',
                'can_sync': True
            },
            {
                'resource': type('', (), {
                    'id': 2,
                    'name': 'demo-switch-001',
                    'kind': 'Switch',
                    'namespace': 'default',
                    'drift_score': 0.45,
                    'last_drift_check': timezone.now(),
                    'fabric': type('', (), {'name': 'Demo Fabric', 'id': 1})()
                })(),
                'severity': 'medium',
                'severity_class': 'info',
                'drift_summary': 'Port configuration drift detected',
                'can_sync': True
            }
        ]
        
        return {
            'drifted_resources': demo_resources,
            'dashboard_stats': {
                'total_resources': 25,
                'drifted_count': 2,
                'in_sync_count': 23,
                'critical_drift_count': 1,
                'drift_percentage': 8.0
            },
            'resource_types': ['VPC', 'Switch', 'Connection', 'Server'],
            'severity_options': [
                ('critical', 'Critical (≥80%)'),
                ('high', 'High (60-79%)'),
                ('medium', 'Medium (30-59%)'),
                ('low', 'Low (<30%)')
            ],
            'page_title': 'Drift Detection Dashboard',
            'show_filters': True
        }


class FabricDriftDetailView(LoginRequiredMixin, TemplateView):
    """
    Detailed drift view for a specific fabric
    """
    template_name = 'netbox_hedgehog/fabric_drift_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fabric_id = kwargs.get('fabric_id')
        
        try:
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            context['fabric'] = fabric
            
            # Run drift analysis for this fabric
            try:
                from ..utils.drift_detection import analyze_fabric_drift
                drift_analysis = analyze_fabric_drift(fabric)
                context['drift_analysis'] = drift_analysis
            except ImportError:
                context['drift_analysis'] = {'error': 'Drift analysis module not available'}
            
            # HedgehogResource always exists - removed condition
                # Get detailed resource drift information
                resources = HedgehogResource.objects.filter(fabric=fabric)
                
                resource_details = []
                for resource in resources:
                    # Get or calculate latest drift information
                    if hasattr(resource, 'drift_details') and resource.drift_details:
                        drift_info = resource.drift_details
                    else:
                        # Calculate drift on-demand
                        try:
                            from ..utils.drift_detection import DriftAnalyzer
                            analyzer = DriftAnalyzer()
                            drift_info = analyzer._analyze_resource_drift(resource)
                        except ImportError:
                            drift_info = {'error': 'Drift analyzer not available', 'has_drift': False, 'drift_score': 0.0}
                    
                    resource_details.append({
                        'resource': resource,
                        'drift_info': drift_info,
                        'has_drift': drift_info.get('has_drift', False),
                        'drift_score': drift_info.get('drift_score', 0.0)
                    })
                
                context['resource_details'] = resource_details
            else:
                context['resource_details'] = []
            
            context['page_title'] = f'Drift Analysis - {fabric.name}'
            
        except Exception as e:
            logger.error(f"Fabric drift detail error: {e}")
            context['error'] = str(e)
        
        return context


class DriftAnalysisAPIView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for drift analysis data (JSON responses)
    """
    
    def get(self, request, *args, **kwargs):
        """Get drift analysis data as JSON"""
        try:
            fabric_id = request.GET.get('fabric_id')
            action = request.GET.get('action', 'summary')
            
            if action == 'summary':
                # Return dashboard summary data
                # HedgehogResource always exists - removed condition
                    total_resources = HedgehogResource.objects.count()
                    drifted_resources = HedgehogResource.objects.exclude(drift_status='in_sync')
                    
                    # Group by fabric
                    fabric_drift_data = []
                    for fabric in HedgehogFabric.objects.all():
                        fabric_resources = drifted_resources.filter(fabric=fabric)
                        fabric_drift_data.append({
                            'fabric_id': fabric.id,
                            'fabric_name': fabric.name,
                            'total_resources': HedgehogResource.objects.filter(fabric=fabric).count(),
                            'drifted_count': fabric_resources.count(),
                            'critical_count': fabric_resources.filter(drift_score__gte=0.8).count(),
                            'avg_drift_score': fabric_resources.aggregate(
                                avg_score=Avg('drift_score')
                            )['avg_score'] or 0.0
                        })
                    
                    return JsonResponse({
                        'success': True,
                        'summary': {
                            'total_resources': total_resources,
                            'drifted_count': drifted_resources.count(),
                            'in_sync_count': total_resources - drifted_resources.count(),
                            'critical_count': drifted_resources.filter(drift_score__gte=0.8).count()
                        },
                        'fabric_data': fabric_drift_data,
                        'timestamp': timezone.now().isoformat()
                    })
                # HedgehogResource always exists - removed demo data fallback
            
            elif action == 'fabric_detail' and fabric_id:
                # Return detailed fabric drift analysis
                fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
                try:
                    from ..utils.drift_detection import analyze_fabric_drift
                    drift_analysis = analyze_fabric_drift(fabric)
                except ImportError:
                    drift_analysis = {'error': 'Drift analysis module not available'}
                
                return JsonResponse({
                    'success': True,
                    'fabric_id': fabric.id,
                    'fabric_name': fabric.name,
                    'analysis': drift_analysis,
                    'timestamp': timezone.now().isoformat()
                })
            
            elif action == 'refresh_drift':
                # Trigger drift recalculation
                updated_count = 0
                
                # HedgehogResource always exists - removed condition
                resources = HedgehogResource.objects.all()
                
                if fabric_id:
                    fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
                    resources = resources.filter(fabric=fabric)
                    
                    try:
                        from ..utils.drift_detection import DriftAnalyzer
                        analyzer = DriftAnalyzer()
                        for resource in resources[:50]:  # Limit to prevent timeout
                            try:
                                analyzer._analyze_resource_drift(resource)
                                updated_count += 1
                            except Exception as e:
                                logger.error(f"Drift refresh failed for {resource}: {e}")
                    except ImportError:
                        logger.warning("Drift analyzer not available for refresh operation")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Refreshed drift analysis for {updated_count} resources',
                    'updated_count': updated_count,
                    'timestamp': timezone.now().isoformat()
                })
            
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid action or missing parameters'
                }, status=400)
                
        except Exception as e:
            logger.error(f"Drift analysis API error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


# URL patterns for drift detection
from django.urls import path

drift_urls = [
    path('drift-detection/', DriftDetectionDashboardView.as_view(), name='drift_dashboard'),
    path('drift-detection/fabric/<int:fabric_id>/', FabricDriftDetailView.as_view(), name='fabric_drift_detail'),
    path('api/drift-analysis/', DriftAnalysisAPIView.as_view(), name='drift_analysis_api'),
]
