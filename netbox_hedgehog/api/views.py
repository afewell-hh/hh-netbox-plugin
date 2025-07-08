from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from netbox.api.viewsets import NetBoxModelViewSet
from django.shortcuts import get_object_or_404
import logging

from .. import models
from . import serializers
from ..utils.gitops_integration import (
    bulk_sync_fabric_to_gitops,
    get_fabric_gitops_status,
    CRDGitOpsIntegrator
)

logger = logging.getLogger(__name__)

# Fabric ViewSet
class FabricViewSet(NetBoxModelViewSet):
    queryset = models.HedgehogFabric.objects.all()
    serializer_class = serializers.FabricSerializer

# VPC API ViewSets
class VPCViewSet(NetBoxModelViewSet):
    queryset = models.VPC.objects.all()
    serializer_class = serializers.VPCSerializer

class ExternalViewSet(NetBoxModelViewSet):
    queryset = models.External.objects.all()
    serializer_class = serializers.ExternalSerializer

class ExternalAttachmentViewSet(NetBoxModelViewSet):
    queryset = models.ExternalAttachment.objects.all()
    serializer_class = serializers.ExternalAttachmentSerializer

class ExternalPeeringViewSet(NetBoxModelViewSet):
    queryset = models.ExternalPeering.objects.all()
    serializer_class = serializers.ExternalPeeringSerializer

class IPv4NamespaceViewSet(NetBoxModelViewSet):
    queryset = models.IPv4Namespace.objects.all()
    serializer_class = serializers.IPv4NamespaceSerializer

class VPCAttachmentViewSet(NetBoxModelViewSet):
    queryset = models.VPCAttachment.objects.all()
    serializer_class = serializers.VPCAttachmentSerializer

class VPCPeeringViewSet(NetBoxModelViewSet):
    queryset = models.VPCPeering.objects.all()
    serializer_class = serializers.VPCPeeringSerializer

# Wiring API ViewSets
class ConnectionViewSet(NetBoxModelViewSet):
    queryset = models.Connection.objects.all()
    serializer_class = serializers.ConnectionSerializer

class ServerViewSet(NetBoxModelViewSet):
    queryset = models.Server.objects.all()
    serializer_class = serializers.ServerSerializer

class SwitchViewSet(NetBoxModelViewSet):
    queryset = models.Switch.objects.all()
    serializer_class = serializers.SwitchSerializer

class SwitchGroupViewSet(NetBoxModelViewSet):
    queryset = models.SwitchGroup.objects.all()
    serializer_class = serializers.SwitchGroupSerializer

class VLANNamespaceViewSet(NetBoxModelViewSet):
    queryset = models.VLANNamespace.objects.all()
    serializer_class = serializers.VLANNamespaceSerializer

# Custom API Views
class SyncAPIView(APIView):
    """API endpoint for triggering synchronization"""
    
    def post(self, request):
        # TODO: Implement sync logic
        return Response({
            'status': 'success',
            'message': 'Synchronization initiated'
        }, status=status.HTTP_200_OK)

class StatusAPIView(APIView):
    """API endpoint for checking fabric status"""
    
    def get(self, request):
        # TODO: Implement status checking
        fabrics = models.HedgehogFabric.objects.all()
        return Response({
            'fabrics': len(fabrics),
            'status': 'operational'
        }, status=status.HTTP_200_OK)


