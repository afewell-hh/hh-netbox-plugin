# RA Asset Publishing

Final RA assets should be published into the composition directory for each
variant inside the `training-ra` or `inference-ra` repository.

To avoid clobbering top-level placeholder files while the pipeline is still
being refined, generated outputs are copied into a `generated/` subtree.

## Destination Layout

Example:

```text
training-ra/compositions/OPG-128/clos-ro--.../
  README.md
  bom.yaml
  connectivity-map.csv
  wiring.yaml
  vpc.yaml
  diagrams/
  generated/
    inputs/
      topology-plan.yaml
      topology-plan.test-case.yaml
      translation-notes.md
      source-links.txt
    netbox/
      inventory.json
      interface-connections.csv
    wiring/
      full.yaml
      backend.yaml
      frontend.yaml
    hhfab/
      backend.validate.txt
      backend.drawio
      frontend.validate.txt
      frontend.drawio
    logs/
      ingest.log
      generate.log
      export.log
      diagram.log
```

## Publisher Script

Use:

```bash
cd /home/ubuntu/afewell-hh/hh-netbox-plugin
scripts/publish_ra_assets.sh \
  --artifact-root <local-artifact-root> \
  --composition-dir <ra-composition-dir>
```

The script copies these sections when present:

- `inputs/`
- `netbox/`
- `wiring/`
- `hhfab/`
- `logs/`

Each destination section is replaced atomically at the directory level by
removing the existing section and copying the source section fresh.

## Recommended Flow

1. Generate all local artifacts under the standard pipeline artifact root.
2. Review the generated files locally.
3. Publish into the target RA composition directory with the script above.
4. Review the `generated/` subtree in the RA repo.
5. Commit/push from the RA repo once the bundle is accepted.
