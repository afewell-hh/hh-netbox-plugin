# Infrastructure Integration Plan: HCKC & ArgoCD Integration

## Current Infrastructure Status

### What We Have Now
- ✅ **NetBox with HNP**: Working Git sync and CR navigation
- ✅ **Remote HCKC Cluster**: Fresh Hedgehog lab installation
- ✅ **Local ArgoCD Cluster**: Fresh k3s cluster with ArgoCD
- ✅ **Connectivity**: kubectl configured for remote HCKC cluster

### New Cluster Details
- **HCKC Cluster**: Remote hedgehog lab (primary kubectl context)
- **ArgoCD Cluster**: Local k3s container
  - **Username**: `admin`
  - **Password**: `FMQx51F0FAcaVKkI`
  - **Kubeconfig**: `/home/ubuntu/cc/hedgehog-netbox-plugin/hemk/poc_development/kubeconfig/kubeconfig.yaml`

### Integration Challenge
All existing fabric configurations in HNP point to the **old clusters** that crashed. We need to update these to work with the new infrastructure.

## Integration Timeline with Agent Work

### Phase 1: Architectural Cleanup (Current - Week 1-4)
**Infrastructure Impact**: MINIMAL  
**Agent Focus**: Circular dependency resolution, clean architecture  
**Infrastructure Needs**: Basic NetBox functionality for testing  

**Action Required**: ⚠️ **Update Fabric Configuration** to prevent conflicts during architecture work
- Update existing fabric records to point to new clusters
- Verify Git sync still works with new infrastructure
- Ensure no hard-coded references to old cluster endpoints

### Phase 2: Real-Time Monitoring (Week 5-8)
**Infrastructure Impact**: HIGH  
**Agent Focus**: Kubernetes Watch APIs, WebSocket integration  
**Infrastructure Needs**: **Live HCKC cluster with active CRDs**

**Critical Dependencies**:
- ✅ HCKC cluster must be actively running Hedgehog CRDs
- ✅ ArgoCD managing deployment from Git repositories
- ✅ Live CRD state changes for testing real-time monitoring
- ✅ Network connectivity from NetBox to both clusters

### Phase 3: Performance Optimization (Week 9-11)
**Infrastructure Impact**: MEDIUM  
**Agent Focus**: Redis, Celery, database optimization  
**Infrastructure Needs**: **Load testing environment**

**Testing Requirements**:
- Multiple fabrics with substantial CR counts
- Git repositories with realistic YAML file structures
- Concurrent user scenarios for performance testing

### Phase 4: Security Enhancement (Week 12-14)
**Infrastructure Impact**: HIGH  
**Agent Focus**: Encrypted credentials, RBAC, secure integrations  
**Infrastructure Needs**: **Production-like security testing**

**Security Testing Requirements**:
- Multiple Git repositories with different credential types
- ArgoCD integration with proper authentication
- Role-based access testing scenarios

### Phase 5: UI/UX Enhancement (Week 15-18)
**Infrastructure Impact**: MEDIUM  
**Agent Focus**: Advanced UI, real-time dashboards  
**Infrastructure Needs**: **Rich data sets for UI testing**

**UI Testing Requirements**:
- Complex fabric topologies
- Live state changes for real-time UI testing
- Multiple user workflows and scenarios

## Immediate Action Plan

### Week 1-2: Infrastructure Preparation (While Architect Works)
**Timing**: Parallel to current architectural cleanup  
**Goal**: Prepare infrastructure without blocking architectural work

#### Task 1: Update HNP Fabric Configuration
```bash
# Access NetBox admin and update fabric records:
# 1. Update kubernetes server endpoints to new HCKC cluster
# 2. Update Git repository configurations if needed
# 3. Verify ArgoCD connectivity configuration
```

#### Task 2: Verify Cluster Connectivity
```bash
# Test HCKC connectivity
kubectl get nodes
kubectl get crds | grep hedgehog

# Test ArgoCD connectivity  
export KUBECONFIG=/home/ubuntu/cc/hedgehog-netbox-plugin/hemk/poc_development/kubeconfig/kubeconfig.yaml
kubectl get pods -n argocd
```

#### Task 3: Test Current Git Sync with New Infrastructure
- Verify existing Git sync functionality works with new HCKC cluster
- Confirm CRDs can be created/read from new cluster
- Test ArgoCD deployment workflow

### Week 3: HCKC Lab Population
**Goal**: Ensure HCKC cluster has realistic Hedgehog CRDs for testing

