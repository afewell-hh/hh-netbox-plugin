# Hedgehog Wiring Schema Requirements for DIET

**Research Date:** 2025-12-27
**Purpose:** Inform DIET data modeling to support Hedgehog wiring YAML (Connection CRD) generation

---

## Executive Summary

Hedgehog Open Network Fabric uses Kubernetes Custom Resource Definitions (CRDs) to represent all network infrastructure as a "Wiring Diagram" - a YAML file that defines switches, servers, and connections between them. DIET must capture sufficient data in NetBox to generate valid Connection CRDs that Hedgehog's `hhfab` tooling can process.

**Key Finding:** Hedgehog validates all configurations against SwitchProfile definitions. NetBox MUST store or reference accurate switch profile data including port groups, breakout modes, and supported speeds.

---

## 1. Connection CRD Schema (wiring.githedgehog.com/v1beta1)

### 1.1 Overview

All connections use the same base structure:

```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: {descriptive-name}
  namespace: default
spec:
  {connection-type}:
    # Type-specific configuration
```

**Naming Convention:** `{device}--{connection-type}--{switch(es)}` using double hyphens as separators.

### 1.2 Server Connection Types

#### Unbundled
Single port connection from server to switch.

**Required Fields:**
- `spec.unbundled.link.server.port` (format: `server-name/interface`)
- `spec.unbundled.link.switch.port` (format: `switch-name/port`)

**Example:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: server-4--unbundled--s5248-02
spec:
  unbundled:
    link:
      server:
        port: server-4/enp2s1
      switch:
        port: s5248-02/E1/1
```

**Validation:**
- Switch port MUST exist in SwitchProfile
- Server port validated for uniqueness only

#### Bundled
Multiple ports to single switch (LAG/port channel).

**Required Fields:**
- `spec.bundled.links[]` (array of link objects)
- Each link requires `server.port` and `switch.port`

**Requirements:**
- Server interfaces MUST be configured for 802.3ad LACP
- All ports on same switch

**Example:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: server-2--bundled--s5248-01
spec:
  bundled:
    links:
      - server:
          port: server-2/enp2s1
        switch:
          port: s5248-01/E1/2
      - server:
          port: server-2/enp2s2
        switch:
          port: s5248-01/E1/3
```

#### MCLAG
Dual-homing across switch pair with redundancy.

**Required Fields:**
- `spec.mclag.links[]` with server and switch port pairs

**Requirements:**
- Switches MUST be in `mclag` type redundancy group
- MCLAG switches MUST have the same `spec.ASN` and `spec.VTEPIP`
- Requires `mclag-domain` connection between switches (see below)
- Server interfaces MUST be configured for 802.3ad LACP

**Example:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: server-1--mclag--s5248-01--s5248-02
spec:
  mclag:
    links:
      - server:
          port: server-1/enp2s1
        switch:
          port: s5248-01/E1/1
      - server:
          port: server-1/enp2s2
        switch:
          port: s5248-02/E1/1
```

#### ESLAG
Multi-homing across 2-4 switches (Enhanced Server LAG).

**Required Fields:**
- `spec.eslag.links[]` with server and switch port pairs

**Requirements:**
- Switches in `eslag` type redundancy group
- Server interfaces MUST be configured for 802.3ad LACP
- Supports 2-4 switches (vs MCLAG which is exactly 2)
- No other special configuration required (simpler than MCLAG)

**Example:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: server-1--eslag--s5248-01--s5248-02
spec:
  eslag:
    links:
      - server:
          port: server-1/enp2s1
        switch:
          port: s5248-01/E1/1
      - server:
          port: server-1/enp2s2
        switch:
          port: s5248-02/E1/1
```

### 1.3 Switch-to-Switch Connection Types

#### Fabric
Spine-to-leaf connections (the backbone of the fabric).

**Required Fields:**
- `spec.fabric.links[]`
- Each link requires:
  - `leaf.ip` (CIDR notation, e.g., 172.30.30.1/31)
  - `leaf.port` (e.g., s5248-01/E1/18)
  - `spine.ip` (CIDR notation, e.g., 172.30.30.0/31)
  - `spine.port` (e.g., s5232-01/E1/1)

**Topology Rules:**
- Standard spine-leaf: Each leaf MUST connect to every spine
- Each spine MUST connect to every leaf
- Leaf switches cannot connect to each other (use mesh for that)
- Spine switches cannot connect to each other

**Example:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: s5232-01--fabric--s5248-01
spec:
  fabric:
    links:
      - leaf:
          ip: 172.30.30.1/31
          port: s5248-01/E1/18
        spine:
          ip: 172.30.30.0/31
          port: s5232-01/E1/1
      - leaf:
          ip: 172.30.30.3/31
          port: s5248-01/E1/19
        spine:
          ip: 172.30.30.2/31
          port: s5232-01/E1/2
```

**Note:** IP addresses in wiring diagram are for fabric underlay only. The `hhfab build` process handles IP/ASN assignment for overlay.

#### Mesh
Direct leaf-to-leaf connections without spine.

**Required Fields:**
- `spec.mesh.links[]`
- Each link requires:
  - `leaf1.ip`, `leaf1.port`
  - `leaf2.ip`, `leaf2.port`

**Limitations:**
- "Mesh connections have major limitations on TH5-based devices"
- Use for collapsed core topology only

#### MCLAG-Domain
Defines MCLAG switch pair with session and peer links.

**Required Fields:**
- `spec.mclagDomain.peerLinks[]` (data plane links)
- `spec.mclagDomain.sessionLinks[]` (control plane links)
- Each requires `switch1.port` and `switch2.port`

**Requirements:**
- Required for ANY MCLAG server connections
- Default configuration: 2 peer links + 2 session links
- Both switches MUST reference the same `SwitchGroup` with `type: mclag`

**Example:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: s5248-01--mclag-domain--s5248-02
spec:
  mclagDomain:
    peerLinks:
      - switch1:
          port: s5248-01/E1/12
        switch2:
          port: s5248-02/E1/12
      - switch1:
          port: s5248-01/E1/13
        switch2:
          port: s5248-02/E1/13
    sessionLinks:
      - switch1:
          port: s5248-01/E1/14
        switch2:
          port: s5248-02/E1/14
      - switch1:
          port: s5248-01/E1/15
        switch2:
          port: s5248-02/E1/15
```

