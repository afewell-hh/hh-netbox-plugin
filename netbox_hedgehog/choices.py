from utilities.choices import ChoiceSet

class KubernetesStatusChoices(ChoiceSet):
    """Choices for Kubernetes resource status"""
    
    UNKNOWN = 'unknown'
    PENDING = 'pending'
    APPLIED = 'applied'
    LIVE = 'live'
    ERROR = 'error'
    DELETING = 'deleting'
    
    CHOICES = [
        (UNKNOWN, 'Unknown'),
        (PENDING, 'Pending'),
        (APPLIED, 'Applied'),
        (LIVE, 'Live'),
        (ERROR, 'Error'),
        (DELETING, 'Deleting'),
    ]

class FabricStatusChoices(ChoiceSet):
    """Choices for Hedgehog fabric status"""
    
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    ERROR = 'error'
    SYNCING = 'syncing'
    
    CHOICES = [
        (ACTIVE, 'Active'),
        (INACTIVE, 'Inactive'),
        (ERROR, 'Error'),
        (SYNCING, 'Syncing'),
    ]

class CRDTypeChoices(ChoiceSet):
    """Choices for CRD types"""
    
    # VPC API CRDs
    VPC = 'vpc'
    EXTERNAL = 'external'
    EXTERNAL_ATTACHMENT = 'external_attachment'
    EXTERNAL_PEERING = 'external_peering'
    IPV4_NAMESPACE = 'ipv4_namespace'
    VPC_ATTACHMENT = 'vpc_attachment'
    VPC_PEERING = 'vpc_peering'
    
    # Wiring API CRDs
    CONNECTION = 'connection'
    SERVER = 'server'
    SWITCH = 'switch'
    SWITCH_GROUP = 'switch_group'
    VLAN_NAMESPACE = 'vlan_namespace'
    
    CHOICES = [
        # VPC API
        (VPC, 'VPC'),
        (EXTERNAL, 'External'),
        (EXTERNAL_ATTACHMENT, 'External Attachment'),
        (EXTERNAL_PEERING, 'External Peering'),
        (IPV4_NAMESPACE, 'IPv4 Namespace'),
        (VPC_ATTACHMENT, 'VPC Attachment'),
        (VPC_PEERING, 'VPC Peering'),
        # Wiring API
        (CONNECTION, 'Connection'),
        (SERVER, 'Server'),
        (SWITCH, 'Switch'),
        (SWITCH_GROUP, 'Switch Group'),
        (VLAN_NAMESPACE, 'VLAN Namespace'),
    ]

class ConnectionTypeChoices(ChoiceSet):
    """Choices for Hedgehog connection types"""
    
    UNBUNDLED = 'unbundled'
    BUNDLED = 'bundled'
    MCLAG = 'mclag'
    ESLAG = 'eslag'
    FABRIC = 'fabric'
    VPC_LOOPBACK = 'vpc_loopback'
    EXTERNAL = 'external'
    
    CHOICES = [
        (UNBUNDLED, 'Unbundled'),
        (BUNDLED, 'Bundled'),
        (MCLAG, 'MCLAG'),
        (ESLAG, 'ESLAG'),
        (FABRIC, 'Fabric'),
        (VPC_LOOPBACK, 'VPC Loopback'),
        (EXTERNAL, 'External'),
    ]