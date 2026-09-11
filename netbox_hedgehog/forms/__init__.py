# Forms for Hedgehog NetBox Plugin
from django import forms
from django.forms import ModelForm
from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC, External

class HedgehogFabricForm(ModelForm):
    """Form for creating and editing Hedgehog Fabrics"""
    
    class Meta:
        model = HedgehogFabric
        fields = [
            'name', 'description', 'status', 
            'kubernetes_server', 'kubernetes_token', 'kubernetes_ca_cert',
            'kubernetes_namespace', 'sync_enabled', 'sync_interval'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'kubernetes_server': forms.URLInput(attrs={
                'placeholder': 'https://k8s-api.example.com:6443',
                'class': 'form-control'
            }),
            # DIET-625: never render the stored token back into the page.
            # PasswordInput(render_value=False) keeps the field writable while
            # ensuring the response body carries no credential material.
            'kubernetes_token': forms.PasswordInput(
                render_value=False,
                attrs={
                    'placeholder': 'Leave blank to keep the existing token',
                    'class': 'form-control',
                    'autocomplete': 'new-password',
                },
            ),
            'kubernetes_ca_cert': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'CA certificate for TLS verification (optional)',
                'class': 'form-control'
            }),
            'kubernetes_namespace': forms.TextInput(attrs={
                'placeholder': 'default',
                'class': 'form-control'
            }),
            'sync_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sync_interval': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'kubernetes_server': 'Kubernetes API server URL for this fabric',
            'kubernetes_token': 'Service account token with appropriate permissions',
            'kubernetes_ca_cert': 'CA certificate for TLS verification (leave empty for insecure connections)',
            'kubernetes_namespace': 'Default namespace for this fabric\'s resources',
            'sync_interval': 'Sync interval in seconds (0 to disable)',
        }

    def clean_kubernetes_token(self):
        """Blank means "unchanged", not "clear the credential".

        The widget deliberately renders empty (DIET-625), so an ordinary save
        submits an empty value. Treating that as a clear would silently rotate
        every configured fabric's credential and break its connectivity --
        turning a disclosure fix into an outage.
        """
        submitted = self.cleaned_data.get('kubernetes_token')
        if not submitted and self.instance and self.instance.pk:
            return self.instance.kubernetes_token
        return submitted

    def clean_kubernetes_ca_cert(self):
        """Blank means "unchanged" -- same rationale as the token."""
        submitted = self.cleaned_data.get('kubernetes_ca_cert')
        if not submitted and self.instance and self.instance.pk:
            return self.instance.kubernetes_ca_cert
        return submitted

# Import forms from other modules
from .vpc_api import VPCForm, ExternalForm, IPv4NamespaceForm, ExternalAttachmentForm, ExternalPeeringForm, VPCAttachmentForm, VPCPeeringForm
from .wiring_api import ConnectionForm, SwitchForm, ServerForm, SwitchGroupForm, VLANNamespaceForm
from .topology_planning import (
    BreakoutOptionForm,
    DeviceTypeExtensionForm,
    TopologyPlanForm,
    PlanServerClassForm,
    PlanServerNICForm,
    PlanSwitchClassForm,
    PlanServerConnectionForm,
    SwitchPortZoneForm,
)

__all__ = [
    'HedgehogFabricForm',
    'VPCForm',
    'ExternalForm',
    'IPv4NamespaceForm',
    'ExternalAttachmentForm',
    'ExternalPeeringForm',
    'VPCAttachmentForm',
    'VPCPeeringForm',
    'ConnectionForm',
    'SwitchForm',
    'ServerForm',
    'SwitchGroupForm',
    'VLANNamespaceForm',
    'BreakoutOptionForm',
    'DeviceTypeExtensionForm',
    'TopologyPlanForm',
    'PlanServerClassForm',
    'PlanServerNICForm',
    'PlanSwitchClassForm',
    'PlanServerConnectionForm',
    'SwitchPortZoneForm',
]