### 1.4 External Connectivity

#### StaticExternal
Direct connections to external systems (DHCP, NTP, non-BGP).

**Required Fields:**
- `spec.staticExternal.link.switch.port`
- `spec.staticExternal.link.switch.ip` (CIDR)

**Optional Fields:**
- `vlan` (0 means no VLAN configured)
- `subnets[]` (routes list)
- `nextHop` (next hop IP)
- `withinVPC` (VPC name for scoped access)

**Example:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: dhcp-server--static--s5248-01
spec:
  staticExternal:
    link:
      switch:
        port: s5248-01/E1/20
        ip: 10.0.0.1/24
    vlan: 100
    subnets:
      - 10.0.0.0/24
```

#### External
BGP peering to edge/provider routers.

**Required Fields:**
- `spec.external.link.switch.port`

**Use Case:** BGP peering for external connectivity

#### VPCLoopback
Physical cable with both ends on same switch (workaround for local VPC peering).

**Requirements:**
- Required for local VPC peering on older Broadcom hardware
- **DEPRECATED** in newer releases with L3VNI VPC mode support
- Suggested but not required to use adjacent ports
- Default: 2 loopbacks per leaf

**Bandwidth:** Traffic between VPCs limited by loopback port speed

**Example:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: s5248-01--vpc-loopback--1
spec:
  vpcLoopback:
    links:
      - switch1:
          port: s5248-01/E1/54
        switch2:
          port: s5248-01/E1/55
```

### 1.5 Gateway Connections

#### Gateway
Connections between gateway and spine (or leaf in mesh topology).

**Required Fields:**
- `spec.gateway.links[]`
- Each link requires:
  - `gateway.ip` (CIDR)
  - `gateway.port`
  - `switch.ip` (CIDR)
  - `switch.port`

**Note:** In mesh topology, connections are between gateway and leaf nodes.

---

## 2. Hedgehog Fabric Model

### 2.1 Topology Types

**Supported Topologies:**
1. **CLOS/Leaf-Spine** (standard)
   - 2+ spine switches
   - 2+ leaf switches
   - All-to-all connectivity between spines and leaves

2. **Collapsed Core** (mesh)
   - Leaf-to-leaf connections without spines
   - Limited scalability
   - TH5 hardware limitations

### 2.2 Switch Roles

Hedgehog defines the following switch roles:

- **`spine`**: Aggregation layer, connects to all leaves
- **`server-leaf`**: Access layer for servers only
- **`border-leaf`**: External connectivity (BGP peering)
- **`mixed-leaf`**: Both server and border functionality

**Role Assignment:** Configured in Switch object `spec.role` field

### 2.3 Switch Objects

**Required Fields:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: switch-name
spec:
  profile: switch-profile-name  # MANDATORY reference to SwitchProfile
  boot:
    serial: XXX  # Serial number OR MAC address (at least one required)
    mac: YYY
  role: server-leaf | spine | border-leaf | mixed-leaf
```

**Optional Configuration Fields:**
- `asn`: Autonomous System Number for BGP
- `ip`: Management IP (accessible from Control Node)
- `protocolIP`: BGP router ID
- `vtepIP`: VXLAN Tunnel Endpoint address
- `vlanNamespaces`: Available VLANs for server attachment
- `portBreakouts`: Port splitting configuration (e.g., `{"E1/55": "4x25G"}`)
- `portGroupSpeeds`: Speed for port groups (e.g., `{"1": "10G"}`)
- `portSpeeds`: Individual port speeds (e.g., `{"E1/1": "25G"}`)
- `groups`: References to `SwitchGroup` objects
- `redundancy`: Redundancy group membership with type (`mclag` or `eslag`)

### 2.4 Redundancy Groups (SwitchGroup)

**MCLAG Redundancy Group:**
- Exactly 2 switches
- Switches MUST have same ASN
- Switches MUST have same VTEP IP
- Requires `mclag-domain` connection

**ESLAG Redundancy Group:**
- 2-4 switches
- Simpler configuration than MCLAG
- No special ASN/VTEP requirements

**Example:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: SwitchGroup
metadata:
  name: mclag-leaf-pair-1
spec:
  type: mclag
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: s5248-01
spec:
  profile: dell-s5248f-on
  redundancy:
    group: mclag-leaf-pair-1
    type: mclag
  asn: 65001
  vtepIP: 10.99.0.1
```

### 2.5 Server Objects

Minimal configuration required:

```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Server
metadata:
  name: server-name
spec:
  description: optional description
```

Servers connect to switches via `Connection` objects (unbundled, bundled, mclag, eslag).

### 2.6 VLANNamespace and IPv4Namespace

**VLANNamespace:** Defines non-overlapping VLAN ranges for server attachment.

```yaml
apiVersion: wiring.githedgehog.com/v1alpha2
kind: VLANNamespace
metadata:
  name: default
spec:
  ranges:
    - from: 1000
      to: 2999
```

