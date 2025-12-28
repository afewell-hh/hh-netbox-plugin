# DIET Testing Strategy

## Overview

The DIET (Design & Implementation Excellence Tools) module uses a three-tier testing strategy to ensure correctness and prevent regressions while keeping PR feedback fast.

This document describes:
1. The three-tier testing approach
2. Management commands for data seeding and cleanup
3. CI/CD workflows
4. Manual testing procedures

## Three-Tier Testing Approach

## Local Development Workflow (Fast Iteration)

Use the local NetBox container for rapid iteration. Reset DIET data as needed to avoid stale state.

**Quick reset (recommended for daily use)**:
```bash
cd /home/ubuntu/afewell-hh/hh-netbox-plugin
scripts/reset_local_dev.sh
```

**Quick reset + purge inventory (return to near-empty NetBox inventory)**:
```bash
cd /home/ubuntu/afewell-hh/hh-netbox-plugin
scripts/reset_local_dev.sh --purge-inventory
```

**Full reset (occasional, heavier)**:
```bash
cd /home/ubuntu/afewell-hh/hh-netbox-plugin
scripts/reset_local_dev.sh --full
```

**Plan-scoped cleanup (fastest)**:
```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose exec netbox python manage.py reset_diet_data --plan <plan_id> --no-input
```

### Tier 1: Fast Unit & Integration Tests (Every PR)

**Purpose**: Catch bugs quickly without requiring a full NetBox deployment.

**What it tests**:
- Model validation and business logic
- Topology calculations (switch quantity, port allocation, etc.)
- Form validation
- Service layer functionality
- Template rendering

**How to run**:
```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning --verbosity=2
```

**Location**: `netbox_hedgehog/tests/test_topology_planning/`

**CI**: Runs on every PR push (Job: `django-tests`)

**Expected duration**: 2-5 minutes

---

### Tier 2: Fresh-Install Smoke Test (Every PR)

**Purpose**: Prove that DIET works on a clean NetBox install without stale data.

**What it tests**:
- Fresh NetBox installation via docker compose
- Plugin migrations apply cleanly
- Seed commands work correctly
- 128-GPU test case creates valid topology
- Device generation completes successfully
- YAML export produces valid output

**How to run manually**:
```bash
# Start fresh NetBox instance
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose down -v  # Clean slate
docker compose up -d

# Wait for NetBox to be ready
docker compose exec netbox python manage.py migrate

# Seed data
docker compose exec netbox python manage.py load_diet_reference_data
docker compose exec netbox python manage.py seed_diet_device_types

# Create test case
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --generate

# Verify
docker compose exec netbox python manage.py shell
>>> from netbox_hedgehog.models.topology_planning import TopologyPlan
>>> plan = TopologyPlan.objects.get(name="UX Case 128GPU Odd Ports")
>>> print(f"Plan has {plan.switch_classes.count()} switch classes")
```

**CI**: Runs on every PR push (Job: `fresh-install-smoke`)

**Expected duration**: 8-12 minutes

---

### Tier 3: Reset + Seed Verification (Nightly / Manual)

**Purpose**: Confirm that cleanup commands work and data can be reset to baseline state.

**What it tests**:
- Reset command deletes all DIET data
- Re-seeding produces identical results
- No hidden dependencies on stale data
- Commands are idempotent

**How to run manually**:
```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Create initial state
docker compose exec netbox python manage.py load_diet_reference_data
docker compose exec netbox python manage.py seed_diet_device_types
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --generate

# Reset DIET data (preserve DeviceTypes)
docker compose exec netbox python manage.py reset_diet_data --no-input

# Verify clean state
docker compose exec netbox python manage.py shell
>>> from netbox_hedgehog.models.topology_planning import TopologyPlan
>>> TopologyPlan.objects.count()  # Should be 0

# Re-seed
docker compose exec netbox python manage.py load_diet_reference_data
docker compose exec netbox python manage.py seed_diet_device_types
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --generate

# Verify idempotency
```

