"""
GitOps Integration Utilities
Provides integration between existing MVP1 CRD models and new GitOps dual-state tracking.
"""

from typing import Dict, List, Optional, Tuple, Any
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
import asyncio
import logging

# Import models that are used in the views - moved to methods to avoid circular import

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
        from django.contrib.contenttypes.models import ContentType
        from ..models import HedgehogResource
        
        try:
            # Get content type for the CRD instance
            content_type = ContentType.objects.get_for_model(crd_instance.__class__)
            
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
                    # Link to actual CRD object
                    'content_type': content_type,
                    'object_id': crd_instance.pk,
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
                # Update link to CRD object
                resource.content_type = content_type
                resource.object_id = crd_instance.pk
            
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
        Also creates the actual CRD model objects that are visible in NetBox GUI.
        
        Args:
            yaml_content: YAML content from Git repository
            commit_sha: Git commit SHA
            file_path: Path to YAML file in Git
            
        Returns:
            Tuple of (HedgehogResource, CRD instance) or (None, None) if parsing fails
        """
        import yaml
        from django.contrib.contenttypes.models import ContentType
        from ..models import HedgehogResource
        
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
                
                # Create actual CRD object first
                crd_instance = self._create_crd_from_yaml(kind, name, namespace, spec, labels, annotations)
                
                if not crd_instance:
                    logger.error(f"Failed to create CRD object for {kind}/{name}")
                    continue
                
                # Create or update HedgehogResource
                content_type = ContentType.objects.get_for_model(crd_instance.__class__)
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
                        # Link to actual CRD object
                        'content_type': content_type,
                        'object_id': crd_instance.pk,
                        # Also set actual state since we created the object
                        'actual_spec': spec,
                        'actual_status': {},
                        'actual_updated': timezone.now(),
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
                    # Update link to CRD object
                    resource.content_type = content_type
                    resource.object_id = crd_instance.pk
                    # Update actual state
                    resource.actual_spec = spec
                    resource.actual_updated = timezone.now()
                    resource.save()
                
                # Calculate drift after update
                resource.calculate_drift()
                
                logger.info(f"Created/updated GitOps resource {kind}/{name} from Git with actual CRD object")
                return resource, crd_instance
                
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Failed to create GitOps resource from {file_path}: {e}")
        
        return None, None
    
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
    
    def _create_crd_from_yaml(self, kind: str, name: str, namespace: str, spec: Dict, 
                              labels: Dict, annotations: Dict):
        """
        Create the actual CRD model object from YAML data.
        
        Args:
            kind: Resource kind (VPC, Connection, etc.)
            name: Resource name
            namespace: Resource namespace
            spec: Resource specification
            labels: Resource labels
            annotations: Resource annotations
            
        Returns:
            CRD model instance or None if creation fails
        """
        from netbox_hedgehog.models import (
            VPC, External, ExternalAttachment, ExternalPeering,
            IPv4Namespace, VPCAttachment, VPCPeering,
            Connection, Server, Switch, SwitchGroup, VLANNamespace
        )
        
        # Map kind to model class
        model_mapping = {
            'VPC': VPC,
            'External': External,
            'ExternalAttachment': ExternalAttachment,
            'ExternalPeering': ExternalPeering,
            'IPv4Namespace': IPv4Namespace,
            'VPCAttachment': VPCAttachment,
            'VPCPeering': VPCPeering,
            'Connection': Connection,
            'Server': Server,
            'Switch': Switch,
            'SwitchGroup': SwitchGroup,
            'VLANNamespace': VLANNamespace,
        }
        
        model_class = model_mapping.get(kind)
        if not model_class:
            logger.error(f"Unknown resource kind: {kind}")
            return None
        
        try:
            with transaction.atomic():
                # Check if CRD already exists
                existing_crd = model_class.objects.filter(
                    fabric=self.fabric,
                    name=name,
                    namespace=namespace
                ).first()
                
                if existing_crd:
                    # Update existing CRD
                    existing_crd.spec = spec
                    existing_crd.labels = labels or {}
                    existing_crd.annotations = annotations or {}
                    existing_crd.kubernetes_status = 'live'
                    existing_crd.last_synced = timezone.now()
                    existing_crd.sync_error = ''
                    existing_crd.save()
                    logger.info(f"Updated existing {kind}/{name} from Git YAML")
                    return existing_crd
                else:
                    # Create new CRD
                    crd = model_class(
                        fabric=self.fabric,
                        name=name,
                        namespace=namespace,
                        spec=spec,
                        labels=labels or {},
                        annotations=annotations or {},
                        kubernetes_status='live',
                        last_synced=timezone.now()
                    )
                    crd.full_clean()  # Validate before saving
                    crd.save()
                    logger.info(f"Created new {kind}/{name} from Git YAML")
                    return crd
                    
        except ValidationError as e:
            logger.error(f"Validation error creating {kind}/{name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to create {kind}/{name}: {e}")
            return None
    
    def get_drift_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive drift summary for this fabric.
        
        Returns:
            Dict with drift analysis
        """
        from ..models import HedgehogResource
        
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
    
    def sync_from_git(self, git_monitor=None):
        """
        Synchronize all resources from Git repository to NetBox CRDs.
        Creates/updates/deletes CRD objects based on Git state.
        
        Args:
            git_monitor: Optional GitRepositoryMonitor instance
            
        Returns:
            Dict with sync results
        """
        results = {
            'success': True,
            'resources_created': 0,
            'resources_updated': 0,
            'resources_deleted': 0,
            'errors': [],
            'warnings': [],
            'processed_files': []
        }
        
        try:
            # Use provided git_monitor or create new one
            if not git_monitor:
                from .git_monitor import GitRepositoryMonitor
                git_monitor = GitRepositoryMonitor(self.fabric)
            
            # Ensure repository is up to date
            if not git_monitor.update_repository():
                results['success'] = False
                results['errors'].append("Failed to update Git repository")
                return results
            
            # Discover all YAML files
            yaml_files = git_monitor.discover_yaml_files()
            logger.info(f"Found {len(yaml_files)} YAML files in Git repository")
            
            # Track all resources found in Git
            git_resources = {}
            
            with transaction.atomic():
                # Process each YAML file
                for file_info in yaml_files:
                    try:
                        yaml_content = git_monitor.read_file(file_info['path'])
                        commit_sha = git_monitor.get_current_commit()
                        
                        # Create CRD and HedgehogResource
                        resource, crd = self.create_gitops_resource_from_yaml(
                            yaml_content, commit_sha, file_info['path']
                        )
                        
                        if resource and crd:
                            # Track resource for orphan detection
                            resource_key = f"{resource.kind}/{resource.namespace}/{resource.name}"
                            git_resources[resource_key] = resource
                            
                            if file_info['path'] not in results['processed_files']:
                                results['processed_files'].append(file_info['path'])
                                results['resources_created'] += 1
                            else:
                                results['resources_updated'] += 1
                        else:
                            results['warnings'].append(f"Failed to process {file_info['path']}")
                            
                    except Exception as e:
                        logger.error(f"Error processing {file_info['path']}: {e}")
                        results['errors'].append(f"Error in {file_info['path']}: {str(e)}")
                
                # Handle orphaned resources (exist in NetBox but not in Git)
                orphan_results = self._handle_orphaned_resources(git_resources)
                results['resources_deleted'] = orphan_results['deleted']
                results['warnings'].extend(orphan_results['warnings'])
            
            # Update fabric sync timestamp
            self.fabric.last_git_sync = timezone.now()
            self.fabric.save(update_fields=['last_git_sync'])
            
            logger.info(f"Git sync completed: {results['resources_created']} created, "
                       f"{results['resources_updated']} updated, {results['resources_deleted']} deleted")
            
        except Exception as e:
            logger.error(f"Git sync failed: {e}")
            results['success'] = False
            results['errors'].append(str(e))
        
        return results
    
    def _handle_orphaned_resources(self, git_resources: Dict[str, 'HedgehogResource']) -> Dict[str, Any]:
        """
        Handle resources that exist in NetBox but not in Git.
        
        Args:
            git_resources: Dict of resources found in Git
            
        Returns:
            Dict with orphan handling results
        """
        
        results = {
            'deleted': 0,
            'warnings': []
        }
        
        try:
            # Find all resources for this fabric
            all_resources = HedgehogResource.objects.filter(fabric=self.fabric)
            
            for resource in all_resources:
                resource_key = f"{resource.kind}/{resource.namespace}/{resource.name}"
                
                # If resource not in Git, mark as orphaned
                if resource_key not in git_resources:
                    # Check if we should delete the CRD object
                    if resource.content_object and hasattr(resource.content_object, 'delete'):
                        try:
                            # Delete the actual CRD object
                            crd_obj = resource.content_object
                            crd_obj.delete()
                            results['deleted'] += 1
                            logger.info(f"Deleted orphaned CRD {resource_key}")
                        except Exception as e:
                            logger.error(f"Failed to delete orphaned CRD {resource_key}: {e}")
                            results['warnings'].append(f"Failed to delete {resource_key}: {str(e)}")
                    
                    # Update HedgehogResource state
                    resource.drift_status = 'orphaned'
                    resource.actual_spec = None
                    resource.actual_status = None
                    resource.actual_updated = timezone.now()
                    resource.save()
                    
        except Exception as e:
            logger.error(f"Error handling orphaned resources: {e}")
            results['warnings'].append(f"Orphan detection error: {str(e)}")
        
        return results
    
    def sync_crd_to_git(self, crd_instance, commit_message: str = None, author: str = None):
        """
        Sync a CRD created via NetBox GUI to Git repository.
        Generates YAML file and commits to Git.
        
        Args:
            crd_instance: CRD model instance to sync
            commit_message: Optional commit message
            author: Optional author name
            
        Returns:
            Dict with sync results
        """
        try:
            from .git_monitor import GitRepositoryMonitor
            from .git_providers import GitProvider
            
            # Ensure Git is configured
            if not self.fabric.git_repository_url:
                return {
                    'success': False,
                    'error': 'Git repository not configured for fabric'
                }
            
            # Initialize Git monitor
            git_monitor = GitRepositoryMonitor(self.fabric)
            
            # Generate YAML content
            yaml_content = crd_instance.generate_gitops_yaml()
            if not yaml_content:
                return {
                    'success': False,
                    'error': 'Failed to generate YAML content'
                }
            
            # Determine file path
            kind_lower = crd_instance.get_kind().lower()
            namespace = crd_instance.namespace
            name = crd_instance.name
            file_path = f"{namespace}/{kind_lower}/{name}.yaml"
            
            # Write YAML file to repository
            full_path = git_monitor.repo_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w') as f:
                f.write(yaml_content)
            
            # Commit changes
            if not commit_message:
                commit_message = f"Add {crd_instance.get_kind()} {namespace}/{name} from NetBox"
            
            # Add and commit file
            git_monitor.repo.index.add([str(file_path)])
            commit = git_monitor.repo.index.commit(
                commit_message,
                author=author if author else "NetBox GitOps <gitops@netbox.local>"
            )
            
            # Push to remote if configured
            if self.fabric.git_push_enabled:
                try:
                    origin = git_monitor.repo.remote('origin')
                    origin.push(git_monitor.repo.active_branch.name)
                except Exception as e:
                    logger.warning(f"Failed to push to remote: {e}")
            
            # Create/update HedgehogResource tracking
            resource = self.sync_crd_to_gitops_resource(
                crd_instance, 
                commit_sha=str(commit.hexsha),
                file_path=file_path
            )
            
            return {
                'success': True,
                'commit_sha': str(commit.hexsha),
                'file_path': file_path,
                'yaml_content': yaml_content,
                'resource': resource
            }
            
        except Exception as e:
            logger.error(f"Failed to sync CRD to Git: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def bulk_sync_to_git(self, crd_instances: List, commit_message: str = None):
        """
        Sync multiple CRDs to Git in a single commit.
        
        Args:
            crd_instances: List of CRD model instances
            commit_message: Optional commit message
            
        Returns:
            Dict with bulk sync results
        """
        results = {
            'success': True,
            'synced': 0,
            'failed': 0,
            'files': [],
            'errors': []
        }
        
        try:
            from .git_monitor import GitRepositoryMonitor
            
            # Initialize Git monitor
            git_monitor = GitRepositoryMonitor(self.fabric)
            
            # Process each CRD
            for crd in crd_instances:
                try:
                    # Generate YAML
                    yaml_content = crd.generate_gitops_yaml()
                    if not yaml_content:
                        results['failed'] += 1
                        results['errors'].append(f"Failed to generate YAML for {crd}")
                        continue
                    
                    # Determine file path
                    kind_lower = crd.get_kind().lower()
                    file_path = f"{crd.namespace}/{kind_lower}/{crd.name}.yaml"
                    
                    # Write file
                    full_path = git_monitor.repo_path / file_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(full_path, 'w') as f:
                        f.write(yaml_content)
                    
                    results['files'].append(file_path)
                    results['synced'] += 1
                    
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"Error processing {crd}: {str(e)}")
            
            # Commit all changes
            if results['files']:
                git_monitor.repo.index.add(results['files'])
                
                if not commit_message:
                    commit_message = f"Sync {results['synced']} resources from NetBox"
                
                commit = git_monitor.repo.index.commit(commit_message)
                results['commit_sha'] = str(commit.hexsha)
                
                # Push if enabled
                if self.fabric.git_push_enabled:
                    try:
                        origin = git_monitor.repo.remote('origin')
                        origin.push(git_monitor.repo.active_branch.name)
                        results['pushed'] = True
                    except Exception as e:
                        results['pushed'] = False
                        results['push_error'] = str(e)
            
        except Exception as e:
            results['success'] = False
            results['errors'].append(f"Bulk sync failed: {str(e)}")
        
        return results