**IPv4Namespace:** Defines non-overlapping IPv4 ranges for VPC subnets.

```yaml
apiVersion: vpc.githedgehog.com/v1beta1
kind: IPv4Namespace
metadata:
  name: default
spec:
  subnets:
    - 10.10.0.0/16
```

**Switches reference VLANNamespaces** in their `spec.vlanNamespaces` field.

---

## 3. Port Naming & Breakouts

### 3.1 Hedgehog Port Naming Format

**General Format:** `E<asic-or-chassis-number>/<port-number>[/<breakout>][.<subinterface>]`

**Examples:**
- `E1/1` - Standard port
- `E1/55/1` - First breakout of port 55
- `E1/55/2` - Second breakout of port 55

### 3.2 Breakout Naming Rules

- Breakout number starts from 1
- Only applies to breakout ports
- Uses consecutive numbers independent of lane allocation
- Omitting breakout number allowed for first breakout (E1/55 same as E1/55/1)

**Example Breakout Configuration:**
If E1/1 configured for 4x25G breakout:
- E1/1 or E1/1/1 (first breakout)
- E1/1/2 (second breakout)
- E1/1/3 (third breakout)
- E1/1/4 (fourth breakout)

### 3.3 Server Interface Names

Server ports use standard Linux interface naming:
- `enp2s1`, `enp2s2`, etc.
- Format: `server-name/interface` (e.g., `server-1/enp2s1`)

**Validation:** Server ports validated for uniqueness only (no profile enforcement)

### 3.4 Gateway Interface Names

Gateway interface names must be accurate; NOS port names are NOT supported.

### 3.5 Switch Port Validation

**Critical:** Only switch profile-defined port names are valid for switches.

All port names MUST exist in the referenced `SwitchProfile` definition.

---

## 4. Switch Models and Profiles

### 4.1 SwitchProfile CRD

**Purpose:** Defines switch model, supported features, and port capabilities.

**SwitchProfile defines:**
- Switch model and capabilities
- Port groups with available speeds
- Breakout port configurations
- Supported features for validation

**Usage in Wiring Diagram:**
```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: s5248-01
spec:
  profile: dell-s5248f-on  # MANDATORY reference
```

### 4.2 Port Configuration Types in SwitchProfile

#### Type 1: Non-breakout, Non-group Ports
- Reference to port profile with default/available speeds
- Configurable via `portSpeeds` in Switch object
- Example: `portSpeeds: {"E1/1": "25G"}`

#### Type 2: Port Groups
- Non-breakout, not directly configurable
- Reference to port group → port profile with speeds
- Speed applies to ENTIRE group
- Configurable via `portGroupSpeeds` in Switch object
- Example: If group 1 contains E1/1-E1/4, setting `{"1": "10G"}` applies 10G to all 4 ports

#### Type 3: Breakout Ports
- Reference to port profile with default/available breakout modes
- Configurable via `portBreakouts` in Switch object
- Example: `portBreakouts: {"E1/55": "4x25G"}`

### 4.3 Supported Hardware Vendors

**Certified Vendors:**
- Celestica
- Cisco
- Dell
- Edgecore
- NVIDIA
- Supermicro

**Certified Edgecore Models:**
- DCS204
- DCS203
- DCS501
- EPS203

**Silicon Partners:**
- NVIDIA
- Broadcom

**Custom Certification:** 1-2 months following receipt of test equipment

### 4.4 Virtual Lab (VLAB) Profile

**Profile Name:** `vs` (SONiC Virtual Switch)

**Default VLAB Topology:**
- 2 spines
- 2 MCLAG leaves
- 1 non-MCLAG leaf
- 6 servers
- 1 Hedgehog control node

**Customization Flags:**
- `--spines-count`: Number of spines
- `--mclag-leafs-count`: Number of MCLAG leaves

### 4.5 Can We Import Switch Profile Data?

**Recommendation: YES, with caveats**

**Approach 1: Reference Hedgehog Profiles**
- Store mapping of NetBox device types to Hedgehog SwitchProfile names
- DIET generates wiring YAML referencing Hedgehog's built-in profiles
- **Pros:** No duplication, always up-to-date with Hedgehog
- **Cons:** Requires Hedgehog installation to validate, limited to certified hardware

**Approach 2: Import Profile Data into NetBox**
- Parse Hedgehog SwitchProfile CRDs and import into NetBox
- Store port groups, breakout modes, speeds in NetBox device type
- **Pros:** NetBox has full validation capability, works offline
- **Cons:** Must maintain sync with Hedgehog updates

**Approach 3: Hybrid**
- Store SwitchProfile name reference in NetBox device type
- Import only essential validation data (port names, groups)
- Delegate detailed validation to Hedgehog
- **Recommended for MVP**

**Implementation Notes:**
- Hedgehog SwitchProfiles likely stored in githedgehog/fabric repository
- CRD definitions in `api/meta/` or similar directory
- Could be fetched via GitHub API or bundled with plugin
- Consider adding `hedgehog_switch_profile` custom field to NetBox Device Type

---

## 5. Validation & Constraints

### 5.1 Port Validation Rules

**Switch Ports:**
- MUST exist in referenced SwitchProfile
- MUST match exact naming convention (E1/1, E1/55/2, etc.)
- Cannot use NOS or other port names
- Breakout ports only valid if breakout mode configured in Switch object

**Server Ports:**
- Validated for uniqueness only
- No profile enforcement
- Format: `server-name/interface`

**Gateway Ports:**
- Must use accurate interface names
- NOS port names NOT supported

### 5.2 Connection Validation Rules