**CI**: Runs nightly at 2 AM UTC (Job: `reset-seed-verification`)

**Expected duration**: 10-15 minutes

---

## Management Commands

### `load_diet_reference_data`

**Purpose**: Load BreakoutOption reference data.

**Usage**:
```bash
docker compose exec netbox python manage.py load_diet_reference_data
```

**What it creates**:
- 15 BreakoutOption records (1x800g, 2x400g, 4x200g, etc.)

**Idempotent**: Yes (uses `update_or_create`)

**Dependencies**: None

---

### `seed_diet_device_types`

**Purpose**: Create standard DIET DeviceTypes for topology planning.

**Usage**:
```bash
# Seed DeviceTypes
docker compose exec netbox python manage.py seed_diet_device_types

# Re-seed (removes old ones first)
docker compose exec netbox python manage.py seed_diet_device_types --clean
```

**What it creates**:
- **DS5000** switch (Celestica, 64x800G ports)
  - 64 InterfaceTemplates (Ethernet1/1 - Ethernet1/64)
  - DeviceTypeExtension with native_speed=800, supported_breakouts, etc.
- **GPU-Server-FE** (Generic, 2x200G frontend)
  - 2 InterfaceTemplates (eth1, eth2)
- **GPU-Server-FE-BE** (Generic, 2x200G + 8x400G)
  - 10 InterfaceTemplates (eth1, eth2, cx7-1 through cx7-8)
- **Storage-Server-200G** (Generic, 2x200G)
  - 2 InterfaceTemplates (eth1, eth2)

**Idempotent**: Yes (uses `get_or_create` and updates missing fields)

**Dependencies**: None (creates manufacturers if needed)

**Options**:
- `--clean`: Delete existing DIET DeviceTypes before seeding

---

### `setup_case_128gpu_odd_ports`

**Purpose**: Create the 128-GPU odd-port breakout test case.

**Usage**:
```bash
# Create test case
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports

# Re-create (clean old data first)
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --clean

# Create and generate devices
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --generate
```

**What it creates**:
- TopologyPlan: "UX Case 128GPU Odd Ports"
- 4 server classes (96 GPU FE-only, 32 GPU with BE, 18 storage)
- 6 switch classes (FE leaf, BE leaf, spines, storage leaves)
- Port zones with 4x200G and 2x400G breakouts
- Server connections (alternating, rail-optimized, bundled)

**With `--generate`**:
- Creates Device objects for all servers and switches
- Creates Interface objects based on InterfaceTemplates
- Creates Cable objects for all connections
- Tags all objects with `hedgehog-generated`
- Stores `hedgehog_plan_id` in custom fields

**Idempotent**: With `--clean` flag

**Dependencies**:
- `load_diet_reference_data` (for BreakoutOptions)
- `seed_diet_device_types` (for DeviceTypes) - OR - will create them itself

**Options**:
- `--clean`: Remove existing case data before creating
- `--generate`: Generate devices/interfaces/cables after creating plan

---

### `reset_diet_data`

**Purpose**: Comprehensive cleanup of all DIET planning data.

**Usage**:
```bash
# Preview what will be deleted (dry run)
docker compose exec netbox python manage.py reset_diet_data --dry-run

# Reset planning data (preserve DeviceTypes)
docker compose exec netbox python manage.py reset_diet_data

# Reset everything including DeviceTypes
docker compose exec netbox python manage.py reset_diet_data --include-device-types

# Skip confirmation (for CI)
docker compose exec netbox python manage.py reset_diet_data --no-input
```

**What it deletes**:

**Always deleted**:
- All TopologyPlan objects
- All PlanServerClass objects
- All PlanSwitchClass objects
- All PlanServerConnection objects
- All SwitchPortZone objects
- All GenerationState objects
- All Devices tagged with `hedgehog-generated`
- All Interfaces tagged with `hedgehog-generated`
- All Cables tagged with `hedgehog-generated`

