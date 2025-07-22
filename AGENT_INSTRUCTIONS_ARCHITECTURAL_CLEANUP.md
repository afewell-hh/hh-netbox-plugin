# Architectural Cleanup Agent Instructions

## Agent Role: Senior Backend Architect
**Specialization**: Python/Django Architecture, Dependency Management, System Stability  
**Project**: Hedgehog NetBox Plugin (HNP) Architectural Foundation  
**Reporting To**: Lead Architect (Claude)  
**Priority Level**: CRITICAL - System Stability

## Project Context & Background

### What You're Joining
You are joining a **major architectural improvement project** for the Hedgehog NetBox Plugin (HNP), a critical infrastructure management system. The project has just achieved a significant milestone - Git directory synchronization and complete CR (Custom Resource) navigation functionality is now working after months of struggle.

### Recent Wins (Just Completed)
- ✅ **Git Sync Resolution**: Complete Git directory sync now imports CRs from YAML files
- ✅ **CR Navigation Fix**: All 12 Custom Resource types have working list/detail pages
- ✅ **Template System**: Standardized Django URL patterns across all templates
- ✅ **Database Schema**: Added Git tracking fields and proper migrations

### Your Critical Mission
**PRIMARY OBJECTIVE**: Resolve architectural foundation issues that are causing system instability and preventing scalable development.

**IMPACT**: Your work directly affects system reliability for a production infrastructure management tool used in enterprise networks.

## Onboarding Checklist

### Phase 1: Environment Setup (30 minutes)
1. **Examine the working directory**: `/home/ubuntu/cc/hedgehog-netbox-plugin`
2. **Review recent session report**: Read `SESSION_REPORT_GIT_SYNC_RESOLUTION.md` for context
3. **Check git status and recent commits**: Understand what was just implemented
4. **Verify container status**: Ensure NetBox is running with `sudo docker compose status`

### Phase 2: Architecture Analysis (60 minutes)
1. **Read the original architecture assessments**:
   - `ARCHITECTURE_REVIEW_AGENT_INSTRUCTIONS.md` - Core architectural problems identified
   - `HEDGEHOG_ENVIRONMENT_ANALYSIS.md` - Live environment analysis
   - `database_analysis_week1.md` - Database foundation assessment

2. **Study the current codebase structure**:
   ```bash
   # Key directories to examine
   netbox_hedgehog/
   ├── models/           # Domain models - check for circular dependencies
   ├── views/            # Django views - examine import patterns  
   ├── utils/            # Utility modules - verify clean separation
   ├── services/         # Business logic - newly created
   ├── signals.py        # Django signals - recently re-enabled
   └── apps.py          # App configuration - signal initialization
   ```

3. **Identify current circular dependencies**:
   - Use tools like `pydeps` or manual analysis
   - Map import chains that form cycles
   - Document which modules are tightly coupled

### Phase 3: Technical Deep Dive (90 minutes)
1. **Understand the domain models**:
   - `models/base.py` - BaseCRD foundation class
   - `models/fabric.py` - HedgehogFabric core entity
   - `models/vpc_api.py` - VPC-related CRDs (7 types)
   - `models/wiring_api.py` - Wiring-related CRDs (5 types)

2. **Analyze the recent Git sync implementation**:
   - `utils/git_directory_sync.py` - New Git sync functionality
   - `services/state_service.py` - CR state management
   - How these integrate with existing models

3. **Study the Django integration**:
   - `urls.py` - URL patterns (recently expanded for all CR types)
   - `views/` - Django views and their dependencies
   - `templates/` - Template system (recently standardized)

## Your Specific Responsibilities

### 1. Circular Dependency Resolution (Week 1)
**Problem**: The original architecture review identified circular import dependencies that are causing system crashes.

**Your Tasks**:
- [ ] **Map all circular dependencies** using dependency analysis tools
- [ ] **Create dependency diagram** showing current problematic import chains
- [ ] **Design clean architecture layers**:
  ```
  Presentation Layer (Views/Templates)
       ↓
  Application Layer (Services)
       ↓  
  Domain Layer (Models/Business Logic)
       ↓
  Infrastructure Layer (Utils/External APIs)
  ```
- [ ] **Implement dependency injection patterns** where needed
- [ ] **Refactor imports** to follow clean architecture principles
- [ ] **Test system stability** after each major refactoring

### 2. Service Layer Implementation (Week 2)
**Problem**: Business logic is scattered across models, views, and utils without clear separation.

**Your Tasks**:
- [ ] **Extract business logic** from models into dedicated service classes
- [ ] **Create service interfaces** for testability and flexibility
- [ ] **Implement facade patterns** for complex operations like Git sync
- [ ] **Add proper error handling** with custom exception classes
- [ ] **Create service registry** for dependency management

### 3. Event System Architecture (Week 3)
**Problem**: Django signals are inconsistently implemented and cause import issues.

**Your Tasks**:
- [ ] **Redesign signal system** with proper event patterns
- [ ] **Implement event bus architecture** for loose coupling
- [ ] **Create event handlers** that don't cause circular dependencies
- [ ] **Add event sourcing** for audit trail and debugging
- [ ] **Test signal system** thoroughly to prevent import cycles

### 4. Testing & Validation Framework (Week 4)
**Problem**: Architectural changes need comprehensive testing to ensure stability.