#### Deploy Test CRDs to HCKC
- Create sample VPC, Connection, Switch CRDs
- Deploy via ArgoCD from Git repository
- Verify HNP can read these CRDs successfully
- Test Git sync with populated cluster

### Week 4: Integration Testing Framework
**Goal**: Prepare comprehensive testing environment for Phase 2 agent

#### Set Up Automated Testing
- Scripts to populate/clear test data
- ArgoCD application configurations
- Git repository structures for testing
- Network connectivity verification

## Integration Points for Each Agent

### Architectural Cleanup Agent (Current)
**Immediate Needs**: 
- [ ] Update fabric configurations to new cluster endpoints
- [ ] Verify basic connectivity doesn't break architectural work
- [ ] Test that circular dependency fixes don't break cluster connectivity

**Integration Work**:
```python
# Ensure clean architecture doesn't break cluster connectivity
# Test points:
# 1. Fabric model connectivity methods
# 2. Kubernetes client initialization
# 3. Git repository access patterns
```

### Real-Time Monitoring Agent (Week 5-8)
**Critical Infrastructure Needs**:
- [ ] Live HCKC cluster with active CRD deployments
- [ ] ArgoCD actively managing deployments
- [ ] CRD state changes happening for real-time testing
- [ ] Network paths optimized for WebSocket + Kubernetes API calls

**Pre-Phase 2 Setup Required**:
- HCKC cluster populated with realistic CRDs
- ArgoCD applications deployed and sync'd
- Git repositories configured for continuous deployment
- Monitoring endpoints accessible from NetBox host

### Performance Agent (Week 9-11)
**Infrastructure Requirements**:
- [ ] Multiple fabrics with substantial CR counts (100+ CRDs each)
- [ ] Large Git repositories for sync performance testing
- [ ] Redis cluster for caching testing
- [ ] Load testing tools and scenarios

### Security Agent (Week 12-14)
**Security Infrastructure Needs**:
- [ ] Multiple Git repositories with different authentication methods
- [ ] ArgoCD with RBAC configured
- [ ] Certificate management for secure communications
- [ ] Audit logging infrastructure

### UI/UX Agent (Week 15-18)
**Rich Data Requirements**:
- [ ] Complex fabric topologies
- [ ] Real-time data changes for live UI testing
- [ ] Multiple user scenarios and workflows
- [ ] Performance data for dashboard visualization

## Risk Mitigation

### Integration Risks
1. **Cluster Connectivity Issues**: Test all connections before agent phases
2. **ArgoCD Configuration Problems**: Verify GitOps workflow early  
3. **Data Migration Issues**: Backup existing configurations before updates
4. **Network Performance**: Optimize paths for real-time monitoring needs

### Contingency Plans
- **Fallback Clusters**: Keep old cluster details for emergency rollback
- **Local Testing**: Docker-based local clusters for development testing
- **Simplified Scenarios**: Reduced complexity testing if full infrastructure unavailable

## Success Metrics

### Infrastructure Integration Success
- [ ] All fabric configurations updated to new clusters
- [ ] Git sync working with new HCKC cluster
- [ ] ArgoCD deploying CRDs successfully from Git
- [ ] Real-time monitoring ready for live cluster testing
- [ ] Performance testing environment ready
- [ ] Security testing infrastructure prepared

### Quality Gates
- [ ] No regression in existing HNP functionality
- [ ] Improved testing coverage with new infrastructure
- [ ] Reliable deployment pipeline via ArgoCD
- [ ] Comprehensive test data sets available

## Coordination with Current Work

### This Week (While Architect Cleaning Architecture)
**Priority**: Don't block architectural work, but prepare infrastructure
- Update fabric configurations in NetBox
- Test basic connectivity to new clusters
- Verify Git sync still works
- Document new cluster endpoints and credentials

### Next Week (Architecture Work Continues)
**Priority**: Populate test environment
- Deploy comprehensive CRD sets to HCKC
- Configure ArgoCD applications
- Test complete GitOps workflow
- Prepare for real-time monitoring phase

This infrastructure integration ensures each agent has the proper testing environment while maintaining development momentum. The key is updating configurations now while architectural work progresses, then having rich test data ready for the real-time monitoring phase.

---

**Bottom Line**: We can update the cluster configurations this week without blocking the architectural cleanup work, and have everything ready for comprehensive testing when the real-time monitoring agent starts in Week 5.