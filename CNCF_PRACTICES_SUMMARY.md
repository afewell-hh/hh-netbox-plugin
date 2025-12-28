# CNCF Design Patterns Research - Summary for DIET

**Full Document:** See `CNCF_PRACTICES_GUIDE.md` for comprehensive 400+ line guide

## Executive Summary

Researched CNCF project patterns to inform DIET architecture. Key findings align well with current direction but suggest specific enhancements.

## Top Recommendations for DIET

### 1. Spec/Status Separation (Kubernetes Pattern) ⭐

**Current:** DIET models mix user inputs and calculated values
**Recommendation:** Explicitly separate:

```python
class DIETPlan(models.Model):
    # User inputs (spec) - what they want
    gpu_count = models.IntegerField()
    redundancy_policy = models.CharField(...)

    # Calculated values (status) - what system generated
    calculated_leaf_count = models.IntegerField(null=True, blank=True)
    calculated_spine_count = models.IntegerField(null=True, blank=True)
    validation_status = models.CharField(...)
```

**Benefits:**
- Clear ownership (user vs system)
- Obvious what can be edited
- Matches Kubernetes/CNCF patterns

### 2. Plan-Preview-Apply Workflow (Terraform Pattern) ⭐

**Current:** DIET generates topology but no explicit approval workflow
**Recommendation:** Add workflow states:

```python
STATUS_DRAFT = 'draft'      # Editing in progress
STATUS_PLANNED = 'planned'  # Calculations complete, ready for review
STATUS_APPROVED = 'approved' # Ready to apply
STATUS_APPLIED = 'applied'  # Pushed to production NetBox
```

**Benefits:**
- Review changes before applying (like `terraform plan`)
- Audit trail (who approved when)
- Prevents accidental production changes

### 3. Diff/Preview Functionality (ArgoCD Pattern) ⭐

**Current:** No way to see what will change when applying plan
**Recommendation:** Implement diff view:

```python
def generate_diff(plan):
    """Show additions/modifications/deletions like terraform plan"""
    return {
        'additions': ['16 leaf switches', '256 cables', ...],
        'modifications': ['2 devices (add interfaces)', ...],
        'deletions': [],
    }
```

**Benefits:**
- Users see exactly what will be created
- Prevents surprises
- Enables informed approval decisions

### 4. Deterministic Generation (IaC Pattern) ✅

**Current:** Already implemented! ✓
**Keep doing:**
- Same input → same output (every time)
- Deterministic naming (leaf-01, leaf-02)
- No randomness in calculations

### 5. Declarative Validation (CEL/OPA Pattern)

**Current:** Django model validation + clean() methods ✓
**Enhancement:** Add policy-as-code validation (future):

```python
# Example OPA policy
deny[msg] {
    input.spec.gpuCount > 256
    input.metadata.environment != "research"
    msg = "GPU count exceeds limit for non-research environments"
}
```

## Testing Recommendations

### Current State ✓
- Good integration tests in `test_topology_planning/`
- Test real UX flows (views, forms, validation)
- Test 8-GPU and 128-GPU scenarios

### Suggested Additions

**1. Scale Tests**
```python
def test_256_gpu_fabric(self): ...
def test_512_gpu_fabric(self): ...
def test_1024_gpu_fabric(self): ...
```

**2. Performance Benchmarks**
```python
def test_calculation_performance(self):
    """Ensure calculations complete in <60s"""
    for gpu_count in [8, 16, 32, 64, 128, 256]:
        start = time.time()
        plan = create_diet_plan(gpu_count=gpu_count)
        assert time.time() - start < 60
```

**3. Negative Tests**
```python
def test_invalid_gpu_count(self):
    with self.assertRaises(ValidationError):
        create_diet_plan(gpu_count=0)
```

**4. Round-Trip Tests**
```python
def test_plan_lifecycle(self):
    """Test: create → calculate → approve → apply → verify"""
```

## Documentation Recommendations

**Add:**
- Architecture doc: How DIET works internally
- User guide: How to create and apply a plan
- API reference: Auto-generated from models

## Relevant CNCF Projects to Study

1. **Kubernetes**: CRD patterns, spec/status separation, reconciliation loops
2. **ArgoCD**: GitOps workflows, diff preview, continuous reconciliation
3. **Terraform**: Plan/apply pattern, state management
4. **Crossplane**: Composition patterns, high-level abstractions
5. **Helm**: Templating, values abstraction, DRY principles
6. **OPA**: Policy-as-code validation
7. **KusionStack**: Topology visualization UI (added CNCF Sandbox 2024)

## Alignment with Issue #114

This research supports the direction in #114 (moving away from coarse abstractions):

- **Declarative schemas** should use OpenAPI v3 validation with CEL
- **Port zones** align with Kubernetes' compositional approach (complex resources from primitives)
- **NetBox alignment** matches CNCF principle: use standard APIs, extend minimally

## Key CNCF Patterns Summary

| Pattern | Description | DIET Application |
|---------|-------------|------------------|
| **Desired State Reconciliation** | Spec (desired) vs Status (observed) | User inputs vs calculated topology |
| **Level-Triggered Reconciliation** | Continuously converge to desired state | Recalculate on spec changes |
| **Plan-Preview-Apply** | Review before execution | Preview topology before applying to NetBox |
| **Declarative Validation** | Schema + semantic + policy validation | OpenAPI schema + clean() + future OPA |
| **Composition** | High-level abstractions from primitives | GPUCluster = LeafSet + SpineSet + Cables |
| **Versioning** | Multiple API versions with conversion | v1beta1 → v1 with migration |

## Immediate Action Items

**High Priority:**
1. Add workflow states (draft/planned/approved/applied) to DIETPlan model
2. Implement diff/preview functionality
3. Separate spec fields from status fields in models
4. Add 256/512 GPU scale tests

**Medium Priority:**
5. Add performance benchmarks
6. Create architecture documentation
7. Add user guide for DIET workflows

**Future:**
8. GitOps integration (plans in Git, preview in PRs)
9. OPA policy validation
10. Topology visualization UI

## Sources

Full guide includes 60+ sources from:
- Kubernetes official docs (KEPs, CRD validation, versioning)
- CNCF project documentation (ArgoCD, Helm, Crossplane)
- 2025 blog posts and best practices
- CNCF sandbox project patterns

See `CNCF_PRACTICES_GUIDE.md` for complete source list with links.

---

**Research Date:** 2025-12-27
**Status:** Ready for review and prioritization
**Related Issues:** #82, #83, #84, #106, #114
