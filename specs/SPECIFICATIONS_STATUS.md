# DIET Technical Specifications - Status

**Date:** 2025-12-27
**Process:** Following CNCF Enhancement Proposal (KEP) style specifications

---

## Overview

Creating detailed technical specifications before implementation to ensure:
- ✅ No arbitrary architectural decisions by implementation agents
- ✅ Complete test coverage specifications
- ✅ Exact code changes with line numbers
- ✅ Clear error handling and edge cases
- ✅ Backward compatibility guarantees

---

## Specifications Created

### ✅ DIET-SPEC-TEMPLATE.md
**Status:** Complete
**Purpose:** Template for all future specifications
**Contents:**
- Metadata section
- Motivation and goals
- Detailed design (models, code, algorithms)
- Testing specifications
- Implementation plan
- Approval workflow

---

### ✅ DIET-SPEC-001: Fix Hardcoded Port Counts
**Status:** Complete - Approved for Implementation
**File:** `specs/DIET-SPEC-001-Fix-Hardcoded-Port-Counts.md`
**Priority:** HIGH (Phase 1)
**Risk:** LOW

**Summary:** Replace `physical_ports = 64` with dynamic InterfaceTemplate query

**Key Details:**
- **New Function:** `get_physical_port_count(device_type)` with full signature, docstring, examples
- **Modified Locations:** 3 exact locations with line numbers (236, 306, 568)
- **Test Cases:** 5 specified test cases with expected outcomes
- **Fallback:** Returns 64 if no InterfaceTemplates (backward compatible)
- **Implementation Time:** 1 day

**Deliverables:**
- Exact code changes (before/after comparison)
- New test file: `test_port_count.py` with 4 test methods
- Integration test for DS3000 (32-port switch)
- File changes checklist (7 files)
- Rollback plan
- Test helper function for creating InterfaceTemplates
- Prominent caveat about non-physical template over-count risk

**Resolved Questions:**
1. Fallback to 64 vs raise ValidationError? → **Decided: Fallback to 64**
2. Caching needed? → **Decided: No, COUNT query is fast**
3. Fallback logging? → **Decided: No logging for MVP**

**Approval Status:**
- [x] Dev C review (incorporated feedback)
- [x] User approval (2025-12-27)
- [ ] Ready for implementation

---

### ✅ DIET-SPEC-002: Zone-Based Speed Derivation
**Status:** Complete - Approved for Implementation
**File:** `specs/DIET-SPEC-002-Zone-Based-Speed-Derivation.md`
**Priority:** HIGH (Phase 2)
**Risk:** MEDIUM

**Summary:** Replace `native_speed` with zone-based speed lookup with conditional uplink subtraction

**Updates (2025-12-27):**
- ✅ Fixed connection_type: 'downlink' → 'server' (matches PortZoneTypeChoices)
- ✅ Reuses get_physical_port_count() from SPEC-001 in fallback path
- ✅ Added conditional uplink subtraction logic (avoids double-count)
- ✅ Updated all test cases to use 'server' zone type
- ✅ Fixed error table and test assertion messages (final cleanup)

**Approval Status:**
- [x] User approval (2025-12-27)

**Key Details:**
- **New Dataclass:** `PortCapacity` with fields (native_speed, port_count, source_zone, is_fallback)
- **New Function:** `get_port_capacity_for_connection(device_extension, switch_class, connection_type)`
- **Modified Locations:** 3 calculation functions (lines 217-227, 290-306, 413-568)
- **Test Cases:** 8+ unit tests (zone-based, fallback, mixed-port, errors, priority)
- **Fallback Logic:** Use DeviceTypeExtension.native_speed when no zones defined
- **Implementation Time:** 2-3 days

**Deliverables:**
- Complete function implementation with docstring
- Algorithm specification (step-by-step)
- Before/after code patterns
- New test file: `test_port_capacity.py` with 8+ test methods
- Integration test for ES1000 (48×1G + 4×25G mixed-port switch)
- Test helper recommendation for zone creation
- Edge cases table (6 cases)
- NetBox schema alignment section

**Complexity:**
- More complex than SPEC-001 (fallback logic, dataclass, multiple code paths)
- Requires validation of connection_type parameter
- Needs extensive test coverage for ES1000 (mixed-port switch)
- Handles zone ordering (order_by priority)

**Resolved Design Decisions:**
1. Return type: Dict vs NamedTuple vs Dataclass? → **Decided: Dataclass**
2. Error handling: Raise vs return None? → **Decided: Raise ValidationError**
3. Zone selection: First zone vs prioritize by criteria? → **Decided: First zone by priority**

**Open Questions:**
1. Fallback logging? → **Recommend: No logging for MVP** (same as SPEC-001)

**Approval Status:**
- [ ] Dev B review
- [ ] Dev C review
- [ ] User approval

---

