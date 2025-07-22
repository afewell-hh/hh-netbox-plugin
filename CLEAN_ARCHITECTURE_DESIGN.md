# Clean Architecture Design - HNP Refactoring Plan
**Date:** July 22, 2025  
**Agent:** Senior Backend Architect  
**Purpose:** Comprehensive clean architecture design for eliminating circular dependencies  
**Status:** Design Complete - Ready for Implementation

## Executive Summary

This document presents a comprehensive clean architecture design to eliminate circular dependencies and establish proper separation of concerns in the Hedgehog NetBox Plugin. The design follows Robert C. Martin's Clean Architecture principles with Django-specific adaptations.

## Architecture Principles

### Core Principles
1. **Dependency Inversion**: High-level modules should not depend on low-level modules
2. **Single Responsibility**: Each module has one reason to change
3. **Interface Segregation**: Many specific interfaces better than one general interface
4. **Open/Closed**: Open for extension, closed for modification
5. **Separation of Concerns**: Each layer handles specific responsibilities

### Django-Specific Adaptations
- Models remain in Django's expected location but follow domain-driven design
- Views become thin controllers that delegate to services
- Services layer handles all business logic
- Utils become pure infrastructure helpers

## Layer Architecture Design

### 1. Infrastructure Layer (Bottom)
**Purpose:** External concerns, utilities, adapters
**Dependencies:** None (depends only on external libraries)

```
netbox_hedgehog/infrastructure/
├── adapters/
│   ├── __init__.py
│   ├── git_adapter.py           # Git operations wrapper
│   ├── kubernetes_adapter.py    # K8s API wrapper  
│   └── argocd_adapter.py        # ArgoCD API wrapper
├── clients/
│   ├── __init__.py
│   ├── git_client.py           # Low-level Git client
│   ├── kubernetes_client.py    # Low-level K8s client
│   └── http_client.py          # HTTP utilities
├── repositories/
│   ├── __init__.py
│   ├── crd_repository.py       # Data access patterns
│   └── fabric_repository.py    # Data access patterns
└── utils/                      # Pure utility functions
    ├── __init__.py
    ├── yaml_parser.py          # YAML utilities
    ├── file_operations.py      # File system utilities
    └── validation_helpers.py   # Validation utilities
```

**Key Characteristics:**
- ✅ No imports from higher layers
- ✅ Pure functions and classes
- ✅ Easily testable in isolation
- ✅ Can be replaced without affecting business logic

### 2. Domain Layer
**Purpose:** Business entities, rules, and core logic
**Dependencies:** Infrastructure layer only

```
netbox_hedgehog/domain/
├── models/                     # Keep existing location for Django
│   ├── __init__.py
│   ├── base.py                # Domain entities
│   ├── fabric.py              # Core fabric entity
│   ├── git_repository.py      # Git repository entity
│   ├── vpc_api.py             # VPC domain entities
│   ├── wiring_api.py          # Wiring domain entities
│   ├── gitops.py              # GitOps domain entities
│   └── reconciliation.py      # Reconciliation entities
├── entities/                   # Domain value objects
│   ├── __init__.py
│   ├── git_reference.py       # Git commit, branch references
│   ├── kubernetes_manifest.py # K8s manifest value object
│   └── sync_status.py         # Sync status value object
├── events/                     # Domain events
│   ├── __init__.py
│   ├── fabric_events.py       # Fabric lifecycle events
│   ├── sync_events.py         # Sync-related events
│   └── crd_events.py          # CRD lifecycle events
├── exceptions/                 # Domain-specific exceptions
│   ├── __init__.py
│   ├── sync_exceptions.py     # Sync-related errors
│   └── validation_exceptions.py
└── interfaces/                 # Abstract interfaces
    ├── __init__.py
    ├── git_service_interface.py
    ├── kubernetes_service_interface.py
    └── sync_service_interface.py
```

**Key Characteristics:**
- ✅ Contains business rules and logic
- ✅ Independent of frameworks (except Django ORM)
- ✅ Defines interfaces for external services
- ✅ No dependencies on application or infrastructure concerns

### 3. Application Layer (Services)
**Purpose:** Use cases, orchestration, business workflows
**Dependencies:** Domain layer, Infrastructure layer (through interfaces)

