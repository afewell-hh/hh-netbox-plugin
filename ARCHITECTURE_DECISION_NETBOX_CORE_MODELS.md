# Architecture Decision: Use NetBox Core Models for Reference Data

**Date:** 2025-12-19
**Decision By:** Agent C (recommended), Agent A (analyzing)
**Status:** Proposed - Awaiting User Confirmation
**Impact:** High - Changes data model architecture for DIET tools

---

## Context

Agent C reviewed the DIET topology planning PRD (issue #83) and identified that the proposed custom reference data models (SwitchModel, NICModel, SwitchPortGroup) duplicate functionality already present in NetBox's core DCIM models.

**Agent C's Comment (Issue #84):**
> "Goal alignment: keep the spreadsheet-like planning workflow, but **reuse NetBox's native inventory models wherever possible** to avoid duplicated reference data."

## Current Approach (Original PRD #83)

### Custom Reference Data Models

```python
# netbox_hedgehog/models/topology_planning/reference_data.py

class SwitchModel(NetBoxModel):
    """Custom model for switch specifications"""
    model_id = models.CharField(max_length=100, unique=True)
    vendor = models.CharField(max_length=100)
    part_number = models.CharField(max_length=100)
    total_ports = models.IntegerField()
    mclag_capable = models.BooleanField(default=False)
    hedgehog_roles = models.JSONField(default=list)
    # ... additional fields

class SwitchPortGroup(NetBoxModel):
    """Custom model for port groups with breakout capabilities"""
    switch_model = models.ForeignKey(SwitchModel, ...)
    group_name = models.CharField(max_length=100)
    port_count = models.IntegerField()
    native_speed = models.IntegerField()
    supported_breakouts = models.CharField(max_length=200)
    # ... additional fields

class NICModel(NetBoxModel):
    """Custom model for NIC specifications"""
    model_id = models.CharField(max_length=100, unique=True)
    vendor = models.CharField(max_length=100)
    part_number = models.CharField(max_length=100)
    port_count = models.IntegerField()
    port_speed = models.IntegerField()
    # ... additional fields

class BreakoutOption(NetBoxModel):
    """Custom model for breakout configurations"""
    breakout_id = models.CharField(max_length=50, unique=True)
    from_speed = models.IntegerField()
    logical_ports = models.IntegerField()
    logical_speed = models.IntegerField()
    # ... additional fields
```

**Problems with this approach:**
- ❌ Duplicates NetBox's existing device catalog (dcim.DeviceType)
- ❌ Requires maintaining parallel data sets
- ❌ Users must enter switch/NIC data in two places
- ❌ Data can get out of sync between DIET and NetBox inventory
- ❌ Doesn't leverage NetBox's extensive device type features
- ❌ Migration compatibility issues with existing operational models

## Proposed Approach (Agent C's Recommendation)

### Leverage NetBox Core DCIM Models

**Map to NetBox Core:**

| DIET Model | NetBox Core Model | Notes |
|------------|-------------------|-------|
| `SwitchModel` | `dcim.DeviceType` + `dcim.Manufacturer` | NetBox already has comprehensive device catalog |
| `NICModel` | `dcim.ModuleType` or `dcim.DeviceType` | Use ModuleType for add-in NICs, DeviceType for servers |
| Port specifications | `dcim.InterfaceTemplate` | NetBox models interface types, speeds per device |
| `BreakoutOption` | **Keep Custom** | NetBox doesn't model breakout math well |
| `SwitchPortGroup` | **Keep Custom or Infer** | May keep for breakout groupings, or infer from InterfaceTemplates |

**Revised Model Structure:**

```python
# netbox_hedgehog/models/topology_planning/reference_data.py

from dcim.models import DeviceType, Manufacturer, ModuleType

# REMOVE: SwitchModel (use dcim.DeviceType instead)
# REMOVE: NICModel (use dcim.ModuleType or DeviceType instead)

class BreakoutOption(NetBoxModel):
    """
    Breakout configuration for port speeds.
    NetBox doesn't model breakout math, so this stays custom.
    """
    breakout_id = models.CharField(max_length=50, unique=True)
    from_speed = models.IntegerField(help_text="Native port speed in Gbps")
    logical_ports = models.IntegerField(help_text="Number of logical ports after breakout")
    logical_speed = models.IntegerField(help_text="Speed per logical port in Gbps")
    optic_type = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['-from_speed', '-logical_speed']
        verbose_name = "Breakout Option"
        verbose_name_plural = "Breakout Options"

    def __str__(self):
        return f"{self.logical_ports}x{self.logical_speed}G (from {self.from_speed}G)"


class DeviceTypeExtension(NetBoxModel):
    """
    Optional: Hedgehog-specific metadata for NetBox DeviceTypes.
    Only needed if NetBox DeviceType doesn't have all fields we need.
    """
    device_type = models.OneToOneField(
        DeviceType,
        on_delete=models.CASCADE,
        related_name='hedgehog_metadata'
    )
    mclag_capable = models.BooleanField(
        default=False,
        help_text="Whether this device supports MCLAG"
    )
    hedgehog_roles = models.JSONField(
        default=list,
        blank=True,
        help_text="Supported Hedgehog roles: spine, server-leaf, border-leaf"
    )

    class Meta:
        verbose_name = "Device Type Extension (Hedgehog)"
        verbose_name_plural = "Device Type Extensions (Hedgehog)"

    def __str__(self):
        return f"Hedgehog metadata for {self.device_type}"
```

**Updated Planning Models:**

```python
# netbox_hedgehog/models/topology_planning/topology_plans.py

from dcim.models import DeviceType, ModuleType

class PlanSwitchClass(NetBoxModel):
    """Switch class in a topology plan"""
    plan = models.ForeignKey(TopologyPlan, on_delete=models.CASCADE)
    switch_class_id = models.CharField(max_length=50)

    # CHANGED: Reference NetBox DeviceType instead of custom SwitchModel
    switch_device_type = models.ForeignKey(
        DeviceType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        limit_choices_to={'is_full_depth': False},  # Switches are typically half-depth
        help_text="NetBox device type for this switch class"
    )

    fabric = models.CharField(max_length=20, choices=FabricChoices.choices)
    hedgehog_role = models.CharField(max_length=20, choices=RoleChoices.choices)
    uplink_ports_per_switch = models.IntegerField(default=0)
    mclag_pair = models.BooleanField(default=False)

    calculated_quantity = models.IntegerField(default=0)
    override_quantity = models.IntegerField(null=True, blank=True)

    @property
    def effective_quantity(self):
        return self.override_quantity if self.override_quantity is not None else self.calculated_quantity

    @property
    def total_ports(self):
        """Get total ports from NetBox DeviceType"""
        if self.switch_device_type:
            return self.switch_device_type.interfacetemplates.count()
        return 0

    @property
    def mclag_capable(self):
        """Check MCLAG capability from extension or default to False"""
        if self.switch_device_type and hasattr(self.switch_device_type, 'hedgehog_metadata'):
            return self.switch_device_type.hedgehog_metadata.mclag_capable
        return False


class PlanServerClass(NetBoxModel):
    """Server class in a topology plan"""
    plan = models.ForeignKey(TopologyPlan, on_delete=models.CASCADE)
    server_class_id = models.CharField(max_length=50)

    # CHANGED: Reference NetBox DeviceType
    server_device_type = models.ForeignKey(
        DeviceType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="NetBox device type for this server class"
    )

    quantity = models.IntegerField(default=0)
    gpus_per_server = models.IntegerField(default=0)
    category = models.CharField(max_length=20, choices=CategoryChoices.choices)


class PlanServerConnection(NetBoxModel):
    """Connection definition for a server class"""
    server_class = models.ForeignKey(PlanServerClass, on_delete=models.CASCADE)
    connection_id = models.CharField(max_length=50)

    # CHANGED: Reference NetBox ModuleType for NICs
    nic_module_type = models.ForeignKey(
        ModuleType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="NetBox module type for this NIC"
    )

    nic_slot = models.CharField(max_length=20)
    ports_per_connection = models.IntegerField(default=1)
    speed = models.IntegerField(help_text="Connection speed in Gbps")
    # ... rest of fields
```

## Benefits of Proposed Approach

### 1. Eliminates Data Duplication
- ✅ Switch specifications entered once in NetBox, reused everywhere
- ✅ No need to maintain parallel switch/NIC catalogs
- ✅ Single source of truth for device specifications

### 2. Leverages NetBox Features
- ✅ Use NetBox's extensive device type library
- ✅ Benefit from NetBox's device type import tools
- ✅ InterfaceTemplate provides detailed port information
- ✅ Manufacturer relationships already built-in

### 3. Better Integration
- ✅ DIET planning data aligns with operational inventory
- ✅ Can transition from plan to deployment using same device types
- ✅ Reports and dashboards work across planning and operations

### 4. Reduces Maintenance Burden
- ✅ Fewer custom models to maintain
- ✅ Let NetBox handle device catalog complexity
- ✅ Updates to NetBox device types automatically available in DIET

### 5. Follows NetBox Best Practices
- ✅ Recommended approach from Agent C (NetBox expert)
- ✅ Aligns with how other NetBox plugins extend functionality
- ✅ Users already familiar with DeviceType management

## Drawbacks & Considerations

### 1. Additional Complexity for Users
- ⚠️ Must set up DeviceTypes in NetBox before planning
- ⚠️ More steps if device catalog is empty
- **Mitigation:** Provide seed data migration with common Hedgehog devices

### 2. Learning Curve
- ⚠️ Users need to understand NetBox DeviceType model
- **Mitigation:** Documentation and examples

### 3. NetBox Model Limitations
- ⚠️ DeviceType might not have all Hedgehog-specific fields
- **Mitigation:** Use DeviceTypeExtension for additional metadata

### 4. Migration Path
- ⚠️ If users already have SwitchModel data, need migration script
- **Mitigation:** Currently no users, clean slate

## Implementation Impact

### What Changes

1. **Models to Remove:**
   - ❌ `SwitchModel`
   - ❌ `NICModel`
   - ❌ `SwitchPortGroup` (maybe - assess if needed)

2. **Models to Keep:**
   - ✅ `BreakoutOption` (NetBox doesn't model this)
   - ✅ All planning models (TopologyPlan, PlanServerClass, PlanSwitchClass, etc.)

3. **Models to Add:**
   - ➕ `DeviceTypeExtension` (optional, for Hedgehog-specific metadata)

4. **Foreign Keys to Update:**
   - `PlanSwitchClass.switch_model` → `PlanSwitchClass.switch_device_type` (FK to DeviceType)
   - `PlanServerClass.server_model` → `PlanServerClass.server_device_type` (FK to DeviceType)
   - `PlanServerConnection.nic_model` → `PlanServerConnection.nic_module_type` (FK to ModuleType)

5. **Migration Changes:**
   - ❌ Migration 0008 creates wrong tables (SwitchModel, NICModel, SwitchPortGroup)
   - ✅ Need new migration that creates BreakoutOption + DeviceTypeExtension only

### What Stays the Same

- ✅ Planning workflow (user enters server quantities, gets switch calculations)
- ✅ YAML generation logic
- ✅ Calculation engine for switch quantities
- ✅ UI/UX for topology planning
- ✅ Spreadsheet-like planning approach

## Recommendation

**Agent A recommends ACCEPTING Agent C's proposal with the following implementation:**

1. **Use NetBox Core Models:**
   - DeviceType for switches and servers
   - ModuleType for NICs
   - InterfaceTemplate for port specifications

2. **Keep Custom Models:**
   - BreakoutOption (NetBox doesn't model breakout math)
   - DeviceTypeExtension (optional, for Hedgehog-specific metadata)

3. **Seed Data Strategy:**
   - Provide migration that creates common Hedgehog DeviceTypes
   - Include Celestica DS5000, DS3000, NVIDIA SN5600, etc.
   - Include common NICs (ConnectX-7, ConnectX-6)

4. **Migration Path:**
   - Revert migration 0008 (it creates wrong tables)
   - Create new migration with:
     - BreakoutOption table
     - DeviceTypeExtension table
     - Seed DeviceTypes for Hedgehog switches
     - Seed ModuleTypes for common NICs

## Next Steps (Pending User Confirmation)

1. **User Decision Required:**
   - Confirm acceptance of Agent C's recommendation
   - Approve using NetBox core models vs custom models

2. **If Approved:**
   - Delete migration 0008
   - Refactor reference_data.py to use NetBox core models
   - Create DeviceTypeExtension model
   - Update planning models to use DeviceType/ModuleType FKs
   - Create seed data migration for common Hedgehog devices
   - Update tests to work with NetBox models
   - Update documentation

3. **If Not Approved:**
   - Continue with original custom model approach
   - Fix migration 0008 compatibility issues
   - Proceed with issue #85 as originally planned

## Questions for User

1. **Do you approve using NetBox's DeviceType instead of custom SwitchModel/NICModel?**
2. **Should we provide seed data for common Hedgehog devices?**
3. **Any Hedgehog-specific fields that DeviceType doesn't cover?**

---

**Status:** Awaiting user decision before proceeding with implementation.