**With `--include-device-types`**:
- DS5000 DeviceType (and its InterfaceTemplates, DeviceTypeExtension)
- GPU-Server-FE DeviceType
- GPU-Server-FE-BE DeviceType
- Storage-Server-200G DeviceType

**What it preserves**:
- Users and permissions
- BreakoutOption reference data
- Other NetBox objects (Sites, Manufacturers not used by DIET, etc.)
- DeviceTypes (unless `--include-device-types` is used)

**Idempotent**: Yes (safe to run multiple times)

**Dependencies**: None

**Options**:
- `--dry-run`: Show what would be deleted without deleting
- `--include-device-types`: Also delete DIET seed DeviceTypes
- `--no-input`: Skip confirmation prompt (use with caution!)

**Safety**:
- Requires typing "DELETE" to confirm (unless `--no-input`)
- Uses transactions (all-or-nothing)
- Provides detailed summary before deletion

---

## CI/CD Workflows

### `.github/workflows/ci-diet-tests.yml`

**Triggers**:
- Push to `main`, `develop`, or `diet-*` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch
- Nightly schedule (2 AM UTC)

**Jobs**:

#### Job A: `django-tests`
- Runs Django unit/integration tests
- Uses test database
- Fast (2-5 minutes)
- **Runs on**: Every PR push

#### Job B: `fresh-install-smoke`
- Brings up clean NetBox via docker compose
- Runs migrations
- Seeds data (`load_diet_reference_data`, `seed_diet_device_types`)
- Creates 128-GPU test case
- Generates devices
- Verifies calculations, devices, YAML export
- **Runs on**: Every PR push

#### Job C: `reset-seed-verification`
- Creates initial data
- Resets all DIET data
- Re-seeds data
- Verifies idempotency
- **Runs on**: Nightly schedule or manual trigger

---

## Testing Checklist for PRs

When submitting a PR that touches DIET code:

### Required Tests (All PRs)
- [ ] All Django unit tests pass (`django-tests` job)
- [ ] Fresh-install smoke test passes (`fresh-install-smoke` job)
- [ ] No calculation errors in 128-GPU test case
- [ ] Generated devices match expected counts

### Additional Tests (For Calculation Changes)
- [ ] Run specific calculation test cases:
  ```bash
  docker compose exec netbox python manage.py test \
    netbox_hedgehog.tests.test_topology_planning.test_topology_calculations
  ```
- [ ] Verify SPEC compliance (SPEC-001, SPEC-002, SPEC-003)
- [ ] Check edge cases (zero servers, single switch, MCLAG pairing)

### Additional Tests (For Data Model Changes)
- [ ] Create and apply migration
- [ ] Test migration on fresh database
- [ ] Test migration rollback
- [ ] Update `reset_diet_data` command if new models added

### Additional Tests (For Generator Changes)
- [ ] Verify device naming conventions
- [ ] Check interface assignments
- [ ] Validate cable terminations
- [ ] Test YAML export format

---

## Manual Testing Procedures

### Test Fresh Install

```bash
# Clean environment
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose down -v

# Start NetBox
docker compose up -d

# Wait and migrate
sleep 30
docker compose exec netbox python manage.py migrate

# Seed
docker compose exec netbox python manage.py load_diet_reference_data
docker compose exec netbox python manage.py seed_diet_device_types

# Create test case
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --generate

# Verify in UI
open http://localhost:8000/plugins/hedgehog/topology-plans/
```

### Test Reset + Re-seed

```bash
# Assume data exists from previous test

# Dry run
docker compose exec netbox python manage.py reset_diet_data --dry-run

# Actually reset
docker compose exec netbox python manage.py reset_diet_data

# Verify clean
docker compose exec netbox python manage.py shell
>>> from netbox_hedgehog.models.topology_planning import TopologyPlan
>>> TopologyPlan.objects.count()  # Should be 0

# Re-seed
docker compose exec netbox python manage.py load_diet_reference_data
docker compose exec netbox python manage.py seed_diet_device_types
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --generate

# Verify same results
```

