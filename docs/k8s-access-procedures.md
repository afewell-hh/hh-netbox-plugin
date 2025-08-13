# Kubernetes Access Procedures for Hedgehog NetBox Plugin

This document provides comprehensive procedures for accessing and managing Kubernetes clusters from the Hedgehog NetBox Plugin DevContainer environment.

## 🎯 Overview

The DevContainer provides secure, isolated access to multiple Hedgehog fabric Kubernetes clusters while maintaining proper security boundaries and permissions.

## 🔧 Setup and Configuration

### Prerequisites

1. **Host Requirements**:
   - Docker and Docker Compose installed
   - VS Code with Dev Containers extension
   - Valid kubeconfig at `~/.kube/config` on host machine
   - Network access to target Kubernetes clusters

2. **Security Requirements**:
   - Host kubeconfig with proper permissions (600)
   - Valid service account tokens or certificates
   - Network connectivity to cluster API servers

### Initial Setup

1. **Open DevContainer**:
   ```bash
   # From VS Code
   Cmd/Ctrl+Shift+P -> "Dev Containers: Reopen in Container"
   
   # Or from terminal
   code .
   ```

2. **Validate Setup**:
   ```bash
   # Run comprehensive validation
   ~/.kube/validate-kubectl.sh
   
   # Or use the alias
   hh-kubectl-validate
   ```

3. **Test Connectivity**:
   ```bash
   # List available contexts
   kubectl config get-contexts
   
   # Test current context
   kubectl cluster-info
   
   # Test specific fabric
   .devcontainer/scripts/test-fabric-connection.sh fabric-datacenter1
   ```

## 🏗️ Fabric-Specific Configuration

### Adding a New Fabric Context

Use the provided script to add fabric-specific kubectl contexts:

```bash
# Method 1: Using the helper script
~/.kube/fabric-configs/add-fabric-context.sh \
  datacenter1 \
  https://k8s.fabric1.local:6443 \
  LS0tLS1CRUdJTi... \
  eyJhbGciOiJSUzI1NiIs...

# Method 2: Using the Python generator
.devcontainer/scripts/generate-fabric-kubeconfig.py \
  datacenter1 \
  https://k8s.fabric1.local:6443 \
  LS0tLS1CRUdJTi... \
  eyJhbGciOiJSUzI1NiIs...
```

### Parameters Explained

- **fabric-name**: Unique identifier for the fabric (e.g., `datacenter1`, `prod-east`)
- **cluster-server**: Kubernetes API server URL (e.g., `https://k8s.fabric1.local:6443`)
- **ca-cert-base64**: Base64 encoded CA certificate from the cluster
- **user-token**: Service account token or user token for authentication

### Extracting Configuration from NetBox

If you have fabric data in NetBox, extract the Kubernetes configuration:

```python
# In Django shell or management command
from netbox_hedgehog.models import HedgehogFabric

fabric = HedgehogFabric.objects.get(name='datacenter1')
k8s_config = fabric.get_kubernetes_config()

print("Server:", k8s_config['host'])
print("CA Cert:", k8s_config['ssl_ca_cert'])
print("Token:", k8s_config['api_key']['authorization'])
```

## 🔐 Security Model

### Permission Structure

```
~/.kube/
├── config (600)              # Main kubeconfig file
├── backups/ (700)            # Automatic backups
├── fabric-configs/ (700)     # Fabric-specific configurations
│   ├── add-fabric-context.sh (700)
│   ├── fabric-context-template.yaml (600)
│   └── datacenter1-kubeconfig.yaml (600)
└── validate-kubectl.sh (700) # Validation script
```

### Security Features

1. **File Permissions**: All kubectl files use restrictive permissions (600/700)
2. **User Isolation**: All operations run as `developer` user (UID 1000)
3. **Read-Only Mounts**: Host kubeconfig is mounted read-only
4. **Token Security**: Service account tokens are never logged or exposed
5. **Network Isolation**: DevContainer network is isolated from host

### Best Practices

1. **Regular Token Rotation**: Rotate service account tokens periodically
2. **Principle of Least Privilege**: Use tokens with minimal required permissions
3. **Backup Management**: Automatic backups are created before modifications
4. **Audit Logging**: All kubectl operations are logged by Kubernetes clusters

## 🔄 Daily Operations

### Switching Between Fabrics

```bash
# List all contexts
kubectl config get-contexts

# Switch to specific fabric
kubectl config use-context fabric-datacenter1

# Use context for single command
kubectl --context=fabric-datacenter2 get nodes

# Use fabric alias (if available)
k-fabric get pods
```

### Common Tasks

#### 1. Checking Cluster Status
```bash
# Cluster information
kubectl cluster-info

# Node status
kubectl get nodes

# Cluster version
kubectl version

# Available APIs
kubectl api-versions
```

#### 2. Managing Hedgehog Resources
```bash
# List all Hedgehog CRDs
kubectl api-resources | grep githedgehog

# Get VPCs
kubectl get vpcs

# Get connections
kubectl get connections

# Get switches
kubectl get switches

# Describe specific resource
kubectl describe vpc my-vpc-name
```

#### 3. Namespace Operations
```bash
# List namespaces
kubectl get namespaces

# Set default namespace for context
kubectl config set-context --current --namespace=hedgehog-system

# Create namespace
kubectl create namespace my-namespace
```

