DIET Test Cases
================

Note
----
For the current YAML authoring format used by `apply_diet_test_case`, see
`docs/DIET_TOPOLOGY_PLAN_YAML_REFERENCE.md`.

This file describes specific scenarios, not the full ingest schema.

Case: 128 GPU Servers + Storage Split + Odd-Port Breakouts
----------------------------------------------------------

Goal
Verify DIET can model and generate a realistic topology with:
- 128 GPU servers (FE redundant, BE rails)
- 18 storage appliances split across two dedicated FE leaf classes
- DS5000-only switch model
- 4x200G breakouts restricted to odd-numbered ports

Scenario Summary
----------------
- GPU servers: 128 total
  - 96 servers: frontend only (2x200G)
  - 32 servers: frontend (2x200G) + backend (8x400G)
- Storage appliances: 18 total
  - Storage A: 9 servers, 2x200G bundled to storage leaf A
  - Storage B: 9 servers, 2x200G bundled to storage leaf B
- Switch model: Celestica DS5000 (64x800G)
- Leaf uplinks: 32x800G per leaf
- Odd-port breakout rule:
  - Downlink breakouts use only odd ports: 1-63:2
  - Even ports reserved for uplinks or other uses

Plan Configuration
------------------
Plan name: "UX Case 128GPU Odd Ports"

Switch classes
- fe-gpu-leaf (Frontend, server-leaf, MCLAG pair, uplinks=32)
- fe-storage-leaf-a (Frontend, server-leaf, uplinks=32)
- fe-storage-leaf-b (Frontend, server-leaf, uplinks=32)
- fe-spine (Frontend, spine, uplinks=0)
- be-rail-leaf (Backend, server-leaf, uplinks=32, rail-aware calculation)
- be-spine (Backend, spine, uplinks=0)

Port zones (server downlinks only)
- fe-gpu-leaf: port_spec=1-63:2, breakout=4x200g, strategy=sequential
- fe-storage-leaf-a: port_spec=1-63:2, breakout=4x200g, strategy=sequential
- fe-storage-leaf-b: port_spec=1-63:2, breakout=4x200g, strategy=sequential
- be-rail-leaf: port_spec=1-63:2, breakout=2x400g, strategy=sequential

Server classes
- gpu-fe-only (96x, GPU, 8 GPUs)
- gpu-with-backend (32x, GPU, 8 GPUs)
- storage-a (9x, Storage)
- storage-b (9x, Storage)

Connections
- gpu-fe-only -> fe-gpu-leaf
  - ports_per_connection=2, speed=200, type=unbundled, distribution=alternating
- gpu-with-backend -> fe-gpu-leaf
  - ports_per_connection=2, speed=200, type=unbundled, distribution=alternating
- gpu-with-backend -> be-rail-leaf
  - 8 connections, ports_per_connection=1, speed=400, type=unbundled,
    distribution=rail-optimized, rail=0..7
- storage-a -> fe-storage-leaf-a
  - ports_per_connection=2, speed=200, type=bundled, distribution=same-switch
- storage-b -> fe-storage-leaf-b
  - ports_per_connection=2, speed=200, type=bundled, distribution=same-switch

Expected Counts
---------------
- Servers: 146 (128 GPU + 18 storage)
- Leaf switches: 8
  - fe-gpu-leaf: 2 (MCLAG pair, calculated)
  - fe-storage-leaf-a: 1 (calculated)
  - fe-storage-leaf-b: 1 (calculated)
  - be-rail-leaf: 4 (calculated)
- Spine switches: 4
  - fe-spine: 2 (calculated: 4 frontend leaves × 32 uplinks = 128 / 64 ports per spine = 2)
  - be-spine: 2 (calculated: 4 backend leaves × 32 uplinks = 128 / 64 ports per spine = 2)
- Total switches: 12 (8 leaves + 4 spines)
- Total devices: 158 (146 servers + 12 switches)
- Port demand (connections): 548
- Interfaces: 1,096 (server + fabric interfaces)
- Cables: 804
  - Server-to-switch: 548
  - Fabric (leaf-to-spine): 256
    - Frontend fabric: 128
    - Backend fabric: 128

Execution Notes
---------------
- Plan created via NetBox plugin objects (server/switch classes, connections, zones).
- Generate Devices preview shows:
  - Devices: 158 (146 servers + 12 switches)
  - Servers: 146
  - Switches: 12 (8 leaves + 4 spines)
  - Interfaces: 1,096
  - Cables: 548 (preview does not include fabric cabling yet)
- Generation completed with:
  - Devices: 158
  - Interfaces: 1,096
  - Cables: 804

Fabric Connection Breakdown
---------------------------

