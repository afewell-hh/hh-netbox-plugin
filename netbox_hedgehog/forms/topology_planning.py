"""
Topology Planning Forms (DIET Module)
Forms for BreakoutOption and DeviceTypeExtension models.
"""

from collections import Counter

from django import forms
from netbox.forms import NetBoxModelForm
from dcim.models import DeviceType, ModuleType
from utilities.forms.fields import DynamicModelChoiceField


# ---------------------------------------------------------------------------
# Transceiver picker label helpers (DIET-460)
# ---------------------------------------------------------------------------

def _xcvr_label(mt) -> str:
    """Single-value description-first label for one ModuleType (no collision check)."""
    if mt is None:
        return '—'
    desc = (mt.description or '').strip()
    if desc:
        return f'{desc} ({mt.model})'
    return f'{mt.manufacturer} {mt.model}'


def _make_xcvr_label_fn(queryset):
    """
    Return a label function for a transceiver ModelChoiceField.

    Pre-scans *queryset* to detect description collisions. When two or more
    ModuleTypes in the queryset share the same non-empty description, the
    returned label function appends ``[manufacturer]`` to disambiguate.

    Usage::

        qs = ModuleType.objects.filter(...).select_related('manufacturer')
        field.label_from_instance = _make_xcvr_label_fn(qs)
    """
    # Count descriptions across the queryset (blank descriptions never collide)
    desc_counts: Counter = Counter()
    for mt in queryset:
        desc = (mt.description or '').strip()
        if desc:
            desc_counts[desc] += 1

    def label_fn(mt) -> str:
        desc = (mt.description or '').strip()
        if not desc:
            return f'{mt.manufacturer} {mt.model}'
        if desc_counts[desc] > 1:
            return f'{desc} ({mt.model}) [{mt.manufacturer}]'
        return f'{desc} ({mt.model})'

    return label_fn

from ..models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    TopologyPlan,
    PlanServerClass,
    PlanServerNIC,
    PlanSwitchClass,
    PlanServerConnection,
    SwitchPortZone,
)
from ..choices import ConnectionDistributionChoices, FabricClassChoices, CageTypeChoices, MediumChoices, ConnectorChoices
from ..services._fabric_utils import _legacy_fabric_name_to_class


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

    fabric_name = forms.CharField(
        label='Fabric Name',
        required=True,
        help_text='User-defined fabric name used to partition switch-to-switch and scoped exports.',
    )

    fabric_class = forms.ChoiceField(
        label='Fabric Class',
        choices=[('', '---------')] + list(FabricClassChoices.CHOICES),
        required=True,
        initial='',
        help_text='Required explicit selection. Managed exports as Switch CRDs; unmanaged exports as Server surrogates.',
    )

    def __init__(self, *args, **kwargs):
        data = kwargs.get('data')
        if data is not None and hasattr(data, 'copy'):
            mutable_data = data.copy()
            if not mutable_data.get('fabric_name') and mutable_data.get('fabric'):
                mutable_data['fabric_name'] = mutable_data['fabric']
            if not mutable_data.get('fabric_class') and mutable_data.get('fabric'):
                mutable_data['fabric_class'] = _legacy_fabric_name_to_class(mutable_data['fabric'])
            kwargs['data'] = mutable_data
        super().__init__(*args, **kwargs)

    class Meta:
        model = PlanSwitchClass
        fields = [
            'plan',
            'switch_class_id',
            'fabric_name',
            'fabric_class',
            'hedgehog_role',
            'device_type_extension',
            'topology_mode',
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
            'fabric_name': 'User-defined fabric name used for partitioning and scoped export discovery.',
            'fabric_class': 'Behavioral class that controls whether switches export as managed switches or unmanaged surrogates.',
            'hedgehog_role': 'Hedgehog role (Spine, Server Leaf, Border Leaf)',
            'device_type_extension': 'Switch model with Hedgehog-specific metadata',
            'redundancy_type': 'Redundancy mode (MCLAG=even pairs with peer link, ESLAG=2-4 switches without peer link)',
            'redundancy_group': 'Redundancy group name (must match a SwitchGroup). Required if redundancy_type is set.',
            'uplink_ports_per_switch': '[DEPRECATED] Number of uplink ports per switch. Use SwitchPortZone with zone_type="uplink" instead. This field will be removed in v3.0.',
            'mclag_pair': '[DEPRECATED] Use redundancy_type="mclag" instead. This field will be removed in v3.0.',
            'override_quantity': 'Manual override of calculated quantity (leave empty to use calculated value). Must satisfy redundancy constraints (MCLAG=even, ESLAG=2-4).',
            'notes': 'Additional notes about this switch class',
        }


# =============================================================================
# =============================================================================
# PlanServerNIC Form (DIET-294)
# =============================================================================

class PlanServerNICForm(NetBoxModelForm):
    """
    Form for creating and editing PlanServerNICs (DIET-294).

    One PlanServerNIC represents one physical NIC/DPU card slot.
    The generator creates exactly one NetBox Module per PlanServerNIC.
    """

    server_class = forms.ModelChoiceField(
        queryset=PlanServerClass.objects.all(),
        label='Server Class',
        help_text='Server class this NIC belongs to',
    )

    module_type = DynamicModelChoiceField(
        queryset=ModuleType.objects.all(),
        label='Module Type',
        help_text='NetBox ModuleType for this NIC (must have InterfaceTemplates defined)',
    )

    class Meta:
        model = PlanServerNIC
        fields = [
            'server_class',
            'nic_id',
            'module_type',
            'description',
            'tags',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'nic_id': (
                "Unique NIC slot identifier within this server class "
                "(e.g., 'nic-fe', 'nic-be-rail-0'). "
                "Used as ModuleBay name and interface name prefix. "
                "Alphanumeric, hyphens, underscores only; must start with alphanumeric."
            ),
        }


