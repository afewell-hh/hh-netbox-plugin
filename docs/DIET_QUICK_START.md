# DIET Quick Start Guide

**DIET (Design and Implementation Excellence Tools)** - Topology Planning for Pre-Sales

This guide covers the MVP features for designing Hedgehog network topologies, calculating switch requirements, and exporting wiring diagrams.

---

## Overview

The DIET module helps you:
1. Define server and switch configurations
2. Auto-calculate required switch quantities based on port demand
3. Export Hedgehog wiring diagram YAML for deployment

**Key Concepts:**
- **Reference Data**: Reusable device specifications (DeviceTypes, BreakoutOptions)
- **Topology Plan**: A design project containing server/switch classes
- **Server Class**: A group of identical servers (e.g., "32x GPU Training Servers")
- **Switch Class**: A group of identical switches with auto-calculated quantities
- **Connections**: How servers connect to switches (ports, speed, distribution)

---

## Prerequisites

- NetBox 4.0+ with Hedgehog plugin installed
- User account with appropriate permissions:
  - `netbox_hedgehog.view_*` - View DIET objects
  - `netbox_hedgehog.add_*` - Create DIET objects
  - `netbox_hedgehog.change_*` - Edit objects, recalculate, export YAML
  - `netbox_hedgehog.delete_*` - Delete DIET objects

---

## Step 1: Set Up Device Types (NetBox Core)

Before using DIET, you need switch and server **DeviceTypes** in NetBox.

### Adding a DeviceType

1. Navigate to **Organization → Device Types**
2. Click **Add** button
3. Fill in the form:
   - **Manufacturer**: Select or create (e.g., "Celestica", "Dell")
   - **Model**: Device model name (e.g., "DS5000")
   - **Slug**: Auto-generated from model
   - **Part Number**: Optional manufacturer part number
   - **U Height**: Rack units (typically 1U or 2U)
   - **Is Full Depth**: Check if device is full-depth

4. Click **Create**

**Example: Celestica DS5000 Switch**
```
Manufacturer: Celestica
Model: DS5000
Slug: ds5000
U Height: 1
Is Full Depth: Yes
```

### Adding Interface Templates

After creating a DeviceType, add its port specifications:

1. Go to the DeviceType detail page
2. Scroll to **Interfaces** section
3. Click **Add Interface Template**
4. Fill in template details:
   - **Name**: Port naming pattern (e.g., "Ethernet{module}/{port}")
   - **Type**: Port type (e.g., "800GBASE-X QSFP-DD")
   - **Management Only**: Leave unchecked for data ports

**Example: DS5000 Ports**
```
Name: Ethernet1/{port}
Type: 800GBASE-X QSFP-DD
[Bulk create 64 ports using pattern]
```

---

## Step 2: Add Breakout Options

**BreakoutOptions** define how physical ports can be split into logical ports.

### Navigate to Breakout Options

1. In NetBox, click **Hedgehog** in the navigation menu
2. Under **Topology Planning (DIET)**, click **Breakout Options**

### Create a Breakout Option

1. Click **Add Breakout Option** button (green plus icon)
2. Fill in the form:
   - **Breakout ID**: Unique identifier (e.g., "2x400g", "4x200g")
   - **From Speed**: Native port speed in Gbps (e.g., 800)
   - **Logical Ports**: Number of ports after breakout (e.g., 2)
   - **Logical Speed**: Speed per logical port in Gbps (e.g., 400)
   - **Optic Type**: Optional (e.g., "QSFP-DD")

3. Click **Create**

**Example: 800G → 2x400G Breakout**
```
Breakout ID: 2x400g
From Speed: 800
Logical Ports: 2
Logical Speed: 400
Optic Type: QSFP-DD
```

**Common Breakout Options to Create:**
- 1x800g (no breakout): from_speed=800, logical_ports=1, logical_speed=800
- 2x400g: from_speed=800, logical_ports=2, logical_speed=400
- 4x200g: from_speed=800, logical_ports=4, logical_speed=200
- 8x100g: from_speed=800, logical_ports=8, logical_speed=100
- 4x25g: from_speed=100, logical_ports=4, logical_speed=25

---

## Step 3: Add Device Type Extensions

**DeviceTypeExtensions** add Hedgehog-specific metadata to your DeviceTypes.

### Navigate to Device Type Extensions

1. In Hedgehog menu, click **Device Type Extensions**

### Create an Extension