**Frontend Fabric** (128 cables):
- fe-gpu-leaf (2 switches, MCLAG pair): 2 × 32 uplinks = 64 uplinks
- fe-storage-leaf-a (1 switch): 32 uplinks
- fe-storage-leaf-b (1 switch): 32 uplinks
- Total: 128 uplinks distributed across 2 fe-spines

**Backend Fabric** (128 cables):
- be-rail-leaf (4 switches): 4 × 32 uplinks = 128 uplinks
- Total: 128 uplinks distributed across 2 be-spines

Port Allocation Verification
----------------------------
Sample checks after generation:
- fe-gpu-leaf-01 uses odd physical ports only (1..63, step 2)
- be-rail-leaf-01 uses odd physical ports only (1..31, step 2)

Resolved Features
-----------------
- ✅ Rail-aware leaf sizing: be-rail-leaf now calculates to 8 switches automatically
  (1 switch per rail × 8 rails) without needing override_quantity
- ✅ Spine sizing: fe-spine and be-spine quantities are calculated based on
  leaf uplink demand (fe-spine: 2, be-spine: 4)

Case: Shared Physical NIC Cage (synthetic)
------------------------------------------

Goal
Two logical NIC interfaces on two logical channels of one physical cage share one
installed optic. The schema is in the
[YAML reference](DIET_TOPOLOGY_PLAN_YAML_REFERENCE.md#mapped-nic-cage-layouts-hnp_nic_cage_map).
The example uses a fictional two-port 400G NIC type mapped to `cage-0` in mode
`2x400g`, with one fictional optic type. Generation should produce one NIC Module, one
nested `cage-0` ModuleBay and one optic per server. Both logical interfaces stay
separate wiring endpoints, and the public BOM counts one NIC and one server optic per
server. This is synthetic behavior coverage only. It does not qualify any vendor part,
optic, workbook, topology family, hhfab run, GUI rendering or release.

Configuring a mapped NIC type through the native NetBox API
-----------------------------------------------------------
HNP has no layout editor and no layout REST route. The HNP NIC form still just selects
a configured ModuleType. An operator authorized for the target NetBox catalog
configures the type with the native API:

1. Create or choose a ModuleTypeProfile whose `schema` declares `hnp_nic_cage_map`,
   plus any other attributes the type carries:

   ```http
   POST /api/dcim/module-type-profiles/
   Authorization: Token <API_TOKEN from your secret store>
   Content-Type: application/json

   {"name": "<profile name>", "schema": {"type": "object",
     "required": ["hnp_nic_cage_map"],
     "properties": {"hnp_nic_cage_map": {"type": "object"}, "<other_attribute>": {"type": "string"}}}}
   ```

2. Create the NIC ModuleType with that profile and the complete `attributes` object.
   The native API field is `attributes`, which is stored as `attribute_data`:

   ```http
   POST /api/dcim/module-types/
   {"manufacturer": <manufacturer id>, "model": "<NIC model>", "profile": <profile id>,
    "attributes": {"hnp_nic_cage_map": {"version": 1,
        "ports": [{"cage": "cage-0", "logical_lane": 0}, {"cage": "cage-0", "logical_lane": 1}],
        "cages": {"cage-0": {"breakout_id": "2x400g"}}},
      "<other_attribute>": "<value>"}}
   ```

   To change the map later, `PATCH /api/dcim/module-types/<id>/` with the complete
   `attributes` object.
3. Check admission with a read-back: `GET /api/dcim/module-types/<id>/`. The type is
   admitted only if `profile.id` is the intended profile and `attributes` equals exactly
   what was sent. A 2xx status alone does not admit it. Native validation returns 400
   for attributes that violate the profile schema. A request without a profile can
   return 2xx with the attributes cleared, and that lost layout is not admitted. Any
   other HNP-owned rule is enforced later by bay population and generation, with
   specific `[nic_layout_*]` errors.
4. Create the type's InterfaceTemplates, one per `ports` row, in natural name order.
   Then ready the declared cage bays with the scoped `populate_bays` / ingest
   population, which creates only declared cages. Configure the optic type on the
   existing `Network Transceiver` profile, with `breakout_topology` equal to the cage
   mode.
5. Reference the configured type from a plan: through the NIC form, through a V1 case
   (`attribute_data` absent, or the exact whole payload) or through a V2 `module_type`
   reference.

Use placeholders and secret-store references only. Never put token values in case
files, docs or issues. `logical_lane` values are logical channels of the BreakoutOption,
not 8 SerDes lanes. These steps create no seeds, aliases or profiles and need no DDL or
HNP editor. Applying them to a real catalog is a separate, explicitly authorized
operation.
