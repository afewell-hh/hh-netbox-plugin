# Hedgehog Fabric Port Naming and Breakout Calculation Specification

**Document Version:** 1.0
**Date:** 2026-01-06
**Author:** Analysis of hh-netbox-plugin codebase and Hedgehog documentation

---

## Executive Summary

This document provides a complete specification for Hedgehog fabric's port naming system, breakout calculations, and the relationship between Hedgehog's logical port names (E1/N format) and underlying network operating system identifiers (SONiC Ethernet format).

**Critical Finding:** Hedgehog uses an abstraction layer where:
- **Wiring diagrams use ONLY Hedgehog format** (E1/1, E1/1/1, etc.)
- **NOS names like "Ethernet0" are NOT supported** in Connection CRDs
- **Switch profiles handle the internal mapping** to actual switch hardware

---

## 1. Port Naming Formats

### 1.1 Hedgehog Port Naming Convention (HNP Format)

**General Pattern:** `E<asic>/<port>[/<lane>][.<subinterface>]`

Where:
- `<asic>`: ASIC or chassis number (always `1` for current Hedgehog switches)
- `<port>`: Physical port number (1-based: 1, 2, 3, ..., 64)
- `<lane>`: Breakout lane number (1-based: 1, 2, 3, 4, ..., 8) - **OPTIONAL**
- `<subinterface>`: VLAN subinterface (rarely used in physical wiring)

**Examples:**
```
E1/1          # Physical port 1, no breakout
E1/55         # Physical port 55, no breakout
E1/1/1        # Physical port 1, breakout lane 1
E1/1/2        # Physical port 1, breakout lane 2
E1/55/1       # Physical port 55, breakout lane 1
E1/55/2       # Physical port 55, breakout lane 2
```

**Key Rules:**
1. Port numbers start from 1 (NOT 0)
2. Breakout lane numbers start from 1 (NOT 0)
3. Breakout lanes are sequential: 1, 2, 3, 4 (for 4x breakout)
4. First breakout can omit `/1` suffix: `E1/55` = `E1/55/1` (allowed but not recommended in HNP)
5. **NetBox plugin ALWAYS includes breakout suffix** when breakout is configured

### 1.2 SONiC Port Naming Convention (NOS Format)

**Pattern:** `Ethernet<index>`

Where:
- `<index>`: SerDes lane base index (0-based, increments by lanes per port)

**Examples for 4-lane interfaces (100G/800G):**
```
Ethernet0     # Lanes 0-3 (physical port 1)
Ethernet4     # Lanes 4-7 (physical port 2)
Ethernet8     # Lanes 8-11 (physical port 3)
Ethernet12    # Lanes 12-15 (physical port 4)
```

**Examples for 8-lane interfaces (400G):**
```
Ethernet0     # Lanes 0-7 (physical port 1)
Ethernet8     # Lanes 8-15 (physical port 2)
Ethernet16    # Lanes 16-23 (physical port 3)
```

**Mapping Formula:**
```
SONiC_index = (physical_port - 1) × lanes_per_port
```

For standard 100G/800G switches (4 lanes per port):
- E1/1 → Ethernet0
- E1/2 → Ethernet4
- E1/3 → Ethernet8
- E1/N → Ethernet{(N-1) × 4}

**IMPORTANT:** Hedgehog wiring diagrams do NOT use SONiC names. This mapping exists internally in switch profiles but is not exposed in Connection CRDs.

---

## 2. Breakout Configuration System

### 2.1 BreakoutOption Model

Hedgehog uses a `BreakoutOption` model to define breakout capabilities:

```python
class BreakoutOption:
    breakout_id: str        # e.g., "4x200g", "2x400g"
    from_speed: int         # Native port speed in Gbps (800, 100, etc.)
    logical_ports: int      # Number of logical ports after breakout (1, 2, 4, 8)
    logical_speed: int      # Speed per logical port in Gbps (200, 400, etc.)
    optic_type: str         # Optic type (QSFP-DD, QSFP28, etc.)
```

### 2.2 Standard Breakout Configurations

From production database (as of 2026-01-06):

