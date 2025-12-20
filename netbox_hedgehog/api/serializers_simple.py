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
        fields = ['id', 'server_class', 'switch_class', 'nic_module_type',
                  'port_type', 'ports_per_server', 'connection_speed', 'connection_distribution']


class PlanMCLAGDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PlanMCLAGDomain
        fields = ['id', 'plan', 'domain_id', 'member_switches']
