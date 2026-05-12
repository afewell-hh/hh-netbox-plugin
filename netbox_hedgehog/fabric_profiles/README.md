# fabric_profiles

## Ownership

This directory contains only switch profile files that are **explicitly bundled
with this plugin** and maintained by HNP contributors.

**Do not add profiles imported via `--fabric-ref` here.**

The `--fabric-ref` flag on `import_fabric_profiles` pulls profiles from an
external Hedgehog fabric reference. Those profiles are dynamic, externally
owned, and must not be committed to this directory.

## What belongs here

- Profile files for switches that HNP bundles directly (e.g. `p_bcm_celestica_ds5000.go`)
- Each profile file here is seeded by `load_diet_reference_data` via `import_fabric_profiles`

## What does not belong here

- Profiles fetched at runtime with `--fabric-ref` — these are dynamic and
  externally owned
- Stale or manually-edited copies of external profiles

## How profiles are loaded

`load_diet_reference_data` calls `import_fabric_profiles` without `--fabric-ref`,
which processes only the files in this directory. That is the canonical path for
bundled switch inventory.

For the full Hedgehog switch library, run:

```bash
docker compose exec netbox python manage.py import_fabric_profiles --fabric-ref <ref>
```

That result is **not** stored in this directory.
