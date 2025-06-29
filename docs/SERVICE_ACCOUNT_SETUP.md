# Hedgehog NetBox Plugin - Service Account Setup

This guide explains how to set up Kubernetes service accounts for the NetBox Hedgehog Plugin to securely connect to your Hedgehog fabric clusters.

## Overview

The NetBox Hedgehog Plugin requires access to your Kubernetes cluster where Hedgehog is installed to:
- Query existing Hedgehog Custom Resources (CRs) 
- Create, update, and delete Hedgehog CRs from NetBox
- Perform periodic reconciliation to sync changes

## Prerequisites

- Kubernetes cluster with Hedgehog installed
- `kubectl` access to the cluster with admin privileges
- NetBox with the Hedgehog plugin installed

## Step 1: Generate Service Account Configuration

The plugin can generate the necessary YAML configuration for your fabric. From NetBox, navigate to the fabric onboarding interface and download the service account YAML, or use the following template:

```yaml
# Replace 'your-fabric-name' with your actual fabric name
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: netbox-hedgehog-your-fabric-name
  namespace: default
  labels:
    app.kubernetes.io/name: netbox-hedgehog-plugin
    app.kubernetes.io/instance: your-fabric-name

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: netbox-hedgehog-your-fabric-name
rules:
# VPC API permissions
- apiGroups: ["vpc.githedgehog.com"]
  resources: ["*"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Wiring API permissions  
- apiGroups: ["wiring.githedgehog.com"]
  resources: ["*"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Core API permissions
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list"]

# CRD discovery permissions
- apiGroups: ["apiextensions.k8s.io"]
  resources: ["customresourcedefinitions"]
  verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: netbox-hedgehog-your-fabric-name
subjects:
- kind: ServiceAccount
  name: netbox-hedgehog-your-fabric-name
  namespace: default
roleRef:
  kind: ClusterRole
  name: netbox-hedgehog-your-fabric-name
  apiGroup: rbac.authorization.k8s.io

---
apiVersion: v1
kind: Secret
metadata:
  name: netbox-hedgehog-your-fabric-name-token
  namespace: default
  annotations:
    kubernetes.io/service-account.name: netbox-hedgehog-your-fabric-name
type: kubernetes.io/service-account-token
```

## Step 2: Apply the Service Account Configuration

1. Save the YAML to a file (e.g., `netbox-service-account.yaml`)

2. Apply it to your cluster:
```bash
kubectl apply -f netbox-service-account.yaml
```

3. Verify the service account was created:
```bash
kubectl get serviceaccount netbox-hedgehog-your-fabric-name
kubectl get clusterrole netbox-hedgehog-your-fabric-name
kubectl get clusterrolebinding netbox-hedgehog-your-fabric-name
```

## Step 3: Extract the Service Account Token

### For Kubernetes 1.24+

1. Get the token from the secret:
```bash
kubectl get secret netbox-hedgehog-your-fabric-name-token -o jsonpath='{.data.token}' | base64 -d
```

2. Get the cluster CA certificate:
```bash
kubectl get secret netbox-hedgehog-your-fabric-name-token -o jsonpath='{.data.ca\.crt}'
```

3. Get your cluster server URL:
```bash
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'
```

### For Kubernetes 1.23 and earlier

The token is automatically created. Get it with:
```bash
kubectl get secret $(kubectl get serviceaccount netbox-hedgehog-your-fabric-name -o jsonpath='{.secrets[0].name}') -o jsonpath='{.data.token}' | base64 -d
```

## Step 4: Create Kubeconfig for NetBox

Create a kubeconfig file that NetBox can use:

```yaml
apiVersion: v1
kind: Config
clusters:
- name: your-fabric-name
  cluster:
    certificate-authority-data: <CA_CERT_FROM_STEP_3>
    server: <SERVER_URL_FROM_STEP_3>
users:
- name: netbox-hedgehog-your-fabric-name
  user:
    token: <TOKEN_FROM_STEP_3>
contexts:
- name: your-fabric-name-context
  context:
    cluster: your-fabric-name
    user: netbox-hedgehog-your-fabric-name
    namespace: default
current-context: your-fabric-name-context
```

## Step 5: Configure NetBox Plugin

1. In NetBox, navigate to **Hedgehog Fabrics** → **Add Fabric**

2. Fill in the fabric details:
   - **Name**: Your fabric name
   - **Description**: Description of your fabric
   - **Cluster Endpoint**: Your Kubernetes API server URL
   - **Authentication Method**: Select "Service Account Token" or "Kubeconfig"

3. Upload or paste the kubeconfig file content

4. Test the connection using the "Test Connection" button

5. Once connection is successful, click "Import Existing Resources" to import all existing Hedgehog CRs

## Step 6: Verify Setup

After setup, verify that:

1. **Connection Test**: The plugin can connect to your cluster
2. **Resource Discovery**: Existing Hedgehog CRs are visible in NetBox
3. **Create Test**: You can create a test VPC from NetBox
4. **Reconciliation**: Changes made directly with `kubectl` appear in NetBox

## Security Considerations

### Principle of Least Privilege
The service account has only the minimum permissions needed:
- Full access to Hedgehog CRDs (`vpc.githedgehog.com` and `wiring.githedgehog.com`)
- Read access to namespaces and CRD definitions
- No access to other cluster resources

### Token Rotation
For production environments, consider:
- Rotating service account tokens periodically
- Using short-lived tokens with token refresh
- Monitoring service account usage

### Network Security
- Ensure NetBox can reach your Kubernetes API server
- Consider using private networks or VPNs for communication
- Implement proper firewall rules

## Troubleshooting

### Connection Issues
```bash
# Test service account permissions
kubectl auth can-i create vpcs --as=system:serviceaccount:default:netbox-hedgehog-your-fabric-name

# Verify token validity
kubectl get pods --token=<YOUR_TOKEN> --server=<YOUR_SERVER> --certificate-authority=<CA_CERT_FILE>
```

### Permission Issues
```bash
# Check service account details
kubectl describe serviceaccount netbox-hedgehog-your-fabric-name
kubectl describe clusterrolebinding netbox-hedgehog-your-fabric-name
```

### Resource Discovery Issues
```bash
# Check if Hedgehog CRDs exist
kubectl get crd | grep githedgehog.com

# Check if resources exist
kubectl get vpcs,switches,connections -A
```

## Advanced Configuration

### Multiple Namespaces
To grant access to multiple namespaces, modify the ClusterRole:

```yaml
# Add namespace-specific permissions
- apiGroups: [""]
  resources: ["*"]
  resourceNames: ["namespace1", "namespace2"]
  verbs: ["get", "list", "watch"]
```

### Read-Only Access
For read-only monitoring, remove write permissions:

```yaml
# Remove write verbs
- apiGroups: ["vpc.githedgehog.com", "wiring.githedgehog.com"]
  resources: ["*"]
  verbs: ["get", "list", "watch"]  # Removed: create, update, patch, delete
```

### Audit Logging
Enable audit logging for service account actions:

```yaml
# Add to your cluster's audit policy
- level: RequestResponse
  namespaces: ["default"]
  verbs: ["create", "update", "patch", "delete"]
  users: ["system:serviceaccount:default:netbox-hedgehog-your-fabric-name"]
```

## Support

For issues with service account setup:
1. Check the [troubleshooting section](#troubleshooting)
2. Review the NetBox plugin logs
3. Verify Kubernetes cluster permissions
4. Open an issue in the plugin repository

---

**Next Steps**: After completing the service account setup, proceed to [Fabric Onboarding](FABRIC_ONBOARDING.md) to import your existing Hedgehog installation into NetBox.