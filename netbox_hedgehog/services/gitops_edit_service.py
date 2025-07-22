import logging
import yaml
import os
import json
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
        """Update the YAML file in the Git repository"""
        try:
            # Generate YAML content from CR instance
            yaml_content = self._generate_cr_yaml(cr_instance)
            
            # Determine file path
            file_path = self._get_cr_file_path(fabric, cr_instance)
            
            # Get Git repository path
            repo_path = self._get_git_repo_path(fabric)
            full_file_path = os.path.join(repo_path, file_path)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
            
            # Write YAML file
            with open(full_file_path, 'w') as f:
                f.write(yaml_content)
            
            # Update CR with file path
            cr_instance.git_file_path = file_path
            cr_instance.save()
            
            logger.info(f"Updated YAML file: {file_path}")
            return {
                'success': True,
                'file_path': file_path,
                'full_path': full_file_path,
                'yaml_content': yaml_content
            }
            
        except Exception as e:
            logger.error(f"Failed to update YAML file: {str(e)}")
            raise
    
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
        """Commit and push changes to Git repository"""
        try:
            import subprocess
            
            repo_path = self._get_git_repo_path(fabric)
            
            # Generate commit message if not provided
            if not commit_message:
                commit_message = self._generate_commit_message(cr_instance, user)
            
            # Git operations
            git_commands = [
                ['git', 'add', '.'],
                ['git', 'commit', '-m', commit_message],
                ['git', 'push', 'origin', fabric.git_branch or 'main']
            ]
            
            results = []
            for cmd in git_commands:
                result = subprocess.run(
                    cmd, 
                    cwd=repo_path, 
                    capture_output=True, 
                    text=True
                )
                results.append({
                    'command': ' '.join(cmd),
                    'returncode': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                })
                
                if result.returncode != 0:
                    raise Exception(f"Git command failed: {' '.join(cmd)}, Error: {result.stderr}")
            
            # Get commit SHA
            sha_result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'], 
                cwd=repo_path, 
                capture_output=True, 
                text=True
            )
            commit_sha = sha_result.stdout.strip() if sha_result.returncode == 0 else 'unknown'
            
            logger.info(f"Successfully committed and pushed changes: {commit_sha}")
            return {
                'success': True,
                'commit_sha': commit_sha,
                'commit_message': commit_message,
                'git_operations': results
            }
            
        except Exception as e:
            logger.error(f"Git commit/push failed: {str(e)}")
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