**General:**
- Connection `metadata.name` must be unique within namespace
- Connection type field is mutually exclusive (only one type per Connection)

**MCLAG Specific:**
- Both switches MUST be in same redundancy group
- Redundancy group MUST have `type: mclag`
- Switches MUST have identical `spec.ASN`
- Switches MUST have identical `spec.VTEPIP`
- Requires corresponding `mclag-domain` connection between switches

**ESLAG Specific:**
- 2-4 switches required
- All switches MUST be in same redundancy group
- Redundancy group MUST have `type: eslag`

**Fabric Specific:**
- Requires IP addresses in CIDR notation
- Each spine-leaf pair needs Connection object
- Standard topology: All leaves connect to all spines

### 5.3 Fabric Topology Rules

**Standard Spine-Leaf Rules:**
1. Each leaf switch MUST connect to every spine switch
2. Each spine switch MUST connect to every leaf switch
3. Leaf switches CANNOT connect to each other (use mesh for that)
4. Spine switches CANNOT connect to each other

**Verification:** All-to-all connectivity matrix must be complete

### 5.4 Redundancy Group Rules

**MCLAG:**
- Exactly 2 switches (no more, no less)
- Both switches MUST be same model/profile (recommended)
- Same ASN and VTEP IP (REQUIRED)

**ESLAG:**
- 2-4 switches
- Should be same model/profile (recommended)
- No ASN/VTEP constraints

### 5.5 Switch Configuration Constraints

**Port Breakouts:**
- Can only configure ports marked as breakout-capable in SwitchProfile
- Breakout mode MUST be in port's available modes list

**Port Group Speeds:**
- Speed applies to ALL ports in group
- Cannot configure individual ports in a group
- Speed MUST be in group's available speeds list

**Port Speeds:**
- Only for non-group, non-breakout ports
- Speed MUST be in port's available speeds list

### 5.6 Namespace Constraints

**VLANNamespace:**
- Ranges MUST NOT overlap within namespace
- Switches can reference multiple namespaces

**IPv4Namespace:**
- Subnets MUST NOT overlap within namespace
- VPCs pick subnets from their namespace

---

## 6. hhfab Tooling

### 6.1 hhfab Overview

**Purpose:** Operational tool to generate, initiate, and maintain the fabric software appliance

**Capabilities:**
- Generate environment-specific image with baked-in configuration
- Process wiring diagram YAML files
- Validate wiring against switch profiles
- Auto-assign IP addresses and ASN numbers
- Generate fabric configuration

### 6.2 hhfab Commands

**Initialize:**
```bash
hhfab init --preset lab --dev --wiring file1.yaml --wiring file2.yaml
```
- Can specify multiple wiring files
- Creates default topology if no wiring specified (2 spines, 2 MCLAG leaves, 1 non-MCLAG leaf)

**Build:**
```bash
hhfab build
```
- Creates IP addresses and ASN numbers from wiring diagram
- Wiring diagram has NO IP/ASN; build step generates them

**VLAB Generate:**
```bash
hhfab vlab gen
```
- Generates topology for virtual lab
- Customize with `--spines-count` and `--mclag-leafs-count` flags

**Diagram Generation:**
```bash
hhfab diagram
```
- Generates Draw.io, Graphviz (dot), and Mermaid diagrams from wiring

### 6.3 What hhfab Validates

**Port Existence:**
- All switch ports exist in SwitchProfile
- Port naming matches conventions

**Topology Completeness:**
- Spine-leaf all-to-all connectivity (likely)
- MCLAG domain presence for MCLAG connections

**Configuration Consistency:**
- MCLAG switches have matching ASN/VTEP
- Redundancy group types match connection types

**Profile Constraints:**
- Breakout modes are valid for port
- Speeds are valid for port/group

### 6.4 What Errors hhfab Catches

Based on validation rules:
- Invalid port names
- Missing SwitchProfile references
- Breakout configuration on non-breakout ports
- Speed configuration outside available range
- MCLAG ASN/VTEP mismatch
- Missing mclag-domain connection for MCLAG servers

### 6.5 Flexibility in Wiring Definitions

**Flexible:**
- Number of fabric links per spine-leaf pair
- Server connection types (unbundled, bundled, mclag, eslag)
- Port selection (any valid port from profile)

**Inflexible:**
- Port naming (MUST match profile exactly)
- MCLAG requires domain connection
- Spine-leaf all-to-all connectivity (standard topology)
- Switch profile reference (MANDATORY)

---

## 7. NetBox Data Requirements for DIET

### 7.1 Required NetBox Objects

**To generate valid wiring YAML, NetBox MUST contain:**

#### Devices (Switches)
- Device name → Switch `metadata.name`
- Device type → SwitchProfile reference
- Device role → Switch `spec.role` (spine, server-leaf, border-leaf, mixed-leaf)
- Serial number → Switch `spec.boot.serial`
- Primary MAC → Switch `spec.boot.mac`
- Custom fields:
  - `hedgehog_asn` → Switch `spec.asn`
  - `hedgehog_vtep_ip` → Switch `spec.vtepIP`
  - `hedgehog_protocol_ip` → Switch `spec.protocolIP`
  - `hedgehog_switch_profile` → SwitchProfile name override

#### Devices (Servers)
- Device name → Server `metadata.name`
- Description → Server `spec.description`

#### Device Types
- Manufacturer + model → SwitchProfile name mapping
- Custom fields:
  - `hedgehog_switch_profile` → Hedgehog profile name
  - `port_naming_scheme` → Validation data