| Breakout ID | Native Speed | Logical Ports | Logical Speed | Use Case |
|-------------|--------------|---------------|---------------|----------|
| 1x1g | 1G | 1 | 1G | Edge switches |
| 1x10g | 10G | 1 | 10G | Management ports |
| 1x100g | 100G | 1 | 100G | Native 100G (DS3000) |
| 4x10g | 100G | 4 | 10G | 100G → 4×10G |
| 4x25g | 100G | 4 | 25G | 100G → 4×25G |
| 2x50g | 100G | 2 | 50G | 100G → 2×50G |
| 1x40g | 100G | 1 | 40G | Legacy 40G |
| 1x400g | 400G | 1 | 400G | Native 400G |
| 2x200g | 400G | 2 | 200G | 400G → 2×200G |
| 4x100g | 400G | 4 | 100G | 400G → 4×100G |
| 1x800g | 800G | 1 | 800G | Native 800G (DS5000) |
| 2x400g | 800G | 2 | 400G | 800G → 2×400G |
| 4x200g | 800G | 4 | 200G | 800G → 4×200G (most common) |
| 8x100g | 800G | 8 | 100G | 800G → 8×100G |

**Conservation Law:** `from_speed = logical_ports × logical_speed`

### 2.3 Breakout Offset Patterns

**Offsets in HNP are sequential lane numbers, NOT SONiC lane indices.**

For 4x200G breakout (4 logical ports):
```
Physical Port: E1/3 (native 800G)
Breakout Mode: 4x200g
Logical Ports:
  - E1/3/1 (lane 1, 200G)
  - E1/3/2 (lane 2, 200G)
  - E1/3/3 (lane 3, 200G)
  - E1/3/4 (lane 4, 200G)
```

For 2x50G breakout (2 logical ports):
```
Physical Port: E1/55 (native 100G)
Breakout Mode: 2x50g
Logical Ports:
  - E1/55/1 (lane 1, 50G)
  - E1/55/2 (lane 2, 50G)
```

**Why sequential numbering (NOT [0, 2] offsets)?**
- Hedgehog abstracts away SONiC SerDes lane complexities
- User-facing names are simple: 1, 2, 3, 4
- Switch profiles handle the mapping to actual hardware lanes

---

## 3. Algorithm Specification

### 3.1 Port Name Generation Algorithm

**Input:**
- `physical_port`: int (1-based physical port number)
- `breakout_option`: BreakoutOption | None
- `lane_index`: int (1-based lane number within breakout)

**Output:**
- HNP format port name (string)

**Python Implementation:**
```python
def generate_port_name(physical_port: int, breakout_option=None, lane_index=None) -> str:
    """
    Generate Hedgehog port name from physical port and breakout configuration.

    Args:
        physical_port: Physical port number (1-based: 1, 2, 3, ...)
        breakout_option: BreakoutOption instance or None for no breakout
        lane_index: Lane index (1-based: 1, 2, 3, 4) if breakout configured

    Returns:
        Port name in HNP format (e.g., 'E1/3', 'E1/3/2')

    Examples:
        >>> generate_port_name(1)
        'E1/1'
        >>> generate_port_name(3, breakout_4x200g, lane_index=1)
        'E1/3/1'
        >>> generate_port_name(3, breakout_4x200g, lane_index=4)
        'E1/3/4'
    """
    if breakout_option and breakout_option.logical_ports > 1:
        # Breakout configured - include lane suffix
        if lane_index is None:
            raise ValueError("lane_index required when breakout has multiple logical ports")
        return f"E1/{physical_port}/{lane_index}"
    else:
        # No breakout or 1x native speed
        return f"E1/{physical_port}"
```

### 3.2 Breakout Expansion Algorithm

**Input:**
- `physical_ports`: list[int] (e.g., [1, 2, 3])
- `breakout_option`: BreakoutOption | None

**Output:**
- List of PortSlot objects with HNP names

**Python Implementation:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class PortSlot:
    """Represents an allocated switch port."""
    physical_port: int          # Physical port number (1-based)
    breakout_index: int | None  # Breakout lane (1-based) or None
    name: str                   # HNP format name (e.g., 'E1/3/2')


