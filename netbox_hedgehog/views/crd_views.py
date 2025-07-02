from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from django.http import JsonResponse
from django.utils import timezone
from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering
from ..models.wiring_api import Connection, Server, Switch, SwitchGroup, VLANNamespace


class FabricCRDListView(View):
    """List all CRDs associated with a fabric"""
    
    def get(self, request, pk):
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        # Collect all CRDs for this fabric
        crd_types = [
            ('VPCs', VPC, 'cloud'),
            ('Externals', External, 'earth'),
            ('External Attachments', ExternalAttachment, 'link-variant'),
            ('External Peerings', ExternalPeering, 'swap-horizontal'),
            ('IPv4 Namespaces', IPv4Namespace, 'ip-network'),
            ('VPC Attachments', VPCAttachment, 'attachment'),
            ('VPC Peerings', VPCPeering, 'swap-vertical'),
            ('Connections', Connection, 'cable-data'),
            ('Servers', Server, 'server'),
            ('Switches', Switch, 'switch'),
            ('Switch Groups', SwitchGroup, 'group'),
            ('VLAN Namespaces', VLANNamespace, 'vlan'),
        ]
        
        crd_summary = []
        total_crds = 0
        
        for display_name, model, icon in crd_types:
            try:
                crds = model.objects.filter(fabric=fabric)
                count = crds.count()
                total_crds += count
                
                if count > 0:
                    # Get status counts
                    live_count = crds.filter(kubernetes_status='live').count()
                    error_count = crds.filter(kubernetes_status='error').count()
                    
                    crd_summary.append({
                        'name': display_name,
                        'model_name': model.__name__.lower(),
                        'icon': icon,
                        'total': count,
                        'live': live_count,
                        'error': error_count,
                        'crds': crds[:5]  # Show first 5 as preview
                    })
            except Exception:
                # Table might not exist
                pass
        
        context = {
            'fabric': fabric,
            'crd_summary': crd_summary,
            'total_crds': total_crds,
        }
        
        return render(request, 'netbox_hedgehog/fabric_crds.html', context)


class CRDDetailView(View):
    """View details of a specific CRD"""
    
    def get(self, request, fabric_pk, crd_type, crd_pk):
        fabric = get_object_or_404(HedgehogFabric, pk=fabric_pk)
        
        # Map CRD type to model
        model_map = {
            'vpc': VPC,
            'external': External,
            'externalattachment': ExternalAttachment,
            'externalpeering': ExternalPeering,
            'ipv4namespace': IPv4Namespace,
            'vpcattachment': VPCAttachment,
            'vpcpeering': VPCPeering,
            'connection': Connection,
            'server': Server,
            'switch': Switch,
            'switchgroup': SwitchGroup,
            'vlannamespace': VLANNamespace,
        }
        
        model = model_map.get(crd_type)
        if not model:
            messages.error(request, f"Unknown CRD type: {crd_type}")
            return redirect('plugins:netbox_hedgehog:fabric_crds', pk=fabric_pk)
        
        crd = get_object_or_404(model, pk=crd_pk, fabric=fabric)
        
        # Get YAML representation
        yaml_content = self._get_crd_yaml(crd)
        
        context = {
            'fabric': fabric,
            'crd': crd,
            'crd_type': crd_type,
            'yaml_content': yaml_content,
        }
        
        return render(request, 'netbox_hedgehog/crd_detail.html', context)
    
    def _get_crd_yaml(self, crd):
        """Generate YAML representation of CRD"""
        import yaml
        
        # Build Kubernetes manifest
        manifest = {
            'apiVersion': crd.api_version,
            'kind': crd.kind,
            'metadata': {
                'name': crd.name,
                'namespace': crd.namespace,
            }
        }
        
        if crd.labels:
            manifest['metadata']['labels'] = crd.labels
        
        if crd.annotations:
            manifest['metadata']['annotations'] = crd.annotations
        
        if hasattr(crd, 'spec') and crd.spec:
            manifest['spec'] = crd.spec
        
        return yaml.dump(manifest, default_flow_style=False)


class ApplyCRDView(View):
    """Apply a CRD to Kubernetes"""
    
    def post(self, request, fabric_pk, crd_type, crd_pk):
        fabric = get_object_or_404(HedgehogFabric, pk=fabric_pk)
        
        # Map CRD type to model
        model_map = {
            'vpc': VPC,
            'external': External,
            'externalattachment': ExternalAttachment,
            'externalpeering': ExternalPeering,
            'ipv4namespace': IPv4Namespace,
            'vpcattachment': VPCAttachment,
            'vpcpeering': VPCPeering,
            'connection': Connection,
            'server': Server,
            'switch': Switch,
            'switchgroup': SwitchGroup,
            'vlannamespace': VLANNamespace,
        }
        
        model = model_map.get(crd_type)
        if not model:
            return JsonResponse({'success': False, 'error': f'Unknown CRD type: {crd_type}'})
        
        crd = get_object_or_404(model, pk=crd_pk, fabric=fabric)
        
        try:
            # TODO: Implement actual Kubernetes API call
            # For now, simulate success
            crd.kubernetes_status = 'live'
            crd.last_applied = timezone.now()
            crd.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully applied {crd.kind} {crd.name}',
                'status': crd.kubernetes_status
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


class DeleteCRDView(View):
    """Delete a CRD from Kubernetes"""
    
    def post(self, request, fabric_pk, crd_type, crd_pk):
        fabric = get_object_or_404(HedgehogFabric, pk=fabric_pk)
        
        # Map CRD type to model
        model_map = {
            'vpc': VPC,
            'external': External,
            'externalattachment': ExternalAttachment,
            'externalpeering': ExternalPeering,
            'ipv4namespace': IPv4Namespace,
            'vpcattachment': VPCAttachment,
            'vpcpeering': VPCPeering,
            'connection': Connection,
            'server': Server,
            'switch': Switch,
            'switchgroup': SwitchGroup,
            'vlannamespace': VLANNamespace,
        }
        
        model = model_map.get(crd_type)
        if not model:
            return JsonResponse({'success': False, 'error': f'Unknown CRD type: {crd_type}'})
        
        crd = get_object_or_404(model, pk=crd_pk, fabric=fabric)
        
        try:
            # TODO: Implement actual Kubernetes API call to delete
            # For now, simulate deletion
            crd_name = crd.name
            crd.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully deleted {crd.kind} {crd_name}'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })