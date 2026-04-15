"""
Topology Plan Models for DIET (Design and Implementation Excellence Tools)

These models enable pre-sales topology planning and design workflows.
They reference NetBox core models (DeviceType, ModuleType) and the custom
DeviceTypeExtension model for Hedgehog-specific metadata.
"""

from django.db import models
from django.urls import reverse
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from netbox.models import NetBoxModel
from dcim.models import DeviceType, ModuleType

from .reference_data import DeviceTypeExtension
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricClassChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    PortTypeChoices,
    CageTypeChoices,
    MediumChoices,
    ConnectorChoices,
    TopologyModeChoices,
)
from netbox_hedgehog.services._fabric_utils import _legacy_fabric_name_to_class

User = get_user_model()


class TopologyPlan(NetBoxModel):
    """
    Container for a topology plan.

    A topology plan represents a complete network design including server
    quantities, switch requirements, and connection specifications. Plans
    can be created, reviewed, approved, and exported to Hedgehog YAML.
    """

    name = models.CharField(
        max_length=200,
        help_text="Plan name (e.g., 'Cambium 2MW', '128-GPU Training Cluster')"
    )

    customer_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Customer or project name"
    )

    description = models.TextField(
        blank=True,
        help_text="Detailed description of the topology plan"
    )

    status = models.CharField(
        max_length=50,
        choices=TopologyPlanStatusChoices,
        default=TopologyPlanStatusChoices.DRAFT,
        help_text="Current status of the plan"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='topology_plans',
        help_text="User who created this plan"
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this plan"
    )

    class Meta:
        ordering = ['-created']
        verbose_name = "Topology Plan"
        verbose_name_plural = "Topology Plans"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.pk])

    @property
    def last_generated_at(self):
        """
        Timestamp of last generation.

        Returns:
            datetime: When objects were last generated, or None if never generated
        """
        try:
            return self.generation_state.generated_at
        except AttributeError:
            # No GenerationState exists yet
            return None

    @property
    def needs_regeneration(self):
        """
        Check if plan needs regeneration.

        Returns:
            bool: True if plan has been modified since last generation, False otherwise
        """
        try:
            return self.generation_state.is_dirty()
        except AttributeError:
            # No GenerationState exists yet
            return False


class PlanServerClass(NetBoxModel):
    """
    Server class definition within a topology plan.

    Represents a group of identical servers (e.g., "GPU-B200", "Storage-A").
    The quantity field is the primary user input - all switch calculations
    are derived from server quantities and their connection requirements.
    """

    plan = models.ForeignKey(
        TopologyPlan,
        on_delete=models.CASCADE,
        related_name='server_classes',
        help_text="Topology plan this server class belongs to"
    )

    server_class_id = models.CharField(
        max_length=100,
        help_text="Unique identifier for this server class (e.g., 'GPU-B200', 'INF-001')"
    )

    description = models.TextField(
        blank=True,
        help_text="Description of this server class"
    )

    category = models.CharField(
        max_length=50,
        choices=ServerClassCategoryChoices,
        blank=True,
        help_text="Server category (GPU, Storage, Infrastructure)"
    )

    server_device_type = models.ForeignKey(
        DeviceType,
        on_delete=models.PROTECT,
        related_name='plan_server_classes',
        help_text="NetBox DeviceType for this server model"
    )

    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of servers of this class (PRIMARY USER INPUT)"
    )

    gpus_per_server = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of GPUs per server (for GPU server classes)"
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this server class"
    )

    class Meta:
        ordering = ['plan', 'server_class_id']
        verbose_name = "Server Class"
        verbose_name_plural = "Server Classes"
        unique_together = [['plan', 'server_class_id']]

    def __str__(self):
        return f"{self.server_class_id} ({self.quantity}x {self.server_device_type})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:planserverclass_detail', args=[self.pk])


