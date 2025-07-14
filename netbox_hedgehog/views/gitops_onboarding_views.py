"""
GitOps Onboarding Views for MVP2 Integration Phase

This module provides the backend integration for the Git-first onboarding wizard,
connecting the corrected UI to the functional backend models and utilities.
"""

import json
import logging
from typing import Dict, Any, Optional

from django.http import JsonResponse
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

from ..models import HedgehogFabric, HedgehogResource
from ..models.gitops import ResourceStateChoices, StateTransitionHistory
from ..utils.git_first_onboarding import GitFirstOnboardingWorkflow, GitRepositoryValidator
from ..utils.git_providers import GitProviderFactory
from ..utils.git_monitor import GitRepositoryMonitor
from ..utils.states import StateTransitionManager

logger = logging.getLogger(__name__)


class GitOpsOnboardingWizardView(LoginRequiredMixin, TemplateView):
    """
    Main onboarding wizard view that displays the UI and serves as the entry point
    for the Git-first onboarding process.
    """
    template_name = 'netbox_hedgehog/gitops_onboarding_wizard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['wizard_title'] = 'Git-First Fabric Onboarding'
        context['wizard_description'] = 'Create a new Hedgehog fabric with Git-first architecture'
        return context


@method_decorator(csrf_exempt, name='dispatch')
class GitConnectionTestView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for testing Git repository connections during onboarding.
    """
    
    def post(self, request, *args, **kwargs):
        """Test Git repository connection with provided credentials."""
        try:
            data = json.loads(request.body)
            
            # Extract connection parameters
            repository_url = data.get('url', '').strip()
            branch = data.get('branch', 'main').strip()
            path = data.get('path', 'hedgehog/').strip()
            auth_method = data.get('authMethod', 'token')
            provider = data.get('provider', 'github')
            
            # Validate required fields
            if not repository_url:
                return JsonResponse({
                    'success': False,
                    'error': 'Repository URL is required'
                }, status=400)
            
            # Extract authentication credentials
            access_token = None
            username = None
            
            if auth_method == 'token':
                access_token = data.get('token', '').strip()
                if not access_token:
                    return JsonResponse({
                        'success': False,
                        'error': 'Access token is required for token authentication'
                    }, status=400)
            elif auth_method == 'basic':
                username = data.get('username', '').strip()
                password = data.get('password', '').strip()
                if not username or not password:
                    return JsonResponse({
                        'success': False,
                        'error': 'Username and password are required for basic authentication'
                    }, status=400)
                access_token = password  # Use password as token for basic auth
            elif auth_method == 'ssh':
                # SSH authentication not implemented yet
                return JsonResponse({
                    'success': False,
                    'error': 'SSH authentication is not yet implemented'
                }, status=501)
            
            # Test repository connection
            validator = GitRepositoryValidator(repository_url, branch, path)
            repo_info = validator.validate_repository(access_token, username)
            
            # Prepare response
            response_data = {
                'success': not bool(repo_info.validation_errors),
                'repository_url': repository_url,
                'branch': branch,
                'path': path,
                'provider': provider,
                'accessible': repo_info.is_accessible,
                'has_hedgehog_directory': repo_info.has_hedgehog_directory,
                'discovered_resources': repo_info.discovered_resources,
                'repository_structure': repo_info.repository_structure,
                'validation_errors': repo_info.validation_errors or []
            }
            
            if response_data['success']:
                logger.info(f"Git connection test successful for {repository_url}")
                response_data['message'] = 'Repository connection successful'
            else:
                logger.warning(f"Git connection test failed for {repository_url}: {repo_info.validation_errors}")
                response_data['message'] = 'Repository connection failed'
                response_data['error'] = '; '.join(repo_info.validation_errors)
            
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Git connection test error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Connection test failed: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class YAMLDiscoveryView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for discovering YAML files in the Git repository.
    """
    
    def post(self, request, *args, **kwargs):
        """Discover YAML files in the Git repository."""
        try:
            data = json.loads(request.body)
            
            # Extract repository parameters
            repository_url = data.get('url', '').strip()
            branch = data.get('branch', 'main').strip()
            path = data.get('path', 'hedgehog/').strip()
            access_token = data.get('token', '').strip()
            username = data.get('username', '').strip()
            
            if not repository_url:
                return JsonResponse({
                    'success': False,
                    'error': 'Repository URL is required'
                }, status=400)
            
            # Validate repository and discover resources
            validator = GitRepositoryValidator(repository_url, branch, path)
            repo_info = validator.validate_repository(access_token, username)
            
            if repo_info.validation_errors:
                return JsonResponse({
                    'success': False,
                    'error': '; '.join(repo_info.validation_errors),
                    'validation_errors': repo_info.validation_errors
                }, status=400)
            
            # Prepare discovered resources with validation
            discovered_files = []
            for resource_path in repo_info.discovered_resources:
                # Determine resource type from path
                resource_type = 'Unknown'
                if 'vpc' in resource_path.lower():
                    resource_type = 'VPC'
                elif 'connection' in resource_path.lower():
                    resource_type = 'Connection'
                elif 'server' in resource_path.lower():
                    resource_type = 'Server'
                elif 'switch' in resource_path.lower():
                    resource_type = 'Switch'
                elif 'external' in resource_path.lower():
                    resource_type = 'External'
                elif 'namespace' in resource_path.lower():
                    resource_type = 'Namespace'
                
                discovered_files.append({
                    'name': resource_path,
                    'type': resource_type,
                    'valid': True,  # Basic validation for now
                    'path': resource_path
                })
            
            response_data = {
                'success': True,
                'repository_url': repository_url,
                'branch': branch,
                'path': path,
                'has_hedgehog_directory': repo_info.has_hedgehog_directory,
                'discovered_files': discovered_files,
                'total_files': len(discovered_files),
                'repository_structure': repo_info.repository_structure,
                'message': f'Discovered {len(discovered_files)} YAML files in repository'
            }
            
            logger.info(f"YAML discovery successful for {repository_url}: {len(discovered_files)} files found")
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"YAML discovery error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'YAML discovery failed: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class RepositoryInitializeView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for initializing repository structure.
    """
    
    def post(self, request, *args, **kwargs):
        """Initialize Git repository with Hedgehog directory structure."""
        try:
            data = json.loads(request.body)
            
            # Extract repository parameters
            repository_url = data.get('url', '').strip()
            branch = data.get('branch', 'main').strip()
            path = data.get('path', 'hedgehog/').strip()
            access_token = data.get('token', '').strip()
            
            if not repository_url:
                return JsonResponse({
                    'success': False,
                    'error': 'Repository URL is required'
                }, status=400)
            
            # Initialize repository structure
            workflow = GitFirstOnboardingWorkflow()
            result = workflow.initialize_repository(repository_url, branch, path, access_token)
            
            if result['success']:
                logger.info(f"Repository initialization successful for {repository_url}")
                return JsonResponse({
                    'success': True,
                    'message': result['message'],
                    'files_created': result['files_created'],
                    'repository_url': repository_url,
                    'branch': branch,
                    'path': path
                })
            else:
                logger.error(f"Repository initialization failed for {repository_url}: {result['errors']}")
                return JsonResponse({
                    'success': False,
                    'error': '; '.join(result['errors']),
                    'errors': result['errors']
                }, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Repository initialization error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Repository initialization failed: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class FabricCreationView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for creating a new fabric through the onboarding wizard.
    """
    
    def post(self, request, *args, **kwargs):
        """Create a new Hedgehog fabric with Git-first configuration."""
        try:
            data = json.loads(request.body)
            
            # Extract fabric configuration
            fabric_name = data.get('fabricName', '').strip()
            fabric_description = data.get('fabricDescription', '').strip()
            fabric_mode = data.get('fabricMode', 'git-first')
            
            # Extract repository configuration
            repository_url = data.get('repositoryUrl', '').strip()
            repository_branch = data.get('repositoryBranch', 'main').strip()
            repository_path = data.get('repositoryPath', 'hedgehog/').strip()
            
            # Extract authentication
            auth_method = data.get('authMethod', 'token')
            access_token = data.get('token', '').strip()
            username = data.get('username', '').strip()
            
            # Extract GitOps configuration
            target_namespace = data.get('targetNamespace', 'hedgehog-system').strip()
            gitops_tool = data.get('gitopsTools', 'manual')
            auto_create_namespace = data.get('autoCreateNamespace', True)
            
            # Validate required fields
            if not fabric_name:
                return JsonResponse({
                    'success': False,
                    'error': 'Fabric name is required'
                }, status=400)
            
            if not repository_url:
                return JsonResponse({
                    'success': False,
                    'error': 'Repository URL is required'
                }, status=400)
            
            # Check if fabric already exists
            if HedgehogFabric.objects.filter(name=fabric_name).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'Fabric with name "{fabric_name}" already exists'
                }, status=400)
            
            # Create fabric using Git-first workflow
            workflow = GitFirstOnboardingWorkflow()
            result = workflow.onboard_fabric(
                name=fabric_name,
                description=fabric_description,
                repository_url=repository_url,
                branch=repository_branch,
                path=repository_path,
                access_token=access_token,
                username=username,
                validate_only=False
            )
            
            if result.success:
                fabric = result.fabric
                
                # Update additional configuration
                if fabric:
                    fabric.kubernetes_namespace = target_namespace
                    fabric.gitops_tool = gitops_tool
                    fabric.save()
                
                logger.info(f"Fabric created successfully: {fabric_name}")
                
                response_data = {
                    'success': True,
                    'message': f'Fabric "{fabric_name}" created successfully',
                    'fabric_id': fabric.id if fabric else None,
                    'fabric_name': fabric_name,
                    'repository_url': repository_url,
                    'branch': repository_branch,
                    'path': repository_path,
                    'resources_discovered': len(result.discovered_resources),
                    'created_resources': result.created_resources,
                    'processing_time': result.processing_time,
                    'onboarding_metadata': result.onboarding_metadata
                }
                
                # Add redirect URL for UI
                response_data['redirect_url'] = f'/plugins/netbox_hedgehog/fabrics/{fabric.id}/' if fabric else '/plugins/netbox_hedgehog/fabrics/'
                
                return JsonResponse(response_data)
            else:
                logger.error(f"Fabric creation failed for {fabric_name}: {result.validation_errors}")
                return JsonResponse({
                    'success': False,
                    'error': '; '.join(result.validation_errors),
                    'validation_errors': result.validation_errors,
                    'warnings': result.warnings
                }, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Fabric creation error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Fabric creation failed: {str(e)}'
            }, status=500)


