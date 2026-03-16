# DIET Topology Plan YAML Reference

This is the current agent-focused reference for YAML-defined DIET topology plans
loaded by `apply_diet_test_case`.

Use this when another agent needs to create a valid topology plan YAML without
reverse-engineering the loader or copying a large case file.

## What this file is

- It documents the input format consumed by:
  - `netbox_hedgehog/test_cases/loader.py`
  - `netbox_hedgehog/test_cases/schema.py`
  - `netbox_hedgehog/test_cases/ingest.py`
- It is not the exported Hedgehog wiring YAML.
- It is the authoring format for creating a DIET plan inside NetBox.

## Fast rules

- Required top-level sections:
  - `meta`
  - `plan`
  - `switch_classes`
  - `server_classes`
  - `server_connections`
- Usually also needed in real cases:
  - `reference_data`
  - `switch_port_zones`
  - `server_nics`
- `meta.managed_by` must be exactly `yaml`.
- `meta.case_id` must match `^[a-z0-9_]+$`.
- `plan.status` must be one of: `draft`, `review`, `approved`, `exported`.
- Do not use deprecated keys:
  - `server_connections[].target_switch_class`
  - `server_connections[].nic_module_type`
- Use:
  - `server_connections[].target_zone: "<switch_class_id>/<zone_name>"`
  - `server_connections[].nic: "<nic_id>"`

## Minimal valid example

```yaml
meta:
  case_id: agent_minimal_example
  name: Agent Minimal Example
  description: Small valid DIET topology plan
  version: 1
  managed_by: yaml
  tags: [agent, example]

reference_data:
  manufacturers:
    - id: generic
      name: Generic
      slug: generic
    - id: nvidia
      name: NVIDIA
      slug: nvidia

  device_types:
    - id: server_dt
      manufacturer: generic
      model: Example Server
      slug: example-server
      interface_templates:
        - name: eth1
          type: 200gbase-x-qsfp56
    - id: switch_dt
      manufacturer: generic
      model: Example Switch
      slug: example-switch
      interface_templates:
        - name: E1/1
          type: 800gbase-x-qsfpdd
        - name: E1/2
          type: 800gbase-x-qsfpdd
        - name: E1/3
          type: 800gbase-x-qsfpdd
        - name: E1/4
          type: 800gbase-x-qsfpdd

  device_type_extensions:
    - id: switch_ext
      device_type: switch_dt
      mclag_capable: false
      hedgehog_roles: [server-leaf]
      supported_breakouts: [1x800g, 4x200g]
      native_speed: 800
      uplink_ports: 0

  breakout_options:
    - id: bo_4x200
      breakout_id: 4x200g
      from_speed: 800
      logical_ports: 4
      logical_speed: 200
      optic_type: QSFP-DD

  module_types:
    - id: nic_single
      manufacturer: nvidia
      model: Example NIC 1x200G
      interface_templates:
        - name: p0
          type: other

plan:
  name: Agent Minimal Example
  status: draft
  description: One switch class, one server class, one connection

switch_classes:
  - switch_class_id: fe-leaf
    fabric_name: frontend
    fabric_class: managed
    hedgehog_role: server-leaf
    device_type_extension: switch_ext
    uplink_ports_per_switch: 0

switch_port_zones:
  - switch_class: fe-leaf
    zone_name: server-ports
    zone_type: server
    port_spec: 1-4
    breakout_option: bo_4x200
    allocation_strategy: sequential
    priority: 100

server_classes:
  - server_class_id: gpu-small
    description: Small GPU server class
    category: gpu
    quantity: 2
    gpus_per_server: 8
    server_device_type: server_dt

server_nics:
  - server_class: gpu-small
    nic_id: nic-fe
    module_type: nic_single
    description: Frontend NIC

server_connections:
  - server_class: gpu-small
    connection_id: fe
    connection_name: frontend
    nic: nic-fe
    port_index: 0
    ports_per_connection: 1
    hedgehog_conn_type: unbundled
    distribution: same-switch
    target_zone: fe-leaf/server-ports
    speed: 200
    port_type: data
```

## Section reference

### `meta`

Required:

- `case_id`
- `name`
- `version`
- `managed_by`

Optional:

- `description`
- `tags`

Rules:

- `case_id` must be lowercase snake case.
- `managed_by` must be `yaml`.

### `reference_data`

This section is how the loader resolves or creates NetBox reference objects.

Subsections:

- `manufacturers`
- `device_types`
- `device_type_extensions`
- `breakout_options`
- `module_types`

Reference rule:

- IDs inside `reference_data` are case-local symbolic IDs.
- Other sections reference these IDs, not database PKs.

#### `manufacturers[]`

Required:

- `id`
- `name`

Optional:

- `slug`

#### `device_types[]`

Required:

- `id`
- `manufacturer`
- `model`

Optional:

- `slug`
- `u_height`
- `is_full_depth`
- `interface_templates`

Notes:

- `manufacturer` points to `reference_data.manufacturers[].id`.
- `interface_templates[]` should usually be present for realistic plans.

#### `device_type_extensions[]`

Required:

- `id`
- `device_type`

Optional:

- `mclag_capable`
- `hedgehog_roles`
- `supported_breakouts`
- `native_speed`
- `uplink_ports`
- `hedgehog_profile_name`
- `notes`

Notes:

- `device_type` points to `reference_data.device_types[].id`.
- Switch classes reference this object, not raw `device_type`.

#### `breakout_options[]`

Required:

- `id`
- `breakout_id`

Optional but normally needed:

- `from_speed`
- `logical_ports`
- `logical_speed`
- `optic_type`

#### `module_types[]`

Required:

- `id`
- `manufacturer`
- `model`

Optional:

- `attribute_data`
- `interface_templates`

Critical rule:

- `interface_templates[]` must exist if the module type will be used by
  `server_nics`, otherwise connection validation fails.

### `plan`

Required:

- `name`
- `status`

Optional:

- `description`

Valid `status` values:

- `draft`
- `review`
- `approved`
- `exported`

### `switch_classes[]`

Required:

- `switch_class_id`
- `fabric_name`
- `device_type_extension`

Optional:

- `fabric_class`
- `hedgehog_role`
- `uplink_ports_per_switch`
- `mclag_pair`
- `override_quantity`
- `redundancy_type`
- `redundancy_group`
- `topology_mode`
- `groups`
- `fabric`

Valid values:

- `fabric_class`: `managed`, `unmanaged`
- `hedgehog_role`: `spine`, `server-leaf`, `border-leaf`, `virtual`
- `redundancy_type`: `mclag`, `eslag`
- `topology_mode`: `spine-leaf`, `prefer-mesh`

Rules:

- `fabric_name` must be non-blank.
- If both `fabric` and `fabric_name` are present, they must match.
- `device_type_extension` points to `reference_data.device_type_extensions[].id`.
- If `redundancy_type` is set, `redundancy_group` is required.
- If `mclag_pair: true` and `redundancy_type` is omitted, the model auto-fills
  `redundancy_type: mclag` and a generated `redundancy_group`.
- If `override_quantity` is present:
  - `mclag` requires an even quantity and at least `2`
  - `eslag` requires `2-4`
- `prefer-mesh` cannot coexist with a spine class in the same fabric.
- All non-spine switch classes in the same fabric must share the same
  `topology_mode`.

### `switch_port_zones[]`

Not required by the shallow schema, but normally required because
`server_connections` target zones, not switch classes.

Required:

- `switch_class`
- `zone_name`
- `zone_type`
- `port_spec`

Optional:

- `breakout_option`
- `allocation_strategy`
- `allocation_order`
- `priority`
- `peer_zone`

Valid values:

- `zone_type`: `server`, `uplink`, `mclag`, `peer`, `session`, `oob`, `fabric`, `mesh`
- `allocation_strategy`: `sequential`, `interleaved`, `spaced`, `custom`

Rules:

- `switch_class` points to `switch_classes[].switch_class_id`.
- `breakout_option` points to `reference_data.breakout_options[].id`.
- `peer_zone`, if used, must be `"<switch_class_id>/<zone_name>"`.
- `port_spec` uses the DIET port-spec grammar, for example:
  - `1-32`
  - `1-63:2`
  - `1,3,5,7`
- If `allocation_strategy: custom`, then `allocation_order` is required and
  must exactly match the parsed port list.

### `server_classes[]`

Required:

- `server_class_id`
- `quantity`
- `server_device_type`

Optional:

- `description`
- `category`
- `gpus_per_server`

Valid `category` values:

- `gpu`
- `storage`
- `infrastructure`

Rules:

- `quantity` must be at least `1`.
- `server_device_type` points to `reference_data.device_types[].id`.

### `server_nics[]`

Current ingest requires NIC-first modeling for modern cases.

Required:

