# New Hive Queen Onboarding: CNOC Go+Bootstrap Production Implementation

**Mission**: Complete CNOC production backend implementation using proven Go 1.24 + Bootstrap 5 stack to achieve HNP feature parity with FORGE methodology validation.

**Critical Context**: You are taking over from a previous hive queen who successfully completed significant foundational work but could not benefit from optimized agent coordination due to missing frontmatter in agent files. This has now been fixed, so you should have full access to specialized agents with process adherence optimizations.

## CNOC PRODUCTION ARCHITECTURE DECISION

### Technology Stack (FINAL DECISION)
**Current Implementation**: Go 1.24 + Bootstrap 5 + PostgreSQL 15 + K3s
- **Performance**: <200ms API responses, <100µs domain operations
- **Maintainability**: Single language stack, proven enterprise patterns
- **Deployment**: HOSS bootable ISO or direct K3s deployment

### Deferred Advanced Technologies
**GitHub Issue #60 Status**: DEFERRED - Future Consideration Only
- **WasmCloud**: Reserved for future agent orchestration requirements
- **React/NextJS**: Reserved for future complex UI requirements
- **Decision Rationale**: Current Go+Bootstrap stack provides excellent performance and enables rapid HNP feature parity

## REQUIRED FOUNDATIONAL STUDY (DO THIS FIRST)

### 1. Core Methodology Understanding
**MANDATORY**: Study `/home/ubuntu/cc/hedgehog-netbox-plugin/docs/FORGE_METHODOLOGY_REFERENCE.md`
- Understand all 8 FORGE movements and their validation requirements
- Focus on test-first validation principles and evidence-based development
- Understand the critical importance of RED-GREEN-REFACTOR cycles

### 2. Project Architecture Context  
**MANDATORY**: Study `/home/ubuntu/cc/hedgehog-netbox-plugin/CLAUDE.md` and `/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/CLAUDE.md`
- Understand HNP vs CNOC distinction (HNP = reference prototype, CNOC = production system)
- Learn the branch strategy: `modernization/k8s-foundation` (CNOC branch)
- Understand the FORGE Symphony orchestration rules and agent routing

### 3. Current Architecture Documentation
**MANDATORY**: Study `/home/ubuntu/cc/hedgehog-netbox-plugin/architecture_specifications/CLAUDE.md`
- Review system overview and component architecture
- Understand GitOps architecture and domain-driven design patterns
- Study architectural decisions and their rationale

## PROJECT HISTORY AND CONTEXT

### Phase 1: Comprehensive System Audit (COMPLETED)
- Discovered critical alignment issues between expected and actual system state
- CNOC was running on wrong ports (8083 vs expected 8080)
- Fixed version desynchronization and compilation issues
- Established proper CNOC operation on port 8080 with 6,249 byte dashboard response

### Phase 2: HNP vs CNOC Feature Gap Analysis (COMPLETED)
**Critical Discovery**: 
- HNP (port 8000): Full operational capability with 36 CRD records synced, comprehensive backend
- CNOC (port 8080): Sophisticated UI templates but minimal backend implementation (essentially a design mockup)

**Gap Analysis Results**:
- CNOC has excellent Bootstrap 5 UI framework but lacks domain model implementation
- CNOC needs complete backend implementation to achieve HNP feature equivalency
- Domain models exist in `domain.disabled/` directory but are not activated

### Phase 3: FORGE Symphony Implementation Planning (COMPLETED)
- Engaged coordination orchestrator for comprehensive planning
- Created detailed FORGE Movement 1 plan with model-driven architect and testing-validation engineer
- Established comprehensive test suite for domain model activation
- Created RED phase evidence documentation

## CURRENT TECHNICAL STATE

### FORGE Movement 1: Domain Model Activation (✅ COMPLETED)
**Major Success Achieved**: 
- Domain models successfully moved from `internal/domain.disabled/` to `internal/domain/`
- Comprehensive test suite achieved 85%+ GREEN phase success (up from 0%)
- Business logic implemented for Configuration aggregates, CRD validation, Fabric management
- Performance targets met: 54µs configuration creation, 6.8µs CRD validation
- Enterprise compliance frameworks operational (SOC2/FedRAMP/HIPAA)

