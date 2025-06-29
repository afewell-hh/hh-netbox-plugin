# Hedgehog NetBox Plugin - API Reference

This document provides detailed API reference for developers and automation scripts.

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Fabric Management API](#fabric-management-api)
4. [VPC Management API](#vpc-management-api)
5. [Infrastructure API](#infrastructure-api)
6. [Bulk Operations API](#bulk-operations-api)
7. [Status and Monitoring API](#status-and-monitoring-api)
8. [Code Examples](#code-examples)

---

## Overview

The Hedgehog NetBox Plugin provides REST API endpoints for programmatic access to all plugin functionality. The API follows NetBox conventions and provides both read and write operations.

### Base URL

All API endpoints are prefixed with:
```
https://your-netbox-instance/api/plugins/hedgehog/
```

### Response Format

All responses use JSON format with consistent structure:

```json
{
  "count": 25,
  "next": "https://netbox/api/plugins/hedgehog/vpcs/?offset=20",
  "previous": null,
  "results": [...]
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## Authentication

### Token Authentication

```bash
curl -H "Authorization: Token YOUR_API_TOKEN" \
     https://netbox/api/plugins/hedgehog/fabrics/
```

### Session Authentication

```python
import requests

session = requests.Session()
session.headers.update({'Authorization': 'Token YOUR_API_TOKEN'})
```

---

## Fabric Management API

### List Fabrics

**Endpoint**: `GET /api/plugins/hedgehog/fabrics/`

**Parameters**:
- `limit`: Number of results per page (default: 50)
- `offset`: Starting position for pagination
- `name`: Filter by fabric name
- `sync_status`: Filter by sync status

**Example Request**:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "https://netbox/api/plugins/hedgehog/fabrics/?sync_status=synced"
```

**Example Response**:
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "url": "https://netbox/api/plugins/hedgehog/fabrics/1/",
      "name": "production-dc1",
      "description": "Production datacenter 1",
      "sync_status": "synced",
      "last_sync": "2025-06-29T12:34:56.789Z",
      "cluster_info": {
        "version": "v1.32.4+k3s1",
        "nodes": 7,
        "namespace_count": 15
      },
      "created": "2025-06-28T10:00:00.000Z",
      "last_updated": "2025-06-29T12:34:56.789Z"
    }
  ]
}
```

### Create Fabric

**Endpoint**: `POST /api/plugins/hedgehog/fabrics/`

**Request Body**:
```json
{
  "name": "staging-fabric",
  "description": "Staging environment",
  "kubeconfig_yaml": "apiVersion: v1\nkind: Config\n..."
}
```

**Response**: Returns created fabric object with ID

### Get Fabric Details

**Endpoint**: `GET /api/plugins/hedgehog/fabrics/{id}/`

**Response**: Single fabric object with full details

### Update Fabric

**Endpoint**: `PATCH /api/plugins/hedgehog/fabrics/{id}/`

**Request Body**: Partial fabric object with fields to update

### Delete Fabric

**Endpoint**: `DELETE /api/plugins/hedgehog/fabrics/{id}/`

**Response**: 204 No Content on success

### Fabric Actions

#### Test Connection

**Endpoint**: `POST /api/plugins/hedgehog/fabrics/{id}/test-connection/`

**Response**:
```json
{
  "success": true,
  "message": "Connection successful",
  "cluster_info": {
    "version": "v1.32.4+k3s1",
    "nodes": 7
  }
}
```

#### Sync Fabric

**Endpoint**: `POST /api/plugins/hedgehog/fabrics/{id}/sync/`

**Response**:
```json
{
  "success": true,
  "message": "Sync completed",
  "imported_resources": {
    "switches": 7,
    "connections": 26,
    "vpcs": 3
  }
}
```

---

## VPC Management API

### List VPCs

**Endpoint**: `GET /api/plugins/hedgehog/vpcs/`

**Parameters**:
- `fabric`: Filter by fabric ID
- `kubernetes_status`: Filter by status
- `name`: Filter by VPC name

**Example Request**:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "https://netbox/api/plugins/hedgehog/vpcs/?fabric=1&kubernetes_status=applied"
```

**Example Response**:
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "url": "https://netbox/api/plugins/hedgehog/vpcs/1/",
      "name": "web-prod",
      "description": "Production web tier",
      "fabric": {
        "id": 1,
        "name": "production-dc1",
        "url": "https://netbox/api/plugins/hedgehog/fabrics/1/"
      },
      "kubernetes_status": "applied",
      "subnets_config": {
        "web": {
          "subnet": "10.100.10.0/24",
          "gateway": "10.100.10.1",
          "vlan": 1110,
          "dhcp": {"enable": true}
        }
      },
      "ipv4_namespace": null,
      "vlan_namespace": null,
      "managed_by_netbox": true,
      "last_applied": "2025-06-29T12:30:00.000Z"
    }
  ]
}
```

### Create VPC

**Endpoint**: `POST /api/plugins/hedgehog/vpcs/`

**Request Body**:
```json
{
  "name": "api-staging",
  "description": "Staging API environment",
  "fabric": 1,
  "subnets_config": {
    "api": {
      "subnet": "10.101.20.0/24",
      "gateway": "10.101.20.1",
      "vlan": 1120,
      "dhcp": {"enable": true}
    }
  },
  "apply_immediately": true
}
```

### VPC Actions

#### Apply to Cluster

**Endpoint**: `POST /api/plugins/hedgehog/vpcs/{id}/apply/`

**Response**:
```json
{
  "success": true,
  "message": "VPC applied successfully",
  "kubernetes_uid": "abc123-def456-ghi789"
}
```

#### Get VPC Status

**Endpoint**: `GET /api/plugins/hedgehog/vpcs/{id}/status/`

**Response**:
```json
{
  "kubernetes_status": "applied",
  "last_applied": "2025-06-29T12:30:00.000Z",
  "cluster_status": {
    "ready": true,
    "conditions": [
      {
        "type": "Ready",
        "status": "True",
        "message": "VPC is operational"
      }
    ]
  }
}
```

---

## Infrastructure API

### Switches

#### List Switches

**Endpoint**: `GET /api/plugins/hedgehog/switches/`

**Parameters**:
- `fabric`: Filter by fabric ID
- `role`: Filter by switch role
- `kubernetes_status`: Filter by status

**Example Response**:
```json
{
  "count": 7,
  "results": [
    {
      "id": 1,
      "name": "spine-1",
      "fabric": {
        "id": 1,
        "name": "production-dc1"
      },
      "role": "spine",
      "asn": 65100,
      "profile": "vs",
      "kubernetes_status": "applied",
      "ip": "192.168.1.10",
      "protocol_ip": "10.10.10.1",
      "vtep_ip": "10.20.10.1"
    }
  ]
}
```

### Connections

#### List Connections

**Endpoint**: `GET /api/plugins/hedgehog/connections/`

**Parameters**:
- `fabric`: Filter by fabric ID
- `connection_type`: Filter by connection type

**Example Response**:
```json
{
  "count": 26,
  "results": [
    {
      "id": 1,
      "name": "spine1-leaf1",
      "fabric": {
        "id": 1,
        "name": "production-dc1"
      },
      "connection_type": "unbundled",
      "kubernetes_status": "applied",
      "connection_config": {
        "links": [
          {
            "switch": "spine-1",
            "port": "Ethernet1"
          },
          {
            "switch": "leaf-1", 
            "port": "Ethernet49"
          }
        ]
      }
    }
  ]
}
```

### VLAN Namespaces

#### List VLAN Namespaces

**Endpoint**: `GET /api/plugins/hedgehog/vlan-namespaces/`

**Example Response**:
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "name": "production",
      "fabric": {
        "id": 1,
        "name": "production-dc1"
      },
      "ranges_config": [
        {"from": 1000, "to": 1999},
        {"from": 3000, "to": 3099}
      ],
      "kubernetes_status": "applied"
    }
  ]
}
```

