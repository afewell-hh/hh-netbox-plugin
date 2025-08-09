"""
CRUD Service Protocols

typing.Protocol definitions for CRUD operations on all models.
Each service protocol defines the standard operations: create, read, update, delete, list.
"""

from typing import Protocol, List, Optional, Dict, Any, Union
from datetime import datetime
from ..models import *


class BaseCRUDService(Protocol):
    """Base protocol for CRUD operations"""
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new instance"""
        ...
    
    def get_by_id(self, id: int) -> Optional[Dict[str, Any]]:
        """Retrieve instance by ID"""
        ...
    
    def update(self, id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update existing instance"""
        ...
    
    def delete(self, id: int) -> bool:
        """Delete instance by ID"""
        ...
    
    def list(self, filters: Optional[Dict[str, Any]] = None, 
             limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """List instances with optional filtering and pagination"""
        ...
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count instances with optional filtering"""
        ...
    
    def exists(self, id: int) -> bool:
        """Check if instance exists"""
        ...


class FabricService(BaseCRUDService, Protocol):
    """Service protocol for HedgehogFabric operations"""
    
    def test_kubernetes_connection(self, id: int) -> Dict[str, Any]:
        """Test Kubernetes connectivity for fabric"""
        ...
    
    def trigger_sync(self, id: int) -> Dict[str, Any]:
        """Trigger manual synchronization"""
        ...
    
    def get_sync_status(self, id: int) -> Dict[str, Any]:
        """Get current sync status and last sync information"""
        ...
    
    def get_crds(self, id: int, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get all CRDs belonging to this fabric"""
        ...
    
    def update_connection_status(self, id: int, status: str, error: Optional[str] = None) -> bool:
        """Update fabric connection status"""
        ...
    
    def update_sync_status(self, id: int, status: str, error: Optional[str] = None) -> bool:
        """Update fabric sync status"""
        ...


class GitRepositoryService(BaseCRUDService, Protocol):
    """Service protocol for GitRepository operations"""
    
    def test_connection(self, id: int) -> Dict[str, Any]:
        """Test Git repository connectivity"""
        ...
    
    def validate_credentials(self, id: int) -> Dict[str, Any]:
        """Validate stored credentials"""
        ...
    
    def get_branches(self, id: int) -> List[str]:
        """List available branches"""
        ...
    
    def get_files(self, id: int, path: str = "/", branch: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files in repository path"""
        ...
    
    def get_file_content(self, id: int, file_path: str, branch: Optional[str] = None) -> str:
        """Get content of specific file"""
        ...
    
    def update_fabric_count(self, id: int) -> int:
        """Update and return fabric count using this repository"""
        ...


class BaseCRDService(BaseCRUDService, Protocol):
    """Service protocol for BaseCRD operations"""
    
    def apply_to_kubernetes(self, id: int) -> Dict[str, Any]:
        """Apply CRD to Kubernetes cluster"""
        ...
    
    def sync_from_kubernetes(self, id: int) -> Dict[str, Any]:
        """Sync CRD state from Kubernetes"""
        ...
    
    def get_kubernetes_status(self, id: int) -> Dict[str, Any]:
        """Get current Kubernetes status"""
        ...
    
    def validate_spec(self, id: int) -> Dict[str, Any]:
        """Validate CRD specification"""
        ...
    
    def generate_yaml(self, id: int) -> str:
        """Generate YAML representation"""
        ...
    
    def update_kubernetes_status(self, id: int, status: str, 
                               uid: Optional[str] = None, 
                               resource_version: Optional[str] = None) -> bool:
        """Update Kubernetes-related fields"""
        ...


class HedgehogResourceService(BaseCRUDService, Protocol):
    """Service protocol for HedgehogResource operations"""
    
    def commit_draft(self, id: int, commit_message: str) -> Dict[str, Any]:
        """Commit draft changes to Git repository"""
        ...
    
    def discard_draft(self, id: int) -> bool:
        """Discard draft changes"""
        ...
    
    def detect_drift(self, id: int) -> Dict[str, Any]:
        """Detect drift between desired and actual state"""
        ...
    
    def resolve_drift(self, id: int, action: str) -> Dict[str, Any]:
        """Resolve detected drift with specified action"""
        ...
    
    def update_desired_state(self, id: int, spec: Dict[str, Any], 
                           commit_sha: str, file_path: str) -> bool:
        """Update desired state from Git repository"""
        ...
    
    def update_actual_state(self, id: int, spec: Dict[str, Any], 
                          status: Dict[str, Any], resource_version: str) -> bool:
        """Update actual state from Kubernetes"""
        ...
    
    def transition_state(self, id: int, new_state: str, 
                        trigger: str, reason: Optional[str] = None, 
                        context: Optional[Dict[str, Any]] = None) -> bool:
        """Transition resource to new state"""
        ...


class StateTransitionHistoryService(BaseCRUDService, Protocol):
    """Service protocol for StateTransitionHistory operations"""
    
    def get_resource_history(self, resource_id: int, 
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get state transition history for specific resource"""
        ...
    
    def get_fabric_history(self, fabric_id: int, 
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get state transition history for fabric"""
        ...
    
    def get_user_history(self, user_id: int, 
                       limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get state transitions triggered by user"""
        ...


class ReconciliationAlertService(BaseCRUDService, Protocol):
    """Service protocol for ReconciliationAlert operations"""
    
    def acknowledge(self, id: int, user_id: int) -> bool:
        """Acknowledge alert"""
        ...
    
    def resolve(self, id: int, user_id: int, action: str, 
               metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Resolve alert with specified action"""
        ...
    
    def suppress(self, id: int, duration: Optional[int] = None) -> bool:
        """Suppress alert for specified duration"""
        ...
    
    def get_active_alerts(self, fabric_id: Optional[int] = None, 
                         severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get active alerts with optional filtering"""
        ...
    
    def get_alert_metrics(self, fabric_id: Optional[int] = None) -> Dict[str, Any]:
        """Get alert metrics and statistics"""
        ...


# VPC API Services
class VPCService(BaseCRDService, Protocol):
    """Service protocol for VPC operations"""
    
    def get_subnets(self, id: int) -> List[str]:
        """Get VPC subnets from spec"""
        ...
    
    def validate_subnets(self, id: int) -> Dict[str, Any]:
        """Validate VPC subnet configuration"""
        ...


class ExternalService(BaseCRDService, Protocol):
    """Service protocol for External operations"""
    
    def get_peerings(self, id: int) -> List[Dict[str, Any]]:
        """Get external peerings for this external system"""
        ...


class ExternalAttachmentService(BaseCRDService, Protocol):
    """Service protocol for ExternalAttachment operations"""
    
    def validate_attachment(self, id: int) -> Dict[str, Any]:
        """Validate external attachment configuration"""
        ...


class ExternalPeeringService(BaseCRDService, Protocol):
    """Service protocol for ExternalPeering operations"""
    
    def validate_peering(self, id: int) -> Dict[str, Any]:
        """Validate external peering configuration"""
        ...


class IPv4NamespaceService(BaseCRDService, Protocol):
    """Service protocol for IPv4Namespace operations"""
    
    def check_subnet_conflicts(self, id: int) -> List[Dict[str, Any]]:
        """Check for subnet conflicts with other namespaces"""
        ...


class VPCAttachmentService(BaseCRDService, Protocol):
    """Service protocol for VPCAttachment operations"""
    
    def validate_attachment(self, id: int) -> Dict[str, Any]:
        """Validate VPC attachment configuration"""
        ...


class VPCPeeringService(BaseCRDService, Protocol):
    """Service protocol for VPCPeering operations"""
    
    def validate_peering(self, id: int) -> Dict[str, Any]:
        """Validate VPC peering configuration"""
        ...


# Wiring API Services
class ConnectionService(BaseCRDService, Protocol):
    """Service protocol for Connection operations"""
    
    def get_connection_type(self, id: int) -> str:
        """Get connection type from spec"""
        ...
    
    def validate_connection(self, id: int) -> Dict[str, Any]:
        """Validate connection configuration"""
        ...


class ServerService(BaseCRDService, Protocol):
    """Service protocol for Server operations"""
    
    def get_connections(self, id: int) -> List[Dict[str, Any]]:
        """Get connections for this server"""
        ...


class SwitchService(BaseCRDService, Protocol):
    """Service protocol for Switch operations"""
    
    def get_switch_role(self, id: int) -> str:
        """Get switch role from spec"""
        ...
    
    def get_asn(self, id: int) -> Optional[int]:
        """Get ASN from spec"""
        ...
    
    def get_connections(self, id: int) -> List[Dict[str, Any]]:
        """Get connections for this switch"""
        ...


class SwitchGroupService(BaseCRDService, Protocol):
    """Service protocol for SwitchGroup operations"""
    
    def get_group_type(self, id: int) -> str:
        """Get group type from spec"""
        ...
    
    def get_member_switches(self, id: int) -> List[Dict[str, Any]]:
        """Get switches that are members of this group"""
        ...


class VLANNamespaceService(BaseCRDService, Protocol):
    """Service protocol for VLANNamespace operations"""
    
    def get_vlan_ranges(self, id: int) -> List[str]:
        """Get VLAN ranges from spec"""
        ...
    
    def check_range_conflicts(self, id: int) -> List[Dict[str, Any]]:
        """Check for VLAN range conflicts with other namespaces"""
        ...
    
    def allocate_vlan(self, id: int, requested_vlan: Optional[int] = None) -> int:
        """Allocate a VLAN from this namespace"""
        ...
    
    def deallocate_vlan(self, id: int, vlan_id: int) -> bool:
        """Deallocate a VLAN from this namespace"""
        ...