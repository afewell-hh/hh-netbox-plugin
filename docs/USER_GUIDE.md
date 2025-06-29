# Hedgehog NetBox Plugin - User Guide

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Dashboard & Navigation](#dashboard--navigation)
4. [Fabric Management](#fabric-management)
5. [VPC Management](#vpc-management)
6. [Infrastructure Management](#infrastructure-management)
7. [Bulk Operations](#bulk-operations)
8. [Network Topology](#network-topology)
9. [Templates & Automation](#templates--automation)
10. [Troubleshooting](#troubleshooting)
11. [Best Practices](#best-practices)

---

## Overview

The Hedgehog NetBox Plugin provides a comprehensive self-service catalog for managing Hedgehog Open Network Fabric resources directly from NetBox. It enables network administrators to:

- **Manage Multiple Fabrics**: Connect and manage multiple Hedgehog fabric installations
- **Create VPCs**: Use templates to quickly deploy Virtual Private Clouds
- **Monitor Infrastructure**: Track switches, connections, and physical topology
- **Automate Operations**: Perform bulk operations across multiple resources
- **Maintain Consistency**: Bidirectional sync between NetBox and Kubernetes

### Key Features

- 🏗️ **Fabric Onboarding**: Automated setup for new Hedgehog installations
- ☁️ **VPC Templates**: Pre-configured templates for common network patterns
- 🔌 **Infrastructure Tracking**: Real-time status of switches and connections
- 📊 **Dashboard Monitoring**: Centralized view of all fabric health
- ⚡ **Bulk Operations**: Efficient management of multiple resources
- 🔄 **Auto-Reconciliation**: Keeps NetBox and Kubernetes in sync

---

## Getting Started

### Prerequisites

- NetBox instance with Hedgehog plugin installed
- Access to Hedgehog Kubernetes cluster(s)
- Appropriate user permissions in NetBox

### First Login

1. **Access NetBox**: Log into your NetBox instance
2. **Navigate to Hedgehog**: Click "Hedgehog" in the main navigation menu
3. **View Dashboard**: You'll see the fabric overview dashboard

### Quick Start Checklist

- [ ] Add your first fabric
- [ ] Test Kubernetes connection
- [ ] Perform initial sync
- [ ] Create your first VPC
- [ ] Explore the network topology

---

## Dashboard & Navigation

### Main Dashboard

The Hedgehog dashboard provides a centralized view of all your fabric installations:

![Dashboard Overview](images/dashboard-overview.png)

**Key Sections:**

1. **Fabric Health Cards**: Status overview for each fabric
2. **Resource Statistics**: Total counts across all fabrics
3. **Recent Activity**: Latest changes and operations
4. **Quick Actions**: Common tasks and bulk operations

**Health Indicators:**

- 🟢 **Healthy**: Fabric is synced and operational
- 🟡 **Syncing**: Reconciliation in progress
- 🔴 **Error**: Connection or sync issues

### Navigation Structure

The plugin organizes features into logical sections:

**Overview**
- Dashboard: Main status overview
- Network Topology: Visual fabric representation

**Fabric Management**
- Fabrics: Manage fabric connections
- CRD Catalog: Browse available resources

**VPC API**
- VPCs: Virtual Private Cloud management
- Externals: External system connections
- IPv4 Namespaces: IP address management

**Wiring API**
- Connections: Physical/logical connections
- Switches: Network switch configuration
- Servers: Server connectivity
- VLAN Namespaces: VLAN range management

---

## Fabric Management

### Adding a New Fabric

1. **Navigate**: Go to Hedgehog → Fabric Management → Fabrics
2. **Click**: "Add Fabric" button
3. **Fill Details**:
   - **Name**: Descriptive name for the fabric
   - **Description**: Optional description
   - **Kubeconfig**: Kubernetes configuration YAML

```yaml
# Example kubeconfig
apiVersion: v1
kind: Config
clusters:
- cluster:
    server: https://hedgehog-api.example.com:6443
    certificate-authority-data: LS0tLS1CRUdJTi...
  name: hedgehog-cluster
contexts:
- context:
    cluster: hedgehog-cluster
    user: hedgehog-user
  name: hedgehog-context
current-context: hedgehog-context
users:
- name: hedgehog-user
  user:
    token: eyJhbGciOiJSUzI1NiIs...
```

4. **Save**: Click "Create Fabric"

### Fabric Onboarding Process

For new Hedgehog installations, use the guided onboarding:

1. **Create Fabric**: Add basic fabric information
2. **Generate Service Account**: The plugin will generate required YAML
3. **Apply to Cluster**: Apply the service account configuration
4. **Update Kubeconfig**: Use the generated service account token
5. **Test Connection**: Verify connectivity
6. **Initial Sync**: Import existing resources

#### Service Account Setup

The plugin generates a minimal-privilege service account:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: netbox-hedgehog
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: netbox-hedgehog
rules:
- apiGroups: ["vpc.githedgehog.com"]
  resources: ["*"]
  verbs: ["get", "list", "create", "update", "patch", "delete"]
- apiGroups: ["wiring.githedgehog.com"]
  resources: ["*"]
  verbs: ["get", "list", "create", "update", "patch", "delete"]
```

### Fabric Operations

#### Test Connection

Verify that NetBox can communicate with the Kubernetes cluster:

1. **Navigate**: To fabric detail page
2. **Click**: "Test Connection" button
3. **Review**: Connection status and cluster information

#### Sync Fabric

Perform reconciliation to sync NetBox with cluster state:

1. **Navigate**: To fabric detail page
2. **Click**: "Sync Fabric" button
3. **Monitor**: Progress and imported resources

#### Fabric Health Monitoring

Monitor fabric health through:

- **Connection Status**: Last successful connection test
- **Sync Status**: When last reconciliation occurred
- **Resource Counts**: Number of managed resources
- **Cluster Version**: Kubernetes version information

---

## VPC Management

### Creating VPCs with Templates

The plugin provides pre-configured templates for common VPC patterns:

#### Available Templates

1. **Basic VPC**
   - Single subnet for simple workloads
   - DHCP enabled
   - Suitable for: Development, testing

2. **Web + Database**
   - Two-tier application setup
   - Separate web and database subnets
   - Suitable for: Traditional applications

3. **Three-Tier Application**
   - Web, application, and database tiers
   - Complete separation of concerns
   - Suitable for: Enterprise applications

4. **Custom Configuration**
   - Define your own subnet layout
   - Full control over configuration
   - Suitable for: Special requirements

### VPC Creation Process

1. **Navigate**: Go to Hedgehog → VPC API → VPCs
2. **Click**: "Create VPC" button
3. **Configure**:

   **Basic Information:**
   - **VPC Name**: Must be ≤11 characters (Kubernetes requirement)
   - **Fabric**: Select target fabric
   - **Description**: Optional description

   **Template Selection:**
   - Choose from available templates
   - Preview shows expected subnet layout

   **Configuration:**
   - **Base Network**: Starting IP range (e.g., 10.100.0.0/16)
   - **Starting VLAN**: Beginning VLAN ID (e.g., 1100)
   - **Enable DHCP**: Automatic IP assignment

4. **Options**:
   - **Apply Immediately**: Deploy to cluster upon creation

5. **Create**: Click "Create VPC"

### VPC Template Examples

#### Basic VPC Template
```yaml
apiVersion: vpc.githedgehog.com/v1alpha1
kind: VPC
metadata:
  name: basic-vpc
spec:
  subnets:
    main:
      subnet: "10.100.1.0/24"
      gateway: "10.100.1.1"
      vlan: 1100
      dhcp:
        enable: true
```

#### Three-Tier Template
```yaml
apiVersion: vpc.githedgehog.com/v1alpha1
kind: VPC
metadata:
  name: three-tier-vpc
spec:
  subnets:
    web:
      subnet: "10.100.20.0/24"
      gateway: "10.100.20.1"
      vlan: 1120
      dhcp:
        enable: true
    app:
      subnet: "10.100.21.0/24"
      gateway: "10.100.21.1"
      vlan: 1121
      dhcp:
        enable: true
    db:
      subnet: "10.100.22.0/24"
      gateway: "10.100.22.1"
      vlan: 1122
      dhcp:
        enable: true
```

### VPC Lifecycle Management

#### Applying VPCs to Clusters

1. **Navigate**: To VPC detail page
2. **Click**: "Apply to Cluster" button
3. **Monitor**: Application status and any errors

#### VPC Status Tracking

VPCs have the following status indicators:

- **Pending**: Created in NetBox, not yet applied to cluster
- **Applied**: Successfully deployed to Kubernetes
- **Error**: Application failed, check error messages

#### Modifying VPCs

1. **Edit Configuration**: Update subnet settings in NetBox
2. **Apply Changes**: Re-apply to cluster to sync changes
3. **Monitor**: Ensure changes are successfully applied

#### Deleting VPCs

1. **Navigate**: To VPC detail page
2. **Click**: "Delete" button
3. **Confirm**: Deletion removes from both NetBox and cluster

---

## Infrastructure Management

### Switch Management

#### Viewing Switches

1. **Navigate**: Go to Hedgehog → Wiring API → Switches
2. **Filter**: By fabric, role, or search term
3. **View Details**: Click on any switch for detailed information

#### Switch Roles

Hedgehog supports several switch roles:

- **Spine**: Core switching layer
- **Server-Leaf**: Server-facing leaf switches
- **Border-Leaf**: External connection points
- **Mixed**: Switches handling multiple roles

#### Switch Information

Each switch displays:

- **Basic Info**: Name, role, ASN, profile
- **Network Config**: Management IP, protocol IP, VTEP IP
- **Groups**: Switch groups and VLAN namespaces
- **Redundancy**: MCLAG or ESLAG configuration
- **Interface Summary**: Port utilization statistics
- **Connections**: Associated connections and servers
- **Kubernetes Status**: Operational status in cluster

### Connection Management

#### Connection Types

- **Unbundled**: Individual physical connections
- **Bundled**: Link aggregation (LACP)
- **MCLAG**: Multi-chassis LAG
- **ESLAG**: Edge switch LAG

#### Viewing Connections

1. **Navigate**: Go to Hedgehog → Wiring API → Connections
2. **Filter**: By fabric, type, or search
3. **Details**: View endpoint information and configuration

#### Connection Details

Each connection shows:

- **Endpoints**: Connected devices and ports
- **Type Information**: Specific configuration for connection type
- **Related Switches**: Involved switches
- **Status**: Operational status

### VLAN Namespace Management

#### Purpose

VLAN namespaces define available VLAN ranges for VPC allocation:

```yaml
apiVersion: wiring.githedgehog.com/v1alpha1
kind: VLANNamespace
metadata:
  name: production
spec:
  ranges:
  - from: 1000
    to: 1999
  - from: 3000
    to: 3099
```

#### Creating VLAN Namespaces

1. **Navigate**: Go to Hedgehog → Wiring API → VLAN Namespaces
2. **Click**: "Add VLAN Namespace"
3. **Configure**:
   - **Name**: Namespace identifier
   - **Fabric**: Target fabric
   - **Ranges**: VLAN ID ranges

#### VLAN Utilization

The namespace detail page shows:

- **Total VLANs**: Available VLAN count
- **Used VLANs**: Currently allocated VLANs
- **VPCs Using Namespace**: Which VPCs use this namespace

---

## Bulk Operations

Bulk operations allow you to efficiently manage multiple resources simultaneously.

### Available Bulk Operations

#### Fabric Operations

**Test Connection**
- Test Kubernetes connectivity for multiple fabrics
- Useful for: Health checks across environments

**Sync Fabrics**
- Perform reconciliation for multiple fabrics
- Useful for: Updating multiple environments

**Delete Fabrics**
- Remove multiple fabrics from NetBox
- Useful for: Environment cleanup

#### VPC Operations

**Apply VPCs**
- Deploy multiple VPCs to their clusters
- Useful for: Batch deployments

**Delete VPCs**
- Remove multiple VPCs from NetBox and clusters
- Useful for: Environment cleanup

#### Switch Operations

**Apply Switches**
- Deploy multiple switches to clusters
- Useful for: Infrastructure updates

**Update Roles**
- Change roles for multiple switches
- Useful for: Network reorganization

**Delete Switches**
- Remove multiple switches
- Useful for: Decommissioning

#### Connection Operations

**Apply Connections**
- Deploy multiple connections to clusters
- Useful for: Cable management updates

**Update Types**
- Change connection types for multiple connections
- Useful for: Upgrading to bundled connections

**Delete Connections**
- Remove multiple connections
- Useful for: Infrastructure changes

### Using Bulk Operations

1. **Navigate**: To relevant resource list page
2. **Select Items**: 
   - Use checkboxes to select individual items
   - Use "Select All" for all visible items
3. **Choose Action**: Select action from dropdown
4. **Confirm**: Review selection and confirm
5. **Monitor**: Watch progress and results

#### Example: Bulk VPC Deployment

1. Go to VPCs list page
2. Select VPCs with "Pending" status
3. Choose "Apply to Cluster" action
4. Click "Apply to 5 items" button
5. Confirm deployment
6. Monitor progress notifications

### Bulk Operation Safety

- **Permission Checks**: Operations require appropriate permissions
- **Confirmation Dialogs**: Destructive actions require confirmation
- **Progress Feedback**: Real-time status updates
- **Error Handling**: Individual failures don't stop entire operation

---

## Network Topology

### Topology Visualization

The network topology provides a visual representation of your fabric:

1. **Navigate**: Go to Hedgehog → Overview → Network Topology
2. **Select Fabric**: Choose fabric to visualize
3. **Interact**: Click nodes and links for details

### Topology Elements

#### Nodes

- **Switches**: Colored by role (spine, leaf, border)
- **Servers**: Server connections and endpoints
- **Status Indicators**: Online/offline status

#### Links

- **Connection Types**: Different styles for unbundled, bundled, MCLAG
- **Status**: Active/inactive connections
- **Hover Details**: Connection information on hover

#### Legend

- **Spine Switches**: Blue nodes
- **Leaf Switches**: Green nodes  
- **Border Switches**: Orange nodes
- **Servers**: Gray nodes
- **Active Links**: Solid lines
- **Inactive Links**: Dashed lines

### Topology Statistics

The topology view shows:

- **Switch Counts**: By role type
- **Connection Counts**: Total connections
- **Server Counts**: Connected servers
- **Health Overview**: Operational status

---

## Templates & Automation

### VPC Templates

Templates provide standardized VPC configurations for common use cases.

#### Template Structure

Each template defines:

- **Subnet Layout**: Number and naming of subnets
- **IP Allocation**: Base network and sizing
- **VLAN Assignment**: VLAN ID patterns
- **DHCP Configuration**: Automatic IP assignment settings

#### Custom Templates

For advanced users, custom templates can be created by:

1. **Selecting Custom**: Choose custom configuration option
2. **Adding Subnets**: Define each subnet individually
3. **Configuring Details**: Set IP ranges, VLANs, DHCP settings

#### Template Best Practices

- **Consistent Naming**: Use descriptive, consistent subnet names
- **Non-overlapping IPs**: Ensure IP ranges don't conflict
- **VLAN Planning**: Plan VLAN ranges to avoid conflicts
- **Documentation**: Document template purposes and use cases

### Automation Features

#### Auto-Reconciliation

The plugin automatically:

- **Detects Changes**: Monitors cluster for external changes
- **Imports Resources**: Adds externally created resources to NetBox
- **Syncs Status**: Updates resource status based on cluster state
- **Resolves Conflicts**: Handles configuration drift

#### Fabric Onboarding

Automated onboarding includes:

- **Service Account Creation**: Generates required Kubernetes access
- **Permission Setup**: Minimal privilege configuration
- **Connection Testing**: Validates cluster connectivity
- **Resource Discovery**: Imports existing cluster resources

#### Template-Based Creation

Templates automate:

- **Subnet Calculation**: Automatic IP and VLAN allocation
- **Configuration Generation**: Creates valid Kubernetes manifests
- **Validation**: Ensures configuration meets cluster requirements

---

## Troubleshooting

### Common Issues

#### Connection Problems

**Symptoms**: "Connection test failed" errors

**Solutions**:
1. **Check Kubeconfig**: Verify YAML format and credentials
2. **Network Access**: Ensure NetBox can reach Kubernetes API
3. **Permissions**: Verify service account has required permissions
4. **Certificates**: Check certificate validity and trust chain

#### VPC Creation Failures

**Symptoms**: VPCs stuck in "Error" status

**Common Causes**:
- **Name Length**: VPC names must be ≤11 characters
- **VLAN Conflicts**: VLANs already in use
- **IP Overlaps**: Subnet ranges conflict with existing VPCs
- **Namespace Issues**: Missing IPv4 or VLAN namespaces

**Solutions**:
1. **Check Validation**: Review error messages in VPC details
2. **Verify Resources**: Ensure namespaces exist and have capacity
3. **Name Compliance**: Use shorter, Kubernetes-compatible names
4. **Retry Application**: Re-apply after fixing issues

#### Sync Failures

**Symptoms**: Fabric shows "Error" sync status

**Solutions**:
1. **Check Permissions**: Verify service account access
2. **Resource Conflicts**: Review conflicting resources
3. **Manual Sync**: Try manual sync operation
4. **Reset Connection**: Re-test fabric connection

### Debugging Steps

#### For Connection Issues

1. **Test Connectivity**:
   ```bash
   kubectl --kubeconfig=/path/to/config cluster-info
   ```

2. **Verify Permissions**:
   ```bash
   kubectl auth can-i get vpcs.vpc.githedgehog.com
   ```

3. **Check Service Account**:
   ```bash
   kubectl get serviceaccount netbox-hedgehog
   ```

#### For VPC Issues

1. **Check VPC Status**:
   ```bash
   kubectl get vpc <vpc-name> -o yaml
   ```

2. **Review Events**:
   ```bash
   kubectl describe vpc <vpc-name>
   ```

3. **Validate Manifest**:
   - Copy VPC YAML from NetBox
   - Validate with `kubectl apply --dry-run=client`

#### For Sync Issues

1. **Manual Reconciliation**: Use "Sync Fabric" button
2. **Check Logs**: Review NetBox application logs
3. **Resource Review**: Compare NetBox vs cluster resources

### Getting Help

#### Log Information

When reporting issues, include:

- **NetBox Version**: NetBox and plugin versions
- **Error Messages**: Complete error text
- **Configuration**: Relevant kubeconfig (sanitized)
- **Steps to Reproduce**: Detailed reproduction steps

#### Support Channels

- **GitHub Issues**: For bug reports and feature requests
- **Documentation**: Check plugin documentation for updates
- **Community**: Hedgehog community forums and discussions

---

## Best Practices

### Fabric Management

#### Naming Conventions

- **Descriptive Names**: Use environment/location-based names
  - Examples: `prod-dc1`, `staging-cloud`, `dev-lab`
- **Consistent Pattern**: Establish and follow naming standards
- **Avoid Special Characters**: Use alphanumeric and hyphens only

#### Access Control

- **Separate Accounts**: Use dedicated service accounts per fabric
- **Minimal Permissions**: Grant only required Kubernetes permissions
- **Regular Rotation**: Rotate service account tokens periodically
- **Audit Access**: Monitor and log fabric access

#### Environment Separation

- **Fabric Isolation**: Use separate fabrics for prod/staging/dev
- **Permission Boundaries**: Restrict user access by environment
- **Change Management**: Implement approval processes for production

### VPC Management

#### Design Principles

- **Subnet Planning**: Plan IP address space in advance
- **VLAN Organization**: Use consistent VLAN numbering schemes
- **Template Usage**: Leverage templates for consistency
- **Documentation**: Document VPC purposes and ownership

#### Naming Standards

- **Meaningful Names**: Reflect purpose or application
  - Examples: `web-prod`, `api-staging`, `db-cluster`
- **Length Limits**: Keep names ≤11 characters for Kubernetes
- **No Spaces**: Use hyphens instead of spaces
- **Version Indicators**: Include version if needed (`app-v2`)

#### Resource Allocation

- **Size Appropriately**: Don't over-allocate IP space
- **Plan Growth**: Leave room for expansion
- **Monitor Usage**: Track IP and VLAN utilization
- **Clean Up**: Remove unused VPCs regularly

### Operational Practices

#### Regular Maintenance

- **Weekly Sync**: Perform fabric sync weekly or after changes
- **Health Monitoring**: Check fabric status regularly
- **Resource Cleanup**: Remove obsolete resources
- **Documentation Updates**: Keep configuration docs current

#### Change Management

- **Test First**: Use staging fabrics for testing changes
- **Bulk Operations**: Use bulk operations for efficiency
- **Verification**: Verify changes in Kubernetes after application
- **Rollback Plans**: Have rollback procedures ready

#### Monitoring and Alerting

- **Status Checks**: Monitor fabric health indicators
- **Resource Limits**: Alert on IP/VLAN exhaustion
- **Sync Failures**: Alert on reconciliation errors
- **Performance**: Monitor operation response times

### Security Best Practices

#### Access Management

- **Role-Based Access**: Use NetBox groups and permissions
- **Least Privilege**: Grant minimum required permissions
- **Regular Review**: Audit user access quarterly
- **MFA**: Enable multi-factor authentication

#### Credential Management

- **Secure Storage**: Store kubeconfigs securely
- **Token Rotation**: Rotate service account tokens
- **Network Security**: Use encrypted connections only
- **Audit Logging**: Enable and monitor access logs

#### Configuration Security

- **Validation**: Validate all configurations before applying
- **Approval Process**: Require approval for production changes
- **Backup**: Maintain configuration backups
- **Version Control**: Track configuration changes

---

## Conclusion

The Hedgehog NetBox Plugin provides powerful capabilities for managing modern network fabrics. By following the practices outlined in this guide, you can:

- **Efficiently Manage**: Multiple fabric installations from a single interface
- **Standardize Deployments**: Using templates and automation
- **Maintain Consistency**: Through bidirectional synchronization
- **Scale Operations**: With comprehensive bulk operations
- **Monitor Health**: Through real-time status tracking

### Quick Reference

**Common Tasks:**
- [Add Fabric](#adding-a-new-fabric)
- [Create VPC](#creating-vpcs-with-templates)  
- [Bulk Operations](#using-bulk-operations)
- [View Topology](#topology-visualization)

**Troubleshooting:**
- [Connection Issues](#connection-problems)
- [VPC Problems](#vpc-creation-failures)
- [Sync Errors](#sync-failures)

For additional support and updates, refer to the plugin documentation and community resources.

---

*Last Updated: 2025-06-29*  
*Plugin Version: 1.0.0*  
*NetBox Compatibility: 4.0+*