### Test Idempotency

```bash
# Run seed commands multiple times
docker compose exec netbox python manage.py load_diet_reference_data
docker compose exec netbox python manage.py load_diet_reference_data
docker compose exec netbox python manage.py load_diet_reference_data

# Should not create duplicates
docker compose exec netbox python manage.py shell
>>> from netbox_hedgehog.models.topology_planning import BreakoutOption
>>> BreakoutOption.objects.filter(breakout_id="4x200g").count()  # Should be 1

# Test DeviceType seeding
docker compose exec netbox python manage.py seed_diet_device_types
docker compose exec netbox python manage.py seed_diet_device_types

# Should not duplicate
docker compose exec netbox python manage.py shell
>>> from dcim.models import DeviceType
>>> DeviceType.objects.filter(model="DS5000").count()  # Should be 1
```

---

## Troubleshooting

### CI Job Fails: "NetBox is not ready"

**Symptom**: CI workflow times out waiting for NetBox to start.

**Solution**:
- Check Docker resource limits in GitHub Actions
- Increase timeout in workflow (currently 60 iterations × 5 seconds)
- Check netbox logs in CI output

### Test Fails: "Calculation errors detected"

**Symptom**: 128-GPU test case fails with calculation errors.

**Solution**:
- Check if recent changes broke switch quantity calculation
- Run local tests: `python manage.py test netbox_hedgehog.tests.test_topology_planning.test_topology_calculations`
- Review error messages for specific switch class failures
- Verify port zones are correctly configured

### Reset Command Fails: Foreign Key Constraint

**Symptom**: `reset_diet_data` fails with IntegrityError.

**Solution**:
- Deletion order matters (children before parents)
- Check if new models were added without updating reset command
- Review dependencies in `_delete_diet_data()` method
- May need to add new model to deletion sequence

### Fresh Install Test Fails: Missing DeviceType

**Symptom**: Test case creation fails because DeviceType doesn't exist.

**Solution**:
- Ensure `seed_diet_device_types` runs before test case creation
- Check that DeviceType seeding completed successfully
- Verify manufacturer was created
- Check InterfaceTemplates were created

---

## Best Practices

### For Developers

1. **Run tests locally before pushing**:
   ```bash
   docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning
   ```

2. **Test against fresh install** if changing data model or calculations:
   ```bash
   docker compose down -v
   docker compose up -d
   # ... seed and test
   ```

3. **Use dry-run** before running destructive commands:
   ```bash
   docker compose exec netbox python manage.py reset_diet_data --dry-run
   ```

4. **Document test cases** for new features in `test_topology_planning/`

5. **Follow AGENTS.md** requirements:
   - All `manage.py` commands inside container
   - Integration tests for UX flows
   - NetBox plugin conventions

### For CI

1. **Fresh database per job** - Use `docker compose down -v` to ensure clean state

2. **Explicit seeding** - Don't assume any data exists, always seed explicitly

3. **Verification steps** - After seeding, verify expected state with Python shell checks

4. **Timeout limits** - All jobs have timeouts to prevent hanging

5. **Logs on failure** - Capture NetBox logs for debugging

---

## Summary

This three-tier testing strategy ensures:
- **Fast feedback** (Tier 1: 2-5 min unit tests)
- **Fresh-install validation** (Tier 2: 8-12 min smoke test)
- **Idempotency verification** (Tier 3: nightly reset+seed)

Key commands:
- `load_diet_reference_data` - Load BreakoutOptions
- `seed_diet_device_types` - Create standard DeviceTypes
- `setup_case_128gpu_odd_ports` - Create test topology
- `reset_diet_data` - Comprehensive cleanup

All commands are idempotent and safe to run multiple times.

CI runs automatically on every PR and nightly for comprehensive verification.
