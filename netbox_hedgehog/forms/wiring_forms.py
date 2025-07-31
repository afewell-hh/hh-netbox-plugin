"""
Wiring Infrastructure Forms
Forms for managing switches, connections, and physical network infrastructure.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory
import json

# NetBox imports
from netbox.forms import NetBoxModelForm
# from utilities.forms.fields import DynamicModelChoiceField
# from utilities.forms.widgets import StaticSelect2

# Plugin imports
from ..models.fabric import HedgehogFabric
from ..models.wiring import Switch, Connection, Server, SwitchGroup, VLANNamespace
from ..choices import SwitchRoleChoices, ConnectionTypeChoices


class SwitchForm(NetBoxModelForm):
    """Form for switch configuration"""
    
    # Basic switch information
    asn = forms.IntegerField(
        min_value=1,
        max_value=4294967295,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '65101'
        }),
        help_text="BGP ASN for this switch"
    )
    
    ip_address = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '172.30.0.8/21'
        }),
        help_text="Management IP address with prefix"
    )
    
    protocol_ip = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '172.30.8.2/32'
        }),
        help_text="Protocol IP address (loopback)"
    )
    
    vtep_ip = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '172.30.12.0/32'
        }),
        help_text="VTEP IP address for VXLAN"
    )
    
    boot_mac = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0c:20:12:ff:00:00'
        }),
        help_text="Boot MAC address"
    )
    
    # Groups and namespaces (JSON fields)
    groups = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': '["mclag-1", "rack-01"]'
        }),
        help_text="JSON array of group names"
    )
    
    vlan_namespaces = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': '["default", "tenant-1"]'
        }),
        help_text="JSON array of VLAN namespace names"
    )
    
    # Redundancy configuration
    redundancy_type = forms.ChoiceField(
        choices=[
            ('', 'None'),
            ('mclag', 'MCLAG'),
            ('eslag', 'ESLAG'),
        ],
        required=False,
        widget=StaticSelect2(),
        help_text="Redundancy configuration type"
    )
    
    redundancy_group = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'mclag-1'
        }),
        help_text="Redundancy group name"
    )
    
    class Meta:
        model = Switch
        fields = [
            'name', 'description', 'fabric', 'role', 'profile', 'asn',
            'ip_address', 'protocol_ip', 'vtep_ip', 'boot_mac',
            'groups', 'vlan_namespaces', 'redundancy_type', 'redundancy_group',
            'tags'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'leaf-01'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control'
            }),
            'profile': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'vs'
            }),
        }
    
    def clean_groups(self):
        """Validate groups JSON"""
        groups = self.cleaned_data.get('groups')
        
        if not groups:
            return []
        
        try:
            groups_list = json.loads(groups)
            if not isinstance(groups_list, list):
                raise ValidationError("Groups must be a JSON array")
            return groups_list
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON format for groups")
    
    def clean_vlan_namespaces(self):
        """Validate VLAN namespaces JSON"""
        vlan_namespaces = self.cleaned_data.get('vlan_namespaces')
        
        if not vlan_namespaces:
            return []
        
        try:
            vlan_ns_list = json.loads(vlan_namespaces)
            if not isinstance(vlan_ns_list, list):
                raise ValidationError("VLAN namespaces must be a JSON array")
            return vlan_ns_list
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON format for VLAN namespaces")
    
    def save(self, commit=True):
        """Save switch with JSON field processing"""
        instance = super().save(commit=False)
        
        # Store JSON fields
        groups = self.cleaned_data.get('groups')
        vlan_namespaces = self.cleaned_data.get('vlan_namespaces')
        redundancy_type = self.cleaned_data.get('redundancy_type')
        redundancy_group = self.cleaned_data.get('redundancy_group')
        
        instance.groups_config = groups if groups else []
        instance.vlan_namespaces_config = vlan_namespaces if vlan_namespaces else []
        
        # Build redundancy configuration
        if redundancy_type and redundancy_group:
            instance.redundancy_config = {
                'type': redundancy_type,
                'group': redundancy_group
            }
        else:
            instance.redundancy_config = {}
        
        if commit:
            instance.save()
        
        return instance


class ConnectionLinkForm(forms.Form):
    """Form for individual connection link configuration"""
    
    switch = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'leaf-01'
        }),
        help_text="Switch name"
    )
    
    port = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ethernet1'
        }),
        help_text="Port name"
    )
    
    server = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'server-01'
        }),
        help_text="Server name (for server connections)"
    )
    
    location = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rack 1 Position 2'
        }),
        help_text="Physical location"
    )


class ConnectionForm(NetBoxModelForm):
    """Form for connection configuration"""
    
    # MCLAG specific fields
    mclag_domain = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'mclag-domain-1'
        }),
        help_text="MCLAG domain (for MCLAG connections)"
    )
    
    mclag_peers = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'form-control',
            'placeholder': '["leaf-01", "leaf-02"]'
        }),
        help_text="JSON array of MCLAG peer switches"
    )
    
    # ESLAG specific fields
    eslag_group = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'eslag-group-1'
        }),
        help_text="ESLAG group (for ESLAG connections)"
    )
    
    eslag_members = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'form-control',
            'placeholder': '["leaf-01", "leaf-02", "leaf-03"]'
        }),
        help_text="JSON array of ESLAG member switches"
    )
    
    # Connection links (will be built from formset)
    links_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    class Meta:
        model = Connection
        fields = [
            'name', 'description', 'fabric', 'connection_type',
            'mclag_domain', 'mclag_peers', 'eslag_group', 'eslag_members',
            'links_json', 'tags'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'leaf-01--server-01'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control'
            }),
        }
    
    def clean_mclag_peers(self):
        """Validate MCLAG peers JSON"""
        peers = self.cleaned_data.get('mclag_peers')
        
        if not peers:
            return []
        
        try:
            peers_list = json.loads(peers)
            if not isinstance(peers_list, list):
                raise ValidationError("MCLAG peers must be a JSON array")
            return peers_list
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON format for MCLAG peers")
    
    def clean_eslag_members(self):
        """Validate ESLAG members JSON"""
        members = self.cleaned_data.get('eslag_members')
        
        if not members:
            return []
        
        try:
            members_list = json.loads(members)
            if not isinstance(members_list, list):
                raise ValidationError("ESLAG members must be a JSON array")
            return members_list
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON format for ESLAG members")
    
    def save(self, commit=True):
        """Save connection with configuration processing"""
        instance = super().save(commit=False)
        
        # Build connection configuration
        config = {
            'type': instance.connection_type,
            'links': []
        }
        
        # Parse links from JSON
        links_json = self.cleaned_data.get('links_json')
        if links_json:
            try:
                config['links'] = json.loads(links_json)
            except json.JSONDecodeError:
                pass
        
        # Add type-specific configuration
        connection_type = instance.connection_type
        
        if connection_type == 'mclag':
            mclag_config = {}
            if self.cleaned_data.get('mclag_domain'):
                mclag_config['domain'] = self.cleaned_data['mclag_domain']
            if self.cleaned_data.get('mclag_peers'):
                mclag_config['peers'] = self.cleaned_data['mclag_peers']
            
            if mclag_config:
                config['mclag'] = mclag_config
        
        elif connection_type == 'eslag':
            eslag_config = {}
            if self.cleaned_data.get('eslag_group'):
                eslag_config['group'] = self.cleaned_data['eslag_group']
            if self.cleaned_data.get('eslag_members'):
                eslag_config['members'] = self.cleaned_data['eslag_members']
            
            if eslag_config:
                config['eslag'] = eslag_config
        
        instance.connection_config = config
        
        if commit:
            instance.save()
        
        return instance


# Create formset for connection links
ConnectionLinkFormSet = formset_factory(
    ConnectionLinkForm,
    extra=2,
    max_num=10,
    validate_max=True,
    can_delete=True
)


class ServerForm(NetBoxModelForm):
    """Form for server configuration"""
    
    class Meta:
        model = Server
        fields = ['name', 'description', 'fabric', 'server_config', 'tags']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'server-01'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control'
            }),
            'server_config': forms.Textarea(attrs={
                'rows': 10,
                'class': 'form-control',
                'placeholder': 'JSON configuration for server connections'
            }),
        }


class SwitchGroupForm(NetBoxModelForm):
    """Form for switch group configuration"""
    
    class Meta:
        model = SwitchGroup
        fields = ['name', 'description', 'fabric', 'group_config', 'tags']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'mclag-1'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control'
            }),
            'group_config': forms.Textarea(attrs={
                'rows': 8,
                'class': 'form-control',
                'placeholder': 'JSON configuration for switch group'
            }),
        }


# TopologyFilterForm removed - topology feature not implemented


class BulkSwitchOperationsForm(forms.Form):
    """Form for bulk switch operations"""
    
    switches = forms.ModelMultipleChoiceField(
        queryset=Switch.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        help_text="Select switches to operate on"
    )
    
    operation = forms.ChoiceField(
        choices=[
            ('update_role', 'Update Role'),
            ('update_asn', 'Update ASN'),
            ('add_to_group', 'Add to Group'),
            ('remove_from_group', 'Remove from Group'),
            ('export_config', 'Export Configuration'),
        ],
        widget=StaticSelect2(),
        help_text="Operation to perform"
    )
    
    # Operation-specific fields
    new_role = forms.ChoiceField(
        choices=SwitchRoleChoices,
        required=False,
        widget=StaticSelect2(),
        help_text="New role (for update role operation)"
    )
    
    new_asn = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=4294967295,
        help_text="New ASN (for update ASN operation)"
    )
    
    group_name = forms.CharField(
        required=False,
        max_length=50,
        help_text="Group name (for group operations)"
    )
    
    confirm = forms.BooleanField(
        required=True,
        help_text="Confirm bulk operation"
    )


class ConnectionTestForm(forms.Form):
    """Form for testing connection configuration"""
    
    connection = DynamicModelChoiceField(
        queryset=Connection.objects.all(),
        widget=StaticSelect2(),
        help_text="Select connection to test"
    )
    
    test_type = forms.ChoiceField(
        choices=[
            ('validate', 'Validate Configuration'),
            ('ping', 'Ping Test'),
            ('lldp', 'LLDP Discovery'),
            ('full', 'Full Connectivity Test'),
        ],
        initial='validate',
        widget=StaticSelect2(),
        help_text="Type of test to perform"
    )
    
    include_servers = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Include server endpoints in test"
    )