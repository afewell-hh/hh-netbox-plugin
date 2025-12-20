"""
Topology Planning Forms (DIET Module)
Forms for BreakoutOption and DeviceTypeExtension models.
"""

from django import forms
from netbox.forms import NetBoxModelForm
from dcim.models import DeviceType
from utilities.forms.fields import DynamicModelChoiceField

from ..models.topology_planning import BreakoutOption, DeviceTypeExtension


class BreakoutOptionForm(NetBoxModelForm):
    """
    Form for creating and editing BreakoutOptions.

    BreakoutOptions define how physical ports can be broken out into multiple
    logical ports (e.g., 1x800G -> 2x400G, 4x200G, or 8x100G).
    """

    class Meta:
        model = BreakoutOption
        fields = [
            'breakout_id',
            'from_speed',
            'logical_ports',
            'logical_speed',
            'optic_type',
            'tags',
        ]
        help_texts = {
            'breakout_id': "Unique identifier (e.g., '2x400g', '4x200g')",
            'from_speed': "Native port speed in Gbps (e.g., 800 for 800G)",
            'logical_ports': "Number of logical ports after breakout",
            'logical_speed': "Speed per logical port in Gbps",
            'optic_type': "Optic type (e.g., 'QSFP-DD', 'QSFP28')",
        }


class DeviceTypeExtensionForm(NetBoxModelForm):
    """
    Form for creating and editing DeviceTypeExtensions.

    DeviceTypeExtensions add Hedgehog-specific metadata to NetBox DeviceTypes,
    including supported breakout options, MCLAG capability, and fabric roles.
    """

    device_type = DynamicModelChoiceField(
        queryset=DeviceType.objects.all(),
        label='Device Type',
        help_text='Select the NetBox DeviceType to add Hedgehog metadata to'
    )

    hedgehog_roles = forms.MultipleChoiceField(
        choices=[
            ('spine', 'Spine'),
            ('server-leaf', 'Server Leaf'),
            ('border-leaf', 'Border Leaf'),
            ('virtual', 'Virtual/Management'),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text='Select all roles this device type can fulfill in Hedgehog fabrics'
    )

    class Meta:
        model = DeviceTypeExtension
        fields = [
            'device_type',
            'mclag_capable',
            'hedgehog_roles',
            'supported_breakouts',
            'native_speed',
            'uplink_ports',
            'notes',
            'tags',
        ]
        widgets = {
            'supported_breakouts': forms.Textarea(attrs={'rows': 3, 'placeholder': '["1x800g", "2x400g", "4x200g"]'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'device_type': 'NetBox DeviceType this metadata applies to',
            'mclag_capable': 'Whether this device supports MCLAG (Multi-Chassis Link Aggregation)',
            'supported_breakouts': 'JSON list of supported breakout IDs (e.g., ["1x800g", "2x400g"])',
            'native_speed': 'Native port speed in Gbps (e.g., 800 for 800G)',
            'uplink_ports': 'Default number of uplink ports to reserve for spine connections',
            'notes': 'Additional Hedgehog-specific notes about this device type',
        }