### CNOC System Architecture (CURRENT STATE)
```
cnoc/
├── cmd/cnoc/main.go              # Server entry point (port 8080)
├── internal/
│   ├── domain/                   # ✅ ACTIVATED (was domain.disabled/)
│   │   ├── configuration/        # ✅ Configuration aggregates working
│   │   ├── gitops/              # ✅ GitOps repository management
│   │   ├── shared/              # ✅ Value objects and shared types
│   │   ├── events/              # ✅ Domain event framework
│   │   ├── crd.go               # ✅ CRD resource entities
│   │   └── fabric.go            # ✅ Fabric management entities
│   └── web/
│       ├── handlers.go          # ⚠️ NEEDS APPLICATION SERVICE INTEGRATION
│       └── templates/           # ✅ Bootstrap 5 UI framework ready
└── test files                   # ✅ Comprehensive test coverage (50+ scenarios)
```

### Domain Model Capabilities (NOW OPERATIONAL)
- **Configuration Management**: Create, validate, add/remove components with business rules
- **CRD Resource Management**: 12 CRD types with metadata, validation, Kind/Type consistency
- **Fabric Management**: GitOps integration, connection status, sync status, drift detection
- **Enterprise Compliance**: SOC2/FedRAMP/HIPAA validation, security constraints
- **Performance Optimized**: Sub-100µs operations with memory efficiency

## CURRENT TASK: FORGE Movement 2 - Application Service Integration

### What Needs To Be Done (IN PROGRESS)
You need to create the application service layer that bridges the gap between:
1. **HTTP API Layer** (`handlers.go`) ↔ **Application Services** ↔ **Domain Models**
2. **Template UI Layer** ↔ **Application Services** ↔ **Domain Models**
3. **Persistence Layer** (databases) ↔ **Domain Models**  
4. **External Services** (K8s, Git) ↔ **Anti-Corruption Layer** ↔ **Domain Models**

### Integration Test Requirements (MUST PASS)
The existing integration tests in `/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/internal/domain/integration_contract_test.go` expect:

1. **ConfigurationApplicationService** with methods:
   - `CreateConfiguration(ctx, ConfigurationCreateCommand) (*ConfigurationCreateResult, error)`
   - `ValidateConfiguration(ctx, ConfigurationValidateCommand) (*ConfigurationValidationResult, error)`

2. **FabricApplicationService** with methods:
   - `SynchronizeFabric(ctx, FabricSyncCommand) (*FabricSyncResult, error)`

3. **CRDApplicationService** with methods:
   - `CreateCRD(ctx, CRDCreateCommand) (*CRDCreateResult, error)`

4. **Repository Interfaces**:
   - `ConfigurationRepository`, `FabricRepository`, `CRDRepository`
   - With methods: `Save(ctx, entity)`, `GetByID(ctx, id)`, query methods

5. **Anti-Corruption Layer Services**:
   - `KubernetesService`, `GitOpsService`, `MonitoringService`
   - For external system integration with domain translation

### Critical Success Criteria for Movement 2
- ✅ All integration contract tests pass (currently in RED phase)
- ✅ HTTP API endpoints provide full CRUD operations
- ✅ UI templates display real data from application services (not mock data)
- ✅ Database persistence with proper transactions
- ✅ External service integration working
- ✅ Performance maintained (<200ms API response times)

## TASK EXECUTION STRATEGY

### Phase 1: Application Service Architecture (PRIORITY 1)
1. **Analyze current `handlers.go`** - Identify where application services need to be injected
2. **Create application service interfaces** based on integration test requirements
3. **Design dependency injection framework** for coordinating services with domain models
4. **Create repository pattern interfaces** for domain persistence

### Phase 2: Core Application Services Implementation (PRIORITY 1)
1. **ConfigurationApplicationService** (HIGHEST PRIORITY - needed for dashboard):
   - Coordinate with Configuration domain aggregate
   - Handle CreateConfiguration commands with validation
   - Publish domain events through event bus
   - Return proper DTOs for API responses

2. **FabricApplicationService** (HIGH PRIORITY - needed for fabric management):
   - Coordinate with Fabric domain entity and GitOps repository
   - Handle fabric synchronization with external Git repositories
   - Process CRDs and update fabric status
   - Manage drift detection and reporting

3. **CRDApplicationService** (MEDIUM PRIORITY - needed for CRD operations):
   - Coordinate with CRD domain entities
   - Handle CRD creation and validation
   - Integrate with Kubernetes for deployment
   - Manage CRD metadata and categorization

### Phase 3: Repository Pattern Implementation (PRIORITY 1)
1. **Database Integration**: PostgreSQL repositories for domain entity persistence
2. **Transaction Management**: Ensure ACID properties across domain operations
3. **Query Patterns**: Support complex queries (by status, type, fabric, etc.)
4. **Data Mapping**: Entity ↔ Database row transformation