class PlanServerNIC(NetBoxModel):
    """
    One physical NIC/DPU card slot within a PlanServerClass (DIET-294).

    Represents a single installed NIC card.  All connections from this server
    class that physically use the same card must reference the same
    PlanServerNIC.  The generator creates exactly one NetBox Module per
    PlanServerNIC per generated server device.
    """

    server_class = models.ForeignKey(
        PlanServerClass,
        on_delete=models.CASCADE,
        related_name='nics',
        help_text="Server class this NIC belongs to",
    )

    nic_id = models.CharField(
        max_length=100,
        help_text=(
            "Unique NIC identifier within this server class "
            "(e.g., 'nic-fe', 'nic-be-rail-0'). "
            "Used as ModuleBay name and interface name prefix."
        ),
    )

    module_type = models.ForeignKey(
        ModuleType,
        on_delete=models.PROTECT,
        related_name='plan_server_nics',
        help_text="NetBox ModuleType for this NIC (must have InterfaceTemplates)",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description for this NIC slot",
    )

    class Meta:
        ordering = ['server_class', 'nic_id']
        verbose_name = "Server NIC"
        verbose_name_plural = "Server NICs"
        unique_together = [['server_class', 'nic_id']]

    def __str__(self):
        return f"{self.server_class.server_class_id}/{self.nic_id}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:planservernic_detail', args=[self.pk])

    def clean(self):
        super().clean()

        # Validate nic_id follows interface naming conventions
        if self.nic_id:
            import re
            if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', self.nic_id):
                raise ValidationError({
                    'nic_id': (
                        'NIC ID must start with alphanumeric and contain only '
                        'alphanumeric characters, hyphens, and underscores.'
                    )
                })

        # Validate module_type has interface templates
        if self.module_type_id:
            from dcim.models import InterfaceTemplate
            if not InterfaceTemplate.objects.filter(module_type_id=self.module_type_id).exists():
                raise ValidationError({
                    'module_type': (
                        f'Module type "{self.module_type}" has no interface templates defined. '
                        'Add interface templates to this module type before using it as a NIC.'
                    )
                })