class GitOpsStatusView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for getting GitOps status of a fabric.
    """
    
    def get(self, request, fabric_id, *args, **kwargs):
        """Get GitOps status for a specific fabric."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
            
            # Get comprehensive GitOps status
            gitops_summary = fabric.get_gitops_summary()
            git_status = fabric.get_git_status()
            drift_status = fabric.calculate_drift_status()
            
            # Get resources summary
            resources = HedgehogResource.objects.filter(fabric=fabric)
            resource_stats = {
                'total': resources.count(),
                'draft': resources.filter(resource_state='draft').count(),
                'committed': resources.filter(resource_state='committed').count(),
                'synced': resources.filter(resource_state='synced').count(),
                'drifted': resources.filter(resource_state='drifted').count(),
                'orphaned': resources.filter(resource_state='orphaned').count(),
                'pending': resources.filter(resource_state='pending').count(),
            }
            
            response_data = {
                'success': True,
                'fabric_id': fabric.id,
                'fabric_name': fabric.name,
                'gitops_summary': gitops_summary,
                'git_status': git_status,
                'drift_status': drift_status,
                'resource_stats': resource_stats,
                'last_updated': fabric.last_updated.isoformat() if fabric.last_updated else None
            }
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"GitOps status error for fabric {fabric_id}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to get GitOps status: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class GitOpsSyncView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for triggering GitOps sync operations.
    """
    
    def post(self, request, fabric_id, *args, **kwargs):
        """Trigger GitOps sync for a specific fabric."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
            
            # Trigger sync from Git repository
            sync_result = fabric.sync_desired_state()
            
            if sync_result['success']:
                logger.info(f"GitOps sync successful for fabric {fabric.name}")
                return JsonResponse({
                    'success': True,
                    'message': 'GitOps sync completed successfully',
                    'fabric_id': fabric.id,
                    'fabric_name': fabric.name,
                    'sync_result': sync_result
                })
            else:
                logger.error(f"GitOps sync failed for fabric {fabric.name}: {sync_result.get('error', 'Unknown error')}")
                return JsonResponse({
                    'success': False,
                    'error': sync_result.get('error', 'GitOps sync failed'),
                    'fabric_id': fabric.id,
                    'fabric_name': fabric.name
                }, status=400)
            
        except Exception as e:
            logger.error(f"GitOps sync error for fabric {fabric_id}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'GitOps sync failed: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class StateTransitionView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for managing resource state transitions.
    """
    
    def post(self, request, *args, **kwargs):
        """Trigger state transition for a resource."""
        try:
            data = json.loads(request.body)
            
            # Extract parameters
            resource_id = data.get('resource_id')
            target_state = data.get('target_state')
            reason = data.get('reason', '')
            
            # Validate required fields
            if not resource_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Resource ID is required'
                }, status=400)
            
            if not target_state:
                return JsonResponse({
                    'success': False,
                    'error': 'Target state is required'
                }, status=400)
            
            # Get the resource
            try:
                resource = HedgehogResource.objects.get(id=resource_id)
            except HedgehogResource.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Resource not found'
                }, status=404)
            
            # Validate target state
            if target_state not in [choice[0] for choice in ResourceStateChoices.CHOICES]:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid target state: {target_state}'
                }, status=400)
            
            # Check if transition is valid
            state_manager = StateTransitionManager()
            if not state_manager.is_valid_transition(resource.resource_state, target_state):
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid transition from {resource.resource_state} to {target_state}'
                }, status=400)
            
            # Perform the transition
            current_state = resource.resource_state
            result = state_manager.transition_resource(resource, target_state, reason, request.user)
            
            if result.success:
                # Record the transition in history
                StateTransitionHistory.objects.create(
                    resource=resource,
                    from_state=current_state,
                    to_state=target_state,
                    trigger='manual',
                    reason=reason,
                    context={'user': request.user.username, 'method': 'api'},
                    user=request.user
                )
                
                logger.info(f"State transition successful for resource {resource.name}: {current_state} -> {target_state}")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Resource state changed from {current_state} to {target_state}',
                    'resource_id': resource.id,
                    'resource_name': resource.name,
                    'previous_state': current_state,
                    'new_state': target_state,
                    'transition_reason': reason
                })
            else:
                logger.error(f"State transition failed for resource {resource.name}: {result.error}")
                return JsonResponse({
                    'success': False,
                    'error': result.error
                }, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"State transition error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'State transition failed: {str(e)}'
            }, status=500)


class ResourceStateHistoryView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for getting resource state history.
    """
    
    def get(self, request, resource_id, *args, **kwargs):
        """Get state transition history for a resource."""
        try:
            resource = get_object_or_404(HedgehogResource, id=resource_id)
            
            # Get state transition history
            history = StateTransitionHistory.objects.filter(
                resource=resource
            ).order_by('-timestamp')[:20]  # Get last 20 transitions
            
            # Format history data
            history_data = []
            for transition in history:
                history_data.append({
                    'id': transition.id,
                    'from_state': transition.from_state,
                    'to_state': transition.to_state,
                    'trigger': transition.trigger,
                    'reason': transition.reason,
                    'timestamp': transition.timestamp.isoformat(),
                    'duration_display': transition.duration_display,
                    'user': transition.user.username if transition.user else 'System',
                    'context': transition.context,
                    'successful': transition.is_successful_transition,
                    'direction': transition.transition_direction
                })
            
            return JsonResponse({
                'success': True,
                'resource_id': resource.id,
                'resource_name': resource.name,
                'current_state': resource.resource_state,
                'history': history_data,
                'total_transitions': StateTransitionHistory.objects.filter(resource=resource).count()
            })
            
        except Exception as e:
            logger.error(f"Resource state history error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to get state history: {str(e)}'
            }, status=500)