```
netbox_hedgehog/application/
├── services/
│   ├── __init__.py
│   ├── fabric_service.py       # Fabric management service
│   ├── git_sync_service.py     # Git synchronization service
│   ├── crd_lifecycle_service.py # CRD CRUD operations
│   ├── kubernetes_service.py   # K8s operations service
│   ├── state_service.py        # State transition service (existing)
│   ├── reconciliation_service.py # Drift detection service
│   └── audit_service.py        # Audit trail service
├── workflows/
│   ├── __init__.py
│   ├── fabric_onboarding.py   # Complete fabric setup workflow
│   ├── git_sync_workflow.py   # End-to-end Git sync workflow
│   └── disaster_recovery.py   # Recovery workflows
├── commands/                   # Command pattern for operations
│   ├── __init__.py
│   ├── sync_fabric_command.py
│   ├── create_fabric_command.py
│   └── reconcile_drift_command.py
└── queries/                    # Query pattern for reads
    ├── __init__.py
    ├── fabric_queries.py
    ├── drift_queries.py
    └── audit_queries.py
```

**Key Characteristics:**
- ✅ Orchestrates domain objects
- ✅ Implements use cases
- ✅ Handles cross-cutting concerns (logging, transactions)
- ✅ Depends on domain interfaces, not implementations

### 4. Presentation Layer (Top)
**Purpose:** User interface, API endpoints, external interface
**Dependencies:** Application layer only

```
netbox_hedgehog/presentation/
├── api/                        # Keep existing location for Django
│   ├── __init__.py
│   ├── serializers.py         # API serialization
│   ├── views.py               # API endpoints
│   ├── urls.py                # API routing
│   └── webhooks.py            # Webhook handlers
├── views/                      # Keep existing location for Django
│   ├── __init__.py
│   ├── fabric_views.py        # Fabric UI views
│   ├── sync_views.py          # Sync UI views
│   ├── vpc_views.py           # VPC UI views
│   └── wiring_views.py        # Wiring UI views
├── forms/                      # Keep existing location for Django
│   ├── __init__.py
│   ├── fabric_forms.py        # Fabric input forms
│   ├── git_forms.py           # Git configuration forms
│   └── crd_forms.py           # CRD input forms
└── templates/                  # Keep existing location for Django
    └── netbox_hedgehog/
        ├── fabric_list.html
        ├── fabric_detail.html
        └── ...existing templates
```

**Key Characteristics:**
- ✅ Thin layer with minimal logic
- ✅ Delegates all business logic to application services
- ✅ Handles user input validation and formatting
- ✅ Framework-specific code contained here

## Dependency Injection Pattern

### Service Registration
```python
# netbox_hedgehog/application/service_registry.py
from typing import Dict, Type, TypeVar, Generic
from .interfaces import GitServiceInterface, KubernetesServiceInterface

T = TypeVar('T')

class ServiceRegistry:
    """Dependency injection container for services"""
    
    def __init__(self):
        self._services: Dict[Type, object] = {}
        self._singletons: Dict[Type, object] = {}
    
    def register(self, interface: Type[T], implementation: T, singleton: bool = True):
        """Register a service implementation for an interface"""
        if singleton:
            self._singletons[interface] = implementation
        else:
            self._services[interface] = implementation
    
    def get(self, interface: Type[T]) -> T:
        """Get service implementation for interface"""
        if interface in self._singletons:
            return self._singletons[interface]
        elif interface in self._services:
            return self._services[interface]()
        else:
            raise ValueError(f"No implementation registered for {interface}")

# Global registry instance
registry = ServiceRegistry()
```

### Service Interface Example
```python
# netbox_hedgehog/domain/interfaces/git_service_interface.py
from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities.git_reference import GitReference
from ..entities.kubernetes_manifest import KubernetesManifest

class GitServiceInterface(ABC):
    """Abstract interface for Git operations"""
    
    @abstractmethod
    def clone_repository(self, url: str, branch: str, path: str) -> GitReference:
        """Clone Git repository to local path"""
        pass
    
    @abstractmethod
    def list_yaml_files(self, repo_path: str, directory: str) -> List[str]:
        """List YAML files in repository directory"""
        pass
    
    @abstractmethod
    def parse_manifests(self, file_paths: List[str]) -> List[KubernetesManifest]:
        """Parse YAML files into Kubernetes manifests"""
        pass
    
    @abstractmethod
    def get_latest_commit(self, repo_path: str) -> str:
        """Get latest commit SHA"""
        pass
```

