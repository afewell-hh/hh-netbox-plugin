"""
VPC Management Forms
Dynamic forms for VPC creation, editing, and management with template support.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory
import json
import ipaddress

# NetBox imports
from netbox.forms import NetBoxModelForm
from utilities.forms import DynamicModelChoiceField, StaticSelect2, JSONField

# Plugin imports
from ..models.fabric import HedgehogFabric
from ..models.vpc import VPC, IPv4Namespace, VLANNamespace, VPCAttachment, VPCPeering
from ..choices import KubernetesStatusChoices
from ..utils.crd_schemas import VPCCRDSchema


class VPCForm(NetBoxModelForm):
    """Standard VPC form for basic editing"""
    
    class Meta:
        model = VPC
        fields = [
            'name', 'description', 'fabric', 'ipv4_namespace', 'vlan_namespace',
            'subnets_config', 'kubernetes_namespace', 'tags'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., production-vpc'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control'
            }),
            'subnets_config': forms.Textarea(attrs={
                'rows': 10,
                'class': 'form-control',
                'placeholder': 'JSON configuration for subnets'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter namespaces by fabric if editing
        if self.instance and self.instance.fabric:
            self.fields['ipv4_namespace'].queryset = IPv4Namespace.objects.filter(
                fabric=self.instance.fabric
            )
            self.fields['vlan_namespace'].queryset = VLANNamespace.objects.filter(
                fabric=self.instance.fabric
            )


class SubnetConfigForm(forms.Form):
    """Form for individual subnet configuration"""
    
    name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., web, db, app'
        }),
        help_text="Subnet name (no spaces, lowercase recommended)"
    )
    
    subnet = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10.100.1.0/24'
        }),
        help_text="CIDR notation for the subnet"
    )
    
    gateway = forms.GenericIPAddressField(
        protocol='IPv4',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10.100.1.1'
        }),
        help_text="Gateway IP address"
    )
    
    vlan = forms.IntegerField(
        min_value=1,
        max_value=4094,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '100'
        }),
        help_text="VLAN ID (1-4094)"
    )
    
    dhcp_enabled = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Enable DHCP for this subnet"
    )
    
    dhcp_start = forms.GenericIPAddressField(
        protocol='IPv4',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10.100.1.10'
        }),
        help_text="DHCP range start (optional)"
    )
    
    dhcp_end = forms.GenericIPAddressField(
        protocol='IPv4',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10.100.1.200'
        }),
        help_text="DHCP range end (optional)"
    )
    
    def clean(self):
        """Validate subnet configuration"""
        cleaned_data = super().clean()
        
        subnet = cleaned_data.get('subnet')
        gateway = cleaned_data.get('gateway')
        dhcp_start = cleaned_data.get('dhcp_start')
        dhcp_end = cleaned_data.get('dhcp_end')
        
        if subnet and gateway:
            try:
                network = ipaddress.IPv4Network(subnet, strict=False)
                gateway_ip = ipaddress.IPv4Address(gateway)
                
                # Check if gateway is in the subnet
                if gateway_ip not in network:
                    raise ValidationError("Gateway IP must be within the subnet range")
                
                # Validate DHCP range if provided
                if dhcp_start and dhcp_end:
                    dhcp_start_ip = ipaddress.IPv4Address(dhcp_start)
                    dhcp_end_ip = ipaddress.IPv4Address(dhcp_end)
                    
                    if dhcp_start_ip not in network:
                        raise ValidationError("DHCP start IP must be within the subnet range")
                    
                    if dhcp_end_ip not in network:
                        raise ValidationError("DHCP end IP must be within the subnet range")
                    
                    if dhcp_start_ip >= dhcp_end_ip:
                        raise ValidationError("DHCP start IP must be less than end IP")
                        
            except ipaddress.AddressValueError as e:
                raise ValidationError(f"Invalid IP address or network: {e}")
        
        return cleaned_data


class VPCCreateForm(forms.Form):
    """Template-based VPC creation form"""
    
    # Basic VPC information
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., production-web-vpc'
        }),
        help_text="VPC name (must be ≤ 11 characters for Kubernetes)"
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Description of this VPC'
        })
    )
    
    fabric = DynamicModelChoiceField(
        queryset=HedgehogFabric.objects.filter(sync_status='synced'),
        widget=StaticSelect2(),
        help_text="Select the target Hedgehog fabric"
    )
    
    template = forms.ChoiceField(
        choices=[
            ('basic', 'Basic VPC - Single subnet'),
            ('web-db', 'Web + Database - Two-tier application'),
            ('three-tier', 'Three-Tier - Web, App, Database'),
            ('custom', 'Custom Configuration'),
        ],
        initial='basic',
        widget=StaticSelect2(),
        help_text="Select a VPC template"
    )
    
    # Namespace selection
    ipv4_namespace = DynamicModelChoiceField(
        queryset=IPv4Namespace.objects.none(),
        required=False,
        widget=StaticSelect2(),
        help_text="IPv4 namespace for IP allocation"
    )
    
    vlan_namespace = DynamicModelChoiceField(
        queryset=VLANNamespace.objects.none(),
        required=False,
        widget=StaticSelect2(),
        help_text="VLAN namespace for VLAN allocation"
    )
    
    # Template customization
    base_subnet = forms.CharField(
        initial='10.100.0.0/16',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10.100.0.0/16'
        }),
        help_text="Base network for subnet allocation"
    )
    
    base_vlan = forms.IntegerField(
        initial=1100,
        min_value=1,
        max_value=4094,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '1100'
        }),
        help_text="Starting VLAN ID"
    )
    
    enable_dhcp = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Enable DHCP on all subnets"
    )
    
    apply_immediately = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Apply VPC to Kubernetes cluster immediately"
    )
    
    def __init__(self, *args, **kwargs):
        fabric_id = kwargs.pop('fabric_id', None)
        super().__init__(*args, **kwargs)
        
        if fabric_id:
            try:
                fabric = HedgehogFabric.objects.get(pk=fabric_id)
                self.fields['fabric'].initial = fabric
                self.fields['ipv4_namespace'].queryset = IPv4Namespace.objects.filter(fabric=fabric)
                self.fields['vlan_namespace'].queryset = VLANNamespace.objects.filter(fabric=fabric)
            except HedgehogFabric.DoesNotExist:
                pass
    
    def clean_name(self):
        """Validate VPC name for Kubernetes"""
        name = self.cleaned_data.get('name')
        
        if not name:
            return name
        
        # Kubernetes name validation
        if len(name) > 11:
            raise ValidationError("VPC name must be 11 characters or less for Kubernetes")
        
        if not name.islower():
            raise ValidationError("VPC name must be lowercase")
        
        if not name.replace('-', '').replace('_', '').isalnum():
            raise ValidationError("VPC name can only contain lowercase letters, numbers, and hyphens")
        
        # Check uniqueness within fabric
        fabric = self.cleaned_data.get('fabric')
        if fabric:
            if VPC.objects.filter(fabric=fabric, name=name).exists():
                raise ValidationError(f"A VPC named '{name}' already exists in this fabric")
        
        return name
    
    def clean_base_subnet(self):
        """Validate base subnet"""
        base_subnet = self.cleaned_data.get('base_subnet')
        
        try:
            network = ipaddress.IPv4Network(base_subnet, strict=False)
            return str(network)
        except ipaddress.AddressValueError as e:
            raise ValidationError(f"Invalid network: {e}")
    
    def generate_subnet_config(self):
        """Generate subnet configuration based on template"""
        template = self.cleaned_data.get('template')
        base_subnet = self.cleaned_data.get('base_subnet', '10.100.0.0/16')
        base_vlan = self.cleaned_data.get('base_vlan', 1100)
        enable_dhcp = self.cleaned_data.get('enable_dhcp', True)
        
        try:
            base_network = ipaddress.IPv4Network(base_subnet, strict=False)
        except ipaddress.AddressValueError:
            return {}
        
        subnets_config = {}
        
        if template == 'basic':
            # Single subnet
            subnet_network = list(base_network.subnets(new_prefix=24))[0]
            gateway = str(subnet_network.network_address + 1)
            
            subnets_config['main'] = {
                'subnet': str(subnet_network),
                'gateway': gateway,
                'vlan': base_vlan,
            }
            
            if enable_dhcp:
                subnets_config['main']['dhcp'] = {'enable': True}
        
        elif template == 'web-db':
            # Two subnets
            subnets = list(base_network.subnets(new_prefix=24))
            
            subnets_config['web'] = {
                'subnet': str(subnets[0]),
                'gateway': str(subnets[0].network_address + 1),
                'vlan': base_vlan,
            }
            
            subnets_config['db'] = {
                'subnet': str(subnets[1]),
                'gateway': str(subnets[1].network_address + 1),
                'vlan': base_vlan + 1,
            }
            
            if enable_dhcp:
                subnets_config['web']['dhcp'] = {'enable': True}
                subnets_config['db']['dhcp'] = {'enable': True}
        
        elif template == 'three-tier':
            # Three subnets
            subnets = list(base_network.subnets(new_prefix=24))
            
            subnets_config['web'] = {
                'subnet': str(subnets[0]),
                'gateway': str(subnets[0].network_address + 1),
                'vlan': base_vlan,
            }
            
            subnets_config['app'] = {
                'subnet': str(subnets[1]),
                'gateway': str(subnets[1].network_address + 1),
                'vlan': base_vlan + 1,
            }
            
            subnets_config['db'] = {
                'subnet': str(subnets[2]),
                'gateway': str(subnets[2].network_address + 1),
                'vlan': base_vlan + 2,
            }
            
            if enable_dhcp:
                for subnet_name in ['web', 'app', 'db']:
                    subnets_config[subnet_name]['dhcp'] = {'enable': True}
        
        return subnets_config


# Create formset for multiple subnet configurations
SubnetConfigFormSet = formset_factory(
    SubnetConfigForm,
    extra=1,
    max_num=10,
    validate_max=True,
    can_delete=True
)


class VPCCustomForm(forms.Form):
    """Custom VPC configuration form"""
    
    name = forms.CharField(max_length=100)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
    fabric = DynamicModelChoiceField(queryset=HedgehogFabric.objects.filter(sync_status='synced'))
    ipv4_namespace = DynamicModelChoiceField(queryset=IPv4Namespace.objects.none(), required=False)
    vlan_namespace = DynamicModelChoiceField(queryset=VLANNamespace.objects.none(), required=False)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add dynamic subnet forms
        if 'data' in kwargs:
            # Count subnet forms in submitted data
            subnet_count = 0
            for key in kwargs['data'].keys():
                if key.startswith('subnet_') and key.endswith('_name'):
                    subnet_count += 1
            
            for i in range(subnet_count):
                self._add_subnet_form(i)
        else:
            # Add one subnet form by default
            self._add_subnet_form(0)
    
    def _add_subnet_form(self, index):
        """Add subnet configuration fields"""
        prefix = f'subnet_{index}'
        
        self.fields[f'{prefix}_name'] = forms.CharField(
            max_length=50,
            required=True,
            label=f'Subnet {index + 1} Name'
        )
        
        self.fields[f'{prefix}_subnet'] = forms.CharField(
            required=True,
            label=f'Subnet {index + 1} CIDR'
        )
        
        self.fields[f'{prefix}_gateway'] = forms.GenericIPAddressField(
            protocol='IPv4',
            required=True,
            label=f'Subnet {index + 1} Gateway'
        )
        
        self.fields[f'{prefix}_vlan'] = forms.IntegerField(
            min_value=1,
            max_value=4094,
            required=True,
            label=f'Subnet {index + 1} VLAN'
        )
        
        self.fields[f'{prefix}_dhcp'] = forms.BooleanField(
            required=False,
            initial=True,
            label=f'Subnet {index + 1} DHCP'
        )


class VPCApplyForm(forms.Form):
    """Form for applying VPC to cluster"""
    
    vpc = forms.ModelChoiceField(
        queryset=VPC.objects.filter(kubernetes_status__in=['pending', 'error']),
        widget=StaticSelect2(),
        help_text="Select VPC to apply to cluster"
    )
    
    dry_run = forms.BooleanField(
        required=False,
        help_text="Perform dry run (validate but don't apply)"
    )
    
    force = forms.BooleanField(
        required=False,
        help_text="Force apply even if VPC already exists in cluster"
    )


class VPCBulkActionsForm(forms.Form):
    """Form for bulk VPC operations"""
    
    vpcs = forms.ModelMultipleChoiceField(
        queryset=VPC.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        help_text="Select VPCs to operate on"
    )
    
    action = forms.ChoiceField(
        choices=[
            ('apply', 'Apply to Cluster'),
            ('delete', 'Delete from Cluster and NetBox'),
            ('sync_status', 'Sync Status from Cluster'),
            ('export', 'Export Configuration'),
        ],
        widget=StaticSelect2(),
        help_text="Action to perform on selected VPCs"
    )
    
    confirm = forms.BooleanField(
        required=True,
        help_text="Confirm that you want to perform this action"
    )


class IPv4NamespaceForm(NetBoxModelForm):
    """Form for IPv4 namespace management"""
    
    class Meta:
        model = IPv4Namespace
        fields = ['name', 'description', 'fabric', 'subnets_config', 'tags']
        widgets = {
            'subnets_config': forms.Textarea(attrs={
                'rows': 8,
                'class': 'form-control',
                'placeholder': 'JSON array of subnet CIDRs, e.g., ["10.0.0.0/16", "192.168.0.0/16"]'
            }),
        }


class VLANNamespaceForm(NetBoxModelForm):
    """Form for VLAN namespace management"""
    
    class Meta:
        model = VLANNamespace
        fields = ['name', 'description', 'fabric', 'ranges_config', 'tags']
        widgets = {
            'ranges_config': forms.Textarea(attrs={
                'rows': 8,
                'class': 'form-control',
                'placeholder': 'JSON array of VLAN ranges, e.g., [{"from": 1000, "to": 2999}]'
            }),
        }