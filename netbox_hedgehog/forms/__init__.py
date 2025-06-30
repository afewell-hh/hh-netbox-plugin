# Basic forms for initial plugin loading
from django import forms
from netbox.forms import NetBoxModelForm
from ..models.fabric import HedgehogFabric

# Simple forms for testing
class HedgehogFabricForm(NetBoxModelForm):
    class Meta:
        model = HedgehogFabric
        fields = ['name', 'description']

# Legacy forms (for compatibility) - temporarily disabled
# from .fabric import FabricForm as LegacyFabricForm
# from .vpc_api import VPCForm as LegacyVPCForm, ExternalForm, IPv4NamespaceForm as LegacyIPv4NamespaceForm
# from .wiring_api import ConnectionForm as LegacyConnectionForm, SwitchForm as LegacySwitchForm, ServerForm as LegacyServerForm

__all__ = [
    'HedgehogFabricForm',
]