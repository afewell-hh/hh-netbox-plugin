# Hedgehog Wiring Schema Research - Executive Summary

**Research Completed:** 2025-12-27
**Full Document:** See `HEDGEHOG_WIRING_REQUIREMENTS.md` for complete technical details

---

## Key Findings

### 1. Connection CRD Architecture

Hedgehog uses Kubernetes CRDs (`wiring.githedgehog.com/v1beta1`) to represent all network infrastructure. The wiring diagram is a YAML file containing:

**Server Connections (4 types):**
- **Unbundled**: Single port to single switch
- **Bundled**: Multiple ports to single switch (LAG)
- **MCLAG**: Dual-homing to 2 switches (requires matching ASN/VTEP)
- **ESLAG**: Multi-homing to 2-4 switches (simpler than MCLAG)

**Switch Connections (3 types):**
- **Fabric**: Spine-to-leaf connections with IP addresses
- **MCLAG-Domain**: Defines MCLAG switch pair (peer + session links)
- **Mesh**: Direct leaf-to-leaf (limited use, TH5 hardware restrictions)

**External Connections (3 types):**
- **StaticExternal**: Non-BGP external systems (DHCP, NTP)
- **External**: BGP peering
- **VPCLoopback**: Cable looped on same switch (DEPRECATED in newer releases)

### 2. Critical Validation Rules

**MCLAG Requirements:**
- Exactly 2 switches in redundancy group
- MUST have matching `spec.ASN` and `spec.VTEPIP`
- Requires `mclag-domain` connection with peer + session links
- Server interfaces MUST use 802.3ad LACP

**Fabric Topology:**
- All-to-all connectivity: Every leaf connects to every spine
- Every spine connects to every leaf
- No leaf-to-leaf or spine-to-spine fabric connections (use mesh for that)

**Port Naming:**
- Format: `E<asic>/<port>[/<breakout>]`
- Examples: `E1/1`, `E1/55/1`, `E1/55/2`
- MUST match SwitchProfile exactly
- Only profile-defined ports are valid

### 3. SwitchProfile System

**Every switch MUST reference a SwitchProfile** that defines:
- Port groups (speed applies to all ports in group)
- Breakout-capable ports with available modes
- Regular ports with available speeds
- Supported features for validation

**Port Types:**
1. **Port Groups**: Non-breakout, speed set for entire group
2. **Breakout Ports**: Configurable split (e.g., 1x100G → 4x25G)
3. **Regular Ports**: Individual speed configuration

### 4. hhfab Tooling

**What hhfab does:**
- `hhfab init`: Initialize with wiring files
- `hhfab build`: Generates IP/ASN from wiring diagram (wiring has NO IP/ASN!)
- `hhfab vlab gen`: Generate virtual lab topology
- `hhfab diagram`: Create Draw.io/Graphviz/Mermaid diagrams

**What hhfab validates:**
- Port existence in SwitchProfile
- Port naming conventions
- MCLAG ASN/VTEP consistency
- Breakout mode validity
- Speed configuration validity

### 5. Supported Hardware

**Certified Vendors:**
- Celestica, Cisco, Dell, Edgecore, NVIDIA, Supermicro

**Confirmed Edgecore Models:**
- DCS204, DCS203, DCS501, EPS203

**Custom certification:** 1-2 months with test equipment

---

## Critical Requirements for DIET

### Must-Have Data in NetBox

**Switch Configuration:**
- Device name → Switch `metadata.name`
- Device type → SwitchProfile reference (MANDATORY)
- Serial number OR MAC address (boot identification)
- Switch role (spine, server-leaf, border-leaf, mixed-leaf)
- ASN, VTEP IP, Protocol IP (for BGP/VXLAN)

**Redundancy Groups:**
- MCLAG/ESLAG group membership
- Shared ASN/VTEP for MCLAG pairs

**Port Configuration:**
- Interface names MUST match SwitchProfile convention
- Port group membership
- Breakout configuration
- Speed configuration

**Connections:**
- NetBox cables → Hedgehog Connection CRDs
- Connection type inference from device roles + redundancy groups
- MCLAG domain peer/session link designation

### Must-Enforce Validation Rules

1. **Pre-Generation Checks:**
   - [ ] Every switch has SwitchProfile reference
   - [ ] MCLAG pairs have matching ASN and VTEP IP
   - [ ] MCLAG groups have exactly 2 switches
   - [ ] ESLAG groups have 2-4 switches
   - [ ] All switch ports match SwitchProfile naming
   - [ ] Breakout configs only on breakout-capable ports

2. **Topology Validation:**
   - [ ] All-to-all spine-leaf connectivity
   - [ ] MCLAG server connections have mclag-domain connection
   - [ ] Connection names follow convention: `{device}--{type}--{switch(es)}`

3. **Namespace Requirements:**
   - [ ] VLANNamespace defines non-overlapping VLAN ranges
   - [ ] IPv4Namespace defines non-overlapping subnet ranges

