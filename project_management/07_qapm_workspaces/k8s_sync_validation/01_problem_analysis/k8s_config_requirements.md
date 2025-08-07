# Kubernetes Configuration Requirements

**Analysis Date**: July 31, 2025  
**Purpose**: Define required Kubernetes configuration fields and values for fabric synchronization  

## Required Field Mappings

### Environment Variables → Fabric Fields

| Environment Variable | Fabric Field | Current Value | Required Action |
|---------------------|--------------|---------------|-----------------|
| `TEST_FABRIC_K8S_API_SERVER` | `kubernetes_server` | "" (empty) | ✅ Update |
| `TEST_FABRIC_K8S_TOKEN` | `kubernetes_token` | "" (empty) | ✅ Update |
| `TEST_FABRIC_K8S_API_SERVER_CA` | `kubernetes_ca_cert` | "" (empty) | ✅ Update |
| Default | `kubernetes_namespace` | "default" | ✅ Keep current |

### Specific Values Required

#### 1. Kubernetes Server URL
- **Field**: `kubernetes_server`  
- **Value**: `https://172.18.0.8:6443`
- **Purpose**: K8s API endpoint for cluster communication
- **Validation**: Must be accessible URL format

#### 2. Kubernetes Authentication Token  
- **Field**: `kubernetes_token`
- **Value**: JWT service account token from TEST_FABRIC_K8S_TOKEN
- **Purpose**: Authentication for K8s API calls
- **Security**: Should be stored securely in database
- **Length**: ~1400+ characters (JWT format)

#### 3. Kubernetes CA Certificate
- **Field**: `kubernetes_ca_cert`  
- **Value**: X.509 certificate from TEST_FABRIC_K8S_API_SERVER_CA
- **Purpose**: SSL/TLS verification for secure cluster communication
- **Format**: PEM format certificate block
- **Content**: Starts with "-----BEGIN CERTIFICATE-----"

#### 4. Kubernetes Namespace
- **Field**: `kubernetes_namespace`
- **Current Value**: "default" 
- **Action**: Keep existing value
- **Purpose**: Default namespace for CRD operations

## Additional Configuration Requirements

### Connection Validation
- **connection_status**: Should be updated to "connected" after successful validation
- **connection_error**: Should be cleared after successful connection
- **last_sync**: Should be updated after successful K8s sync

### Sync Status Fields
- **sync_status**: Should move from "synced" to appropriate status after K8s sync
- **sync_error**: Should capture any K8s synchronization errors
- **sync_enabled**: Currently true, should remain enabled

### Watch Configuration
- **watch_enabled**: Currently true, ready for real-time monitoring
- **watch_status**: Currently "inactive", should become "active" after K8s config
- **watch_crd_types**: Currently empty (will watch all CRD types)

## Security Considerations

### Token Storage
- Service account token should be stored securely in database
- Consider encryption at rest for sensitive credentials
- Token has expiration date: exp: 1785181247 (year 2026)

### Certificate Validation
- CA certificate enables secure TLS communication
- Self-signed certificate for K3s development cluster
- Certificate subject: k3s-server-ca@1752654549

### Network Access
- K8s API server at 172.18.0.8:6443 (Docker network)
- Requires network connectivity from NetBox container
- May need special SSL verification handling for development setup

## Expected Outcomes After Configuration

### Immediate Results
1. **Connection Status**: Should change from "unknown" to "connected"
2. **K8s Validation**: `get_kubernetes_config()` method should return valid config
3. **API Access**: Kubernetes client should successfully authenticate

### Sync Capabilities Enabled
1. **CRD Fetching**: `sync_actual_state()` method should work
2. **Bidirectional Sync**: Git ↔ K8s synchronization possible
3. **Real-time Monitoring**: Watch service can be activated
4. **Drift Detection**: Can compare Git desired state vs K8s actual state

### CRD Count Updates
- **cached_crd_count**: Should populate with actual CRD count from cluster
- **vpcs_count**: Should show VPC CRD count
- **connections_count**: Should show Connection CRD count  
- **switches_count**: Should show Switch CRD count

## Validation Criteria

### Connection Test Success
- API call to K8s cluster returns successful response
- Authentication accepted by cluster
- TLS certificate validation passes

### CRD Discovery Success
- Can enumerate Hedgehog CRDs in cluster
- Can retrieve CRD specifications and instances
- CRD counts match actual cluster state

### Watch Readiness
- Can establish watch connection to K8s API
- Can receive CRD change events
- Event processing pipeline functional

## Risk Mitigation

### Development Environment Considerations
- Docker network addressing (172.18.0.8)
- Self-signed certificates requiring special handling
- K3s cluster specific configurations

### Error Handling
- Graceful degradation if K8s unavailable
- Clear error messages for connection issues
- Fallback to GitOps-only mode if needed

### Testing Strategy
- Validate connection before saving configuration
- Test CRD enumeration after configuration
- Confirm watch capability before enabling