---

## Bulk Operations API

### VPC Bulk Operations

**Endpoint**: `POST /api/plugins/hedgehog/vpcs/bulk-actions/`

**Request Body**:
```json
{
  "action": "apply",
  "vpcs": [1, 2, 3, 4]
}
```

**Response**:
```json
{
  "success": true,
  "message": "Applied 3 of 4 VPCs successfully",
  "results": {
    "successful": [1, 2, 3],
    "failed": [4],
    "errors": {
      "4": "VLAN conflict detected"
    }
  }
}
```

### Fabric Bulk Operations

**Endpoint**: `POST /api/plugins/hedgehog/fabrics/bulk-actions/`

**Available Actions**:
- `test_connection`: Test connectivity for multiple fabrics
- `sync`: Sync multiple fabrics
- `delete`: Delete multiple fabrics

**Request Body**:
```json
{
  "action": "sync",
  "fabrics": [1, 2]
}
```

### Switch Bulk Operations

**Endpoint**: `POST /api/plugins/hedgehog/switches/bulk-actions/`

**Available Actions**:
- `apply`: Apply switches to clusters
- `update_role`: Update role for multiple switches
- `delete`: Delete multiple switches

**Request Body**:
```json
{
  "action": "update_role",
  "switches": [1, 2, 3],
  "new_role": "spine"
}
```

