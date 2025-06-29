# Hedgehog NetBox Plugin - Quick Start Guide

## 🚀 Get Started in 5 Minutes

This quick start guide will get you up and running with the Hedgehog NetBox Plugin in just a few minutes.

## Prerequisites

- ✅ NetBox 4.0+ with Hedgehog plugin installed
- ✅ Access to a Hedgehog Kubernetes cluster
- ✅ NetBox user account with appropriate permissions

## Step 1: Access the Plugin

1. **Login to NetBox**: Open your NetBox instance in a web browser
2. **Navigate to Hedgehog**: Click "Hedgehog" in the main navigation menu
3. **View Dashboard**: You'll see the fabric overview dashboard

![Navigation Screenshot](images/navigation.png)

## Step 2: Add Your First Fabric

1. **Click "Fabrics"** in the Fabric Management section
2. **Click "Add Fabric"** button (green plus icon)
3. **Fill in the form**:

```yaml
# Basic Information
Name: my-hedgehog-fabric
Description: Production Hedgehog fabric

# Kubeconfig (paste your cluster's kubeconfig)
apiVersion: v1
kind: Config
clusters:
- cluster:
    server: https://your-hedgehog-cluster:6443
    certificate-authority-data: LS0tLS1CRUdJTi...
  name: hedgehog
contexts:
- context:
    cluster: hedgehog
    user: hedgehog-user
  name: default
current-context: default
users:
- name: hedgehog-user
  user:
    token: eyJhbGciOiJSUzI1NiIs...
```

4. **Click "Create Fabric"**

## Step 3: Test Connection

1. **Go to your fabric's detail page** (click the fabric name)
2. **Click "Test Connection"** button
3. **Verify success**: You should see a green success message

![Connection Test](images/connection-test.png)

## Step 4: Initial Sync

1. **Click "Sync Fabric"** button on the fabric detail page
2. **Wait for completion**: This imports existing resources from your cluster
3. **Review results**: Check the imported switches, connections, and other resources

## Step 5: Create Your First VPC

1. **Navigate to VPCs**: Go to Hedgehog → VPC API → VPCs
2. **Click "Create VPC"** button
3. **Configure your VPC**:

   - **VPC Name**: `my-first-vpc` (≤11 characters)
   - **Fabric**: Select your fabric
   - **Template**: Choose "Basic VPC"
   - **Base Network**: `10.100.0.0/16`
   - **Starting VLAN**: `1100`
   - **Enable DHCP**: ✅ Checked
   - **Apply Immediately**: ✅ Checked

4. **Click "Create VPC"**

![VPC Creation](images/vpc-create.png)

## Step 6: Verify Your VPC

1. **Check NetBox**: Your VPC should appear in the VPCs list with "Applied" status
2. **Check Kubernetes**: Verify in your cluster:

```bash
kubectl get vpc my-first-vpc
```

Expected output:
```
NAME           AGE
my-first-vpc   1m
```

## 🎉 Congratulations!

You've successfully:

- ✅ Connected NetBox to your Hedgehog fabric
- ✅ Imported existing infrastructure
- ✅ Created and deployed your first VPC

## What's Next?

### Explore More Templates

Try different VPC templates:

- **Web + Database**: Two-tier application setup
- **Three-Tier**: Web, app, and database tiers
- **Custom**: Define your own configuration

### Bulk Operations

Select multiple VPCs and perform bulk operations:

- Apply multiple VPCs at once
- Delete unused VPCs in batch
- Update configurations across multiple resources

### Network Topology

View your network visually:

1. Go to **Hedgehog → Overview → Network Topology**
2. Select your fabric
3. Explore the interactive topology view

### Infrastructure Management

Explore your imported infrastructure:

- **Switches**: View switch details and configurations
- **Connections**: Examine physical connections
- **Servers**: Check server connectivity

## Common Next Steps

### 1. Set Up Additional Fabrics

For staging or development environments:

```yaml
# Staging fabric example
Name: staging-fabric
Description: Staging environment
# ... staging kubeconfig
```

### 2. Create Application VPCs

Use templates for different application types:

```yaml
# Production web application
Name: web-prod
Template: Three-Tier Application
Base Network: 10.200.0.0/16
Starting VLAN: 2000
```

### 3. Monitor and Maintain

- Check fabric health regularly
- Perform periodic syncs
- Monitor VPC utilization
- Clean up unused resources

## Troubleshooting Quick Fixes

### Connection Failed?

1. **Check kubeconfig**: Ensure valid YAML format
2. **Verify network**: NetBox must reach Kubernetes API
3. **Check permissions**: Service account needs appropriate access

### VPC Creation Failed?

1. **Name length**: Must be ≤11 characters
2. **VLAN conflicts**: Check for existing VLAN usage
3. **IP conflicts**: Ensure subnets don't overlap

### Sync Issues?

1. **Re-test connection**: Click "Test Connection" again
2. **Check resources**: Look for conflicting resource names
3. **Manual retry**: Click "Sync Fabric" again

## Getting Help

- 📖 **Full Documentation**: See [User Guide](USER_GUIDE.md)
- 🐛 **Issues**: Report at GitHub Issues
- 💬 **Community**: Join Hedgehog discussions
- 🔧 **Troubleshooting**: Check [troubleshooting guide](USER_GUIDE.md#troubleshooting)

## Quick Reference Card

### Essential Commands

| Task | Location | Action |
|------|----------|--------|
| Add Fabric | Fabrics → Add Fabric | Paste kubeconfig |
| Test Connection | Fabric Detail | Test Connection button |
| Sync Resources | Fabric Detail | Sync Fabric button |
| Create VPC | VPCs → Create VPC | Choose template |
| View Topology | Overview → Topology | Select fabric |
| Bulk Operations | Any list view | Select items + action |

### VPC Templates Quick Reference

| Template | Subnets | Use Case |
|----------|---------|----------|
| Basic | 1 | Simple workloads |
| Web + DB | 2 | Traditional apps |
| Three-Tier | 3 | Enterprise apps |
| Custom | Variable | Special needs |

### Status Indicators

| Color | Status | Meaning |
|-------|--------|---------|
| 🟢 Green | Healthy/Applied | Working correctly |
| 🟡 Yellow | Syncing/Pending | In progress |
| 🔴 Red | Error | Needs attention |

---

**Time to complete**: 5-10 minutes  
**Difficulty**: Beginner  
**Next**: [Full User Guide](USER_GUIDE.md)

*Happy networking with Hedgehog! 🦔*