### Service Implementation Example
```python
# netbox_hedgehog/application/services/git_sync_service.py
import logging
from typing import List, Dict, Any
from django.db import transaction

from ...domain.interfaces.git_service_interface import GitServiceInterface
from ...domain.models.fabric import HedgehogFabric
from ...infrastructure.adapters.git_adapter import GitAdapter
from ...infrastructure.utils.yaml_parser import YamlParser

logger = logging.getLogger(__name__)

class GitSyncService:
    """Business service for Git synchronization operations"""
    
    def __init__(self, git_service: GitServiceInterface):
        self.git_service = git_service
        self.yaml_parser = YamlParser()
    
    def sync_fabric_from_git(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """
        Synchronize fabric CRDs from Git repository
        
        Args:
            fabric: HedgehogFabric instance with Git configuration
            
        Returns:
            dict: Sync results with statistics
        """
        if not fabric.git_repository_url:
            raise ValueError("Fabric has no Git repository configured")
        
        try:
            with transaction.atomic():
                # Clone repository
                git_ref = self.git_service.clone_repository(
                    fabric.git_repository_url,
                    fabric.git_branch,
                    f"/tmp/sync_{fabric.pk}"
                )
                
                # Find YAML files
                yaml_files = self.git_service.list_yaml_files(
                    git_ref.local_path,
                    fabric.git_path
                )
                
                # Parse manifests
                manifests = self.git_service.parse_manifests(yaml_files)
                
                # Create/update CRDs
                results = self._create_or_update_crds(fabric, manifests)
                
                # Update fabric sync status
                fabric.last_git_sync = timezone.now()
                fabric.desired_state_commit = git_ref.commit_sha
                fabric.save(update_fields=['last_git_sync', 'desired_state_commit'])
                
                logger.info(f"Git sync completed for fabric {fabric.name}: {results}")
                return results
                
        except Exception as e:
            logger.error(f"Git sync failed for fabric {fabric.name}: {e}")
            raise
    
    def _create_or_update_crds(self, fabric: HedgehogFabric, manifests: List) -> Dict[str, int]:
        """Create or update CRDs based on Git manifests"""
        # Implementation moved from utils/git_directory_sync.py
        # Business logic for CRD creation/updates
        pass
```

### View Integration Example
```python
# netbox_hedgehog/presentation/views/fabric_views.py
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse

from ...application.service_registry import registry
from ...application.services.fabric_service import FabricService
from ...application.services.git_sync_service import GitSyncService
from ...domain.models.fabric import HedgehogFabric

class FabricDetailView(View):
    """Fabric detail view - thin controller delegating to services"""
    
    def get(self, request, pk):
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        # Get services from registry
        fabric_service = registry.get(FabricService)
        
        # Get fabric statistics through service
        stats = fabric_service.get_fabric_statistics(fabric)
        
        context = {
            'fabric': fabric,
            'stats': stats,
        }
        return render(request, 'netbox_hedgehog/fabric_detail.html', context)
    
    def post(self, request, pk):
        """Handle sync request"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        if 'sync_git' in request.POST:
            try:
                # Get service from registry
                git_sync_service = registry.get(GitSyncService)
                
                # Delegate to service
                results = git_sync_service.sync_fabric_from_git(fabric)
                
                messages.success(
                    request, 
                    f"Git sync completed: {results['created']} created, "
                    f"{results['updated']} updated"
                )
            except Exception as e:
                messages.error(request, f"Git sync failed: {e}")
        
        return self.get(request, pk)
```

## Migration Strategy

### Phase 1: Foundation (Week 1)
```python
# 1. Break circular dependency using string references
class HedgehogFabric(NetBoxModel):
    # Change from:
    # git_repository = models.ForeignKey(GitRepository, ...)
    # To:
    git_repository = models.ForeignKey(
        'netbox_hedgehog.GitRepository',
        on_delete=models.CASCADE,
        null=True, blank=True
    )

# 2. Create basic service interfaces
# netbox_hedgehog/domain/interfaces/

# 3. Create service registry
# netbox_hedgehog/application/service_registry.py

# 4. Move state_service.py logic to proper application layer
```

### Phase 2: Service Creation (Week 2)
```python
# 1. Create core services with proper dependency injection
FabricService(git_service, kubernetes_service, state_service)
GitSyncService(git_adapter, yaml_parser)
CRDLifecycleService(kubernetes_adapter, state_service)

# 2. Move business logic from utils to services
# utils/git_directory_sync.py → services/git_sync_service.py
# utils/gitops_integration.py → services/gitops_service.py

# 3. Update utils to be pure helpers
# utils/ should only contain framework-independent utilities
```

### Phase 3: View Refactoring (Week 3)
```python
# 1. Update all views to use services instead of utils
# Remove: from ..utils.kubernetes import KubernetesClient
# Add: kubernetes_service = registry.get(KubernetesService)

# 2. Make views thin controllers
# Move business logic from views to services
# Views should only handle HTTP concerns and delegate

# 3. Update API views with same pattern
```

