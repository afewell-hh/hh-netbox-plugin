# migrations

## Scope

Migrations in this directory manage **schema changes only**: creating, altering,
and dropping database tables and columns.

**Do not add seed data, reference data, or DeviceType creation to migrations.**

Seed data (DeviceTypes, BreakoutOptions, ModuleTypes, etc.) belongs in management
commands, not migrations. The canonical bootstrap command is:

```bash
docker compose exec netbox python manage.py load_diet_reference_data
```

## Why this boundary matters

Migration-embedded seed data is hard to purge, hard to update, and becomes stale
as the data model evolves. Repeated regressions (e.g. DIET-556) trace back to
migration 0009 which created DeviceType rows that survived and conflicted with
later canonical seeds.

Migration 0053 introduced a one-time cleanup of those stale rows — the only
acceptable exception: removing rows created incorrectly by a prior migration.

## Adding migrations

```bash
docker compose exec netbox python manage.py makemigrations netbox_hedgehog
```

Always review generated migrations before committing. Never add `DeviceType`,
`ModuleType`, `BreakoutOption`, or other reference-data objects in a migration's
`operations` list.