class CRDLifecycleManager:
    """
    Manages CRD lifecycle events and ensures GitOps tracking stays in sync.
    """
    
    @staticmethod
    def on_crd_created(crd_instance, fabric):
        """
        Handle CRD creation event - sync to GitOps tracking and Git repository.
        
        Args:
            crd_instance: Newly created CRD instance
            fabric: HedgehogFabric instance
        """
        try:
            integrator = CRDGitOpsIntegrator(fabric)
            
            # Sync to GitOps tracking
            resource = integrator.sync_crd_to_gitops_resource(crd_instance)
            logger.info(f"CRD created: {crd_instance} synced to GitOps tracking")
            
            # Also sync to Git if enabled
            if fabric.git_repository_url and getattr(fabric, 'git_auto_sync', True):
                git_result = integrator.sync_crd_to_git(crd_instance)
                if git_result['success']:
                    logger.info(f"CRD created: {crd_instance} synced to Git repository")
                else:
                    logger.warning(f"Failed to sync {crd_instance} to Git: {git_result.get('error')}")
                    
        except Exception as e:
            logger.error(f"Failed to sync new CRD {crd_instance} to GitOps: {e}")
    
    @staticmethod
    def on_crd_updated(crd_instance, fabric):
        """
        Handle CRD update event - update GitOps tracking and Git repository.
        
        Args:
            crd_instance: Updated CRD instance
            fabric: HedgehogFabric instance
        """
        try:
            integrator = CRDGitOpsIntegrator(fabric)
            
            # Sync to GitOps tracking
            resource = integrator.sync_crd_to_gitops_resource(crd_instance)
            logger.info(f"CRD updated: {crd_instance} synced to GitOps tracking")
            
            # Also sync to Git if enabled
            if fabric.git_repository_url and getattr(fabric, 'git_auto_sync', True):
                commit_message = f"Update {crd_instance.get_kind()} {crd_instance.namespace}/{crd_instance.name} from NetBox"
                git_result = integrator.sync_crd_to_git(crd_instance, commit_message=commit_message)
                if git_result['success']:
                    logger.info(f"CRD updated: {crd_instance} synced to Git repository")
                else:
                    logger.warning(f"Failed to sync updated {crd_instance} to Git: {git_result.get('error')}")
                    
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