def expand_breakouts(physical_ports: list[int], breakout_option) -> list[PortSlot]:
    """
    Expand physical ports into logical ports based on breakout configuration.

    Args:
        physical_ports: List of physical port numbers (1-based)
        breakout_option: BreakoutOption instance or None

    Returns:
        List of PortSlot objects representing logical ports

    Examples:
        >>> # No breakout
        >>> expand_breakouts([1, 2], None)
        [PortSlot(physical_port=1, breakout_index=None, name='E1/1'),
         PortSlot(physical_port=2, breakout_index=None, name='E1/2')]

        >>> # 4x200G breakout
        >>> expand_breakouts([1, 2], breakout_4x200g)
        [PortSlot(physical_port=1, breakout_index=1, name='E1/1/1'),
         PortSlot(physical_port=1, breakout_index=2, name='E1/1/2'),
         PortSlot(physical_port=1, breakout_index=3, name='E1/1/3'),
         PortSlot(physical_port=1, breakout_index=4, name='E1/1/4'),
         PortSlot(physical_port=2, breakout_index=1, name='E1/2/1'),
         PortSlot(physical_port=2, breakout_index=2, name='E1/2/2'),
         PortSlot(physical_port=2, breakout_index=3, name='E1/2/3'),
         PortSlot(physical_port=2, breakout_index=4, name='E1/2/4')]
    """
    logical_ports = 1
    if breakout_option:
        logical_ports = breakout_option.logical_ports or 1

    expanded: list[PortSlot] = []
    for port in physical_ports:
        if logical_ports > 1:
            # Breakout configured - create multiple logical ports
            for lane in range(1, logical_ports + 1):
                expanded.append(
                    PortSlot(
                        physical_port=port,
                        breakout_index=lane,
                        name=f"E1/{port}/{lane}",
                    )
                )
        else:
            # No breakout or 1x native speed
            expanded.append(
                PortSlot(
                    physical_port=port,
                    breakout_index=None,
                    name=f"E1/{port}",
                )
            )
    return expanded
```

### 3.3 SONiC Mapping Algorithm (Internal to Switch Profiles)

**Note:** This mapping is NOT used in wiring diagrams, only for understanding switch internals.

**Input:**
- `hnp_port_name`: str (e.g., "E1/3/2")
- `lanes_per_physical_port`: int (typically 4 for 100G/800G, 8 for 400G)

**Output:**
- `sonic_base_name`: str (e.g., "Ethernet8")
- `sonic_lane_offset`: int (lane offset within base port)

**Python Pseudocode:**
```python
def hnp_to_sonic_mapping(hnp_port_name: str, lanes_per_physical_port: int = 4) -> tuple[str, int]:
    """
    Map Hedgehog port name to SONiC Ethernet interface.

    IMPORTANT: This is for internal understanding only.
    Hedgehog wiring diagrams do NOT use SONiC names.

    Args:
        hnp_port_name: Hedgehog port name (e.g., 'E1/3/2')
        lanes_per_physical_port: SerDes lanes per physical port (default: 4)

    Returns:
        Tuple of (base_sonic_name, lane_offset)

    Examples:
        >>> hnp_to_sonic_mapping('E1/1')
        ('Ethernet0', 0)
        >>> hnp_to_sonic_mapping('E1/3')
        ('Ethernet8', 0)
        >>> hnp_to_sonic_mapping('E1/3/1')
        ('Ethernet8', 0)
        >>> hnp_to_sonic_mapping('E1/3/2')
        ('Ethernet8', 1)  # Approximate - actual mapping in switch profile
    """
    # Parse HNP name
    parts = hnp_port_name.split('/')
    asic = parts[0]  # 'E1'
    physical_port = int(parts[1])
    breakout_lane = int(parts[2]) if len(parts) > 2 else 1

    # Calculate base SONiC index
    sonic_base_index = (physical_port - 1) * lanes_per_physical_port

    # Base SONiC name (without breakout consideration)
    base_sonic_name = f"Ethernet{sonic_base_index}"

    # Lane offset (simplified - actual mapping is hardware-specific)
    lane_offset = breakout_lane - 1

    return (base_sonic_name, lane_offset)