class PlanSwitchClass(NetBoxModel):
    """
    Switch class definition within a topology plan.

    Represents a group of identical switches in a specific role
    (e.g., "fe-gpu-leaf", "be-spine"). Switch quantities are calculated
    automatically based on port demand, but can be overridden by the user.
    """

    plan = models.ForeignKey(
        TopologyPlan,
        on_delete=models.CASCADE,
        related_name='switch_classes',
        help_text="Topology plan this switch class belongs to"
    )

    switch_class_id = models.CharField(
        max_length=100,
        help_text="Unique identifier for this switch class (e.g., 'fe-gpu-leaf')"
    )

    fabric_name = models.CharField(
        max_length=50,
        blank=False,
        help_text=(
            'User-defined fabric name used for managed-fabric partitioning '
            "(for example: frontend, backend, converged, storage-rail, my-oob)."
        ),
    )

    fabric_class = models.CharField(
        max_length=16,
        choices=FabricClassChoices,
        default=FabricClassChoices.MANAGED,
        help_text=(
            'Behavioral class for this fabric. Managed fabrics export as Switch CRDs; '
            'unmanaged fabrics export as Server surrogates.'
        ),
    )

    hedgehog_role = models.CharField(
        max_length=50,
        choices=HedgehogRoleChoices,
        blank=True,
        help_text="Hedgehog role (spine, server-leaf, border-leaf, virtual)"
    )

    device_type_extension = models.ForeignKey(
        DeviceTypeExtension,
        on_delete=models.PROTECT,
        related_name='plan_switch_classes',
        help_text="DeviceTypeExtension with Hedgehog metadata for this switch model"
    )

    uplink_ports_per_switch = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Number of ports reserved for uplinks (explicit override). "
                  "If not set, uplink capacity will be derived from SwitchPortZone with zone_type='uplink'. "
                  "Either this field or uplink zones must be defined."
    )

    mclag_pair = models.BooleanField(
        default=False,
        help_text="Whether switches are deployed in MCLAG pairs"
    )

    calculated_quantity = models.IntegerField(
        null=True,
        blank=True,
        editable=False,
        help_text="Automatically calculated switch quantity (computed by calc engine)"
    )

    override_quantity = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="User override for switch quantity (leave blank to use calculated)"
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this switch class"
    )

    topology_mode = models.CharField(
        max_length=20,
        choices=TopologyModeChoices,
        default=TopologyModeChoices.SPINE_LEAF,
        blank=True,
        help_text="Topology mode for this switch class fabric."
    )

    # MCLAG/ESLAG redundancy configuration (Issue #151)
    groups = models.JSONField(
        default=list,
        blank=True,
        help_text="List of SwitchGroup names this switch belongs to. "
                  "Auto-populated from redundancy_group if not set. (e.g., ['mclag-1'])"
    )

    redundancy_type = models.CharField(
        max_length=50,
        choices=[
            ('mclag', 'MCLAG - Multi-Chassis Link Aggregation'),
            ('eslag', 'ESLAG - Enhanced Server Link Aggregation')
        ],
        blank=True,
        null=True,
        help_text="Redundancy type for switches in this class. Leave blank for standalone switches."
    )

    redundancy_group = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Redundancy group name (must match a SwitchGroup). Required if redundancy_type is set."
    )

    class Meta:
        ordering = ['plan', 'fabric_name', 'switch_class_id']
        verbose_name = "Switch Class"
        verbose_name_plural = "Switch Classes"
        unique_together = [['plan', 'switch_class_id']]

    def __str__(self):
        return f"{self.switch_class_id} ({self.effective_quantity}x {self.device_type_extension.device_type})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:planswitchclass_detail', args=[self.pk])

    def __init__(self, *args, **kwargs):
        legacy_fabric = kwargs.pop('fabric', None)
        if legacy_fabric is not None and 'fabric_name' not in kwargs:
            kwargs['fabric_name'] = legacy_fabric
        if 'fabric_class' not in kwargs and kwargs.get('fabric_name'):
            kwargs['fabric_class'] = _legacy_fabric_name_to_class(kwargs['fabric_name'])
        super().__init__(*args, **kwargs)

    @property
    def fabric(self) -> str:
        """Compatibility alias for older DIET code paths and tests."""
        return self.fabric_name

    @fabric.setter
    def fabric(self, value: str) -> None:
        self.fabric_name = value
        if value and not getattr(self, 'fabric_class', None):
            self.fabric_class = _legacy_fabric_name_to_class(value)

    def get_fabric_display(self) -> str:
        return self.fabric_name

    @property
    def is_hedgehog_managed(self) -> bool:
        """Return True if this switch class is exported in Hedgehog wiring YAML."""
        return self.fabric_class == FabricClassChoices.MANAGED

    def save(self, *args, **kwargs):
        """
        Auto-convert deprecated mclag_pair to redundancy_type (DIET-165 Phase 5).

        Per Phase 3 spec addendum: mclag_pair=True auto-converts to redundancy_type='mclag'
        and redundancy_group='mclag-<switch_class_id>' on save.
        """
        if self.fabric_name and self.fabric_class not in {
            FabricClassChoices.MANAGED,
            FabricClassChoices.UNMANAGED,
        }:
            self.fabric_class = _legacy_fabric_name_to_class(self.fabric_name)

        # Auto-conversion: mclag_pair → redundancy_type (only if redundancy_type not already set)
        if self.mclag_pair and not self.redundancy_type:
            self.redundancy_type = 'mclag'
            # Auto-generate redundancy_group if not set
            if not self.redundancy_group:
                # Normalize switch_class_id to DNS-1123 format for valid SwitchGroup names
                # Replace underscores and other invalid chars with hyphens, convert to lowercase
                normalized_id = self.switch_class_id.lower().replace('_', '-')
                # Remove any characters not allowed in DNS-1123 labels (a-z, 0-9, -)
                import re
                normalized_id = re.sub(r'[^a-z0-9-]', '-', normalized_id)
                # Remove consecutive hyphens and strip leading/trailing hyphens
                normalized_id = re.sub(r'-+', '-', normalized_id).strip('-')

                # Fallback if normalization results in empty string (e.g., all symbols/underscores)
                if not normalized_id:
                    # Use pk-based fallback for unique, valid DNS-1123 label
                    # If pk not set yet (new instance), use 'new' placeholder
                    pk_suffix = str(self.pk) if self.pk else 'new'
                    normalized_id = f'switch-{pk_suffix}'

                # Enforce DNS-1123 length limit (max 63 chars total)
                # Format is 'mclag-{normalized_id}', prefix is 6 chars, leaving 57 for normalized_id
                max_id_length = 57
                if len(normalized_id) > max_id_length:
                    # Truncate and ensure it doesn't end with hyphen
                    normalized_id = normalized_id[:max_id_length].rstrip('-')

                self.redundancy_group = f'mclag-{normalized_id}'

            # Ensure groups includes the redundancy_group (critical for SwitchGroup membership)
            if not self.groups:
                self.groups = [self.redundancy_group]
            elif self.redundancy_group not in self.groups:
                self.groups.append(self.redundancy_group)

        super().save(*args, **kwargs)

    def clean(self):
        """Validate redundancy configuration (DIET-165 Phase 5) and mesh topology invariants."""
        super().clean()

        # Mesh mode: require override_quantity exactly 2 or 3
        if self.topology_mode == TopologyModeChoices.MESH:
            if self.override_quantity not in (2, 3):
                raise ValidationError({
                    'override_quantity': (
                        'Mesh mode requires override_quantity to be exactly 2 or 3 '
                        '(the number of physical switches in this mesh fabric).'
                    )
                })

        # Mesh/spine mutual exclusion and fabric-wide topology_mode invariant
        if self.topology_mode == TopologyModeChoices.MESH:
            spine_exists = PlanSwitchClass.objects.filter(
                plan=self.plan, fabric_name=self.fabric_name,
                hedgehog_role='spine'
            ).exclude(pk=self.pk).exists()
            if spine_exists:
                raise ValidationError({'topology_mode': 'Cannot use mesh topology when a spine switch class exists in this fabric.'})

        if self.hedgehog_role == 'spine':
            mesh_exists = PlanSwitchClass.objects.filter(
                plan=self.plan, fabric_name=self.fabric_name,
                topology_mode=TopologyModeChoices.MESH
            ).exclude(pk=self.pk).exists()
            if mesh_exists:
                raise ValidationError({'hedgehog_role': 'Cannot add spine when a mesh switch class exists in this fabric.'})

        peers = PlanSwitchClass.objects.filter(
            plan=self.plan, fabric_name=self.fabric_name
        ).exclude(pk=self.pk).exclude(hedgehog_role='spine')
        conflicting = peers.exclude(topology_mode=self.topology_mode)
        if conflicting.exists():
            raise ValidationError({'topology_mode': f'All non-spine switch classes in fabric "{self.fabric_name}" must share the same topology_mode.'})

        # If redundancy_type is set, redundancy_group is required
        if self.redundancy_type and not self.redundancy_group:
            raise ValidationError({
                'redundancy_group': 'Redundancy group name is required when redundancy type is set.'
            })

        # Auto-populate groups from redundancy_group (if not already set)
        if self.redundancy_group:
            if not self.groups:
                self.groups = [self.redundancy_group]  # Auto-populate
            elif self.redundancy_group not in self.groups:
                raise ValidationError({
                    'groups': f'Redundancy group "{self.redundancy_group}" must be included in groups list.'
                })

        # Redundancy-specific switch count validation (DIET-165 Phase 5)
        # Use override_quantity if set (user's explicit value), otherwise calculated_quantity
        quantity_to_validate = self.override_quantity if self.override_quantity is not None else self.calculated_quantity

        # Determine which field to assign errors to
        # If override_quantity is set, user explicitly provided it → assign errors to override_quantity
        # If override_quantity is None, user relies on calculated → use non-field error
        error_field = 'override_quantity' if self.override_quantity is not None else '__all__'

        if quantity_to_validate is not None:
            if self.redundancy_type == 'mclag':
                # MCLAG: Must have even quantity, minimum 2
                if quantity_to_validate < 2:
                    raise ValidationError({
                        error_field: 'MCLAG requires at least 2 switches.'
                    })
                if quantity_to_validate % 2 != 0:
                    raise ValidationError({
                        error_field: f'MCLAG requires an even number of switches, got {quantity_to_validate}.'
                    })
            elif self.redundancy_type == 'eslag':
                # ESLAG: 2-4 switches
                if quantity_to_validate < 2:
                    raise ValidationError({
                        error_field: 'ESLAG requires at least 2 switches.'
                    })
                if quantity_to_validate > 4:
                    raise ValidationError({
                        error_field: f'ESLAG supports a maximum 4 switches per group, got {quantity_to_validate}.'
                    })
            # Deprecated mclag_pair field (backward compatibility)
            elif self.mclag_pair and quantity_to_validate > 0 and quantity_to_validate % 2 != 0:
                raise ValidationError({
                    error_field: f'MCLAG pair requires even switch count, got {quantity_to_validate}. '
                                 f'(Note: mclag_pair is deprecated, use redundancy_type="mclag" instead)'
                })

    @property
    def effective_quantity(self):
        """
        Return the effective switch quantity.

        Returns override_quantity if set, otherwise calculated_quantity.
        Returns 0 if both are None.
        """
        if self.override_quantity is not None:
            return self.override_quantity
        if self.calculated_quantity is not None:
            return self.calculated_quantity
        return 0


