"""
Fabric Overview Views
Main dashboard and fabric management views for the Hedgehog plugin.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from datetime import datetime
import json

# NetBox imports
from netbox.views import generic
from utilities.views import ViewTab, register_model_view
from utilities.permissions import get_permission_for_model

# Plugin imports  
from ..models import HedgehogFabric
from ..models.vpc_api import VPC, IPv4Namespace
from ..models.wiring_api import Switch, Connection, VLANNamespace
from ..utils.fabric_onboarding import FabricOnboardingManager
from ..utils.reconciliation import ReconciliationManager
from ..choices import KubernetesStatusChoices
from ..tables import FabricTable


@method_decorator(login_required, name='dispatch')
class FabricOverviewView(View):
    """Main fabric overview dashboard"""
    
    template_name = 'netbox_hedgehog/fabric_overview.html'
    
    def get(self, request):
        """Display fabric overview dashboard"""
        
        # Get all fabrics
        fabrics = HedgehogFabric.objects.all()
        
        # Calculate summary statistics
        fabric_stats = []
        total_stats = {
            'fabrics': fabrics.count(),
            'switches': 0,
            'connections': 0,
            'vpcs': 0,
            'healthy_fabrics': 0,
            'syncing_fabrics': 0,
            'error_fabrics': 0
        }
        
        for fabric in fabrics:
            # Get resource counts for this fabric
            switches = Switch.objects.filter(fabric=fabric)
            connections = Connection.objects.filter(fabric=fabric)
            vpcs = VPC.objects.filter(fabric=fabric)
            
            # Calculate fabric health
            if fabric.sync_status == 'synced':
                health = 'healthy'
                total_stats['healthy_fabrics'] += 1
            elif fabric.sync_status == 'syncing':
                health = 'syncing'
                total_stats['syncing_fabrics'] += 1
            else:
                health = 'error'
                total_stats['error_fabrics'] += 1
            
            fabric_info = {
                'fabric': fabric,
                'health': health,
                'switch_count': switches.count(),
                'connection_count': connections.count(),
                'vpc_count': vpcs.count(),
                'last_sync': fabric.last_sync,
                'cluster_version': fabric.cluster_info.get('version', 'Unknown') if fabric.cluster_info else 'Unknown'
            }
            fabric_stats.append(fabric_info)
            
            # Add to totals
            total_stats['switches'] += fabric_info['switch_count']
            total_stats['connections'] += fabric_info['connection_count']
            total_stats['vpcs'] += fabric_info['vpc_count']
        
        # Recent activity (mock for now)
        recent_activities = [
            {
                'timestamp': datetime.now(),
                'fabric': fabrics.first().name if fabrics.exists() else 'Demo Fabric',
                'action': 'VPC Created',
                'resource': 'production-vpc',
                'user': request.user.username,
                'source': 'netbox'
            }
        ]
        
        context = {
            'fabric_stats': fabric_stats,
            'total_stats': total_stats,
            'recent_activities': recent_activities,
            'can_add_fabric': request.user.has_perm('netbox_hedgehog.add_hedgehogfabric'),
            'can_change_fabric': request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'),
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class FabricDetailView(View):
    """Detailed view of a specific fabric"""
    
    template_name = 'netbox_hedgehog/fabric_detail.html'
    
    def get(self, request, pk):
        """Display fabric details"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        # Get resource counts
        switches = Switch.objects.filter(fabric=fabric)
        connections = Connection.objects.filter(fabric=fabric)
        vpcs = VPC.objects.filter(fabric=fabric)
        ipv4_namespaces = IPv4Namespace.objects.filter(fabric=fabric)
        vlan_namespaces = VLANNamespace.objects.filter(fabric=fabric)
        
        # Group switches by role
        switches_by_role = {}
        for switch in switches:
            role = switch.role or 'unknown'
            if role not in switches_by_role:
                switches_by_role[role] = []
            switches_by_role[role].append(switch)
        
        # Recent changes for this fabric
        recent_changes = []  # Would be populated from audit log
        
        # Connection test status
        connection_test = {
            'status': fabric.sync_status,
            'last_test': fabric.last_sync,
            'cluster_version': fabric.cluster_info.get('version') if fabric.cluster_info else None,
            'namespace_count': fabric.cluster_info.get('namespace_count') if fabric.cluster_info else None
        }
        
        context = {
            'fabric': fabric,
            'switches': switches,
            'connections': connections,
            'vpcs': vpcs,
            'ipv4_namespaces': ipv4_namespaces,
            'vlan_namespaces': vlan_namespaces,
            'switches_by_role': switches_by_role,
            'recent_changes': recent_changes,
            'connection_test': connection_test,
            'can_change': request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'),
            'can_delete': request.user.has_perm('netbox_hedgehog.delete_hedgehogfabric'),
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class FabricTestConnectionView(View):
    """Test connection to a fabric's Kubernetes cluster"""
    
    def post(self, request, pk):
        """Test the Kubernetes connection"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        if not request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        try:
            onboarding_manager = FabricOnboardingManager(fabric)
            success, message, cluster_info = onboarding_manager.validate_kubernetes_connection()
            
            if success:
                # Update fabric with cluster info
                fabric.cluster_info = cluster_info
                fabric.sync_status = 'synced'
                fabric.last_sync = datetime.now()
                fabric.save()
                
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'cluster_info': cluster_info
                })
            else:
                fabric.sync_status = 'error'
                fabric.save()
                
                return JsonResponse({
                    'success': False,
                    'error': message
                })
                
        except Exception as e:
            fabric.sync_status = 'error'
            fabric.save()
            
            return JsonResponse({
                'success': False,
                'error': f'Connection test failed: {str(e)}'
            })


@method_decorator(login_required, name='dispatch')
class FabricSyncView(View):
    """Trigger reconciliation for a fabric"""
    
    def post(self, request, pk):
        """Perform reconciliation sync"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        if not request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        try:
            reconciliation_manager = ReconciliationManager(fabric)
            result = reconciliation_manager.perform_reconciliation(dry_run=False)
            
            if result['initialization_success']:
                messages.success(request, f"Reconciliation completed for fabric '{fabric.name}'")
                
                # Extract summary information
                actions = result.get('actions_taken', {})
                summary = f"Imported: {actions.get('imported_to_netbox', 0)}, Applied: {actions.get('applied_to_cluster', 0)}"
                
                return JsonResponse({
                    'success': True,
                    'message': f'Reconciliation completed. {summary}',
                    'results': result
                })
            else:
                messages.error(request, f"Reconciliation failed for fabric '{fabric.name}'")
                return JsonResponse({
                    'success': False,
                    'error': 'Reconciliation failed to initialize',
                    'results': result
                })
                
        except Exception as e:
            messages.error(request, f"Reconciliation error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Reconciliation failed: {str(e)}'
            })