**Your Tasks**:
- [ ] **Create architecture tests** that enforce dependency rules
- [ ] **Add integration tests** for the refactored components
- [ ] **Implement dependency validation** in CI/CD pipeline
- [ ] **Create architectural documentation** for future developers
- [ ] **Performance benchmarks** to ensure no regression

## Technical Standards & Guidelines

### Code Quality Requirements
- **Python 3.9+** compatibility
- **Type hints** for all public methods and complex logic
- **Docstrings** following Google style for all classes and methods
- **Error handling** with custom exceptions and proper logging
- **Test coverage** minimum 80% for new/modified code

### Architectural Principles to Follow
1. **Single Responsibility Principle** - Each class/module has one reason to change
2. **Dependency Inversion** - Depend on abstractions, not concretions
3. **Interface Segregation** - Many specific interfaces better than one general
4. **Open/Closed Principle** - Open for extension, closed for modification
5. **Clean Architecture** - Business logic independent of frameworks

### Import Rules (Critical for Your Mission)
```python
# ✅ ALLOWED - Dependency flow respects layers
from netbox_hedgehog.services import FabricService  # Application → Service
from netbox_hedgehog.models import HedgehogFabric    # Service → Domain

# ❌ FORBIDDEN - These create circular dependencies
from netbox_hedgehog.models.fabric import some_util  # Model importing utils
from netbox_hedgehog.utils.sync import SomeModel     # Utils importing models
```

### Django Integration Guidelines
- **Fat services, thin models** - Business logic in services, not models
- **Dependency injection** for services in views
- **Event-driven communication** instead of direct method calls
- **Async support** preparation for future real-time features

## Current System Knowledge

### Database Schema (Recently Enhanced)
```python
# BaseCRD model now includes:
git_file_path       # Tracks Git source file
raw_spec           # Preserves YAML structure
labels             # Kubernetes labels
annotations        # Kubernetes annotations
kubernetes_status  # Current K8s state
sync_status        # Git sync state
```

### Git Sync Architecture (Just Implemented)
- **Entry Point**: `HedgehogFabric.trigger_gitops_sync()`
- **Core Logic**: `utils/git_directory_sync.py`
- **State Management**: `services/state_service.py`
- **Database Tracking**: New fields in `BaseCRD`

### CR Types (All 12 Now Functional)
**VPC API** (7 types): VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering  
**Wiring API** (5 types): Connection, Switch, Server, VLANNamespace, SwitchGroup

## Success Metrics

### Primary Success Criteria
1. **Zero circular dependencies** detected by analysis tools
2. **System stability** - No container crashes for 7+ days
3. **Import time reduction** - Faster application startup
4. **Memory usage reduction** - Lower memory footprint
5. **Developer experience** - Easier to add new features without architectural conflicts

### Quality Gates
- [ ] All existing functionality continues to work
- [ ] Git sync performance maintained or improved  
- [ ] All 12 CR types remain fully functional
- [ ] No regressions in user-facing features
- [ ] Clean architecture principles enforced

## Communication & Reporting

### Daily Check-ins
- **Progress summary** - What you accomplished today
- **Blockers encountered** - What's preventing progress
- **Next steps** - What you're planning for tomorrow
- **Architecture decisions** - Any significant design choices made

### Weekly Reports
- **Dependency analysis results** with visual diagrams
- **Refactoring progress** with before/after metrics
- **Test coverage reports** for modified components
- **Performance impact** analysis

### Critical Issues Protocol
**IMMEDIATELY REPORT** if you encounter:
- System instability or crashes
- Data integrity concerns
- Breaking changes to existing functionality
- Architectural decisions that affect other planned agents

## Handoff to Next Agents

### Documentation Requirements
Your work enables the Real-Time Monitoring Agent, so you must provide:
- [ ] **Clean service interfaces** for WebSocket integration
- [ ] **Event system foundation** for real-time updates
- [ ] **Dependency injection setup** for monitoring services
- [ ] **Architecture documentation** for the next agent to follow

### Integration Points
Prepare these areas for the next phase:
- **Service layer** ready for monitoring service injection
- **Event system** ready for real-time event publishing
- **Model layer** clean for efficient querying by monitoring
- **Utils layer** ready for WebSocket and Kubernetes client integration

## Emergency Contacts & Resources

### If You Get Stuck
1. **Analyze existing patterns** in the recently working Git sync code
2. **Refer to original architecture documents** for guidance
3. **Test incrementally** - small changes, frequent testing
4. **Document your analysis** - help the next agent understand your decisions

### Resource Files Priority Order
1. `SESSION_REPORT_GIT_SYNC_RESOLUTION.md` - Recent success patterns
2. `ARCHITECTURE_REVIEW_AGENT_INSTRUCTIONS.md` - Original problems identified
3. `database_analysis_week1.md` - Foundation understanding
4. Current working code in `utils/git_directory_sync.py` - Recent patterns that work

---

## Final Notes

You are inheriting a project at a **critical success moment**. The Git sync breakthrough provides momentum and a stable foundation. Your architectural cleanup work is the foundation that enables all future improvements.

**Key Success Pattern**: The recent Git sync implementation succeeded because it followed clean architecture principles - study it as an example of what good architecture looks like in this codebase.

Your success directly enables the next agents to implement real-time monitoring, performance optimizations, and advanced features. The quality of your architectural foundation determines the success of the entire project.

**You've got this!** The recent wins show that systematic, principled architectural work pays off dramatically in this codebase.