---

## Status and Monitoring API

### Cluster Status

**Endpoint**: `GET /api/plugins/hedgehog/fabrics/{id}/cluster-status/`

**Response**:
```json
{
  "cluster_info": {
    "version": "v1.32.4+k3s1",
    "nodes": 7,
    "ready_nodes": 7,
    "namespace_count": 15
  },
  "resource_counts": {
    "vpcs": 5,
    "switches": 7,
    "connections": 26,
    "servers": 12
  },
  "health_status": "healthy",
  "last_check": "2025-06-29T13:00:00.000Z"
}
```

### Resource Statistics

**Endpoint**: `GET /api/plugins/hedgehog/statistics/`

**Response**:
```json
{
  "fabrics": {
    "total": 3,
    "healthy": 3,
    "syncing": 0,
    "error": 0
  },
  "vpcs": {
    "total": 15,
    "applied": 12,
    "pending": 2,
    "error": 1
  },
  "switches": {
    "total": 21,
    "by_role": {
      "spine": 9,
      "server-leaf": 9,
      "border-leaf": 3
    }
  },
  "connections": {
    "total": 78,
    "by_type": {
      "unbundled": 45,
      "bundled": 20,
      "mclag": 10,
      "eslag": 3
    }
  }
}
```

---

## Code Examples

### Python Client Example

```python
import requests
import json

class HedgehogAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        })
    
    def list_fabrics(self):
        """List all fabrics"""
        response = self.session.get(f'{self.base_url}/api/plugins/hedgehog/fabrics/')
        response.raise_for_status()
        return response.json()
    
    def create_vpc(self, name, fabric_id, template_config):
        """Create a new VPC"""
        data = {
            'name': name,
            'fabric': fabric_id,
            'subnets_config': template_config,
            'apply_immediately': True
        }
        response = self.session.post(
            f'{self.base_url}/api/plugins/hedgehog/vpcs/',
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def bulk_apply_vpcs(self, vpc_ids):
        """Apply multiple VPCs to their clusters"""
        data = {
            'action': 'apply',
            'vpcs': vpc_ids
        }
        response = self.session.post(
            f'{self.base_url}/api/plugins/hedgehog/vpcs/bulk-actions/',
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def get_fabric_status(self, fabric_id):
        """Get detailed fabric status"""
        response = self.session.get(
            f'{self.base_url}/api/plugins/hedgehog/fabrics/{fabric_id}/cluster-status/'
        )
        response.raise_for_status()
        return response.json()

# Usage example
api = HedgehogAPI('https://netbox.example.com', 'your-api-token')

# List fabrics
fabrics = api.list_fabrics()
print(f"Found {fabrics['count']} fabrics")

# Create VPC
vpc_config = {
    'web': {
        'subnet': '10.200.10.0/24',
        'gateway': '10.200.10.1',
        'vlan': 2010,
        'dhcp': {'enable': True}
    }
}
new_vpc = api.create_vpc('web-staging', 1, vpc_config)
print(f"Created VPC: {new_vpc['id']}")

# Bulk apply VPCs
result = api.bulk_apply_vpcs([1, 2, 3])
print(f"Applied {len(result['results']['successful'])} VPCs")
```

### Bash/curl Examples