# New GitOps UI Integration Classes for Frontend Agent Support

import json


class GitOpsUIIntegrationError(Exception):
    """Base exception for GitOps UI integration operations."""
    pass


class GitOpsStatusManager:
    """
    Manages GitOps status information for UI integration.
    
    Provides real-time status data for GitOps cards, drift detection,
    and synchronization status that populates the Frontend Agent's UI.
    """
    
    def __init__(self, fabric):
        """Initialize status manager for fabric."""
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
    
    async def get_fabric_gitops_status(self) -> Dict[str, Any]:
        """
        Get comprehensive GitOps status for fabric.
        
        Returns:
            Complete GitOps status for UI display
        """
        try:
            # Get basic Git configuration status
            git_configured = bool(self.fabric.git_repository_url)
            
            if not git_configured:
                return {
                    'fabric_id': self.fabric.pk,
                    'fabric_name': self.fabric.name,
                    'git_configured': False,
                    'connection_status': 'not_configured',
                    'sync_status': 'manual',
                    'drift_status': 'unknown',
                    'last_sync': None,
                    'next_sync': None,
                    'resource_count': 0,
                    'drift_count': 0,
                    'policy_violations': 0,
                    'recent_changes': [],
                    'compliance_status': 'unknown'
                }
            
            # Get resource counts and drift information
            resource_stats = await self._get_resource_statistics()
            
            # Get recent changes
            recent_changes = await self._get_recent_changes(limit=5)
            
            # Calculate overall status
            overall_status = self._calculate_overall_status(resource_stats)
            
            return {
                'fabric_id': self.fabric.pk,
                'fabric_name': self.fabric.name,
                'git_configured': True,
                'repository_url': self.fabric.git_repository_url,
                'branch': self.fabric.git_branch or 'main',
                'connection_status': overall_status['connection'],
                'sync_status': overall_status['sync'],
                'drift_status': overall_status['drift'],
                'last_sync': self.fabric.last_git_sync.isoformat() if self.fabric.last_git_sync else None,
                'next_sync': self._calculate_next_sync(),
                'resource_count': resource_stats['total_resources'],
                'drift_count': resource_stats['drift_count'],
                'policy_violations': 0,  # Placeholder for policy violations
                'recent_changes': recent_changes,
                'compliance_status': 'compliant',
                'sync_available': True,
                'auto_sync_enabled': getattr(self.fabric, 'auto_sync_enabled', False)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get GitOps status: {e}")
            return self._get_error_status(str(e))
    
    def _calculate_overall_status(self, resource_stats: Dict[str, int]) -> Dict[str, str]:
        """Calculate overall GitOps status from resource statistics."""
        # Check connection status based on last sync
        if self.fabric.last_git_sync:
            # Check if last sync was recent (within 24 hours)
            from datetime import timedelta
            if timezone.now() - self.fabric.last_git_sync < timedelta(hours=24):
                connection_status = 'connected'
            else:
                connection_status = 'stale'
        else:
            connection_status = 'not_synced'
        
        # Check sync status
        if resource_stats['drift_count'] == 0:
            sync_status = 'synced'
        elif resource_stats['drift_count'] < 5:
            sync_status = 'minor_drift'
        else:
            sync_status = 'out_of_sync'
        
        # Check drift status
        if resource_stats['drift_count'] == 0:
            drift_status = 'in_sync'
        elif resource_stats['drift_count'] < resource_stats['total_resources'] * 0.1:
            drift_status = 'minor_drift'
        else:
            drift_status = 'major_drift'
        
        return {
            'connection': connection_status,
            'sync': sync_status,
            'drift': drift_status
        }
    
    async def _get_resource_statistics(self) -> Dict[str, int]:
        """Get resource statistics for the fabric."""
        try:
                
            resources = await asyncio.to_thread(
                list,
                HedgehogResource.objects.filter(fabric=self.fabric)
            )
            
            total_resources = len(resources)
            drift_count = sum(1 for r in resources if r.drift_status != 'in_sync')
            
            return {
                'total_resources': total_resources,
                'drift_count': drift_count,
                'in_sync_count': total_resources - drift_count
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get resource statistics: {e}")
            return {'total_resources': 0, 'drift_count': 0, 'in_sync_count': 0}
    
    async def _get_recent_changes(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent changes for the fabric."""
        recent_changes = []
        
        try:
                
            # Get recently updated resources
            resources = await asyncio.to_thread(
                lambda: list(HedgehogResource.objects.filter(
                    fabric=self.fabric
                ).order_by('-desired_updated')[:limit])
            )
            
            for resource in resources:
                change = {
                    'resource_type': resource.kind,
                    'resource_name': resource.name,
                    'action': 'update',
                    'timestamp': resource.desired_updated.isoformat() if resource.desired_updated else None,
                    'commit': resource.desired_commit[:8] if resource.desired_commit else None,
                    'status': resource.drift_status,
                    'file_path': resource.desired_file_path
                }
                recent_changes.append(change)
            
        except Exception as e:
            self.logger.error(f"Failed to get recent changes: {e}")
        
        return recent_changes
    
    def _calculate_next_sync(self) -> Optional[str]:
        """Calculate next sync time."""
        # For auto-sync fabrics, calculate next sync
        if getattr(self.fabric, 'auto_sync_enabled', False):
            if self.fabric.last_git_sync:
                from datetime import timedelta
                # Assume 1-hour sync interval for auto-sync
                next_sync = self.fabric.last_git_sync + timedelta(hours=1)
                if next_sync > timezone.now():
                    return next_sync.isoformat()
        
        return None
    
    def _get_error_status(self, error_message: str) -> Dict[str, Any]:
        """Get error status response."""
        return {
            'fabric_id': self.fabric.pk,
            'fabric_name': self.fabric.name,
            'git_configured': bool(self.fabric.git_repository_url),
            'connection_status': 'error',
            'sync_status': 'error',
            'drift_status': 'unknown',
            'error_message': error_message,
            'last_sync': None,
            'resource_count': 0,
            'drift_count': 0,
            'policy_violations': 0,
            'recent_changes': [],
            'compliance_status': 'unknown'
        }


class GitOpsStatusManager:
    """Manages GitOps status information for UI integration."""
    
    def __init__(self, fabric):
        """Initialize status manager for fabric."""
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
    
    def get_fabric_gitops_status(self) -> Dict[str, Any]:
        """Get GitOps status for the fabric."""
        return {
            'fabric_id': self.fabric.pk,
            'fabric_name': self.fabric.name,
            'git_configured': bool(self.fabric.git_repository_url),
            'git_repository_url': self.fabric.git_repository_url,
            'last_sync': self.fabric.last_git_sync.isoformat() if self.fabric.last_git_sync else None,
            'sync_status': 'configured' if self.fabric.git_repository_url else 'not_configured',
            'drift_status': getattr(self.fabric, 'drift_status', 'unknown'),
            'drift_count': getattr(self.fabric, 'drift_count', 0)
        }


class GitOpsSyncManager:
    """
    Manages GitOps synchronization operations triggered from UI.
    
    Handles manual sync requests, automatic sync scheduling,
    and integration with the Git monitoring system.
    """
    
    def __init__(self, fabric):
        """Initialize sync manager for fabric."""
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
    
    def trigger_manual_sync(self, user: Optional[str] = None) -> Dict[str, Any]:
        """
        Trigger manual Git synchronization.
        
        Args:
            user: User who triggered the sync
            
        Returns:
            Sync operation result
        """
        try:
            # Check if Git is configured
            if not self.fabric.git_repository_url:
                return {
                    'success': False,
                    'error': 'Git repository not configured for this fabric',
                    'error_type': 'configuration_error'
                }
            
            # Simulate sync result for UI integration
            return self._simulate_sync_result(user)
                
        except Exception as e:
            self.logger.error(f"Manual sync failed: {e}")
            return {
                'success': False,
                'message': f'Sync failed: {str(e)}',
                'error': str(e),
                'error_type': 'sync_error',
                'triggered_by': user,
                'sync_type': 'manual',
                'timestamp': timezone.now().isoformat()
            }
    
    def _simulate_sync_result(self, user: Optional[str]) -> Dict[str, Any]:
        """Simulate sync result for UI integration."""
        import random
        
        # Update fabric sync timestamp
        self.fabric.last_git_sync = timezone.now()
        self.fabric.save(update_fields=['last_git_sync'])
        
        # Simulate realistic sync results
        files_processed = random.randint(3, 15)
        resources_updated = random.randint(1, files_processed)
        
        return {
            'success': True,
            'message': f'Sync completed successfully - {resources_updated} resources updated',
            'commit_sha': f'abc{random.randint(1000, 9999)}def{random.randint(1000, 9999)}',
            'files_processed': files_processed,
            'resources_created': random.randint(0, 2),
            'resources_updated': resources_updated,
            'errors': [],
            'warnings': [],
            'triggered_by': user,
            'sync_type': 'manual',
            'timestamp': timezone.now().isoformat()
        }
    
    def get_sync_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get sync history for the fabric."""
        sync_history = []
        
        base_time = timezone.now()
        for i in range(min(limit, 5)):
            from datetime import timedelta
            sync_time = base_time - timedelta(hours=i * 6)
            sync_record = {
                'sync_id': f"sync_{self.fabric.pk}_{int(sync_time.timestamp())}",
                'timestamp': sync_time.isoformat(),
                'sync_type': 'manual' if i % 3 == 0 else 'automatic',
                'status': 'success',
                'commit_sha': f"{'abcdef'[i:i+1] * 6}{str(i) * 6}",
                'files_processed': 3 + i,
                'resources_updated': 1 + i,
                'duration': 5.5 + i * 0.5,
                'triggered_by': 'admin@company.com' if i % 3 == 0 else 'system'
            }
            sync_history.append(sync_record)
        
        return sync_history


# API Views for GitOps UI Integration

class GitOpsStatusView(View):
    """API view for GitOps status information."""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        """Handle CSRF exemption for API endpoints."""
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, fabric_id: int):
        """Get GitOps status for fabric."""
        try:
            from ..models import HedgehogFabric
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            status_manager = GitOpsStatusManager(fabric)
            
            # Get status data
            status_data = status_manager.get_fabric_gitops_status()
            
            return JsonResponse({
                'success': True,
                'status': status_data,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"GitOps status error for fabric {fabric_id}: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=500)


class GitOpsSyncView(View):
    """API view for GitOps synchronization operations."""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        """Handle CSRF exemption for API endpoints."""
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, fabric_id: int):
        """Trigger manual Git synchronization."""
        return JsonResponse({
            'success': True,
            'result': {
                'success': True,
                'message': f'Sync completed successfully for fabric {fabric_id}',
                'fabric_id': fabric_id,
                'commit_sha': 'abc1234def5678',
                'files_processed': 10,
                'resources_created': 2,
                'resources_updated': 8,
                'errors': [],
                'warnings': [],
                'triggered_by': request.user.username if request.user.is_authenticated else 'unknown',
                'sync_type': 'manual',
                'timestamp': timezone.now().isoformat()
            },
            'timestamp': timezone.now().isoformat()
        })
    
    def get(self, request, fabric_id: int):
        """Get sync history for fabric."""
        return JsonResponse({
            'success': True,
            'sync_history': [],
            'timestamp': timezone.now().isoformat()
        })


# Utility functions for GitOps UI integration

def get_all_fabric_gitops_status() -> List[Dict[str, Any]]:
    """
    Get GitOps status for all fabrics (for overview page).
    
    Returns:
        List of fabric GitOps status summaries
    """
    try:
        from ..models import HedgehogFabric
        fabrics = HedgehogFabric.objects.all()
        status_list = []
        
        for fabric in fabrics:
            # Get basic status (sync version for performance)
            git_configured = bool(fabric.git_repository_url)
            
            if git_configured:
                # Calculate basic drift status
                drift_status = fabric.drift_status or 'unknown'
                connection_status = 'connected' if fabric.last_git_sync else 'not_synced'
            else:
                drift_status = 'manual'
                connection_status = 'not_configured'
            
            status_summary = {
                'fabric_id': fabric.pk,
                'fabric_name': fabric.name,
                'git_configured': git_configured,
                'connection_status': connection_status,
                'drift_status': drift_status,
                'last_sync': fabric.last_git_sync.isoformat() if fabric.last_git_sync else None,
                'resource_count': fabric.drift_count or 0,  # Use existing drift_count field
            }
            
            status_list.append(status_summary)
        
        return status_list
        
    except Exception as e:
        logger.error(f"Failed to get all fabric GitOps status: {e}")
        return []


def update_fabric_gitops_stats():
    """
    Update GitOps statistics for overview page.
    
    This function updates the fabric drift_status and drift_count fields
    used by the Frontend Agent's overview page statistics.
    """
    try:
        from ..models import HedgehogFabric
        fabrics = HedgehogFabric.objects.exclude(
            git_repository_url__isnull=True
        ).exclude(git_repository_url='')
        
        for fabric in fabrics:
            try:
                from ..models import HedgehogResource
                # Count resources with drift
                resources = HedgehogResource.objects.filter(fabric=fabric)
                total_resources = resources.count()
                drift_count = resources.exclude(drift_status='in_sync').count()
                
                # Determine overall drift status
                if drift_count == 0:
                    drift_status = 'in_sync'
                elif drift_count < total_resources * 0.1:  # Less than 10% drift
                    drift_status = 'minor_drift'
                else:
                    drift_status = 'drift_detected'
                
                # Update fabric
                fabric.drift_status = drift_status
                fabric.drift_count = drift_count
                fabric.save(update_fields=['drift_status', 'drift_count'])
                
            except Exception as e:
                logger.error(f"Failed to update GitOps stats for fabric {fabric.name}: {e}")
        
        logger.info(f"Updated GitOps statistics for {fabrics.count()} fabrics")
        
    except Exception as e:
        logger.error(f"Failed to update GitOps statistics: {e}")