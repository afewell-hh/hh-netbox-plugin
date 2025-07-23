from django.db import models
from django.urls import reverse
from .base import BaseCRD

class Connection(BaseCRD):
    """
    Hedgehog Connection CRD.
    Defines logical/physical connections between devices.
    Supports multiple connection types: unbundled, bundled, MCLAG, fabric, etc.
    """
    
    class Meta:
        verbose_name = "Connection"
        verbose_name_plural = "Connections"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:connection_detail', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'wiring.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'Connection'
    
    @property
    def connection_type(self):
        """Extract connection type from spec"""
        if not self.spec:
            return 'unknown'
        
        # Connection type is determined by which key is present in spec
        connection_types = ['unbundled', 'bundled', 'mclag', 'eslag', 'fabric', 'vpcLoopback', 'external']
        for conn_type in connection_types:
            if conn_type in self.spec:
                return conn_type
        return 'unknown'

class Server(BaseCRD):
    """
    Hedgehog Server CRD.
    Represents server connection configuration in the fabric.
    """
    
    class Meta:
        verbose_name = "Server"
        verbose_name_plural = "Servers"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:server_detail', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'wiring.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'Server'

class Switch(BaseCRD):
    """
    Hedgehog Switch CRD.
    Represents network switches with configurable roles, redundancy groups, and ports.
    """
    
    class Meta:
        verbose_name = "Switch"
        verbose_name_plural = "Switches"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:switch_detail', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'wiring.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'Switch'
    
    @property
    def switch_role(self):
        """Extract switch role from spec"""
        if not self.spec:
            return 'unknown'
        return self.spec.get('role', 'unknown')
    
    @property
    def asn(self):
        """Extract ASN from spec"""
        if not self.spec:
            return None
        return self.spec.get('asn')

class SwitchGroup(BaseCRD):
    """
    Hedgehog SwitchGroup CRD.
    Groups switches together for redundancy and management purposes.
    """
    
    class Meta:
        verbose_name = "Switch Group"
        verbose_name_plural = "Switch Groups"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:switchgroup_detail', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'wiring.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'SwitchGroup'
    
    @property
    def group_type(self):
        """Extract group type from spec"""
        if not self.spec:
            return 'unknown'
        return self.spec.get('type', 'unknown')

class VLANNamespace(BaseCRD):
    """
    Hedgehog VLANNamespace CRD.
    Manages VLAN ranges and prevents VLAN range overlaps.
    """
    
    class Meta:
        verbose_name = "VLAN Namespace"
        verbose_name_plural = "VLAN Namespaces"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:vlannamespace_detail', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'wiring.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'VLANNamespace'
    
    @property
    def vlan_ranges(self):
        """Extract VLAN ranges from spec"""
        if not self.spec:
            return []
        ranges = self.spec.get('ranges', [])
        if isinstance(ranges, list):
            return ranges
        return []