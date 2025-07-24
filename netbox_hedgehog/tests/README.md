# HNP End-to-End Testing Framework

## Overview

This testing framework verifies that all GUI functionality actually works from the user's perspective, not just that code executes without errors. Every test is designed to simulate real user interactions and validate the complete workflow.

## Critical Testing Philosophy

**NEVER report that something is working unless you have verified it works in the actual GUI.**

## Test Structure

### Core Test Files

- `test_gui_integration.py` - GUI integration tests for all workflows
- `test_api_endpoints.py` - API endpoint testing that supports GUI
- `test_templates.py` - Template rendering and display tests
- `test_e2e_workflows.py` - Complete end-to-end user journey tests

### Utilities

- `utils/gui_test_client.py` - Helper for simulating GUI interactions
- `utils/gitops_test_helpers.py` - GitOps directory manipulation utilities
- `utils/hckc_test_helpers.py` - HCKC cluster testing utilities
- `utils/test_data_factory.py` - Generate test CRs and fabrics

## Running Tests

### Full Test Suite
```bash
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py test netbox_hedgehog.tests
```

### Specific Test Classes
```bash
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py test netbox_hedgehog.tests.test_gui_integration.GUIIntegrationTests
```

### With Verbose Output
```bash
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py test netbox_hedgehog.tests --verbosity=2
```

## Test Categories

### 1. Fabric Onboarding Tests
- New fabric creation through GUI
- GitOps repository connection
- CR discovery and synchronization
- All 12 CR types displayed correctly

### 2. CRUD Operation Tests
For each of the 12 CR types:
- **Create**: GUI form → YAML file creation
- **Read**: List and detail view display
- **Update**: GUI edit → YAML file update
- **Delete**: GUI delete → YAML file removal

### 3. HCKC Integration Tests
- Cluster connection via kubectl
- CR discovery from cluster
- Desired vs actual state comparison
- Sync status indicator accuracy

## Authentication Setup

Tests use the NetBox authentication token located at:
`/home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox.token`

## Test Data

### GitOps Test Repository
- Repository: `https://github.com/afewell-hh/gitops-test-1`
- Local clone: `/tmp/gitops-test-1`
- Contains sample CRs for all 12 types

### HCKC Cluster
- Access via `~/.kube/config`
- Test commands: `kubectl get nodes`, `kubectl get crds | grep hedgehog`

## Success Criteria

Tests pass only when:
1. ✅ All GUI pages load (200 status)
2. ✅ All data displays correctly 
3. ✅ All forms submit successfully
4. ✅ All CRUD operations work
5. ✅ GitOps files sync correctly
6. ✅ HCKC integration functions
7. ✅ Error handling works gracefully

## Debugging Failed Tests

### Check Container Logs
```bash
sudo docker logs netbox-docker-netbox-1 --tail 50
```

### Restart Container
```bash
sudo docker restart netbox-docker-netbox-1
sleep 30
```

### Test Database State
Use Django shell to inspect data:
```bash
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py shell
```

## CR Types Coverage

### VPC API (7 types)
1. VPC - Virtual Private Cloud definitions
2. External - External system connections  
3. ExternalAttachment - Attachments to external systems
4. ExternalPeering - Peering relationships with external systems
5. IPv4Namespace - IPv4 address space management
6. VPCAttachment - VPC attachment configurations
7. VPCPeering - VPC-to-VPC peering relationships

### Wiring API (5 types)
8. Connection - Physical/logical connection definitions
9. Switch - Switch device configurations
10. Server - Server device configurations  
11. VLANNamespace - VLAN namespace management
12. SwitchGroup - Logical groupings of switches

## Important Notes

- Tests create and clean up their own data
- Tests are isolated and can run in any order
- Tests fail fast on first error to prevent cascading failures
- All test data uses predictable naming for easy debugging
- Tests verify both positive and negative cases