```

**CRITICAL:** The actual SONiC lane mapping is hardware-specific and defined in switch profiles. The above is a simplified representation.

---

## 4. Test Cases and Validation

### 4.1 Test Case: No Breakout (Native Speed)

**Scenario:** DS5000 switch, ports 1-4, no breakout (1x800G)

**Input:**
- Physical ports: [1, 2, 3, 4]
- Breakout: None (1x800G)

**Expected Output:**
```python
[
    PortSlot(physical_port=1, breakout_index=None, name='E1/1'),
    PortSlot(physical_port=2, breakout_index=None, name='E1/2'),
    PortSlot(physical_port=3, breakout_index=None, name='E1/3'),
    PortSlot(physical_port=4, breakout_index=None, name='E1/4'),
]
```

### 4.2 Test Case: 4x200G Breakout

**Scenario:** DS5000 switch, port 1, 4x200G breakout

**Input:**
- Physical ports: [1]
- Breakout: 4x200G (from_speed=800, logical_ports=4, logical_speed=200)

**Expected Output:**
```python
[
    PortSlot(physical_port=1, breakout_index=1, name='E1/1/1'),
    PortSlot(physical_port=1, breakout_index=2, name='E1/1/2'),
    PortSlot(physical_port=1, breakout_index=3, name='E1/1/3'),
    PortSlot(physical_port=1, breakout_index=4, name='E1/1/4'),
]
```

**SONiC Mapping (internal):**
```
E1/1/1 → Ethernet0 (lanes 0-1 approx.)
E1/1/2 → Ethernet0 (lanes 2-3 approx.)
E1/1/3 → Ethernet0 (lanes 0-1 of second pair)
E1/1/4 → Ethernet0 (lanes 2-3 of second pair)
```
**Note:** Actual SONiC mapping is switch-specific.

### 4.3 Test Case: 2x400G Breakout

**Scenario:** DS5000 switch, ports 60-64, 2x400G breakout

**Input:**
- Physical ports: [60, 61, 62, 63, 64]
- Breakout: 2x400G (from_speed=800, logical_ports=2, logical_speed=400)

**Expected Output:**
```python
[
    PortSlot(physical_port=60, breakout_index=1, name='E1/60/1'),
    PortSlot(physical_port=60, breakout_index=2, name='E1/60/2'),
    PortSlot(physical_port=61, breakout_index=1, name='E1/61/1'),
    PortSlot(physical_port=61, breakout_index=2, name='E1/61/2'),
    PortSlot(physical_port=62, breakout_index=1, name='E1/62/1'),
    PortSlot(physical_port=62, breakout_index=2, name='E1/62/2'),
    PortSlot(physical_port=63, breakout_index=1, name='E1/63/1'),
    PortSlot(physical_port=63, breakout_index=2, name='E1/63/2'),
    PortSlot(physical_port=64, breakout_index=1, name='E1/64/1'),
    PortSlot(physical_port=64, breakout_index=2, name='E1/64/2'),
]
```

### 4.4 Test Case: Mixed Breakout Configuration

**Scenario:** Server leaf with mixed zones

**Configuration:**
- Ports 1-60: 4x200G breakout (server connections)
- Ports 61-64: 1x800G native (spine uplinks)

**Expected Port Names:**
```
Server Zone (ports 1-60 with 4x200G):
  E1/1/1, E1/1/2, E1/1/3, E1/1/4
  E1/2/1, E1/2/2, E1/2/3, E1/2/4
  ...
  E1/60/1, E1/60/2, E1/60/3, E1/60/4

Uplink Zone (ports 61-64 with 1x800G):
  E1/61
  E1/62
  E1/63
  E1/64
```

---

## 5. Edge Cases and Special Scenarios

### 5.1 Management Ports

**Convention:** Management ports typically use different naming:
- Out-of-band management: `mgmt0`, `eth0`
- NOT part of E1/N series

**Example:**
```yaml
# Management connection (NOT in wiring diagram fabric/unbundled sections)
management:
  interface: mgmt0
  ip: 192.168.1.10/24
```

### 5.2 Non-Sequential Physical Ports

**Scenario:** Port specification with gaps (e.g., "1-4,10-12")

**Implementation:**
```python
# PortSpecification parser handles this
spec = PortSpecification("1-4,10-12")
ports = spec.parse()  # [1, 2, 3, 4, 10, 11, 12]