class PlanMeshLink(models.Model):
    """
    Represents a /31 point-to-point mesh link between two switch classes
    in a prefer-mesh fabric topology (DIET-309).
    """
    plan = models.ForeignKey(
        TopologyPlan,
        on_delete=models.CASCADE,
        related_name='mesh_links',
    )
    fabric_name = models.CharField(max_length=50, blank=True)
    switch_class_a = models.ForeignKey(
        PlanSwitchClass,
        on_delete=models.CASCADE,
        related_name='mesh_links_as_a',
    )
    switch_class_b = models.ForeignKey(
        PlanSwitchClass,
        on_delete=models.CASCADE,
        related_name='mesh_links_as_b',
    )
    subnet = models.CharField(max_length=20, blank=True, help_text="/31 subnet, e.g. 172.30.128.0/31")
    link_index = models.IntegerField(default=0)
    leaf1_port = models.CharField(max_length=50, blank=True)
    leaf2_port = models.CharField(max_length=50, blank=True)
    leaf1_name = models.CharField(max_length=200, blank=True, help_text="Physical switch name for leaf1")
    leaf2_name = models.CharField(max_length=200, blank=True, help_text="Physical switch name for leaf2")

    class Meta:
        ordering = ['plan', 'fabric_name', 'link_index']
        unique_together = [['plan', 'fabric_name', 'link_index']]

    def clean(self):
        import ipaddress
        # Auto-populate fabric_name from switch_class_a if not set
        if self.switch_class_a_id and not self.fabric_name:
            self.fabric_name = self.switch_class_a.fabric_name
        if self.subnet:
            try:
                net = ipaddress.ip_network(self.subnet, strict=True)
            except ValueError as e:
                raise ValidationError({'subnet': str(e)})
            if net.prefixlen != 31:
                raise ValidationError({'subnet': f'Mesh link subnet must be a /31, got /{net.prefixlen}.'})
        if self.switch_class_a and self.switch_class_b:
            if self.switch_class_a.switch_class_id > self.switch_class_b.switch_class_id:
                raise ValidationError('switch_class_a must be alphabetically first.')

    def save(self, *args, **kwargs):
        # Auto-populate fabric_name from switch_class_a if not set
        if self.switch_class_a_id and not self.fabric_name:
            self.fabric_name = self.switch_class_a.fabric_name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.fabric_name} mesh link {self.link_index}: {self.subnet}"


