"""
Drift Detection API Endpoints
Functional API implementation for drift analysis dashboard
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Avg, Count, Q
from django.contrib.auth.mixins import LoginRequiredMixin
import logging
import json

from ...models import HedgehogFabric, HedgehogResource
from ...utils.drift_detection import DriftAnalyzer, analyze_fabric_drift
from ...api.serializers import HedgehogResourceSerializer

logger = logging.getLogger(__name__)


class DriftDashboardAPIView(APIView):
    """
    API endpoint for drift dashboard data
    """
    
    def get(self, request):
        """Get drift dashboard summary data"""
        try:
            # Get filter parameters
            fabric_id = request.GET.get('fabric_id')
            severity = request.GET.get('severity')
            resource_type = request.GET.get('resource_type')
            
            # Build base queryset
            resources_query = HedgehogResource.objects.all()
            
            # Apply filters
            if fabric_id:
                resources_query = resources_query.filter(fabric_id=fabric_id)
            if resource_type:
                resources_query = resources_query.filter(kind=resource_type)
            
            # Get total counts
            total_resources = resources_query.count()
            drifted_resources = resources_query.exclude(drift_status='in_sync')
            
            # Apply severity filter to drifted resources
            if severity:
                if severity == 'critical':
                    drifted_resources = drifted_resources.filter(drift_score__gte=0.8)
                elif severity == 'high':
                    drifted_resources = drifted_resources.filter(drift_score__gte=0.6, drift_score__lt=0.8)
                elif severity == 'medium':
                    drifted_resources = drifted_resources.filter(drift_score__gte=0.3, drift_score__lt=0.6)
                elif severity == 'low':
                    drifted_resources = drifted_resources.filter(drift_score__lt=0.3)
            
            drifted_count = drifted_resources.count()
            
            # Get detailed resource information
            drifted_list = []
            for resource in drifted_resources.select_related('fabric')[:100]:  # Limit for performance
                # Determine severity
                severity_info = self._get_severity_info(resource.drift_score)
                
                # Get drift summary
                drift_summary = 'Configuration drift detected'
                if resource.drift_details and isinstance(resource.drift_details, dict):
                    drift_summary = resource.drift_details.get('summary', drift_summary)
                
                drifted_list.append({
                    'id': resource.id,
                    'name': resource.name,
                    'kind': resource.kind,
                    'namespace': resource.namespace,
                    'fabric': {
                        'id': resource.fabric.id,
                        'name': resource.fabric.name
                    },
                    'drift_status': resource.drift_status,
                    'drift_score': resource.drift_score,
                    'drift_summary': drift_summary,
                    'severity': severity_info['severity'],
                    'severity_class': severity_info['class'],
                    'last_drift_check': resource.last_drift_check.isoformat() if resource.last_drift_check else None,
                    'can_sync': bool(resource.fabric.git_repository_url)
                })
            
            # Get fabric-level statistics
            fabric_stats = []
            for fabric in HedgehogFabric.objects.all():
                fabric_resources = resources_query.filter(fabric=fabric)
                fabric_drifted = fabric_resources.exclude(drift_status='in_sync')
                
                fabric_stats.append({
                    'fabric_id': fabric.id,
                    'fabric_name': fabric.name,
                    'total_resources': fabric_resources.count(),
                    'drifted_count': fabric_drifted.count(),
                    'critical_count': fabric_drifted.filter(drift_score__gte=0.8).count(),
                    'avg_drift_score': fabric_drifted.aggregate(
                        avg=Avg('drift_score')
                    )['avg'] or 0.0
                })
            
            # Calculate summary statistics
            in_sync_count = total_resources - drifted_count
            critical_count = drifted_resources.filter(drift_score__gte=0.8).count()
            
            return Response({
                'success': True,
                'summary': {
                    'total_resources': total_resources,
                    'in_sync_count': in_sync_count,
                    'drifted_count': drifted_count,
                    'critical_count': critical_count,
                    'drift_percentage': (drifted_count / total_resources * 100) if total_resources > 0 else 0
                },
                'drifted_resources': drifted_list,
                'fabric_stats': fabric_stats,
                'filters': {
                    'fabric_id': fabric_id,
                    'severity': severity,
                    'resource_type': resource_type
                },
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Drift dashboard API error: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_severity_info(self, drift_score):
        """Get severity information from drift score"""
        if drift_score >= 0.8:
            return {'severity': 'critical', 'class': 'danger'}
        elif drift_score >= 0.6:
            return {'severity': 'high', 'class': 'warning'}
        elif drift_score >= 0.3:
            return {'severity': 'medium', 'class': 'info'}
        else:
            return {'severity': 'low', 'class': 'secondary'}


class FabricDriftAnalysisAPIView(APIView):
    """
    API endpoint for fabric-specific drift analysis
    """
    
    def get(self, request, fabric_id):
        """Get detailed drift analysis for a specific fabric"""
        try:
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            
            # Run drift analysis using existing logic
            drift_analysis = analyze_fabric_drift(fabric)
            
            # Get detailed resource information
            resources = HedgehogResource.objects.filter(fabric=fabric)
            
            resource_details = []
            for resource in resources:
                drift_info = resource.drift_details or {}
                
                resource_details.append({
                    'id': resource.id,
                    'name': resource.name,
                    'kind': resource.kind,
                    'namespace': resource.namespace,
                    'drift_status': resource.drift_status,
                    'drift_score': resource.drift_score,
                    'has_drift': drift_info.get('has_drift', False),
                    'differences_count': len(drift_info.get('differences', [])),
                    'last_checked': resource.last_drift_check.isoformat() if resource.last_drift_check else None
                })
            
            return Response({
                'success': True,
                'fabric': {
                    'id': fabric.id,
                    'name': fabric.name,
                    'description': fabric.description
                },
                'analysis': drift_analysis,
                'resources': resource_details,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Fabric drift analysis API error: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, fabric_id):
        """Trigger drift analysis refresh for a fabric"""
        try:
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            
            # Refresh drift analysis for all resources in fabric
            resources = HedgehogResource.objects.filter(fabric=fabric)
            
            analyzer = DriftAnalyzer()
            updated_count = 0
            errors = []
            
            for resource in resources:
                try:
                    analyzer._analyze_resource_drift(resource)
                    updated_count += 1
                except Exception as e:
                    errors.append(f"Failed to analyze {resource.name}: {str(e)}")
                    logger.error(f"Resource drift analysis failed: {e}")
            
            return Response({
                'success': True,
                'fabric_id': fabric.id,
                'fabric_name': fabric.name,
                'updated_count': updated_count,
                'total_resources': resources.count(),
                'errors': errors,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Fabric drift refresh API error: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResourceDriftDetailAPIView(APIView):
    """
    API endpoint for individual resource drift details
    """
    
    def get(self, request, resource_id):
        """Get detailed drift information for a specific resource"""
        try:
            resource = get_object_or_404(HedgehogResource, pk=resource_id)
            
            # Get or calculate drift details
            if resource.drift_details:
                drift_details = resource.drift_details
            else:
                # Calculate drift on-demand
                analyzer = DriftAnalyzer()
                drift_details = analyzer._analyze_resource_drift(resource)
            
            # Process differences for API response
            processed_differences = []
            if drift_details.get('differences'):
                for diff in drift_details['differences']:
                    processed_differences.append({
                        'path': diff.get('path', ''),
                        'type': diff.get('type', ''),
                        'severity': diff.get('severity', 'medium'),
                        'desired': diff.get('desired'),
                        'actual': diff.get('actual'),
                        'description': self._format_diff_description(diff)
                    })
            
            return Response({
                'success': True,
                'resource': {
                    'id': resource.id,
                    'name': resource.name,
                    'kind': resource.kind,
                    'namespace': resource.namespace,
                    'fabric': {
                        'id': resource.fabric.id,
                        'name': resource.fabric.name
                    }
                },
                'drift_analysis': {
                    'has_drift': drift_details.get('has_drift', False),
                    'drift_score': drift_details.get('drift_score', 0.0),
                    'drift_status': resource.drift_status,
                    'summary': drift_details.get('summary', ''),
                    'total_differences': len(processed_differences),
                    'differences': processed_differences,
                    'recommendations': drift_details.get('recommendations', [])
                },
                'last_checked': resource.last_drift_check.isoformat() if resource.last_drift_check else None,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Resource drift detail API error: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, resource_id):
        """Refresh drift analysis for a specific resource"""
        try:
            resource = get_object_or_404(HedgehogResource, pk=resource_id)
            
            # Recalculate drift
            analyzer = DriftAnalyzer()
            drift_result = analyzer._analyze_resource_drift(resource)
            
            return Response({
                'success': True,
                'resource_id': resource.id,
                'resource_name': resource.name,
                'drift_result': drift_result,
                'message': 'Drift analysis updated successfully',
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Resource drift refresh API error: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _format_diff_description(self, diff):
        """Format a human-readable description of the difference"""
        diff_type = diff.get('type', 'unknown')
        path = diff.get('path', '')
        
        descriptions = {
            'value_mismatch': f"Value mismatch at {path}",
            'missing_actual': f"Missing in cluster: {path}",
            'missing_desired': f"Missing in Git repository: {path}",
            'type_mismatch': f"Type mismatch at {path}",
            'extra_key_actual': f"Extra field in cluster: {path}",
            'missing_key_actual': f"Missing field in cluster: {path}",
            'missing_actual_resource': "Resource exists in Git but not in cluster",
            'orphaned_actual_resource': "Resource exists in cluster but not in Git"
        }
        
        return descriptions.get(diff_type, f"Drift detected at {path}")


class DriftSyncAPIView(APIView):
    """
    API endpoint for triggering drift resolution (sync operations)
    """
    
    def post(self, request):
        """Trigger sync operation to resolve drift"""
        try:
            action = request.data.get('action', 'sync')
            resource_id = request.data.get('resource_id')
            fabric_id = request.data.get('fabric_id')
            
            if resource_id:
                # Sync specific resource
                resource = get_object_or_404(HedgehogResource, pk=resource_id)
                fabric = resource.fabric
                
                # In a real implementation, this would trigger actual sync
                # For now, we'll simulate the sync operation
                result = self._simulate_resource_sync(resource)
                
                return Response({
                    'success': result['success'],
                    'resource_id': resource.id,
                    'resource_name': resource.name,
                    'fabric_name': fabric.name,
                    'message': result['message'],
                    'sync_details': result.get('details', {}),
                    'timestamp': timezone.now().isoformat()
                })
                
            elif fabric_id:
                # Sync entire fabric
                fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
                
                # In a real implementation, this would trigger fabric-wide sync
                result = self._simulate_fabric_sync(fabric)
                
                return Response({
                    'success': result['success'],
                    'fabric_id': fabric.id,
                    'fabric_name': fabric.name,
                    'message': result['message'],
                    'sync_details': result.get('details', {}),
                    'timestamp': timezone.now().isoformat()
                })
                
            else:
                return Response({
                    'success': False,
                    'error': 'Either resource_id or fabric_id must be provided'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Drift sync API error: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _simulate_resource_sync(self, resource):
        """Simulate resource sync operation"""
        try:
            # In a real implementation, this would:
            # 1. Get desired state from Git
            # 2. Apply to Kubernetes cluster
            # 3. Update resource status
            
            # For simulation, just update the resource status
            resource.drift_status = 'syncing'
            resource.save(update_fields=['drift_status'])
            
            return {
                'success': True,
                'message': f'Sync initiated for {resource.kind}/{resource.name}',
                'details': {
                    'sync_type': 'resource',
                    'status': 'initiated'
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Sync failed: {str(e)}'
            }
    
    def _simulate_fabric_sync(self, fabric):
        """Simulate fabric-wide sync operation"""
        try:
            # In a real implementation, this would trigger fabric-wide sync
            drifted_resources = HedgehogResource.objects.filter(
                fabric=fabric
            ).exclude(drift_status='in_sync')
            
            sync_count = 0
            for resource in drifted_resources:
                resource.drift_status = 'syncing'
                sync_count += 1
            
            HedgehogResource.objects.bulk_update(drifted_resources, ['drift_status'])
            
            return {
                'success': True,
                'message': f'Sync initiated for {sync_count} resources in fabric {fabric.name}',
                'details': {
                    'sync_type': 'fabric',
                    'resources_synced': sync_count,
                    'status': 'initiated'
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Fabric sync failed: {str(e)}'
            }


class DriftExportAPIView(APIView):
    """
    API endpoint for exporting drift reports
    """
    
    def get(self, request):
        """Export drift report in various formats"""
        try:
            format_type = request.GET.get('format', 'json')
            fabric_id = request.GET.get('fabric_id')
            
            # Get drift data
            if fabric_id:
                fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
                resources = HedgehogResource.objects.filter(fabric=fabric)
                report_title = f'Drift Report - {fabric.name}'
            else:
                resources = HedgehogResource.objects.all()
                report_title = 'Global Drift Report'
            
            # Filter drifted resources
            drifted_resources = resources.exclude(drift_status='in_sync')
            
            if format_type == 'csv':
                return self._export_csv(drifted_resources, report_title)
            elif format_type == 'json':
                return self._export_json(drifted_resources, report_title)
            else:
                return Response({
                    'success': False,
                    'error': f'Unsupported format: {format_type}'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Drift export API error: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _export_json(self, resources, title):
        """Export drift data as JSON"""
        export_data = {
            'title': title,
            'generated_at': timezone.now().isoformat(),
            'total_drifted_resources': resources.count(),
            'resources': []
        }
        
        for resource in resources:
            severity_info = self._get_severity_info(resource.drift_score)
            
            export_data['resources'].append({
                'id': resource.id,
                'name': resource.name,
                'kind': resource.kind,
                'namespace': resource.namespace,
                'fabric': resource.fabric.name,
                'drift_status': resource.drift_status,
                'drift_score': resource.drift_score,
                'severity': severity_info['severity'],
                'last_checked': resource.last_drift_check.isoformat() if resource.last_drift_check else None
            })
        
        return Response(export_data)
    
    def _export_csv(self, resources, title):
        """Export drift data as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="drift_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Resource Name', 'Type', 'Namespace', 'Fabric', 
            'Drift Status', 'Drift Score', 'Severity', 'Last Checked'
        ])
        
        for resource in resources:
            severity_info = self._get_severity_info(resource.drift_score)
            writer.writerow([
                resource.name,
                resource.kind,
                resource.namespace,
                resource.fabric.name,
                resource.drift_status,
                resource.drift_score,
                severity_info['severity'],
                resource.last_drift_check.strftime('%Y-%m-%d %H:%M:%S') if resource.last_drift_check else 'Never'
            ])
        
        return response
    
    def _get_severity_info(self, drift_score):
        """Get severity information from drift score"""
        if drift_score >= 0.8:
            return {'severity': 'critical', 'class': 'danger'}
        elif drift_score >= 0.6:
            return {'severity': 'high', 'class': 'warning'}
        elif drift_score >= 0.3:
            return {'severity': 'medium', 'class': 'info'}
        else:
            return {'severity': 'low', 'class': 'secondary'}