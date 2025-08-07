import logging
import yaml
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User

from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering
from ..models.wiring_api import Connection, Server, Switch, SwitchGroup, VLANNamespace

logger = logging.getLogger(__name__)


class GitOpsEditService:
    """
    Service for handling CR edits with automatic Git workflow:
    Edit CR → Update YAML → Git commit/push → GitOps deploy
    """
    
    def __init__(self):
        self.supported_models = {
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
    
    def update_and_commit_cr(self, cr_instance, form_data: Dict[str, Any], user: User, 
                           commit_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point for editing a CR with automatic Git workflow:
        1. Save CR to database
        2. Update YAML file in Git repository
        3. Commit changes
        4. Push to remote
        """
        try:
            fabric = cr_instance.fabric
            cr_name = cr_instance.name
            model_name = cr_instance.__class__.__name__
            
            logger.info(f"Starting GitOps edit workflow for {model_name} {cr_name} in fabric {fabric.name}")
            
            result = {
                'success': False,
                'fabric_id': fabric.id,
                'fabric_name': fabric.name,
                'cr_name': cr_name,
                'cr_type': model_name,
                'workflow_steps': [],
                'started_at': timezone.now(),
                'user': user.username if user else 'system'
            }
            
            # Step 1: Save CR to database
            try:
                self._update_cr_instance(cr_instance, form_data)
                result['workflow_steps'].append({
                    'step': 'database_update',
                    'status': 'completed',
                    'message': f'Updated {model_name} {cr_name} in HNP database'
                })
            except Exception as e:
                logger.error(f"Failed to update CR in database: {str(e)}")
                result['workflow_steps'].append({
                    'step': 'database_update',
                    'status': 'failed',
                    'error': str(e)
                })
                result['error'] = f'Database update failed: {str(e)}'
                return result
            
            # Step 2: Update YAML file in Git repository
            if fabric.git_repository or fabric.git_repository_url:
                try:
                    yaml_result = self._update_cr_yaml_file(fabric, cr_instance)
                    result['workflow_steps'].append({
                        'step': 'yaml_update',
                        'status': 'completed',
                        'message': f'Updated YAML file: {yaml_result.get("file_path")}',
                        'file_path': yaml_result.get('file_path')
                    })
                    result['yaml_file_path'] = yaml_result.get('file_path')
                except Exception as e:
                    logger.error(f"Failed to update YAML file: {str(e)}")
                    result['workflow_steps'].append({
                        'step': 'yaml_update',
                        'status': 'failed',
                        'error': str(e)
                    })
                    result['error'] = f'YAML update failed: {str(e)}'
                    return result
                
                # Step 3: Commit and push changes
                try:
                    git_result = self._commit_and_push_changes(
                        fabric, cr_instance, commit_message, user
                    )
                    result['workflow_steps'].append({
                        'step': 'git_commit_push',
                        'status': 'completed',
                        'message': f'Committed and pushed changes: {git_result.get("commit_sha")}',
                        'commit_sha': git_result.get('commit_sha'),
                        'commit_message': git_result.get('commit_message')
                    })
                    result['commit_sha'] = git_result.get('commit_sha')
                    result['commit_message'] = git_result.get('commit_message')
                except Exception as e:
                    logger.error(f"Failed to commit/push changes: {str(e)}")
                    result['workflow_steps'].append({
                        'step': 'git_commit_push',
                        'status': 'failed',
                        'error': str(e)
                    })
                    result['error'] = f'Git commit/push failed: {str(e)}'
                    return result
            else:
                result['workflow_steps'].append({
                    'step': 'git_operations',
                    'status': 'skipped',
                    'message': 'No Git repository configured for this fabric'
                })
            
            # Step 4: Update CR with Git metadata
            try:
                cr_instance.last_synced = timezone.now()
                cr_instance.last_edited_by = user.username if user else 'system'
                cr_instance.save()
                
                result['workflow_steps'].append({
                    'step': 'metadata_update',
                    'status': 'completed',
                    'message': 'Updated CR metadata'
                })
            except Exception as e:
                logger.warning(f"Failed to update CR metadata: {str(e)}")
                result['workflow_steps'].append({
                    'step': 'metadata_update',
                    'status': 'warning',
                    'error': str(e)
                })
            
            result['success'] = True
            result['completed_at'] = timezone.now()
            result['message'] = f'Successfully updated {model_name} {cr_name} with GitOps workflow'
            
            logger.info(f"Completed GitOps edit workflow for {model_name} {cr_name}")
            return result
            
        except Exception as e:
            logger.error(f"GitOps edit workflow failed: {str(e)}")
            return {
                'success': False,
                'error': f'GitOps edit workflow failed: {str(e)}',
                'completed_at': timezone.now()
            }
    
    def _update_cr_instance(self, cr_instance, form_data: Dict[str, Any]):
        """Update the CR instance with form data"""
        # Update basic fields
        for field_name, value in form_data.items():
            if hasattr(cr_instance, field_name) and field_name not in ['id', 'fabric']:
                setattr(cr_instance, field_name, value)
        
        # Set GitOps metadata
        cr_instance.edited_in_gui = True
        cr_instance.last_gui_edit = timezone.now()
        
        cr_instance.save()
        logger.info(f"Updated {cr_instance.__class__.__name__} {cr_instance.name} in database")
    
    def _update_cr_yaml_file(self, fabric: HedgehogFabric, cr_instance) -> Dict[str, Any]:
        """
        Update the YAML file in the GitHub repository using GitHub API.
        
        CRITICAL FIX: This method now uses GitHub API directly instead of local file operations.
        This ensures changes are actually pushed to the remote repository.
        """
        try:
            # Import the new GitHub sync service
            from .github_sync_service import GitHubSyncService
            
            # Create GitHub service
            github_service = GitHubSyncService(fabric)
            
            # Sync CR to GitHub (handles file creation/update)
            result = github_service.sync_cr_to_github(
                cr_instance,
                operation='update',
                user='system'
            )
            
            if not result['success']:
                raise Exception(f"GitHub sync failed: {result.get('error', 'Unknown error')}")
            
            logger.info(f"Successfully updated YAML file in GitHub: {result.get('file_path')}")
            return {
                'success': True,
                'file_path': result.get('file_path'),
                'method': 'github_api_direct'
            }
                
        except Exception as e:
            logger.error(f"Failed to update YAML file in GitHub: {str(e)}")
            raise
    
    def _uses_new_gitops_structure(self, fabric: HedgehogFabric) -> bool:
        """Check if fabric uses the new GitOps file management structure."""
        return (
            hasattr(fabric, 'gitops_initialized') and 
            fabric.gitops_initialized and
            hasattr(fabric, 'managed_directory_path') and
            fabric.managed_directory_path
        )
    
    def _update_cr_in_managed_directory(self, fabric: HedgehogFabric, cr_instance) -> Dict[str, Any]:
        """
        Update CR in the managed/ directory structure (NEW SAFE METHOD).
        
        This method:
        1. Updates only single-document files in managed/ directory
        2. Never overwrites multi-document files
        3. Preserves all other objects
        """
        try:
            # Generate YAML content from CR instance
            yaml_content = self._generate_cr_yaml(cr_instance)
            
            # Determine managed file path
            managed_path = Path(fabric.managed_directory_path)
            file_path = self._get_managed_file_path(fabric, cr_instance, managed_path)
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write single-document YAML file (SAFE - only one object per file)
            with open(file_path, 'w') as f:
                f.write(yaml_content)
            
            # Update CR with file path
            relative_path = file_path.relative_to(managed_path.parent)
            cr_instance.git_file_path = str(relative_path)
            cr_instance.save()
            
            logger.info(f"SAFELY updated CR in managed file: {file_path}")
            return {
                'success': True,
                'file_path': str(relative_path),
                'full_path': str(file_path),
                'yaml_content': yaml_content,
                'method': 'managed_directory_safe_update'
            }
            
        except Exception as e:
            logger.error(f"Failed to update CR in managed directory: {str(e)}")
            raise
    
    def _get_managed_file_path(self, fabric: HedgehogFabric, cr_instance, managed_path: Path) -> Path:
        """Get the file path for a CR in the managed directory structure."""
        # Map CRD kind to directory
        kind_to_directory = {
            'VPC': 'vpcs',
            'External': 'externals',
            'ExternalAttachment': 'externalattachments',
            'ExternalPeering': 'externalpeerings',
            'IPv4Namespace': 'ipv4namespaces',
            'VPCAttachment': 'vpcattachments',
            'VPCPeering': 'vpcpeerings',
            'Connection': 'connections',
            'Server': 'servers',
            'Switch': 'switches',
            'SwitchGroup': 'switchgroups',
            'VLANNamespace': 'vlannamespaces'
        }
        
        kind = cr_instance.__class__.__name__
        directory = kind_to_directory.get(kind, kind.lower() + 's')
        
        # Generate filename
        namespace = cr_instance.namespace or fabric.kubernetes_namespace or 'default'
        if namespace and namespace != 'default':
            filename = f"{namespace}-{cr_instance.name}.yaml"
        else:
            filename = f"{cr_instance.name}.yaml"
        
        return managed_path / directory / filename
    
    def _legacy_update_cr_yaml_file(self, fabric: HedgehogFabric, cr_instance) -> Dict[str, Any]:
        """
        LEGACY method for updating YAML files (UNSAFE - but preserved for compatibility).
        
        WARNING: This method has the critical bug of overwriting entire files.
        It should only be used for fabrics that haven't been migrated to the new structure.
        """
        logger.warning(f"Using LEGACY (UNSAFE) YAML update for fabric {fabric.name} - consider migrating to new GitOps structure")
        
        try:
            # Check if the target file is multi-document
            file_path = self._get_cr_file_path(fabric, cr_instance)
            repo_path = self._get_git_repo_path(fabric)
            full_file_path = os.path.join(repo_path, file_path)
            
            # SAFETY CHECK: Don't overwrite multi-document files
            if os.path.exists(full_file_path):
                if self._is_multi_document_file(full_file_path):
                    raise Exception(
                        f"PREVENTED DATA LOSS: File {file_path} contains multiple documents. "
                        f"Use GitOps onboarding to migrate to safe file management structure."
                    )
            
            # Generate YAML content from CR instance
            yaml_content = self._generate_cr_yaml(cr_instance)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
            
            # Write YAML file (only if safe)
            with open(full_file_path, 'w') as f:
                f.write(yaml_content)
            
            # Update CR with file path
            cr_instance.git_file_path = file_path
            cr_instance.save()
            
            logger.warning(f"LEGACY update completed for: {file_path}")
            return {
                'success': True,
                'file_path': file_path,
                'full_path': full_file_path,
                'yaml_content': yaml_content,
                'method': 'legacy_update_with_safety_check'
            }
            
        except Exception as e:
            logger.error(f"Failed to update YAML file (legacy method): {str(e)}")
            raise
    
    def _is_multi_document_file(self, file_path: str) -> bool:
        """Check if a YAML file contains multiple documents."""
        try:
            with open(file_path, 'r') as f:
                documents = list(yaml.safe_load_all(f))
            
            # Filter out None/empty documents
            valid_documents = [doc for doc in documents if doc and isinstance(doc, dict)]
            return len(valid_documents) > 1
            
        except Exception as e:
            logger.warning(f"Could not check if file {file_path} is multi-document: {str(e)}")
            # Err on the side of caution
            return True
    
    def _generate_cr_yaml(self, cr_instance) -> str:
        """Generate Kubernetes YAML manifest from CR instance"""
        # Build Kubernetes manifest
        manifest = {
            'apiVersion': cr_instance.api_version or self._get_default_api_version(cr_instance),
            'kind': cr_instance.kind or cr_instance.__class__.__name__,
            'metadata': {
                'name': cr_instance.name,
                'namespace': cr_instance.namespace or cr_instance.fabric.kubernetes_namespace,
            }
        }
        
        # Add labels if present
        if cr_instance.labels:
            if isinstance(cr_instance.labels, str):
                manifest['metadata']['labels'] = json.loads(cr_instance.labels)
            else:
                manifest['metadata']['labels'] = cr_instance.labels
        
        # Add annotations if present
        if cr_instance.annotations:
            if isinstance(cr_instance.annotations, str):
                manifest['metadata']['annotations'] = json.loads(cr_instance.annotations)
            else:
                manifest['metadata']['annotations'] = cr_instance.annotations
        
        # Add spec if present
        if hasattr(cr_instance, 'spec') and cr_instance.spec:
            if isinstance(cr_instance.spec, str):
                manifest['spec'] = json.loads(cr_instance.spec)
            else:
                manifest['spec'] = cr_instance.spec
        
        # Convert to YAML
        yaml_content = yaml.dump(
            manifest, 
            default_flow_style=False, 
            sort_keys=True,
            allow_unicode=True
        )
        
        # Add header comment
        header = f"# {cr_instance.__class__.__name__}: {cr_instance.name}\n"
        header += f"# Generated by Hedgehog NetBox Plugin\n"
        header += f"# Last updated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        header += "---\n"
        
        return header + yaml_content
    
    def _get_default_api_version(self, cr_instance) -> str:
        """Get default API version for CR type"""
        model_name = cr_instance.__class__.__name__
        
        # VPC API CRDs
        vpc_api_models = ['VPC', 'External', 'ExternalAttachment', 'ExternalPeering', 
                         'IPv4Namespace', 'VPCAttachment', 'VPCPeering']
        if model_name in vpc_api_models:
            return 'hhnet.githedgehog.com/v1alpha1'
        
        # Wiring API CRDs
        wiring_api_models = ['Connection', 'Server', 'Switch', 'SwitchGroup', 'VLANNamespace']
        if model_name in wiring_api_models:
            return 'wiring.githedgehog.com/v1alpha1'
        
        # Default
        return 'v1'
    
    def _get_cr_file_path(self, fabric: HedgehogFabric, cr_instance) -> str:
        """Generate file path for CR YAML file"""
        model_name = cr_instance.__class__.__name__.lower()
        cr_name = cr_instance.name
        namespace = cr_instance.namespace or fabric.kubernetes_namespace
        
        # Use existing file path if available
        if cr_instance.git_file_path:
            return cr_instance.git_file_path
        
        # Generate new file path
        gitops_dir = fabric.gitops_directory or ''
        if gitops_dir and not gitops_dir.endswith('/'):
            gitops_dir += '/'
        
        return f"{gitops_dir}crds/{namespace}/{model_name}s/{cr_name}.yaml"
    
    def _get_git_repo_path(self, fabric: HedgehogFabric) -> str:
        """Get local path to Git repository"""
        # This would typically be configured in settings or determined dynamically
        # For now, use a temporary implementation
        repo_name = fabric.name.lower().replace(' ', '-').replace('_', '-')
        return f"/tmp/hedgehog-repos/{repo_name}"
    
    def _commit_and_push_changes(self, fabric: HedgehogFabric, cr_instance, 
                                commit_message: Optional[str], user: User) -> Dict[str, Any]:
        """Commit and push changes to GitHub repository using GitHub API"""
        try:
            # Import the new GitHub sync service
            from .github_sync_service import GitHubSyncService
            
            # Generate commit message if not provided
            if not commit_message:
                commit_message = self._generate_commit_message(cr_instance, user)
            
            # Create GitHub service
            github_service = GitHubSyncService(fabric)
            
            # Test connection first
            connection_test = github_service.test_connection()
            if not connection_test['success']:
                raise Exception(f"GitHub connection failed: {connection_test['error']}")
            
            # Sync CR to GitHub (this handles both create and update)
            result = github_service.sync_cr_to_github(
                cr_instance, 
                operation='update',
                user=user.username if user else 'system',
                commit_message=commit_message
            )
            
            if not result['success']:
                raise Exception(f"GitHub sync failed: {result.get('error', 'Unknown error')}")
            
            logger.info(f"Successfully synced to GitHub: {result.get('commit_sha', 'unknown')}")
            return {
                'success': True,
                'commit_sha': result.get('commit_sha', 'unknown'),
                'commit_message': commit_message,
                'github_operation': result
            }
            
        except Exception as e:
            logger.error(f"GitHub sync failed: {str(e)}")
            raise
    
    def _generate_commit_message(self, cr_instance, user: User) -> str:
        """Generate descriptive commit message for CR changes"""
        model_name = cr_instance.__class__.__name__
        cr_name = cr_instance.name
        user_name = user.username if user else 'system'
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        return (f"Update {model_name}: {cr_name}\n\n"
                f"Updated via Hedgehog NetBox Plugin GUI\n"
                f"User: {user_name}\n"
                f"Timestamp: {timestamp}")
    
    def validate_yaml_schema(self, yaml_content: str, cr_type: str) -> Dict[str, Any]:
        """Validate YAML content against Kubernetes schemas"""
        try:
            # Parse YAML
            manifest = yaml.safe_load(yaml_content)
            
            validation_result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'parsed_manifest': manifest
            }
            
            # Basic structure validation
            required_fields = ['apiVersion', 'kind', 'metadata']
            for field in required_fields:
                if field not in manifest:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f"Missing required field: {field}")
            
            # Validate metadata
            if 'metadata' in manifest:
                if 'name' not in manifest['metadata']:
                    validation_result['valid'] = False
                    validation_result['errors'].append("Missing metadata.name")
                
                # Check for valid name format (Kubernetes naming rules)
                if 'name' in manifest['metadata']:
                    name = manifest['metadata']['name']
                    if not isinstance(name, str) or len(name) == 0:
                        validation_result['valid'] = False
                        validation_result['errors'].append("metadata.name must be a non-empty string")
            
            # Validate spec if present
            if 'spec' in manifest and not isinstance(manifest['spec'], dict):
                validation_result['warnings'].append("spec should typically be an object")
            
            logger.info(f"YAML validation completed for {cr_type}: valid={validation_result['valid']}")
            return validation_result
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing failed: {str(e)}")
            return {
                'valid': False,
                'errors': [f'YAML parsing error: {str(e)}'],
                'warnings': []
            }
        except Exception as e:
            logger.error(f"YAML validation failed: {str(e)}")
            return {
                'valid': False,
                'errors': [f'Validation error: {str(e)}'],
                'warnings': []
            }
    
    def preview_yaml_changes(self, cr_instance, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Preview YAML changes without actually updating files"""
        try:
            # Create a temporary copy of the CR with form data
            temp_cr = cr_instance.__class__(**{
                field.name: getattr(cr_instance, field.name) 
                for field in cr_instance._meta.fields
            })
            
            # Apply form data to temp CR
            for field_name, value in form_data.items():
                if hasattr(temp_cr, field_name) and field_name not in ['id', 'fabric']:
                    setattr(temp_cr, field_name, value)
            
            # Generate YAML content
            new_yaml = self._generate_cr_yaml(temp_cr)
            current_yaml = self._generate_cr_yaml(cr_instance)
            
            # Compare changes
            changes_detected = new_yaml != current_yaml
            
            return {
                'success': True,
                'changes_detected': changes_detected,
                'current_yaml': current_yaml,
                'new_yaml': new_yaml,
                'preview_generated_at': timezone.now()
            }
            
        except Exception as e:
            logger.error(f"YAML preview failed: {str(e)}")
            return {
                'success': False,
                'error': f'YAML preview failed: {str(e)}'
            }