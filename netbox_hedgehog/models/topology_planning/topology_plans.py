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
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    PortTypeChoices,
)

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

    fabric = models.CharField(
        max_length=50,
        choices=FabricTypeChoices,
        blank=True,
        help_text="Fabric type (Frontend, Backend, OOB)"
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
        ordering = ['plan', 'fabric', 'switch_class_id']
        verbose_name = "Switch Class"
        verbose_name_plural = "Switch Classes"
        unique_together = [['plan', 'switch_class_id']]

    def __str__(self):
        return f"{self.switch_class_id} ({self.effective_quantity}x {self.device_type_extension.device_type})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:planswitchclass_detail', args=[self.pk])

    def save(self, *args, **kwargs):
        """
        Auto-convert deprecated mclag_pair to redundancy_type (DIET-165 Phase 5).

        Per Phase 3 spec addendum: mclag_pair=True auto-converts to redundancy_type='mclag'
        and redundancy_group='mclag-<switch_class_id>' on save.
        """
        # Auto-conversion: mclag_pair → redundancy_type (only if redundancy_type not already set)
        if self.mclag_pair and not self.redundancy_type:
            self.redundancy_type = 'mclag'
            # Auto-generate redundancy_group if not set
            if not self.redundancy_group:
                self.redundancy_group = f'mclag-{self.switch_class_id}'

        super().save(*args, **kwargs)

    def clean(self):
        """Validate redundancy configuration (DIET-165 Phase 5)."""
        super().clean()

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

    nic_module_type = models.ForeignKey(
        ModuleType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='plan_server_connections',
        help_text="NIC module type (optional for MVP)"
    )

    nic_slot = models.CharField(
        max_length=50,
        blank=True,
        help_text="NIC slot identifier (e.g., 'NIC1', 'enp1s0f0'). Used for legacy naming when server_interface_template is not set."
    )

    server_interface_template = models.ForeignKey(
        'dcim.InterfaceTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plan_server_connections',
        help_text="First server interface template for this connection. "
                  "If ports_per_connection > 1, subsequent interfaces will be used in order. "
                  "If not set and nic_slot is provided, uses legacy naming mode."
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

    target_switch_class = models.ForeignKey(
        PlanSwitchClass,
        on_delete=models.PROTECT,
        related_name='incoming_connections',
        help_text="Switch class this connection targets"
    )

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

    class Meta:
        ordering = ['server_class', 'connection_id']
        verbose_name = "Server Connection"
        verbose_name_plural = "Server Connections"
        unique_together = [['server_class', 'connection_id']]

    def __str__(self):
        return f"{self.server_class.server_class_id}/{self.connection_id} → {self.target_switch_class.switch_class_id}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[self.pk])

    def clean(self):
        """Validate server interface selection (Option 4: nic_slot as legacy indicator)."""
        super().clean()
        from django.core.exceptions import ValidationError

        # Option 4 validation: Check if either template or nic_slot is provided
        if not self.server_interface_template and not self.nic_slot:
            raise ValidationError({
                'server_interface_template':
                    'Either select an interface template or provide a NIC slot for legacy naming mode.'
            })

        # If template is selected, validate it belongs to server device type
        if self.server_interface_template:
            if not self.server_class or not self.server_class.server_device_type:
                # Skip validation if server_class not set yet (form will handle this)
                return

            if self.server_interface_template.device_type != self.server_class.server_device_type:
                raise ValidationError({
                    'server_interface_template':
                        f'Interface template must belong to device type {self.server_class.server_device_type}'
                })

            # Validate sufficient interfaces for ports_per_connection
            if self.ports_per_connection and self.ports_per_connection > 1:
                available_interfaces = self._get_available_interface_sequence()
                if len(available_interfaces) < self.ports_per_connection:
                    raise ValidationError({
                        'ports_per_connection':
                            f'Insufficient interfaces available. Selected {self.server_interface_template.name}, '
                            f'need {self.ports_per_connection} total, only {len(available_interfaces)} available.'
                    })

    def _get_available_interface_sequence(self):
        """
        Get ordered sequence of interfaces starting from selected template.

        Uses natural sorting and prefix scoping to ensure correct ordering
        (e.g., cx7-2, cx7-3, ..., cx7-10, not cx7-10, cx7-2).

        Only includes interfaces with same prefix as selected template to
        avoid crossing into unrelated interface groups.

        Returns list of InterfaceTemplate objects in natural order.
        """
        from dcim.models import InterfaceTemplate
        import re

        if not self.server_interface_template:
            return []

        if not self.server_class or not self.server_class.server_device_type:
            return []

        # Get all interfaces for device type
        all_interfaces = list(
            InterfaceTemplate.objects.filter(
                device_type=self.server_class.server_device_type
            )
        )

        # Extract prefix from selected interface (e.g., "cx7-1" → "cx7-")
        selected_name = self.server_interface_template.name
        prefix_match = re.match(r'^([a-zA-Z]+[-_]?)', selected_name)
        if prefix_match:
            prefix = prefix_match.group(1)
            # Filter to same prefix only
            all_interfaces = [
                iface for iface in all_interfaces
                if iface.name.startswith(prefix)
            ]

        # Natural sort helper
        def natural_sort_key(iface):
            """Convert interface name to sortable key with numeric awareness."""
            parts = re.split(r'(\d+)', iface.name)
            return [int(p) if p.isdigit() else p.lower() for p in parts]

        # Sort naturally
        all_interfaces.sort(key=natural_sort_key)

        # Find starting position
        try:
            start_idx = all_interfaces.index(self.server_interface_template)
        except ValueError:
            return []

        # Return sequence from starting position
        return all_interfaces[start_idx:]


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
