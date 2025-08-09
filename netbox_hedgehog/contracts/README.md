# NetBox Hedgehog Plugin Contracts

Machine-readable component contracts for all NetBox Hedgehog Plugin models, services, and APIs.

## Overview

This directory contains comprehensive contracts that enable agents and external systems to understand and interact with the NetBox Hedgehog Plugin without reverse-engineering Django models or API implementations.

## Structure

```
contracts/
├── __init__.py                 # Main contract exports
├── README.md                  # This file
├── examples.py                # Example data and test scenarios
├── validate.py                # Contract validation script
├── models/                    # Pydantic model schemas
│   ├── __init__.py
│   ├── core.py               # Core models (Fabric, Git, BaseCRD)
│   ├── gitops.py             # GitOps models (Resource, History, Alerts)
│   ├── vpc_api.py            # VPC API models (VPC, External, etc.)
│   └── wiring_api.py         # Wiring API models (Connection, Switch, etc.)
├── services/                  # typing.Protocol service interfaces
│   ├── __init__.py
│   ├── crud.py               # CRUD operations for all models
│   ├── gitops.py             # GitOps workflow operations
│   ├── sync.py               # Synchronization operations
│   └── validation.py         # Validation services
└── openapi/                   # OpenAPI 3.0 specifications
    ├── __init__.py
    ├── main.py               # Complete OpenAPI spec generator
    ├── models.py             # Model schema definitions
    ├── endpoints.py          # API endpoint definitions
    └── errors.py             # Error response schemas
```

## Model Schemas

All 17 plugin models have complete Pydantic schema definitions:

### Core Models
- **HedgehogFabric**: Main fabric management entity
- **GitRepository**: Git repository configuration and authentication
- **BaseCRD**: Base class for Kubernetes Custom Resource Definitions

### GitOps Models  
- **HedgehogResource**: GitOps resource state management
- **StateTransitionHistory**: Resource state change tracking
- **ReconciliationAlert**: Drift detection and reconciliation alerts

### VPC API Models
- **VPC**: Virtual Private Cloud network isolation
- **External**: External systems connected to fabric
- **ExternalAttachment**: Attachments of external systems to switches
- **ExternalPeering**: Peering between VPCs and external systems
- **IPv4Namespace**: IPv4 address namespace management
- **VPCAttachment**: Workload attachments to VPCs
- **VPCPeering**: Peering between different VPCs

### Wiring API Models
- **Connection**: Logical/physical device connections
- **Server**: Server connection configuration  
- **Switch**: Network switches with roles and configuration
- **SwitchGroup**: Switch groupings for redundancy
- **VLANNamespace**: VLAN range management

## Service Interfaces

typing.Protocol definitions provide type-safe interfaces for all operations:

### CRUD Services
- Standard create, read, update, delete operations for all models
- Type-safe method signatures with proper return types
- Consistent error handling patterns

### GitOps Services
- Resource state management and transitions
- Drift detection and reconciliation
- Workflow orchestration

### Synchronization Services
- Kubernetes cluster synchronization
- Git repository synchronization
- GitHub integration and webhooks

### Validation Services
- YAML validation and parsing
- Kubernetes spec validation
- Business logic validation
- Cross-resource validation

## OpenAPI Specification

Complete OpenAPI 3.0 specification includes:

- All API endpoints with request/response schemas
- Authentication requirements (API token, Bearer token)
- Structured error responses with error codes
- Request/response examples
- Parameter validation

## Usage Examples

### Using Model Schemas

```python
from netbox_hedgehog.contracts.models import HedgehogFabricSchema

# Validate data
fabric_data = {
    "name": "production-fabric",
    "description": "Production network fabric",
    "status": "ACTIVE"
}

fabric = HedgehogFabricSchema(**fabric_data)
print(fabric.json())

# Export JSON schema
schema = HedgehogFabricSchema.model_json_schema()
```

### Using Service Interfaces

```python
from netbox_hedgehog.contracts.services import FabricService
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type hints for agents/IDEs
    fabric_service: FabricService

# Type-safe operations
fabric = fabric_service.create({
    "name": "new-fabric",
    "kubernetes_server": "https://k8s.example.com:6443"
})

connection_test = fabric_service.test_kubernetes_connection(fabric["id"])
```

### Generating OpenAPI Specification

```python
from netbox_hedgehog.contracts.openapi import generate_openapi_spec
import json

spec = generate_openapi_spec()
with open('openapi.json', 'w') as f:
    json.dump(spec, f, indent=2)
```

