# Current HNP Fabric Configuration Documentation

**Extraction Date**: August 2, 2025  
**Purpose**: Document current fabric for deletion/recreation testing  
**API Access**: Authenticated via NetBox token  

## Current Fabric Configuration (ID: 26)

### Basic Information
- **Name**: "Test Fabric for GitOps Initialization"
- **Description**: "Test fabric for complete GitOps initialization workflow"
- **Status**: "planned"
- **ID**: 26

### Kubernetes Configuration
- **Server**: "https://172.18.0.8:6443"
- **Namespace**: "default"
- **Token**: "eyJhbGciOiJSUzI1NiIsImtpZCI6IlhzaVN6Uy1GSk50X1FuU1NwTlE2MEhELWo0ZVNwblU0bWQ2eVNCVjJQRjAifQ..." (truncated)
- **CA Certificate**: "-----BEGIN CERTIFICATE-----..." (full cert in JSON)

### GitOps Configuration
- **Git Repository ID**: 6
- **GitOps Directory**: "gitops/hedgehog/fabric-1/"
- **Git Branch**: "main"
- **Git Path**: "hedgehog/"
- **Git Repository URL**: null (likely uses repository ID 6 configuration)

### Sync Configuration
- **Sync Enabled**: true
- **Sync Interval**: 300 seconds
- **Auto Sync Enabled**: true
- **Prune Enabled**: false
- **Self Heal Enabled**: true

### GitOps Settings
- **GitOps Tool**: "manual"
- **GitOps Initialized**: true
- **Archive Strategy**: "rename_with_extension"
- **Raw Directory Path**: "/var/lib/hedgehog/fabrics/Test Fabric for GitOps Initialization/gitops/raw"
- **Managed Directory Path**: "/var/lib/hedgehog/fabrics/Test Fabric for GitOps Initialization/gitops/managed"

### Current State
- **Connection Status**: "connected"
- **Sync Status**: "synced"
- **Drift Status**: "in_sync"
- **Drift Count**: 0
- **Last Sync**: "2025-08-01T21:46:20.745747Z"
- **Last Git Sync**: "2025-08-02T00:03:04.907965Z"

### Cached Counts (All Zero - Indicating No Ingestion)
- **Cached CRD Count**: 0
- **Cached VPC Count**: 0
- **Cached Connection Count**: 0
- **Connections Count**: 0
- **Servers Count**: 0
- **Switches Count**: 0
- **VPCs Count**: 0

## Critical Finding
**ALL CACHED COUNTS ARE ZERO** - This confirms that despite "sync_status": "synced", **NO ACTUAL INGESTION HAS OCCURRED**. This validates the user's assertion that the functionality is not working.

## Recreation Requirements for Testing

### 1. Delete Current Fabric
```bash
source /home/ubuntu/cc/hedgehog-netbox-plugin/.env
curl -X DELETE -H "Authorization: Token $NETBOX_TOKEN" http://localhost:8000/api/plugins/hedgehog/fabrics/26/
```

### 2. Recreation Data
```json
{
  "name": "Test Fabric for GitOps Initialization",
  "description": "Test fabric for complete GitOps initialization workflow", 
  "status": "planned",
  "kubernetes_server": "https://172.18.0.8:6443",
  "kubernetes_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IlhzaVN6Uy1GSk50X1FuU1NwTlE2MEhELWo0ZVNwblU0bWQ2eVNCVjJQRjAifQ.eyJhdWQiOlsiaHR0cHM6Ly9rdWJlcm5ldGVzLmRlZmF1bHQuc3ZjLmNsdXN0ZXIubG9jYWwiLCJrM3MiXSwiZXhwIjoxNzg1MTgxMjQ3LCJpYXQiOjE3NTM2NDUyNDcsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJkZWZhdWx0Iiwic2VydmljZWFjY291bnQiOnsibmFtZSI6ImhucC1zZXJ2aWNlLWFjY291bnQiLCJ1aWQiOiI1N2IyOGI1NC0wZDExLTQ1MjQtYjRlNC03Y2I0ZTc3ZWNjOGYifX0sIm5iZiI6MTc1MzY0NTI0Nywic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6aG5wLXNlcnZpY2UtYWNjb3VudCJ9.pm_z2DuJm8EgN8A9TmlXif1K6H2LKas4La0mDsUYfhfW6FrobS5RoGeZA0IJ7xZWqxZROuTL67LRhkGsYBRTOHu-R1KZU5tFD34NuE8v0l4Hg-6Zjpxx_QMT0G2XuQeh0916Ij1NcZvolkDbNjJIsNt0UwZLNaGAuL6E4XVZay908hO4p3RsM8kUqR_It-nsj_0Gynaq1MGlxizCHeAxNBThrnwwlUhd1qJY1fByR_nuIAWDpLCFlmqFg3rPCnsNR2ZJwEq69Zc_14Qmgtd3cQ0NACipw5hZVcJGyLLIP1ElLaKqmnRCdw_Fw8RbMRa_WxslabxTFAa3QjcQjafInA",
  "kubernetes_ca_cert": "-----BEGIN CERTIFICATE-----\nMIIBeDCCAR2gAwIBAgIBADAKBggqhkjOPQQDAjAjMSEwHwYDVQQDDBhrM3Mtc2Vy\ndmVyLWNhQDE3NTI2NTQ1NDkwHhcNMjUwNzE2MDgyOTA5WhcNMzUwNzE0MDgyOTA5\nWjAjMSEwHwYDVQQDDBhrM3Mtc2VydmVyLWNhQDE3NTI2NTQ1NDkwWTATBgcqhkjO\nPQIBBggqhkjOPQMBBwNCAATPoBn010uC3pyf4/MftvOCuWO9u4qWKI0A0ROHPBbl\nkM+lz825iCUdaykgBlYzb68jh7WQVYUaIls1JbsWbgTwo0IwQDAOBgNVHQ8BAf8E\nBAMCAqQwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUO4X2MW9v8ao6n2vGst12\n26AmnGYwCgYIKoZIzj0EAwIDSQAwRgIhAN5lHyHe9LPZhxYcZUFg5JnsxIxrCczr\nUcRXrF7otqD7AiEA4gCPALLHtZ9cl40nJCy8wzGL5TJNiIKCiSTqusWF4o8=\n-----END CERTIFICATE-----\n",
  "kubernetes_namespace": "default",
  "sync_enabled": true,
  "sync_interval": 300,
  "gitops_directory": "gitops/hedgehog/fabric-1/",
  "git_repository": 6,
  "git_branch": "main"
}
```

## Test Plan
1. **Document current GitHub state** (files in raw/, empty managed/)
2. **Delete fabric** (clean slate)
3. **Recreate fabric** (via API simulating GUI)
4. **Trigger sync** 
5. **Validate GitHub changes** (files moved to managed/, raw/ empty)

## Expected Results After Fix
- **Cached CRD Count**: 48 (26 connections + 10 servers + 7 switches + 3 switchgroups + 2 vpcs)
- **Raw Directory**: Empty (files deleted after ingestion)  
- **Managed Directory**: 48 individual YAML files in appropriate subdirectories
- **GitHub Repository**: Live repository shows processed files structure

## Current Problem Confirmed
The fabric shows "synced" status but has zero cached counts, proving that **NO FILE INGESTION OCCURRED** despite the fix attempt.