@method_decorator(login_required, name='dispatch')
class FabricOnboardingView(View):
    """Onboard a new fabric"""
    
    template_name = 'netbox_hedgehog/fabric_onboarding.html'
    
    def get(self, request, pk):
        """Display onboarding interface"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        # Generate service account YAML
        onboarding_manager = FabricOnboardingManager(fabric)
        service_account_yaml = onboarding_manager.generate_service_account_yaml()
        
        context = {
            'fabric': fabric,
            'service_account_yaml': service_account_yaml,
            'can_change': request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'),
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request, pk):
        """Perform fabric onboarding"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        if not request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        try:
            onboarding_manager = FabricOnboardingManager(fabric)
            result = onboarding_manager.perform_full_onboarding()
            
            # Check if all steps succeeded
            all_success = all(
                step['success'] for step in result.get('steps', {}).values()
            )
            
            if all_success:
                messages.success(request, f"Successfully onboarded fabric '{fabric.name}'")
                return JsonResponse({
                    'success': True,
                    'message': 'Fabric onboarding completed successfully',
                    'results': result,
                    'redirect_url': f'/plugins/hedgehog/fabrics/{fabric.pk}/'
                })
            else:
                messages.warning(request, f"Partial onboarding completed for fabric '{fabric.name}'")
                return JsonResponse({
                    'success': False,
                    'error': 'Some onboarding steps failed',
                    'results': result
                })
                
        except Exception as e:
            messages.error(request, f"Onboarding failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Onboarding failed: {str(e)}'
            })


class FabricListView(generic.ObjectListView):
    """List view for fabrics using NetBox generic view"""
    queryset = HedgehogFabric.objects.all()
    table = FabricTable