## Validation

The contracts include comprehensive validation to ensure completeness and consistency:

```bash
# Run validation
cd netbox_hedgehog/contracts
python validate.py

# Export examples and OpenAPI spec
python validate.py --export-examples --export-openapi --output-dir ./exports

# Strict mode (treat warnings as errors)
python validate.py --strict
```

### Validation Features

- **Schema Validation**: Ensures all Pydantic schemas are well-formed
- **Completeness Check**: Verifies all models have examples and documentation
- **OpenAPI Validation**: Validates OpenAPI specification structure
- **Relationship Validation**: Checks model relationship consistency
- **Example Validation**: Tests example data against schemas

## Agent Integration

These contracts enable agents to:

1. **Understand Models**: Complete field definitions with types and validation
2. **Use Services**: Type-safe service interfaces with clear contracts
3. **Call APIs**: OpenAPI specifications for REST endpoints
4. **Handle Errors**: Structured error responses with error codes
5. **Test Operations**: Example data and test scenarios

### Integration with Error Handling System (Issue #21)

The contracts integrate seamlessly with the comprehensive error handling system:

```python
from netbox_hedgehog.contracts.models import HedgehogFabricSchema
from netbox_hedgehog.contracts.services import FabricService
from netbox_hedgehog.specifications.error_handling import detect_error_type, execute_recovery_workflow

class ErrorAwareFabricService:
    """Fabric service with comprehensive error handling"""
    
    def create_fabric(self, fabric_data: dict) -> HedgehogFabricSchema:
        """Create fabric with error handling and recovery"""
        try:
            # Validate using contract schema
            fabric_schema = HedgehogFabricSchema(**fabric_data)
            
            # Execute creation
            fabric = self._create_fabric_impl(fabric_schema.dict())
            
            return HedgehogFabricSchema.from_orm(fabric)
            
        except Exception as e:
            # Detect specific error type
            error_info = detect_error_type(e, {
                'operation': 'fabric_creation',
                'fabric_data': fabric_data
            })
            
            if error_info.get('detected'):
                # Try automated recovery
                recovery_result = execute_recovery_workflow(
                    error_info['code'],
                    error_info.get('context', {})
                )
                
                if recovery_result.success:
                    # Retry after recovery
                    return self.create_fabric(fabric_data)
            
            # Re-raise with structured error
            raise FabricCreationError(
                code=error_info.get('code', 'HH-VAL-999'),
                message=error_info.get('message', str(e)),
                details=error_info.get('context', {})
            )
```

**Error Code Integration**:
- Contract validation errors map to **HH-VAL-xxx** error codes
- Service authentication errors use **HH-AUTH-xxx** codes  
- Kubernetes operations leverage **HH-K8S-xxx** error handling
- Git operations integrate **HH-GIT-xxx** recovery workflows
- State transitions use **HH-STATE-xxx** error detection

## CI/CD Integration

The validation script can be integrated into CI/CD pipelines:

```yaml
# .github/workflows/validate-contracts.yml
name: Validate Contracts
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install pydantic
      - name: Validate contracts
        run: python netbox_hedgehog/contracts/validate.py --strict
```

## Contract Quality Requirements

All contracts must meet these quality standards:

✅ **Machine-Readable**: Parseable by agents without human interpretation  
✅ **Complete**: Cover all 17 models with full field specifications  
✅ **Consistent**: Follow consistent patterns across all contracts  
✅ **Validated**: Pass all automated validation checks  
✅ **Documented**: Include examples and clear descriptions  
✅ **Type-Safe**: Provide proper type hints and validation  
✅ **Error-Handled**: Define all error conditions and responses  

## Extending Contracts

When adding new models or services:

1. Add Pydantic schema to appropriate `models/` file
2. Add service interface to appropriate `services/` file  
3. Update OpenAPI specification in `openapi/` files
4. Add examples to `examples.py`
5. Run validation: `python validate.py --strict`
6. Update this README if needed

## Integration with Existing Code

These contracts complement but do not replace the existing Django models and API views. They provide a machine-readable interface layer that agents can use to understand and interact with the plugin.

The contracts are designed to stay synchronized with the actual implementation through:

- Regular validation in CI/CD
- Example data that matches real usage patterns
- OpenAPI specifications that match actual API behavior
- Service interfaces that reflect actual service capabilities

This dual approach ensures agents have reliable contracts while maintaining the flexibility of the underlying Django implementation.