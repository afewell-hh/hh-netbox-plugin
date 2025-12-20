"""
Django Admin Registration for Hedgehog Plugin Models

Registers models with Django's admin interface for easy data management.
"""

from django.contrib import admin
from .models import (
    # Operational CRD Models
    HedgehogFabric,
    Connection,
    Server,
    Switch,
    SwitchGroup,
    VLANNamespace,
    VPC,
    VPCAttachment,
    VPCPeering,
    External,
    ExternalAttachment,
    ExternalPeering,
    IPv4Namespace,
    # DIET Planning Models
    BreakoutOption,
    DeviceTypeExtension,
)


# Operational CRD Models
@admin.register(HedgehogFabric)
class HedgehogFabricAdmin(admin.ModelAdmin):
    list_display = ['name', 'namespace', 'status', 'created', 'last_updated']
    list_filter = ['status', 'created']
    search_fields = ['name', 'namespace']


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(Switch)
class SwitchAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(SwitchGroup)
class SwitchGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(VLANNamespace)
class VLANNamespaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(VPC)
class VPCAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(VPCAttachment)
class VPCAttachmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(VPCPeering)
class VPCPeeringAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(External)
class ExternalAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(ExternalAttachment)
class ExternalAttachmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(ExternalPeering)
class ExternalPeeringAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


@admin.register(IPv4Namespace)
class IPv4NamespaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'fabric', 'created', 'last_updated']
    list_filter = ['fabric', 'created']
    search_fields = ['name']


# DIET Planning Models
@admin.register(BreakoutOption)
class BreakoutOptionAdmin(admin.ModelAdmin):
    """
    Admin interface for BreakoutOption model.

    Allows administrators to configure breakout options for different
    port speeds (e.g., 800G -> 2x400G, 4x200G, 8x100G).
    """
    list_display = [
        'breakout_id',
        'from_speed',
        'logical_ports',
        'logical_speed',
        'optic_type',
        'created',
    ]
    list_filter = ['from_speed', 'logical_speed', 'optic_type']
    search_fields = ['breakout_id', 'optic_type']
    ordering = ['-from_speed', 'logical_ports']

    fieldsets = (
        ('Breakout Configuration', {
            'fields': ('breakout_id', 'from_speed', 'logical_ports', 'logical_speed'),
            'description': 'Define how a physical port breaks out into logical ports'
        }),
        ('Hardware Details', {
            'fields': ('optic_type',),
            'description': 'Optional optic type information'
        }),
    )


@admin.register(DeviceTypeExtension)
class DeviceTypeExtensionAdmin(admin.ModelAdmin):
    """
    Admin interface for DeviceTypeExtension model.

    Allows administrators to add Hedgehog-specific metadata to NetBox DeviceTypes
    such as MCLAG capability and supported fabric roles.
    """
    list_display = [
        'device_type',
        'get_manufacturer',
        'mclag_capable',
        'get_roles',
        'created',
    ]
    list_filter = ['mclag_capable', 'created']
    search_fields = [
        'device_type__model',
        'device_type__manufacturer__name',
        'notes',
    ]
    raw_id_fields = ['device_type']  # Better UX for FK field

    fieldsets = (
        ('Device Type', {
            'fields': ('device_type',),
            'description': 'Select the NetBox DeviceType to add Hedgehog metadata to'
        }),
        ('Hedgehog Capabilities', {
            'fields': ('mclag_capable', 'hedgehog_roles'),
            'description': 'Hedgehog-specific configuration for this device type'
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )

    def get_manufacturer(self, obj):
        """Display manufacturer name in list view."""
        return obj.device_type.manufacturer.name if obj.device_type else '-'
    get_manufacturer.short_description = 'Manufacturer'
    get_manufacturer.admin_order_field = 'device_type__manufacturer__name'

    def get_roles(self, obj):
        """Display supported Hedgehog roles in list view."""
        if obj.hedgehog_roles:
            return ', '.join(obj.hedgehog_roles)
        return '-'
    get_roles.short_description = 'Hedgehog Roles'
