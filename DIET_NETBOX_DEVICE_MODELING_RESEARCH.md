# NetBox Native Device Modeling Research for DIET Architecture Alignment

**Research Date:** 2025-12-27
**Issue Reference:** #114
**Objective:** Align DIET topology planning architecture with NetBox's native device modeling patterns

## Executive Summary

NetBox provides comprehensive native device modeling capabilities through `DeviceType`, `ModuleType`, and `InterfaceTemplate`. The current DIET implementation already leverages these core models effectively, with custom extensions (`BreakoutOption` and `DeviceTypeExtension`) only where NetBox doesn't provide equivalent functionality. This research documents NetBox's native capabilities and provides recommendations for full alignment.

## 1. Core Device Schema

### 1.1 Schema Hierarchy

NetBox's device modeling follows a template-to-instance pattern:

```
DeviceType (template)
├─ InterfaceTemplate (1:many)
├─ ModuleBayTemplate (1:many)
├─ PowerPortTemplate (1:many)
├─ ConsolePortTemplate (1:many)
└─ DeviceBayTemplate (1:many) - for chassis/blade scenarios

Device (instance)
├─ Interface (created from InterfaceTemplate)
├─ ModuleBay (created from ModuleBayTemplate)
│  └─ Module (instance of ModuleType)
│     └─ Interface (created from module's InterfaceTemplate)
├─ PowerPort (created from PowerPortTemplate)
└─ DeviceBay (created from DeviceBayTemplate)

ModuleType (template for field-replaceable units)
├─ InterfaceTemplate (1:many)
├─ PowerPortTemplate (1:many)
└─ ConsolePortTemplate (1:many)
```

**Key Relationships:**
- `DeviceType` → `InterfaceTemplate`: One device type can have many interface templates
- `ModuleType` → `InterfaceTemplate`: One module type can have many interface templates
- `Device` → `Module` → `Interface`: Modules install into module bays, bringing their interfaces

### 1.2 Key Models and Fields

**DeviceType** (from `/opt/netbox/netbox/dcim/models/devices.py`):
```python
class DeviceType(ImageAttachmentsMixin, PrimaryModel, WeightMixin):
    manufacturer = ForeignKey('dcim.Manufacturer')
    model = CharField(max_length=100)
    slug = SlugField(max_length=100)
    u_height = DecimalField(max_digits=4, decimal_places=1, default=1.0)
    is_full_depth = BooleanField(default=True)
    subdevice_role = CharField(choices=SubdeviceRoleChoices)  # parent/child
    airflow = CharField(choices=DeviceAirflowChoices)

    # Counter fields (automatically updated)
    interface_template_count = CounterCacheField()
    module_bay_template_count = CounterCacheField()
```

**ModuleType** (from `/opt/netbox/netbox/dcim/models/modules.py`):
```python
class ModuleType(ImageAttachmentsMixin, PrimaryModel, WeightMixin):
    manufacturer = ForeignKey('dcim.Manufacturer')
    model = CharField(max_length=100)
    part_number = CharField(max_length=50, blank=True)
    airflow = CharField(choices=ModuleAirflowChoices)
    profile = ForeignKey('dcim.ModuleTypeProfile')  # NEW in 2025
    attribute_data = JSONField()  # Validated against profile schema
```

**InterfaceTemplate** (from `/opt/netbox/netbox/dcim/models/device_component_templates.py`):
```python
class InterfaceTemplate(ModularComponentTemplateModel):
    device_type = ForeignKey('dcim.DeviceType', null=True)
    module_type = ForeignKey('dcim.ModuleType', null=True)
    name = CharField(max_length=64)  # Supports {module} placeholder
    label = CharField(max_length=64, blank=True)
    type = CharField(choices=InterfaceTypeChoices)  # 100gbase-x-qsfp28, etc.
    enabled = BooleanField(default=True)
    mgmt_only = BooleanField(default=False)
    bridge = ForeignKey('self')  # For bridge interfaces
    poe_mode = CharField(choices=InterfacePoEModeChoices)
    poe_type = CharField(choices=InterfacePoETypeChoices)
```

## 2. Complex Server Modeling

### 2.1 GPU Servers with Multiple NICs

NetBox models complex servers using a combination of `DeviceType` with `ModuleBayTemplate` and `ModuleType` for field-replaceable units like NICs and GPUs.

**Example: GPU Server Configuration**

