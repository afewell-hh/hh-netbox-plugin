# Reference Architecture Pipeline Execution Plan

## Purpose

Convert every published reference architecture variant listed in
[`topology-catlog.md`](/home/ubuntu/afewell-hh/hh-netbox-plugin/topology-catlog.md)
into a DIET topology-plan YAML, generate NetBox inventory from the plan, export
all required artifacts, validate per-fabric wiring with `hhfab`, and store the
results in a deterministic directory layout.

This plan assumes:

- RA source descriptions are authoritative for server/NIC/fabric intent.
- RA switch-count guesses are not authoritative.
- DIET/HNP must calculate switch quantities from plan inputs.
- `hhfab diagram` runs once per exported wiring YAML file, not once per plan.

## Current Automation Status

Existing commands in this repo:

- `apply_diet_test_case` for YAML-defined plan ingest
- `generate_devices` for NetBox inventory generation
- `export_plan_inventory_json` for plan-scoped inventory JSON export
- `export_interface_connections_csv` for plan-scoped interface-connections CSV export
- `export_wiring_yaml` for full or `--split-by-fabric` wiring export
- `validate_wiring_yaml` for `hhfab validate`-backed validation

Known gaps to plan for:

- No existing repo command found for batch `hhfab diagram` generation/collection
- No manifest-driven batch runner yet

## Inventory Export Strategy

Per-plan NetBox inventory export should be done by filtering generated objects,
not by resetting the whole local inventory after every variant.

Why this is viable:

- Device generation already stamps generated objects with
  `custom_field_data.hedgehog_plan_id = <plan.pk>`
- Generated objects are also tagged with `hedgehog-generated`
- Existing code and tests already scope generated Devices, Interfaces, and
  Cables by `hedgehog_plan_id`

Implication for the RA pipeline:

- Default behavior: export inventory JSON and related artifacts by filtering on
  `hedgehog_plan_id`
- Optional cleanup behavior: after all artifacts for a variant are captured, use
  `reset_diet_data --plan <plan_id> --no-input` if the local environment should
  be kept small or visually clean
- Full-instance reset between every variant is not the preferred default

Recommended export scope for a per-plan inventory JSON:

- Devices where `custom_field_data.hedgehog_plan_id == <plan_id>`
- Interfaces attached to those devices and/or stamped with the same custom field
- Cables stamped with the same custom field
- Modules attached to plan-owned devices if NIC/module inventory is needed

This means the pipeline can safely process multiple plans in one NetBox
instance, as long as all exports are filtered by plan ID and cleanup is done in
a controlled way.

## Local Queue And Worker Strategy

Device generation is expected to be the slowest stage. The pipeline should use
NetBox's queued job model and scale workers conservatively instead of trying to
run generation synchronously in a tight manual loop.

Observed local environment on 2026-03-13:

- Host CPU: 20 vCPU
- Host RAM: 58 GiB
- Load average was low at time of inspection
- Current NetBox worker count: 1
- Current worker containers have no explicit CPU or memory limits

Recommended local policy:

- Queue multiple generation jobs asynchronously.
- Keep export steps dependency-aware: export only after that variant's
  generation job completes successfully.
- Scale workers at the Docker Compose layer, not by changing DIET logic.
- Start with 2 workers.
- Increase to 3 workers only after confirming stable DB/Redis/NetBox behavior.
- Treat 4 workers as the upper bound for routine local batch work unless
  measurements show additional headroom.
- Do not default to 8+ workers on this host.

Recommended commands:

```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose up -d --scale netbox-worker=2
docker compose ps
```

If stable under load:

```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose up -d --scale netbox-worker=3
docker compose ps
```

Operational guidance:

- Default local batch mode: 2 workers
- Aggressive local batch mode: 3 workers
- Only consider 4 workers after observing queue drain times, DB response, and
  NetBox UI responsiveness
- Reset back to 1 worker when not running batch pipelines

Suggested future hardening:

- Add explicit CPU/memory limits for `netbox-worker` in the local Compose
  override so worker scaling cannot overrun the host accidentally.
- Add a manifest-driven runner with configurable concurrency, defaulting to
  `max_parallel_generations=2`.
- Add queue-state polling so the runner can submit the next job only when a
  worker slot is expected to free up soon.

## Scope Summary

Catalog variants currently indexed:

- Training RA: 30
- Inference RA: 6
- Total: 36

These should be processed as a manifest-driven batch, not as ad hoc manual runs.

## Execution Model

Each variant moves through these stages:

1. Read RA source files and normalize them into DIET inputs.
2. Author a topology-plan YAML that contains only planning inputs.
3. Save the authored plan document in two places:
   - a reusable local fixture under `netbox_hedgehog/test_cases/`
   - the final per-variant asset bundle under `inputs/`
