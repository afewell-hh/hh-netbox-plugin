# RA Pilot Translation Worksheet

This worksheet captures the first-pass DIET inputs for the 4 pilot variants
selected in the master manifest. It is intentionally conservative: it records
only what is supported by the current RA source files and highlights any gaps
that block topology-plan YAML authoring.

## Pilot 1: `inference-opg32-minimal-fe-converged`

Source files:

- `/home/ubuntu/afewell-hh/inference-ra/compositions/OPG-32/README.md`
- `/home/ubuntu/afewell-hh/inference-ra/compositions/OPG-32/minimal-fe-converged/README.md`

Confirmed inputs:

- Tier: OPG-32 inference
- Backend fabric: none
- Managed fabric intent: FE + storage converged
- Frontend/storage NIC: BF3 2x200G per server
- FE connection pattern: L3MH across two leaves
- In-band: present
- OoB: present, unmanaged by Hedgehog
- Gateway: distributed x86 connected to border leaves
- QoS note: RDMA class disabled; FE/control prioritized

Current blockers:

- Server count is not explicitly stated in the variant README set
- Storage node count is not explicitly stated
- Gateway count is not explicitly stated
- Border-leaf count is not explicitly stated
- No non-placeholder connectivity map, BOM, or wiring artifact exists yet

Working DIET translation assumption:

- Treat this as a single managed `converged` fabric plus unmanaged OoB.
- Do not author the topology-plan YAML until the endpoint counts are confirmed
  from a more detailed RA source or user guidance.

## Pilot 2: `training-opg128-clos-ro-air-2srv`

Source files:

- `/home/ubuntu/afewell-hh/training-ra/compositions/OPG-128/README.md`
- `/home/ubuntu/afewell-hh/training-ra/compositions/OPG-128/clos-ro--cx7-1x400g--bf3-2x200g--storage-conv-2x200g--cooling-air--dens-2srv/README.md`

Confirmed inputs:

- Tier: OPG-128 training
- Composition size: 128 xPUs
- Compute count: 16 servers x 8 xPUs
- Backend fabric: single-plane rail-optimized Clos
- Backend NIC model intent: CX7 1x400G per GPU
- Frontend/storage NIC model intent: BF3 2x200G per server
- Frontend connection pattern: L3MH
- Storage model: converged into frontend network
- Cooling density: air, approximately 2 servers per rack
- Port-zoning guidance: DS5000 odd-port 4x200G breakout, 2x400G unrestricted,
  32x800G uplinks reserved

Likely DIET shape:

- One compute server class: 16 instances, 8 GPUs each
- One installed FE DPU/NIC entry per server with 2 x 200G ports to a converged FE fabric
- Eight installed backend NICs per server or equivalent server-NIC representation:
  one 400G rail per GPU
- Managed fabrics likely:
  - `frontend` or `converged`
  - `backend`

Current blockers:

- Storage server count is not specified
- Metadata/controller/gateway counts are not specified in the OPG-128 docs
- Exact fabric names are not specified
- No non-placeholder connectivity map or wiring artifact exists yet

Working DIET translation assumption:

- Use `backend` and `frontend` as provisional managed fabric names.
- Model only the compute portion first if non-compute endpoint counts remain unknown.

## Pilot 3: `training-opg256-dual-plane-air-2srv`

Source files:

- `/home/ubuntu/afewell-hh/training-ra/compositions/OPG-256/README.md`
- `/home/ubuntu/afewell-hh/training-ra/compositions/OPG-256/dual-plane--cx8-2x400g--bf3-2x200g--2p--storage-conv-2x200g--cooling-air--dens-2srv/README.md`

Confirmed inputs:

