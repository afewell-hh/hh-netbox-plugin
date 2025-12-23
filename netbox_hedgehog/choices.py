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
    """Configuration status choices for Hedgehog Fabrics"""
    
    PLANNED = 'planned'
    ACTIVE = 'active' 
    MAINTENANCE = 'maintenance'
    DECOMMISSIONED = 'decommissioned'
    
    CHOICES = [
        (PLANNED, 'Planned'),
        (ACTIVE, 'Active'),
        (MAINTENANCE, 'Maintenance'),
        (DECOMMISSIONED, 'Decommissioned'),
    ]

class ConnectionStatusChoices(ChoiceSet):
    """Connection status choices for Hedgehog Fabrics"""
    
    UNKNOWN = 'unknown'
    CONNECTED = 'connected'
    DISCONNECTED = 'disconnected'
    ERROR = 'error'
    
    CHOICES = [
        (UNKNOWN, 'Unknown'),
        (CONNECTED, 'Connected'),
        (DISCONNECTED, 'Disconnected'), 
        (ERROR, 'Error'),
    ]

class SyncStatusChoices(ChoiceSet):
    """Sync status choices for Hedgehog Fabrics"""
    
    NEVER_SYNCED = 'never_synced'
    IN_SYNC = 'in_sync'
    OUT_OF_SYNC = 'out_of_sync'
    SYNCING = 'syncing'
    ERROR = 'error'
    
    CHOICES = [
        (NEVER_SYNCED, 'Never Synced'),
        (IN_SYNC, 'In Sync'),
        (OUT_OF_SYNC, 'Out of Sync'),
        (SYNCING, 'Syncing'),
        (ERROR, 'Sync Error'),
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

# =============================================================================
# Topology Planning Choices (DIET Module)
# =============================================================================

class TopologyPlanStatusChoices(ChoiceSet):
    """Status choices for TopologyPlan"""

    DRAFT = 'draft'
    REVIEW = 'review'
    APPROVED = 'approved'
    EXPORTED = 'exported'

    CHOICES = [
        (DRAFT, 'Draft'),
        (REVIEW, 'Review'),
        (APPROVED, 'Approved'),
        (EXPORTED, 'Exported'),
    ]


class ServerClassCategoryChoices(ChoiceSet):
    """Category choices for PlanServerClass"""

    GPU = 'gpu'
    STORAGE = 'storage'
    INFRASTRUCTURE = 'infrastructure'

    CHOICES = [
        (GPU, 'GPU'),
        (STORAGE, 'Storage'),
        (INFRASTRUCTURE, 'Infrastructure'),
    ]


class FabricTypeChoices(ChoiceSet):
    """Fabric type choices for PlanSwitchClass"""

    FRONTEND = 'frontend'
    BACKEND = 'backend'
    OOB = 'oob'

    CHOICES = [
        (FRONTEND, 'Frontend'),
        (BACKEND, 'Backend'),
        (OOB, 'Out-of-Band'),
    ]


class HedgehogRoleChoices(ChoiceSet):
    """Hedgehog role choices for PlanSwitchClass"""

    SPINE = 'spine'
    SERVER_LEAF = 'server-leaf'
    BORDER_LEAF = 'border-leaf'
    VIRTUAL = 'virtual'

    CHOICES = [
        (SPINE, 'Spine'),
        (SERVER_LEAF, 'Server Leaf'),
        (BORDER_LEAF, 'Border Leaf'),
        (VIRTUAL, 'Virtual'),
    ]


class ConnectionDistributionChoices(ChoiceSet):
    """Distribution choices for PlanServerConnection"""

    SAME_SWITCH = 'same-switch'
    ALTERNATING = 'alternating'
    RAIL_OPTIMIZED = 'rail-optimized'

    CHOICES = [
        (SAME_SWITCH, 'Same Switch'),
        (ALTERNATING, 'Alternating'),
        (RAIL_OPTIMIZED, 'Rail-Optimized'),
    ]


class PortZoneTypeChoices(ChoiceSet):
    """Zone type choices for SwitchPortZone"""

    SERVER = 'server'
    UPLINK = 'uplink'
    MCLAG = 'mclag'
    PEER = 'peer'
    SESSION = 'session'
    OOB = 'oob'
    FABRIC = 'fabric'

    CHOICES = [
        (SERVER, 'Server'),
        (UPLINK, 'Uplink'),
        (MCLAG, 'MCLAG'),
        (PEER, 'Peer'),
        (SESSION, 'Session'),
        (OOB, 'OOB'),
        (FABRIC, 'Fabric'),
    ]


class AllocationStrategyChoices(ChoiceSet):
    """Allocation strategy choices for SwitchPortZone"""

    SEQUENTIAL = 'sequential'
    INTERLEAVED = 'interleaved'
    SPACED = 'spaced'
    CUSTOM = 'custom'

    CHOICES = [
        (SEQUENTIAL, 'Sequential'),
        (INTERLEAVED, 'Interleaved'),
        (SPACED, 'Spaced'),
        (CUSTOM, 'Custom'),
    ]


class PortTypeChoices(ChoiceSet):
    """Port type choices for PlanServerConnection"""

    DATA = 'data'
    IPMI = 'ipmi'
    PXE = 'pxe'

    CHOICES = [
        (DATA, 'Data'),
        (IPMI, 'IPMI'),
        (PXE, 'PXE'),
    ]