#### 4. Monitoring and Logs
```bash
# Get pod logs
kubectl logs -n hedgehog-system deployment/hedgehog-controller

# Follow logs
kubectl logs -f -n hedgehog-system deployment/hedgehog-controller

# Get events
kubectl get events --sort-by=.metadata.creationTimestamp

# Resource usage
kubectl top nodes
kubectl top pods
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Authentication Problems
```bash
# Symptoms: "unable to connect", "unauthorized", "forbidden"

# Check current context
kubectl config current-context

# Validate kubeconfig
kubectl config view --minify

# Test authentication
kubectl auth whoami

# Check token expiry (if using tokens)
kubectl auth can-i get pods --as=system:serviceaccount:default:my-sa
```

#### 2. Network Connectivity Issues
```bash
# Symptoms: "connection refused", "timeout"

# Test DNS resolution
nslookup k8s.fabric1.local

# Test port connectivity
telnet k8s.fabric1.local 6443

# Check cluster endpoint
kubectl cluster-info

# Verify CA certificate
openssl s_client -connect k8s.fabric1.local:6443 -servername k8s.fabric1.local
```

#### 3. Permission Issues
```bash
# Symptoms: "forbidden", "access denied"

# Check current permissions
kubectl auth can-i get pods
kubectl auth can-i create deployments
kubectl auth can-i get vpcs

# List permissions
kubectl auth can-i --list

# Check RBAC
kubectl get rolebindings,clusterrolebindings --all-namespaces | grep my-user
```

#### 4. Configuration Issues
```bash
# Symptoms: "invalid configuration", "malformed"

# Validate configuration
~/.kube/validate-kubectl.sh

# Check file permissions
ls -la ~/.kube/config

# Reset permissions
find ~/.kube -type f -exec chmod 600 {} \;
find ~/.kube -type d -exec chmod 700 {} \;

# Restore from backup
cp ~/.kube/backups/config-YYYYMMDD-HHMMSS ~/.kube/config
```

### Debug Commands

```bash
# Verbose kubectl output
kubectl get pods -v=8

# Raw API access
kubectl get --raw /api/v1/nodes

# Cluster debug info
kubectl cluster-info dump

# Configuration debug
kubectl config view --raw --minify

# Test specific API groups
kubectl api-resources --api-group=vpc.githedgehog.com
```

## 📚 Reference

### Useful Aliases

The DevContainer provides these pre-configured aliases:

```bash
# kubectl shortcuts
k                    # kubectl
kgp                  # kubectl get pods
kgs                  # kubectl get services
kgn                  # kubectl get nodes
kdesc                # kubectl describe
klogs                # kubectl logs

# Hedgehog-specific
hh-kubectl-validate  # Run validation suite
hh-kubectl-contexts  # List contexts
k-fabric             # Use first fabric context
k-list-fabrics       # List fabric contexts
```

### Configuration Files

| File | Purpose | Permissions |
|------|---------|-------------|
| `~/.kube/config` | Main kubeconfig | 600 |
| `~/.kube/validate-kubectl.sh` | Validation script | 700 |
| `~/.kube/fabric-configs/add-fabric-context.sh` | Add fabric script | 700 |
| `.devcontainer/scripts/test-fabric-connection.sh` | Connection test | 755 |
| `.devcontainer/scripts/generate-fabric-kubeconfig.py` | Config generator | 755 |

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `KUBECONFIG` | Path to kubeconfig file | `/home/developer/.kube/config` |
| `KUBECTL_EXTERNAL_DIFF` | External diff command | `colordiff -u` |
| `KUBECTL_LOG_LEVEL` | Log verbosity | `1` |

### Network Requirements

| Direction | Protocol | Port | Purpose |
|-----------|----------|------|---------|
| Outbound | TCP | 6443 | Kubernetes API |
| Outbound | TCP | 443 | HTTPS (if needed) |
| Outbound | UDP | 53 | DNS resolution |

### Support Resources

1. **Internal Documentation**:
   - `.devcontainer/kubectl-setup.sh --help`
   - `~/.kube/validate-kubectl.sh`
   - `.devcontainer/scripts/test-fabric-connection.sh --help`

2. **External Resources**:
   - [Kubernetes Documentation](https://kubernetes.io/docs/)
   - [kubectl Reference](https://kubernetes.io/docs/reference/kubectl/)
   - [Hedgehog Documentation](https://docs.githedgehog.com/)

3. **Emergency Procedures**:
   - Restore kubeconfig from backup
   - Reset DevContainer to clean state
   - Contact fabric administrators for new tokens

## 🔄 Maintenance

### Regular Tasks

1. **Weekly**:
   - Validate all fabric connections
   - Review and clean old backups
   - Update kubectl if needed

2. **Monthly**:
   - Rotate service account tokens
   - Review and update fabric configurations
   - Clean unused contexts

3. **As Needed**:
   - Add new fabric contexts
   - Update cluster endpoints
   - Troubleshoot connectivity issues

### Automation

The DevContainer includes automation for:
- Automatic permission fixing on startup
- Backup creation before modifications
- Health checks for kubectl functionality
- Connection validation on context changes

This ensures a reliable and secure Kubernetes access environment for Hedgehog fabric management.