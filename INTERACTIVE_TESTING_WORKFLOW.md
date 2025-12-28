# Interactive Testing Workflow for DIET Test Cases

## Overview

The `setup_case_128gpu_odd_ports` command now supports interactive inspection workflows with new `--report` and `--cleanup-after` flags. This allows you to:

1. **Run tests and leave environment up** for manual inspection
2. **Generate detailed reports** about the test case
3. **Optionally clean up** after reviewing results

## New Flags

### `--report`
Displays a detailed report of the plan and all generated objects, including:
- Plan summary and status
- All server classes with connections
- All switch classes with calculated quantities
- Port zones and breakout configurations
- Generated devices, interfaces, and cables
- Direct links to NetBox UI

### `--cleanup-after`
When combined with `--report`, automatically cleans up all data after displaying the report. Useful for automated testing where you want to see results but don't need to inspect interactively.

## Workflows

### Workflow 1: Quick Inspection (Leave Environment Up)

**Use case**: You want to run the test, see a summary, then manually inspect in NetBox UI.

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Create test case, generate devices, and show report
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --clean --generate --report

# Output includes:
# - Detailed plan information
# - Server and switch class breakdown
# - Generated object counts
# - Direct NetBox URLs for inspection

# Environment remains up - now you can:
# 1. Visit http://localhost:8000/plugins/hedgehog/topology-plans/
# 2. Inspect devices, cables, interfaces in NetBox UI
# 3. Run additional queries via Django shell
# 4. Export YAML and validate

# When done inspecting, clean up:
docker compose exec netbox python manage.py reset_diet_data --plan <plan_id>
```

**Example Output**:
```
================================================================================
[REPORT] DETAILED REPORT
================================================================================

[PLAN] Plan: UX Case 128GPU Odd Ports (ID: 32)
   Status: draft
   Description: 128 GPU servers with FE redundancy, BE rails, storage split, ...

[SERVERS] Server Classes:
   -  gpu-fe-only: 96 servers
     - Category: gpu
     - GPUs per server: 8
     - Device type: GPU-Server-FE
     - Connections:
       -> fe: 2x200G (unbundled, alternating) to fe-gpu-leaf
   ...

[SWITCHES] Switch Classes:
   -  fe-gpu-leaf (frontend, server-leaf)
     - Quantity: 2 (calculated: 2, override: -)
     - Device type: DS5000
     - MCLAG pair: True
     - Port zones:
       -> server-downlinks (server): ports 1-63:2, breakout 4x200g
       -> uplinks (uplink): ports 2-64:2, breakout 1x800g
   ...

[GENERATED] Generated Objects:
   -  Devices: 164
     - GPU-Server-FE: 96
     - GPU-Server-FE-BE: 32
     - DS5000: 18
     - Storage-Server-200G: 18
   -  Interfaces: 1096
   -  Cables: 548

[LINKS] View in NetBox:
   -  Plan detail: http://localhost:8000/plugins/hedgehog/topology-plans/32/
   -  All plans: http://localhost:8000/plugins/hedgehog/topology-plans/
   -  Generated devices: http://localhost:8000/dcim/devices/?tag=hedgehog-generated

[TIP] Tip: Data remains in database. Clean up with:
  docker compose exec netbox python manage.py reset_diet_data --plan 32
```

---

### Workflow 2: Automated Test with Report (Clean Up After)

**Use case**: CI/CD or automated testing where you want to validate results but don't need to keep the environment.

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Create, generate, report, and clean up in one command
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports \
  --clean --generate --report --cleanup-after

# Output includes:
# - Complete detailed report
# - Automatic cleanup at the end
# - Clean database state after execution
```

**Example Output**:
```
[GENERATED] Creating 128-GPU odd-port breakout case...
OK Case created successfully.
  Plan: UX Case 128GPU Odd Ports (ID: 33)
  Calculated 6 switch classes

[GEN]  Generating devices for case...
OK Generation complete: 164 devices, 1096 interfaces, 548 cables.

================================================================================
[REPORT] DETAILED REPORT
================================================================================
[... full report ...]

[CLEANUP] Cleaning up after report...
  Deleting 548 cables...
  Deleting 164 devices...
  Deleting 1096 interfaces...
  Deleting plan metadata...
  OK Cleanup complete
OK Cleanup complete.
```

---

### Workflow 3: Create Without Report (Original Behavior)

**Use case**: Just want to create the test case without extra output.

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Create plan only (no generation)
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --clean

# Create plan and generate devices (no report)
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --clean --generate

# Both leave data in place for manual inspection
```

---

### Workflow 4: Iterative Development

**Use case**: Testing changes to calculations or generation logic.

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Initial run with report
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports \
  --clean --generate --report

# Review results, identify issues
# Make code changes
# Re-run with clean slate

docker compose exec netbox python manage.py setup_case_128gpu_odd_ports \
  --clean --generate --report

# Repeat until satisfied
```

---

## Manual Inspection Techniques

### Via NetBox UI

After running the command without `--cleanup-after`, you can inspect via the web UI:

1. **Plan Detail Page**:
   ```
   http://localhost:8000/plugins/hedgehog/topology-plans/<plan_id>/
   ```
   - View all server and switch classes
   - See calculated quantities
   - Inspect port zones and connections

2. **Generated Devices**:
   ```
   http://localhost:8000/dcim/devices/?tag=hedgehog-generated
   ```
   - Filter by `hedgehog-generated` tag
   - Inspect individual device configurations
   - View interface assignments

3. **Cables**:
   ```
   http://localhost:8000/dcim/cables/?tag=hedgehog-generated
   ```
   - See all generated connections
   - Verify terminations are correct

### Via Django Shell

