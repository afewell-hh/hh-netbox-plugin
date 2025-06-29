# Hedgehog NetBox Plugin - Common Workflows

This document provides step-by-step workflows for common tasks and scenarios.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Fabric Management Workflows](#fabric-management-workflows)
3. [VPC Management Workflows](#vpc-management-workflows)
4. [Infrastructure Workflows](#infrastructure-workflows)
5. [Troubleshooting Workflows](#troubleshooting-workflows)
6. [Maintenance Workflows](#maintenance-workflows)

---

## Daily Operations

### Morning Health Check

**Frequency**: Daily  
**Duration**: 5 minutes  
**Purpose**: Ensure all fabrics are healthy and synchronized

#### Steps:

1. **Open Dashboard**
   - Navigate to Hedgehog → Overview → Dashboard
   - Review fabric health cards

2. **Check Status Indicators**
   - 🟢 Healthy fabrics: Note count
   - 🟡 Syncing fabrics: Check if expected
   - 🔴 Error fabrics: Investigate immediately

3. **Review Recent Activity**
   - Check recent activity timeline
   - Verify expected changes are reflected
   - Note any unexpected modifications

4. **Quick Fabric Health**
   - For any error fabrics:
     - Click fabric name → fabric detail
     - Click "Test Connection"
     - If successful, click "Sync Fabric"
     - If failed, escalate to troubleshooting

5. **Resource Count Verification**
   - Compare current counts with expected values
   - Note significant changes for investigation

**Expected Outcome**: All fabrics showing green status, recent activity matches expected changes.

---

## Fabric Management Workflows

### Onboarding a New Hedgehog Installation

**Frequency**: As needed  
**Duration**: 15-30 minutes  
**Purpose**: Add new Hedgehog fabric to NetBox management

#### Prerequisites:
- Hedgehog cluster running and accessible
- Cluster admin access
- NetBox fabric management permissions

#### Steps:

1. **Prepare Service Account**
   ```bash
   # Download service account YAML template
   curl -o hedgehog-sa.yaml https://example.com/hedgehog-sa.yaml
   
   # Apply to cluster
   kubectl apply -f hedgehog-sa.yaml
   
   # Get service account token
   kubectl get secret $(kubectl get sa netbox-hedgehog -o jsonpath='{.secrets[0].name}') -o jsonpath='{.data.token}' | base64 -d
   ```

2. **Create Kubeconfig**
   ```yaml
   apiVersion: v1
   kind: Config
   clusters:
   - cluster:
       server: https://your-cluster:6443
       certificate-authority-data: <CA_DATA>
     name: hedgehog
   contexts:
   - context:
       cluster: hedgehog
       user: netbox-hedgehog
     name: hedgehog-context
   current-context: hedgehog-context
   users:
   - name: netbox-hedgehog
     user:
       token: <SERVICE_ACCOUNT_TOKEN>
   ```

3. **Add Fabric to NetBox**
   - Go to Hedgehog → Fabric Management → Fabrics
   - Click "Add Fabric"
   - Fill details:
     - Name: `production-dc1` (descriptive)
     - Description: Environment and location details
     - Kubeconfig: Paste prepared kubeconfig
   - Click "Create Fabric"

4. **Verify Connection**
   - On fabric detail page, click "Test Connection"
   - Should show success with cluster info
   - Note Kubernetes version and node count

5. **Initial Resource Import**
   - Click "Sync Fabric" button
   - Wait for completion (may take 2-5 minutes)
   - Review imported resources:
     - Switches: Should match physical topology
     - Connections: Physical cable connections
     - VPCs: Any existing VPCs

6. **Validation**
   - Go to Hedgehog → Overview → Network Topology
   - Select new fabric
   - Verify topology matches physical layout
   - Check switch roles and connections

**Success Criteria**: Fabric shows healthy status, all expected resources imported, topology visualization correct.

### Fabric Maintenance and Updates

**Frequency**: Weekly or after cluster changes  
**Duration**: 5-10 minutes  
**Purpose**: Keep NetBox synchronized with cluster state

#### Steps:

1. **Pre-Maintenance Check**
   - Note current resource counts
   - Check for any pending changes
   - Backup current configuration if needed

2. **Connection Health Verification**
   - For each fabric, click "Test Connection"
   - If any failures, troubleshoot before proceeding
   - Update kubeconfig if authentication issues

3. **Synchronization**
   - Click "Sync Fabric" for each fabric
   - Monitor progress messages
   - Note any import/export counts

4. **Post-Sync Validation**
   - Compare resource counts before/after
   - Investigate significant differences
   - Verify new resources appear correctly

5. **Health Dashboard Update**
   - Return to main dashboard
   - Confirm all fabrics show healthy status
   - Update any documentation with changes

**Success Criteria**: All fabrics synchronized, resource counts accurate, no sync errors.

---

## VPC Management Workflows

### Production VPC Deployment

**Frequency**: As needed  
**Duration**: 10-15 minutes  
**Purpose**: Deploy production VPC with proper validation

#### Prerequisites:
- Approved network design
- IP address allocation plan
- VLAN assignment
- Environment access

#### Steps:

1. **Preparation**
   - Verify IP ranges don't conflict with existing VPCs
   - Check VLAN availability in target fabric
   - Confirm template matches requirements

2. **VPC Creation**
   - Go to Hedgehog → VPC API → VPCs
   - Click "Create VPC"
   - Configure:
     - Name: Follow naming convention (≤11 chars)
     - Fabric: Select production fabric
     - Template: Choose appropriate template
     - Base Network: Use allocated IP range
     - Starting VLAN: Use assigned VLAN
     - DHCP: Enable if required
     - Apply Immediately: ✅ for production

3. **Validation in NetBox**
   - VPC appears in list with "Applied" status
   - Subnet configuration matches design
   - No validation errors in details

4. **Validation in Cluster**
   ```bash
   # Check VPC creation
   kubectl get vpc <vpc-name> -o yaml
   
   # Verify subnets
   kubectl describe vpc <vpc-name>
   
   # Check for any events/errors
   kubectl get events --field-selector involvedObject.name=<vpc-name>
   ```

5. **Documentation**
   - Update network documentation
   - Record VPC allocation in IPAM
   - Notify application teams of availability

6. **Testing**
   - Deploy test workload if applicable
   - Verify connectivity within VPC
   - Test DHCP functionality if enabled

**Success Criteria**: VPC deployed successfully, validation tests pass, documentation updated.

### VPC Lifecycle Management

**Frequency**: Ongoing  
**Duration**: 5-10 minutes per VPC  
**Purpose**: Manage VPC through lifecycle stages

#### Development to Staging Promotion

1. **Export Configuration**
   - Go to development VPC detail page
   - Copy configuration details
   - Note any customizations made

2. **Create Staging VPC**
   - Use same template and configuration
   - Adjust naming for staging environment
   - Use staging-appropriate IP ranges
   - Deploy to staging fabric

3. **Validation**
   - Test application deployment
   - Verify configuration matches development
   - Document any differences

#### Staging to Production Promotion

1. **Final Review**
   - Confirm all testing completed
   - Review security implications
   - Get necessary approvals

2. **Production Deployment**
   - Use production IP ranges
   - Deploy during maintenance window
   - Monitor deployment closely

3. **Cleanup**
   - Keep staging VPC for rollback
   - Update documentation
   - Notify stakeholders

#### VPC Retirement

1. **Preparation**
   - Verify no active workloads
   - Backup any necessary data
   - Get approval for deletion

2. **Deletion Process**
   - Go to VPC detail page
   - Click "Delete" button
   - Confirm deletion (removes from cluster too)

3. **Cleanup**
   - Update IP allocation records
   - Update documentation
   - Reclaim VLAN if applicable

**Success Criteria**: VPC transitions completed successfully, no service disruption, documentation current.

---

## Infrastructure Workflows

### Switch Configuration Management

**Frequency**: As needed  
**Duration**: Variable  
**Purpose**: Manage switch configurations and roles

#### Switch Role Updates

1. **Planning**
   - Review current topology
   - Plan role changes
   - Consider impact on connections

2. **Bulk Role Update**
   - Go to Hedgehog → Wiring API → Switches
   - Filter to target switches
   - Select multiple switches
   - Choose "Update Role" action
   - Select new role
   - Apply changes

3. **Validation**
   - Check topology view for updates
   - Verify connections remain valid
   - Test network connectivity

#### New Switch Integration

1. **Physical Installation**
   - Install switch in fabric
   - Cable according to design
   - Power on and configure

2. **Sync Discovery**
   - Go to fabric detail page
   - Click "Sync Fabric"
   - New switch should appear automatically

3. **Configuration Verification**
   - Go to switch detail page
   - Verify role assignment
   - Check connection details
   - Confirm interface status

**Success Criteria**: Switch configurations accurate, topology reflects reality, no connectivity issues.

### Connection Management

**Frequency**: Ongoing  
**Duration**: 5-15 minutes  
**Purpose**: Manage physical and logical connections

#### Cable Management Workflow

1. **Planning Phase**
   - Document cable plan
   - Verify port availability
   - Check connection types needed

2. **Physical Implementation**
   - Install cables according to plan
   - Label cables appropriately
   - Update cable management system

3. **NetBox Synchronization**
   - Perform fabric sync
   - Verify new connections appear
   - Check connection types are correct

4. **Validation**
   - Check interface status in switches
   - Verify link aggregation if applicable
   - Test connectivity end-to-end

#### Connection Type Conversions

1. **Assessment**
   - Identify connections to convert
   - Plan maintenance window
   - Verify compatibility

2. **Bulk Conversion**
   - Go to Connections list
   - Select target connections
   - Choose "Update Type" action
   - Select new connection type
   - Apply changes

3. **Deployment**
   - Changes applied to cluster
   - Monitor for configuration errors
   - Verify new type is active

**Success Criteria**: Connections accurately reflect physical reality, types correct, no connectivity loss.

---

## Troubleshooting Workflows

### Connection Failures

**Symptoms**: Fabric shows error status, connection tests fail

#### Diagnosis Steps

1. **Basic Connectivity**
   ```bash
   # Test basic network connectivity
   ping <kubernetes-api-server>
   
   # Test specific port
   telnet <kubernetes-api-server> 6443
   ```

2. **Authentication Issues**
   ```bash
   # Test with kubeconfig
   kubectl --kubeconfig=<path> cluster-info
   
   # Check token validity
   kubectl --kubeconfig=<path> auth can-i get pods
   ```

3. **Permission Verification**
   ```bash
   # Check specific permissions
   kubectl auth can-i get vpcs.vpc.githedgehog.com
   kubectl auth can-i create switches.wiring.githedgehog.com
   ```

#### Resolution Steps

1. **Network Issues**
   - Verify NetBox can reach Kubernetes API
   - Check firewall rules
   - Validate DNS resolution

2. **Authentication Issues**
   - Regenerate service account token
   - Update kubeconfig in NetBox
   - Test connection again

3. **Permission Issues**
   - Review service account ClusterRole
   - Apply updated permissions
   - Re-test operations

### VPC Deployment Failures

**Symptoms**: VPC stuck in "Error" status, deployment fails

#### Diagnosis Steps

1. **Check VPC Status**
   ```bash
   kubectl get vpc <vpc-name> -o yaml
   kubectl describe vpc <vpc-name>
   ```

2. **Review Events**
   ```bash
   kubectl get events --field-selector involvedObject.name=<vpc-name>
   ```

3. **Validate Configuration**
   - Check VPC name length (≤11 chars)
   - Verify IP ranges don't overlap
   - Confirm VLAN availability

#### Resolution Steps

1. **Name Issues**
   - Edit VPC in NetBox
   - Shorten name to ≤11 characters
   - Re-apply to cluster

2. **Resource Conflicts**
   - Identify conflicting resources
   - Choose alternative IP ranges/VLANs
   - Update configuration

3. **Cluster Issues**
   - Check Hedgehog controller logs
   - Verify admission webhooks
   - Review cluster resource limits

### Sync Failures

**Symptoms**: Fabric sync fails, resources out of sync

#### Diagnosis Steps

1. **Check Fabric Health**
   - Test connection first
   - Review error messages
   - Check recent changes

2. **Resource Conflicts**
   - Look for naming conflicts
   - Check for manual cluster changes
   - Verify resource ownership

#### Resolution Steps

1. **Clean Sync**
   - Fix any connection issues
   - Resolve naming conflicts
   - Retry sync operation

2. **Manual Intervention**
   - Identify problematic resources
   - Manually align NetBox/cluster
   - Re-sync to verify

**Success Criteria**: Issues resolved, sync completes successfully, resources consistent.

---

## Maintenance Workflows

### Weekly Maintenance

**Frequency**: Weekly  
**Duration**: 30-60 minutes  
**Purpose**: Ensure system health and consistency

#### Checklist

1. **Health Assessment**
   - [ ] Review fabric status dashboard
   - [ ] Check all fabrics are healthy
   - [ ] Investigate any error conditions

2. **Synchronization**
   - [ ] Sync all fabrics
   - [ ] Verify resource counts
   - [ ] Check for new/removed resources

3. **Resource Cleanup**
   - [ ] Review unused VPCs
   - [ ] Clean up test resources
   - [ ] Update documentation

4. **Performance Review**
   - [ ] Check operation response times
   - [ ] Review resource utilization
   - [ ] Monitor growth trends

5. **Security Review**
   - [ ] Check service account access
   - [ ] Review user permissions
   - [ ] Verify token rotation if needed

### Monthly Maintenance

**Frequency**: Monthly  
**Duration**: 2-4 hours  
**Purpose**: Comprehensive system maintenance

#### Checklist

1. **Comprehensive Review**
   - [ ] Full fabric inventory
   - [ ] Resource utilization analysis
   - [ ] Capacity planning review

2. **Documentation Update**
   - [ ] Update network diagrams
   - [ ] Review naming conventions
   - [ ] Update operational procedures

3. **Security Maintenance**
   - [ ] Rotate service account tokens
   - [ ] Review access permissions
   - [ ] Update security documentation

4. **Performance Optimization**
   - [ ] Review bulk operation efficiency
   - [ ] Optimize resource queries
   - [ ] Clean up historical data

5. **Disaster Recovery**
   - [ ] Test backup procedures
   - [ ] Verify recovery processes
   - [ ] Update DR documentation

### Quarterly Reviews

**Frequency**: Quarterly  
**Duration**: Half day  
**Purpose**: Strategic planning and major updates

#### Checklist

1. **Strategic Review**
   - [ ] Assess plugin adoption
   - [ ] Review workflow efficiency
   - [ ] Plan feature enhancements

2. **Architecture Review**
   - [ ] Evaluate fabric topology
   - [ ] Review integration points
   - [ ] Plan capacity upgrades

3. **Process Improvement**
   - [ ] Review workflow effectiveness
   - [ ] Identify automation opportunities
   - [ ] Update training materials

4. **Technology Updates**
   - [ ] Plan plugin updates
   - [ ] Review Hedgehog upgrades
   - [ ] Assess NetBox updates

**Success Criteria**: All maintenance completed without issues, documentation current, systems optimized.

---

## Workflow Quick Reference

### Emergency Procedures

| Issue | Immediate Action | Follow-up |
|-------|------------------|-----------|
| Fabric Offline | Test connection, check network | Investigate root cause |
| VPC Deploy Fail | Check logs, validate config | Fix and redeploy |
| Sync Errors | Retry sync, check conflicts | Manual reconciliation |
| Performance Slow | Check resource usage | Optimize or scale |

### Escalation Matrix

| Severity | Response Time | Escalation |
|----------|---------------|------------|
| Critical | 15 minutes | Operations manager |
| High | 1 hour | Senior engineer |
| Medium | 4 hours | Team lead |
| Low | Next business day | Standard queue |

### Contact Information

- **Operations Team**: ops@company.com
- **Network Team**: network@company.com
- **Security Team**: security@company.com
- **24/7 Hotline**: +1-555-NETOPS

---

*This document should be customized for your organization's specific procedures and requirements.*