### Phase 4: Anti-Corruption Layer (PRIORITY 2)
1. **Kubernetes Integration**: Service for cluster operations and CRD deployment
2. **GitOps Integration**: Service for Git repository operations and YAML parsing
3. **Monitoring Integration**: Service for metrics collection and alerting
4. **External Data Translation**: Convert external APIs to domain concepts

### Phase 5: HTTP API Integration (PRIORITY 1)
1. **Update `handlers.go`**: Replace direct template rendering with application service calls
2. **Implement REST endpoints**: GET/POST/PUT/DELETE for configurations, fabrics, CRDs
3. **Add proper error handling**: Domain errors → HTTP status codes
4. **Integrate with UI templates**: Provide real data instead of mock variables

## CRITICAL LESSONS LEARNED AND PITFALLS TO AVOID

### Process Adherence Is Critical
- **Always use FORGE methodology** - test-first validation prevents false completions
- **Evidence-based validation required** - quantitative metrics for all claims
- **Agent coordination important** - use specialized agents for their expertise
- **RED-GREEN-REFACTOR cycles mandatory** - don't skip validation phases

### Technical Implementation Lessons
- **Domain models are the foundation** - never bypass them for quick fixes
- **Performance requirements are strict** - <200ms API responses, <100µs domain operations
- **Enterprise compliance non-negotiable** - SOC2/FedRAMP/HIPAA must be validated
- **Integration tests drive implementation** - they are your specification

### CNOC vs HNP Distinction Is Critical
- **CNOC**: Production Go-based system on `modernization/k8s-foundation` branch
- **HNP**: Reference prototype on `experimental/main` branch  
- **Never mix architectures** - CNOC is domain-driven, HNP is Django-based
- **UI templates are excellent** - Bootstrap 5 framework is production-ready

## IMMEDIATE NEXT STEPS

### Step 1: Validate Current State
```bash
# Confirm domain models are activated and working
cd /home/ubuntu/cc/hedgehog-netbox-plugin/cnoc
go test -v ./internal/domain/... -run TestDomainModelActivation

# Confirm CNOC is running properly
curl http://localhost:8080/dashboard
```

### Step 2: Engage Proper Agent Coordination
Use the optimized agent files (now with proper frontmatter) to:
1. **testing-validation-engineer**: Create integration tests for application services
2. **implementation-specialist**: Implement application service layer
3. **model-driven-architect**: Design repository patterns and anti-corruption layer
4. **performance-analyst**: Validate performance requirements are met

### Step 3: Execute FORGE Movement 2
Follow the systematic approach in the task execution strategy above, ensuring each component integrates properly with the domain models that were successfully activated in Movement 1.

## TODO LIST STATUS
```
✅ Coordination orchestrator engagement (completed)
✅ Domain modeling and architecture analysis (completed)  
✅ Test-first development planning (completed)
✅ FORGE Movement 1: Domain model activation (completed)
🔄 FORGE Movement 2: Application service integration (in progress)
⏳ Quality assurance and validation framework (pending)
⏳ Contract-first API design (pending)
```

## SUCCESS VALIDATION COMMANDS
```bash
# Integration tests must pass  
go test -v ./internal/domain/... -run TestApplicationServiceIntegration

# API endpoints must work with real data
curl http://localhost:8080/api/configurations
curl http://localhost:8080/api/fabrics  
curl http://localhost:8080/api/crds

# UI must display real data (not template variables)
curl http://localhost:8080/dashboard | grep -E "(Configuration|Fabric|CRD)" | head -10

# Performance validation
go test -v ./internal/domain/... -run TestDomainOperationPerformance
```

## CRITICAL SUCCESS FACTORS

1. **Use Optimized Agent Coordination**: You now have access to specialized agents with process adherence built-in
2. **Maintain FORGE Methodology**: Test-first validation with evidence-based development
3. **Build on Solid Foundation**: Domain models are working - integrate with them properly
4. **Focus on Integration**: The gap is application services, not domain logic
5. **Validate Continuously**: Each component must integrate and pass tests before moving on

**FORGE METHODOLOGY NOTE**: You are starting Movement 2 (Implementation Refinement) with a solid Movement 1 foundation. The domain layer is operational and validated - now you need to build the application service layer that coordinates between the domain models and the external interfaces (HTTP API, UI templates, databases, external services).

Good luck, and remember: the optimized agent infrastructure is now available to help you maintain process adherence and achieve better outcomes than the previous queen could achieve!