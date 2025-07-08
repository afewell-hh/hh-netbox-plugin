"""
GitOps Integration Utilities
Provides integration between existing MVP1 CRD models and new GitOps dual-state tracking.
"""

from typing import Dict, List, Optional, Tuple, Any
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class CRDGitOpsIntegrator:
    """
    Integrates existing CRD models with GitOps dual-state tracking.
    Provides methods to sync CRD data with HedgehogResource tracking.
    """
    
    def __init__(self, fabric):
        """Initialize integrator for a specific fabric"""
        self.fabric = fabric
        
    def sync_crd_to_gitops_resource(self, crd_instance, commit_sha: str = None, file_path: str = None):
        """
        Create or update HedgehogResource tracking for an existing CRD instance.
        
        Args:
            crd_instance: Instance of a CRD model (VPC, Connection, etc.)
            commit_sha: Git commit SHA if this came from Git
            file_path: Git file path if this came from Git
            
        Returns:
            HedgehogResource instance
        """
        from netbox_hedgehog.models import HedgehogResource
        
        try:
            # Get or create HedgehogResource for this CRD
            resource, created = HedgehogResource.objects.get_or_create(
                fabric=self.fabric,
                name=crd_instance.name,
                namespace=crd_instance.namespace,
                kind=crd_instance.get_kind(),
                defaults={
                    'actual_spec': crd_instance.spec,
                    'actual_status': getattr(crd_instance, 'status', {}),
                    'actual_resource_version': getattr(crd_instance, 'kubernetes_resource_version', ''),
                    'actual_updated': timezone.now(),
                    'labels': getattr(crd_instance, 'labels', {}),
                    'annotations': getattr(crd_instance, 'annotations', {}),
                }
            )
            
            if not created:
                # Update existing resource with actual state
                resource.actual_spec = crd_instance.spec
                resource.actual_status = getattr(crd_instance, 'status', {})
                resource.actual_resource_version = getattr(crd_instance, 'kubernetes_resource_version', '')
                resource.actual_updated = timezone.now()
                resource.labels = getattr(crd_instance, 'labels', {})
                resource.annotations = getattr(crd_instance, 'annotations', {})
            
            # If this came from Git, update desired state too
            if commit_sha and file_path:
                resource.desired_spec = crd_instance.spec
                resource.desired_commit = commit_sha
                resource.desired_file_path = file_path
                resource.desired_updated = timezone.now()
            
            resource.save()
            
            # Calculate drift after update
            resource.calculate_drift()
            
            logger.info(f"Synced {resource.kind}/{resource.name} to GitOps tracking")
            return resource
            
        except Exception as e:
            logger.error(f"Failed to sync CRD {crd_instance} to GitOps: {e}")
            raise
    
    def sync_all_fabric_crds(self):
        """
        Sync all existing CRDs in this fabric to GitOps tracking.
        Creates HedgehogResource entries for all existing CRDs.
        
        Returns:
            Dict with sync results
        """
        from netbox_hedgehog.models import (
            VPC, External, ExternalAttachment, ExternalPeering,
            IPv4Namespace, VPCAttachment, VPCPeering,
            Connection, Server, Switch, SwitchGroup, VLANNamespace
        )
        
        crd_models = [
            VPC, External, ExternalAttachment, ExternalPeering,
            IPv4Namespace, VPCAttachment, VPCPeering,
            Connection, Server, Switch, SwitchGroup, VLANNamespace
        ]
        
        results = {
            'synced': 0,
            'errors': 0,
            'details': {}
        }
        
        with transaction.atomic():
            for model_class in crd_models:
                model_name = model_class.__name__
                try:
                    crds = model_class.objects.filter(fabric=self.fabric)
                    model_synced = 0
                    
                    for crd in crds:
                        try:
                            self.sync_crd_to_gitops_resource(crd)
                            model_synced += 1
                            results['synced'] += 1
                        except Exception as e:
                            logger.error(f"Failed to sync {model_name} {crd.name}: {e}")
                            results['errors'] += 1
                    
                    results['details'][model_name] = {
                        'total': crds.count(),
                        'synced': model_synced,
                        'errors': crds.count() - model_synced
                    }
                    
                except Exception as e:
                    logger.error(f"Failed to process {model_name} models: {e}")
                    results['details'][model_name] = {
                        'error': str(e)
                    }
                    results['errors'] += 1
        
        logger.info(f"Fabric {self.fabric.name}: Synced {results['synced']} CRDs, {results['errors']} errors")
        return results
    
    def create_gitops_resource_from_yaml(self, yaml_content: str, commit_sha: str, file_path: str):
        """
        Create HedgehogResource from YAML content (desired state from Git).
        
        Args:
            yaml_content: YAML content from Git repository
            commit_sha: Git commit SHA
            file_path: Path to YAML file in Git
            
        Returns:
            HedgehogResource instance or None if parsing fails
        """
        import yaml
        from netbox_hedgehog.models import HedgehogResource
        
        try:
            # Parse YAML content
            docs = list(yaml.safe_load_all(yaml_content))
            
            for doc in docs:
                if not self._is_hedgehog_resource(doc):
                    continue
                
                # Extract resource information
                metadata = doc.get('metadata', {})
                name = metadata.get('name')
                namespace = metadata.get('namespace', 'default')
                kind = doc.get('kind')
                spec = doc.get('spec', {})
                labels = metadata.get('labels', {})
                annotations = metadata.get('annotations', {})
                
                if not all([name, kind]):
                    logger.warning(f"Invalid resource in {file_path}: missing name or kind")
                    continue
                
                # Create or update HedgehogResource
                resource, created = HedgehogResource.objects.get_or_create(
                    fabric=self.fabric,
                    name=name,
                    namespace=namespace,
                    kind=kind,
                    defaults={
                        'desired_spec': spec,
                        'desired_commit': commit_sha,
                        'desired_file_path': file_path,
                        'desired_updated': timezone.now(),
                        'labels': labels,
                        'annotations': annotations,
                    }
                )
                
                if not created:
                    # Update existing resource's desired state
                    resource.desired_spec = spec
                    resource.desired_commit = commit_sha
                    resource.desired_file_path = file_path
                    resource.desired_updated = timezone.now()
                    resource.labels = labels
                    resource.annotations = annotations
                    resource.save()
                
                # Calculate drift after update
                resource.calculate_drift()
                
                logger.info(f"Created/updated GitOps resource {kind}/{name} from Git")
                return resource
                
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Failed to create GitOps resource from {file_path}: {e}")
        
        return None
    
    def _is_hedgehog_resource(self, yaml_doc: Dict) -> bool:
        """
        Check if YAML document is a Hedgehog CRD.
        
        Args:
            yaml_doc: Parsed YAML document
            
        Returns:
            True if this is a Hedgehog resource
        """
        if not isinstance(yaml_doc, dict):
            return False
        
        api_version = yaml_doc.get('apiVersion', '')
        kind = yaml_doc.get('kind', '')
        
        # Check for Hedgehog API versions
        hedgehog_apis = [
            'vpc.githedgehog.com/v1beta1',
            'wiring.githedgehog.com/v1beta1'
        ]
        
        # Check for Hedgehog kinds
        hedgehog_kinds = [
            'VPC', 'External', 'ExternalAttachment', 'ExternalPeering',
            'IPv4Namespace', 'VPCAttachment', 'VPCPeering',
            'Connection', 'Server', 'Switch', 'SwitchGroup', 'VLANNamespace'
        ]
        
        return api_version in hedgehog_apis and kind in hedgehog_kinds
    
    def get_drift_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive drift summary for this fabric.
        
        Returns:
            Dict with drift analysis
        """
        from netbox_hedgehog.models import HedgehogResource
        
        resources = HedgehogResource.objects.filter(fabric=self.fabric)
        
        total_resources = resources.count()
        in_sync = resources.filter(drift_status='in_sync').count()
        drifted = total_resources - in_sync
        
        # Group by drift status
        drift_by_status = {}
        for status_choice in ['spec_drift', 'desired_only', 'actual_only', 'creation_pending', 'deletion_pending']:
            count = resources.filter(drift_status=status_choice).count()
            if count > 0:
                drift_by_status[status_choice] = count
        
        # Group by resource kind
        drift_by_kind = {}
        for resource in resources.filter(drift_status__in=['spec_drift', 'desired_only', 'actual_only']):
            kind = resource.kind
            if kind not in drift_by_kind:
                drift_by_kind[kind] = {'total': 0, 'drifted': 0}
            drift_by_kind[kind]['total'] += 1
            if resource.has_drift:
                drift_by_kind[kind]['drifted'] += 1
        
        return {
            'fabric': self.fabric.name,
            'total_resources': total_resources,
            'in_sync': in_sync,
            'drifted': drifted,
            'drift_percentage': (drifted / total_resources * 100) if total_resources > 0 else 0,
            'drift_by_status': drift_by_status,
            'drift_by_kind': drift_by_kind,
            'last_updated': timezone.now()
        }
    
    def reconcile_orphaned_resources(self) -> Dict[str, int]:
        """
        Find and handle resources that exist in cluster but not in Git (orphaned).
        
        Returns:
            Dict with reconciliation results
        """
        from netbox_hedgehog.models import HedgehogResource
        
        orphaned = HedgehogResource.objects.filter(
            fabric=self.fabric,
            drift_status='actual_only'
        )
        
        results = {
            'found': orphaned.count(),
            'processed': 0,
            'errors': 0
        }
        
        for resource in orphaned:
            try:
                # Generate YAML for orphaned resource
                yaml_content = resource.generate_yaml_content()
                if yaml_content:
                    # Mark as needing Git addition
                    resource.drift_status = 'creation_pending'
                    resource.drift_details = {
                        'type': 'orphaned_yaml_generated',
                        'message': 'Resource exists in cluster but not in Git. YAML generated for addition.',
                        'yaml_content': yaml_content
                    }
                    resource.save()
                    results['processed'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to process orphaned resource {resource}: {e}")
                results['errors'] += 1
        
        return results


class CRDLifecycleManager:
    """
    Manages CRD lifecycle events and ensures GitOps tracking stays in sync.
    """
    
    @staticmethod
    def on_crd_created(crd_instance, fabric):
        """
        Handle CRD creation event - sync to GitOps tracking.
        
        Args:
            crd_instance: Newly created CRD instance
            fabric: HedgehogFabric instance
        """
        try:
            integrator = CRDGitOpsIntegrator(fabric)
            integrator.sync_crd_to_gitops_resource(crd_instance)
            logger.info(f"CRD created: {crd_instance} synced to GitOps tracking")
        except Exception as e:
            logger.error(f"Failed to sync new CRD {crd_instance} to GitOps: {e}")
    
    @staticmethod
    def on_crd_updated(crd_instance, fabric):
        """
        Handle CRD update event - update GitOps tracking.
        
        Args:
            crd_instance: Updated CRD instance
            fabric: HedgehogFabric instance
        """
        try:
            integrator = CRDGitOpsIntegrator(fabric)
            integrator.sync_crd_to_gitops_resource(crd_instance)
            logger.info(f"CRD updated: {crd_instance} synced to GitOps tracking")
        except Exception as e:
            logger.error(f"Failed to sync updated CRD {crd_instance} to GitOps: {e}")
    
    @staticmethod
    def on_crd_deleted(crd_name: str, crd_kind: str, namespace: str, fabric):
        """
        Handle CRD deletion event - update GitOps tracking.
        
        Args:
            crd_name: Name of deleted CRD
            crd_kind: Kind of deleted CRD
            namespace: Namespace of deleted CRD
            fabric: HedgehogFabric instance
        """
        from netbox_hedgehog.models import HedgehogResource
        
        try:
            # Find corresponding GitOps resource
            resource = HedgehogResource.objects.filter(
                fabric=fabric,
                name=crd_name,
                kind=crd_kind,
                namespace=namespace
            ).first()
            
            if resource:
                # Clear actual state but keep desired state
                resource.actual_spec = None
                resource.actual_status = None
                resource.actual_resource_version = ''
                resource.actual_updated = timezone.now()
                resource.save()
                
                # Recalculate drift (should show as desired_only)
                resource.calculate_drift()
                
                logger.info(f"CRD deleted: {crd_kind}/{crd_name} GitOps tracking updated")
            
        except Exception as e:
            logger.error(f"Failed to handle CRD deletion {crd_kind}/{crd_name}: {e}")


def bulk_sync_fabric_to_gitops(fabric):
    """
    Convenience function to sync entire fabric to GitOps tracking.
    
    Args:
        fabric: HedgehogFabric instance
        
    Returns:
        Sync results dict
    """
    integrator = CRDGitOpsIntegrator(fabric)
    return integrator.sync_all_fabric_crds()


def get_fabric_gitops_status(fabric):
    """
    Get comprehensive GitOps status for a fabric.
    
    Args:
        fabric: HedgehogFabric instance
        
    Returns:
        Complete status dict
    """
    integrator = CRDGitOpsIntegrator(fabric)
    drift_summary = integrator.get_drift_summary()
    
    return {
        'fabric_status': fabric.get_gitops_summary(),
        'drift_summary': drift_summary,
        'git_config': {
            'configured': bool(fabric.git_repository_url),
            'repository': fabric.git_repository_url,
            'branch': fabric.git_branch,
            'last_sync': fabric.last_git_sync
        },
        'gitops_tool': {
            'tool': fabric.gitops_tool,
            'configured': fabric.gitops_tool != 'none' and bool(fabric.gitops_app_name)
        }
    }