### ✅ DIET-SPEC-003: Uplink Capacity from Zones
**Status:** Complete - Approved for Implementation
**File:** `specs/DIET-SPEC-003-Uplink-Capacity-from-Zones.md`
**Priority:** MEDIUM (Phase 3)
**Risk:** LOW-MEDIUM

**Summary:** Derive uplink ports from zones with conditional subtraction to avoid double-count

**Updates (2025-12-27):**
- ✅ Documented conditional uplink subtraction logic
- ✅ Clarified when get_uplink_port_count() should/shouldn't be called
- ✅ Updated to align with SPEC-002's capacity.is_fallback pattern

**Approval Status:**
- [x] User approval (2025-12-27)

**Key Details:**
- **New Function:** `get_uplink_port_count(switch_class)`
- **Priority Order:** Override (Priority 1) > Zones (Priority 2) > Error (Priority 3)
- **Deprecation:** Mark `DeviceTypeExtension.uplink_ports` as deprecated
- **Override Logic:** PlanSwitchClass.uplink_ports_per_switch takes precedence over zones
- **Modified Locations:** 3 calculation functions (lines 241, 308, 571)
- **Test Cases:** 7+ unit tests (override, zones, priority, multiple zones, errors)
- **Implementation Time:** 1 day

**Deliverables:**
- Complete function implementation with priority logic
- Algorithm specification (3-step priority)
- Deprecation notice for DeviceTypeExtension.uplink_ports
- New test file: `test_uplink_capacity.py` with 7+ test methods
- Integration test for zone-derived uplinks
- Migration guide for existing deployments (audit script)
- Edge cases table (3 cases)

**Breaking Change Alert:**
- Plans with `uplink_ports_per_switch = None` AND no uplink zones will fail with ValidationError
- Migration guide provides audit script to identify affected plans

**Migration Strategy:**
- Audit script to find plans needing fixes
- Two fix options: (A) Set override, (B) Create uplink zone
- Optional data migration from deprecated uplink_ports field

**Resolved Design Decisions:**
1. Default uplink count when none specified? → **Decided: Error (fail fast)**
2. Use deprecated DeviceTypeExtension.uplink_ports as fallback? → **Decided: No (deprecate, not use)**
3. Multiple uplink zones? → **Decided: Sum all zones**

**Open Questions:**
1. Audit script scope? → **Recommend: Audit only (manual fixes)**

**Approval Status:**
- [ ] Dev B review
- [ ] Dev C review
- [ ] User approval

---

## Implementation Approach

### Current Approach: Detailed Specifications First ✅

**Why:**
- Prevents arbitrary implementation decisions
- Ensures architectural consistency
- Provides clear test specifications
- Enables parallel implementation (once approved)
- Reduces code review cycles

**Inspired by:**
- CNCF KEP (Kubernetes Enhancement Proposal) process
- Our own research findings (CNCF_PRACTICES_GUIDE.md)
- Industry best practices (Terraform RFCs, Python PEPs)

---

## Next Steps

### ✅ Step 1: Create All Three Specifications (Complete)
**Status:** Complete (2025-12-27)

Completed Tasks:
- [x] DIET-SPEC-001: Fix Hardcoded Port Counts (approved)
- [x] DIET-SPEC-002: Zone-Based Speed Derivation (complete)
- [x] DIET-SPEC-003: Uplink Capacity from Zones (complete)
- [x] All specs follow approved format
- [x] Dev C feedback incorporated into SPEC-001

### Step 2: Team Review of All Three Specs (Current)
**Estimate:** 1-2 days

Tasks:
- [x] SPEC-001 approved by user (2025-12-27)
- [ ] Post SPEC-002 and SPEC-003 to GitHub issue #114 for review
- [ ] Dev B reviews for implementation clarity
- [ ] Dev C reviews for testing completeness
- [ ] User approves architectural direction
- [ ] Address feedback if needed

### Step 3: Begin Implementation (After Approval)
**Estimate:** 4-5 days total

**Implementation Order:**
1. **SPEC-001** (1 day) - Low risk, no dependencies, **approved**
2. **SPEC-002** (2-3 days) - Depends on SPEC-001, awaiting approval
3. **SPEC-003** (1 day) - Can run parallel to SPEC-002 (low dependency), awaiting approval

**Parallel Opportunities:**
- SPEC-001 can start immediately (approved)
- SPEC-003 can start in parallel with SPEC-002 (only uses zone query pattern, not PortCapacity)

---

## Specifications Methodology

### Structure (from DIET-SPEC-TEMPLATE)

Each spec contains:

