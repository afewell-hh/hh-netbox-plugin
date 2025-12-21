"""
Topology Planning Forms (DIET Module)
Forms for BreakoutOption and DeviceTypeExtension models.
"""

from django import forms
from netbox.forms import NetBoxModelForm
from dcim.models import DeviceType, ModuleType
from utilities.forms.fields import DynamicModelChoiceField

from ..models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
)
from ..choices import ConnectionDistributionChoices


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


# =============================================================================
# Topology Plan Forms (DIET-004)
# =============================================================================

class TopologyPlanForm(NetBoxModelForm):
    """
    Form for creating and editing TopologyPlans.

    TopologyPlans are the top-level container for network designs, containing
    server classes, switch classes, and connection specifications.
    """

    class Meta:
        model = TopologyPlan
        fields = [
            'name',
            'customer_name',
            'description',
            'status',
            'notes',
            'tags',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'name': "Plan name (e.g., 'Cambium 2MW', '128-GPU Training Cluster')",
            'customer_name': 'Customer or project name (optional)',
            'description': 'Detailed description of the topology plan',
            'status': 'Current status of the plan',
            'notes': 'Additional notes about this plan',
        }


class PlanServerClassForm(NetBoxModelForm):
    """
    Form for creating and editing PlanServerClasses.

    Server classes define groups of identical servers with their quantities
    and connection requirements. Quantity is the primary user input that
    drives switch quantity calculations.
    """

    plan = forms.ModelChoiceField(
        queryset=TopologyPlan.objects.all(),
        label='Topology Plan',
        help_text='Select the topology plan this server class belongs to'
    )

    server_device_type = forms.ModelChoiceField(
        queryset=DeviceType.objects.all(),
        label='Server Device Type',
        help_text='Select the NetBox DeviceType for this server model'
    )

    class Meta:
        model = PlanServerClass
        fields = [
            'plan',
            'server_class_id',
            'description',
            'category',
            'quantity',
            'gpus_per_server',
            'server_device_type',
            'notes',
            'tags',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'server_class_id': "Unique identifier (e.g., 'INF-B200', 'GPU-001')",
            'description': 'Human-readable description of this server class',
            'category': 'Server category (GPU, Storage, Infrastructure)',
            'quantity': 'Number of servers in this class (PRIMARY INPUT)',
            'gpus_per_server': 'Number of GPUs per server (0 for non-GPU servers)',
            'server_device_type': 'Optional reference to NetBox DeviceType',
            'notes': 'Additional notes about this server class',
        }


class PlanSwitchClassForm(NetBoxModelForm):
    """
    Form for creating and editing PlanSwitchClasses.

    Switch classes define groups of identical switches. Their quantities are
    automatically calculated based on server port demand, but can be manually
    overridden via the override_quantity field.
    """

    plan = forms.ModelChoiceField(
        queryset=TopologyPlan.objects.all(),
        label='Topology Plan',
        help_text='Select the topology plan this switch class belongs to'
    )

    device_type_extension = forms.ModelChoiceField(
        queryset=DeviceTypeExtension.objects.select_related('device_type', 'device_type__manufacturer'),
        label='Device Type (with Hedgehog Extension)',
        help_text='Select the switch DeviceType with Hedgehog metadata'
    )

    class Meta:
        model = PlanSwitchClass
        fields = [
            'plan',
            'switch_class_id',
            'fabric',
            'hedgehog_role',
            'device_type_extension',
            'uplink_ports_per_switch',
            'mclag_pair',
            'override_quantity',
            'notes',
            'tags',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'switch_class_id': "Unique identifier (e.g., 'fe-gpu-leaf', 'be-spine')",
            'fabric': 'Fabric type (Frontend, Backend, OOB)',
            'hedgehog_role': 'Hedgehog role (Spine, Server Leaf, Border Leaf)',
            'device_type_extension': 'Switch model with Hedgehog-specific metadata',
            'uplink_ports_per_switch': 'Number of uplink ports to reserve per switch',
            'mclag_pair': 'Whether switches are deployed in MCLAG pairs (affects quantity rounding)',
            'override_quantity': 'Manual override of calculated quantity (leave empty to use calculated value)',
            'notes': 'Additional notes about this switch class',
        }


# =============================================================================
# PlanServerConnection Form (DIET-005)
# =============================================================================

class PlanServerConnectionForm(NetBoxModelForm):
    """
    Form for creating and editing PlanServerConnections.

    Server connections define how servers connect to switches, including
    port counts, distribution strategies, and optional rail assignments
    for rail-optimized topologies.
    """

    class Meta:
        model = PlanServerConnection
        fields = '__all__'
        # Note: Using '__all__' to let NetBox handle standard fields automatically
        widgets = {
            'connection_name': forms.TextInput(attrs={'placeholder': 'frontend, backend-rail-0, etc.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If editing an existing connection, filter target_switch_class to same plan
        if self.instance and self.instance.pk and self.instance.server_class:
            plan = self.instance.server_class.plan
            self.fields['target_switch_class'].queryset = PlanSwitchClass.objects.filter(plan=plan)
            self.fields['target_switch_class'].help_text = f'Switch classes from plan: {plan.name}'
        else:
            # For new connections, add help text about plan filtering
            self.fields['target_switch_class'].help_text = (
                'Select a server class first. Target switch must be from the same plan as the server class.'
            )

    def clean(self):
        """Validate that rail is required when distribution is rail-optimized"""
        # Call parent clean - it modifies self.cleaned_data in place
        super().clean()

        # Use self.cleaned_data instead of return value from super().clean()
        distribution = self.cleaned_data.get('distribution')
        rail = self.cleaned_data.get('rail')
        server_class = self.cleaned_data.get('server_class')
        target_switch_class = self.cleaned_data.get('target_switch_class')

        # Rail validation: required only for rail-optimized distribution
        if distribution == ConnectionDistributionChoices.RAIL_OPTIMIZED:
            if rail is None or rail == '':  # rail can be 0, but not None or empty string
                self.add_error('rail', 'Rail is required when distribution is set to rail-optimized.')

        # Ensure target_switch_class is from same plan as server_class
        if server_class and target_switch_class:
            if server_class.plan != target_switch_class.plan:
                self.add_error(
                    'target_switch_class',
                    f'Target switch class must be from the same plan as server class '
                    f'({server_class.plan.name}). Selected switch is from plan {target_switch_class.plan.name}.'
                )

        # Don't return anything - NetBoxModelForm.clean() returns None
