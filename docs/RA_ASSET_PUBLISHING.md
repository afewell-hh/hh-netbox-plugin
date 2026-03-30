# RA Asset Publishing

Final RA assets are published into the composition directory for each variant
inside the `training-ra` or `inference-ra` repository.

## Destination Layout

Assets are published directly into the composition directory using a flat
layout.  There is no `generated/` wrapper.

Example (two-fabric plan with `backend` and `frontend` managed fabrics):

```text
training-ra/compositions/OPG-128/clos-ro--.../
  README.md
  bom.yaml
  connectivity-map.csv
  wiring.yaml          ← top-level placeholder (hand-authored)
  vpc.yaml
  diagrams/
    README.md
    hhfab/
      backend.drawio
      hhfab_validate_backend.log     ← present only when validation failed
      hhfab_validate_frontend.log    ← present (documents gap or success)
  wiring/
    wiring-backend.yaml
    wiring-frontend.yaml             ← absent while MCLAG gap exists; see note
```

For a dual-plane backend plan the wiring/ and diagrams/hhfab/ directories
would contain `backend-plane-a` and `backend-plane-b` entries instead.

For a single-backend, FE-only plan the wiring/ directory contains only
`WIRING_GAP.txt` (no wiring YAML is exportable).

### What `publish_ra_assets.sh` copies

| Artifact source              | Destination                          |
|------------------------------|--------------------------------------|
| `wiring/`                    | `<comp>/wiring/` (full dir replace)  |
| `hhfab/*.drawio`             | `<comp>/diagrams/hhfab/`             |
| `hhfab/hhfab_validate_*.log` | `<comp>/diagrams/hhfab/`             |

Pipeline-internal artifacts (`inputs/`, `netbox/`, `logs/`) are **not**
published to the composition directory.

### Frontend wiring gap note

All current training variants have both `backend` and `frontend` managed
fabrics.  The `export_wiring_yaml --split-by-fabric` command attempts to
export both fabrics but the frontend export fails with:

> Switch references group 'fe-mclag' but no PlanMCLAGDomain exists

As a result `wiring-frontend.yaml` is absent from `wiring/`.  This is a
known pre-existing DIET gap (DS5000 L3MH MCLAG domain not modeled).  Each
variant documents the situation in `diagrams/hhfab/hhfab_validate_frontend.log`.

## Publisher Script

```bash
cd /home/ubuntu/afewell-hh/hh-netbox-plugin
scripts/publish_ra_assets.sh \
  --artifact-root <pipeline-artifact-root> \
  --composition-dir <ra-composition-dir>
```

The script is safe to run repeatedly — it replaces destination directories
atomically so there are no stale files from prior runs.

## Recommended Flow

1. Generate all local artifacts under the standard pipeline artifact root
   (`/tmp/ra_pipeline/<case_id>/`).
2. Review the generated files locally.
3. Publish into the target RA composition directory:
   ```bash
   scripts/publish_ra_assets.sh \
     --artifact-root /tmp/ra_pipeline/<case_id> \
     --composition-dir /path/to/training-ra/compositions/<variant>
   ```
4. Review the `wiring/` and `diagrams/hhfab/` changes in the RA repo.
5. Commit/push from the RA repo once the bundle is accepted.

The `run_ra_pipeline.sh` script calls `publish_ra_assets.sh` automatically
as its final step; the `--composition-dir` argument controls the destination.

## Verification

After publishing, verify the artifact layout with:

```bash
# Check wiring files landed correctly
ls <comp>/wiring/

# Check hhfab diagrams and validation logs landed correctly
ls <comp>/diagrams/hhfab/

# Run the pipeline-level contract checker against the local artifact root
scripts/verify_ra_artifacts.sh --artifact-root /tmp/ra_pipeline/<case_id>
```