# =============================================================================
# PlanServerConnection Form (DIET-005)
# =============================================================================

class PlanServerConnectionForm(NetBoxModelForm):
    """
    Form for creating and editing PlanServerConnections (DIET-173 Phase 5).

    Server connections define how servers connect to switches, including
    NIC module type selection, port index specification, connection types,
    and distribution strategies.

    Implements clean-break NIC modeling with required nic_module_type
    and port_index fields following NetBox Module patterns.
    """

    class Meta:
        model = PlanServerConnection
        fields = [
            'server_class',
            'connection_id',
            'connection_name',
            'nic',
            'port_index',
            'ports_per_connection',
            'hedgehog_conn_type',
            'distribution',
            'target_zone',
            'speed',
            'rail',
            'port_type',
            'transceiver_module_type',
            'cage_type',
            'medium',
            'connector',
            'standard',
            'tags',
        ]
        widgets = {
            'connection_name': forms.TextInput(attrs={'placeholder': 'frontend, backend-rail-0, etc.'}),
        }
        help_texts = {
            'nic': (
                'Physical NIC card this connection uses. '
                'The NIC must belong to the same server class.'
            ),
            'port_index': (
                'Zero-based port index on the NIC (0 for first port, 1 for second port). '
                'Used to select which physical port on the NIC to use for this connection.'
            ),
            'transceiver_module_type': (
                'Transceiver or DAC/AOC SKU to install in this port cage. '
                'Must have the Network Transceiver profile. '
                'Leave blank to use flat fields for spec only.'
            ),
            'cage_type': 'Transceiver cage/port form factor (leave blank if not specified).',
            'medium': 'Physical transmission medium (leave blank if not specified).',
            'connector': 'Fiber connector type (leave blank for DAC or if not specified).',
            'standard': 'Optical/electrical standard (e.g., 200GBASE-SR4). Optional.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Resolve server_class from instance or submitted data
        server_class = None

        if self.instance and self.instance.pk and self.instance.server_class_id:
            try:
                server_class = self.instance.server_class
            except Exception:
                pass
        else:
            server_class_id = self.data.get('server_class') or self.initial.get('server_class')
            if server_class_id:
                try:
                    server_class = PlanServerClass.objects.get(pk=server_class_id)
                except (PlanServerClass.DoesNotExist, ValueError):
                    pass

        if server_class:
            plan = server_class.plan
            # Filter target_zone to the same plan
            self.fields['target_zone'].queryset = SwitchPortZone.objects.filter(
                switch_class__plan=plan, zone_type__in=['server', 'oob']
            ).select_related('switch_class')
            self.fields['target_zone'].help_text = f'Server/OOB zones from plan: {plan.name}'
            # Filter nic to the same server_class
            self.fields['nic'].queryset = PlanServerNIC.objects.filter(
                server_class=server_class
            )
            self.fields['nic'].help_text = f'NICs for server class: {server_class.server_class_id}'
        else:
            self.fields['target_zone'].help_text = (
                'Select a server class first. Target zone must be from the same plan.'
            )
            self.fields['nic'].help_text = (
                'Select a server class first. NIC must belong to the same server class.'
            )

        # Filter transceiver_module_type to Network Transceiver profile only (DIET-334).
        # Wire description-first labels (DIET-460).
        from dcim.models import ModuleType, ModuleTypeProfile
        xcvr_profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        if xcvr_profile:
            xcvr_qs = ModuleType.objects.filter(
                profile=xcvr_profile
            ).select_related('manufacturer').order_by('manufacturer__name', 'model')
            self.fields['transceiver_module_type'].queryset = xcvr_qs
            self.fields['transceiver_module_type'].label_from_instance = _make_xcvr_label_fn(xcvr_qs)
        else:
            self.fields['transceiver_module_type'].queryset = ModuleType.objects.none()
        # Help text: tell user switch-side optic is on the zone (DIET-460)
        self.fields['transceiver_module_type'].help_text = (
            'Server-side transceiver for this port. '
            'The switch-side transceiver is set on the zone — edit it via the Switch Port Zone form.'
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
            'transceiver_module_type',
            'tags',
        ]
        widgets = {
            'allocation_order': forms.Textarea(attrs={'rows': 2}),
        }
        help_texts = {
            'zone_name': "Zone name (e.g., 'server-ports', 'spine-uplinks')",
            'port_spec': "Port specification (e.g., '1-48', '1-32:2', '1,3,5')",
            'allocation_order': 'JSON list of port numbers used when strategy is custom',
            'transceiver_module_type': (
                'Intended transceiver/DAC SKU for all ports in this zone. '
                'Must have the Network Transceiver profile. '
                'Used for plan-save compatibility validation (Stage 2: switch-side Module generation).'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter transceiver_module_type to Network Transceiver profile only (DIET-334).
        # Wire description-first labels (DIET-460).
        from dcim.models import ModuleType, ModuleTypeProfile
        xcvr_profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        if xcvr_profile:
            xcvr_qs = ModuleType.objects.filter(
                profile=xcvr_profile
            ).select_related('manufacturer').order_by('manufacturer__name', 'model')
            self.fields['transceiver_module_type'].queryset = xcvr_qs
            self.fields['transceiver_module_type'].label_from_instance = _make_xcvr_label_fn(xcvr_qs)
        else:
            self.fields['transceiver_module_type'].queryset = ModuleType.objects.none()