- `server_class`
- `nic_id`
- `module_type`

Optional:

- `description`

Rules:

- `server_class` points to `server_classes[].server_class_id`.
- `module_type` points to `reference_data.module_types[].id`.
- `nic_id` must start with an alphanumeric character and then use only:
  - letters
  - digits
  - `_`
  - `-`

### `server_connections[]`

Required:

- `server_class`
- `connection_id`
- `nic`
- `ports_per_connection`
- `target_zone`
- `speed`

Optional:

- `connection_name`
- `port_index`
- `hedgehog_conn_type`
- `distribution`
- `rail`
- `port_type`
- `cage_type`
- `medium`
- `connector`
- `standard`

Valid values:

- `hedgehog_conn_type`: `unbundled`, `bundled`, `mclag`, `eslag`
- `distribution`: `same-switch`, `alternating`, `rail-optimized`
- `port_type`: `data`, `ipmi`, `pxe`
- `cage_type`: `QSFP112`, `OSFP`, `QSFP-DD`, `QSFP28`, `SFP28`, `SFP+`, `RJ45`
- `medium`: `MMF`, `SMF`, `DAC`, `ACC`
- `connector`: `LC`, `MPO-12`, `MPO-16`, `Direct`

Rules:

- `server_class` points to `server_classes[].server_class_id`.
- `nic` points to `server_nics[].nic_id` within the same server class.
- `target_zone` must be `"<switch_class_id>/<zone_name>"`.
- `connection_id` may only use alphanumeric characters, `_`, and `-`.
- `port_index` is zero-based.
- `port_index + ports_per_connection` must fit within the NIC module type's
  interface template count.
- IPMI connections must target an `oob` zone.
- Non-IPMI connections cannot target an `oob` zone.
- Connections may only target `server` or `oob` zones.
- `distribution: alternating` with `hedgehog_conn_type` of `bundled`,
  `mclag`, or `eslag` requires the target switch class to have
  `redundancy_type` set.
- `distribution: rail-optimized` should include `rail`.

### `expected`

Optional assertion block used by the loader after apply.

Supported today:

- `expected.counts`

Important meaning:

- `expected.counts.connections` means the number of ingested DIET
  `PlanServerConnection` objects created from `server_connections[]`.
- It does not mean the number of exported Hedgehog wiring `Connection` CRDs.
- A single `server_connections[]` entry can expand into many generated wiring
  `Connection` documents after device generation and YAML export.

Example:

```yaml
expected:
  counts:
    server_classes: 1
    switch_classes: 2
    connections: 3
```

Example interpretation:

- If `server_connections[]` contains 9 entries, then
  `expected.counts.connections: 9` is correct.
- The generated wiring YAML may still contain dozens of Hedgehog `Connection`
  CRDs after expansion across all concrete devices and fabric links.

## Deprecated fields

Do not emit these in new YAML:

- `server_connections[].target_switch_class`
- `server_connections[].nic_module_type`

Use this pattern instead:

```yaml
server_nics:
  - server_class: gpu-small
    nic_id: nic-fe
    module_type: nic_bf3

server_connections:
  - server_class: gpu-small
    nic: nic-fe
    target_zone: fe-leaf/server-downlinks
```

## Recommended authoring workflow for agents

1. Start from the minimal example in this file.
2. Copy patterns from a nearby real case in `netbox_hedgehog/test_cases/`.
3. Keep IDs stable and symbolic.
4. Prefer `target_zone` names that read clearly.
5. Declare `server_nics` first, then reference them from connections.
6. Validate with a dry run before relying on the case.

## Validation command

Run inside the NetBox container:

```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose exec -T netbox python manage.py apply_diet_test_case --case <case_id> --dry-run
```

Useful flags:

- `--require-reference`
  - Fails if referenced manufacturers/device types/module types are not already present.
- Default mode is ensure mode
  - Missing reference objects from `reference_data` are created or updated.

## Good source examples

- Current large regression case:
  - `netbox_hedgehog/test_cases/ux_case_128gpu_odd_ports.yaml`
- Modern generated-plan cases:
  - `netbox_hedgehog/test_cases/training_opg128_clos_ro_air_2srv.yaml`
  - `netbox_hedgehog/test_cases/inference_opg64_clos_ro_air_2srv.yaml`

## Important note

`docs/DIET_TEST_CASES.md` is a scenario write-up for a specific regression case.
It is useful as a design example, but it is not the schema reference.