class ValidTransitionsView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for getting valid state transitions for a resource.
    """
    
    def get(self, request, resource_id, *args, **kwargs):
        """Get valid state transitions for a resource."""
        try:
            resource = get_object_or_404(HedgehogResource, id=resource_id)
            
            # Get valid transitions
            state_manager = StateTransitionManager()
            valid_transitions = state_manager.get_valid_transitions(resource.resource_state)
            
            # Format transition data
            transitions_data = []
            for target_state in valid_transitions:
                transitions_data.append({
                    'target_state': target_state,
                    'target_state_display': dict(ResourceStateChoices.CHOICES).get(target_state, target_state),
                    'description': state_manager.get_transition_description(resource.resource_state, target_state),
                    'requirements': state_manager.get_transition_requirements(resource.resource_state, target_state)
                })
            
            return JsonResponse({
                'success': True,
                'resource_id': resource.id,
                'resource_name': resource.name,
                'current_state': resource.resource_state,
                'current_state_display': dict(ResourceStateChoices.CHOICES).get(resource.resource_state, resource.resource_state),
                'valid_transitions': transitions_data,
                'has_drift': resource.has_drift,
                'drift_status': resource.drift_status
            })
            
        except Exception as e:
            logger.error(f"Valid transitions error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to get valid transitions: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class BulkStateTransitionView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for bulk state transitions.
    """
    
    def post(self, request, *args, **kwargs):
        """Perform bulk state transitions for multiple resources."""
        try:
            data = json.loads(request.body)
            
            # Extract parameters
            resource_ids = data.get('resource_ids', [])
            target_state = data.get('target_state')
            reason = data.get('reason', '')
            
            # Validate required fields
            if not resource_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'Resource IDs are required'
                }, status=400)
            
            if not target_state:
                return JsonResponse({
                    'success': False,
                    'error': 'Target state is required'
                }, status=400)
            
            # Get the resources
            resources = HedgehogResource.objects.filter(id__in=resource_ids)
            
            if not resources.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'No resources found'
                }, status=404)
            
            # Validate target state
            if target_state not in [choice[0] for choice in ResourceStateChoices.CHOICES]:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid target state: {target_state}'
                }, status=400)
            
            # Perform transitions
            state_manager = StateTransitionManager()
            results = {
                'successful': [],
                'failed': [],
                'skipped': []
            }
            
            for resource in resources:
                try:
                    # Check if transition is valid
                    if not state_manager.is_valid_transition(resource.resource_state, target_state):
                        results['skipped'].append({
                            'resource_id': resource.id,
                            'resource_name': resource.name,
                            'current_state': resource.resource_state,
                            'reason': f'Invalid transition from {resource.resource_state} to {target_state}'
                        })
                        continue
                    
                    # Perform the transition
                    current_state = resource.resource_state
                    result = state_manager.transition_resource(resource, target_state, reason, request.user)
                    
                    if result.success:
                        # Record the transition in history
                        StateTransitionHistory.objects.create(
                            resource=resource,
                            from_state=current_state,
                            to_state=target_state,
                            trigger='bulk_manual',
                            reason=reason,
                            context={'user': request.user.username, 'method': 'bulk_api'},
                            user=request.user
                        )
                        
                        results['successful'].append({
                            'resource_id': resource.id,
                            'resource_name': resource.name,
                            'previous_state': current_state,
                            'new_state': target_state
                        })
                    else:
                        results['failed'].append({
                            'resource_id': resource.id,
                            'resource_name': resource.name,
                            'current_state': current_state,
                            'reason': result.error
                        })
                
                except Exception as e:
                    results['failed'].append({
                        'resource_id': resource.id,
                        'resource_name': resource.name,
                        'current_state': resource.resource_state,
                        'reason': str(e)
                    })
            
            logger.info(f"Bulk state transition completed: {len(results['successful'])} successful, {len(results['failed'])} failed, {len(results['skipped'])} skipped")
            
            return JsonResponse({
                'success': True,
                'message': f'Bulk transition completed: {len(results["successful"])} successful, {len(results["failed"])} failed, {len(results["skipped"])} skipped',
                'target_state': target_state,
                'results': results,
                'summary': {
                    'total_requested': len(resource_ids),
                    'successful': len(results['successful']),
                    'failed': len(results['failed']),
                    'skipped': len(results['skipped'])
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Bulk state transition error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Bulk state transition failed: {str(e)}'
            }, status=500)