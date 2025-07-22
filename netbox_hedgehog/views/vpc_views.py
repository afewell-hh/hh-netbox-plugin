"""
VPC Management Views
Views for managing Virtual Private Clouds and related resources.
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
from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC, IPv4Namespace, VPCAttachment, VPCPeering
from ..models.wiring_api import VLANNamespace
from ..utils.kubernetes import KubernetesClient
from ..utils.crd_schemas import CRDSchemaManager
from ..choices import KubernetesStatusChoices


@method_decorator(login_required, name='dispatch')
class VPCListView(View):
    """List view for VPCs across all fabrics"""
    
    template_name = 'netbox_hedgehog/vpc_list.html'
    
    def get(self, request):
        """Display VPC list with filtering"""
        
        # Get query parameters
        fabric_id = request.GET.get('fabric')
        status_filter = request.GET.get('status')
        search = request.GET.get('search', '')
        
        # Build queryset
        vpcs = VPC.objects.select_related('fabric', 'ipv4_namespace', 'vlan_namespace')
        
        if fabric_id:
            vpcs = vpcs.filter(fabric_id=fabric_id)
        
        if status_filter:
            vpcs = vpcs.filter(kubernetes_status=status_filter)
        
        if search:
            vpcs = vpcs.filter(name__icontains=search)
        
        # Order by fabric, then name
        vpcs = vpcs.order_by('fabric__name', 'name')
        
        # Pagination
        paginator = Paginator(vpcs, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get fabric choices for filter
        fabrics = HedgehogFabric.objects.all().order_by('name')
        
        # Status statistics
        status_stats = {
            'total': vpcs.count(),
            'active': vpcs.filter(kubernetes_status='applied').count(),
            'pending': vpcs.filter(kubernetes_status='pending').count(),
            'error': vpcs.filter(kubernetes_status='error').count(),
        }
        
        context = {
            'page_obj': page_obj,
            'vpcs': page_obj.object_list,
            'fabrics': fabrics,
            'status_stats': status_stats,
            'current_fabric': fabric_id,
            'current_status': status_filter,
            'search_query': search,
            'can_add': request.user.has_perm('netbox_hedgehog.add_vpc'),
            'can_change': request.user.has_perm('netbox_hedgehog.change_vpc'),
            'can_delete': request.user.has_perm('netbox_hedgehog.delete_vpc'),
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class VPCDetailView(View):
    """Detailed view of a specific VPC"""
    
    template_name = 'netbox_hedgehog/vpc_detail.html'
    
    def get(self, request, pk):
        """Display VPC details"""
        vpc = get_object_or_404(VPC, pk=pk)
        
        # Parse subnets from JSON field
        subnets = []
        if vpc.subnets_config:
            try:
                subnets_data = json.loads(vpc.subnets_config) if isinstance(vpc.subnets_config, str) else vpc.subnets_config
                for subnet_name, subnet_config in subnets_data.items():
                    subnet_info = {
                        'name': subnet_name,
                        'subnet': subnet_config.get('subnet'),
                        'gateway': subnet_config.get('gateway'),
                        'vlan': subnet_config.get('vlan'),
                        'dhcp_enabled': subnet_config.get('dhcp', {}).get('enable', False),
                        'dhcp_start': subnet_config.get('dhcp', {}).get('start'),
                        'dhcp_end': subnet_config.get('dhcp', {}).get('end'),
                    }
                    subnets.append(subnet_info)
            except (json.JSONDecodeError, AttributeError):
                subnets = []
        
        # Get related VPC attachments and peerings
        attachments = VPCAttachment.objects.filter(vpc=vpc)
        peerings = VPCPeering.objects.filter(vpc=vpc)
        
        # Get Kubernetes status if available
        k8s_status = None
        if vpc.fabric and vpc.kubernetes_status == 'applied':
            try:
                k8s_client = KubernetesClient(vpc.fabric)
                # Would get actual status from cluster
                k8s_status = {
                    'ready': True,
                    'conditions': [
                        {'type': 'Ready', 'status': 'True', 'message': 'VPC is operational'}
                    ],
                    'vni': vpc.kubernetes_uid,  # Mock VNI
                }
            except Exception:
                k8s_status = {'ready': False, 'error': 'Unable to fetch status'}
        
        # Recent events (mock for now)
        events = [
            {
                'timestamp': vpc.updated_at or vpc.created_at,
                'event': 'VPC Created' if not vpc.updated_at else 'VPC Updated',
                'source': 'netbox' if vpc.managed_by_netbox else 'kubernetes',
                'user': request.user.username
            }
        ]
        
        context = {
            'vpc': vpc,
            'subnets': subnets,
            'attachments': attachments,
            'peerings': peerings,
            'k8s_status': k8s_status,
            'events': events,
            'can_change': request.user.has_perm('netbox_hedgehog.change_vpc'),
            'can_delete': request.user.has_perm('netbox_hedgehog.delete_vpc'),
            'can_apply': request.user.has_perm('netbox_hedgehog.change_vpc') and vpc.kubernetes_status in ['pending', 'error'],
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class VPCCreateView(View):
    """Create a new VPC using template selection"""
    
    template_name = 'netbox_hedgehog/vpc_create.html'
    
    def get(self, request):
        """Display VPC creation form"""
        
        # Get fabric choices
        fabrics = HedgehogFabric.objects.filter(sync_status='synced').order_by('name')
        
        # VPC templates
        templates = {
            'basic': {
                'name': 'Basic VPC',
                'description': 'Single subnet VPC for simple workloads',
                'subnets': 1,
                'dhcp': True,
                'example': {
                    'main': {
                        'subnet': '10.100.1.0/24',
                        'gateway': '10.100.1.1',
                        'vlan': 1100,
                        'dhcp': {'enable': True}
                    }
                }
            },
            'web-db': {
                'name': 'Web + Database',
                'description': 'Two-tier application with web and database subnets',
                'subnets': 2,
                'dhcp': True,
                'example': {
                    'web': {
                        'subnet': '10.100.10.0/24',
                        'gateway': '10.100.10.1',
                        'vlan': 1110,
                        'dhcp': {'enable': True}
                    },
                    'db': {
                        'subnet': '10.100.11.0/24',
                        'gateway': '10.100.11.1',
                        'vlan': 1111,
                        'dhcp': {'enable': True}
                    }
                }
            },
            'three-tier': {
                'name': 'Three-Tier Application',
                'description': 'Web, application, and database tiers',
                'subnets': 3,
                'dhcp': True,
                'example': {
                    'web': {
                        'subnet': '10.100.20.0/24',
                        'gateway': '10.100.20.1',
                        'vlan': 1120,
                        'dhcp': {'enable': True}
                    },
                    'app': {
                        'subnet': '10.100.21.0/24',
                        'gateway': '10.100.21.1',
                        'vlan': 1121,
                        'dhcp': {'enable': True}
                    },
                    'db': {
                        'subnet': '10.100.22.0/24',
                        'gateway': '10.100.22.1',
                        'vlan': 1122,
                        'dhcp': {'enable': True}
                    }
                }
            },
            'custom': {
                'name': 'Custom Configuration',
                'description': 'Define your own subnet configuration',
                'subnets': 'variable',
                'dhcp': 'configurable',
                'example': {}
            }
        }
        
        # Get available namespaces for selected fabric
        fabric_id = request.GET.get('fabric')
        ipv4_namespaces = []
        vlan_namespaces = []
        
        if fabric_id:
            try:
                fabric = HedgehogFabric.objects.get(pk=fabric_id)
                ipv4_namespaces = IPv4Namespace.objects.filter(fabric=fabric)
                vlan_namespaces = VLANNamespace.objects.filter(fabric=fabric)
            except HedgehogFabric.DoesNotExist:
                pass
        
        context = {
            'fabrics': fabrics,
            'templates': templates,
            'ipv4_namespaces': ipv4_namespaces,
            'vlan_namespaces': vlan_namespaces,
            'selected_fabric': fabric_id,
            'can_create': request.user.has_perm('netbox_hedgehog.add_vpc'),
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Create VPC from form data"""
        
        if not request.user.has_perm('netbox_hedgehog.add_vpc'):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        try:
            # Parse form data
            fabric_id = request.POST.get('fabric')
            vpc_name = request.POST.get('name')
            description = request.POST.get('description', '')
            template_type = request.POST.get('template')
            ipv4_namespace_id = request.POST.get('ipv4_namespace')
            vlan_namespace_id = request.POST.get('vlan_namespace')
            
            # Validate required fields
            if not all([fabric_id, vpc_name, template_type]):
                return JsonResponse({'success': False, 'error': 'Missing required fields'})
            
            # Get related objects
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            ipv4_namespace = get_object_or_404(IPv4Namespace, pk=ipv4_namespace_id) if ipv4_namespace_id else None
            vlan_namespace = get_object_or_404(VLANNamespace, pk=vlan_namespace_id) if vlan_namespace_id else None
            
            # Build subnets configuration based on template
            if template_type == 'custom':
                # Parse custom subnet configuration from form
                subnets_config = {}  # Would parse from form data
            else:
                # Use predefined template
                templates = {
                    'basic': {
                        'main': {
                            'subnet': '10.100.1.0/24',
                            'gateway': '10.100.1.1',
                            'vlan': 1100,
                            'dhcp': {'enable': True}
                        }
                    },
                    'web-db': {
                        'web': {
                            'subnet': '10.100.10.0/24',
                            'gateway': '10.100.10.1',
                            'vlan': 1110,
                            'dhcp': {'enable': True}
                        },
                        'db': {
                            'subnet': '10.100.11.0/24',
                            'gateway': '10.100.11.1',
                            'vlan': 1111,
                            'dhcp': {'enable': True}
                        }
                    }
                }
                subnets_config = templates.get(template_type, {})
            
            # Create VPC
            vpc = VPC.objects.create(
                fabric=fabric,
                name=vpc_name,
                description=description,
                ipv4_namespace=ipv4_namespace,
                vlan_namespace=vlan_namespace,
                subnets_config=subnets_config,
                managed_by_netbox=True,
                kubernetes_status='pending'
            )
            
            messages.success(request, f"VPC '{vpc_name}' created successfully")
            
            return JsonResponse({
                'success': True,
                'message': f"VPC '{vpc_name}' created successfully",
                'vpc_id': vpc.pk,
                'redirect_url': f'/plugins/hedgehog/vpcs/{vpc.pk}/'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Failed to create VPC: {str(e)}'
            })