1. Click **Add Device Type Extension** button
2. Fill in the form:
   - **Device Type**: Select the DeviceType to extend
   - **Hedgehog Roles**: Comma-separated roles (e.g., "spine,server-leaf")
   - **Port Count**: Total physical ports (e.g., 64)
   - **Native Speed**: Port speed in Gbps (e.g., 800)
   - **Supported Breakouts**: Comma-separated breakout IDs (e.g., "1x800g,2x400g,4x200g")
   - **Default Uplink Ports**: Default uplink count (e.g., 4)
   - **MCLAG Capable**: Check if switch supports MCLAG

3. Click **Create**

**Example: DS5000 Extension**
```
Device Type: Celestica DS5000
Hedgehog Roles: spine,server-leaf
Port Count: 64
Native Speed: 800
Supported Breakouts: 1x800g,2x400g,4x200g,8x100g
Default Uplink Ports: 4
MCLAG Capable: No
```

---

## Step 4: Create a Topology Plan

Now you can design a network topology.

### Create the Plan

1. In Hedgehog menu, click **Topology Plans**
2. Click **Add Topology Plan** button
3. Fill in the form:
   - **Name**: Plan name (e.g., "Customer ABC - 128 GPU Cluster")
   - **Customer Name**: Optional customer name
   - **Status**: Select status (Draft, Review, Approved, Deployed)
   - **Description**: Optional description

4. Click **Create**

You'll be redirected to the plan detail page.

---

## Step 5: Add Server Classes

**Server Classes** define groups of identical servers.

### Navigate from Plan Detail

On your plan's detail page, you'll see sections for:
- Server Classes
- Switch Classes
- Server Connections

### Add a Server Class

1. In the **Server Classes** section, click **Add Server Class**
   (or use navigation: Hedgehog → Server Classes → Add)

2. Fill in the form:
   - **Plan**: Select your plan (pre-filled if coming from plan detail)
   - **Server Class ID**: Unique identifier (e.g., "gpu-training")
   - **Description**: Human-readable name (e.g., "GPU Training Servers")
   - **Category**: Select category (GPU, Storage, Infrastructure, Other)
   - **Device Type**: Select server DeviceType from NetBox
   - **Quantity**: Number of servers (e.g., 32) **← PRIMARY INPUT**
   - **GPUs per Server**: Optional GPU count (e.g., 8)
   - **Notes**: Optional notes

3. Click **Create**

**Example: GPU Training Servers**
```
Plan: Customer ABC - 128 GPU Cluster
Server Class ID: gpu-training
Description: GPU Training Servers with 8x H100
Category: GPU
Device Type: [Select your server type]
Quantity: 32
GPUs per Server: 8
```

---

## Step 6: Add Switch Classes

**Switch Classes** define switch types. Quantities are **auto-calculated** based on server port demand.

### Add a Switch Class

1. In the plan detail page, click **Add Switch Class**
   (or use navigation: Hedgehog → Switch Classes → Add)

2. Fill in the form:
   - **Plan**: Select your plan
   - **Switch Class ID**: Unique identifier (e.g., "frontend-leaf")
   - **Description**: Human-readable name (e.g., "Frontend Leaf Switches")
   - **Fabric**: Select fabric type (Frontend, Backend, Management)
   - **Hedgehog Role**: Select role (server-leaf, spine, border-leaf, virtual-edge)
   - **Device Type Extension**: Select the switch extension
   - **Uplink Ports per Switch**: Uplink port count (e.g., 4)
   - **MCLAG Pair**: Check if switches are deployed in pairs
   - **Override Quantity**: Optional manual override (leave blank for auto-calc)
   - **Notes**: Optional notes

3. Click **Create**

**Example: Frontend Leaf Switches**
```
Plan: Customer ABC - 128 GPU Cluster
Switch Class ID: frontend-leaf
Description: Frontend Leaf Switches
Fabric: Frontend
Hedgehog Role: server-leaf
Device Type Extension: Celestica DS5000
Uplink Ports per Switch: 4
MCLAG Pair: No
Override Quantity: [leave blank]
```

**Note:** The **calculated_quantity** and **effective_quantity** will be populated when you run the recalculate action.

---

## Step 7: Add Server Connections

**Connections** define how servers connect to switches.

### Add a Connection

1. From plan detail, click **Add Connection** in the Server Connections section
   (or use navigation: Hedgehog → Topology Plans → [Your Plan] → Connections tab)