### Phase 4: Testing & Validation (Week 4)
```python
# 1. Create architecture tests
def test_no_circular_dependencies():
    # Test each module imports independently
    
def test_dependency_direction():
    # Ensure utils don't import models
    # Ensure views don't import utils directly
    
def test_service_isolation():
    # Test services can be mocked/replaced

# 2. Create integration tests for refactored components
# 3. Performance benchmarking
# 4. Documentation updates
```

## Error Handling Strategy

### Domain-Level Exceptions
```python
# netbox_hedgehog/domain/exceptions/
class HedgehogDomainError(Exception):
    """Base domain exception"""
    pass

class GitSyncError(HedgehogDomainError):
    """Git synchronization errors"""
    pass

class KubernetesConnectionError(HedgehogDomainError):
    """Kubernetes connectivity errors"""
    pass

class CRDValidationError(HedgehogDomainError):
    """CRD specification validation errors"""
    pass
```

### Service-Level Error Handling
```python
class GitSyncService:
    def sync_fabric_from_git(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        try:
            # Business logic
            return results
        except GitSyncError as e:
            logger.error(f"Git sync failed for {fabric.name}: {e}")
            # Handle domain-specific error
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Git sync: {e}")
            # Convert to domain exception
            raise GitSyncError(f"Git sync failed: {e}") from e
```

## Performance Considerations

### Service Caching
```python
from functools import lru_cache
from django.core.cache import cache

class FabricService:
    @lru_cache(maxsize=128)
    def get_fabric_statistics(self, fabric_id: int) -> Dict[str, Any]:
        """Cached fabric statistics"""
        # Implementation with caching
        
    def invalidate_fabric_cache(self, fabric_id: int):
        """Invalidate cache when fabric changes"""
        self.get_fabric_statistics.cache_clear()
```

### Async Service Support
```python
# Prepare for future async support
from typing import Union
import asyncio

class GitSyncService:
    def sync_fabric_from_git(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Synchronous version"""
        pass
    
    async def async_sync_fabric_from_git(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Asynchronous version for future real-time features"""
        pass
```

## Testing Strategy

### Unit Testing
```python
# Test services in isolation with mocked dependencies
class TestGitSyncService:
    def test_sync_fabric_success(self):
        # Mock git service
        mock_git_service = Mock(spec=GitServiceInterface)
        
        # Create service with mock
        service = GitSyncService(mock_git_service)
        
        # Test business logic
        result = service.sync_fabric_from_git(fabric)
        
        # Verify calls and results
        assert result['created'] == 3
        mock_git_service.clone_repository.assert_called_once()
```

### Integration Testing
```python
# Test complete workflows with real dependencies
class TestFabricSyncWorkflow:
    def test_end_to_end_sync(self):
        # Create test fabric with Git repository
        # Trigger sync through service
        # Verify CRDs created in database
        # Verify Kubernetes resources created
```

### Architecture Testing
```python
# Enforce architectural rules
def test_utils_dont_import_models():
    """Ensure utils directory has no model imports"""
    utils_files = glob.glob('netbox_hedgehog/utils/*.py')
    for file_path in utils_files:
        with open(file_path) as f:
            content = f.read()
            assert 'from ..models' not in content
            assert 'from netbox_hedgehog.models' not in content

def test_views_use_services():
    """Ensure views import from services, not utils"""
    view_files = glob.glob('netbox_hedgehog/views/*.py')
    for file_path in view_files:
        with open(file_path) as f:
            content = f.read()
            # Views should import services
            if 'from ..utils' in content:
                assert 'from ..application.services' in content
```

## Success Metrics

### Architecture Quality
- [ ] Zero circular dependencies detected
- [ ] All utils modules are pure (no model imports)
- [ ] All views delegate to services (no direct utils imports)
- [ ] Service layer handles all business logic
- [ ] Domain layer independent of infrastructure

### System Stability
- [ ] Container runs for 7+ days without restart
- [ ] All existing functionality preserved
- [ ] Performance maintained or improved
- [ ] Memory usage stable or reduced

### Developer Experience
- [ ] New features can be added without touching multiple layers
- [ ] Services can be unit tested in isolation
- [ ] Clear separation of concerns
- [ ] Code is self-documenting through architecture

## Conclusion

This clean architecture design provides a comprehensive solution to the circular dependency issues while establishing a scalable, maintainable foundation. The layered approach ensures proper separation of concerns and enables the system to evolve without architectural constraints.

**Key Benefits:**
1. **Eliminates circular dependencies** through proper layering
2. **Improves testability** through dependency injection
3. **Enhances maintainability** through clear separation of concerns  
4. **Enables future growth** with stable architectural foundation
5. **Preserves existing functionality** through incremental migration

**Next Steps:** Begin implementation with Phase 1 - breaking the circular dependency and establishing the service registry foundation.