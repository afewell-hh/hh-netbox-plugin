# CNCF Design Patterns and Best Practices for DIET Module

**Research Date:** 2025-12-27
**Purpose:** Inform the design and implementation of the DIET (Design and Implementation Excellence Tools) module for hh-netbox-plugin

## Executive Summary

This guide synthesizes CNCF project patterns, declarative infrastructure best practices, and GitOps workflows to inform the development of DIET - a design-time tooling module for Hedgehog network fabric planning. The research covers how leading CNCF projects separate planning from execution, implement declarative specifications, and test at scale.

**Key Takeaways:**
- Kubernetes' desired-state reconciliation pattern is fundamental to declarative systems
- Separation of user inputs (spec) from calculated/observed values (status) is critical
- Preview/diff/apply workflows enable safe infrastructure changes
- OpenAPI v3 schema validation with CEL provides powerful declarative validation
- Testing at scale requires both unit tests and integration tests with real reconciliation loops
- Policy-as-code validates design-time decisions before execution

---

## 1. CNCF Project Design Patterns

### 1.1 Desired State vs Actual State (Kubernetes Pattern)

**Core Concept:**
Kubernetes implements a control loop where you define desired state (spec), the system observes actual state (status), and controllers continuously reconcile the difference.

**Key Principles:**
- **Spec and Status Separation**: Almost every Kubernetes object has `spec` (desired state) and `status` (observed state) fields
- **Level-Triggered Reconciliation**: Controllers don't react to individual events, but instead continuously compare current state to desired state
- **Self-Healing**: The reconciliation loop automatically corrects drift and recovers from failures
- **Idempotency**: Applying the same desired state multiple times produces the same result

**Implementation Pattern:**
```yaml
apiVersion: example.com/v1
kind: NetworkFabric
metadata:
  name: my-fabric
spec:
  # User-provided inputs - what you want
  leafCount: 128
  spineCount: 8
  leafPorts: 32
  uplinkPolicy: "max-bandwidth"
status:
  # System-calculated and observed - what you have
  observedGeneration: 5
  phase: "Ready"
  conditions:
    - type: "Valid"
      status: "True"
      reason: "AllConstraintsSatisfied"
  generatedDevices: 136
  totalConnections: 1024
```

**Reconciliation Loop Process:**
1. Watch for changes to desired state (spec updates)
2. Read current actual state from system
3. Compare desired vs actual
4. Take action to make actual match desired
5. Update observed state in status
6. Repeat continuously

**DIET Application:**
- User-provided DIET inputs go in `spec` (GPU counts, rack layout, policies)
- Calculated topology, cable plans, and validation results go in `status`
- Changes to spec trigger re-calculation of topology
- Status reflects the "planned state" - not yet applied to production

### 1.2 Declarative Specification Pattern

**Separation of Concerns:**

| Layer | Description | Example |
|-------|-------------|---------|
| **User Inputs** | What the user provides | "I need 128 GPUs" |
| **Derived Values** | Calculated from inputs | "This requires 16 leaf switches" |
| **Templates** | Reusable abstractions | "Standard 8-leaf cluster pattern" |
| **Generated Resources** | Final expanded output | Individual device/cable objects |

**Forward vs Backward Chaining:**
- **Forward Chaining**: When inputs change, automatically recalculate derived values (like Pega Declare Expressions)
- **Backward Chaining**: Calculate derived values only when needed/referenced
- **DIET Recommendation**: Use forward chaining - recalculate full topology when any input changes

**Referential Transparency:**
- Functions should produce the same output given the same input
- DIET calculations should be deterministic - same inputs always produce same topology
- No hidden state or external dependencies in generation logic

### 1.3 Helm: Templating and Abstraction Patterns

