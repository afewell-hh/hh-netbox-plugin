# netbox_hedgehog

NetBox plugin for Hedgehog network fabric automation (HNP).

## Bootstrap Path

The canonical bootstrap path for all locally-bundled reference inventory is:

```bash
docker compose exec netbox python manage.py load_diet_reference_data
```

Run this command after install, after a purge (`--purge-inventory`), or after a
full reset. It is idempotent — safe to run multiple times.

`load_diet_reference_data` seeds:
- Bundled switch DeviceTypes (e.g. `celestica-ds5000`) via `import_fabric_profiles`
- Management switch (`celestica-es1000`) via `seed_management_switch_device_types`
- Server DeviceTypes (`gpu-server-fe`, `gpu-server-fe-be`, `storage-server-200g`)
- All BreakoutOptions and NIC / transceiver ModuleTypes

After seeding, run `populate_transceiver_bays` to build ModuleBayTemplates.

## Static vs Dynamic Inventory

| Type | Owner | Seeded by |
|------|-------|-----------|
| Bundled switch profiles | `fabric_profiles/` | `import_fabric_profiles` (called by `load_diet_reference_data`) |
| Management switch, server DeviceTypes | `seed_catalog.py` | `load_diet_reference_data` |
| Full Hedgehog switch library | external `--fabric-ref` | `import_fabric_profiles --fabric-ref` — **not stored here** |

Do not add external switch profile data to `fabric_profiles/`. That directory
owns only the profiles explicitly bundled with this plugin.

## Directory Map

- `fabric_profiles/` — bundled switch profile files (static, repo-owned)
- `management/commands/` — Django management commands; see `management/commands/README.md`
- `migrations/` — schema migrations only; see `migrations/README.md`
- `models/topology_planning/` — DIET planning models
- `tests/test_topology_planning/` — integration and unit tests
- `seed_catalog.py` — static reference data catalog (repo-owned inventory)