# GitOps API Views (MVP2)
class HedgehogResourceViewSet(NetBoxModelViewSet):
    """API ViewSet for HedgehogResource dual-state tracking"""
    queryset = models.HedgehogResource.objects.all()
    serializer_class = serializers.HedgehogResourceSerializer
    filterset_fields = ['fabric', 'kind', 'namespace', 'drift_status']
    
    @action(detail=True, methods=['post'])
    def calculate_drift(self, request, pk=None):
        """Calculate drift for a specific resource"""
        resource = self.get_object()
        try:
            result = resource.calculate_drift()
            serializer = serializers.DriftStatusSerializer(result)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Drift calculation failed for resource {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def yaml(self, request, pk=None):
        """Generate YAML content for this resource"""
        resource = self.get_object()
        try:
            yaml_content = resource.generate_yaml_content()
            if yaml_content:
                return Response({
                    'yaml': yaml_content,
                    'file_path': resource.desired_file_path,
                    'commit': resource.desired_commit
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Unable to generate YAML content'
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"YAML generation failed for resource {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get comprehensive status for this resource"""
        resource = self.get_object()
        try:
            status_data = resource.get_status_summary()
            return Response(status_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Status retrieval failed for resource {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EnhancedFabricViewSet(NetBoxModelViewSet):
    """Enhanced Fabric ViewSet with GitOps functionality"""
    queryset = models.HedgehogFabric.objects.all()
    serializer_class = serializers.EnhancedFabricSerializer
    
    @action(detail=True, methods=['get'])
    def git_status(self, request, pk=None):
        """Get Git repository status for this fabric"""
        fabric = self.get_object()
        try:
            git_status = fabric.get_git_status()
            serializer = serializers.GitStatusSerializer(git_status)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Git status failed for fabric {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def sync_git(self, request, pk=None):
        """Trigger Git repository synchronization"""
        fabric = self.get_object()
        try:
            result = fabric.sync_desired_state()
            serializer = serializers.GitSyncSerializer(result)
            return Response(serializer.data, 
                          status=status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Git sync failed for fabric {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def drift_report(self, request, pk=None):
        """Get comprehensive drift report for this fabric"""
        fabric = self.get_object()
        try:
            integrator = CRDGitOpsIntegrator(fabric)
            drift_summary = integrator.get_drift_summary()
            serializer = serializers.DriftReportSerializer(drift_summary)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Drift report failed for fabric {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def gitops_sync(self, request, pk=None):
        """Trigger GitOps tool synchronization"""
        fabric = self.get_object()
        try:
            result = fabric.trigger_gitops_sync()
            serializer = serializers.GitOpsSyncSerializer(result)
            return Response(serializer.data,
                          status=status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"GitOps sync failed for fabric {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def bulk_sync(self, request, pk=None):
        """Trigger bulk synchronization of all CRDs to GitOps tracking"""
        fabric = self.get_object()
        try:
            result = bulk_sync_fabric_to_gitops(fabric)
            serializer = serializers.BulkSyncSerializer(result)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Bulk sync failed for fabric {pk}: {e}")
            return Response({
                'synced': 0,
                'errors': 1,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def gitops_status(self, request, pk=None):
        """Get comprehensive GitOps status for this fabric"""
        fabric = self.get_object()
        try:
            status_data = get_fabric_gitops_status(fabric)
            serializer = serializers.FabricGitOpsStatusSerializer(status_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"GitOps status failed for fabric {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitOpsAPIView(APIView):
    """Global GitOps operations API endpoint"""
    
    def get(self, request):
        """Get global GitOps status across all fabrics"""
        try:
            fabrics = models.HedgehogFabric.objects.all()
            
            # Calculate global statistics
            total_fabrics = fabrics.count()
            configured_fabrics = fabrics.exclude(git_repository_url='').count()
            
            # Get total resource counts
            total_resources = models.HedgehogResource.objects.count()
            drifted_resources = models.HedgehogResource.objects.exclude(drift_status='in_sync').count()
            
            # Per-fabric summary
            fabric_summaries = []
            for fabric in fabrics:
                try:
                    integrator = CRDGitOpsIntegrator(fabric)
                    drift_summary = integrator.get_drift_summary()
                    fabric_summaries.append({
                        'fabric_id': fabric.id,
                        'fabric_name': fabric.name,
                        'git_configured': bool(fabric.git_repository_url),
                        'total_resources': drift_summary['total_resources'],
                        'drift_count': drift_summary['drifted'],
                        'drift_percentage': drift_summary['drift_percentage']
                    })
                except Exception as e:
                    logger.error(f"Failed to get summary for fabric {fabric.name}: {e}")
                    fabric_summaries.append({
                        'fabric_id': fabric.id,
                        'fabric_name': fabric.name,
                        'error': str(e)
                    })
            
            return Response({
                'global_stats': {
                    'total_fabrics': total_fabrics,
                    'configured_fabrics': configured_fabrics,
                    'total_resources': total_resources,
                    'drifted_resources': drifted_resources,
                    'global_drift_percentage': (drifted_resources / total_resources * 100) if total_resources > 0 else 0
                },
                'fabric_summaries': fabric_summaries
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Global GitOps status failed: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DriftAnalysisAPIView(APIView):
    """API endpoint for drift analysis operations"""
    
    def post(self, request):
        """Trigger drift analysis for specific fabric or all fabrics"""
        fabric_id = request.data.get('fabric_id')
        
        try:
            if fabric_id:
                # Analyze specific fabric
                fabric = get_object_or_404(models.HedgehogFabric, id=fabric_id)
                resources = models.HedgehogResource.objects.filter(fabric=fabric)
                
                results = {
                    'fabric': fabric.name,
                    'analyzed': 0,
                    'errors': 0,
                    'details': []
                }
                
                for resource in resources:
                    try:
                        drift_result = resource.calculate_drift()
                        results['analyzed'] += 1
                        if drift_result.get('success'):
                            results['details'].append({
                                'resource': f"{resource.kind}/{resource.name}",
                                'drift_status': drift_result['drift_status'],
                                'drift_score': drift_result['drift_score']
                            })
                        else:
                            results['errors'] += 1
                    except Exception as e:
                        results['errors'] += 1
                        logger.error(f"Drift analysis failed for {resource}: {e}")
                
                return Response(results, status=status.HTTP_200_OK)
            
            else:
                # Analyze all fabrics
                fabrics = models.HedgehogFabric.objects.all()
                results = {
                    'analyzed_fabrics': 0,
                    'total_resources': 0,
                    'errors': 0,
                    'fabric_results': []
                }
                
                for fabric in fabrics:
                    try:
                        resources = models.HedgehogResource.objects.filter(fabric=fabric)
                        fabric_analyzed = 0
                        fabric_errors = 0
                        
                        for resource in resources:
                            try:
                                resource.calculate_drift()
                                fabric_analyzed += 1
                            except Exception:
                                fabric_errors += 1
                        
                        results['fabric_results'].append({
                            'fabric': fabric.name,
                            'analyzed': fabric_analyzed,
                            'errors': fabric_errors
                        })
                        
                        results['analyzed_fabrics'] += 1
                        results['total_resources'] += fabric_analyzed
                        results['errors'] += fabric_errors
                        
                    except Exception as e:
                        results['errors'] += 1
                        logger.error(f"Fabric analysis failed for {fabric.name}: {e}")
                
                return Response(results, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Drift analysis failed: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)