#### Interfaces (Switch Ports)
- Interface name → MUST match SwitchProfile convention (E1/1, E1/55/2)
- Interface type → Determines if breakout capable
- Enabled status → Available for connections
- Custom fields:
  - `port_group` → Port group membership
  - `breakout_mode` → Configured breakout (4x25G, etc.)
  - `port_speed` → Configured speed

#### Interfaces (Server Ports)
- Interface name → Linux interface name (enp2s1)
- Enabled status → Available for connections

#### Cables
- A-side device + interface
- B-side device + interface
- Cable type → Determines connection type (with DIET logic)

### 7.2 DIET-Specific Data Models

**TopologyPlan:**
- Name, description
- Fabric type (clos, collapsed-core)
- IP allocation settings
- VLAN allocation settings

**FabricSwitch:**
- Foreign key to NetBox Device
- Switch role (spine, server-leaf, border-leaf, mixed-leaf)
- ASN
- VTEP IP
- Protocol IP
- Redundancy group membership
- VLAN namespaces

**FabricServer:**
- Foreign key to NetBox Device
- Connection type (unbundled, bundled, mclag, eslag)

**FabricConnection:**
- Foreign key to TopologyPlan
- Connection type (unbundled, bundled, mclag, eslag, fabric, mclag-domain, etc.)
- Validation status
- Generated YAML snippet

**RedundancyGroup:**
- Name
- Type (mclag, eslag)
- Member switches
- Shared ASN (for MCLAG)
- Shared VTEP IP (for MCLAG)

**SwitchPortGroup:**
- Foreign key to Device Type
- Group number/name
- Member ports
- Available speeds
- Configured speed

### 7.3 Derived/Calculated Data

DIET must calculate or infer:

**Connection Types:**
- From NetBox cables + device roles + redundancy groups
- Logic: If cable between server and switch → server connection
- If cable between spine and leaf → fabric connection
- If cable between MCLAG pair members → mclag-domain connection

**Fabric Links:**
- All spine-to-leaf cables grouped by switch pair
- IP address assignment (DIET assigns, not NetBox)

**MCLAG Domain Links:**
- Identify peer links vs session links
- Default: First 2 links = peer, next 2 = session
- Or use custom field to designate

**VPC Loopback:**
- Cables with both ends on same switch
- Adjacent ports preferred
- DEPRECATED in new releases

### 7.4 Validation Data Needed

**Switch Port Validation:**
- List of valid port names from SwitchProfile
- Port group memberships
- Breakout capabilities
- Available speeds/breakout modes

**Options for obtaining this data:**
1. Import from Hedgehog SwitchProfile CRDs
2. Manual configuration in NetBox device types
3. Query Hedgehog API at runtime (if available)
4. Bundle with plugin (static data files)

**Recommendation:** Hybrid approach
- Store SwitchProfile name in NetBox device type
- Import basic port naming patterns for validation
- Delegate detailed validation to hhfab

---

## 8. Validation Rules DIET Must Enforce

### 8.1 Pre-Generation Validation

**Before generating wiring YAML, DIET MUST validate:**

#### Switch Configuration
- [ ] Every switch has a SwitchProfile reference (device type → profile mapping)
- [ ] Every switch has serial number OR MAC address
- [ ] MCLAG switches in same redundancy group have matching ASN
- [ ] MCLAG switches in same redundancy group have matching VTEP IP
- [ ] Switch role is valid (spine, server-leaf, border-leaf, mixed-leaf)

#### Port Configuration
- [ ] All switch ports match SwitchProfile naming convention
- [ ] Breakout ports only configured if port is breakout-capable
- [ ] Breakout modes are valid for the port
- [ ] Port speeds are valid for the port/group
- [ ] Port groups have consistent speed across all member ports

#### Redundancy Groups
- [ ] MCLAG groups have exactly 2 switches
- [ ] ESLAG groups have 2-4 switches
- [ ] All switches in group are same model/profile (warning if not)

#### Connections
- [ ] MCLAG server connections reference switches in same MCLAG redundancy group
- [ ] MCLAG redundancy group has corresponding mclag-domain connection
- [ ] MCLAG domain has peer links and session links
- [ ] ESLAG server connections reference switches in same ESLAG redundancy group
- [ ] Fabric connections are between spine and leaf roles
- [ ] No leaf-to-leaf or spine-to-spine fabric connections (unless mesh)

#### Topology Completeness
- [ ] All-to-all connectivity: Every leaf connects to every spine
- [ ] All-to-all connectivity: Every spine connects to every leaf
- [ ] Spine-leaf pairs have at least one fabric connection

#### Naming Conventions
- [ ] Connection names follow pattern: `{device}--{type}--{switch(es)}`
- [ ] Connection names are unique within topology plan
- [ ] Device names are valid Kubernetes resource names

### 8.2 Validation Error Messages

**Critical Errors (block generation):**
- "Switch {name} missing SwitchProfile reference"
- "MCLAG switches {sw1} and {sw2} have mismatched ASN ({asn1} vs {asn2})"
- "MCLAG group {group} has {count} switches (must be exactly 2)"
- "Port {port} not found in SwitchProfile {profile}"
- "Fabric connection {name} missing IP addresses"
- "MCLAG server connection {name} missing mclag-domain connection"

**Warnings (allow generation with warnings):**
- "MCLAG switches {sw1} and {sw2} have different models"
- "Incomplete fabric: Leaf {leaf} missing connection to spine {spine}"
- "VPC loopback detected (deprecated in newer Hedgehog releases)"

### 8.3 Validation Workflow

**Option 1: Validate on Save**
- Real-time validation as user configures plan
- Immediate feedback on errors
- Blocks saving invalid configurations

