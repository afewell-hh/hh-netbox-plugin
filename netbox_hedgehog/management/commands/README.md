# management/commands

## Command Taxonomy

### Canonical Bootstrap Command

**`load_diet_reference_data`** — the single entry point for all locally-bundled
reference data. Run this after install, purge, or reset.

```bash
docker compose exec netbox python manage.py load_diet_reference_data
```

This command is idempotent and covers all bundled DeviceTypes, BreakoutOptions,
NIC/transceiver ModuleTypes, and bundled switch profiles. It is the only command
that should appear in bootstrap or reset scripts.

### Supporting Commands (called by load_diet_reference_data)

- `import_fabric_profiles` — loads bundled switch profiles from `fabric_profiles/`
- `seed_management_switch_device_types` — seeds `celestica-es1000`
- `seed_generic_server_device_types` — seeds server DeviceTypes
- `load_breakout_options` — seeds BreakoutOptions
- `populate_transceiver_bays` — builds ModuleBayTemplates from InterfaceTemplates
  (run after `load_diet_reference_data`)

### Deprecated Commands

**`seed_diet_device_types`** — DEPRECATED (DIET-448). Do not call from any
bootstrap or reset script. Retained for historical reference only. It produces
the legacy `ds5000` slug with wrong interface types (`800gbase-x-qsfpdd`).
Use `load_diet_reference_data` instead.

## Ownership Boundaries

- Bootstrap/reset scripts must call only `load_diet_reference_data`.
- Do not add seed logic to migration files — seed data belongs in management commands.
- The `fabric_profiles/` directory owns bundled switch profile files; see `fabric_profiles/README.md`.