**DRY Principles (Don't Repeat Yourself):**
Helm addresses environment duplication through:

1. **Values-Based Abstraction**
   - All environment-specific config in `values.yaml`
   - Templates remain generic and reusable
   - Same template generates configs for dev/staging/prod

2. **Library Charts**
   - Reusable functions and templates
   - Shared across multiple charts
   - Example: Bitnami Common Chart provides consistent patterns

3. **Template Functions**
   - Go templates enable dynamic resource generation
   - Reduces boilerplate through loops and conditionals
   - Example: Generate N devices from a count parameter

**DIET Application:**
```yaml
# User provides compact, high-level spec
fabricSpec:
  type: "gpu-cluster"
  gpuCount: 128
  redundancy: "redundant"

# Template expands to full topology
# - Calculates leaf/spine counts
# - Generates device configs
# - Creates cable plan
# - Validates constraints
```

### 1.4 Terraform: Plan-Preview-Apply Workflow

**Core Workflow:**

1. **Write**: Define desired infrastructure in declarative config
2. **Plan**: Preview changes before applying (`terraform plan`)
3. **Apply**: Execute the planned changes (`terraform apply`)

**Key Benefits:**
- Review infrastructure changes before making them
- Prevent unintended modifications
- Enable team collaboration and approval processes
- Support CI/CD pipelines with manual gates

**Plan Output Shows:**
- Resources to be created (+)
- Resources to be modified (~)
- Resources to be destroyed (-)
- No changes (no symbol)

**DIET Application:**
- DIET Plan = preview generated topology
- Shows what devices/cables/IPs will be created
- Users review and approve before "applying" to production NetBox
- Plan can be saved, reviewed, diffed, approved in workflow

### 1.5 ArgoCD/GitOps: Diff and Reconciliation

**ArgoCD Diff Workflow:**

1. **Git as Source of Truth**: Desired state lives in Git
2. **Automatic Reconciliation**: ArgoCD checks cluster state every 3 minutes
3. **Diff Preview**: Before sync, view differences between Git and cluster
4. **Drift Detection**: Identify when live state diverges from Git

**Preview Environment Pattern:**
- Spin up ephemeral environment from PR branch
- Render diff of what would change
- Review changes before merging to main
- Tear down when PR closes

**argocd-diff-preview Tool:**
- Renders manifest changes on pull requests
- Spins up ephemeral cluster for accurate diff
- Integrates with CI/CD pipelines
- Shows exact changes before deployment

**DIET Application:**
- DIET specs stored in Git (infrastructure as code)
- Generate preview of topology changes in PR
- Show diff: "Adding 16 leaf switches, 512 cables"
- Approve/merge PR to update DIET plan
- Final "apply" step pushes to production NetBox

### 1.6 Crossplane: Composition and Abstraction

**Composition Pattern:**
- Define reusable infrastructure templates
- Compose multiple managed resources into higher-level abstractions
- Create platform APIs that hide complexity

**Key Concepts:**

1. **Composite Resource Definitions (XRDs)**: Custom APIs for infrastructure
2. **Composition Functions**: Dynamically generate resources
3. **Patch and Transform**: Modify configurations based on inputs
4. **Multi-cloud Abstractions**: Cloud-agnostic APIs

**DIET Application:**
- Create high-level abstractions like "GPU Cluster"
- Hide complexity of leaf/spine calculations
- Users work with business-level concepts, not low-level topology
- Example: `GPUCluster` composed of `LeafSet` + `SpineSet` + `CableBundle`

---

## 2. Declarative Specification Best Practices

### 2.1 Schema Design Principles

**OpenAPI v3 for Validation:**

Kubernetes CRDs use OpenAPI v3 schemas with powerful validation:

```yaml
spec:
  properties:
    gpuCount:
      type: integer
      minimum: 1
      maximum: 2048
      description: "Total number of GPUs in fabric"
    redundancy:
      type: string
      enum: ["non-redundant", "redundant", "redundant-shared"]
      default: "redundant"
    leafPorts:
      type: integer
      minimum: 16
      maximum: 64
      multipleOf: 8
  required:
    - gpuCount
```

**Validation Best Practices:**

1. **Use Standard OpenAPI Validations First**
   - `required`, `enum`, `minimum`, `maximum`
   - `minLength`, `maxLength`, `maxItems`, `maxProperties`
   - `pattern` for regex matching
   - String formats: `date-time`, `email`, `uri`

2. **Set Size Limits on Everything**
   - Always set `maxItems` on arrays
   - Always set `maxProperties` on maps
   - Always set `maxLength` on strings
   - Prevents resource exhaustion attacks

3. **Prevent Unknown Fields**
   - Use `additionalProperties: false`
   - Catches typos and invalid fields early
   - Forces explicit schema evolution

4. **Use Required Arrays for Mandatory Fields**
   ```yaml
   required:
     - gpuCount
     - rackLayout
   ```

5. **Provide Defaults for Optional Fields**
   ```yaml
   redundancy:
     type: string
     default: "redundant"
   ```

**Advanced Validation with CEL:**

Kubernetes 1.25+ supports Common Expression Language (CEL) for complex validation:

```yaml
validation:
  openAPIV3Schema:
    properties:
      spec:
        x-kubernetes-validations:
          - rule: "self.spineCount >= 2"
            message: "Spine count must be at least 2 for redundancy"
          - rule: "self.gpuCount <= self.leafCount * self.gpuPerLeaf"
            message: "GPU count exceeds capacity"
```

**Transition Rules:**

Compare old state vs new state during updates:

```yaml
x-kubernetes-validations:
  - rule: "self.gpuCount >= oldSelf.gpuCount"
    message: "Cannot reduce GPU count - scale down not supported"
```

**DIET Application:**
- Define comprehensive OpenAPI schema for DIET specs
- Use CEL for cross-field validation (e.g., GPU count vs rack capacity)
- Validate transition rules (prevent invalid spec changes)
- Provide clear error messages when validation fails

### 2.2 Versioning and Migration

**CRD Versioning Strategy:**

Kubernetes supports multiple versions of the same resource:

```yaml
versions:
  - name: v1
    served: true
    storage: true  # Current storage version
  - name: v1beta1
    served: true   # Still accepted, converted to v1
    storage: false
```

**Hub and Spoke Pattern:**
- One version is the "storage version" (hub)
- All other versions are "spokes"
- Conversion must be lossless (round-trippable)

**Conversion Webhook:**
- Automatic conversion between versions
- API server calls webhook for any version conversion
- Supports both upgrade and downgrade

**Migration Best Practices:**

1. **Never Make Breaking Changes**
   - Don't remove required fields
   - Don't rename fields without deprecation
   - Don't change field types incompatibly

2. **Deprecation Process**
   - Add new version (v2) while keeping old (v1)
   - Serve both versions with conversion
   - Mark v1 as deprecated in docs
   - Migrate existing resources to v2
   - Eventually stop serving v1

3. **Storage Version Migration**
   - Update CRD to new storage version
   - Trigger StorageVersionMigration to rewrite existing objects
   - Ensures all stored objects use new format

**DIET Application:**
- Start with v1beta1 during initial development
- Promote to v1 when API stabilizes
- Support multiple versions with conversion webhooks
- Migrate existing DIET plans when schema changes

### 2.3 User Inputs vs Calculated Values

**Separation Pattern:**

| Type | Field Location | Examples | Mutability |
|------|----------------|----------|------------|
| **User Inputs** | `spec.*` | gpuCount, rackLayout, policies | User editable |
| **Calculated Values** | `status.*` | leafCount, spineCount, totalCost | System managed |
| **Derived Inputs** | `spec.calculated.*` | May be auto-populated but user-editable | Semi-automatic |

**Best Practices:**

1. **Never Put Calculated Values in Spec**
   - Spec is user-controlled, status is system-controlled
   - Clear ownership prevents conflicts
   - Makes it obvious what user can change

2. **Make Calculations Visible in Status**
   ```yaml
   status:
     topology:
       leafSwitches: 16
       spineSwitches: 8
       totalPorts: 512
     cabling:
       totalCables: 256
       fiberCount: 512
   ```

3. **Support Both Manual and Automatic Modes**
   - Auto mode: System calculates optimal topology
   - Manual mode: User overrides specific values
   - Hybrid: System suggests, user reviews and modifies

4. **Validate Consistency**
   - If user provides both high-level goals and low-level details, validate they're consistent
   - Example: If user specifies both gpuCount and leafCount, ensure leafCount is sufficient

**DIET Application:**
```yaml
spec:
  # User inputs - what they want
  mode: "automatic"  # or "manual"
  gpuCount: 128
  redundancy: "redundant"

  # Optional user overrides (when mode=manual)
  overrides:
    leafCount: 16  # User can override calculation

status:
  # System calculations
  calculatedTopology:
    leafCount: 16
    spineCount: 8
    gpuPerLeaf: 8
  validation:
    status: "Valid"
    warnings:
      - "Using non-standard leaf count"
```

---

## 3. Planning Tool Patterns

### 3.1 Preview/Plan Before Apply

**Universal Pattern Across Tools:**

| Tool | Plan Command | Apply Command | Diff Command |
|------|-------------|---------------|--------------|
| Terraform | `terraform plan` | `terraform apply` | Built into plan |
| ArgoCD | `argocd app diff` | `argocd app sync` | `argocd app diff` |
| Kubectl | `kubectl diff` | `kubectl apply` | `kubectl diff` |
| Helm | `helm diff upgrade` | `helm upgrade` | Via plugin |
| Kustomize | `kustomize build` | `kubectl apply -k` | `kubectl diff -k` |

**Plan Output Requirements:**

1. **Show What Will Change**
   - Additions (green/+)
   - Modifications (yellow/~)
   - Deletions (red/-)
   - No changes (-)

2. **Provide Details**
   - Exactly what fields will change
   - Old value vs new value
   - Resource names and types

3. **Calculate Impact**
   - Number of resources affected
   - Estimated cost/time
   - Risk level

4. **Enable Review Workflow**
   - Save plan to file
   - Share for review
   - Require approval before apply

**DIET Application:**

```bash
# Generate plan
hh-netbox diet plan create --name="128-gpu-cluster" --spec=fabric.yaml

# Preview changes
hh-netbox diet plan show --plan-id=123
# Output:
# Will create:
#   + 16 LeafSwitch devices
#   + 8 SpineSwitch devices
#   + 256 Cables
#   + 512 IP addresses
# Will modify:
#   ~ 2 existing devices (add interfaces)

# Diff against current production
hh-netbox diet plan diff --plan-id=123 --compare-to=production
# Shows exactly what's different from current NetBox state

# Apply plan to production
hh-netbox diet plan apply --plan-id=123
```

### 3.2 Validation at Design Time

**Shift-Left Validation:**

Catch errors as early as possible in the workflow:

```
User Input → Schema Validation → Business Rules → Constraint Checking → Preview → Apply
     ↓              ↓                   ↓                  ↓               ↓        ↓
  Typos      Field types      Policy compliance    Resource limits    Review    Execute
```

**Validation Layers:**

1. **Schema Validation** (OpenAPI/JSON Schema)
   - Field types, formats, ranges
   - Required fields, enum values
   - Structural correctness

2. **Semantic Validation** (CEL/Webhooks)
   - Cross-field constraints
   - Business rules
   - Complex dependencies

3. **Policy Validation** (OPA/Rego)
   - Security policies
   - Compliance requirements
   - Cost/capacity constraints

4. **Constraint Validation** (Custom Logic)
   - Physical constraints (rack space, power, cooling)
   - Network constraints (bandwidth, latency)
   - Resource availability

**Example Validation Pipeline:**

```yaml
# 1. Schema validation (OpenAPI)
gpuCount: 128  # ✓ Type: integer, within range

# 2. Semantic validation (CEL)
rule: "self.gpuCount % self.gpuPerLeaf == 0"  # ✓ Divisible

# 3. Policy validation (OPA)
deny[msg] {
  input.spec.gpuCount > 256
  msg = "Exceeds max GPU limit per fabric"
}  # ✓ Passes

# 4. Constraint validation (Python)
validate_rack_capacity(
  rack_count=rack_layout.count,
  device_count=calculated.leafCount + calculated.spineCount
)  # ✓ Fits in racks
```

**DIET Application:**
- Layer 1: Django model field validation + OpenAPI schema
- Layer 2: Model clean() methods + custom validators
- Layer 3: OPA policies for cost/compliance (future)
- Layer 4: Topology validation logic in update_plan_calculations

### 3.3 Scale Generation Patterns

**Generating Thousands of Resources from Compact Specs:**

**Problem**: User wants 128-GPU fabric = hundreds of devices and thousands of cables
**Solution**: Templating + loops + calculations

**Patterns:**

1. **Count-Based Generation**
   ```yaml
   spec:
     leafCount: 16

   # Generates 16 leaf switch objects
   for i in range(spec.leafCount):
     create_device(name=f"leaf-{i+1:02d}")
   ```

2. **Topology-Based Generation**
   ```yaml
   spec:
     topology: "fat-tree"
     layers: 3
     radix: 32

   # Algorithm generates full fat-tree topology
   ```

3. **Template Expansion**
   ```yaml
   template: "gpu-cluster"
   parameters:
     gpuCount: 128

   # Template expands to full device/cable list
   ```

**Deterministic Generation:**

Key requirement: **Same input → same output** (every time)

- Use deterministic naming (leaf-01, leaf-02, not random UUIDs)
- Use deterministic ordering (sorted by name)
- Use deterministic algorithms (same calculation every time)
- No randomness, no timestamps in generated names
- Enables diff between versions

**DIET Application:**
- `determine_optimal_breakout()` calculates topology from GPU count
- `update_plan_calculations()` generates full resource list
- All calculations are deterministic
- Tests verify same input produces same output

### 3.4 Reconciliation and Drift Detection

**Continuous Reconciliation Pattern:**

```python
def reconcile(desired_state, actual_state):
    """
    Compare desired vs actual, take corrective action.
    """
    diff = calculate_diff(desired_state, actual_state)

    if diff.is_empty():
        return "In Sync"

    for change in diff.changes:
        apply_change(change)

    update_status(observed_state=actual_state)
    return "Reconciled"
```

**Drift Detection:**

Identify when actual state diverges from desired state:

- Kubernetes: Controllers detect drift and auto-correct
- ArgoCD: Shows "OutOfSync" status, can auto-sync
- Terraform: `terraform plan` shows drift from last apply
- NetBox: No built-in drift detection (manual comparison)

**DIET Application (Future):**

```python
# Periodically compare DIET plan vs production NetBox
diff = compare_states(
    desired=diet_plan.get_calculated_topology(),
    actual=netbox_production.query_topology()
)

if diff.has_drift:
    alert("Production NetBox has drifted from approved DIET plan")
    show_diff(diff)
    offer_reconciliation()
```

---

## 4. Documentation & Testing Standards

### 4.1 Design Document Patterns (KEP/RFC)

**Kubernetes Enhancement Proposal (KEP) Structure:**

Effective design documents include:

1. **Metadata**
   - KEP number, title, authors
   - Status (provisional, implementable, implemented)
   - Dates (creation, last update)

2. **Summary**
   - One-paragraph overview
   - Target user personas
   - Key goals

3. **Motivation**
   - What problem does this solve?
   - Why is this important?
   - User stories / use cases

4. **Proposal**
   - Detailed design
   - API changes (if applicable)
   - Implementation details

5. **Alternatives Considered**
   - What other approaches were evaluated?
   - Why was this approach chosen?

6. **Risks and Mitigations**
   - What could go wrong?
   - How do we mitigate risks?

7. **Test Plan**
   - Unit tests
   - Integration tests
   - Performance tests
   - How will we know it works?

8. **Graduation Criteria**
   - Alpha: initial implementation
   - Beta: well-tested, documented
   - GA: production-ready, stable API

**Production Readiness Review:**

Modern KEPs include detailed production readiness review:
- Observability (metrics, logs, traces)
- Scalability testing results
- Rollout/rollback plan
- Monitoring requirements
- Troubleshooting guides

**DIET Application:**
- Create design documents for major features (GitHub issues #82, #83, #84)
- Include all KEP sections
- Review and approve before implementation
- Update as design evolves

### 4.2 Testing Strategies

**Test Pyramid for Infrastructure Tools:**

```
           /\
          /  \    E2E Tests (Few)
         /____\   - Full workflow: input → plan → apply
        /      \  - Real NetBox instance
       /        \ - Slow, expensive, fragile
      /__________\
     /            \  Integration Tests (Many)
    /              \ - API calls, database queries
   /                \ - Test containers, fixtures
  /                  \ - Medium speed, good coverage
 /____________________\
/                      \  Unit Tests (Most)
--------------------------
 - Pure functions         - Fast, isolated
 - Model validation       - Test edge cases
 - Calculation logic      - High coverage
```

**Kubernetes Operator Testing Patterns:**

1. **Unit Tests** (Fastest)
   - Test pure functions, calculations
   - Mock external dependencies
   - Framework: Python unittest, pytest

2. **Integration Tests** (EnvTest Pattern)
   - Spin up lightweight Kubernetes API
   - Test controllers with real API
   - Framework: Testcontainers, K3s

3. **End-to-End Tests** (Slowest)
   - Test full workflow in real cluster
   - Validate user scenarios
   - Framework: KUTTL (KUbernetes Test TooL)

**Scale Testing:**

For systems that generate many resources:

1. **Volumetric Testing**
   - Test with small inputs (8 GPUs)
   - Test with medium inputs (128 GPUs)
   - Test with large inputs (2048 GPUs)
   - Measure performance, memory usage

2. **Boundary Testing**
   - Minimum values (1 GPU)
   - Maximum values (max supported)
   - Edge cases (odd numbers, primes)

3. **Performance Testing**
   - k6 Operator for distributed load testing
   - Grafana for visualization
   - Measure latency, throughput

**DIET Application:**

Current testing approach aligns well with best practices:

✓ Integration tests in `test_topology_planning/`
✓ Test real Django views and forms
✓ Test validation and error handling
✓ Test multiple scale scenarios (8, 128 GPUs)

Recommendations:
- Add more volumetric tests (256, 512, 1024 GPUs)
- Add performance benchmarks (time to generate 2048-GPU fabric)
- Add negative tests (invalid inputs, constraint violations)
- Add round-trip tests (create → read → update → delete)

### 4.3 Documentation Standards

**CNCF Documentation Requirements:**

1. **User Documentation**
   - Getting started guide
   - Tutorials (step-by-step)
   - How-to guides (task-focused)
   - Reference (API, CLI, config)

2. **Developer Documentation**
   - Architecture overview
   - Development setup
   - Contributing guide
   - Testing guide

3. **API Documentation**
   - Auto-generated from code (OpenAPI/Swagger)
   - Examples for each endpoint
   - Error codes and meanings

4. **Operator/Admin Documentation**
   - Installation guide
   - Configuration reference
   - Troubleshooting guide
   - Upgrade procedures

**DIET Application:**

Current documentation (AGENTS.md/CLAUDE.md) is strong.

Suggested additions:
- User guide: How to create a DIET plan
- Architecture doc: How DIET calculations work
- API reference: Auto-generated from Django models
- Troubleshooting: Common errors and solutions

---

## 5. Relevant CNCF Projects

### 5.1 Network-Related CNCF Projects

**Cilium** (Graduated/Incubating)
- eBPF-based networking and security
- Multi-cluster connectivity (Cluster Mesh)
- Network policy enforcement
- **Relevance to DIET**: Network fabric connectivity patterns

**Network Service Mesh** (Sandbox)
- L2/L3 network service management
- Multi-cluster networking
- **Relevance to DIET**: Service-oriented network modeling

**Kube-OVN** (Sandbox)
- Scalable network fabric via Open vSwitch
- Integration with OVN (Open Virtual Network)
- **Relevance to DIET**: Large-scale network fabric design

**Antrea** (Sandbox)
- Kubernetes-native networking
- Network policy implementation
- **Relevance to DIET**: Policy-based network configuration

### 5.2 Infrastructure & Topology Projects

**KusionStack/Kusion** (Sandbox)
- Added to CNCF Sandbox in 2024 H2
- v0.14.0 (Jan 2025) introduced Developer Portal
- **Topology Visualization**: Web UI visualizes application resource topology
- **Relevance to DIET**: UI pattern for topology visualization

**Crossplane** (Incubating)
- Infrastructure composition and abstraction
- Multi-cloud resource management
- **Relevance to DIET**: Composition pattern for complex infrastructure

**Kubernetes** (Graduated)
- Topology-aware scheduling (Kueue)
- Zone/rack/node affinity
- **Relevance to DIET**: Hardware topology awareness

### 5.3 Data Center Observability

**OpenTelemetry** (Incubating)
- November 2025 CNCF blog: "Bringing data center observability into the cloud native world"
- OpenTelemetry Collector standardizes diverse signals
- Hardware data via SNMP, Redfish protocols
- **Relevance to DIET**: Integration with hardware monitoring

**NetBox** (Not CNCF, but widely used)
- Mentioned in CNCF ecosystem discussions
- Network source of truth (IPAM + DCIM)
- **Relevance to DIET**: DIET extends NetBox for planning workflows

### 5.4 GitOps & Deployment

**Argo Project** (Incubating)
- ArgoCD: Declarative GitOps
- Argo Workflows: Orchestration
- **Relevance to DIET**: GitOps pattern for DIET specs

**Flux** (Incubating)
- GitOps continuous delivery
- Multi-tenancy
- **Relevance to DIET**: Alternative GitOps implementation

**Helm** (Graduated)
- Package manager for Kubernetes
- Templating engine
- **Relevance to DIET**: Template patterns for DIET spec expansion

---

## 6. Recommendations for DIET

### 6.1 Architectural Patterns to Adopt

**1. Spec/Status Separation**

Current DIET models should clearly separate user inputs from calculated values:

```python
class DIETPlan(models.Model):
    # User inputs (spec)
    name = models.CharField(max_length=100)
    gpu_count = models.IntegerField()
    redundancy_policy = models.CharField(
        choices=[
            ('non-redundant', 'Non-Redundant'),
            ('redundant', 'Redundant'),
            ('redundant-shared', 'Redundant Shared'),
        ]
    )

    # Calculated values (status) - could be separate model or JSON field
    calculated_leaf_count = models.IntegerField(null=True, blank=True)
    calculated_spine_count = models.IntegerField(null=True, blank=True)
    last_calculated = models.DateTimeField(null=True, blank=True)

    # Status conditions
    validation_status = models.CharField(
        choices=[
            ('pending', 'Pending'),
            ('valid', 'Valid'),
            ('invalid', 'Invalid'),
            ('error', 'Error'),
        ]
    )
    validation_message = models.TextField(blank=True)
```

**2. Declarative Validation**

Use Django's built-in validation plus custom validators:

```python
from django.core.validators import MinValueValidator, MaxValueValidator

class DIETPlan(models.Model):
    gpu_count = models.IntegerField(
        validators=[
            MinValueValidator(1, message="Must have at least 1 GPU"),
            MaxValueValidator(2048, message="Exceeds maximum supported GPUs"),
        ],
        help_text="Total number of GPUs in fabric (1-2048)"
    )

    def clean(self):
        """Cross-field validation (like CEL)"""
        super().clean()

        # Validate consistency
        if self.calculated_leaf_count:
            max_gpus = self.calculated_leaf_count * 8  # Max 8 GPUs per leaf
            if self.gpu_count > max_gpus:
                raise ValidationError(
                    f"GPU count {self.gpu_count} exceeds capacity "
                    f"with {self.calculated_leaf_count} leaves (max {max_gpus})"
                )
```

**3. Plan-Preview-Apply Workflow**

Add explicit workflow states:

```python
class DIETPlan(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PLANNED = 'planned'
    STATUS_APPROVED = 'approved'
    STATUS_APPLIED = 'applied'
    STATUS_FAILED = 'failed'

    status = models.CharField(
        max_length=20,
        choices=[
            (STATUS_DRAFT, 'Draft - editing in progress'),
            (STATUS_PLANNED, 'Planned - calculations complete, ready for review'),
            (STATUS_APPROVED, 'Approved - ready to apply'),
            (STATUS_APPLIED, 'Applied - pushed to production NetBox'),
            (STATUS_FAILED, 'Failed - error during apply'),
        ],
        default=STATUS_DRAFT
    )

    def calculate(self):
        """Generate plan (terraform plan equivalent)"""
        update_plan_calculations(self)
        self.status = self.STATUS_PLANNED
        self.save()

    def approve(self, user):
        """Approve plan for application"""
        if self.status != self.STATUS_PLANNED:
            raise ValidationError("Can only approve planned designs")
        self.status = self.STATUS_APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()

    def apply(self):
        """Apply plan to production NetBox (terraform apply equivalent)"""
        if self.status != self.STATUS_APPROVED:
            raise ValidationError("Can only apply approved designs")

        try:
            # Create devices, cables, IPs in production NetBox
            create_production_resources(self)
            self.status = self.STATUS_APPLIED
        except Exception as e:
            self.status = self.STATUS_FAILED
            self.last_error = str(e)
        finally:
            self.save()
```

**4. Diff Functionality**

Show what will change when applying a plan:

```python
def generate_diff(plan):
    """
    Show what will be created/modified/deleted when applying plan.
    Returns structured diff like terraform plan output.
    """
    diff = {
        'additions': [],
        'modifications': [],
        'deletions': [],
    }

    # Compare planned topology vs current NetBox state
    planned_devices = plan.get_calculated_devices()
    current_devices = Device.objects.filter(site=plan.site)

    # Find additions
    for device in planned_devices:
        if not current_devices.filter(name=device.name).exists():
            diff['additions'].append({
                'type': 'device',
                'name': device.name,
                'role': device.role,
            })

    # Find deletions (if plan includes decom)
    # ...

    return diff
```

**5. Policy as Code Integration (Future)**

Add OPA policy validation:

```python
# policies/diet_policies.rego
package diet

# Deny if GPU count exceeds budget
deny[msg] {
    input.spec.gpuCount > 256
    input.metadata.costCenter != "research"
    msg = "GPU count exceeds limit for non-research cost centers"
}

# Require redundancy for production
deny[msg] {
    input.metadata.environment == "production"
    input.spec.redundancy == "non-redundant"
    msg = "Production environments must use redundant topology"
}
```

### 6.2 Testing Recommendations

**1. Expand Integration Test Coverage**

Current tests are good, but could add:

```python
# test_topology_planning/test_scale.py

class DIETScaleTestCase(TestCase):
    """Test DIET plan generation at various scales"""

    def test_8_gpu_fabric(self):
        """Minimum viable fabric"""
        plan = create_diet_plan(gpu_count=8)
        self.assertEqual(plan.calculated_leaf_count, 1)

    def test_128_gpu_fabric(self):
        """Standard size (current test)"""
        # Already have this
        pass

    def test_256_gpu_fabric(self):
        """Large fabric"""
        plan = create_diet_plan(gpu_count=256)
        self.assertLessEqual(plan.calculated_leaf_count, 32)

    def test_1024_gpu_fabric(self):
        """Very large fabric"""
        plan = create_diet_plan(gpu_count=1024)
        # Should complete in reasonable time
        self.assertLess(plan.calculation_time_seconds, 60)

    def test_deterministic_generation(self):
        """Same input produces same output"""
        plan1 = create_diet_plan(gpu_count=128, seed=42)
        plan2 = create_diet_plan(gpu_count=128, seed=42)

        # Should generate identical topologies
        self.assertEqual(
            plan1.get_device_names(),
            plan2.get_device_names()
        )
```

**2. Add Performance Benchmarks**

```python
# test_topology_planning/test_performance.py

class DIETPerformanceTestCase(TestCase):
    """Benchmark DIET plan generation performance"""

    def test_calculation_performance(self):
        """Ensure calculations complete in reasonable time"""
        sizes = [8, 16, 32, 64, 128, 256, 512]

        for gpu_count in sizes:
            start = time.time()
            plan = create_diet_plan(gpu_count=gpu_count)
            duration = time.time() - start

            # Should scale sub-linearly
            max_time = 0.1 * math.log2(gpu_count)
            self.assertLess(
                duration,
                max_time,
                f"{gpu_count} GPUs took {duration}s (max {max_time}s)"
            )
```

**3. Add Negative Tests**

```python
# test_topology_planning/test_validation.py

class DIETValidationTestCase(TestCase):
    """Test error handling and validation"""

    def test_invalid_gpu_count(self):
        """Reject invalid GPU counts"""
        with self.assertRaises(ValidationError):
            create_diet_plan(gpu_count=0)

        with self.assertRaises(ValidationError):
            create_diet_plan(gpu_count=-1)

        with self.assertRaises(ValidationError):
            create_diet_plan(gpu_count=10000)  # Exceeds max

    def test_incompatible_policy(self):
        """Catch policy mismatches"""
        with self.assertRaises(ValidationError):
            create_diet_plan(
                gpu_count=128,
                leaf_policy='dedicated',
                spine_policy='shared'  # Incompatible
            )

    def test_insufficient_rack_space(self):
        """Validate physical constraints"""
        plan = create_diet_plan(
            gpu_count=1024,
            racks=[small_rack]  # Not enough space
        )

        with self.assertRaises(ValidationError):
            plan.validate_constraints()
```

**4. Add Round-Trip Tests**

```python
def test_plan_lifecycle(self):
    """Test full workflow: create → update → apply → verify"""

    # Create plan
    plan = DIETPlan.objects.create(
        name="Test Fabric",
        gpu_count=128,
    )

    # Calculate topology
    plan.calculate()
    self.assertEqual(plan.status, DIETPlan.STATUS_PLANNED)

    # Approve plan
    plan.approve(user=admin_user)
    self.assertEqual(plan.status, DIETPlan.STATUS_APPROVED)

    # Apply to production (in test DB)
    plan.apply()
    self.assertEqual(plan.status, DIETPlan.STATUS_APPLIED)

    # Verify resources created
    devices = Device.objects.filter(
        tags__name='diet-plan-{plan.id}'
    )
    self.assertEqual(devices.count(), plan.calculated_device_count)
```

### 6.3 Documentation Recommendations

**1. Add Architecture Documentation**

Create `docs/architecture/DIET.md`:

```markdown
# DIET Architecture

## Overview
DIET (Design and Implementation Excellence Tools) implements a
plan-preview-apply workflow for network fabric design.

## Components

### Models
- DIETPlan: User inputs and calculated topology
- LeafSpineDesign: Topology parameters
- CableDesign: Cabling requirements

### Calculation Engine
- `determine_optimal_breakout()`: GPU count → topology
- `update_plan_calculations()`: Generate full resource list
- Validation: Constraint checking

### Workflow States
1. Draft → user editing
2. Planned → calculations complete
3. Approved → ready to apply
4. Applied → in production

## Design Patterns

### Spec/Status Separation
User inputs in spec fields, calculations in status fields.

### Deterministic Generation
Same input always produces same output.

### Declarative Validation
Schema validation + semantic validation + constraints.
```

**2. Add User Guide**

Create `docs/user-guide/DIET.md`:

```markdown
# DIET User Guide

## Creating a Fabric Plan

1. Navigate to DIET → Plans → Add
2. Enter fabric name and GPU count
3. Select redundancy policy
4. Click "Calculate Topology"
5. Review generated topology in preview
6. If satisfied, click "Approve"
7. When ready, click "Apply to Production"

## Understanding the Preview

The preview shows:
- Leaf switches (how many, what model)
- Spine switches (how many, what model)
- Cables (count, types, connections)
- IP addresses (subnets, assignments)

## Modifying a Plan

Plans in "Draft" state can be edited.
Plans in "Planned" state can be recalculated.
Plans in "Approved" or "Applied" state are read-only.
```

**3. Add API Reference**

Use Django REST Framework's automatic schema generation:

```python
# Add to urls.py
from rest_framework.schemas import get_schema_view

schema_view = get_schema_view(
    title="DIET API",
    description="API for DIET topology planning",
    version="1.0.0"
)

urlpatterns = [
    path('api/schema/', schema_view),
    path('api/docs/', include('rest_framework.urls')),
]
```

### 6.4 Future Enhancements

**1. GitOps Integration**

Store DIET plans in Git:

```yaml
# plans/production/fabric-01.yaml
apiVersion: diet.hedgehog.com/v1
kind: FabricPlan
metadata:
  name: fabric-01
  namespace: production
spec:
  gpuCount: 128
  redundancy: redundant
  site: dc1
  racks:
    - rack-01
    - rack-02
```

CI/CD pipeline:
- On PR: Generate plan, show diff in PR comment
- On merge: Apply approved plan to production

**2. Policy as Code**

Add OPA policy validation:

```python
def validate_policy(plan):
    """Validate plan against OPA policies"""
    policy_engine = OPA(policies_dir='policies/')

    result = policy_engine.evaluate(
        input={
            'spec': plan.get_spec(),
            'metadata': {
                'environment': plan.environment,
                'costCenter': plan.cost_center,
            }
        }
    )

    if result.violations:
        raise ValidationError(result.violations)
```

**3. Drift Detection**

Periodically compare DIET plan vs production:

```python
def detect_drift(plan):
    """Compare plan vs actual production state"""
    planned = plan.get_calculated_topology()
    actual = query_production_netbox(plan.site)

    diff = compare_topologies(planned, actual)

    if diff.has_differences:
        send_alert(
            title=f"Drift detected in {plan.name}",
            diff=diff.summary()
        )
```

**4. Cost Estimation**

Add cost calculation to plans:

```python
class DIETPlan(models.Model):
    estimated_hardware_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    estimated_power_watts = models.IntegerField(
        null=True,
        blank=True
    )

    def calculate_costs(self):
        """Estimate costs based on BOM"""
        cost = 0
        power = 0

        for device in self.get_calculated_devices():
            cost += device.device_type.purchase_price or 0
            power += device.device_type.power_draw or 0

        self.estimated_hardware_cost = cost
        self.estimated_power_watts = power
        self.save()
```

**5. Topology Visualization**

Add interactive topology diagram (like KusionStack):

```python
def get_topology_graph(plan):
    """Generate graph data for visualization"""
    nodes = []
    edges = []

    # Add leaf nodes
    for leaf in plan.get_leaf_switches():
        nodes.append({
            'id': leaf.name,
            'type': 'leaf',
            'label': leaf.name,
        })

    # Add spine nodes
    for spine in plan.get_spine_switches():
        nodes.append({
            'id': spine.name,
            'type': 'spine',
            'label': spine.name,
        })

    # Add edges (cables)
    for cable in plan.get_cables():
        edges.append({
            'source': cable.termination_a.device.name,
            'target': cable.termination_b.device.name,
            'label': cable.type,
        })

    return {'nodes': nodes, 'edges': edges}
```

Frontend (using vis.js or cytoscape.js):
```javascript
// Render topology graph
const graph = new vis.Network(
    container,
    topologyData,
    options
);
```

---

## 7. Summary & Action Items

### Key Takeaways

1. **Spec/Status Separation**: Adopt Kubernetes pattern of separating user inputs (spec) from calculated values (status)

2. **Plan-Preview-Apply**: Implement explicit workflow states (draft → planned → approved → applied)

3. **Declarative Validation**: Use schema validation + semantic validation + constraints

4. **Deterministic Generation**: Ensure same inputs produce same outputs

5. **Testing at Scale**: Expand tests to cover larger scenarios and performance benchmarks

6. **Documentation**: Add architecture docs, user guide, and API reference

### Immediate Actions

**High Priority:**

- [ ] Refactor models to clearly separate spec vs status fields
- [ ] Add workflow states (draft, planned, approved, applied)
- [ ] Implement diff/preview functionality
- [ ] Expand integration tests to 256, 512, 1024 GPU scenarios
- [ ] Add performance benchmarks
- [ ] Document DIET architecture

**Medium Priority:**

- [ ] Add more negative tests (validation, errors)
- [ ] Add round-trip tests (full lifecycle)
- [ ] Create user guide documentation
- [ ] Generate OpenAPI schema for API docs
- [ ] Add cost estimation to plans

**Future/Nice-to-Have:**

- [ ] GitOps integration (plans in Git)
- [ ] OPA policy validation
- [ ] Drift detection (plan vs production)
- [ ] Topology visualization UI
- [ ] Multi-version support with conversion webhooks

### Projects to Study Further

1. **Kubernetes**: CRD patterns, validation, versioning
2. **ArgoCD**: GitOps workflows, diff preview, reconciliation
3. **Terraform**: Plan/apply pattern, state management
4. **Crossplane**: Composition patterns, abstraction layers
5. **Helm**: Templating, values abstraction, library charts
6. **KusionStack**: Topology visualization UI
7. **OPA**: Policy as code validation

---

## Sources

### Kubernetes & CRDs
- [Kubernetes CRD Best Practices](https://medium.com/@serishahid17/what-are-crds-in-kubernetes-and-how-to-use-manage-and-optimize-them-76d5ff8d4fe8)
- [CRD Validation - Kubebuilder](https://book.kubebuilder.io/reference/markers/crd-validation)
- [OpenAPI v3 Schema Validation](https://kubernetes.io/blog/2023/04/24/openapi-v3-field-validation-ga/)
- [CRD Versioning](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definition-versioning/)
- [Controllers and Reconciliation](https://kubernetes.io/docs/concepts/architecture/controller/)
- [Desired State Systems](https://branislavjenco.github.io/desired-state-systems/)

### Enhancement Proposals & Design Docs
- [Kubernetes Enhancement Proposals (KEPs)](https://kubernetes.io/blog/2025/01/21/sig-architecture-enhancements/)
- [KEP Process](https://github.com/kubernetes/enhancements/blob/master/keps/sig-architecture/0000-kep-process/README.md)
- [CNCF Design Proposals Template](https://github.com/cncf/project-template/blob/main/DESIGN-PROPOSALS.md)
- [CNCF Project Template](https://github.com/cncf/project-template)

### GitOps & ArgoCD
- [ArgoCD Diff Preview](https://github.com/dag-andersen/argocd-diff-preview)
- [Understanding ArgoCD Reconciliation](https://docs.rafay.co/blog/2025/08/04/understanding-argocd-reconciliation-how-it-works-why-it-matters-and-best-practices/)
- [GitOps Environment Modeling](https://codefresh.io/blog/how-to-model-your-gitops-environments-and-promote-releases-between-them/)
- [Preview Environments with GitOps](https://www.loft.sh/blog/implementing-preview-environments-with-gitops-in-kubernetes)

### Helm & Templating
- [Helm Best Practices (2025)](https://carlosneto.dev/blog/2025/2025-02-25-helm-best-practices/)
- [Helm Chart Template Guide](https://helm.sh/docs/chart_template_guide/)
- [Helm Chart Best Practices - Templates](https://helm.sh/docs/chart_best_practices/templates/)

### Testing
- [Kubernetes Operator Testing Patterns](https://seifrajhi.github.io/blog/testing-kubernetes-clusters-and-components/)
- [Testing Kubernetes Operators with EnvTest](https://www.infracloud.io/blogs/testing-kubernetes-operator-envtest/)
- [Testcontainers for Kubernetes Operators](https://www.docker.com/blog/testcontainers-the-simplest-way-to-test-kubernetes-operators/)
- [Kubebuilder Writing Tests](https://book.kubebuilder.io/cronjob-tutorial/writing-tests)

### Validation & Policy
- [Kubernetes Admission Webhooks (2025)](https://medium.com/@DynamoDevOps/kubernetes-admission-control-how-mutating-and-validating-webhooks-actually-secure-your-cluster-0a2121a57b38)
- [ValidatingAdmissionPolicy GA](https://kubernetes.io/blog/2024/04/24/validating-admission-policy-ga/)
- [OPA & Terraform Policy Guide (2025)](https://policyascode.dev/guides/opa-terraform-policy-guide/)
- [Policy as Code with OPA](https://www.env0.com/blog/how-policy-as-code-enhances-infrastructure-governance-with-open-policy-agent-opa)

### Infrastructure as Code
- [IaC Testing Strategies](https://www.techtarget.com/searchitoperations/tip/Infrastructure-as-code-testing-strategies-to-validate-a-deployment)
- [IaC Validation](https://www.prancer.io/infrastructure-as-code-validation/)
- [Infrastructure Testing 2025](https://codecondo.com/infrastructure-testing-tools-engineer-must-know-2025/)
- [Idempotency in Infrastructure](https://shahadarsh.com/2020/07/12/principles-patterns-and-practices-for-effective-infrastructure-as-code/)

### CNCF Network Projects
- [7 CNCF Projects for Cloud-Native Networks](https://cloudnativenow.com/features/7-cncf-projects-for-building-cloud-native-networks/)
- [Cilium & SD-WAN Network Fabric](https://www.cncf.io/blog/2025/10/25/connecting-distributed-kubernetes-with-cilium-and-sd-wan-building-an-intelligent-network-fabric/)
- [CNCF Sandbox Projects 2025](https://palark.com/blog/cncf-sandbox-2025-jan/)
- [Data Center Observability](https://www.cncf.io/blog/2025/11/04/bringing-data-center-observability-into-the-cloud-native-world/)

### NetBox & Network Source of Truth
- [NetBox Network Source of Truth](https://netboxlabs.com/products/netbox/)
- [Network Automation Architecture](https://netboxlabs.com/blog/network-automation-architecture/)
- [Using NetBox for Ansible](https://www.ansible.com/blog/using-netbox-for-ansible-source-of-truth)
- [NetBox GitHub](https://github.com/netbox-community/netbox)

### Operator Patterns
- [Kubebuilder Good Practices](https://book.kubebuilder.io/reference/good-practices)
- [CNCF Operator White Paper](https://tag-app-delivery.cncf.io/whitepapers/operator/)
- [Status Conditions Pattern](https://book-v1.book.kubebuilder.io/basics/status_subresource)
- [Advanced Kubernetes Operators](https://medium.com/swlh/advanced-kubernetes-operators-development-988edad5f58a)

---

**Document Version:** 1.0
**Last Updated:** 2025-12-27
**Next Review:** When implementing major DIET features

**Feedback:** Please comment on this document or create issues for specific patterns to adopt.