class FabricCreateView(generic.ObjectEditView):
    """Create view for fabrics"""
    queryset = HedgehogFabric.objects.all()
    # form_class = FabricForm  # Will need to create form class
    template_name = 'netbox_hedgehog/fabric_form.html'


class FabricEditView(generic.ObjectEditView):
    """Edit view for fabrics"""
    queryset = HedgehogFabric.objects.all()
    # form_class = FabricForm  # Will need to create form class 
    template_name = 'netbox_hedgehog/fabric_form.html'


class FabricDeleteView(generic.ObjectDeleteView):
    """Delete view for fabrics with cascade warnings"""
    queryset = HedgehogFabric.objects.all()
    template_name = 'netbox_hedgehog/fabric_confirm_delete.html'
    
    def get_context_data(self, **kwargs):
        """Add cascade deletion summary to context"""
        context = super().get_context_data(**kwargs)
        fabric = self.get_object()
        
        # Get counts of all related objects that will be deleted
        from ..models.vpc_api import VPC, External, IPv4Namespace, VPCAttachment, VPCPeering, ExternalAttachment, ExternalPeering
        from ..models.wiring_api import Switch, Connection, VLANNamespace, Server, SwitchGroup
        
        deletion_summary = {
            'switches': Switch.objects.filter(fabric=fabric).count(),
            'connections': Connection.objects.filter(fabric=fabric).count(),
            'vpcs': VPC.objects.filter(fabric=fabric).count(),
            'externals': External.objects.filter(fabric=fabric).count(),
            'ipv4_namespaces': IPv4Namespace.objects.filter(fabric=fabric).count(),
            'vlan_namespaces': VLANNamespace.objects.filter(fabric=fabric).count(),
            'vpc_attachments': VPCAttachment.objects.filter(fabric=fabric).count(),
            'vpc_peerings': VPCPeering.objects.filter(fabric=fabric).count(),
            'external_attachments': ExternalAttachment.objects.filter(fabric=fabric).count(),
            'external_peerings': ExternalPeering.objects.filter(fabric=fabric).count(),
            'servers': Server.objects.filter(fabric=fabric).count(),
            'switch_groups': SwitchGroup.objects.filter(fabric=fabric).count(),
        }
        
        # Calculate total count
        total_crd_count = sum(deletion_summary.values())
        
        # Get sample critical items to show (first 5 of each type)
        critical_items = {}
        has_more_items = {}
        
        if deletion_summary['switches'] > 0:
            switches = Switch.objects.filter(fabric=fabric)[:5]
            critical_items['switches'] = switches
            has_more_items['switches'] = deletion_summary['switches'] > 5
            
        if deletion_summary['connections'] > 0:
            connections = Connection.objects.filter(fabric=fabric)[:5]
            critical_items['connections'] = connections
            has_more_items['connections'] = deletion_summary['connections'] > 5
            
        if deletion_summary['vpcs'] > 0:
            vpcs = VPC.objects.filter(fabric=fabric)[:5]
            critical_items['vpcs'] = vpcs
            has_more_items['vpcs'] = deletion_summary['vpcs'] > 5
        
        context.update({
            'deletion_summary': deletion_summary,
            'total_crd_count': total_crd_count,
            'critical_items': critical_items,
            'has_more_items': has_more_items,
        })
        
        return context


@method_decorator(login_required, name='dispatch')
class FabricBulkActionsView(View):
    """Bulk actions for fabrics"""
    
    def post(self, request):
        """Perform bulk actions on fabrics"""
        
        if not request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        action = request.POST.get('action')
        fabric_ids = request.POST.getlist('fabrics')
        
        if not action or not fabric_ids:
            return JsonResponse({'success': False, 'error': 'Missing action or fabric selection'})
        
        fabrics = HedgehogFabric.objects.filter(pk__in=fabric_ids)
        
        try:
            if action == 'test_connection':
                # Test connection for selected fabrics
                success_count = 0
                for fabric in fabrics:
                    try:
                        onboarding_manager = FabricOnboardingManager(fabric)
                        success, message, cluster_info = onboarding_manager.validate_kubernetes_connection()
                        
                        if success:
                            fabric.cluster_info = cluster_info
                            fabric.sync_status = 'synced'
                            fabric.last_sync = datetime.now()
                            fabric.save()
                            success_count += 1
                        else:
                            fabric.sync_status = 'error'
                            fabric.save()
                    except Exception:
                        fabric.sync_status = 'error'
                        fabric.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Tested {success_count} of {fabrics.count()} fabric connections'
                })
                
            elif action == 'sync':
                # Sync selected fabrics
                success_count = 0
                for fabric in fabrics:
                    try:
                        reconciliation_manager = ReconciliationManager(fabric)
                        result = reconciliation_manager.perform_reconciliation(dry_run=False)
                        
                        if result.get('initialization_success'):
                            success_count += 1
                    except Exception:
                        pass
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully synced {success_count} of {fabrics.count()} fabrics'
                })
                
            elif action == 'delete':
                # Delete selected fabrics
                deleted_count = fabrics.count()
                fabrics.delete()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Deleted {deleted_count} fabrics'
                })
            
            else:
                return JsonResponse({'success': False, 'error': f'Unknown action: {action}'})
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Bulk action failed: {str(e)}'
            })


