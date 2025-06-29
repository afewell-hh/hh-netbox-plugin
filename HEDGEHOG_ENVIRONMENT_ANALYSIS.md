# Hedgehog Environment Analysis

## Live Environment Status ✅ ACTIVE

**Environment Assets:**
- ✅ Hedgehog cluster running and operational
- ✅ NetBox instance running on localhost:8000 (netbox-docker)
- ✅ kubectl configured and working
- ✅ All Hedgehog CRDs deployed and functional

## Discovered CRDs

### VPC API CRDs (vpc.githedgehog.com/v1beta1)
- **vpcs**: Virtual Private Cloud configuration
- **externals**: External system connections  
- **externalattachments**: External system attachments to fabric
- **externalpeerings**: VPC to external peering relationships
- **ipv4namespaces**: IPv4 address namespace management
- **vpcattachments**: Workload to VPC attachments
- **vpcpeerings**: VPC to VPC peering relationships

### Wiring API CRDs (wiring.githedgehog.com/v1beta1)
- **connections**: Physical/logical connections (unbundled, bundled, mclag, eslag, fabric, vpc-loopback)
- **servers**: Server connection configurations
- **switches**: Network switch configurations with roles and ASN
- **switchgroups**: Switch redundancy groups
- **vlannamespaces**: VLAN range management
- **serverprofiles**: Server profile templates
- **switchprofiles**: Switch profile templates

### Additional CRDs
- **agents**: Agent configurations
- **catalogs**: Catalog configurations
- **dhcpsubnets**: DHCP subnet management
- **controlnodes**: Fabricator control nodes
- **fabnodes**: Fabric nodes
- **fabricators**: Fabricator configurations

## Real Infrastructure Analysis

### Current Fabric Topology
**Switches (7 total):**
- **Spine switches**: spine-01, spine-02 (role: spine)
- **Leaf switches**: leaf-01 through leaf-05 (role: server-leaf)
- **Redundancy groups**: 
  - mclag-1: leaf-01, leaf-02
  - eslag-1: leaf-03, leaf-04
  - leaf-05: standalone

### Sample Switch Configuration (leaf-01)
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
spec:
  asn: 65101
  role: server-leaf
  profile: vs
  description: "VS-01 MCLAG 1"
  groups: ["mclag-1"]
  ip: 172.30.0.8/21
  protocolIP: 172.30.8.2/32
  vtepIP: 172.30.12.0/32
  redundancy:
    group: mclag-1
    type: mclag
  vlanNamespaces: ["default"]
```

### Connection Types in Use
**22 Connections total:**
- **fabric**: 10 connections (spine-leaf fabric links)
- **mclag**: 2 connections (server multi-homing to MCLAG pair)
- **eslag**: 2 connections (server multi-homing to ESLAG pair) 
- **unbundled**: 4 connections (single link server connections)
- **bundled**: 2 connections (LAG server connections)
- **vpc-loopback**: 5 connections (switch loopback configurations)
- **mclag-domain**: 1 connection (MCLAG domain between leaf-01/leaf-02)

### Sample Connection Configurations

**MCLAG Connection:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
spec:
  mclag:
    links:
    - server: {port: "server-01/enp2s1"}
      switch: {port: "leaf-01/E1/5"}
    - server: {port: "server-01/enp2s2"}
      switch: {port: "leaf-02/E1/5"}
```

**Fabric Connection:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
spec:
  fabric:
    links:
    - leaf: {ip: "172.30.128.1/31", port: "leaf-01/E1/8"}
      spine: {ip: "172.30.128.0/31", port: "spine-01/E1/1"}
    - leaf: {ip: "172.30.128.3/31", port: "leaf-01/E1/9"} 
      spine: {ip: "172.30.128.2/31", port: "spine-01/E1/2"}
```

### Network Namespaces

**IPv4 Namespace (default):**
```yaml
apiVersion: vpc.githedgehog.com/v1beta1
kind: IPv4Namespace
spec:
  subnets: ["10.0.0.0/16"]
```

**VLAN Namespace (default):**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: VLANNamespace
spec:
  ranges:
  - from: 1000
    to: 2999
```

## NetBox Environment

**Status**: ✅ Running on localhost:8000
**Setup**: netbox-docker with standard configuration
**Plugin Configuration**: Available at `/configuration/plugins.py`

**Plugin Installation Path:**
1. Add plugin to `configuration/plugins.py`
2. Add plugin to container requirements
3. Rebuild container or mount plugin volume

## Key Insights for Plugin Development

### 1. Real Schema Validation
- All CRD schemas are now validated against real Hedgehog deployment
- Field names, types, and structures are confirmed
- Connection types and their specific configurations are documented

### 2. Actual Fabric Scale
- 7 switches, 22 connections - realistic lab scale
- Multiple connection types in active use
- Real IP addressing and VLAN ranges

### 3. Namespace Usage
- Default namespace contains all fabric resources
- IPv4 and VLAN namespaces are pre-configured
- No VPCs currently deployed (greenfield for testing)

### 4. Development Opportunities
- Can test plugin against real CRDs immediately
- Can create VPCs and validate full lifecycle
- Can test synchronization with live cluster
- Can validate UI against real data

## Next Steps Priority

1. **Update CRD schemas** with real field structures
2. **Install plugin** in running NetBox instance  
3. **Test Kubernetes client** against live cluster
4. **Create sample VPCs** to test full workflow
5. **Validate UI/UX** with real data

---

**Analysis Date**: 2025-06-29  
**Environment**: Live Hedgehog lab + NetBox docker  
**Status**: Ready for plugin development and testing