1. **Metadata** - ID, status, authors, reviewers, dependencies
2. **Motivation** - Problem statement, current vs desired behavior
3. **Goals/Non-Goals** - Explicit scope boundaries
4. **Detailed Design** - Data models, code changes, algorithms
5. **Error Handling** - Every error case documented
6. **Backward Compatibility** - Compatibility matrix, migration guide
7. **Testing** - Test scenarios, matrix, performance tests
8. **Implementation Plan** - Step-by-step with file changes checklist
9. **Alternatives Considered** - Why we chose this approach
10. **Open Questions** - Decisions needing team input
11. **Approval** - Reviewer checklist and sign-off

### Level of Detail

**Code Examples:**
- Exact function signatures with types
- Complete docstrings (Args, Returns, Raises, Examples)
- Before/after comparisons for modifications
- Line numbers for precision

**Tests:**
- Exact test method names
- Test scenario descriptions
- Expected outcomes
- Test data setup code

**Migration:**
- Exact commands to run
- Rollback procedures
- Data migration scripts (if needed)

---

## Questions for Team

### Q1: Specification Detail Level
**Current:** Very detailed (exact line numbers, complete code examples)
**Question:** Is this level of detail helpful, or too verbose?
**Feedback:** [Awaiting team input]

### Q2: Open Questions in Specs
**Current:** Specs include open questions for team discussion
**Question:** Should we resolve all questions before finalizing spec, or iterate?
**Feedback:** [Awaiting team input]

### Q3: Review Process
**Question:** How should we review specs?
**Options:**
- A) GitHub issue comments
- B) Dedicated review meeting
- C) Async document review with tracked changes
**Recommendation:** Option A (GitHub) for async + transparency
**Feedback:** [Awaiting team input]

---

## Benefits Observed

### From Creating All Three Specs:

**DIET-SPEC-001:**
1. **Discovered edge cases:** Fallback behavior for devices without InterfaceTemplates
2. **Clarified testing:** Exact test scenarios prevent gaps
3. **Identified test fixture issues:** Existing tests need InterfaceTemplate setup
4. **Documented decisions:** Fallback to 64 (not error) - rationale captured
5. **Clear file changes:** Implementation agent knows exactly what to modify
6. **Dev C feedback loop:** Incorporated non-physical template caveat, logging notes, test helper

**DIET-SPEC-002:**
1. **Model discovery:** Found actual SwitchPortZone structure (different from refactoring plan)
2. **Priority logic:** Documented zone selection by priority field
3. **Dataclass design:** Structured return type with is_fallback flag for debugging
4. **ES1000 support:** Complete specification for mixed-port switch calculations
5. **Backward compatibility:** Explicit fallback path preserves existing behavior

**DIET-SPEC-003:**
1. **Priority order clarity:** Three-tier priority (override > zones > error)
2. **Breaking change identification:** Plans with uplink_ports_per_switch=None will fail
3. **Migration guidance:** Audit script to identify affected plans
4. **Deprecation path:** Clear timeline for DeviceTypeExtension.uplink_ports removal
5. **Parallel implementation:** Can run with SPEC-002 (low dependency)

---

## Estimated Timeline

### ✅ Specification Phase (Complete)
- [x] DIET-SPEC-TEMPLATE: 1 hour (complete)
- [x] DIET-SPEC-001: 3 hours (complete, approved)
- [x] DIET-SPEC-002: 2.5 hours (complete)
- [x] DIET-SPEC-003: 2 hours (complete)
- **Total:** ~8.5 hours for 3 detailed specs (2025-12-27)

### Review Phase (Current)
- [x] SPEC-001 user approval: 2025-12-27
- [ ] SPEC-002 team review: 1-2 days (async)
- [ ] SPEC-003 team review: 1-2 days (async)
- [ ] Address feedback if needed: 0.5-1 day
- **Total:** 2-4 days

### Implementation Phase (After Approval)
- [ ] SPEC-001: 1 day (can start immediately - approved)
- [ ] SPEC-002: 2-3 days (depends on SPEC-001)
- [ ] SPEC-003: 1 day (can run parallel with SPEC-002)
- **Total:** 4-5 days (3-4 days if parallel)

**Overall Timeline:** ~2 weeks from spec start to implementation complete

**Actual Spec Creation Time:** 8.5 hours (vs estimated 8 hours)

**Comparison:** Without specs, implementation might be faster (1 week) but would require:
- Multiple code review cycles
- Rework for architectural issues
- Missing test coverage
- Inconsistent patterns
- Risk of arbitrary architectural decisions

**Net Benefit:** Specs save time in code review and prevent technical debt

---

## Next Action

**Immediate:** Post SPEC-002 and SPEC-003 to GitHub issue #114 for team review

**Then:** Begin SPEC-001 implementation (approved)

**Parallel opportunities:**
- Dev B/Dev C review SPEC-002 and SPEC-003 (async)
- Dev A implements SPEC-001 (approved)
- Once SPEC-002/003 approved, start implementation (can run in parallel)

---

**Status:** ✅ All three specifications complete and ready for team review.
**Date:** 2025-12-27