**Option 2: Validate on Generate**
- Allow partial/incomplete configurations
- Validate before YAML generation
- Show validation report with errors/warnings
- Block generation if critical errors exist

**Recommendation:** Hybrid
- Basic validation on save (required fields, referential integrity)
- Comprehensive validation on generate (topology rules, consistency checks)

---

## 9. Importing Hedgehog Switch Model Data

### 9.1 Data Sources

**Hedgehog SwitchProfile CRDs:**
- Repository: `github.com/githedgehog/fabric`
- Likely location: `api/meta/` or `config/` directory
- Format: YAML CRD definitions

**Potential Import Methods:**

#### Method 1: Static Bundle
- Include SwitchProfile data files with plugin
- Update with each Hedgehog release
- Simple, no external dependencies
- **Cons:** Manual updates required

#### Method 2: GitHub API Fetch
- Fetch from githedgehog/fabric at runtime or install
- Always up-to-date
- **Cons:** Requires internet access, API rate limits

#### Method 3: User Upload
- Admin uploads SwitchProfile CRDs
- Flexibility for custom/unreleased hardware
- **Cons:** Manual process, potential for errors

#### Method 4: Hedgehog API Integration
- If Hedgehog provides API to query profiles
- Real-time validation against actual Hedgehog installation
- **Cons:** Requires Hedgehog access, coupling

**Recommendation for MVP:** Method 1 (Static Bundle) with Method 3 (User Upload) as fallback
- Ship plugin with common profiles (Dell, Edgecore, etc.)
- Allow admins to upload custom profiles
- Provide Django management command to update from GitHub

### 9.2 SwitchProfile Data Model in NetBox

**Approach 1: Extend Device Type**
Add custom fields to NetBox DeviceType:
- `hedgehog_switch_profile` (string): SwitchProfile name
- `port_naming_pattern` (string): Regex for valid port names
- JSON field for port groups, breakout modes (if needed)

**Approach 2: New Model (SwitchProfile)**
Create DIET-specific model:
```python
class SwitchProfile(models.Model):
    name = models.CharField(max_length=100, unique=True)
    device_types = models.ManyToManyField(DeviceType)
    port_groups_data = models.JSONField()
    breakout_ports_data = models.JSONField()
    features = models.JSONField()
```

**Approach 3: Hybrid**
- Store only `hedgehog_switch_profile` name in DeviceType
- Reference Hedgehog's profiles at generation time
- Cache profile data in DIET for validation

**Recommendation:** Approach 3 (Hybrid)
- Lightweight data in NetBox
- Leverage Hedgehog's authoritative profile definitions
- Cache for performance and offline validation

### 9.3 Profile Data Parsing

**Required Parsing Logic:**

```python
def parse_switchprofile_crd(yaml_content):
    """
    Parse Hedgehog SwitchProfile CRD.

    Returns:
        {
            'name': 'dell-s5248f-on',
            'port_groups': {
                '1': {
                    'ports': ['E1/1', 'E1/2', 'E1/3', 'E1/4'],
                    'speeds': ['10G', '25G']
                }
            },
            'breakout_ports': {
                'E1/55': {
                    'modes': ['4x10G', '4x25G', '2x50G', '1x100G'],
                    'default': '1x100G'
                }
            },
            'regular_ports': {
                'E1/1': {
                    'speeds': ['10G', '25G'],
                    'default': '25G'
                }
            }
        }
    """
    # Parse YAML
    # Extract port groups, breakout capabilities, speeds
    # Normalize port naming patterns
    # Return structured data
```

### 9.4 Update Strategy

**Versioning:**
- Track Hedgehog version compatibility
- Store profile version with imported data
- Warn if profiles are outdated

**Update Triggers:**
1. Manual: Admin runs `python manage.py update_hedgehog_profiles`
2. Scheduled: Daily/weekly check for updates
3. On-demand: Before YAML generation, check for newer profiles

**Update Process:**
1. Fetch latest profiles from GitHub
2. Parse and validate CRDs
3. Compare with existing profiles
4. Show diff and prompt for confirmation
5. Update profile data
6. Log changes and version

### 9.5 Custom Profile Support

**Use Case:** Unreleased hardware, custom configurations, test environments

**Implementation:**
- Web UI to upload SwitchProfile YAML
- Validation against CRD schema
- Store as custom profile (separate from bundled)
- Mark as custom in UI (distinguish from official)

**Management:**
- List profiles (bundled vs custom)
- Edit custom profiles
- Delete custom profiles
- Export custom profiles (for sharing)

---

## 10. Complete Wiring Diagram Example

### 10.1 Small Fabric Example

**Topology:**
- 2 spine switches
- 2 leaf switches in MCLAG pair
- 2 servers (1 MCLAG, 1 unbundled)

**Complete YAML:**

