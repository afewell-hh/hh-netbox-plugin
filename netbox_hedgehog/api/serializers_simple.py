"""
Simple serializers for Topology Planning models (DIET Module)

These are minimal serializers needed for NetBox's event/webhook system.
Full REST API views are deferred to a future issue.
"""

from rest_framework import serializers
from .. import models


class BreakoutOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BreakoutOption
        fields = ['id', 'breakout_id', 'from_speed', 'logical_ports', 'logical_speed', 'optic_type']


class DeviceTypeExtensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DeviceTypeExtension
        fields = ['id', 'device_type', 'mclag_capable', 'hedgehog_roles', 'native_speed', 'uplink_ports']


class TopologyPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TopologyPlan
        fields = ['id', 'name', 'customer_name', 'description', 'status', 'created_by', 'notes']


class PlanServerClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PlanServerClass
        fields = ['id', 'plan', 'server_class_id', 'description', 'category', 'quantity',
                  'gpus_per_server', 'server_device_type']


class PlanSwitchClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PlanSwitchClass
        fields = ['id', 'plan', 'switch_class_id', 'fabric', 'hedgehog_role',
                  'device_type_extension', 'uplink_ports_per_switch', 'mclag_pair',
                  'calculated_quantity', 'override_quantity']


class PlanServerConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PlanServerConnection
        fields = ['id', 'server_class', 'connection_id', 'nic_module_type', 'nic_slot',
                  'connection_name', 'ports_per_connection', 'hedgehog_conn_type',
                  'distribution', 'target_switch_class', 'speed', 'rail', 'port_type']


class PlanMCLAGDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PlanMCLAGDomain
        fields = ['id', 'plan', 'domain_id', 'switch_class', 'peer_link_count',
                  'session_link_count', 'peer_start_port', 'session_start_port']


class SwitchPortZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SwitchPortZone
        fields = [
            'id',
            'switch_class',
            'zone_name',
            'zone_type',
            'port_spec',
            'breakout_option',
            'allocation_strategy',
            'allocation_order',
            'priority',
        ]
