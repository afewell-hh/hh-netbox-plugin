"""
Topology Plan Models for DIET (Design and Implementation Excellence Tools)

These models enable pre-sales topology planning and design workflows.
They reference NetBox core models (DeviceType, ModuleType) and the custom
DeviceTypeExtension model for Hedgehog-specific metadata.
"""

from django.db import models
from django.urls import reverse
from django.core.validators import MinValueValidator
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
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of ports reserved for uplinks (spine connections)"
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

    class Meta:
        ordering = ['plan', 'fabric', 'switch_class_id']
        verbose_name = "Switch Class"
        verbose_name_plural = "Switch Classes"
        unique_together = [['plan', 'switch_class_id']]

    def __str__(self):
        return f"{self.switch_class_id} ({self.effective_quantity}x {self.device_type_extension.device_type})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:planswitchclass_detail', args=[self.pk])

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
        help_text="NIC slot identifier (e.g., 'NIC1', 'enp1s0f0')"
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

    class Meta:
        ordering = ['plan', 'domain_id']
        verbose_name = "MCLAG Domain"
        verbose_name_plural = "MCLAG Domains"
        unique_together = [['plan', 'domain_id']]

    def __str__(self):
        return f"{self.domain_id} ({self.switch_class.switch_class_id})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:planmclagdomain_detail', args=[self.pk])