```yaml
---
# VLANNamespace
apiVersion: wiring.githedgehog.com/v1alpha2
kind: VLANNamespace
metadata:
  name: default
spec:
  ranges:
    - from: 1000
      to: 2999
---
# IPv4Namespace
apiVersion: vpc.githedgehog.com/v1beta1
kind: IPv4Namespace
metadata:
  name: default
spec:
  subnets:
    - 10.10.0.0/16
---
# Redundancy Group for MCLAG
apiVersion: wiring.githedgehog.com/v1beta1
kind: SwitchGroup
metadata:
  name: mclag-leaf-pair-1
spec:
  type: mclag
---
# Spine Switch 1
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: spine-01
spec:
  role: spine
  profile: dell-s5232f-on
  boot:
    serial: SPINE01SN
  asn: 65100
  protocolIP: 10.99.1.1
---
# Spine Switch 2
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: spine-02
spec:
  role: spine
  profile: dell-s5232f-on
  boot:
    serial: SPINE02SN
  asn: 65100
  protocolIP: 10.99.1.2
---
# Leaf Switch 1 (MCLAG pair)
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: leaf-01
spec:
  role: server-leaf
  profile: dell-s5248f-on
  boot:
    serial: LEAF01SN
  asn: 65001
  vtepIP: 10.99.0.1
  protocolIP: 10.99.2.1
  vlanNamespaces:
    - default
  redundancy:
    group: mclag-leaf-pair-1
    type: mclag
---
# Leaf Switch 2 (MCLAG pair)
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: leaf-02
spec:
  role: server-leaf
  profile: dell-s5248f-on
  boot:
    serial: LEAF02SN
  asn: 65001
  vtepIP: 10.99.0.1
  protocolIP: 10.99.2.2
  vlanNamespaces:
    - default
  redundancy:
    group: mclag-leaf-pair-1
    type: mclag
---
# Server 1
apiVersion: wiring.githedgehog.com/v1beta1
kind: Server
metadata:
  name: server-01
spec:
  description: MCLAG connected server
---
# Server 2
apiVersion: wiring.githedgehog.com/v1beta1
kind: Server
metadata:
  name: server-02
spec:
  description: Unbundled connected server
---
# Fabric Connection: Spine-01 to Leaf-01
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: spine-01--fabric--leaf-01
spec:
  fabric:
    links:
      - spine:
          port: spine-01/E1/1
          ip: 172.30.1.0/31
        leaf:
          port: leaf-01/E1/50
          ip: 172.30.1.1/31
      - spine:
          port: spine-01/E1/2
          ip: 172.30.1.2/31
        leaf:
          port: leaf-01/E1/51
          ip: 172.30.1.3/31
---
# Fabric Connection: Spine-01 to Leaf-02
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: spine-01--fabric--leaf-02
spec:
  fabric:
    links:
      - spine:
          port: spine-01/E1/3
          ip: 172.30.2.0/31
        leaf:
          port: leaf-02/E1/50
          ip: 172.30.2.1/31
      - spine:
          port: spine-01/E1/4
          ip: 172.30.2.2/31
        leaf:
          port: leaf-02/E1/51
          ip: 172.30.2.3/31
---
# Fabric Connection: Spine-02 to Leaf-01
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: spine-02--fabric--leaf-01
spec:
  fabric:
    links:
      - spine:
          port: spine-02/E1/1
          ip: 172.30.3.0/31
        leaf:
          port: leaf-01/E1/52
          ip: 172.30.3.1/31
      - spine:
          port: spine-02/E1/2
          ip: 172.30.3.2/31
        leaf:
          port: leaf-01/E1/53
          ip: 172.30.3.3/31
---
# Fabric Connection: Spine-02 to Leaf-02
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: spine-02--fabric--leaf-02
spec:
  fabric:
    links:
      - spine:
          port: spine-02/E1/3
          ip: 172.30.4.0/31
        leaf:
          port: leaf-02/E1/52
          ip: 172.30.4.1/31
      - spine:
          port: spine-02/E1/4
          ip: 172.30.4.2/31
        leaf:
          port: leaf-02/E1/53
          ip: 172.30.4.3/31
---
# MCLAG Domain Connection
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: leaf-01--mclag-domain--leaf-02
spec:
  mclagDomain:
    peerLinks:
      - switch1:
          port: leaf-01/E1/54
        switch2:
          port: leaf-02/E1/54
      - switch1:
          port: leaf-01/E1/55
        switch2:
          port: leaf-02/E1/55
    sessionLinks:
      - switch1:
          port: leaf-01/E1/56
        switch2:
          port: leaf-02/E1/56
---
# MCLAG Server Connection
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: server-01--mclag--leaf-01--leaf-02
spec:
  mclag:
    links:
      - server:
          port: server-01/enp2s1
        switch:
          port: leaf-01/E1/1
      - server:
          port: server-01/enp2s2
        switch:
          port: leaf-02/E1/1
---
# Unbundled Server Connection
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: server-02--unbundled--leaf-01
spec:
  unbundled:
    link:
      server:
        port: server-02/enp2s1
      switch:
        port: leaf-01/E1/2
```

### 10.2 Key Observations from Example

**All-to-All Connectivity:**
- 2 spines × 2 leaves = 4 fabric connections
- Each connection has 2 links (for redundancy)

**MCLAG Configuration:**
- Leaf-01 and Leaf-02 share ASN (65001)
- Leaf-01 and Leaf-02 share VTEP IP (10.99.0.1)
- MCLAG domain has 2 peer links + 1 session link

**Naming Patterns:**
- Switches: `{role}-{number}` (spine-01, leaf-01)
- Connections: `{device}--{type}--{device(s)}` (server-01--mclag--leaf-01--leaf-02)
- Ports: `{switch}/{port}` (leaf-01/E1/1)
- Server ports: `{server}/{interface}` (server-01/enp2s1)

**IP Addressing:**
- Fabric links use /31 subnets (172.30.x.x/31)
- IP addresses assigned manually in wiring (or by hhfab build)

---

## 11. Summary and Recommendations

### 11.1 Critical Requirements for DIET

**Must Have:**
1. **SwitchProfile Mapping**: Every NetBox device type → Hedgehog SwitchProfile name
2. **Port Naming Validation**: Enforce Hedgehog port naming conventions (E1/1, E1/55/2)
3. **MCLAG ASN/VTEP Consistency**: Validate matching ASN and VTEP IP for MCLAG pairs
4. **Topology Validation**: Ensure all-to-all spine-leaf connectivity
5. **Connection Type Inference**: Determine connection type from cables + device roles
6. **Redundancy Group Management**: Track MCLAG/ESLAG groups and membership