4. Ingest the topology-plan YAML into NetBox.
5. Generate devices/interfaces/cables from the plan.
6. Export operational artifacts.
7. Validate/export one wiring artifact per managed fabric.
8. Store everything in a stable asset directory.
9. Update manifest status and review notes.

## Rules For Translation

When converting an RA into a DIET topology plan:

- Preserve server classes, quantities, NIC/DPU identities, port speeds, and
  fabric intent from the RA.
- Preserve storage, infrastructure, and management node counts from the RA.
- Preserve fabric semantics such as converged, backend, frontend, dual-plane,
  or split-horizon intent.
- Do not copy RA-estimated switch counts into the plan.
- Do not precompute leaf/spine counts outside DIET unless needed only as a
  reasonableness check.
- Let DIET compute switch quantities from the provided server/NIC inputs.
- Record any ambiguity in a translation-notes file before plan creation.

## Batch Strategy

Process the catalog by archetype, not by raw count.

Recommended proving order:

1. Inference `minimal-fe-converged`
2. Training single-fabric CLOS RO
3. Training single-fabric CLOS SH
4. Training dual-plane
5. XOC composed variants
6. Remaining density/cooling permutations

This reduces risk by validating one instance of each topology pattern before
bulk execution.

## Work Breakdown

### Phase 1: Catalog Normalization

Deliverables:

- Variant manifest for all 36 catalog entries
- Source file links per variant
- Archetype classification per variant
- Translation worksheet per variant

Checklist:

- [ ] Catalog entry copied into manifest
- [ ] RA repo and composition path confirmed
- [ ] Primary README/source files identified
- [ ] Variant classified by archetype
- [ ] Expected managed fabrics identified
- [ ] Unknowns/questions logged

### Phase 2: Topology-Plan Authoring

Deliverables:

- One topology-plan YAML per variant
- One reusable local YAML fixture per variant under `netbox_hedgehog/test_cases/`
- One copied topology-plan document inside the final variant asset bundle
- Translation notes for any RA-to-DIET assumptions

Checklist:

- [ ] Server classes represented
- [ ] Quantities represented
- [ ] Installed NICs/DPUs represented accurately
- [ ] Connection intent modeled per fabric
- [ ] No manual switch counts copied from RA
- [ ] YAML passes ingest validation
- [ ] Local reusable fixture saved under `netbox_hedgehog/test_cases/`
- [ ] Asset-bundle copy saved under the variant `inputs/` directory

### Phase 3: Execution Pipeline

Deliverables:

- Generated NetBox inventory per variant
- Interface-connections CSV
- Inventory JSON
- Full wiring YAML
- Split wiring YAMLs per managed fabric
- `hhfab validate` output per wiring file
- `hhfab diagram` Draw.io output per wiring file

Checklist:

- [ ] Plan ingested successfully
- [ ] Devices generated successfully
- [ ] Full wiring YAML exported
- [ ] Split wiring YAMLs exported for all inventory-backed managed fabrics
- [ ] `hhfab validate` passed for each wiring file
- [ ] `hhfab diagram` ran for each wiring file
- [ ] CSV export saved
- [ ] Inventory JSON saved

### Phase 4: Review and Signoff

Deliverables:

- Per-variant status notes
- Failure log for unresolved variants
- Batch summary by archetype

Checklist:

- [ ] Asset directory complete
- [ ] Manifest status updated
- [ ] Translation assumptions captured
- [ ] Validation failures captured with stdout/stderr
- [ ] Ready for peer review

## Artifact Layout

Store outputs by variant, not by tool.

```text
artifacts/
  training/
    OPG-128/
      clos-ro--cx7-1x400g--bf3-2x200g--storage-conv-2x200g--cooling-air--dens-2srv/
        manifest.yaml
        inputs/
          topology-plan.yaml
          topology-plan.test-case.yaml
          translation-notes.md
          source-links.txt
        netbox/
          interface-connections.csv
          inventory.json
        wiring/
          full.yaml
          managed-fabric-a.yaml
          managed-fabric-b.yaml
        hhfab/
          full.validate.txt
          managed-fabric-a.validate.txt
          managed-fabric-a.drawio
          managed-fabric-b.validate.txt
          managed-fabric-b.drawio
        logs/
          ingest.log
          generate.log
          export.log
          diagram.log
```

Rules:

- One variant per directory
- One `drawio` file per wiring YAML
- Validation logs named to match the wiring artifact they validate
- Keep raw command logs
- Keep manifest beside the generated assets for local review
- Keep the authored topology-plan YAML in the asset bundle even if the same
  plan also exists locally as a reusable test-case fixture

## Manifest Schema

Each variant should have a manifest record with at least:

- `variant_id`: stable local ID
- `ra_family`: `training` or `inference`
- `ra_series`: `OPG-64`, `XOC-512`, etc.
- `composition_group`: optional grouping such as `2x-OPG-512`
- `variant_slug`
- `source_repo`
- `source_path`
- `source_url`
- `archetype`
- `expected_managed_fabrics`
- `topology_plan_name`
- `topology_plan_yaml`
- `asset_root`
- `status`
- `owner`
- `peer_reviewer`
- `translation_notes`
- `known_gaps`

Recommended status values:

- `catalogued`
- `sources-reviewed`
- `yaml-authored`
- `yaml-fixture-saved`
- `ingested`
- `generated`
- `exported`
- `validated`
- `diagrammed`
- `complete`
- `blocked`

## Per-Variant Definition Of Done

A variant is complete only when all of the following are true:

- Topology-plan YAML exists and is reviewable
- Local YAML fixture exists under `netbox_hedgehog/test_cases/`
- Asset-bundle copy of the topology-plan document exists
- Plan ingest succeeds
- Device generation succeeds
- Interface-connections CSV exists
- Inventory JSON exists
- Full wiring export exists
- Split wiring export exists for every inventory-backed managed fabric
- `hhfab validate` succeeded for every wiring export that should validate
- `hhfab diagram` produced one Draw.io file per wiring export
- Asset directory contains logs and notes
- Manifest status is `complete`

## Command Skeleton

Existing command skeletons to reuse:

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

docker compose exec -T netbox python manage.py apply_diet_test_case --case <case_id> --clean
docker compose exec -T netbox python manage.py generate_devices <plan_id>
docker compose exec -T netbox python manage.py export_plan_inventory_json <plan_id> --output <path>/inventory.json
docker compose exec -T netbox python manage.py export_interface_connections_csv <plan_id> --output <path>/interface-connections.csv
docker compose exec -T netbox python manage.py export_wiring_yaml <plan_id> --output <path>/full.yaml
docker compose exec -T netbox python manage.py export_wiring_yaml <plan_id> --output <path>/managed-fabric --split-by-fabric
docker compose exec -T netbox python manage.py validate_wiring_yaml <plan_id>
```

Additional pipeline steps to implement or standardize:

- save each authored plan as a reusable local YAML fixture under
  `netbox_hedgehog/test_cases/`
- run `hhfab diagram` against each split wiring YAML artifact
- collect all outputs under the variant asset directory
- optionally enqueue generation via NetBox jobs while keeping post-generation
  export stages blocked on per-variant completion
- optionally clean up plan-owned generated inventory after artifact capture with
  `reset_diet_data --plan <plan_id> --no-input`

Suggested local fixture naming convention:

- training variants:
  `netbox_hedgehog/test_cases/training_<series>_<variant_tokens>.yaml`
- inference variants:
  `netbox_hedgehog/test_cases/inference_<series>_<variant_tokens>.yaml`

Examples:

- `netbox_hedgehog/test_cases/training_opg128_clos_ro.yaml`
- `netbox_hedgehog/test_cases/inference_opg32_minimal_fe_converged.yaml`

## Translation Worksheet Guidance

Every variant should answer these questions before YAML authoring:

- What server classes exist?
- How many instances of each server class exist?
- Which installed NICs/DPUs exist on each server class?
- Which server connections land on which fabrics?
- Are frontend and backend separate, converged, or dual-plane?
- Are there management-only fabrics that should be excluded from wiring export?
- Are there XOC composition boundaries that map to multiple managed fabrics?
- What is unclear in the RA text that requires a recorded assumption?

## Suggested Team Split

Dev C:

- Own manifest format
- Own artifact layout
- Own automation plan and batch runner design
- Review topology-plan YAMLs for correctness against DIET rules
- Review per-fabric export/diagram completeness

Dev A:

- Read RA sources and fill translation worksheets
- Draft topology-plan YAMLs from normalized inputs
- Run first-pass manual executions for each archetype
- Record ambiguities and failed cases

User-mediated coordination:

- Pass reviewed assumptions between Dev A and Dev C
- Resolve ambiguities in RA intent
- Approve archetype-level translation rules before bulk execution

## Immediate Next Tasks

1. Create the 36-row master manifest from `topology-catlog.md`.
2. Add archetype labels to each row.
3. Select one pilot variant for each archetype.
4. Create translation worksheets for the pilot variants.
5. Identify whether CSV/JSON export should use NetBox REST, ORM, or new
   management commands.
6. Implement a manifest-driven runner only after the pilot archetypes succeed.

## Open Questions

- Should inventory JSON be a raw NetBox object export, a DIET-scoped normalized
  export, or both?
- What exact interface-connections CSV schema is required?
- Should full wiring YAML also get a Draw.io diagram, or only split per-fabric
  artifacts?
- For XOC variants, should each constituent OPG become a separate plan or one
  multi-fabric plan?
- What naming convention should be used for topology-plan names and asset roots?
