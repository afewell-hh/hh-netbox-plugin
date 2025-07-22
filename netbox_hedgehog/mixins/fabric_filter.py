from django.shortcuts import get_object_or_404
from ..models.fabric import HedgehogFabric


class FabricFilterMixin:
    """
    Mixin to add fabric filtering functionality to CR list views.
    Supports filtering by fabric ID via ?fabric=X parameter.
    """
    
    def get_queryset(self):
        """Filter queryset by fabric if fabric parameter is provided"""
        queryset = super().get_queryset()
        fabric_id = self.request.GET.get('fabric')
        
        if fabric_id:
            try:
                # Validate fabric exists
                fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
                # Filter queryset by fabric
                queryset = queryset.filter(fabric=fabric)
            except (ValueError, HedgehogFabric.DoesNotExist):
                # Invalid fabric ID - return empty queryset
                queryset = queryset.none()
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add fabric filtering context to templates"""
        context = super().get_context_data(**kwargs)
        
        # Get current fabric filter
        fabric_id = self.request.GET.get('fabric')
        selected_fabric = None
        
        if fabric_id:
            try:
                selected_fabric = HedgehogFabric.objects.get(pk=fabric_id)
            except (ValueError, HedgehogFabric.DoesNotExist):
                pass
        
        # Add fabric context
        context.update({
            'selected_fabric': selected_fabric,
            'fabric_filter_id': fabric_id,
            'all_fabrics': HedgehogFabric.objects.all().order_by('name'),
            'show_fabric_filter': True,
        })
        
        return context


class FabricCRCountService:
    """Service to get CR counts by fabric for dashboard views"""
    
    @staticmethod
    def get_fabric_cr_counts(fabric):
        """Return counts of each CR type for a specific fabric"""
        from ..models.vpc_api import VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering
        from ..models.wiring_api import Connection, Server, Switch, SwitchGroup, VLANNamespace
        
        cr_types = [
            ('VPCs', VPC),
            ('Externals', External),
            ('External Attachments', ExternalAttachment),
            ('External Peerings', ExternalPeering),
            ('IPv4 Namespaces', IPv4Namespace),
            ('VPC Attachments', VPCAttachment),
            ('VPC Peerings', VPCPeering),
            ('Connections', Connection),
            ('Servers', Server),
            ('Switches', Switch),
            ('Switch Groups', SwitchGroup),
            ('VLAN Namespaces', VLANNamespace),
        ]
        
        counts = {}
        total = 0
        
        for display_name, model in cr_types:
            try:
                count = model.objects.filter(fabric=fabric).count()
                counts[display_name] = count
                total += count
            except Exception:
                counts[display_name] = 0
        
        counts['Total'] = total
        return counts
    
    @staticmethod
    def get_all_fabrics_cr_counts():
        """Return CR counts for all fabrics"""
        fabrics_data = []
        
        for fabric in HedgehogFabric.objects.all().order_by('name'):
            fabric_counts = FabricCRCountService.get_fabric_cr_counts(fabric)
            fabrics_data.append({
                'fabric': fabric,
                'counts': fabric_counts,
            })
        
        return fabrics_data