2. Fill in the form:
   - **Server Class**: Select the server class
   - **Connection ID**: Unique identifier (e.g., "gpu-frontend")
   - **Connection Name**: Human-readable name (e.g., "Frontend Data")
   - **Ports per Connection**: Number of ports (e.g., 2)
   - **Speed**: Port speed in Gbps (e.g., 200)
   - **Hedgehog Connection Type**: Select type (unbundled, bundled, mclag, eslag)
   - **Distribution**: How ports spread across switches:
     - **same-switch**: All ports to same switch
     - **alternating**: Ports alternate between switches
     - **rail-optimized**: Specific rail assignment (requires Rail field)
   - **Target Switch Class**: Select destination switch class
   - **Rail**: Required only for rail-optimized distribution (e.g., 1-8 for GPU rails)
   - **Port Type**: data, ipmi, or pxe
   - **Notes**: Optional notes

3. Click **Create**

**Example: GPU Server Frontend Connection**
```
Server Class: gpu-training
Connection ID: gpu-frontend
Connection Name: Frontend Data Ports
Ports per Connection: 2
Speed: 200
Hedgehog Connection Type: unbundled
Distribution: alternating
Target Switch Class: frontend-leaf
Port Type: data
```

**Validation Rules:**
- **Rail field** is required when distribution is "rail-optimized"
- **Rail field** must be empty for other distribution types
- Target switch class must belong to the same plan

---

## Step 8: Recalculate Switch Quantities

After adding server classes, switch classes, and connections, trigger the calculation engine.

### Run Recalculate

1. Go to your **Topology Plan detail page**
2. Click the **Recalculate** button

   **Required Permission:** `netbox_hedgehog.change_topologyplan`

3. You'll see a success message: "Recalculated N switch classes for plan '[Plan Name]'."

4. Check the **Switch Classes** section - each switch class now shows:
   - **Calculated Quantity**: Auto-calculated based on port demand
   - **Override Quantity**: Your manual override (if set)
   - **Effective Quantity**: Calculated OR Override (whichever applies)

**What the calculation does:**
- Sums total ports needed across all server connections targeting each switch class
- Accounts for port breakout (4x200G from 800G native ports)
- Subtracts uplink ports from available capacity
- Ensures MCLAG pairs are even-numbered
- Saves results to `calculated_quantity` field

---

## Step 9: Export YAML Wiring Diagram

Once your plan is complete, export it as Hedgehog wiring YAML.

### Export the Plan

1. Go to your **Topology Plan detail page**
2. Click the **Export YAML** button

   **Required Permission:** `netbox_hedgehog.change_topologyplan`

   **Note:** Export automatically runs recalculation first to ensure quantities are current.

3. A file downloads with the name `[plan-name].yaml`

4. Open the file to see generated Connection CRDs

**Example YAML Output:**
```yaml
# Generated by Hedgehog NetBox Plugin - Topology Planner
# Plan: customer-abc-128-gpu-cluster
# Generated: 2024-12-21T10:30:00Z

apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: server--gpu-training-001--unbundled--frontend-leaf-01--frontend-data
  namespace: default
spec:
  unbundled:
    link:
      server:
        port: gpu-training-001/enp1s0f0
      switch:
        port: frontend-leaf-01/Ethernet1/1/1
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: server--gpu-training-001--unbundled--frontend-leaf-02--frontend-data
  namespace: default
spec:
  unbundled:
    link:
      server:
        port: gpu-training-001/enp1s0f1
      switch:
        port: frontend-leaf-02/Ethernet1/1/1
---
# ... (hundreds more connections)
```

**What's included in the YAML:**
- Server-to-switch Connection CRDs for all servers
- Proper port naming based on breakout configuration
- Switch port allocation (no duplicate ports)
- Metadata with plan name and generation timestamp

**Not included in MVP:**
- MCLAG domain connections (post-MVP)
- Fabric (spine-leaf) connections (post-MVP)
- Switch or Server CRDs (only Connection CRDs)

---

## Common Workflows

### Update Server Quantity

1. Go to **Server Classes** list or plan detail
2. Click the server class name
3. Click **Edit**
4. Change the **Quantity** field
5. Click **Update**
6. Go back to plan detail and click **Recalculate** to update switch quantities

### Override Calculated Switch Quantity

If you need more (or fewer) switches than calculated:

