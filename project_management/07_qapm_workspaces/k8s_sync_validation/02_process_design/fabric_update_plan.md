# Fabric Update Implementation Plan

**Date**: July 31, 2025  
**Fabric ID**: 26  
**Purpose**: Update fabric record with Kubernetes cluster configuration for synchronization capability

## Executive Summary

The fabric "Test Fabric for GitOps Initialization" has complete GitOps configuration but is missing Kubernetes cluster connection parameters. This plan details the exact steps to add K8s configuration and validate synchronization capability.

## Current State Analysis

### ✅ Already Configured
- GitOps integration with GitRepository ID 6
- GitOps directory: "gitops/hedgehog/fabric-1/"
- Git synchronization working (last sync: 2025-07-30T22:54:37Z)
- Fabric structure and relationships established

### ❌ Missing Configuration
- Kubernetes API server URL
- Kubernetes authentication token  
- Kubernetes CA certificate
- Connection validation

## Implementation Steps

### Phase 1: Prepare Update Data

#### Step 1.1: Extract Environment Variables
```bash
# Source values from .env file:
KUBERNETES_SERVER="https://172.18.0.8:6443"
KUBERNETES_TOKEN="eyJhbGciOiJSUzI1NiIsImtpZCI6IlhzaVN6Uy1GSk50X1FuU1NwTlE2MEhELWo0ZVNwblU0bWQ2eVNCVjJQRjAifQ..."
KUBERNETES_CA_CERT="-----BEGIN CERTIFICATE-----\nMIIBeDCCAR2gAwIBAgIBADAKBggqhkjOPQQDAjAjMSEwHwYDVQQDDBhrM3Mtc2VydmVyLWNhQDE3NTI2NTQ1NDkwHhcNMjUwNzE2MDgyOTA5WhcNMzUwNzE0MDgyOTA5WjAjMSEwHwYDVQQDDBhrM3Mtc2VydmVyLWNhQDE3NTI2NTQ1NDkwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAATPoBn010uC3pyf4/MftvOCuWO9u4qWKI0A0ROHPBblkM+lz825iCUdaykgBlYzb68jh7WQVYUaIls1JbsWbgTwo0IwQDAOBgNVHQ8BAf8EBAMCAqQwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUO4X2MW9v8ao6n2vGst1226AmnGYwCgYIKoZIzj0EAwIDSQAwRgIhAN5lHyHe9LPZhxYcZUFg5JnsxIxrCczrUcRXrF7otqD7AiEA4gCPALLHtZ9cl40nJCy8wzGL5TJNiIKCiSTqusWF4o8=\n-----END CERTIFICATE-----"
```

#### Step 1.2: Prepare API Update Payload
```json
{
    "kubernetes_server": "https://172.18.0.8:6443",
    "kubernetes_token": "[FULL_JWT_TOKEN]",
    "kubernetes_ca_cert": "[FULL_CA_CERTIFICATE]",
    "kubernetes_namespace": "default"
}
```

### Phase 2: Update Fabric Configuration

#### Step 2.1: Execute API Update
```bash
curl -X PATCH \
  -H "Authorization: Token ced6a3e0a978db0ad4de39cd66af4868372d7dd0" \
  -H "Content-Type: application/json" \
  -d '[UPDATE_PAYLOAD]' \
  "http://localhost:8000/api/plugins/hedgehog/fabrics/26/"
```

#### Step 2.2: Verify Configuration Saved
- Confirm kubernetes_server field populated
- Confirm kubernetes_token field populated  
- Confirm kubernetes_ca_cert field populated
- Verify no API errors returned

### Phase 3: Validate Kubernetes Connectivity

#### Step 3.1: Test Connection
Execute connection test through HNP functionality:
- Fabric model `get_kubernetes_config()` method should return valid config
- Connection test should succeed with authentication
- TLS certificate validation should pass

#### Step 3.2: Update Connection Status
Expected automatic updates:
- `connection_status`: "unknown" → "connected"
- `connection_error`: Should remain empty if successful
- Error handling if connection fails

### Phase 4: Execute Initial Kubernetes Sync

