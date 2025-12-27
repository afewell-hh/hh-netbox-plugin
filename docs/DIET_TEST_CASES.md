DIET Test Cases
================

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
- Leaf switches: 12
  - fe-gpu-leaf: 2 (MCLAG pair, calculated)
  - fe-storage-leaf-a: 1 (calculated)
  - fe-storage-leaf-b: 1 (calculated)
  - be-rail-leaf: 8 (rail-aware calculation: 1 per rail × 8 rails)
- Spine switches: 6
  - fe-spine: 2 (calculated: 4 frontend leaves × 32 uplinks = 128 / 64 ports per spine = 2)
  - be-spine: 4 (calculated: 8 backend leaves × 32 uplinks = 256 / 64 ports per spine = 4)
- Total switches: 18 (12 leaves + 6 spines)
- Total devices: 164 (146 servers + 18 switches)
- Port demand (connections): 548
- Interfaces: 1,096 (2 per connection)
- Cables: 548

Execution Notes
---------------
- Plan created via NetBox plugin objects (server/switch classes, connections, zones).
- Generate Devices preview shows:
  - Devices: 164 (146 servers + 18 switches)
  - Servers: 146
  - Switches: 18 (12 leaves + 6 spines)
  - Interfaces: 1,096
  - Cables: 548
- Generation completed with:
  - Devices: 164
  - Interfaces: 1,096
  - Cables: 548

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
