# Claude Code Configuration - CNOC Production System

## 🎯 Project: CNOC (Cloud NetOps Command)
**FORGE Methodology: Formal Operations with Rigorous Guaranteed Engineering**
**Architecture: Cloud-Native GitOps + Kubernetes CRD Management**

## 🚀 CRITICAL: Go Development Workflow
**EVERY code change MUST:**
1. Edit Go code → `go run ./cmd/cnoc` → Test at http://localhost:8080
2. CNOC runs as standalone Go binary - changes visible immediately
3. NO task complete without: compilation + live API verification

## ⚡ Parallel Execution (MANDATORY)
- **ONE message = ALL operations** (never sequential)
- Batch: TodoWrite, Read/Write, Bash commands, MCP tools
- ruv-swarm coordinates, Claude Code executes

## 🧠 FORGE Symphony Agent Orchestration

### Hive Queen Coordination Protocol
**Primary Orchestrator**: coordination-orchestrator
**Process Routing Decision Matrix**:

#### Test-First Development Tasks (MANDATORY)
```yaml
Task_Types_Requiring_TDD_Process:
  - go_implementation: testing-validation-engineer → implementation-specialist
  - api_endpoints: testing-validation-engineer → implementation-specialist  
  - domain_models: testing-validation-engineer → implementation-specialist
  - kubernetes_integration: testing-validation-engineer → implementation-specialist
  - web_components: testing-validation-engineer → implementation-specialist
```

#### FORGE Symphony Movements
```yaml
Movement_1_Domain_Analysis: model-driven-architect + testing-validation-engineer
Movement_2_API_Contracts: contract-first-api-designer + testing-validation-engineer
Movement_3_Test_First: testing-validation-engineer → comprehensive test creation
Movement_4_Implementation: implementation-specialist → make tests pass
Movement_5_K8s_Deployment: infrastructure-deployment-specialist + kubernetes-gitops-specialist
```

### FORGE Agent Pool (10 Core Specialists)
```
Strategic: coordination-orchestrator (FORGE conductor), research-analysis-specialist
Validation: testing-validation-engineer (SDET), implementation-specialist (TDD)
Modeling: model-driven-architect, contract-first-api-designer
Specialized: go-development-specialist, kubernetes-gitops-specialist,
             infrastructure-deployment-specialist, quality-performance-specialist
```

## 🔄 Memory-Enhanced Context Injection + Test-First Routing

### Context Triggers (Enhanced with Test-First Detection)
```yaml
File_Pattern_Triggers:
  "*/tests/*|*_test.go": [testing_patterns.md] + test_first_enforcement
  "*/domain/*": [domain_modeling.md] + mdd_validation
  "*/api/*|*/controllers/*": [api_design.md] + test_first_enforcement
  "*/k8s/*|*/kubernetes/*": [kubernetes_integration.md]
  
Task_Type_Triggers:
  go_implementation: [testing_patterns.md] + MANDATORY_test_first_process
  testing: [testing_patterns.md] + evidence_based_validation
  domain_modeling: [domain_modeling.md] + mdd_validation
  api_design: [api_design.md] + contract_first_validation
```

### Orchestration Decision Logic
- **Adaptive loading**: Contexts triggered by file patterns/task types
- **Success patterns**: Memory-driven context effectiveness scoring (94% domain modeling, 92% API design)
- **Quality gates**: Enhanced MDD validation + Test-First enforcement with 98% automation
- **Process routing**: Automated agent selection based on task analysis and memory patterns

## 📋 FORGE Symphony Process Flow

### FORGE Movement Progression
1. **Domain Analysis** → model-driven-architect → bounded contexts + stakeholder validation
2. **API Contracts** → contract-first-api-designer → OpenAPI/REST + validation + client generation  
3. **Test Creation** → testing-validation-engineer → comprehensive Go tests with red-green-refactor validation
4. **Go Implementation** → implementation-specialist → make tests pass (test integrity protected)
5. **Quality Validation** → quality-performance-specialist → multi-layer + evidence-based validation
6. **Cloud Deployment** → infrastructure-deployment-specialist + kubernetes-gitops-specialist → K8s + monitoring

### Critical Process Routing Rules
- **ANY Go implementation task** → MUST route through testing-validation-engineer FIRST
- **Test modification requests** → BLOCKED (test integrity protection)
- **Evidence-based completion** → quantitative metrics required for ALL phases
- **Memory-driven optimization** → success patterns stored and reused across sessions

## 🐝 ruv-swarm FORGE Integration
```bash
# Initialize FORGE Symphony swarm for CNOC
npx ruv-swarm swarm-init --topology hierarchical --strategy forge-symphony
npx ruv-swarm agent-spawn --type model-driven-architect --memory-context adaptive
npx ruv-swarm task-orchestrate --strategy parallel --validation strict
```

## 🎯 CNOC-Specific Context
- **Cloud-Native**: Independent Go application with PostgreSQL + Redis
- **Enterprise GitOps**: Multi-repository integration with drift detection
- **Kubernetes Integration**: K8s Go client v0.33.4 with CRD management
- **Domain Architecture**: FORGE-aligned with anti-corruption layers
- **HNP Reference**: @docs/HNP_PROTOTYPE_REFERENCE.md (prototype patterns only)

## 📊 Performance Targets (Validated)
- 85% cognitive load reduction (memory-based contexts)
- 75% faster agent selection (consolidated agents)
- 98% automated quality validation (enhanced gates)
- 95% methodology adherence (MDD process enforcement)

## 🔗 Essential Commands
- `go run ./cmd/cnoc` - Start CNOC API server (MANDATORY)
- `go test ./...` - Run comprehensive test suite
- `npx ruv-swarm memory-usage` - Memory operations
- Context loading: Automatic via file patterns + task analysis
- Quality gates: Automatic via enhanced hooks

**Foundation**: Build upon ruv-swarm's proven 84.8% SWE-Bench solve rate + 32.3% token efficiency with FORGE Symphony methodology for rigorous cloud-native development.