```yaml
# DeviceType: GPU-Server-B200.yaml
manufacturer: Dell
model: PowerEdge-XE9680-B200
slug: poweredge-xe9680-b200
u_height: 8.0
is_full_depth: true

# Module bays for GPUs
module-bays:
  - name: GPU-1
    position: "1"
  - name: GPU-2
    position: "2"
  # ... up to GPU-8

# Module bays for NICs
module-bays:
  - name: NIC-Slot-1
    position: "NIC1"
  - name: NIC-Slot-2
    position: "NIC2"

# Built-in interfaces (IPMI, management)
interfaces:
  - name: iDRAC
    type: 1000base-t
    mgmt_only: true
  - name: PXE
    type: 1000base-t
```

**ModuleType for NIC (e.g., NVIDIA ConnectX-7)**

```yaml
# ModuleType: ConnectX-7-Dual-400G.yaml
manufacturer: NVIDIA
model: MCX755106AS-HEAT
part_number: MCX755106AS-HEAT
description: ConnectX-7 Dual-Port 400G QSFP112 NIC

interfaces:
  - name: "{module}/0"  # Dynamic naming based on slot
    type: 400gbase-x-qsfpdd
    count: 1
  - name: "{module}/1"
    type: 400gbase-x-qsfpdd
    count: 1
```

**ModuleType for GPU (e.g., NVIDIA B200)**

```yaml
# ModuleType: NVIDIA-B200-GPU.yaml
manufacturer: NVIDIA
model: B200
description: NVIDIA B200 GPU

# Note: GPUs typically don't have network interfaces
# This would be tracked via inventory items or custom fields
# For network topology, focus on NIC modules
```

### 2.2 Dynamic Interface Naming with {module} Token

NetBox supports the `{module}` placeholder in interface template names, which automatically resolves based on the module bay position:

**Example:**
- Module template interface name: `Ethernet{module}/0/1`
- Module bay position: `3`
- Resulting interface name: `Ethernet3/0/1`

**Multi-level nesting** (for chassis with modules containing submodules):
- Template: `Gi{module}/0/[1-48]`
- Module in bay position "3": Results in `Gi3/0/1` through `Gi3/0/48`

### 2.3 Mixed Interface Types

NetBox handles mixed interface types through multiple approaches:

1. **Direct InterfaceTemplate on DeviceType** - for built-in interfaces (IPMI, PXE)
2. **ModuleType with InterfaceTemplate** - for NIC modules with data interfaces
3. **Interface type field** - distinguishes data, management, etc.

**Example Multi-NIC Server:**
```python
# Create DeviceType for server
server_type = DeviceType.objects.create(
    manufacturer=dell,
    model='PowerEdge-XE9680',
    u_height=8,
)

# Built-in IPMI interface
InterfaceTemplate.objects.create(
    device_type=server_type,
    name='iDRAC',
    type='1000base-t',
    mgmt_only=True,
)

# Module bays for NICs
ModuleBayTemplate.objects.create(
    device_type=server_type,
    name='NIC-Slot-1',
    position='1',
)

# NIC ModuleType with 400G interfaces
nic_module = ModuleType.objects.create(
    manufacturer=nvidia,
    model='ConnectX-7-Dual-400G',
)

InterfaceTemplate.objects.create(
    module_type=nic_module,
    name='{module}/0',
    type='400gbase-x-qsfpdd',
)
InterfaceTemplate.objects.create(
    module_type=nic_module,
    name='{module}/1',
    type='400gbase-x-qsfpdd',
)
```

## 3. Switch Port Modeling

### 3.1 Physical Ports with Breakout Options

**NetBox 4.5+ Cable Profiles** (Released 2025)

NetBox 4.5 introduced **Cable Profiles** to better represent breakout cables:

- A cable profile defines how connectors/lanes map between cable ends
- Profiles enable NetBox to trace individual paths through breakout cables
- Example: 4x10GE breakout profile maps four 10GE lanes to one 40GE connector

**Before NetBox 4.5** - Two approaches existed:
1. **Virtual interfaces** - Create child interfaces under parent (logical)
2. **Physical interfaces** - Create discrete interfaces for each breakout lane (preferred)

**Current Best Practice (NetBox 4.5+):**
```python
# Create interface for native 800G port
interface_800g = Interface.objects.create(
    device=switch,
    name='Ethernet1/1',
    type='800gbase-x-qsfpdd',
)

# When breaking out to 4x200G:
# 1. Create 4 discrete 200G interfaces
for i in range(1, 5):
    Interface.objects.create(
        device=switch,
        name=f'Ethernet1/1/{i}',  # Breakout naming
        type='200gbase-x-qsfp56',
    )

# 2. Use Cable Profile to map lanes
cable_profile = CableProfile.objects.create(
    name='800G-to-4x200G-Breakout',
    # Profile defines lane mappings
)
```

### 3.2 Port Groups/Zones

NetBox doesn't have a native "port group" concept, but provides several patterns:

