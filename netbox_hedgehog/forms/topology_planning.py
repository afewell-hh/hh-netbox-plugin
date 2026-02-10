"""
Topology Planning Forms (DIET Module)
Forms for BreakoutOption and DeviceTypeExtension models.
"""

from django import forms
from netbox.forms import NetBoxModelForm
from dcim.models import DeviceType, ModuleType, InterfaceTemplate
from utilities.forms.fields import DynamicModelChoiceField

from ..models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    SwitchPortZone,
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
    Form for creating and editing PlanSwitchClasses (DIET-165 Phase 5).

    Switch classes define groups of identical switches. Their quantities are
    automatically calculated based on server port demand, but can be manually
    overridden via the override_quantity field.

    Redundancy fields (redundancy_type/redundancy_group) replace deprecated mclag_pair.
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
            'redundancy_type',
            'redundancy_group',
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
            'redundancy_type': 'Redundancy mode (MCLAG=even pairs, ESLAG=2-4 switches, Rail-Optimized=N switches for N rails)',
            'redundancy_group': 'Redundancy group name (must match a SwitchGroup). Required if redundancy_type is set.',
            'uplink_ports_per_switch': '[DEPRECATED] Number of uplink ports per switch. Use SwitchPortZone with zone_type="uplink" instead. This field will be removed in v3.0.',
            'mclag_pair': '[DEPRECATED] Use redundancy_type="mclag" instead. This field will be removed in v3.0.',
            'override_quantity': 'Manual override of calculated quantity (leave empty to use calculated value). Must satisfy redundancy constraints (MCLAG=even, ESLAG=2-4).',
            'notes': 'Additional notes about this switch class',
        }


# =============================================================================
# PlanServerConnection Form (DIET-005)
# =============================================================================

class PlanServerConnectionForm(NetBoxModelForm):
    """
    Form for creating and editing PlanServerConnections (DIET-165 Phase 5).

    Server connections define how servers connect to switches, including
    port counts, distribution strategies, and optional rail assignments
    for rail-optimized topologies.

    NIC modeling fields (nic_module_type/server_interface_template) support
    NetBox-native device modeling patterns. Legacy nic_slot mode is supported
    for backward compatibility.
    """

    server_interface_template = DynamicModelChoiceField(
        queryset=InterfaceTemplate.objects.none(),
        required=False,
        label='Server Interface Template',
        help_text='Recommended: Select the first server interface template for this connection. '
                  'If multiple ports are needed, subsequent interfaces will be used automatically. '
                  'Mutually exclusive with nic_slot (legacy mode).'
    )

    class Meta:
        model = PlanServerConnection
        fields = '__all__'
        # Note: Using '__all__' to let NetBox handle standard fields automatically
        widgets = {
            'connection_name': forms.TextInput(attrs={'placeholder': 'frontend, backend-rail-0, etc.'}),
        }
        help_texts = {
            'nic_slot': '[LEGACY] NIC slot identifier (e.g., "NIC1"). Only used when server_interface_template is not set. Use server_interface_template for NetBox-native interface modeling.'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter target_switch_class based on server_class selection
        server_class = None

        # Check if editing existing connection
        if self.instance and self.instance.pk and self.instance.server_class:
            server_class = self.instance.server_class
        else:
            # For add mode, check if server_class is in form data or initial data
            server_class_id = self.data.get('server_class') or self.initial.get('server_class')
            if server_class_id:
                try:
                    server_class = PlanServerClass.objects.get(pk=server_class_id)
                except (PlanServerClass.DoesNotExist, ValueError):
                    pass

        # Apply filtering if we found a server_class
        if server_class:
            plan = server_class.plan
            self.fields['target_switch_class'].queryset = PlanSwitchClass.objects.filter(plan=plan)
            self.fields['target_switch_class'].help_text = f'Switch classes from plan: {plan.name}'

            # Filter server_interface_template to device type interfaces
            if server_class.server_device_type:
                self.fields['server_interface_template'].queryset = InterfaceTemplate.objects.filter(
                    device_type=server_class.server_device_type
                ).order_by('name')

                # Show available interface count
                interface_count = self.fields['server_interface_template'].queryset.count()
                self.fields['server_interface_template'].help_text = (
                    f'Select first interface from {server_class.server_device_type} '
                    f'({interface_count} interfaces available). '
                    f'Subsequent interfaces will be used if ports_per_connection > 1.'
                )
        else:
            # No server class selected yet - show help text
            self.fields['target_switch_class'].help_text = (
                'Select a server class first. Target switch must be from the same plan as the server class.'
            )
            self.fields['server_interface_template'].help_text = (
                'Select a server class first to see available interfaces.'
            )

    def clean(self):
        """Validate form data including interface selection"""
        from django.core.exceptions import ValidationError as DjangoValidationError

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

        # Interface validation is handled by model.clean()
        # Create temporary instance to validate
        if self.cleaned_data and not self._errors:
            # Use existing instance if available (edit mode), otherwise create temp
            if self.instance and self.instance.pk:
                # Update existing instance with form data for validation
                for key, value in self.cleaned_data.items():
                    if key == 'tags':
                        continue
                    if hasattr(self.instance, key):
                        setattr(self.instance, key, value)
                temp_instance = self.instance
                if temp_instance.custom_field_data is None:
                    temp_instance.custom_field_data = {}
            else:
                # Create new temporary instance
                temp_instance = PlanServerConnection(**{
                    k: v for k, v in self.cleaned_data.items()
                    if k != 'tags' and k in [f.name for f in PlanServerConnection._meta.get_fields()]
                })
                # Initialize custom_field_data to avoid AttributeError in NetBox model clean()
                if temp_instance.custom_field_data is None:
                    temp_instance.custom_field_data = {}

            try:
                temp_instance.clean()
            except DjangoValidationError as e:
                # Surface model validation errors to form
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            self.add_error(field, error)
                elif hasattr(e, 'messages'):
                    for error in e.messages:
                        self.add_error(None, error)

        # Note: Cross-plan validation is handled by queryset filtering in __init__()
        # Django's form validation will reject any target_switch_class not in the filtered queryset

        # Don't return anything - NetBoxModelForm.clean() returns None


# =============================================================================
# SwitchPortZone Form (DIET-011)
# =============================================================================

class SwitchPortZoneForm(NetBoxModelForm):
    """
    Form for creating and editing SwitchPortZones.
    """

    switch_class = forms.ModelChoiceField(
        queryset=PlanSwitchClass.objects.all(),
        label='Switch Class',
        help_text='Switch class this port zone belongs to',
    )

    breakout_option = forms.ModelChoiceField(
        queryset=BreakoutOption.objects.all(),
        label='Breakout Option',
        required=False,
        help_text='Optional breakout option for logical ports',
    )

    class Meta:
        model = SwitchPortZone
        fields = [
            'switch_class',
            'zone_name',
            'zone_type',
            'port_spec',
            'breakout_option',
            'allocation_strategy',
            'allocation_order',
            'priority',
            'tags',
        ]
        widgets = {
            'allocation_order': forms.Textarea(attrs={'rows': 2}),
        }
        help_texts = {
            'zone_name': "Zone name (e.g., 'server-ports', 'spine-uplinks')",
            'port_spec': "Port specification (e.g., '1-48', '1-32:2', '1,3,5')",
            'allocation_order': 'JSON list of port numbers used when strategy is custom',
        }