@method_decorator(login_required, name='dispatch')
class VPCApplyView(View):
    """Apply VPC to Kubernetes cluster"""
    
    def post(self, request, pk):
        """Apply VPC to cluster"""
        vpc = get_object_or_404(VPC, pk=pk)
        
        if not request.user.has_perm('netbox_hedgehog.change_vpc'):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        try:
            # Create Kubernetes client
            k8s_client = KubernetesClient(vpc.fabric)
            
            # Build VPC manifest
            manifest = vpc.to_kubernetes_manifest()
            
            # Apply to cluster
            success, message = k8s_client.apply_crd(manifest)
            
            if success:
                vpc.kubernetes_status = 'applied'
                vpc.last_applied = datetime.now()
                vpc.save()
                
                messages.success(request, f"VPC '{vpc.name}' applied to cluster successfully")
                
                return JsonResponse({
                    'success': True,
                    'message': message
                })
            else:
                vpc.kubernetes_status = 'error'
                vpc.save()
                
                return JsonResponse({
                    'success': False,
                    'error': message
                })
                
        except Exception as e:
            vpc.kubernetes_status = 'error'
            vpc.save()
            
            return JsonResponse({
                'success': False,
                'error': f'Apply failed: {str(e)}'
            })


@method_decorator(login_required, name='dispatch')  
class VPCDeleteView(View):
    """Delete VPC (both from NetBox and cluster)"""
    
    def post(self, request, pk):
        """Delete VPC"""
        vpc = get_object_or_404(VPC, pk=pk)
        
        if not request.user.has_perm('netbox_hedgehog.delete_vpc'):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        try:
            vpc_name = vpc.name
            
            # If VPC is applied to cluster, delete from cluster first
            if vpc.kubernetes_status == 'applied':
                k8s_client = KubernetesClient(vpc.fabric)
                k8s_client.delete_crd('VPC', vpc.name, vpc.kubernetes_namespace or 'default')
            
            # Delete from NetBox
            vpc.delete()
            
            messages.success(request, f"VPC '{vpc_name}' deleted successfully")
            
            return JsonResponse({
                'success': True,
                'message': f"VPC '{vpc_name}' deleted successfully",
                'redirect_url': '/plugins/hedgehog/vpcs/'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Delete failed: {str(e)}'
            })


