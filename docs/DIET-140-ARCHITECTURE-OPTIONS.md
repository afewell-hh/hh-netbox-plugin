# Issue #140 Architecture Options: Fabric Connection Generation

**Date**: 2026-01-05
**Issue**: #140 - Leaf to spine connections not generated
**Status**: Architecture Design Phase

---

## Problem Statement

The device generator creates NetBox devices and server-to-switch cables but does not create leaf-to-spine fabric connections, despite:
- Spine quantities being calculated from leaf uplink demand
- Port zones (UPLINK, FABRIC) being defined and configured
- Full-mesh topology requirements being documented

This document presents architecture options for implementing fabric connection generation.

---

## Design Constraints

### Must Have
1. Full-mesh leaf-spine connectivity within each fabric
2. Deterministic port allocation (reproducible on regeneration)
3. Respect port zone definitions (UPLINK, FABRIC)
4. Support breakout interfaces for high-density uplinks
5. Integration with existing `DeviceGenerator` lifecycle
6. Plan-scoped cleanup (don't affect other plans)
7. Pass UX-accurate TDD tests (AGENTS.md compliance)

### Should Have
1. MCLAG peer link generation
2. Support for non-standard topologies (future)
3. Performance scaling to 1000+ cables
4. Clear error messages for misconfigurations

### Nice to Have
1. IP address assignment for fabric links
2. YAML export of fabric Connection CRDs
3. Validation of fabric topology completeness

---

## Option 1: Implicit Fabric Connections (Recommended for MVP)

### Overview
Generate fabric connections automatically from switch class topology without explicit connection model.

### Design

```python
class DeviceGenerator:
    def _create_connections(self, switch_devices, server_devices):
        interfaces = []
        cables = []

        # Phase 1: Server-to-switch (existing)
        for server_class in self.plan.server_classes.all():
            server_ifaces, server_cables = self._create_server_connections(...)
            interfaces.extend(server_ifaces)
            cables.extend(server_cables)

        # Phase 2: Leaf-to-spine fabric connections (NEW)
        fabric_ifaces, fabric_cables = self._create_fabric_connections(switch_devices)
        interfaces.extend(fabric_ifaces)
        cables.extend(fabric_cables)

        # Phase 3: MCLAG peer links (NEW)
        mclag_ifaces, mclag_cables = self._create_mclag_connections(switch_devices)
        interfaces.extend(mclag_ifaces)
        cables.extend(mclag_cables)

        return interfaces, cables

    def _create_fabric_connections(self, switch_devices):
        """Generate leaf-spine fabric connections for all fabrics."""
        interfaces = []
        cables = []

        for fabric in ['frontend', 'backend', 'oob']:
            # Get leaves and spines in this fabric
            leaves = [d for d in switch_devices
                      if d.custom_field_data.get('hedgehog_fabric') == fabric
                      and d.custom_field_data.get('hedgehog_role') in ['server-leaf', 'border-leaf']]
            spines = [d for d in switch_devices
                      if d.custom_field_data.get('hedgehog_fabric') == fabric
                      and d.custom_field_data.get('hedgehog_role') == 'spine']

            if not leaves or not spines:
                continue  # No fabric connections needed

            # Full-mesh: each leaf connects to each spine
            for leaf in sorted(leaves, key=lambda d: d.name):
                switch_class = self._get_switch_class(leaf)
                uplink_zones = switch_class.port_zones.filter(zone_type='uplink')

                for uplink_zone in uplink_zones:
                    # Distribute uplinks across all spines
                    uplinks_per_spine = math.ceil(
                        uplink_zone.get_port_count() / len(spines)
                    )

                    for spine in sorted(spines, key=lambda d: d.name):
                        # Allocate ports
                        leaf_ports = self.port_allocator.allocate(
                            leaf.name, uplink_zone, count=uplinks_per_spine
                        )

                        spine_class = self._get_switch_class(spine)
                        fabric_zone = spine_class.port_zones.filter(zone_type='fabric').first()

                        spine_ports = self.port_allocator.allocate(
                            spine.name, fabric_zone, count=uplinks_per_spine
                        )

                        # Create cables
                        for leaf_port, spine_port in zip(leaf_ports, spine_ports):
                            leaf_iface = self._get_or_create_interface(
                                device=leaf,
                                name=leaf_port.name,
                                interface_type=self._speed_to_interface_type(uplink_zone.get_speed()),
                                custom_fields={
                                    'hedgehog_zone': uplink_zone.zone_name,
                                    'hedgehog_physical_port': leaf_port.physical_port,
                                    'hedgehog_breakout_index': leaf_port.breakout_index
                                }
                            )

                            spine_iface = self._get_or_create_interface(
                                device=spine,
                                name=spine_port.name,
                                interface_type=self._speed_to_interface_type(fabric_zone.get_speed()),
                                custom_fields={
                                    'hedgehog_zone': fabric_zone.zone_name,
                                    'hedgehog_physical_port': spine_port.physical_port,
                                    'hedgehog_breakout_index': spine_port.breakout_index
                                }
                            )

                            cable = Cable(
                                a_terminations=[leaf_iface],
                                b_terminations=[spine_iface],
                                custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
                            )

                            interfaces.extend([leaf_iface, spine_iface])
                            cables.append(cable)

        return interfaces, cables
```

### Pros
- ✅ **Simple**: No new models, forms, or UI
- ✅ **Consistent**: Aligns with automatic switch quantity calculations
- ✅ **Guaranteed full-mesh**: Algorithm enforces all-to-all connectivity
- ✅ **Fast to implement**: ~3-4 days for MVP
- ✅ **Testable**: Straightforward integration tests

### Cons
- ❌ **Less flexible**: Cannot model non-full-mesh topologies
- ❌ **No user control**: Cannot exclude specific connections
- ❌ **Assumes even distribution**: May not match all customer needs

### Test Plan
```python
class TestFabricConnectionGeneration(NetBoxTestCase):
    def test_full_mesh_leaf_spine_connections(self):
        """Verify each leaf connects to every spine in same fabric."""
        plan = self._create_plan_with_fabric()
        # 2 leaves, 1 spine, 32 uplinks per leaf = 64 fabric cables
        result = DeviceGenerator(plan).generate()

        self.assertEqual(Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count(), 64)

    def test_uplink_zone_port_allocation(self):
        """Verify uplink ports are allocated from UPLINK zones."""
        plan = self._create_plan_with_uplink_zones()
        DeviceGenerator(plan).generate()

        leaf_ifaces = Interface.objects.filter(
            device__custom_field_data__hedgehog_role='server-leaf',
            custom_field_data__hedgehog_zone='spine-uplinks'
        )
        self.assertEqual(leaf_ifaces.count(), 32)

    def test_fabric_zone_port_allocation(self):
        """Verify downlink ports are allocated from FABRIC zones."""
        plan = self._create_plan_with_fabric_zones()
        DeviceGenerator(plan).generate()

        spine_ifaces = Interface.objects.filter(
            device__custom_field_data__hedgehog_role='spine',
            custom_field_data__hedgehog_zone='leaf-downlinks'
        )
        self.assertEqual(spine_ifaces.count(), 64)

    def test_breakout_interface_creation(self):
        """Verify breakout interfaces are created when needed."""
        plan = self._create_plan_requiring_breakout()
        # 2 leaves × 32 uplinks with 2x breakout = 128 logical uplinks
        DeviceGenerator(plan).generate()

        leaf_ifaces = Interface.objects.filter(
            device__custom_field_data__hedgehog_role='server-leaf',
            custom_field_data__hedgehog_zone='spine-uplinks'
        )
        # Expect E1/1/1, E1/1/2, E1/2/1, E1/2/2, etc.
        self.assertTrue(any('/' in i.name for i in leaf_ifaces))

    def test_mclag_pair_fabric_connections(self):
        """Verify MCLAG pairs both connect to all spines."""
        plan = self._create_plan_with_mclag()
        # 1 MCLAG pair (2 leaves), 2 spines, 32 uplinks per leaf
        # = 2 leaves × 2 spines × 32 uplinks = 128 cables
        result = DeviceGenerator(plan).generate()

        self.assertEqual(result.cable_count, 128)

    def test_multiple_fabrics_independent(self):
        """Verify frontend/backend fabrics don't cross-connect."""
        plan = self._create_plan_with_fe_and_be()
        DeviceGenerator(plan).generate()

        # No cables between FE leaves and BE spines
        fe_leaf_ifaces = Interface.objects.filter(
            device__custom_field_data__hedgehog_fabric='frontend',
            device__custom_field_data__hedgehog_role='server-leaf'
        )
        for iface in fe_leaf_ifaces:
            cable = iface.cable
            if cable:
                peer = cable.b_terminations[0].parent
                self.assertEqual(
                    peer.custom_field_data.get('hedgehog_fabric'),
                    'frontend'
                )
```

### Migration Path
1. Implement `_create_fabric_connections()` method
2. Add integration tests
3. Test with 128-GPU case
4. Deploy with feature flag (optional)
5. Remove post-MVP notes from documentation

---

## Option 2: Explicit Fabric Connection Model

### Overview
Add `PlanFabricConnection` model for explicit user control over fabric connections.

### Data Model

```python
class PlanFabricConnection(NetBoxModel):
    """Explicit fabric connection definition between switch classes."""

    plan = ForeignKey(TopologyPlan, related_name='fabric_connections')
    connection_id = CharField(max_length=100)  # e.g., "fe-leaf-to-spine"

    # Source (leaf)
    source_switch_class = ForeignKey(PlanSwitchClass, related_name='outgoing_fabric')
    source_zone = ForeignKey(SwitchPortZone, related_name='fabric_sources')

    # Destination (spine)
    target_switch_class = ForeignKey(PlanSwitchClass, related_name='incoming_fabric')
    target_zone = ForeignKey(SwitchPortZone, related_name='fabric_targets')

    # Configuration
    links_per_pair = PositiveIntegerField(default=1)  # Links between each leaf-spine pair
    speed = PositiveIntegerField()  # e.g., 800 (Gbps)
    connection_type = CharField(choices=ConnectionTypeChoices, default='fabric')

    class Meta:
        ordering = ['plan', 'connection_id']
        unique_together = [['plan', 'connection_id']]
```

### Form & UI

New form fields in topology planning:
- "Add Fabric Connection" button on switch class detail page
- Select source leaf class + zone
- Select target spine class + zone
- Specify links per pair (default: auto-calculate)

### Pros
- ✅ **Explicit control**: Users can model non-standard topologies
- ✅ **Flexible**: Can exclude specific connections if needed
- ✅ **Audit trail**: Visible in UI which connections are planned
- ✅ **Validation**: Can validate before generation

### Cons
- ❌ **Complex**: Requires new model, migration, form, views, serializers
- ❌ **User burden**: Users must manually define connections
- ❌ **Inconsistent**: Switch quantities auto-calculated, but connections manual
- ❌ **Slow to implement**: ~8-10 days for full implementation

### When to Use
- Phase 2 feature for advanced topologies
- Customer requirement for non-full-mesh designs
- Integration with external fabric planning tools

---

## Option 3: Hybrid Approach

### Overview
Default to automatic generation (Option 1) but allow `PlanFabricConnection` overrides (Option 2).

### Algorithm

```python
def _create_fabric_connections(self, switch_devices):
    """Generate fabric connections, respecting explicit overrides."""

    # Check for explicit connections
    explicit_connections = self.plan.fabric_connections.all()

    if explicit_connections.exists():
        # User provided explicit connections, use those
        return self._create_explicit_fabric_connections(explicit_connections)
    else:
        # No explicit connections, auto-generate full-mesh
        return self._create_automatic_fabric_connections(switch_devices)
```

### Pros
- ✅ **Best of both worlds**: Simple default + advanced control
- ✅ **Gradual adoption**: Start with auto, add model later
- ✅ **Backward compatible**: Existing plans work unchanged

### Cons
- ❌ **Deferred complexity**: Eventually need to implement Option 2
- ❌ **Two code paths**: Increases maintenance burden

---

## Option 4: Configuration-Based Approach

### Overview
Add `fabric_connection_mode` field to `TopologyPlan` with options: `auto`, `manual`, `disabled`.

### Model Change

```python
class TopologyPlan(NetBoxModel):
    # ... existing fields ...

    fabric_connection_mode = CharField(
        max_length=20,
        choices=[
            ('auto', 'Automatic (full-mesh)'),
            ('manual', 'Manual (explicit connections)'),
            ('disabled', 'No fabric connections')
        ],
        default='auto'
    )
```

### Behavior
- `auto`: Use Option 1 (implicit full-mesh)
- `manual`: Use Option 2 (explicit `PlanFabricConnection` model)
- `disabled`: Skip fabric connection generation

### Pros
- ✅ **Clear intent**: User chooses behavior explicitly
- ✅ **Feature flag**: Can disable for testing/rollout
- ✅ **Flexible**: Supports all use cases

### Cons
- ❌ **Still requires Option 2**: Manual mode needs explicit model
- ❌ **Migration complexity**: Existing plans default to new behavior

---

## Recommended Approach

### Phase 1 (MVP): Option 1 - Implicit Fabric Connections

**Rationale**:
1. Aligns with existing calculation-driven design
2. Simplest implementation (3-4 days)
3. Meets documented topology requirements (full-mesh)
4. Can be extended later with Option 2 if needed

**Acceptance Criteria**:
- All leaves connect to all spines in same fabric
- Uplink ports allocated from UPLINK zones
- Downlink ports allocated from FABRIC zones
- Breakout interfaces created when needed
- Integration tests verify cable counts
- 128-GPU case generates 1828 cables (548 server + 1280 fabric)

### Phase 2 (Future): Option 3 - Hybrid Approach

**When**:
- After MVP proves stable
- Customer requests non-full-mesh topologies
- Time budget allows (8-10 additional days)

**Implementation**:
1. Add `PlanFabricConnection` model
2. Add UI for creating explicit connections
3. Update `_create_fabric_connections()` to check for explicit connections first
4. Add validation (no conflicting explicit + automatic)
5. Document advanced use cases

---

## Implementation Checklist

### Pre-Implementation
- [ ] Review research summary with team
- [ ] Approve recommended approach (Option 1)
- [ ] Finalize test plan (minimum 15 tests)
- [ ] Create implementation spec document

### Core Implementation
- [ ] Add `_create_fabric_connections()` method
- [ ] Add `_create_mclag_connections()` method (separate concern)
- [ ] Update `_create_connections()` orchestration
- [ ] Add breakout interface creation logic
- [ ] Add fabric zone port allocation

### Testing
- [ ] Write integration tests for fabric connections
- [ ] Write unit tests for port allocation logic
- [ ] Update existing tests (cable count expectations)
- [ ] Add performance benchmark tests (1000+ cables)
- [ ] Test 128-GPU case manually

### Documentation
- [ ] Update `DIET_QUICK_START.md` (remove post-MVP note)
- [ ] Update `DIET_TEST_CASES.md` (new cable counts)
- [ ] Add troubleshooting guide for misconfigurations
- [ ] Update API documentation if needed

### Deployment
- [ ] Run full test suite
- [ ] Manual verification in staging
- [ ] Performance testing on large topologies
- [ ] Feature flag deployment (optional)
- [ ] Monitor for regressions

---

## Risk Mitigation

### Technical Risks

**Risk**: Breakout interface naming conflicts
- **Mitigation**: Use custom fields to track physical port + breakout index
- **Test**: Verify E1/1/1, E1/1/2 naming in integration tests

**Risk**: Port allocation order affects availability
- **Mitigation**: Allocate uplinks before server ports (priority-based)
- **Test**: Verify SERVER zones don't consume UPLINK zone ports

**Risk**: MCLAG pair discovery fails
- **Mitigation**: Use deterministic sorting (by name) and validate pair count
- **Test**: Add assertion that MCLAG switches come in pairs

### Operational Risks

**Risk**: Cable count explosion impacts performance
- **Mitigation**: Benchmark on 500+ device topologies
- **Action**: Optimize queries, use bulk_create()

**Risk**: Existing plans regenerate with new cables
- **Mitigation**: Add feature flag, staged rollout
- **Action**: Clear communication about cable count changes

**Risk**: User confusion about new cables appearing
- **Mitigation**: Documentation updates, release notes
- **Action**: Add "Fabric Connections" section to preview page

---

## Performance Considerations

### Current Performance (128-GPU Case)
- 164 devices
- 1096 interfaces
- 548 cables
- **Generation time**: ~2-3 seconds

### Projected Performance (with Fabric)
- 164 devices (unchanged)
- ~2372 interfaces (1096 + 1276 fabric)
- 1828 cables (548 + 1280 fabric)
- **Estimated time**: ~6-8 seconds (3x cable count)

### Optimization Strategies
1. Use `bulk_create()` for interfaces and cables
2. Prefetch related objects (switch_class, port_zones)
3. Cache port allocator state across fabrics
4. Use `select_related()` for device queries

---

## Open Questions for Team

1. **IP Address Assignment**: Should fabric cables include IP addresses, or defer to hhfab?
   - Recommendation: Defer to hhfab (post-MVP)

2. **YAML Export**: Implement fabric YAML export simultaneously or separately?
   - Recommendation: Separately (post-MVP as documented)

3. **Feature Flag**: Deploy behind feature flag for gradual rollout?
   - Recommendation: Yes - add `enable_fabric_connections` setting

4. **Border-Leaf Handling**: Implement special border-leaf external connections?
   - Recommendation: No - defer until customer requirement emerges

5. **Validation**: Add topology validation (all leaves reach all spines)?
   - Recommendation: Yes - add as part of plan validation

---

## Success Metrics

### MVP Success Criteria
1. ✅ 128-GPU case generates expected cable count (1828)
2. ✅ All integration tests pass (minimum 15 new tests)
3. ✅ No regressions in existing tests
4. ✅ Generation time < 10 seconds for 128-GPU case
5. ✅ Documentation updated and reviewed

### Phase 2 Success Criteria
1. ✅ Explicit fabric connections UI functional
2. ✅ Users can create non-full-mesh topologies
3. ✅ YAML export includes fabric connections
4. ✅ Border-leaf external connections supported (if prioritized)

---

## Conclusion

**Recommended**: Implement Option 1 (Implicit Fabric Connections) for MVP.

**Justification**:
- Fastest path to value (3-4 days)
- Aligns with existing design patterns
- Meets documented topology requirements
- Low technical risk
- Easily extended to Option 3 (Hybrid) if needed

**Next Step**: Proceed to detailed specification and test plan creation.