class PlanServerConnection(NetBoxModel):
    """
    Server connection definition within a topology plan.

    Defines how servers connect to switches, including:
    - Number of ports per connection
    - Connection type (unbundled, bundled, mclag, eslag)
    - Distribution strategy (same-switch, alternating, rail-optimized)
    - Target switch class
    """

    server_class = models.ForeignKey(
        PlanServerClass,
        on_delete=models.CASCADE,
        related_name='connections',
        help_text="Server class this connection belongs to"
    )

    connection_id = models.CharField(
        max_length=100,
        help_text="Unique connection identifier (e.g., 'FE-001', 'BE-RAIL-0')"
    )

    nic = models.ForeignKey(
        PlanServerNIC,
        on_delete=models.PROTECT,
        related_name='connections',
        help_text="Physical NIC card this connection uses (DIET-294 NIC-first model)",
    )

    port_index = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Zero-based port index on the NIC (e.g., 0 for first port, 1 for second port)"
    )

    connection_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Descriptive connection name (e.g., 'frontend', 'backend-rail-0')"
    )

    ports_per_connection = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of ports used for this connection"
    )

    hedgehog_conn_type = models.CharField(
        max_length=50,
        choices=ConnectionTypeChoices,
        default=ConnectionTypeChoices.UNBUNDLED,
        help_text="Hedgehog connection type (unbundled, bundled, mclag, eslag)"
    )

    distribution = models.CharField(
        max_length=50,
        choices=ConnectionDistributionChoices,
        blank=True,
        help_text="Port distribution strategy (same-switch, alternating, rail-optimized)"
    )

    target_zone = models.ForeignKey(
        'netbox_hedgehog.SwitchPortZone',
        on_delete=models.PROTECT,
        related_name='server_connections',
        help_text="Switch port zone this connection targets",
    )

    @property
    def target_switch_class(self):
        """Derived from target_zone for backward compatibility."""
        return self.target_zone.switch_class if self.target_zone_id else None

    speed = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Connection speed in Gbps (e.g., 200 for 200G)"
    )

    rail = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Rail number for rail-optimized distribution (0-7 for 8-rail backend)"
    )

    port_type = models.CharField(
        max_length=50,
        choices=PortTypeChoices,
        blank=True,
        help_text="Port type (data, ipmi, pxe)"
    )

    # Transceiver review fields (DIET-294) – flat attributes for engineer review.
    # These fields are UI-only metadata after Stage 3 (#347) removed the legacy
    # hedgehog_transceiver_spec write path. Transceiver generation uses the
    # Module-based model via transceiver_module_type FK (DIET-334 Stage 2).

    cage_type = models.CharField(
        max_length=20,
        choices=CageTypeChoices,
        blank=True,
        help_text="Transceiver cage/port form factor (e.g., QSFP112, OSFP)",
    )

    medium = models.CharField(
        max_length=10,
        choices=MediumChoices,
        blank=True,
        help_text="Physical transmission medium (e.g., MMF, DAC)",
    )

    connector = models.CharField(
        max_length=10,
        choices=ConnectorChoices,
        blank=True,
        help_text="Fiber connector type (e.g., LC, MPO-12); blank for DAC/direct-attach",
    )

    standard = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optical/electrical standard (e.g., 200GBASE-SR4, 400GAUI-8 C2M)",
    )

    # DIET-334 Stage 1: authoritative transceiver ModuleType FK.
    # When set, the generator installs a transceiver Module in a device-level
    # ModuleBay named '{nic_id}-cage-{port_index}' on the server Device.
    # Flat fields above remain for backward compat and validation cross-checking.
    transceiver_module_type = models.ForeignKey(
        ModuleType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plan_server_connections',
        help_text=(
            "Transceiver or DAC/AOC ModuleType to install in this port cage. "
            "Must have the 'Network Transceiver' ModuleTypeProfile. "
            "If null, no transceiver Module is generated (Stage 1 backward compat)."
        ),
    )

    class Meta:
        ordering = ['server_class', 'connection_id']
        verbose_name = "Server Connection"
        verbose_name_plural = "Server Connections"
        unique_together = [['server_class', 'connection_id']]

    def __str__(self):
        zone_label = str(self.target_zone) if self.target_zone_id else "no-zone"
        return f"{self.server_class.server_class_id}/{self.connection_id} → {zone_label}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[self.pk])

    def clean(self):
        """Validate NIC configuration and zone targeting."""
        super().clean()

        # Validate target_zone is in the same plan as server_class
        if self.target_zone_id and self.server_class_id:
            zone_plan = self.target_zone.switch_class.plan_id
            if zone_plan != self.server_class.plan_id:
                raise ValidationError({
                    'target_zone': 'Target zone must belong to the same plan as the server class.'
                })

        # Validate zone_type alignment: IPMI → OOB zone, other → SERVER zone
        if self.target_zone_id:
            expected_type = 'oob' if self.port_type == PortTypeChoices.IPMI else 'server'
            if self.target_zone.zone_type not in (expected_type, 'server', 'oob'):
                raise ValidationError({
                    'target_zone': f'Zone type mismatch: port_type={self.port_type!r} requires zone_type={expected_type!r}.'
                })
            if self.port_type == PortTypeChoices.IPMI and self.target_zone.zone_type != 'oob':
                raise ValidationError({
                    'target_zone': 'IPMI connections must target an OOB zone.'
                })
            if self.port_type != PortTypeChoices.IPMI and self.target_zone.zone_type == 'oob':
                raise ValidationError({
                    'target_zone': 'Non-IPMI connections cannot target an OOB zone.'
                })
            if self.target_zone.zone_type not in ('server', 'oob'):
                raise ValidationError({
                    'target_zone': f'Connections cannot target zone_type={self.target_zone.zone_type!r}. '
                                   'Must be server or oob.'
                })

        # Validate connection_id follows NetBox interface naming conventions
        # (used as prefix for auto-created interface names)
        if self.connection_id:
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', self.connection_id):
                raise ValidationError({
                    'connection_id': 'Connection ID must contain only alphanumeric characters, '
                                   'hyphens, and underscores (used as interface name prefix).'
                })

        # Validate that distribution=alternating + bundled connection type has explicit
        # redundancy_type on the target switch class.  Bundled types (mclag, eslag, bundled)
        # create bonded link groups and require an explicit HA shim.  Unbundled alternating
        # is a valid multi-homed placement without bonding and does NOT require redundancy_type
        # — forcing mclag/eslag on unbundled topologies is incorrect (issue #303).
        # Option A (calculate_switch_quantity min-2) remains as a defence-in-depth fallback.
        from netbox_hedgehog.choices import ConnectionTypeChoices
        _bundled_conn_types = {
            ConnectionTypeChoices.BUNDLED,
            ConnectionTypeChoices.MCLAG,
            ConnectionTypeChoices.ESLAG,
        }
        if (self.distribution == 'alternating'
                and self.hedgehog_conn_type in _bundled_conn_types
                and self.target_zone_id
                and not self.target_zone.switch_class.redundancy_type):
            switch_class_id = self.target_zone.switch_class.switch_class_id
            raise ValidationError({
                'distribution': (
                    f"distribution=alternating with a bundled connection type "
                    f"({self.hedgehog_conn_type}) requires the target switch class "
                    f"'{switch_class_id}' to have redundancy_type set (e.g. 'eslag' or 'mclag'). "
                    f"Set redundancy_type on the switch class before creating this connection."
                )
            })

        # Validate nic is set (NOT NULL enforced by migration 0038)
        if not self.nic_id:
            raise ValidationError({
                'nic': 'NIC is required.'
            })

        # DIET-334 Stage 1: transceiver_module_type validation.
        self._validate_transceiver_module_type()

    def _validate_transceiver_module_type(self):
        """Validate transceiver_module_type FK and cross-end compatibility."""
        xcvr_mt = None
        if self.transceiver_module_type_id:
            from dcim.models import ModuleTypeProfile
            xcvr_mt = self.transceiver_module_type
            # V1: FK must reference a Network Transceiver ModuleType.
            if not (xcvr_mt.profile_id and xcvr_mt.profile.name == 'Network Transceiver'):
                raise ValidationError({
                    'transceiver_module_type': (
                        "Must reference a ModuleType with the 'Network Transceiver' profile. "
                        f"'{xcvr_mt.model}' does not have this profile."
                    )
                })
            xcvr_ad = xcvr_mt.attribute_data or {}
            # V2: flat cage_type must match FK attribute_data if both set.
            if self.cage_type and xcvr_ad.get('cage_type') and self.cage_type != xcvr_ad['cage_type']:
                raise ValidationError({
                    'cage_type': (
                        f"cage_type '{self.cage_type}' conflicts with transceiver_module_type "
                        f"attribute_data cage_type '{xcvr_ad['cage_type']}'."
                    )
                })
            # V3: flat medium must match FK attribute_data if both set.
            if self.medium and xcvr_ad.get('medium') and self.medium != xcvr_ad['medium']:
                raise ValidationError({
                    'medium': (
                        f"medium '{self.medium}' conflicts with transceiver_module_type "
                        f"attribute_data medium '{xcvr_ad['medium']}'."
                    )
                })
            # V2c: flat connector must match FK attribute_data connector if both set.
            if self.connector and xcvr_ad.get('connector') and self.connector != xcvr_ad['connector']:
                raise ValidationError({
                    'connector': (
                        f"connector '{self.connector}' conflicts with transceiver_module_type "
                        f"attribute_data connector '{xcvr_ad['connector']}'."
                    )
                })
            # V7: reach_class must be compatible with resolved medium (copper vs. optical invariant).
            rc = xcvr_ad.get('reach_class')
            resolved_medium = xcvr_ad.get('medium') or self.medium
            if rc and resolved_medium:
                _copper_mediums = {'DAC', 'ACC'}
                _optical_mediums = {'MMF', 'SMF'}
                _optical_reach_classes = {'SR', 'LR', 'DR'}
                if rc == 'DAC' and resolved_medium in _optical_mediums:
                    raise ValidationError({
                        'transceiver_module_type': (
                            f"reach_class 'DAC' is incompatible with medium '{resolved_medium}': "
                            f"DAC reach class requires a copper medium (DAC or ACC)."
                        )
                    })
                elif rc in _optical_reach_classes and resolved_medium in _copper_mediums:
                    raise ValidationError({
                        'transceiver_module_type': (
                            f"reach_class '{rc}' is incompatible with medium '{resolved_medium}': "
                            f"optical reach classes (SR, LR, DR) require a fiber medium (MMF or SMF)."
                        )
                    })
                # Unknown reach_class values not in either group → null-skip (forward-compatible).

        # Cross-end compatibility against target zone's transceiver FK (V4, V5, V6).
        if self.target_zone_id:
            zone_mt = getattr(self.target_zone, 'transceiver_module_type', None)
            if zone_mt is not None:
                zone_ad = zone_mt.attribute_data or {}
                # Resolve all cross-end fields up front (FK takes precedence over flat fields).
                srv_cage = (xcvr_mt.attribute_data or {}).get('cage_type') if xcvr_mt else self.cage_type
                srv_medium = (xcvr_mt.attribute_data or {}).get('medium') if xcvr_mt else self.medium
                srv_connector = (xcvr_mt.attribute_data or {}).get('connector') if xcvr_mt else self.connector
                zone_cage = zone_ad.get('cage_type')
                zone_medium = zone_ad.get('medium')
                zone_connector = zone_ad.get('connector')
                zone_breakout_topology = zone_ad.get('breakout_topology')
                # Consult approved-asymmetric-pair registry before cage/connector checks.
                # Medium (V5/V8) is always enforced independently of this registry.
                from netbox_hedgehog.transceiver_compat import is_approved_asymmetric_pair
                _approved = is_approved_asymmetric_pair(
                    zone_cage, zone_connector, zone_medium, zone_breakout_topology,
                    srv_cage, srv_connector,
                )
                # V4/V6: cage_type must match (unless approved asymmetric pair).
                if not _approved and srv_cage and zone_cage and srv_cage != zone_cage:
                    field = 'transceiver_module_type' if xcvr_mt else 'cage_type'
                    raise ValidationError({
                        field: (
                            f"Server-side cage_type '{srv_cage}' does not match "
                            f"zone transceiver cage_type '{zone_cage}'."
                        )
                    })
                # V5/V8: medium must be compatible (DAC↔DAC, ACC↔ACC, MMF↔MMF, SMF↔SMF).
                # Always enforced — approved asymmetric pairs do not bypass medium strictness.
                if srv_medium and zone_medium and srv_medium != zone_medium:
                    field = 'transceiver_module_type' if xcvr_mt else 'medium'
                    raise ValidationError({
                        field: (
                            f"Server-side medium '{srv_medium}' is incompatible with "
                            f"zone transceiver medium '{zone_medium}'. Both ends must use the same medium."
                        )
                    })
                # V6: connector must match (unless approved asymmetric pair).
                if not _approved and srv_connector and zone_connector and srv_connector != zone_connector:
                    field = 'transceiver_module_type' if xcvr_mt else 'connector'
                    raise ValidationError({
                        field: (
                            f"Server-side connector '{srv_connector}' does not match "
                            f"zone transceiver connector '{zone_connector}'."
                        )
                    })

        # Validate nic belongs to the same server_class (not cross-plan, not cross-server-class)
        if self.nic_id and self.server_class_id:
            if self.nic.server_class_id != self.server_class_id:
                raise ValidationError({
                    'nic': (
                        'NIC must belong to the same server class as this connection. '
                        f'NIC belongs to "{self.nic.server_class.server_class_id}", '
                        f'connection belongs to server class pk={self.server_class_id}.'
                    )
                })

        # Get interface templates for the NIC's module_type
        from dcim.models import InterfaceTemplate
        nic_interfaces = InterfaceTemplate.objects.filter(
            module_type=self.nic.module_type
        ).order_by('name')

        if not nic_interfaces.exists():
            raise ValidationError({
                'nic': f'NIC module type "{self.nic.module_type}" has no interface templates defined.'
            })

        # Validate port_index doesn't exceed available ports
        port_count = nic_interfaces.count()
        if self.port_index >= port_count:
            raise ValidationError({
                'port_index': f'Port index {self.port_index} exceeds available ports (0-{port_count - 1}) '
                             f'on NIC "{self.nic.module_type}".'
            })

        # Validate sufficient ports for ports_per_connection
        if self.ports_per_connection:
            available_ports = port_count - self.port_index
            if self.ports_per_connection > available_ports:
                raise ValidationError({
                    'ports_per_connection': f'Insufficient ports for this connection. '
                                          f'Requested {self.ports_per_connection} ports starting from index {self.port_index}, '
                                          f'but only {available_ports} ports available on "{self.nic.module_type}".'
                })



