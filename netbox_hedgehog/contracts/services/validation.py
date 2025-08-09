"""
Validation Service Protocols

typing.Protocol definitions for validation operations:
- YAML validation and parsing
- Kubernetes spec validation
- Business logic validation
- Cross-resource validation
"""

from typing import Protocol, List, Optional, Dict, Any, Union
from datetime import datetime


class ValidationService(Protocol):
    """Base service protocol for validation operations"""
    
    def validate(self, data: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate data and return validation result"""
        ...
    
    def get_validation_schema(self) -> Dict[str, Any]:
        """Get validation schema definition"""
        ...
    
    def get_validation_errors(self, data: Any) -> List[Dict[str, Any]]:
        """Get detailed validation error messages"""
        ...


class YAMLValidationService(ValidationService, Protocol):
    """Service protocol for YAML validation and parsing"""
    
    def validate_yaml_syntax(self, yaml_content: str) -> Dict[str, Any]:
        """Validate YAML syntax"""
        ...
    
    def parse_yaml(self, yaml_content: str) -> Dict[str, Any]:
        """Parse YAML content to dictionary"""
        ...
    
    def validate_yaml_structure(self, yaml_content: str, 
                              expected_kind: str) -> Dict[str, Any]:
        """Validate YAML has expected Kubernetes structure"""
        ...
    
    def convert_yaml_to_json(self, yaml_content: str) -> str:
        """Convert YAML to JSON string"""
        ...
    
    def convert_json_to_yaml(self, json_content: str) -> str:
        """Convert JSON to YAML string"""
        ...
    
    def validate_multiple_yamls(self, yaml_content: str) -> Dict[str, Any]:
        """Validate multiple YAML documents in single string"""
        ...
    
    def extract_yaml_metadata(self, yaml_content: str) -> Dict[str, Any]:
        """Extract Kubernetes metadata from YAML"""
        ...


class SpecValidationService(ValidationService, Protocol):
    """Service protocol for Kubernetes spec validation"""
    
    def validate_crd_spec(self, kind: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate CRD spec against kind schema"""
        ...
    
    def validate_vpc_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate VPC specification"""
        ...
    
    def validate_connection_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Connection specification"""
        ...
    
    def validate_switch_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Switch specification"""
        ...
    
    def validate_server_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Server specification"""
        ...
    
    def validate_external_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate External specification"""
        ...
    
    def validate_field_types(self, spec: Dict[str, Any], 
                           schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate field types against schema"""
        ...
    
    def validate_required_fields(self, spec: Dict[str, Any],
                               required_fields: List[str]) -> List[str]:
        """Validate all required fields are present"""
        ...
    
    def validate_field_constraints(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate field value constraints"""
        ...


class BusinessLogicValidationService(ValidationService, Protocol):
    """Service protocol for business logic validation"""
    
    def validate_fabric_configuration(self, fabric_id: int) -> Dict[str, Any]:
        """Validate fabric configuration is consistent"""
        ...
    
    def validate_network_configuration(self, fabric_id: int) -> Dict[str, Any]:
        """Validate network configuration doesn't have conflicts"""
        ...
    
    def validate_subnet_allocation(self, vpc_id: int, subnets: List[str]) -> Dict[str, Any]:
        """Validate subnet allocation doesn't conflict"""
        ...
    
    def validate_vlan_allocation(self, namespace_id: int, vlans: List[int]) -> Dict[str, Any]:
        """Validate VLAN allocation doesn't conflict"""
        ...
    
    def validate_connection_topology(self, connection_id: int) -> Dict[str, Any]:
        """Validate connection topology is valid"""
        ...
    
    def validate_switch_connectivity(self, switch_id: int) -> Dict[str, Any]:
        """Validate switch has valid connections"""
        ...
    
    def validate_asn_allocation(self, fabric_id: int, asn: int) -> Dict[str, Any]:
        """Validate ASN allocation doesn't conflict"""
        ...
    
    def validate_redundancy_groups(self, fabric_id: int) -> Dict[str, Any]:
        """Validate switch redundancy group configuration"""
        ...


class CrossResourceValidationService(ValidationService, Protocol):
    """Service protocol for cross-resource validation"""
    
    def validate_resource_dependencies(self, resource_id: int) -> Dict[str, Any]:
        """Validate resource dependencies exist and are valid"""
        ...
    
    def validate_vpc_references(self, fabric_id: int) -> Dict[str, Any]:
        """Validate all VPC references are valid"""
        ...
    
    def validate_connection_references(self, fabric_id: int) -> Dict[str, Any]:
        """Validate all connection references are valid"""
        ...
    
    def validate_namespace_references(self, fabric_id: int) -> Dict[str, Any]:
        """Validate all namespace references are valid"""
        ...
    
    def find_orphaned_resources(self, fabric_id: int) -> List[Dict[str, Any]]:
        """Find resources with invalid references"""
        ...
    
    def find_circular_dependencies(self, fabric_id: int) -> List[List[int]]:
        """Find circular dependency chains"""
        ...
    
    def validate_dependency_order(self, resource_ids: List[int]) -> Dict[str, Any]:
        """Validate resources can be applied in dependency order"""
        ...


class IntegrationValidationService(ValidationService, Protocol):
    """Service protocol for integration validation"""
    
    def validate_kubernetes_connectivity(self, fabric_id: int) -> Dict[str, Any]:
        """Validate Kubernetes cluster connectivity"""
        ...
    
    def validate_git_connectivity(self, repo_id: int) -> Dict[str, Any]:
        """Validate Git repository connectivity"""
        ...
    
    def validate_github_integration(self, repo_id: int) -> Dict[str, Any]:
        """Validate GitHub integration is working"""
        ...
    
    def validate_webhook_configuration(self, webhook_id: str) -> Dict[str, Any]:
        """Validate webhook configuration"""
        ...
    
    def validate_credentials(self, credential_type: str, 
                           credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Validate stored credentials are valid"""
        ...
    
    def validate_permissions(self, user_id: int, fabric_id: int,
                           operation: str) -> Dict[str, Any]:
        """Validate user has required permissions"""
        ...
    
    def validate_api_endpoints(self, fabric_id: int) -> Dict[str, Any]:
        """Validate all API endpoints are accessible"""
        ...


class ComplianceValidationService(ValidationService, Protocol):
    """Service protocol for compliance validation"""
    
    def validate_security_policies(self, fabric_id: int) -> Dict[str, Any]:
        """Validate configuration meets security policies"""
        ...
    
    def validate_naming_conventions(self, resource_id: int) -> Dict[str, Any]:
        """Validate resource naming follows conventions"""
        ...
    
    def validate_tagging_compliance(self, resource_id: int) -> Dict[str, Any]:
        """Validate resource has required tags/labels"""
        ...
    
    def validate_environment_isolation(self, fabric_id: int) -> Dict[str, Any]:
        """Validate environment isolation is maintained"""
        ...
    
    def validate_change_approval(self, resource_id: int, 
                               user_id: int) -> Dict[str, Any]:
        """Validate change has required approvals"""
        ...
    
    def generate_compliance_report(self, fabric_id: int) -> Dict[str, Any]:
        """Generate comprehensive compliance report"""
        ...
    
    def get_compliance_violations(self, fabric_id: int) -> List[Dict[str, Any]]:
        """Get list of current compliance violations"""
        ...