**Should Have:**
1. **Port Group Configuration**: Store and validate port group speeds
2. **Breakout Configuration**: Store and validate breakout modes
3. **Profile Import**: Import SwitchProfile data from Hedgehog
4. **Validation Reports**: Detailed error/warning messages before YAML generation
5. **MCLAG Domain Auto-Detection**: Identify peer/session links from cables

**Nice to Have:**
1. **Topology Visualization**: Show spine-leaf connectivity matrix
2. **Profile Updates**: Auto-update from GitHub
3. **Custom Profiles**: Upload custom SwitchProfile CRDs
4. **Diff View**: Show changes before re-generating YAML
5. **hhfab Integration**: Validate against actual hhfab installation

### 11.2 Data Model Priorities

**Phase 1 (MVP):**
- FabricSwitch: Role, ASN, VTEP, profile reference
- FabricServer: Connection type
- RedundancyGroup: Type, members, shared ASN/VTEP
- FabricConnection: Type, validation status
- Device Type custom field: `hedgehog_switch_profile`

**Phase 2 (Enhanced Validation):**
- SwitchPortGroup: Port groups, speeds
- BreakoutConfiguration: Breakout modes
- SwitchProfile model: Imported profile data
- Validation rules engine

**Phase 3 (Advanced Features):**
- Profile import/update automation
- Custom profile upload
- hhfab integration
- Topology visualization

### 11.3 Validation Strategy

**Three-Tier Validation:**

**Tier 1: NetBox Built-in**
- Required fields, referential integrity
- Enforced by Django model validation

**Tier 2: DIET Business Logic**
- MCLAG ASN/VTEP consistency
- Redundancy group rules
- Connection type compatibility
- Enforced at save time with warnings

**Tier 3: Topology-Level**
- All-to-all spine-leaf connectivity
- Complete MCLAG domain configuration
- Namespace completeness
- Enforced at YAML generation time

### 11.4 Profile Import Strategy

**Recommended Approach:**
1. **Bundle common profiles** with plugin (Dell, Edgecore, Celestica)
2. **Store profile name reference** in NetBox device type custom field
3. **Cache basic validation data** (port naming patterns, groups)
4. **Delegate detailed validation** to hhfab (optional)
5. **Provide management command** to update profiles from GitHub
6. **Support custom profiles** via admin UI upload

**Implementation:**
```python
# Custom field on DeviceType
hedgehog_switch_profile = "dell-s5248f-on"

# Bundled profile data (JSON)
SWITCH_PROFILES = {
    "dell-s5248f-on": {
        "port_pattern": r"^E1/\d+(/\d+)?$",
        "port_groups": {...},
        "breakout_ports": {...}
    }
}

# Or dynamic fetch from Hedgehog
profile_data = fetch_hedgehog_profile("dell-s5248f-on")
```

### 11.5 Next Steps

**Immediate Actions:**
1. **Review this document** with team and stakeholders
2. **Post to GitHub issue** (#83 or #106) for discussion
3. **Prioritize requirements** for sprint planning
4. **Design DIET data models** based on requirements
5. **Create validation rule specifications**

**Design Phase:**
1. **ERD for DIET models** (FabricSwitch, RedundancyGroup, etc.)
2. **Validation rule catalog** (with error messages)
3. **YAML generation algorithm** (NetBox → Hedgehog CRDs)
4. **Profile import design** (static vs dynamic)

**Implementation Phase:**
1. **Extend NetBox models** with DIET tables
2. **Implement validation logic** (three-tier strategy)
3. **Build YAML generator** (template-based or programmatic)
4. **Create profile import** (management command + UI)
5. **Write integration tests** (per CLAUDE.md requirements)

---

## 12. Sources and References

### Documentation
- [Hedgehog Connections Documentation](https://docs.hedgehog.cloud/latest/user-guide/connections/)
- [Hedgehog Switch Profiles and Port Naming](https://docs.hedgehog.cloud/beta-1/user-guide/profiles/)
- [Build Wiring Diagram](https://docs.hedgehog.cloud/dev/install-upgrade/build-wiring/)
- [Switches and Servers](https://docs.hedgehog.cloud/24.09/user-guide/devices/)
- [Hedgehog Concepts](https://docs.githedgehog.com/beta-1/concepts/overview/)
- [Fabric Configuration](https://docs.githedgehog.com/beta-1/install-upgrade/config/)
- [VPCs and Namespaces](https://docs.hedgehog.cloud/dev/user-guide/vpcs/)
- [External Peering](https://docs.hedgehog.cloud/dev/user-guide/external/)

### GitHub Repositories
- [Hedgehog GitHub Organization](https://github.com/githedgehog)
- [Hedgehog Open Network Fabric](https://github.com/githedgehog/fabric)
- [Hedgehog Fabricator](https://github.com/githedgehog/fabricator)

### Additional Resources
- [Hedgehog Architecture](https://githedgehog.com/architecture/)
- [Running VLAB](https://docs.githedgehog.com/beta-1/vlab/running/)
- [Experiment with SONiC using Hedgehog Virtual Lab](https://hedgehog.cloud/blog/experiment-with-sonic-using-hedgehog-virtual-lab)
- [Release Notes](https://docs.hedgehog.cloud/dev/release-notes/)

---

**Document Version:** 1.0
**Last Updated:** 2025-12-27
**Author:** Claude Code Research (Sonnet 4.5)
**Status:** Ready for Review
