"""
Wiring Infrastructure Views
Views for managing switches, connections, and physical infrastructure.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from datetime import datetime
import json

# NetBox imports
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

# Plugin imports
from ..models.fabric import HedgehogFabric
from ..models.wiring import Switch, Connection, Server, SwitchGroup, VLANNamespace
from ..utils.kubernetes import KubernetesClient
from ..choices import SwitchRoleChoices, ConnectionTypeChoices


@method_decorator(login_required, name='dispatch')
class SwitchListView(View):
    """List view for switches across all fabrics"""
    
    template_name = 'netbox_hedgehog/switch_list.html'
    
    def get(self, request):
        """Display switch list with filtering"""
        
        # Get query parameters
        fabric_id = request.GET.get('fabric')
        role_filter = request.GET.get('role')
        search = request.GET.get('search', '')
        
        # Build queryset
        switches = Switch.objects.select_related('fabric', 'switch_group')
        
        if fabric_id:
            switches = switches.filter(fabric_id=fabric_id)
        
        if role_filter:
            switches = switches.filter(role=role_filter)
        
        if search:
            switches = switches.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(asn__icontains=search)
            )
        
        # Order by fabric, role, then name
        switches = switches.order_by('fabric__name', 'role', 'name')
        
        # Pagination
        paginator = Paginator(switches, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get filter choices
        fabrics = HedgehogFabric.objects.all().order_by('name')
        roles = SwitchRoleChoices
        
        # Statistics by role
        role_stats = {}
        for role_choice in SwitchRoleChoices:
            role_code = role_choice[0]
            role_name = role_choice[1]
            count = switches.filter(role=role_code).count() if role_code else switches.filter(role__isnull=True).count()
            role_stats[role_name] = count
        
        # Fabric distribution
        fabric_stats = switches.values('fabric__name').annotate(count=Count('id')).order_by('fabric__name')
        
        context = {
            'page_obj': page_obj,
            'switches': page_obj.object_list,
            'fabrics': fabrics,
            'roles': roles,
            'role_stats': role_stats,
            'fabric_stats': fabric_stats,
            'current_fabric': fabric_id,
            'current_role': role_filter,
            'search_query': search,
            'total_switches': switches.count(),
            'can_add': request.user.has_perm('netbox_hedgehog.add_switch'),
            'can_change': request.user.has_perm('netbox_hedgehog.change_switch'),
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class SwitchDetailView(View):
    """Detailed view of a specific switch"""
    
    template_name = 'netbox_hedgehog/switch_detail.html'
    
    def get(self, request, pk):
        """Display switch details"""
        switch = get_object_or_404(Switch, pk=pk)
        
        # Get connections where this switch is involved
        connections = Connection.objects.filter(
            Q(connection_config__contains=switch.name) |  # JSON field search
            Q(description__icontains=switch.name)
        ).distinct()
        
        # Parse VLAN namespaces from JSON field
        vlan_namespaces = []
        if switch.vlan_namespaces_config:
            try:
                vlan_data = json.loads(switch.vlan_namespaces_config) if isinstance(switch.vlan_namespaces_config, str) else switch.vlan_namespaces_config
                vlan_namespaces = vlan_data if isinstance(vlan_data, list) else []
            except (json.JSONDecodeError, AttributeError):
                vlan_namespaces = []
        
        # Parse groups from JSON field
        groups = []
        if switch.groups_config:
            try:
                group_data = json.loads(switch.groups_config) if isinstance(switch.groups_config, str) else switch.groups_config
                groups = group_data if isinstance(group_data, list) else []
            except (json.JSONDecodeError, AttributeError):
                groups = []
        
        # Parse redundancy configuration
        redundancy_info = None
        if switch.redundancy_config:
            try:
                redundancy_info = json.loads(switch.redundancy_config) if isinstance(switch.redundancy_config, str) else switch.redundancy_config
            except (json.JSONDecodeError, AttributeError):
                redundancy_info = None
        
        # Get related servers
        servers = Server.objects.filter(
            server_config__contains=switch.name
        ).distinct()
        
        # Get Kubernetes status
        k8s_status = None
        if switch.fabric and switch.kubernetes_status == 'applied':
            try:
                k8s_client = KubernetesClient(switch.fabric)
                # Would get actual status from cluster
                k8s_status = {
                    'ready': True,
                    'conditions': [
                        {'type': 'Ready', 'status': 'True', 'message': 'Switch is operational'}
                    ],
                    'profile': switch.profile or 'vs',
                }
            except Exception:
                k8s_status = {'ready': False, 'error': 'Unable to fetch status'}
        
        # Interface summary (mock data based on typical switch)
        interface_summary = {
            'total_ports': 48,  # Would come from switch profile
            'used_ports': connections.count(),
            'free_ports': 48 - connections.count(),
            'breakout_ports': 4,
        }
        
        context = {
            'switch': switch,
            'connections': connections,
            'servers': servers,
            'vlan_namespaces': vlan_namespaces,
            'groups': groups,
            'redundancy_info': redundancy_info,
            'interface_summary': interface_summary,
            'k8s_status': k8s_status,
            'can_change': request.user.has_perm('netbox_hedgehog.change_switch'),
            'can_delete': request.user.has_perm('netbox_hedgehog.delete_switch'),
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class ConnectionListView(View):
    """List view for connections across all fabrics"""
    
    template_name = 'netbox_hedgehog/connection_list.html'
    
    def get(self, request):
        """Display connection list with filtering"""
        
        # Get query parameters
        fabric_id = request.GET.get('fabric')
        type_filter = request.GET.get('type')
        search = request.GET.get('search', '')
        
        # Build queryset
        connections = Connection.objects.select_related('fabric')
        
        if fabric_id:
            connections = connections.filter(fabric_id=fabric_id)
        
        if type_filter:
            connections = connections.filter(connection_type=type_filter)
        
        if search:
            connections = connections.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Order by fabric, type, then name
        connections = connections.order_by('fabric__name', 'connection_type', 'name')
        
        # Pagination
        paginator = Paginator(connections, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get filter choices
        fabrics = HedgehogFabric.objects.all().order_by('name')
        connection_types = ConnectionTypeChoices
        
        # Statistics by type
        type_stats = {}
        for type_choice in ConnectionTypeChoices:
            type_code = type_choice[0]
            type_name = type_choice[1]
            count = connections.filter(connection_type=type_code).count()
            type_stats[type_name] = count
        
        context = {
            'page_obj': page_obj,
            'connections': page_obj.object_list,
            'fabrics': fabrics,
            'connection_types': connection_types,
            'type_stats': type_stats,
            'current_fabric': fabric_id,
            'current_type': type_filter,
            'search_query': search,
            'total_connections': connections.count(),
            'can_add': request.user.has_perm('netbox_hedgehog.add_connection'),
            'can_change': request.user.has_perm('netbox_hedgehog.change_connection'),
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class ConnectionDetailView(View):
    """Detailed view of a specific connection"""
    
    template_name = 'netbox_hedgehog/connection_detail.html'
    
    def get(self, request, pk):
        """Display connection details"""
        connection = get_object_or_404(Connection, pk=pk)
        
        # Parse connection configuration
        connection_details = {}
        if connection.connection_config:
            try:
                connection_details = json.loads(connection.connection_config) if isinstance(connection.connection_config, str) else connection.connection_config
            except (json.JSONDecodeError, AttributeError):
                connection_details = {}
        
        # Extract endpoints information
        endpoints = []
        if 'links' in connection_details:
            for link in connection_details['links']:
                endpoint_info = {
                    'switch': link.get('switch'),
                    'port': link.get('port'),
                    'server': link.get('server'),
                    'location': link.get('location')
                }
                endpoints.append(endpoint_info)
        
        # Connection type specific information
        type_info = {}
        if connection.connection_type == 'bundled':
            type_info = {
                'bundle_members': connection_details.get('links', []),
                'lacp_enabled': True,  # Would be parsed from config
            }
        elif connection.connection_type == 'mclag':
            type_info = {
                'mclag_domain': connection_details.get('mclag', {}).get('domain'),
                'peer_switches': connection_details.get('mclag', {}).get('peers', []),
            }
        elif connection.connection_type == 'eslag':
            type_info = {
                'eslag_group': connection_details.get('eslag', {}).get('group'),
                'member_switches': connection_details.get('eslag', {}).get('members', []),
            }
        
        # Get related switches
        related_switches = []
        for endpoint in endpoints:
            if endpoint.get('switch'):
                try:
                    switch = Switch.objects.get(name=endpoint['switch'], fabric=connection.fabric)
                    related_switches.append(switch)
                except Switch.DoesNotExist:
                    pass
        
        context = {
            'connection': connection,
            'endpoints': endpoints,
            'type_info': type_info,
            'related_switches': related_switches,
            'connection_details': connection_details,
            'can_change': request.user.has_perm('netbox_hedgehog.change_connection'),
            'can_delete': request.user.has_perm('netbox_hedgehog.delete_connection'),
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class TopologyView(View):
    """Network topology visualization"""
    
    template_name = 'netbox_hedgehog/topology.html'
    
    def get(self, request):
        """Display network topology"""
        
        fabric_id = request.GET.get('fabric')
        
        if fabric_id:
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            switches = Switch.objects.filter(fabric=fabric)
            connections = Connection.objects.filter(fabric=fabric)
            servers = Server.objects.filter(fabric=fabric)
        else:
            fabric = None
            switches = Switch.objects.all()
            connections = Connection.objects.all()
            servers = Server.objects.all()
        
        # Build topology data for visualization
        topology_data = {
            'nodes': [],
            'links': []
        }
        
        # Add switches as nodes
        for switch in switches:
            node = {
                'id': f"switch-{switch.id}",
                'name': switch.name,
                'type': 'switch',
                'role': switch.role,
                'asn': switch.asn,
                'status': 'active' if switch.kubernetes_status == 'applied' else 'inactive',
                'group': switch.role or 'unknown'
            }
            topology_data['nodes'].append(node)
        
        # Add servers as nodes
        for server in servers:
            node = {
                'id': f"server-{server.id}",
                'name': server.name,
                'type': 'server',
                'status': 'active',
                'group': 'server'
            }
            topology_data['nodes'].append(node)
        
        # Add connections as links
        for connection in connections:
            # Parse connection config to extract endpoints
            if connection.connection_config:
                try:
                    config = json.loads(connection.connection_config) if isinstance(connection.connection_config, str) else connection.connection_config
                    links = config.get('links', [])
                    
                    # Create links between endpoints
                    for i, link in enumerate(links):
                        if i < len(links) - 1:
                            source_name = link.get('switch') or link.get('server')
                            target_name = links[i + 1].get('switch') or links[i + 1].get('server')
                            
                            if source_name and target_name:
                                link_data = {
                                    'id': f"connection-{connection.id}-{i}",
                                    'source': f"switch-{source_name}" if link.get('switch') else f"server-{source_name}",
                                    'target': f"switch-{target_name}" if links[i + 1].get('switch') else f"server-{target_name}",
                                    'type': connection.connection_type,
                                    'name': connection.name
                                }
                                topology_data['links'].append(link_data)
                
                except (json.JSONDecodeError, AttributeError):
                    pass
        
        # Fabric choices for filter
        fabrics = HedgehogFabric.objects.all().order_by('name')
        
        # Statistics
        stats = {
            'switches': switches.count(),
            'connections': connections.count(),
            'servers': servers.count(),
            'spine_switches': switches.filter(role='spine').count(),
            'leaf_switches': switches.filter(role__in=['server-leaf', 'border-leaf']).count(),
        }
        
        context = {
            'fabric': fabric,
            'fabrics': fabrics,
            'topology_data': json.dumps(topology_data),
            'stats': stats,
            'switches': switches,
            'connections': connections,
            'servers': servers,
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class VLANNamespaceListView(View):
    """List view for VLAN namespaces"""
    
    template_name = 'netbox_hedgehog/vlan_namespace_list.html'
    
    def get(self, request):
        """Display VLAN namespace list"""
        
        fabric_id = request.GET.get('fabric')
        
        # Build queryset
        vlan_namespaces = VLANNamespace.objects.select_related('fabric')
        
        if fabric_id:
            vlan_namespaces = vlan_namespaces.filter(fabric_id=fabric_id)
        
        vlan_namespaces = vlan_namespaces.order_by('fabric__name', 'name')
        
        # Get fabric choices
        fabrics = HedgehogFabric.objects.all().order_by('name')
        
        context = {
            'vlan_namespaces': vlan_namespaces,
            'fabrics': fabrics,
            'current_fabric': fabric_id,
            'can_add': request.user.has_perm('netbox_hedgehog.add_vlannamespace'),
            'can_change': request.user.has_perm('netbox_hedgehog.change_vlannamespace'),
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class VLANNamespaceDetailView(View):
    """Detail view for VLAN namespace"""
    
    template_name = 'netbox_hedgehog/vlan_namespace_detail.html'
    
    def get(self, request, pk):
        """Display VLAN namespace details"""
        vlan_namespace = get_object_or_404(VLANNamespace, pk=pk)
        
        # Parse VLAN ranges
        vlan_ranges = []
        if vlan_namespace.ranges_config:
            try:
                ranges_data = json.loads(vlan_namespace.ranges_config) if isinstance(vlan_namespace.ranges_config, str) else vlan_namespace.ranges_config
                vlan_ranges = ranges_data if isinstance(ranges_data, list) else []
            except (json.JSONDecodeError, AttributeError):
                vlan_ranges = []
        
        # Calculate VLAN utilization
        total_vlans = 0
        used_vlans = 0  # Would be calculated from VPCs using this namespace
        
        for vlan_range in vlan_ranges:
            if isinstance(vlan_range, dict) and 'from' in vlan_range and 'to' in vlan_range:
                total_vlans += vlan_range['to'] - vlan_range['from'] + 1
        
        # Get VPCs using this namespace
        from ..models.vpc import VPC
        vpcs_using_namespace = VPC.objects.filter(vlan_namespace=vlan_namespace)
        
        context = {
            'vlan_namespace': vlan_namespace,
            'vlan_ranges': vlan_ranges,
            'total_vlans': total_vlans,
            'used_vlans': used_vlans,
            'available_vlans': total_vlans - used_vlans,
            'vpcs_using_namespace': vpcs_using_namespace,
            'can_change': request.user.has_perm('netbox_hedgehog.change_vlannamespace'),
            'can_delete': request.user.has_perm('netbox_hedgehog.delete_vlannamespace'),
        }
        
        return render(request, self.template_name, context)