class VPCBulkActionsView(View):
    """Bulk actions for VPCs"""
    
    def post(self, request):
        """Perform bulk actions on VPCs"""
        
        if not request.user.has_perm('netbox_hedgehog.change_vpc'):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        action = request.POST.get('action')
        vpc_ids = request.POST.getlist('vpcs')
        
        if not action or not vpc_ids:
            return JsonResponse({'success': False, 'error': 'Missing action or VPC selection'})
        
        vpcs = VPC.objects.filter(pk__in=vpc_ids)
        
        try:
            if action == 'apply':
                # Apply selected VPCs to cluster
                applied_count = 0
                for vpc in vpcs:
                    if vpc.kubernetes_status in ['pending', 'error']:
                        k8s_client = KubernetesClient(vpc.fabric)
                        manifest = vpc.to_kubernetes_manifest()
                        success, _ = k8s_client.apply_crd(manifest)
                        
                        if success:
                            vpc.kubernetes_status = 'applied'
                            vpc.last_applied = datetime.now()
                            vpc.save()
                            applied_count += 1
                
                return JsonResponse({
                    'success': True,
                    'message': f'Applied {applied_count} VPCs to cluster'
                })
                
            elif action == 'delete':
                # Delete selected VPCs
                deleted_count = vpcs.count()
                
                # Delete from clusters first
                for vpc in vpcs:
                    if vpc.kubernetes_status == 'applied':
                        try:
                            k8s_client = KubernetesClient(vpc.fabric)
                            k8s_client.delete_crd('VPC', vpc.name, vpc.kubernetes_namespace or 'default')
                        except Exception:
                            pass  # Continue with NetBox deletion even if cluster deletion fails
                
                vpcs.delete()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Deleted {deleted_count} VPCs'
                })
            
            else:
                return JsonResponse({'success': False, 'error': f'Unknown action: {action}'})
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Bulk action failed: {str(e)}'
            })