**Option 1: InterfaceTemplate + Custom Fields**
```python
# Add custom field to InterfaceTemplate
CustomField.objects.create(
    name='port_zone',
    type='text',
    content_types=['dcim.interfacetemplate'],
)

# Tag interfaces during template creation
InterfaceTemplate.objects.create(
    device_type=switch_type,
    name='Ethernet1/1',
    type='800gbase-x-qsfpdd',
    custom_field_data={'port_zone': 'server-ports'},
)
```

**Option 2: Tags**
```python
# Use NetBox's tagging system
server_port_tag = Tag.objects.create(name='server-ports', slug='server-ports')
uplink_tag = Tag.objects.create(name='uplink-ports', slug='uplink-ports')

# Apply during template creation
template = InterfaceTemplate.objects.create(...)
template.tags.add(server_port_tag)
```

**Option 3: Custom Model (Current DIET Approach)**
```python
# SwitchPortZone model provides structured grouping
class SwitchPortZone(NetBoxModel):
    switch_class = ForeignKey(PlanSwitchClass)
    zone_name = CharField(max_length=100)
    zone_type = CharField(choices=PortZoneTypeChoices)
    port_spec = CharField(max_length=200)  # e.g., '1-48', '1-32:2'
    breakout_option = ForeignKey(BreakoutOption, null=True)
```

**DIET Current Implementation** uses Option 3 - a custom `SwitchPortZone` model that provides:
- Structured port range specifications (`1-48`, `1,3,5`, `1-32:2`)
- Breakout option associations
- Allocation strategies (sequential, alternating, custom)
- Priority-based ordering

**Recommendation:** Continue using custom `SwitchPortZone` model as NetBox doesn't provide equivalent structured port grouping with allocation logic.

### 3.3 Uplink vs Downlink Port Designations

NetBox doesn't enforce uplink/downlink semantics natively, but provides patterns:

**Option 1: Custom Fields**
```python
CustomField.objects.create(
    name='port_direction',
    type='select',
    choices=['uplink', 'downlink', 'peer'],
    content_types=['dcim.interface', 'dcim.interfacetemplate'],
)
```

**Option 2: Tags** (simpler, built-in)
```python
uplink_tag = Tag.objects.create(name='uplink', color='blue')
downlink_tag = Tag.objects.create(name='downlink', color='green')
```

**Option 3: DeviceTypeExtension** (DIET current approach)
```python
class DeviceTypeExtension(NetBoxModel):
    device_type = OneToOneField(DeviceType)
    uplink_ports_per_switch = IntegerField()
    # Combined with SwitchPortZone for structured allocation
```

## 4. Interface Naming

### 4.1 NetBox Native Naming Patterns

**Module-Based Dynamic Naming:**
```python
# InterfaceTemplate with {module} placeholder
InterfaceTemplate.objects.create(
    module_type=line_card,
    name='Gi{module}/0/[1-48]',
    type='1000base-t',
)

# When installed in bay position "3":
# Resulting interfaces: Gi3/0/1, Gi3/0/2, ... Gi3/0/48
```

**Range Notation:**
```python
# Create multiple interfaces with range syntax
InterfaceTemplate.objects.create(
    device_type=switch,
    name='Ethernet1/[1-64]',  # Creates 64 templates
    type='800gbase-x-qsfpdd',
)
```

### 4.2 Bulk Rename with Regex

NetBox supports bulk interface renaming using regex patterns:

**Example: Adding Stack Member Prefix**
- Find pattern: `(\d+)`
- Replace pattern: `2/\1`
- Result: `1` → `2/1`, `2` → `2/2`, etc.

**Example: Module Slot Prefix**
- Find pattern: `GigabitEthernet(\d+)`
- Replace pattern: `Gi1/0/\1`
- Result: `GigabitEthernet1` → `Gi1/0/1`

### 4.3 Label Field

NetBox provides separate `label` and `name` fields:
- **name** - Logical/CLI name (e.g., `eth0`, `eno1`)
- **label** - Physical label on device (e.g., `1`, `Eth 2`)

```python
InterfaceTemplate.objects.create(
    device_type=server,
    name='eno1',        # Linux interface name
    label='Ethernet 1', # Physical port label
    type='1000base-t',
)
```

### 4.4 Customization via Naming Conventions

**DIET Approach:** Custom `NamingTemplate` model provides:
- Template-based device naming (e.g., `{fabric}-{role}-{number}`)
- Validation of naming patterns
- Consistent naming across topology plans

**NetBox Native:** Doesn't enforce naming conventions, but provides:
- Custom validation rules via `CUSTOM_VALIDATORS` config
- Custom scripts for enforcing standards
- API/bulk edit for standardization

## 5. Bulk Operations

### 5.1 Creating Many Devices from DeviceType