---

## Recommendations

### Phase 1 (MVP) - Core Functionality

**Data Models:**
- `FabricSwitch`: Role, ASN, VTEP, profile reference
- `FabricServer`: Connection type
- `RedundancyGroup`: Type (mclag/eslag), members, shared ASN/VTEP
- `FabricConnection`: Type, validation status
- Custom field on DeviceType: `hedgehog_switch_profile`

**Validation:**
- Three-tier approach:
  - Tier 1: NetBox built-in (required fields, referential integrity)
  - Tier 2: DIET business logic (MCLAG consistency, redundancy rules)
  - Tier 3: Topology-level (all-to-all connectivity, completeness)

**Profile Management:**
- Store SwitchProfile name reference in NetBox device type
- Bundle common profiles (Dell, Edgecore, Celestica) with plugin
- Cache basic validation data (port naming patterns)
- Delegate detailed validation to hhfab (optional)

### Phase 2 - Enhanced Validation

- `SwitchPortGroup`: Port groups, available speeds
- `BreakoutConfiguration`: Breakout modes
- `SwitchProfile` model: Imported profile data
- Validation rules engine with detailed error messages

### Phase 3 - Advanced Features

- Profile import/update automation from GitHub
- Custom profile upload via admin UI
- hhfab integration for real-time validation
- Topology visualization (spine-leaf connectivity matrix)

### Profile Import Strategy

**Recommended: Hybrid Approach**

1. **Bundle common profiles** with plugin (static JSON/YAML)
2. **Store profile name** in NetBox device type custom field
3. **Cache validation data** for offline operation
4. **Provide management command** to update from GitHub:
   ```bash
   python manage.py update_hedgehog_profiles [--from-github]
   ```
5. **Support custom profiles** via admin UI upload

**Pros:**
- No duplication of Hedgehog's authoritative data
- Works offline with bundled profiles
- Easy updates from upstream
- Supports custom/unreleased hardware

**Cons:**
- Requires periodic updates
- GitHub API rate limits (mitigated by caching)

---

## Connection Type Inference Logic

**DIET must determine connection type from NetBox cables:**

```
IF cable between server and switch(es):
    IF 1 switch, 1 cable → Unbundled
    IF 1 switch, 2+ cables → Bundled
    IF 2 switches in MCLAG group → MCLAG
    IF 2-4 switches in ESLAG group → ESLAG

IF cable between spine and leaf:
    → Fabric connection

IF cable between MCLAG pair members:
    IF designated as peer → MCLAG domain peer link
    IF designated as session → MCLAG domain session link
    DEFAULT: First 2 = peer, next 2 = session

IF cable with both ends on same switch:
    → VPCLoopback (warn: deprecated)
```

---

## Example YAML Structure

**Minimal Spine-Leaf with MCLAG Server:**

```yaml
# Switches
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: leaf-01
spec:
  role: server-leaf
  profile: dell-s5248f-on
  asn: 65001
  vtepIP: 10.99.0.1
  redundancy:
    group: mclag-leaf-pair-1
    type: mclag
---
# Fabric Connection
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
---
# MCLAG Domain
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
```

---

## Next Steps

1. **Review** full requirements document (`HEDGEHOG_WIRING_REQUIREMENTS.md`)
2. **Discuss** approach and priorities with team
3. **Design** DIET data models (ERD)
4. **Specify** validation rules catalog with error messages
5. **Prototype** YAML generation algorithm
6. **Plan** profile import implementation

---

## Questions for Discussion

1. **Profile Management:** Static bundle vs dynamic GitHub fetch vs user upload?
2. **Validation Timing:** Real-time on save vs on-demand before generation?
3. **MCLAG Domain Detection:** Auto-detect peer/session links or require manual designation?
4. **IP Assignment:** DIET assigns fabric IPs or leave to hhfab build?
5. **Topology Scope:** Support only CLOS or also collapsed core (mesh)?

---

## Resources

**Full Requirements Document:** `HEDGEHOG_WIRING_REQUIREMENTS.md` (12 sections, 50+ pages)

**Key Documentation:**
- [Hedgehog Connections](https://docs.hedgehog.cloud/latest/user-guide/connections/)
- [Switch Profiles](https://docs.hedgehog.cloud/beta-1/user-guide/profiles/)
- [Build Wiring Diagram](https://docs.hedgehog.cloud/dev/install-upgrade/build-wiring/)
- [Hedgehog GitHub](https://github.com/githedgehog/fabric)

**Research Coverage:**
- ✅ Connection CRD complete schema with examples
- ✅ Hedgehog fabric model and constraints
- ✅ Port naming and breakout conventions
- ✅ Switch models and profile system
- ✅ Validation rules and topology constraints
- ✅ hhfab tooling capabilities
- ✅ NetBox data requirements
- ✅ Profile import recommendations

Ready for sprint planning and implementation!