#### Step 4.1: Trigger CRD Discovery
Execute sync operation to discover existing CRDs:
- Call `sync_actual_state()` method on fabric
- Should enumerate Hedgehog CRDs in cluster
- Should populate HedgehogResource records

#### Step 4.2: Validate Sync Results
Expected outcomes:
- CRD counts updated (cached_crd_count, vpcs_count, etc.)
- HedgehogResource records created for cluster CRDs
- Sync timestamp updated
- No sync errors

### Phase 5: Enable Real-time Monitoring

#### Step 5.1: Activate Watch Service
- Verify `watch_enabled` is true (already set)
- `watch_status` should change from "inactive" to "active"
- Watch service should begin monitoring CRD changes

#### Step 5.2: Test Watch Functionality
- Generate test CRD change in cluster
- Verify watch event received and processed
- Confirm `watch_event_count` increments

## Success Criteria

### Phase 1 Success
- [x] Environment variables extracted
- [x] Update payload prepared
- [x] API endpoint identified

### Phase 2 Success
- [ ] Fabric record updated successfully
- [ ] All K8s fields populated
- [ ] No API errors during update

### Phase 3 Success  
- [ ] Kubernetes connection test passes
- [ ] connection_status = "connected"
- [ ] TLS certificate validation works
- [ ] Authentication successful

### Phase 4 Success
- [ ] CRD discovery completes successfully
- [ ] CRD counts populated with actual values
- [ ] HedgehogResource records created
- [ ] sync_status updated appropriately

### Phase 5 Success
- [ ] Watch service activated
- [ ] Real-time monitoring functional
- [ ] Event processing working

## Risk Assessment

### High Risk Items
1. **Network Connectivity**: Docker network access to K8s cluster
2. **Certificate Validation**: Self-signed cert handling
3. **Token Expiration**: JWT token valid until 2026
4. **API Compatibility**: K8s API version compatibility

### Mitigation Strategies
1. **Network Issues**: Test connectivity before configuration
2. **Certificate Issues**: Verify certificate format and encoding
3. **Authentication Issues**: Validate token format and permissions
4. **API Issues**: Handle gracefully with clear error messages

## Rollback Plan

### If Configuration Fails
1. Restore original empty K8s fields
2. Reset connection_status to "unknown"
3. Clear any error messages
4. Maintain GitOps functionality

### If Sync Fails
1. Keep K8s configuration (if connection works)
2. Document sync errors in sync_error field
3. Maintain GitOps-only operation
4. Retry sync after resolving issues

## Validation Commands

### Pre-Update Validation
```bash
# Verify current state
curl -H "Authorization: Token [TOKEN]" \
  "http://localhost:8000/api/plugins/hedgehog/fabrics/26/" | jq '.kubernetes_server'
```

### Post-Update Validation  
```bash
# Verify configuration applied
curl -H "Authorization: Token [TOKEN]" \
  "http://localhost:8000/api/plugins/hedgehog/fabrics/26/" | jq '.kubernetes_server'

# Check connection status
curl -H "Authorization: Token [TOKEN]" \
  "http://localhost:8000/api/plugins/hedgehog/fabrics/26/" | jq '.connection_status'

# Verify CRD counts
curl -H "Authorization: Token [TOKEN]" \
  "http://localhost:8000/api/plugins/hedgehog/fabrics/26/" | jq '.cached_crd_count'
```

## Expected Timeline

- **Phase 1**: 5 minutes (preparation)
- **Phase 2**: 5 minutes (API update)  
- **Phase 3**: 10 minutes (connection validation)
- **Phase 4**: 15 minutes (initial sync)
- **Phase 5**: 10 minutes (watch activation)

**Total Estimated Time**: 45 minutes

## Implementation Notes

### Special Considerations
- Development environment with Docker networking
- K3s cluster with self-signed certificates
- Service account token with long expiration
- Existing GitOps configuration must be preserved

### Testing Strategy
- Incremental validation at each phase
- Rollback capability at each step
- Comprehensive error logging
- Success criteria verification

### Documentation Requirements
- Record all configuration values applied
- Document any issues encountered
- Capture before/after state comparison
- Note performance impact of sync operations