@method_decorator(login_required, name='dispatch')
class ArgoCDSetupWizardView(View):
    """ArgoCD Setup Wizard view for GitOps integration"""
    
    template_name = 'netbox_hedgehog/argocd_setup_wizard.html'
    
    def get(self, request, pk):
        """Display ArgoCD setup wizard"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        # Check permissions
        if not request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'):
            messages.error(request, 'Permission denied - you cannot modify fabrics')
            return redirect('plugins:netbox_hedgehog:fabric_detail', pk=pk)
        
        # Check if ArgoCD is already installed
        if getattr(fabric, 'argocd_installed', False):
            messages.info(request, f'ArgoCD is already installed for fabric {fabric.name}')
            return redirect('plugins:netbox_hedgehog:fabric_detail', pk=pk)
        
        context = {
            'fabric': fabric,
            'can_change': True,
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request, pk):
        """Handle ArgoCD installation request"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        # Check permissions
        if not request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'):
            return JsonResponse({
                'success': False,
                'error': 'Permission denied - you cannot modify fabrics'
            }, status=403)
        
        try:
            # Import ArgoCD installer
            from ..utils.argocd_installer import ArgoCDInstaller
            
            # Create installer instance
            installer = ArgoCDInstaller(fabric)
            
            # Start installation (this will be async in real implementation)
            installation_result = {
                'success': True,
                'message': 'ArgoCD installation started',
                'status': 'installing',
                'progress': 0
            }
            
            # Update fabric status to indicate installation in progress
            fabric.gitops_setup_status = 'installing'
            fabric.save(update_fields=['gitops_setup_status'])
            
            # Implement actual installation call
            try:
                # Use the installer's async installation method
                import asyncio
                
                async def run_installation():
                    return await installer.install_argocd()
                
                # Run the async installation
                result = asyncio.run(run_installation())
                
                # Update installation result with actual result
                if result.get('success', False):
                    installation_result.update({
                        'success': True,
                        'status': 'completed',
                        'progress': 100,
                        'argocd_status': result.get('argocd_status', {}),
                        'installation_details': result.get('installation_details', {})
                    })
                    fabric.gitops_setup_status = 'configured'
                else:
                    installation_result.update({
                        'success': False,
                        'status': 'failed',
                        'error': result.get('error', 'Installation failed'),
                        'details': result.get('details', {})
                    })
                    fabric.gitops_setup_status = 'failed'
                
                fabric.save(update_fields=['gitops_setup_status'])
                
            except Exception as install_error:
                logger.error(f"ArgoCD installation execution failed: {install_error}")
                installation_result.update({
                    'success': False,
                    'status': 'failed',
                    'error': f'Installation execution failed: {str(install_error)}'
                })
                fabric.gitops_setup_status = 'failed'
                fabric.save(update_fields=['gitops_setup_status'])
            
            return JsonResponse(installation_result)
            
        except ImportError as e:
            return JsonResponse({
                'success': False,
                'error': f'ArgoCD installer not available: {str(e)}'
            }, status=500)
        except Exception as e:
            logger.error(f"ArgoCD installation failed for fabric {fabric.name}: {e}")
            
            # Update fabric status to indicate error
            fabric.gitops_setup_status = 'error'
            fabric.gitops_setup_error = str(e)
            fabric.save(update_fields=['gitops_setup_status', 'gitops_setup_error'])
            
            return JsonResponse({
                'success': False,
                'error': f'Installation failed: {str(e)}'
            }, status=500)