**Pattern 1: Django ORM Bulk Create**
```python
from dcim.models import Device, DeviceType, DeviceRole, Site

device_type = DeviceType.objects.get(model='DS5000')
role = DeviceRole.objects.get(name='Leaf')
site = Site.objects.get(name='DC1')

# Bulk create devices
devices = []
for i in range(1, 33):
    devices.append(Device(
        name=f'leaf-{i:02d}',
        device_type=device_type,
        role=role,
        site=site,
    ))

Device.objects.bulk_create(devices)
```

**Pattern 2: NetBox Custom Script**
```python
from extras.scripts import Script
from dcim.models import Device, DeviceType, Site

class ProvisionSwitches(Script):
    class Meta:
        name = "Provision Switch Cluster"
        description = "Create multiple switches from template"

    def run(self, data, commit):
        device_type = DeviceType.objects.get(model='DS5000')

        for i in range(1, 33):
            device = Device(
                name=f'leaf-{i:02d}',
                device_type=device_type,
                site=data['site'],
                role=data['role'],
            )
            device.full_clean()  # IMPORTANT: Always validate
            device.save()

            self.log_success(f"Created {device.name}")
```

**Pattern 3: PyNetBox API**
```python
import pynetbox

nb = pynetbox.api('http://netbox.local', token='your-token')

# Bulk create via API
devices = []
for i in range(1, 33):
    devices.append({
        'name': f'leaf-{i:02d}',
        'device_type': device_type_id,
        'role': role_id,
        'site': site_id,
    })

nb.dcim.devices.create(devices)  # Accepts list for bulk
```

### 5.2 Automatic Interface Generation

**Automatic on Device Creation:**

When a `Device` is created from a `DeviceType`, NetBox automatically:
1. Creates all interfaces from `InterfaceTemplate` definitions
2. Creates all module bays from `ModuleBayTemplate` definitions
3. Creates all power ports, console ports, etc.

```python
# Create device
device = Device.objects.create(
    name='spine-01',
    device_type=ds5000_type,  # Has 64 InterfaceTemplates
    site=site,
    role=role,
)

# Interfaces are automatically created!
assert device.interfaces.count() == 64  # True
```

**Automatic on Module Installation:**

When a `Module` is installed into a `ModuleBay`, NetBox automatically:
1. Creates all interfaces from the `ModuleType`'s `InterfaceTemplate` definitions
2. Resolves `{module}` placeholders in interface names
3. Can optionally adopt existing unassigned interfaces

```python
# Install NIC module
module = Module.objects.create(
    device=server,
    module_bay=server.modulebays.get(name='NIC-Slot-1'),
    module_type=connectx7_type,  # Has 2 InterfaceTemplates
)

# Interfaces automatically created with {module} resolved!
# NIC-Slot-1/0, NIC-Slot-1/1
```

**Component Adoption Pattern:**
```python
# When creating a module, can adopt existing interfaces
module = Module(
    device=device,
    module_bay=bay,
    module_type=module_type,
)
module._adopt_components = True  # Adopt unassigned components
module.save()
```

**Disable Automatic Creation:**
```python
module = Module(...)
module._disable_replication = True  # Don't auto-create components
module.save()
```

### 5.3 Bulk Cable Creation

**Pattern 1: Django ORM**
```python
from dcim.models import Cable, Interface

# Get interfaces
leaf_interfaces = Interface.objects.filter(
    device__name__startswith='leaf-',
    name__startswith='Ethernet1/49',
)

spine_interfaces = Interface.objects.filter(
    device__name__startswith='spine-',
)

# Create cables
cables = []
for leaf_int, spine_int in zip(leaf_interfaces, spine_interfaces):
    cables.append(Cable(
        termination_a=leaf_int,
        termination_b=spine_int,
        type='cat6a',
        status='connected',
    ))

Cable.objects.bulk_create(cables)
```

**Pattern 2: NetBox Custom Script**
```python
from extras.scripts import Script
from dcim.models import Cable

class CableLeafToSpine(Script):
    class Meta:
        name = "Cable Leaf-Spine Topology"

    def run(self, data, commit):
        # Calculate cable requirements
        for leaf in Leaf.objects.all():
            for uplink in range(1, 5):  # 4 uplinks per leaf
                spine = calculate_spine(leaf, uplink)

                cable = Cable(
                    termination_a=leaf.interfaces.get(name=f'Ethernet1/{48+uplink}'),
                    termination_b=spine.interfaces.get(name=f'Ethernet1/{calculate_port()}'),
                )
                cable.full_clean()
                cable.save()

                self.log_success(f"Cabled {leaf} to {spine}")
```