1. Go to **Switch Classes** list or plan detail
2. Click the switch class name
3. Click **Edit**
4. Enter a value in **Override Quantity** field
5. Click **Update**
6. The **Effective Quantity** will now use your override instead of the calculation

### Delete a Plan

1. Go to plan detail page
2. Click **Delete** button
3. Confirm deletion

**Note:** Deleting a plan also deletes all associated server classes, switch classes, and connections.

---

## Permissions Summary

| Action | Required Permission |
|--------|---------------------|
| View plans, classes, reference data | `netbox_hedgehog.view_topologyplan` (and related) |
| Create/edit plans, classes | `netbox_hedgehog.add_*`, `netbox_hedgehog.change_*` |
| Recalculate switch quantities | `netbox_hedgehog.change_topologyplan` |
| Export YAML | `netbox_hedgehog.change_topologyplan` |
| Delete plans, classes | `netbox_hedgehog.delete_*` |

Superusers have all permissions by default.

---

## Navigation Quick Reference

**Hedgehog Menu → Topology Planning (DIET):**
- **Topology Plans** - Main planning interface
- **Server Classes** - Server configuration groups
- **Switch Classes** - Switch configuration with auto-calc
- **Breakout Options** - Port breakout definitions
- **Device Type Extensions** - Hedgehog metadata for switches

**NetBox Core (outside plugin):**
- **Organization → Manufacturers** - Device vendors
- **Organization → Device Types** - Switch/server models
- **Device Types → [Select] → Interface Templates** - Port specifications

---

## Troubleshooting

### "No switches calculated" after recalculate

**Cause:** No server connections target the switch class, or all servers have quantity=0.

**Fix:**
1. Verify server class quantity > 0
2. Add connections that target the switch class
3. Run recalculate again

### "Permission denied" on Recalculate or Export

**Cause:** User lacks `change_topologyplan` permission.

**Fix:** Contact NetBox administrator to grant `netbox_hedgehog.change_topologyplan` permission.

### Export YAML is empty or has few connections

**Cause:**
- Server classes have quantity=0
- No connections defined
- No effective switch quantity (calculated=0 and no override)

**Fix:**
1. Check server class quantities
2. Add connections between server and switch classes
3. Run recalculate to ensure switch effective_quantity > 0

### "Rail is required for rail-optimized distribution"

**Cause:** Creating a connection with distribution="rail-optimized" but rail field is empty.

**Fix:** Enter a rail number (e.g., 1-8) in the Rail field.

### Cannot add DeviceTypeExtension - "Device type already has an extension"

**Cause:** Each DeviceType can only have one extension.

**Fix:** Edit the existing extension instead of creating a new one.

---

## What's Not in MVP

The following features are planned but not yet available:

- **Templates**: Pre-configured topology plan templates
- **MCLAG Domain Connections**: Automatic generation of peer-link and session CRDs
- **Fabric Connections**: Spine-to-leaf uplink generation
- **Switch/Server CRDs**: Only Connection CRDs are generated
- **Bulk Import/Export**: CSV import of server/switch classes
- **Visualization**: Topology diagram preview

These will be added in future releases after MVP.

---

## Container Commands Reference

If you need to work with the plugin code or database directly:

```bash
# All commands run from /home/ubuntu/afewell-hh/netbox-docker/

# Access Django shell
docker compose exec netbox python manage.py shell_plus

# Run tests
docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning

# Create migrations (developers only)
docker compose exec netbox python manage.py makemigrations netbox_hedgehog

# Apply migrations (developers only)
docker compose exec netbox python manage.py migrate netbox_hedgehog

# View logs
docker compose logs -f netbox
```

---

## Next Steps

After completing this guide, you should be able to:
- ✅ Create and manage Device Types in NetBox
- ✅ Define breakout options and device type extensions
- ✅ Build topology plans with server and switch classes
- ✅ Auto-calculate switch requirements based on port demand
- ✅ Export Hedgehog wiring YAML for deployment

For more details on the operational features (managing live Hedgehog fabrics), see:
- [Quick Start Guide](QUICK_START.md) - Fabric management and CRD sync
- [User Guide](USER_GUIDE.md) - Complete operational workflows

For API access to DIET features, see:
- [API Reference](API_REFERENCE.md) - REST API endpoints

---

**Document Version:** MVP (December 2024)
**Plugin Version:** v1.0-DIET-MVP
**NetBox Version:** 4.0+
