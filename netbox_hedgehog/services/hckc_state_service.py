import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from django.utils import timezone

from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering
from ..models.wiring_api import Connection, Server, Switch, SwitchGroup, VLANNamespace
from ..utils.kubernetes import KubernetesClient

logger = logging.getLogger(__name__)


class HCKCStateService:
    """Service for synchronizing and comparing state between Git (desired) and HCKC cluster (actual)"""
    
    def __init__(self):
        self.cr_models = {
            'vpc.hhnet.githedgehog.com': VPC,
            'external.hhnet.githedgehog.com': External,
            'externalattachment.hhnet.githedgehog.com': ExternalAttachment,
            'externalpeering.hhnet.githedgehog.com': ExternalPeering,
            'ipv4namespace.hhnet.githedgehog.com': IPv4Namespace,
            'vpcattachment.hhnet.githedgehog.com': VPCAttachment,
            'vpcpeering.hhnet.githedgehog.com': VPCPeering,
            'connection.wiring.githedgehog.com': Connection,
            'server.wiring.githedgehog.com': Server,
            'switch.wiring.githedgehog.com': Switch,
            'switchgroup.wiring.githedgehog.com': SwitchGroup,
            'vlannamespace.wiring.githedgehog.com': VLANNamespace,
        }
    
    def sync_actual_state_from_cluster(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """
        Read actual CRD state from HCKC cluster and update HNP database
        Returns sync summary with counts and any errors
        """
        try:
            k8s_client = KubernetesClient(fabric)
            sync_summary = {
                'fabric_id': fabric.id,
                'fabric_name': fabric.name,
                'sync_started_at': timezone.now(),
                'success': False,
                'cr_types_synced': {},
                'total_resources_found': 0,
                'total_resources_updated': 0,
                'errors': []
            }
            
            logger.info(f"Starting HCKC state sync for fabric {fabric.name}")
            
            # Sync each CR type from cluster
            for api_version, model_class in self.cr_models.items():
                try:
                    cr_summary = self._sync_cr_type_from_cluster(k8s_client, fabric, api_version, model_class)
                    sync_summary['cr_types_synced'][api_version] = cr_summary
                    sync_summary['total_resources_found'] += cr_summary.get('found_in_cluster', 0)
                    sync_summary['total_resources_updated'] += cr_summary.get('updated_in_hnp', 0)
                    
                except Exception as e:
                    error_msg = f"Failed to sync {api_version}: {str(e)}"
                    logger.error(error_msg)
                    sync_summary['errors'].append(error_msg)
            
            # Update fabric sync status
            fabric.last_sync = timezone.now()
            if not sync_summary['errors']:
                fabric.sync_status = 'in_sync'
                fabric.sync_error = None
                sync_summary['success'] = True
            else:
                fabric.sync_status = 'error'
                fabric.sync_error = '; '.join(sync_summary['errors'][:3])  # Keep first 3 errors
            
            fabric.save()
            
            sync_summary['sync_completed_at'] = timezone.now()
            logger.info(f"Completed HCKC state sync for fabric {fabric.name} - Success: {sync_summary['success']}")
            
            return sync_summary
            
        except Exception as e:
            error_msg = f"HCKC sync failed for fabric {fabric.name}: {str(e)}"
            logger.error(error_msg)
            
            # Update fabric with error status
            fabric.sync_status = 'error'
            fabric.sync_error = str(e)[:500]  # Truncate long errors
            fabric.last_sync = timezone.now()
            fabric.save()
            
            return {
                'fabric_id': fabric.id,
                'fabric_name': fabric.name,
                'success': False,
                'error': error_msg,
                'sync_completed_at': timezone.now()
            }
    
    def _sync_cr_type_from_cluster(self, k8s_client: KubernetesClient, fabric: HedgehogFabric, 
                                   api_version: str, model_class) -> Dict[str, Any]:
        """Sync a specific CR type from the cluster"""
        summary = {
            'api_version': api_version,
            'model_name': model_class.__name__,
            'found_in_cluster': 0,
            'updated_in_hnp': 0,
            'created_in_hnp': 0,
            'errors': []
        }
        
        try:
            # Get all CRDs of this type from cluster
            cluster_crds = k8s_client.list_custom_resources(api_version, fabric.kubernetes_namespace)
            summary['found_in_cluster'] = len(cluster_crds)
            
            for crd_data in cluster_crds:
                try:
                    # Update or create CRD in HNP database
                    updated = self._update_cr_from_cluster_data(fabric, model_class, crd_data)
                    if updated:
                        summary['updated_in_hnp'] += 1
                    else:
                        summary['created_in_hnp'] += 1
                        
                except Exception as e:
                    error_msg = f"Failed to update {crd_data.get('metadata', {}).get('name', 'unknown')}: {str(e)}"
                    summary['errors'].append(error_msg)
                    logger.warning(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to list {api_version} from cluster: {str(e)}"
            summary['errors'].append(error_msg)
            logger.error(error_msg)
        
        return summary
    
    def _update_cr_from_cluster_data(self, fabric: HedgehogFabric, model_class, crd_data: Dict) -> bool:
        """Update or create a CR instance from cluster data. Returns True if updated, False if created"""
        metadata = crd_data.get('metadata', {})
        cr_name = metadata.get('name')
        cr_namespace = metadata.get('namespace', fabric.kubernetes_namespace)
        
        if not cr_name:
            raise ValueError("CR missing name in metadata")
        
        # Try to find existing CR
        try:
            cr_instance = model_class.objects.get(
                fabric=fabric,
                name=cr_name,
                namespace=cr_namespace
            )
            is_update = True
        except model_class.DoesNotExist:
            # Create new CR instance
            cr_instance = model_class(
                fabric=fabric,
                name=cr_name,
                namespace=cr_namespace
            )
            is_update = False
        
        # Update CR with cluster data
        cr_instance.kubernetes_status = 'live'
        cr_instance.last_applied = timezone.now()
        
        # Update spec if present
        if 'spec' in crd_data:
            cr_instance.spec = crd_data['spec']
        
        # Update labels if present
        if metadata.get('labels'):
            cr_instance.labels = metadata['labels']
        
        # Update annotations if present  
        if metadata.get('annotations'):
            cr_instance.annotations = metadata['annotations']
        
        # Set API version and kind from cluster data
        cr_instance.api_version = crd_data.get('apiVersion', '')
        cr_instance.kind = crd_data.get('kind', '')
        
        cr_instance.save()
        return is_update
    
    def compare_desired_vs_actual(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """
        Compare Git state (desired) with HCKC state (actual) to detect drift
        Returns comprehensive drift analysis
        """
        comparison_result = {
            'fabric_id': fabric.id,
            'fabric_name': fabric.name,
            'comparison_time': timezone.now(),
            'total_resources': 0,
            'in_sync': 0,
            'drifted': 0,
            'missing_from_cluster': 0,
            'missing_from_git': 0,
            'drift_details': [],
            'summary_by_type': {}
        }
        
        for api_version, model_class in self.cr_models.items():
            try:
                type_comparison = self._compare_cr_type(fabric, model_class)
                comparison_result['summary_by_type'][api_version] = type_comparison
                
                # Aggregate totals
                comparison_result['total_resources'] += type_comparison['total']
                comparison_result['in_sync'] += type_comparison['in_sync']
                comparison_result['drifted'] += type_comparison['drifted']
                comparison_result['missing_from_cluster'] += type_comparison['missing_from_cluster']
                comparison_result['missing_from_git'] += type_comparison['missing_from_git']
                
                # Add detailed drift information
                comparison_result['drift_details'].extend(type_comparison.get('drift_details', []))
                
            except Exception as e:
                logger.error(f"Failed to compare {api_version} for fabric {fabric.name}: {str(e)}")
        
        return comparison_result
    
    def _compare_cr_type(self, fabric: HedgehogFabric, model_class) -> Dict[str, Any]:
        """Compare a specific CR type between Git and cluster state"""
        type_result = {
            'model_name': model_class.__name__,
            'total': 0,
            'in_sync': 0,
            'drifted': 0,
            'missing_from_cluster': 0,
            'missing_from_git': 0,
            'drift_details': []
        }
        
        # Get all CRs of this type for the fabric
        all_crs = model_class.objects.filter(fabric=fabric)
        type_result['total'] = all_crs.count()
        
        for cr in all_crs:
            # Determine sync status based on kubernetes_status and git_file_path
            if cr.git_file_path and cr.kubernetes_status == 'live':
                # Resource exists in both Git and cluster
                if self._is_cr_in_sync(cr):
                    type_result['in_sync'] += 1
                else:
                    type_result['drifted'] += 1
                    type_result['drift_details'].append({
                        'name': cr.name,
                        'type': model_class.__name__,
                        'drift_type': 'configuration_drift',
                        'reason': 'Spec differs between Git and cluster'
                    })
            elif cr.git_file_path and cr.kubernetes_status != 'live':
                # Resource in Git but not in cluster
                type_result['missing_from_cluster'] += 1
                type_result['drift_details'].append({
                    'name': cr.name,
                    'type': model_class.__name__,
                    'drift_type': 'missing_from_cluster',
                    'reason': 'Resource defined in Git but not deployed to cluster'
                })
            elif not cr.git_file_path and cr.kubernetes_status == 'live':
                # Resource in cluster but not in Git
                type_result['missing_from_git'] += 1
                type_result['drift_details'].append({
                    'name': cr.name,
                    'type': model_class.__name__,
                    'drift_type': 'missing_from_git',
                    'reason': 'Resource deployed in cluster but not defined in Git'
                })
        
        return type_result
    
    def _is_cr_in_sync(self, cr) -> bool:
        """
        Determine if a CR is in sync between Git and cluster
        This is a simplified check - in practice would compare spec content
        """
        # For now, consider a resource in sync if it has both git_file_path and live status
        # and was recently synced (within last hour)
        if not (cr.git_file_path and cr.kubernetes_status == 'live'):
            return False
        
        if cr.last_synced and cr.last_applied:
            # Consider in sync if both Git sync and Kubernetes apply happened recently
            # and are within reasonable time of each other
            time_diff = abs((cr.last_synced - cr.last_applied).total_seconds())
            return time_diff < 3600  # Within 1 hour
        
        return False
    
    def detect_drift(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """
        High-level drift detection - identifies resources that are out of sync
        Returns summary focused on actionable drift information
        """
        comparison = self.compare_desired_vs_actual(fabric)
        
        drift_summary = {
            'fabric_id': fabric.id,
            'fabric_name': fabric.name,
            'has_drift': comparison['drifted'] > 0 or comparison['missing_from_cluster'] > 0 or comparison['missing_from_git'] > 0,
            'drift_score': self._calculate_drift_score(comparison),
            'critical_issues': [],
            'recommended_actions': [],
            'sync_health': 'healthy'
        }
        
        # Categorize issues by severity
        if comparison['missing_from_cluster'] > 0:
            drift_summary['critical_issues'].append({
                'type': 'missing_from_cluster',
                'count': comparison['missing_from_cluster'],
                'description': f"{comparison['missing_from_cluster']} resources defined in Git but not deployed"
            })
            drift_summary['recommended_actions'].append("Run 'Apply to Cluster' to deploy missing resources")
            drift_summary['sync_health'] = 'critical'
        
        if comparison['missing_from_git'] > 0:
            drift_summary['critical_issues'].append({
                'type': 'missing_from_git',
                'count': comparison['missing_from_git'],
                'description': f"{comparison['missing_from_git']} resources deployed but not in Git"
            })
            drift_summary['recommended_actions'].append("Review and add missing resources to Git repository")
            if drift_summary['sync_health'] != 'critical':
                drift_summary['sync_health'] = 'warning'
        
        if comparison['drifted'] > 0:
            drift_summary['critical_issues'].append({
                'type': 'configuration_drift',
                'count': comparison['drifted'],
                'description': f"{comparison['drifted']} resources have configuration differences"
            })
            drift_summary['recommended_actions'].append("Review and resolve configuration differences")
            if drift_summary['sync_health'] == 'healthy':
                drift_summary['sync_health'] = 'warning'
        
        return drift_summary
    
    def _calculate_drift_score(self, comparison: Dict) -> float:
        """Calculate a drift score from 0 (perfect sync) to 100 (completely out of sync)"""
        if comparison['total_resources'] == 0:
            return 0.0
        
        # Weight different types of drift
        drift_points = (
            comparison['missing_from_cluster'] * 3 +  # Most critical
            comparison['missing_from_git'] * 2 +      # Important
            comparison['drifted'] * 1                 # Moderate
        )
        
        max_possible_points = comparison['total_resources'] * 3
        drift_score = (drift_points / max_possible_points) * 100 if max_possible_points > 0 else 0.0
        
        return min(100.0, drift_score)
    
    def generate_fabric_state_report(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Generate comprehensive state report for a fabric"""
        try:
            comparison = self.compare_desired_vs_actual(fabric)
            drift_summary = self.detect_drift(fabric)
            
            report = {
                'fabric': {
                    'id': fabric.id,
                    'name': fabric.name,
                    'status': fabric.status,
                    'sync_status': fabric.sync_status,
                    'last_sync': fabric.last_sync,
                    'sync_enabled': fabric.sync_enabled
                },
                'state_comparison': comparison,
                'drift_analysis': drift_summary,
                'recommendations': self._generate_recommendations(fabric, drift_summary),
                'generated_at': timezone.now()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate state report for fabric {fabric.name}: {str(e)}")
            return {
                'fabric': {'id': fabric.id, 'name': fabric.name},
                'error': str(e),
                'generated_at': timezone.now()
            }
    
    def _generate_recommendations(self, fabric: HedgehogFabric, drift_summary: Dict) -> List[Dict]:
        """Generate actionable recommendations based on drift analysis"""
        recommendations = []
        
        if drift_summary['sync_health'] == 'critical':
            recommendations.append({
                'priority': 'high',
                'action': 'immediate_sync',
                'title': 'Immediate Sync Required',
                'description': 'Critical drift detected. Run sync operations immediately.',
                'steps': ['Review critical issues', 'Run Git sync', 'Apply to cluster', 'Verify deployment']
            })
        
        elif drift_summary['sync_health'] == 'warning':
            recommendations.append({
                'priority': 'medium', 
                'action': 'review_and_sync',
                'title': 'Review and Sync',
                'description': 'Configuration drift detected. Review changes and sync.',
                'steps': ['Review drift details', 'Validate changes', 'Run selective sync']
            })
        
        else:
            recommendations.append({
                'priority': 'low',
                'action': 'routine_maintenance',
                'title': 'System Healthy',
                'description': 'No significant drift detected. Continue routine monitoring.',
                'steps': ['Monitor regularly', 'Schedule next sync check']
            })
        
        return recommendations