# Breakout expansion works on ANY list
expanded = expand_breakouts(ports, breakout_4x200g)
# Results: E1/1/1, E1/1/2, ..., E1/4/4, E1/10/1, ..., E1/12/4
```

### 5.3 Odd-Numbered Port Specifications

**Scenario:** Allocation strategy uses every other port (interleaved)

**Example:**
```python
zone = SwitchPortZone(
    port_spec="1-8",
    allocation_strategy="interleaved",
    breakout_option=breakout_4x200g
)

# Allocation order: [1, 3, 5, 7, 2, 4, 6, 8]
allocator = PortAllocatorV2()
first_four = allocator.allocate('leaf-01', zone, 4)
# Results: E1/1/1, E1/1/2, E1/1/3, E1/1/4
# (First 4 logical ports from port 1, which is first in interleaved order)
```

### 5.4 Ports Without Breakout Capability

**Switch Profile Constraint:** Not all ports support breakout.

**Example (Dell S5248F):**
- Ports 1-48: 25G (non-breakout capable)
- Ports 49-54: 100G (breakout-capable: 4x25G, 4x10G)

**Validation:** HNP must validate that breakout is only configured on capable ports.

### 5.5 Multiple Breakout Zones on Same Switch

**Scenario:** Different port zones with different breakout configurations

**Example:**
```python
# Zone 1: Server ports with 4x200G
zone_server = SwitchPortZone(
    zone_name='server-ports',
    port_spec='1-60',
    breakout_option=breakout_4x200g,
)

# Zone 2: Uplink ports with 1x800G
zone_uplink = SwitchPortZone(
    zone_name='uplink-ports',
    port_spec='61-64',
    breakout_option=breakout_1x800g,
)

# Port allocator handles each zone independently
allocator = PortAllocatorV2()
server_ports = allocator.allocate('leaf-01', zone_server, 8)
# E1/1/1, E1/1/2, E1/1/3, E1/1/4, E1/2/1, E1/2/2, E1/2/3, E1/2/4

uplink_ports = allocator.allocate('leaf-01', zone_uplink, 2)
# E1/61, E1/62
```

---

## 6. NetBox Integration and YAML Export

### 6.1 Interface Custom Fields

When creating NetBox Interface objects, HNP stores breakout metadata:

```python
interface = Interface.objects.create(
    device=switch,
    name='E1/3/2',  # HNP format with breakout suffix
    type='200gbase-x-qsfp56',
)
interface.custom_field_data = {
    'hedgehog_plan_id': str(plan.pk),
    'hedgehog_zone': 'server-ports',
    'hedgehog_physical_port': 3,      # Physical port number (integer)
    'hedgehog_breakout_index': 2,     # Breakout lane (integer, 1-based)
}
interface.save()
```

### 6.2 YAML Export Format

Connection CRDs use HNP format EXACTLY as stored in Interface.name:

```yaml
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: server-03-nic1--unbundled--leaf-01
spec:
  unbundled:
    link:
      server:
        port: server-03/enp2s1
      switch:
        port: fe-leaf-01/E1/3/2  # Exact Interface.name value
