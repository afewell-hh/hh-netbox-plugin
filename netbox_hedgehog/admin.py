"""
Django Admin Configuration for Hedgehog NetBox Plugin

Registers models with Django admin for data entry and management.
"""

from django.contrib import admin
from .models.topology_planning import (
    SwitchModel, SwitchPortGroup, NICModel, BreakoutOption
)


@admin.register(SwitchModel)
class SwitchModelAdmin(admin.ModelAdmin):
    """Admin configuration for SwitchModel"""

    list_display = ['model_id', 'vendor', 'part_number', 'total_ports', 'mclag_capable']
    search_fields = ['model_id', 'vendor', 'part_number']
    list_filter = ['vendor', 'mclag_capable']
    fieldsets = (
        ('Identification', {
            'fields': ('model_id', 'vendor', 'part_number')
        }),
        ('Specifications', {
            'fields': ('total_ports', 'mclag_capable', 'hedgehog_roles')
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(SwitchPortGroup)
class SwitchPortGroupAdmin(admin.ModelAdmin):
    """Admin configuration for SwitchPortGroup"""

    list_display = ['switch_model', 'group_name', 'port_count', 'native_speed', 'port_range']
    search_fields = ['group_name', 'switch_model__model_id']
    list_filter = ['switch_model__vendor', 'native_speed']
    autocomplete_fields = ['switch_model']
    fieldsets = (
        ('Port Group', {
            'fields': ('switch_model', 'group_name', 'port_count', 'port_range')
        }),
        ('Speed and Breakout', {
            'fields': ('native_speed', 'supported_breakouts')
        }),
    )


@admin.register(NICModel)
class NICModelAdmin(admin.ModelAdmin):
    """Admin configuration for NICModel"""

    list_display = ['model_id', 'vendor', 'part_number', 'port_count', 'port_speed', 'port_type']
    search_fields = ['model_id', 'vendor', 'part_number']
    list_filter = ['vendor', 'port_speed', 'port_type']
    fieldsets = (
        ('Identification', {
            'fields': ('model_id', 'vendor', 'part_number')
        }),
        ('Specifications', {
            'fields': ('port_count', 'port_speed', 'port_type')
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(BreakoutOption)
class BreakoutOptionAdmin(admin.ModelAdmin):
    """Admin configuration for BreakoutOption"""

    list_display = ['breakout_id', 'from_speed', 'logical_ports', 'logical_speed', 'optic_type']
    search_fields = ['breakout_id', 'optic_type']
    list_filter = ['from_speed', 'logical_speed']
    fieldsets = (
        ('Breakout Configuration', {
            'fields': ('breakout_id', 'from_speed', 'logical_ports', 'logical_speed', 'optic_type')
        }),
    )