```bash
#!/bin/bash

# Configuration
NETBOX_URL="https://netbox.example.com"
API_TOKEN="your-api-token"
API_BASE="${NETBOX_URL}/api/plugins/hedgehog"

# Helper function for API calls
api_call() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    
    curl -s \
         -X "$method" \
         -H "Authorization: Token $API_TOKEN" \
         -H "Content-Type: application/json" \
         ${data:+-d "$data"} \
         "${API_BASE}${endpoint}"
}

# List all fabrics
echo "Listing fabrics:"
api_call GET "/fabrics/" | jq '.results[] | {id, name, sync_status}'

# Create a VPC
echo "Creating VPC:"
vpc_data='{
  "name": "test-vpc",
  "fabric": 1,
  "subnets_config": {
    "main": {
      "subnet": "10.100.50.0/24",
      "gateway": "10.100.50.1",
      "vlan": 1150,
      "dhcp": {"enable": true}
    }
  },
  "apply_immediately": true
}'
api_call POST "/vpcs/" "$vpc_data" | jq '{id, name, kubernetes_status}'

# Test fabric connection
echo "Testing fabric connection:"
api_call POST "/fabrics/1/test-connection/" | jq '{success, message}'

# Bulk apply VPCs
echo "Bulk applying VPCs:"
bulk_data='{"action": "apply", "vpcs": [1, 2, 3]}'
api_call POST "/vpcs/bulk-actions/" "$bulk_data" | jq '{success, message, results}'
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

class HedgehogClient {
    constructor(baseURL, token) {
        this.client = axios.create({
            baseURL: `${baseURL}/api/plugins/hedgehog`,
            headers: {
                'Authorization': `Token ${token}`,
                'Content-Type': 'application/json'
            }
        });
    }

    async listFabrics() {
        const response = await this.client.get('/fabrics/');
        return response.data;
    }

    async createVPC(vpcData) {
        const response = await this.client.post('/vpcs/', vpcData);
        return response.data;
    }

    async syncFabric(fabricId) {
        const response = await this.client.post(`/fabrics/${fabricId}/sync/`);
        return response.data;
    }

    async bulkOperation(endpoint, action, resourceIds) {
        const data = {
            action: action,
            [endpoint.slice(1, -1)]: resourceIds // Extract resource type from endpoint
        };
        const response = await this.client.post(`${endpoint}bulk-actions/`, data);
        return response.data;
    }
}

// Usage
async function main() {
    const client = new HedgehogClient('https://netbox.example.com', 'your-token');
    
    try {
        // List fabrics
        const fabrics = await client.listFabrics();
        console.log(`Found ${fabrics.count} fabrics`);
        
        // Create VPC
        const vpcData = {
            name: 'api-dev',
            fabric: 1,
            subnets_config: {
                api: {
                    subnet: '10.150.10.0/24',
                    gateway: '10.150.10.1',
                    vlan: 1510,
                    dhcp: { enable: true }
                }
            },
            apply_immediately: true
        };
        
        const newVPC = await client.createVPC(vpcData);
        console.log(`Created VPC: ${newVPC.id}`);
        
        // Sync fabric
        const syncResult = await client.syncFabric(1);
        console.log(`Sync result: ${syncResult.message}`);
        
    } catch (error) {
        console.error('API Error:', error.response?.data || error.message);
    }
}

main();
```

---

## Error Handling

### Common Error Responses

#### Validation Error (400)
```json
{
  "error": "Validation failed",
  "details": {
    "name": ["This field is required."],
    "subnets_config": ["Invalid subnet configuration."]
  }
}
```

#### Permission Error (403)
```json
{
  "error": "Permission denied",
  "message": "You don't have permission to perform this action."
}
```

#### Resource Not Found (404)
```json
{
  "error": "Not found",
  "message": "Fabric with id 999 does not exist."
}
```

### Best Practices

1. **Always check HTTP status codes**
2. **Handle rate limiting appropriately**
3. **Use pagination for large result sets**
4. **Implement proper error handling**
5. **Cache responses when appropriate**
6. **Use bulk operations for efficiency**
7. **Validate data before sending requests**

---

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Rate Limit**: 100 requests per minute per user
- **Headers**: Check `X-RateLimit-*` headers in responses
- **429 Response**: When rate limit exceeded

```bash
# Example response headers
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```

---

## Webhook Events

The plugin supports webhooks for real-time notifications:

### Event Types

- `fabric.created`
- `fabric.updated`
- `fabric.deleted`
- `vpc.created`
- `vpc.applied`
- `vpc.deleted`
- `switch.discovered`
- `connection.updated`

### Webhook Payload

```json
{
  "event": "vpc.created",
  "timestamp": "2025-06-29T13:00:00.000Z",
  "data": {
    "id": 1,
    "name": "new-vpc",
    "fabric": "production-dc1",
    "user": "admin"
  }
}
```

---

*This API reference covers the core functionality. For additional endpoints and detailed parameter descriptions, refer to the interactive API documentation at `/api/docs/` in your NetBox instance.*