- Tier: OPG-256 training
- Composition size: 256 xPUs
- Compute count: 32 servers x 8 xPUs
- Backend fabric: dual plane
- Plane count: 2 independent backend fabrics, Plane A and Plane B
- Backend NIC model intent: CX8 2x400G per GPU
- Per-GPU connectivity intent: one CX8 port to Plane A and one CX8 port to Plane B
- Frontend/storage fabric: converged
- Frontend/storage NIC model intent: BF3 2x200G per server
- Frontend connection pattern: L3MH across two FE leaves
- Cooling density: air, approximately 2 servers per rack
- DS5000 is the referenced switch family

Likely DIET shape:

- One compute server class: 32 instances, 8 GPUs each
- One FE DPU/NIC per server: BF3 2 x 200G
- Eight installed backend NICs per server or equivalent GPU-linked NIC objects:
  each GPU served by a CX8 dual-port 400G adapter with one link per plane
- Managed fabrics likely:
  - `backend-plane-a`
  - `backend-plane-b`
  - `frontend`

Current blockers:

- Storage, metadata, controller, and gateway counts are not specified in this variant README
- Exact DIET representation of "CX8 2x400G per GPU" needs to be matched against
  the current PlanServerNIC/PlanServerConnection model carefully
- No non-placeholder connectivity map or wiring artifact exists yet

Working DIET translation assumption:

- Use `backend-plane-a`, `backend-plane-b`, and `frontend` as provisional fabric names.
- Start with compute-only topology-plan modeling if non-compute endpoint counts are still absent.

## Pilot 4: `training-xoc512-1xopg512-dual-plane-air-2srv`

Source files:

- `/home/ubuntu/afewell-hh/training-ra/compositions/XOC-512/README.md`
- `/home/ubuntu/afewell-hh/training-ra/compositions/XOC-512/1x-OPG-512/README.md`
- `/home/ubuntu/afewell-hh/training-ra/compositions/XOC-512/1x-OPG-512/dual-plane--cx8-2x400g--bf3-2x200g--2p--storage-conv-2x200g--cooling-air--dens-2srv/README.md`
- `/home/ubuntu/afewell-hh/training-ra/compositions/OPG-512/README.md`

Confirmed inputs:

- Tier: XOC-512
- Bundle: 1x-OPG-512 under a DS5000 spine
- Variant mirrors the underlying OPG-512 dual-plane pattern
- Backend fabric: dual plane
- Backend NIC model intent: CX8 2x400G per GPU
- Frontend/storage NIC model intent: BF3 2x200G with L3MH
- Cooling density: air, approximately 2 servers per rack

Current blockers:

- XOC composition semantics are underspecified
- It is not yet clear whether this should be modeled as:
  - one topology plan with additional XOC spine/domain constructs, or
  - an OPG-512-equivalent plan plus extra inter-OPG/XOC metadata
- No explicit endpoint counts appear in the XOC-512 pilot README set
- No non-placeholder connectivity map or wiring artifact exists yet

Working DIET translation assumption:

- Do not author this topology-plan YAML until the base OPG-512 dual-plane
  translation rules are established from more detailed OPG-512 source files.
- Treat this as dependent on the OPG-512 dual-plane archetype plus an XOC
  composition layer that still needs clarification.

## Cross-Pilot Findings

What is usable now:

- Topology class
- Compute scale for OPG-128 and OPG-256
- FE/backend/high-level converged vs dual-plane semantics
- Reference NIC/DPU intent
- Some rack density metadata

What is still missing in the RA repos:

- Populated connectivity maps
- Populated BOMs
- Populated wiring artifacts
- Explicit non-compute endpoint counts in several pilot variants
- Final managed-fabric naming conventions

## Recommended Immediate Actions

1. Use the pilot worksheet to ask for or locate missing endpoint counts.
2. Start actual topology-plan YAML authoring with Pilot 2 and Pilot 3 first,
   because they have explicit compute counts and clearer fabric semantics.
3. Defer Pilot 1 and Pilot 4 YAML authoring until the missing quantitative
   inputs are confirmed.
4. Consider adding a small RA authoring rule: every composition README should
   state compute count, storage count, infra/controller count, gateway count,
   and intended managed-fabric names explicitly.