**Pattern 3: PyNetBox API with Parallel Processing**
```python
import pynetbox
from concurrent.futures import ThreadPoolExecutor

nb = pynetbox.api('http://netbox.local', token='token')

def create_cable(leaf_int_id, spine_int_id):
    return nb.dcim.cables.create({
        'termination_a_type': 'dcim.interface',
        'termination_a_id': leaf_int_id,
        'termination_b_type': 'dcim.interface',
        'termination_b_id': spine_int_id,
        'status': 'connected',
    })

# Parallel cable creation
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = []
    for leaf_int, spine_int in cable_pairs:
        futures.append(
            executor.submit(create_cable, leaf_int.id, spine_int.id)
        )

    # Wait for completion
    results = [f.result() for f in futures]
```

## 6. DIET Alignment Analysis

### 6.1 Current DIET Architecture (Good Practices)

The current DIET implementation already follows NetBox best practices:

✅ **Uses NetBox Core Models:**
- `PlanServerClass.server_device_type = ForeignKey(DeviceType)`
- `PlanServerConnection.nic_module_type = ForeignKey(ModuleType)`
- `PlanSwitchClass.device_type_extension.device_type = DeviceType`

✅ **Custom Models Only Where Needed:**
- `BreakoutOption` - NetBox doesn't model breakout math/logic
- `DeviceTypeExtension` - Hedgehog-specific metadata (OneToOne pattern)
- `SwitchPortZone` - Structured port grouping with allocation logic

