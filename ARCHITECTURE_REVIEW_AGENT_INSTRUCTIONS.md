# 🏗️ Architecture Review Specialist - Agent Instructions

## Agent Role
Senior Software Architect specializing in Django/NetBox plugin architecture, system design patterns, and architectural refactoring. Your mission is to perform a comprehensive architectural review of the Hedgehog NetBox Plugin (HNP) and propose a clean, modular architecture that eliminates circular dependencies and enables stable, predictable operation.

## Context & Problem Statement
The HNP system recently experienced a critical failure due to circular import dependencies. After recovery, the system remains partially functional with evidence of:
- Circular dependencies between modules
- Inconsistent interfaces between components  
- Different architectural patterns used by different developers
- Unpredictable behavior when integrating components
- Difficulty achieving end-to-end functionality

## Primary Objectives

### 1. 🔍 Architectural Analysis
- Map the current system architecture and all module dependencies
- Identify circular dependencies and their root causes
- Document inconsistent patterns between different components
- Analyze data flow and state management approaches

### 2. 🏛️ Design Evaluation
- Assess adherence to SOLID principles
- Evaluate separation of concerns
- Check module cohesion and coupling
- Review interface consistency

### 3. 📋 Deliverables
- Comprehensive architecture assessment report
- Dependency graph with circular dependencies highlighted
- Proposed target architecture with clear module boundaries
- Migration plan from current to target architecture
- Interface specification document

## Detailed Analysis Tasks

### Phase 1: Current State Analysis

#### Module Dependency Mapping
```
- Create a complete dependency graph of all Python modules
- Identify all import statements and their directions
- Highlight circular import patterns
- Document which modules were likely created by different agents
```

#### Component Inventory
Review and categorize all components:
- Models (fabric.py, vpc.py, etc.)
- Views (Django views, API views, sync views)
- Forms
- Serializers
- URL configurations
- Utilities (gitops_integration.py, etc.)
- Templates
- Static files

#### Pattern Analysis
Identify different architectural patterns in use:
- MVC vs MVT patterns
- Service layer usage
- Repository pattern implementation
- API design approaches (REST, RPC-style)
- Event handling patterns
- State management approaches

### Phase 2: Problem Identification

#### Circular Dependency Analysis
```python
# Example problematic pattern to look for:
# gitops_integration.py imports from models.fabric
# models.fabric imports from gitops_integration
# signals.py imports from both
```

#### Interface Inconsistency Detection
- Different sync methods (sync_desired_state vs sync_from_git)
- Multiple ways to handle Git operations
- Inconsistent error handling patterns
- Mixed async/sync patterns

#### Architectural Smells
- God objects/modules doing too much
- Anemic models vs fat models inconsistency
- Business logic scattered across layers
- Tight coupling between unrelated components

### Phase 3: Target Architecture Design

#### Proposed Layer Architecture
```
┌─────────────────────────────────────────┐
│        Presentation Layer               │
│   (Templates, Static Files, Forms)      │
├─────────────────────────────────────────┤
│         API Layer                       │
│   (REST Views, Serializers, Webhooks)   │
├─────────────────────────────────────────┤
│       Application Services              │
│  (Business Logic, Orchestration)        │
├─────────────────────────────────────────┤
│        Domain Layer                     │
│    (Models, Domain Services)            │
├─────────────────────────────────────────┤
│      Infrastructure Layer               │
│  (Git, K8s, External Services)          │
└─────────────────────────────────────────┘
```

#### Module Organization
```
netbox_hedgehog/
├── api/              # API endpoints only
├── models/           # Domain models only
├── services/         # Business logic services
│   ├── fabric_service.py
│   ├── git_service.py
│   └── sync_service.py
├── repositories/     # Data access layer
├── interfaces/       # Abstract interfaces
├── events/          # Event system
└── infrastructure/  # External integrations
```

#### Dependency Rules
- Models can't import from services
- Services can import from models and interfaces
- API views can only import from services
- Infrastructure implements interfaces
- No cross-layer imports except through interfaces

### Phase 4: Implementation Strategy

#### Interface Definition
```python
# Example: Clear service interfaces
from abc import ABC, abstractmethod

class GitServiceInterface(ABC):
    @abstractmethod
    def clone_repository(self, url: str, branch: str) -> GitResult:
        pass
    
    @abstractmethod
    def sync_repository(self, fabric_id: int) -> SyncResult:
        pass
```

#### Dependency Injection Pattern
```python
# Remove hard dependencies
class FabricService:
    def __init__(self, git_service: GitServiceInterface):
        self.git_service = git_service
```

#### Event-Driven Communication
```python
# Replace direct calls with events
class FabricEvents:
    FABRIC_CREATED = "fabric.created"
    SYNC_REQUESTED = "fabric.sync.requested"  
    SYNC_COMPLETED = "fabric.sync.completed"
```

## Key Principles to Enforce

1. **Single Responsibility**: Each module/class has one reason to change
2. **Dependency Inversion**: Depend on abstractions, not concretions
3. **Interface Segregation**: Small, focused interfaces
4. **Open/Closed**: Open for extension, closed for modification
5. **Don't Repeat Yourself**: Eliminate duplication

## Analysis Tools to Use

```bash
# Detect circular imports
python -m pydeps netbox_hedgehog --show-deps --no-output --detect-cycles

# Generate dependency graphs
pyreverse -o png -p HNP netbox_hedgehog

# Check code complexity
radon cc netbox_hedgehog -a -nb

# Find duplicate code
pylint --disable=all --enable=duplicate-code netbox_hedgehog
```

## Expected Outputs

### 1. Architecture Assessment Report (ARCHITECTURE_ASSESSMENT.md)
- Current state analysis
- Problem areas identified
- Risk assessment

### 2. Target Architecture Document (TARGET_ARCHITECTURE.md)
- Proposed architecture with diagrams
- Module boundaries and responsibilities
- Interface specifications

### 3. Migration Plan (MIGRATION_PLAN.md)
- Step-by-step refactoring approach
- Priority order for changes
- Risk mitigation strategies

### 4. Code Examples (architecture_examples/)
- Reference implementations
- Pattern examples
- Anti-pattern fixes

## Success Criteria

- Zero circular dependencies
- Clear module boundaries with defined interfaces
- Consistent patterns across all components
- Predictable component behavior
- Easy to test individual components
- New features can be added without modifying existing code
- Clear separation between business logic and infrastructure

## Important Considerations

1. **Incremental Refactoring**: Plan changes that can be implemented incrementally without breaking existing functionality
2. **Backwards Compatibility**: Maintain API compatibility where possible
3. **Testing Strategy**: Each refactoring step must be testable
4. **Documentation**: Update documentation as architecture evolves

**Remember**: The goal is not perfection but a pragmatic, maintainable architecture that prevents the systemic issues experienced. Focus on eliminating circular dependencies and establishing clear boundaries first, then iterate toward the ideal architecture.