```bash
docker compose exec netbox python manage.py shell

# Interactive Python shell with Django context
from netbox_hedgehog.models.topology_planning import TopologyPlan, PlanSwitchClass
from dcim.models import Device, Cable, Interface

# Get the plan
plan = TopologyPlan.objects.get(name="UX Case 128GPU Odd Ports")

# Inspect switch classes
for swc in plan.switch_classes.all():
    print(f"{swc.switch_class_id}: {swc.effective_quantity} switches")

# Count generated objects
devices = Device.objects.filter(
    tags__slug='hedgehog-generated',
    custom_field_data__hedgehog_plan_id=str(plan.pk)
)
print(f"Generated {devices.count()} devices")

# Inspect specific device
device = devices.first()
print(f"Device: {device.name}")
print(f"Interfaces: {device.interfaces.count()}")
```

### Via Management Commands

```bash
# Check specific switch class calculation
docker compose exec netbox python manage.py shell << EOF
from netbox_hedgehog.models.topology_planning import TopologyPlan
plan = TopologyPlan.objects.get(name="UX Case 128GPU Odd Ports")
fe_leaf = plan.switch_classes.get(switch_class_id="fe-gpu-leaf")
print(f"FE GPU Leaf: {fe_leaf.effective_quantity} switches")
print(f"Calculated: {fe_leaf.calculated_quantity}")
print(f"Override: {fe_leaf.override_quantity}")
EOF

# Export YAML for validation
docker compose exec netbox python manage.py shell << EOF
from netbox_hedgehog.models.topology_planning import TopologyPlan
from netbox_hedgehog.services.yaml_generator import YAMLGenerator

plan = TopologyPlan.objects.get(name="UX Case 128GPU Odd Ports")
generator = YAMLGenerator(plan)
yaml_output = generator.generate()

print(f"Generated {yaml_output.count('kind: Connection')} Connection CRDs")
print("\nFirst connection:")
print(yaml_output.split('---')[0])
EOF
```

---

## Cleanup Options

### Option 1: Clean Specific Plan (Recommended for Shared Environments)

```bash
# Get plan ID from report output or query
docker compose exec netbox python manage.py reset_diet_data --plan 32
```

**Deletes**:
- Only the specified plan and its related objects
- Devices/cables/interfaces scoped to that plan

**Preserves**:
- Other plans
- DeviceTypes
- Reference data

### Option 2: Clean All DIET Data

```bash
# Preview what will be deleted
docker compose exec netbox python manage.py reset_diet_data --dry-run

# Actually delete all DIET planning data
docker compose exec netbox python manage.py reset_diet_data --no-input
```

**Deletes**:
- All TopologyPlans
- All generated devices/cables/interfaces (scoped by hedgehog_plan_id)

**Preserves**:
- DeviceTypes (unless `--include-device-types` specified)
- Reference data (BreakoutOptions)

### Option 3: Full Reset Including DeviceTypes

```bash
docker compose exec netbox python manage.py reset_diet_data \
  --include-device-types --no-input
```

**Deletes**:
- All DIET planning data
- All generated objects
- DS5000 and server DeviceTypes
- InterfaceTemplates

**Use case**: Complete reset to pristine state

---

## Flag Combinations Reference

| Flags | Behavior | Use Case |
|-------|----------|----------|
| (none) | Create plan only, no generation | Quick plan creation |
| `--generate` | Create + generate devices | Standard test case creation |
| `--report` | Create + show report (no cleanup) | Interactive inspection |
| `--generate --report` | Create + generate + report (no cleanup) | Full test with inspection |
| `--report --cleanup-after` | Create + report + cleanup | Automated testing |
| `--generate --report --cleanup-after` | Create + generate + report + cleanup | CI/CD pipeline |
| `--clean` | Remove old data first | Fresh slate |
| `--clean --generate --report` | Full test from scratch | Development workflow |

---

## Example: Complete Interactive Session

```bash
# Start with clean environment
cd /home/ubuntu/afewell-hh/netbox-docker

# 1. Create test case with full report
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports \
  --clean --generate --report

# Output shows:
#   Plan ID: 32
#   164 devices generated
#   URLs for NetBox UI

# 2. Open NetBox UI in browser
# Visit: http://localhost:8000/plugins/hedgehog/topology-plans/32/

# 3. Inspect devices
# Visit: http://localhost:8000/dcim/devices/?tag=hedgehog-generated

# 4. Run additional queries via shell
docker compose exec netbox python manage.py shell
>>> from dcim.models import Cable
>>> Cable.objects.filter(tags__slug='hedgehog-generated').count()
548

# 5. Export and validate YAML
docker compose exec netbox python manage.py shell << EOF
from netbox_hedgehog.models.topology_planning import TopologyPlan
from netbox_hedgehog.services.yaml_generator import YAMLGenerator

plan = TopologyPlan.objects.get(pk=32)
yaml_output = YAMLGenerator(plan).generate()
with open('/tmp/wiring.yaml', 'w') as f:
    f.write(yaml_output)
print("YAML written to /tmp/wiring.yaml")
EOF

# 6. When done, clean up
docker compose exec netbox python manage.py reset_diet_data --plan 32
```

---

## Summary

**For Quick Inspection** (leave environment up):
```bash
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports \
  --clean --generate --report
```

**For Automated Testing** (clean up after):
```bash
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports \
  --clean --generate --report --cleanup-after
```

**For Interactive Development** (inspect, modify, re-run):
```bash
# Run test
docker compose exec netbox python manage.py setup_case_128gpu_odd_ports \
  --clean --generate --report

# Inspect results, make code changes, then re-run
# Repeat until satisfied
```

The new flags make it easy to switch between automated testing (with cleanup) and interactive inspection (leave environment up) without changing your workflow!