```

**Critical Rules:**
1. Port names MUST include breakout suffix when breakout is configured
2. Format is `{device-name}/{interface-name}`
3. NO SONiC names (Ethernet0) allowed
4. NO BaseNOSName fields in wiring YAML

---

## 7. Comparison: Hedgehog vs. SONiC Port Naming

| Aspect | Hedgehog (HNP) | SONiC NOS |
|--------|----------------|-----------|
| **Base Format** | E1/{port} | Ethernet{index} |
| **Port Numbering** | 1-based (1, 2, 3, ...) | 0-based (0, 4, 8, ...) |
| **Breakout Format** | E1/{port}/{lane} | Varies by config |
| **Lane Numbering** | Sequential 1-based (1, 2, 3, 4) | SerDes lane indices |
| **Increment** | Always by 1 | By lanes_per_port (4 or 8) |
| **User-Facing** | YES (in wiring diagrams) | NO (internal only) |
| **Switch Profile** | Defines mapping | Implementation detail |
| **Abstraction** | High-level, hardware-agnostic | Low-level, hardware-specific |

**Example Comparison:**

| Physical Port | Hedgehog Name | SONiC Name (4-lane) | SONiC Lanes |
|---------------|---------------|---------------------|-------------|
| Port 1 | E1/1 | Ethernet0 | 0-3 |
| Port 1, Lane 1 | E1/1/1 | Ethernet0 (subset) | 0-1 |
| Port 1, Lane 2 | E1/1/2 | Ethernet0 (subset) | 2-3 |
| Port 2 | E1/2 | Ethernet4 | 4-7 |
| Port 3 | E1/3 | Ethernet8 | 8-11 |
| Port 64 | E1/64 | Ethernet252 | 252-255 |

---

## 8. Implementation Reference

### 8.1 Source Code Locations

**Port Allocator:**
- File: `/netbox_hedgehog/services/port_allocator.py`
- Function: `PortAllocatorV2._expand_breakouts()`
- Lines: 87-111
- Logic: Simple sequential lane numbering (1, 2, 3, ...)

**Device Generator:**
- File: `/netbox_hedgehog/services/device_generator.py`
- Function: `DeviceGenerator._create_connections()`
- Lines: 281-298
- Creates Interface objects with breakout metadata

**YAML Generator:**
- File: `/netbox_hedgehog/services/yaml_generator.py`
- Function: `YAMLGenerator._create_unbundled_crd()`
- Lines: 207-247
- Uses `Interface.name` directly (E1/N/M format)

### 8.2 Test Coverage

**Port Allocator Tests:**
- File: `/netbox_hedgehog/tests/test_topology_planning/test_port_allocator.py`
- Test: `test_allocate_with_breakout_expands_logical_ports`
- Line: 87-104
- Validates: E1/1/1, E1/1/2, E1/1/3, E1/1/4 naming

**YAML Export Tests:**
- File: `/netbox_hedgehog/tests/test_topology_planning/test_yaml_export_inventory_based.py`
- Test: `test_fabric_connections_use_leaf_spine_schema`
- Lines: 713-789
- Validates: Port names in Connection CRDs

---

## 9. Summary and Key Takeaways

### 9.1 Port Naming Rules

1. **Hedgehog uses E1/N format exclusively** in wiring diagrams
2. **SONiC Ethernet names are internal** to switch profiles
3. **Breakout lanes are sequential**: 1, 2, 3, 4 (NOT SONiC lane indices)
4. **Physical ports are 1-based**: E1/1, E1/2, ..., E1/64
5. **Always include breakout suffix** when multiple logical ports exist

### 9.2 Breakout Calculation

1. **logical_ports field** determines how many logical ports
2. **Sequential expansion**: For each physical port, create `logical_ports` entries
3. **Lane numbering**: Always 1, 2, 3, ..., N
4. **No complex offsets**: HNP abstracts away hardware lane details

### 9.3 NetBox Integration

1. **Interface.name stores HNP format** (E1/3/2)
2. **Custom fields store breakout metadata** (physical_port, breakout_index)
3. **YAML export uses Interface.name** directly
4. **No BaseNOSName or SONiC fields** in wiring YAML

### 9.4 Validation Requirements

1. **Port names MUST match SwitchProfile** conventions
2. **Breakout only on capable ports** (validated by switch profile)
3. **Consistent naming across plan** (all E1/N format)
4. **NO mixing of NOS names** in wiring diagrams

---

## 10. References

### Documentation Sources
- [SONiC Port Configuration Utility](https://github.com/sonic-net/SONiC/wiki/Port-Configuration-Utility-High-Level-Design)
- [SONiC Port Breakout Design](https://github.com/sonic-net/SONiC/wiki/Port-Breakout-High-Level-Design)
- [Hedgehog Switch Profiles](https://docs.hedgehog.cloud/beta-1/user-guide/profiles/)
- [Hedgehog Switches and Servers](https://docs.hedgehog.cloud/24.09/user-guide/devices/)
- [Hedgehog Connections](https://docs.hedgehog.cloud/latest/user-guide/connections/)

### Codebase Analysis
- hh-netbox-plugin repository (commit: adb93d2)
- NetBox Hedgehog Plugin v1.x
- Analysis date: 2026-01-06

---

**Document Maintenance:**
- Update this specification when switch profiles change
- Validate against Hedgehog fabric releases
- Test coverage must match specification examples
- Report discrepancies as bugs

**End of Specification**
