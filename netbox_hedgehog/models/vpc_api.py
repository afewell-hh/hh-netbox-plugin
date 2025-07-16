from django.db import models
from django.urls import reverse
from .base import BaseCRD

class VPC(BaseCRD):
    """
    Hedgehog VPC (Virtual Private Cloud) CRD.
    Represents a virtual network with isolated network resources.
    """
    
    class Meta:
        verbose_name = "VPC"
        verbose_name_plural = "VPCs"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:vpc', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'VPC'

class External(BaseCRD):
    """
    Hedgehog External CRD.
    Represents external systems connected to the Fabric.
    """
    
    class Meta:
        verbose_name = "External"
        verbose_name_plural = "Externals"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:external_detail', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'External'

class ExternalAttachment(BaseCRD):
    """
    Hedgehog ExternalAttachment CRD.
    Attaches external systems to fabric switches.
    """
    
    class Meta:
        verbose_name = "External Attachment"
        verbose_name_plural = "External Attachments"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:externalattachment_detail', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'ExternalAttachment'

class ExternalPeering(BaseCRD):
    """
    Hedgehog ExternalPeering CRD.
    Enables peering between VPCs and external systems.
    """
    
    class Meta:
        verbose_name = "External Peering"
        verbose_name_plural = "External Peerings"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:externalpeering_detail', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'ExternalPeering'

class IPv4Namespace(BaseCRD):
    """
    Hedgehog IPv4Namespace CRD.
    Manages IPv4 address namespaces for network isolation.
    """
    
    class Meta:
        verbose_name = "IPv4 Namespace"
        verbose_name_plural = "IPv4 Namespaces"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:ipv4namespace', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'IPv4Namespace'

class VPCAttachment(BaseCRD):
    """
    Hedgehog VPCAttachment CRD.
    Attaches workloads to VPCs.
    """
    
    class Meta:
        verbose_name = "VPC Attachment"
        verbose_name_plural = "VPC Attachments"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:vpcattachment_detail', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'VPCAttachment'

class VPCPeering(BaseCRD):
    """
    Hedgehog VPCPeering CRD.
    Enables peering between different VPCs.
    """
    
    class Meta:
        verbose_name = "VPC Peering"
        verbose_name_plural = "VPC Peerings"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:vpcpeering_detail', kwargs={'pk': self.pk})
    
    def get_api_version(self):
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self):
        return 'VPCPeering'