✅ **Follows Plugin Best Practices:**
- OneToOne extension pattern (doesn't modify core models)
- ForeignKey relationships to core models
- Leverages NetBox's device catalog

### 6.2 Architecture Example from Current Codebase

**Seed Data Migration (0009_seed_data_hedgehog_devices.py):**
```python
# Create DeviceType
ds5000, created = DeviceType.objects.get_or_create(
    manufacturer=celestica,
    model='DS5000',
    defaults={
        'slug': 'ds5000',
        'u_height': 1,
        'is_full_depth': True,
        'comments': '64-port 800G QSFP-DD switch',
    }
)

# Create InterfaceTemplates
if created:
    for i in range(1, 65):
        InterfaceTemplate.objects.create(
            device_type=ds5000,
            name=f'Ethernet1/{i}',
            type='800gbase-x-qsfpdd',
        )

    # Add Hedgehog-specific metadata
    DeviceTypeExtension.objects.create(
        device_type=ds5000,
        mclag_capable=False,
        hedgehog_roles=['spine', 'server-leaf'],
        supported_breakouts=['1x800g', '2x400g', '4x200g', '8x100g'],
        native_speed=800,
        notes='Supports 800G native with breakout options.',
    )
```

**Planning Model Usage:**
```python
# Create switch class referencing NetBox DeviceType
switch_class = PlanSwitchClass.objects.create(
    plan=topology_plan,
    switch_class_id='fe-gpu-leaf',
    fabric='Frontend',
    hedgehog_role='server-leaf',
    device_type_extension=ds5000_extension,  # Links to DeviceType
    uplink_ports_per_switch=4,
)

# Port zones reference switch class
SwitchPortZone.objects.create(
    switch_class=switch_class,
    zone_name='server-ports',
    zone_type='downlink',
    port_spec='1-60',  # Ports 1-60 for servers
    breakout_option=breakout_4x200g,
)
```

### 6.3 What Could Be Further Aligned

**Potential Improvements:**

1. **Port Count Calculation** (TODO in code):
```python
# Current: Hardcoded in topology_calculations.py
# TODO: Replace hardcoded port count with actual count from InterfaceTemplate
#       Query: dcim.InterfaceTemplate.objects.filter(
#           device_type=switch_class.device_type_extension.device_type
#       ).count()
```

**Recommendation:** Implement dynamic port counting from InterfaceTemplates

2. **Module-Based NIC Modeling:**

Current DIET uses `nic_module_type` on `PlanServerConnection` (good!), but doesn't fully leverage:
- Dynamic interface naming with `{module}` placeholders
- Automatic interface generation when modules are installed

**Recommendation:** When generating actual `Device` instances from topology plans:
```python
# Create server device
server = Device.objects.create(
    name=f'gpu-server-{i}',
    device_type=server_class.server_device_type,
    site=site,
    role=role,
)

# Install NIC modules
for connection in server_class.connections.all():
    # Find appropriate module bay
    bay = server.modulebays.get(name=connection.nic_slot)

    # Install module (interfaces auto-created!)
    module = Module.objects.create(
        device=server,
        module_bay=bay,
        module_type=connection.nic_module_type,
    )
    # module.interfaces.count() now reflects InterfaceTemplates
```

3. **Breakout Modeling:**

Current DIET has custom `BreakoutOption` model (appropriate - NetBox doesn't model breakout math).

However, NetBox 4.5+ `CableProfile` could be used for actual cable tracing after breakout:

```python
# DIET BreakoutOption calculates breakout math (keep this)
breakout = BreakoutOption.objects.create(
    breakout_id='4x200g',
    from_speed=800,
    logical_ports=4,
    logical_speed=200,
)

# When generating actual devices, use CableProfile for tracing
cable_profile = CableProfile.objects.create(
    name='800G-to-4x200G',
    # Defines lane mappings for path tracing
)
```

**Recommendation:** Continue using `BreakoutOption` for planning calculations, optionally use `CableProfile` for operational device generation.

### 6.4 Recommendations Summary

| Area | Current Approach | Recommendation | Priority |
|------|-----------------|----------------|----------|
| Device Types | ✅ Uses `dcim.DeviceType` | Continue | N/A |
| Module Types | ✅ Uses `dcim.ModuleType` for NICs | Continue | N/A |
| Interface Templates | ✅ Created in seed data | Use for port counts in calc engine | High |
| Breakout Options | ✅ Custom model | Keep custom model, NetBox doesn't provide equivalent | N/A |
| DeviceTypeExtension | ✅ OneToOne extension pattern | Continue, follows best practices | N/A |
| SwitchPortZone | ✅ Custom model | Keep custom model, provides structured allocation | N/A |
| Port Counting | ⚠️ Hardcoded | Query InterfaceTemplate.count() | High |
| Module Installation | ⚠️ Planning-only | Leverage auto-generation in device creation | Medium |
| Cable Profiles | ❌ Not used | Consider for operational phase | Low |

## 7. Code Examples and Patterns

### 7.1 DeviceType Creation with InterfaceTemplates

**Example: Creating a GPU Server DeviceType**

```python
from dcim.models import Manufacturer, DeviceType, ModuleBayTemplate, InterfaceTemplate

# Create manufacturer
dell = Manufacturer.objects.get_or_create(
    name='Dell',
    defaults={'slug': 'dell'}
)[0]

# Create server device type
gpu_server = DeviceType.objects.create(
    manufacturer=dell,
    model='PowerEdge-XE9680-B200',
    slug='xe9680-b200',
    u_height=8,
    is_full_depth=True,
    comments='8x NVIDIA B200 GPU server with dual 400G NICs',
)

# Built-in management interfaces
InterfaceTemplate.objects.create(
    device_type=gpu_server,
    name='iDRAC',
    type='1000base-t',
    mgmt_only=True,
    description='Integrated Dell Remote Access Controller',
)

InterfaceTemplate.objects.create(
    device_type=gpu_server,
    name='PXE',
    type='1000base-t',
    description='PXE boot interface',
)

# Module bays for NICs
for i in range(1, 3):  # 2 NIC slots
    ModuleBayTemplate.objects.create(
        device_type=gpu_server,
        name=f'NIC-Slot-{i}',
        position=str(i),
    )

# Module bays for GPUs (for inventory tracking)
for i in range(1, 9):  # 8 GPU slots
    ModuleBayTemplate.objects.create(
        device_type=gpu_server,
        name=f'GPU-{i}',
        position=f'GPU{i}',
    )
```

**Example: Creating NIC ModuleType**

```python
from dcim.models import ModuleType, InterfaceTemplate

# Create NIC module type
nic_cx7 = ModuleType.objects.create(
    manufacturer=nvidia,
    model='MCX755106AS-HEAT',
    part_number='MCX755106AS-HEAT',
    description='ConnectX-7 Dual-Port 400G QSFP112',
)

# Interfaces on the NIC (using {module} for dynamic naming)
InterfaceTemplate.objects.create(
    module_type=nic_cx7,
    name='{module}/0',
    type='400gbase-x-qsfpdd',
    description='Port 0',
)

InterfaceTemplate.objects.create(
    module_type=nic_cx7,
    name='{module}/1',
    type='400gbase-x-qsfpdd',
    description='Port 1',
)
```

### 7.2 Device Creation from DeviceType

**Example: Creating Multiple Servers**

```python
from dcim.models import Device, DeviceType, DeviceRole, Site, Module

# Get references
gpu_server_type = DeviceType.objects.get(slug='xe9680-b200')
nic_type = ModuleType.objects.get(model='MCX755106AS-HEAT')
site = Site.objects.get(name='DC1')
role = DeviceRole.objects.get(name='Compute')

# Create 128 GPU servers
devices = []
for i in range(1, 129):
    device = Device(
        name=f'gpu-server-{i:03d}',
        device_type=gpu_server_type,
        site=site,
        role=role,
    )
    device.full_clean()  # Validate before save
    devices.append(device)

Device.objects.bulk_create(devices)

# Install NIC modules (must be after devices are saved)
for device in Device.objects.filter(name__startswith='gpu-server-'):
    # Install 2 NICs per server
    for slot in ['1', '2']:
        bay = device.modulebays.get(position=slot)
        module = Module.objects.create(
            device=device,
            module_bay=bay,
            module_type=nic_type,
            serial=f'SN-{device.name}-NIC{slot}',
        )
        # Interfaces auto-created: NIC-Slot-1/0, NIC-Slot-1/1, etc.
```

### 7.3 Querying Device Topology

**Example: Get All Interfaces for a Device**

```python
device = Device.objects.get(name='gpu-server-001')

# All interfaces (both device-level and module-level)
all_interfaces = device.interfaces.all()

# Filter by type
mgmt_interfaces = device.interfaces.filter(mgmt_only=True)
data_interfaces = device.interfaces.filter(type='400gbase-x-qsfpdd')

# Filter by module
nic1_interfaces = device.interfaces.filter(
    module__module_bay__name='NIC-Slot-1'
)
```

**Example: Get Available Ports on Switch**

```python
switch = Device.objects.get(name='leaf-01')

# Get all interfaces
all_ports = switch.interfaces.all()

# Filter unconnected ports
available = switch.interfaces.filter(cable__isnull=True)

# Get uplink ports (using custom field or tag)
uplinks = switch.interfaces.filter(tags__name='uplink')

# Get ports by speed
ports_400g = switch.interfaces.filter(type='400gbase-x-qsfpdd')
```

### 7.4 Custom Validation Example

**Example: Validate DeviceType has Required Roles**

```python
# In plugin's validators.py
from django.core.exceptions import ValidationError
from utilities.validators import CustomValidator

class HedgehogDeviceTypeValidator(CustomValidator):
    """Validate that DeviceTypes with Hedgehog metadata have valid roles."""

    def validate(self, instance, request):
        # Only validate if this DeviceType has Hedgehog metadata
        if not hasattr(instance, 'hedgehog_metadata'):
            return

        metadata = instance.hedgehog_metadata

        # Validate hedgehog_roles is not empty
        if not metadata.hedgehog_roles:
            self.fail(
                "DeviceType with Hedgehog metadata must have at least one role",
                field='hedgehog_metadata'
            )

        # Validate roles are from allowed set
        allowed_roles = ['spine', 'server-leaf', 'border-leaf', 'virtual']
        invalid_roles = set(metadata.hedgehog_roles) - set(allowed_roles)
        if invalid_roles:
            self.fail(
                f"Invalid Hedgehog roles: {invalid_roles}. "
                f"Allowed: {allowed_roles}",
                field='hedgehog_metadata'
            )

# Register in configuration.py
CUSTOM_VALIDATORS = {
    'dcim.devicetype': [
        HedgehogDeviceTypeValidator(),
    ]
}
```

## 8. Community Resources

### 8.1 NetBox Device Type Library

The [netbox-community/devicetype-library](https://github.com/netbox-community/devicetype-library) repository contains:
- 2000+ community-sourced DeviceType definitions
- YAML-based format for easy import
- Organized by manufacturer
- Examples of complex devices with modules

**Example YAML Structure** (Cisco N9K-X9732C-EX Module):
```yaml
manufacturer: Cisco
model: N9K-X9732C-EX
part_number: N9K-X9732C-EX
description: Cisco Nexus 9500 32p 100G QSFP cloud-scale line card
weight: 5.5
weight_unit: kg
interfaces:
  - name: Ethernet{module}/1-32
    type: 100gbase-x-qsfp28
    count: 32
```

### 8.2 NetBox Documentation

Key documentation pages:
- [Device Types](https://netboxlabs.com/docs/netbox/models/dcim/devicetype/)
- [Module Types](https://netboxlabs.com/docs/netbox/models/dcim/moduletype/)
- [Interface Templates](https://netboxlabs.com/docs/netbox/models/dcim/interfacetemplate/)
- [Front Ports](https://netboxlabs.com/docs/netbox/models/dcim/frontport/) / [Rear Ports](https://netboxlabs.com/docs/netbox/models/dcim/rearport/)
- [Custom Validation](https://netboxlabs.com/docs/netbox/customization/custom-validation/)
- [Custom Scripts](https://netboxlabs.com/docs/netbox/customization/custom-scripts/)
- [Extending Models](https://netboxlabs.com/docs/netbox/en/stable/development/extending-models/)
- [Devices & Cabling](https://netboxlabs.com/docs/netbox/features/devices-cabling/)

### 8.3 Community Discussions

Relevant GitHub discussions:
- [Representing breakout interfaces/cable](https://github.com/netbox-community/netbox/discussions/11917)
- [Improved Breakout Modeling](https://github.com/netbox-community/netbox/discussions/11158)
- [Network card modeling for servers](https://github.com/netbox-community/devicetype-library/discussions/1342)
- [Community approach to the new modules model](https://github.com/netbox-community/netbox/discussions/9238)
- [Proper way to model interfaces using SFPs as Module Types](https://github.com/netbox-community/netbox/discussions/19670)

### 8.4 Automation Tools

- **pynetbox** - Official Python API client: [GitHub](https://github.com/netbox-community/pynetbox)
- **Device-Type-Library-Import** - Import tool: [GitHub](https://github.com/netbox-community/Device-Type-Library-Import)
- **netbox-agent** - Auto-discovery agent: [PyPI](https://pypi.org/project/netbox-agent/)

## 9. Implementation Roadmap for Issue #114

### Phase 1: Documentation and Analysis (Completed)
- ✅ Research NetBox device modeling capabilities
- ✅ Document current DIET alignment
- ✅ Identify gaps and opportunities

### Phase 2: Port Count from InterfaceTemplates (High Priority)
```python
# In topology_calculations.py
def get_switch_port_count(device_type_extension):
    """Get total port count from InterfaceTemplates."""
    return InterfaceTemplate.objects.filter(
        device_type=device_type_extension.device_type
    ).count()

# Replace hardcoded values
# OLD: total_ports = 64
# NEW: total_ports = get_switch_port_count(switch_class.device_type_extension)
```

### Phase 3: Enhanced Module Support (Medium Priority)
- Add module bay definitions to server DeviceTypes
- Create ModuleTypes for common NICs (CX-7, BF-3)
- Update planning models to track module bay positions
- Leverage automatic interface generation in device creation

### Phase 4: Operational Device Generation (Future)
- Implement bulk device creation from topology plans
- Auto-install modules based on PlanServerConnection specs
- Generate cables based on calculated topology
- Optional: Use CableProfile for breakout tracing

## 10. Conclusion

NetBox provides robust native device modeling capabilities that DIET already leverages effectively. The current architecture follows NetBox plugin best practices:

**What DIET Does Well:**
- Uses NetBox core models (DeviceType, ModuleType) as primary catalog
- Extends with OneToOne pattern (DeviceTypeExtension) for Hedgehog metadata
- Custom models only where NetBox doesn't provide functionality (BreakoutOption, SwitchPortZone)

**Key Recommendations:**
1. Replace hardcoded port counts with InterfaceTemplate queries (high priority)
2. Leverage automatic interface generation when creating operational devices
3. Consider NetBox 4.5+ Cable Profiles for breakout cable tracing
4. Continue current extension pattern - it aligns with NetBox best practices

**No Major Refactoring Needed:** The DIET architecture is well-aligned with NetBox patterns. Recommended changes are incremental improvements, not architectural overhauls.

---

## Sources

- [NetBox Device Type Library](https://github.com/netbox-community/devicetype-library)
- [Module Types Documentation](https://netboxlabs.com/docs/netbox/models/dcim/moduletype/)
- [Device Types Documentation](https://netboxlabs.com/docs/netbox/models/dcim/devicetype/)
- [Interface Templates Documentation](https://netboxlabs.com/docs/netbox/models/dcim/interfacetemplate/)
- [Devices & Cabling](https://netboxlabs.com/docs/netbox/features/devices-cabling/)
- [NetBox 4.5 Beta Announcement](https://netboxlabs.com/blog/announcing-the-netbox-4-5-beta/)
- [Representing breakout interfaces](https://github.com/netbox-community/netbox/discussions/11917)
- [Improved Breakout Modeling](https://github.com/netbox-community/netbox/discussions/11158)
- [Network card modeling discussion](https://github.com/netbox-community/devicetype-library/discussions/1342)
- [Module Types with Dynamic Naming](https://github.com/netbox-community/netbox/discussions/13811)
- [Extending Models](https://netboxlabs.com/docs/netbox/en/stable/development/extending-models/)
- [Custom Validation](https://netboxlabs.com/docs/netbox/customization/custom-validation/)
- [Custom Scripts](https://netboxlabs.com/docs/netbox/customization/custom-scripts/)
- [PyNetBox Documentation](https://ttl255.com/pynetbox-netbox-python-api-client-part-2-creating-objects/)
- [Bulk Interface Renaming](https://constantpinger.home.blog/2022/05/13/renaming-interfaces-in-bulk-in-netbox/)
- [Django OneToOne Relationships](https://docs.djangoproject.com/en/4.2/topics/db/examples/one_to_one/)