class PlanMCLAGDomain(NetBoxModel):
    """
    MCLAG domain definition within a topology plan.

    Defines MCLAG (Multi-Chassis Link Aggregation) domain configuration
    for switch pairs, including peer link and session link specifications.
    """

    plan = models.ForeignKey(
        TopologyPlan,
        on_delete=models.CASCADE,
        related_name='mclag_domains',
        help_text="Topology plan this MCLAG domain belongs to"
    )

    domain_id = models.CharField(
        max_length=100,
        help_text="Unique MCLAG domain identifier (e.g., 'MCLAG-001')"
    )

    switch_class = models.ForeignKey(
        PlanSwitchClass,
        on_delete=models.CASCADE,
        related_name='mclag_domains',
        help_text="Switch class this MCLAG domain applies to"
    )

    peer_link_count = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of peer links between switch pair"
    )

    session_link_count = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of session links between switch pair"
    )

    peer_start_port = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Starting port number for peer links"
    )

    session_start_port = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Starting port number for session links"
    )

    # SwitchGroup CRD configuration (Issue #151)
    switch_group_name = models.CharField(
        max_length=100,
        help_text="Name for generated SwitchGroup CRD (e.g., 'mclag-1', 'eslag-storage')"
    )

    redundancy_type = models.CharField(
        max_length=50,
        choices=[
            ('mclag', 'MCLAG'),
            ('eslag', 'ESLAG')
        ],
        default='mclag',
        help_text="Redundancy type for this domain"
    )

    class Meta:
        ordering = ['plan', 'switch_group_name']
        verbose_name = "MCLAG Domain"
        verbose_name_plural = "MCLAG Domains"
        unique_together = [['plan', 'switch_group_name']]

    def __str__(self):
        return f"{self.domain_id} ({self.switch_class.switch_class_id})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:planmclagdomain_detail', args=[self.pk])

    def clean(self):
        """Validate switch_group_name DNS-1123 compliance."""
        super().clean()

        import re

        # DNS-1123 validation for switch_group_name
        if self.switch_group_name:
            if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', self.switch_group_name):
                raise ValidationError({
                    'switch_group_name': 'Must be valid DNS-1123 label (lowercase, alphanumeric + hyphens, '
                                        'start/end with alphanumeric).'
                })

            if len(self.switch_group_name) > 63:
                raise ValidationError({
                    'switch_group_name': 'Must be max 63 characters.'
                })
