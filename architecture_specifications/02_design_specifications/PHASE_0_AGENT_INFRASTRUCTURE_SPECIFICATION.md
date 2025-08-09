# Phase 0: Agent Infrastructure Foundation Specification

**Document Type**: Technical Implementation Specification  
**Phase**: 0 - Infrastructure Foundation  
**Priority**: Immediate (Days 1-2)  
**System Architect**: Approved  
**Status**: Implementation Ready  

---

## Executive Summary

Phase 0 establishes the machine-readable contract framework and single-command development environment that eliminates the 70% reverse-engineering burden blocking agent productivity. This foundational infrastructure enables agents to begin productive implementation work within 5 minutes rather than hours of environment setup and code archaeology.

## Strategic Objectives

**Primary Goal**: Transform agent experience from detective-developer to implementation-focused builder  
**Success Metric**: Agent productivity improves from 30% to 60% success rate in Phase 0 alone  
**Foundation**: Machine-readable contracts eliminate ambiguity and hidden dependencies  

---

## Technical Implementation Requirements

### 1. Machine-Readable Contract Framework

#### 1.1 OpenAPI 3.0 Specification Framework
```yaml
# netbox_hedgehog/contracts/api_contracts.yaml
openapi: 3.0.0
info:
  title: NetBox Hedgehog Plugin API
  version: 1.0.0
  description: Machine-readable API contracts for agent productivity

paths:
  /api/plugins/hedgehog/fabrics/:
    get:
      summary: List Hedgehog fabrics
      parameters:
        - name: status
          in: query
          description: Filter by sync status
          schema:
            type: string
            enum: [never_synced, syncing, synced, error]
      responses:
        200:
          description: List of fabrics with complete metadata
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/HedgehogFabric'

components:
  schemas:
    HedgehogFabric:
      type: object
      required: [name, kubeconfig_file_path]
      properties:
        id:
          type: integer
          readOnly: true
        name:
          type: string
          maxLength: 100
          description: "Unique identifier for the fabric"
        kubeconfig_file_path:
          type: string
          description: "Path to kubernetes configuration"
        sync_interval:
          type: integer
          minimum: 0
          description: "Sync interval in seconds (0 disables auto-sync)"
        sync_status:
          type: string
          enum: [never_synced, syncing, synced, error]
          readOnly: true
```

**Implementation Requirements**:
- [ ] Generate OpenAPI specs for all existing REST endpoints
- [ ] Implement automated API documentation generation
- [ ] Add request/response validation middleware
- [ ] Create CI validation pipeline for contract compliance

#### 1.2 Pydantic Data Models
```python
# netbox_hedgehog/contracts/validation_models.py
from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import Optional, List
from datetime import datetime

class SyncStatusEnum(str, Enum):
    NEVER_SYNCED = "never_synced"
    SYNCING = "syncing"  
    SYNCED = "synced"
    ERROR = "error"

class HedgehogFabricModel(BaseModel):
    """Machine-readable fabric model with validation"""
    
    name: str = Field(
        ..., 
        max_length=100,
        description="Unique fabric identifier"
    )
    kubeconfig_file_path: str = Field(
        ...,
        description="Path to kubernetes configuration file"
    )
    sync_interval: int = Field(
        300,
        ge=0,
        description="Sync interval in seconds (0 disables automatic sync)"
    )
    sync_status: SyncStatusEnum = Field(
        SyncStatusEnum.NEVER_SYNCED,
        description="Current synchronization status"
    )
    
    @validator('kubeconfig_file_path')
    def validate_kubeconfig_path(cls, v):
        """Validate kubeconfig file accessibility"""
        if not v or not v.strip():
            raise ValueError("kubeconfig_file_path cannot be empty")
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "name": "development-cluster",
                "kubeconfig_file_path": "/opt/netbox/kubeconfig/dev-cluster.yaml",
                "sync_interval": 300,
                "sync_status": "synced"
            }
        }

class SyncResult(BaseModel):
    """Standard result format for all sync operations"""
    
    success: bool = Field(..., description="Whether sync operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    affected_resources: List[str] = Field(
        default_factory=list,
        description="List of resource types that were modified"
    )
    error_details: Optional[List[str]] = Field(
        None,
        description="Detailed error information when success=False"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the sync operation completed"
    )
```

#### 1.3 typing.Protocol Service Interfaces
```python
# netbox_hedgehog/contracts/service_protocols.py
from typing import Protocol, List, Optional
from .validation_models import HedgehogFabricModel, SyncResult

class GitOpsSyncService(Protocol):
    """Machine-readable contract for GitOps sync operations"""
    
    def sync_fabric(self, fabric: HedgehogFabricModel) -> SyncResult:
        """
        Synchronize fabric with git repository
        
        Args:
            fabric: Validated fabric model with all required fields
            
        Returns:
            SyncResult with success/failure details
            
        Raises:
            ConnectionError: When fabric is unreachable
            ValidationError: When fabric configuration is invalid
        """
        ...
    
    def validate_crd_data(self, data: dict) -> SyncResult:
        """
        Validate CRD data against kubernetes schemas
        
        Args:
            data: Raw CRD data dictionary
            
        Returns:
            SyncResult indicating validation success/failure with details
        """
        ...

class FabricManagementService(Protocol):
    """Machine-readable contract for fabric management operations"""
    
    def get_fabric_count(self) -> int:
        """Return total number of active fabrics"""
        ...
    
    def get_fabric_by_name(self, name: str) -> Optional[HedgehogFabricModel]:
        """Retrieve fabric by unique name"""
        ...
    
    def update_fabric_status(self, fabric_id: int, status: SyncStatusEnum) -> bool:
        """Update fabric sync status atomically"""
        ...
```

#### 1.4 django-fsm State Machine Definitions
```python
# netbox_hedgehog/contracts/state_machines.py
from django_fsm import FSMField, transition
from .validation_models import SyncStatusEnum

class FabricSyncStateMachine:
    """Explicit state transitions for fabric sync operations"""
    
    sync_status = FSMField(
        default=SyncStatusEnum.NEVER_SYNCED,
        choices=[(status.value, status.value) for status in SyncStatusEnum]
    )
    
    @transition(
        field=sync_status,
        source=SyncStatusEnum.NEVER_SYNCED,
        target=SyncStatusEnum.SYNCING
    )
    def start_initial_sync(self):
        """Begin first-time fabric synchronization"""
        pass
    
    @transition(
        field=sync_status,
        source=[SyncStatusEnum.SYNCED, SyncStatusEnum.ERROR],
        target=SyncStatusEnum.SYNCING  
    )
    def start_resync(self):
        """Begin subsequent synchronization"""
        pass
    
    @transition(
        field=sync_status,
        source=SyncStatusEnum.SYNCING,
        target=SyncStatusEnum.SYNCED
    )
    def complete_sync_success(self):
        """Mark synchronization as successful"""
        pass
    
    @transition(
        field=sync_status,
        source=SyncStatusEnum.SYNCING,
        target=SyncStatusEnum.ERROR
    )
    def complete_sync_error(self):
        """Mark synchronization as failed"""
        pass
```

### 2. Single-Command Development Environment

#### 2.1 Development Setup Makefile
```makefile
# Makefile - Single command agent productivity setup
.PHONY: dev-setup dev-clean dev-status test-env

dev-setup: ## Complete development environment in <5 minutes
	@echo "🚀 Setting up NetBox Hedgehog Plugin development environment..."
	
	# 1. Environment validation
	@command -v docker >/dev/null 2>&1 || (echo "❌ Docker required but not installed" && exit 1)
	@command -v docker-compose >/dev/null 2>&1 || (echo "❌ Docker-compose required but not installed" && exit 1)
	
	# 2. Create environment file with defaults
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env file with development defaults..."; \
		cp .env.example .env; \
	fi
	
	# 3. Start development containers
	@echo "🐳 Starting NetBox development containers..."
	docker-compose -f docker-compose.dev.yml up -d --build
	
	# 4. Wait for database readiness
	@echo "⏳ Waiting for database initialization..."
	@timeout=60; while [ $$timeout -gt 0 ]; do \
		if docker-compose -f docker-compose.dev.yml exec -T postgres pg_isready -U netbox 2>/dev/null; then \
			break; \
		fi; \
		sleep 2; \
		timeout=$$((timeout-2)); \
	done
	
	# 5. Run migrations and create superuser
	@echo "📊 Running database migrations..."
	docker-compose -f docker-compose.dev.yml exec netbox python manage.py migrate
	
	# 6. Create development superuser
	@echo "👤 Creating development superuser (admin/admin)..."
	docker-compose -f docker-compose.dev.yml exec netbox python manage.py shell -c \
		"from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@localhost', 'admin')"
	
	# 7. Load test data
	@echo "🎯 Loading test data..."
	docker-compose -f docker-compose.dev.yml exec netbox python manage.py loaddata test_fixtures.json
	
	# 8. Final status check
	@$(MAKE) dev-status
	
	@echo "✅ Development environment ready!"
	@echo "🌐 NetBox: http://localhost:8000 (admin/admin)"
	@echo "📚 API Docs: http://localhost:8000/api/docs/"
	@echo "⚡ Agent can now begin productive work!"

dev-status: ## Check development environment health
	@echo "🔍 Development Environment Status:"
	@echo "NetBox: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/ | grep -q 200 && echo '✅ Running' || echo '❌ Not available')"
	@echo "Database: $$(docker-compose -f docker-compose.dev.yml exec -T postgres pg_isready -U netbox 2>/dev/null && echo '✅ Ready' || echo '❌ Not ready')"
	@echo "Redis: $$(docker-compose -f docker-compose.dev.yml exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && echo '✅ Connected' || echo '❌ Not connected')"

dev-clean: ## Clean development environment
	@echo "🧹 Cleaning development environment..."
	docker-compose -f docker-compose.dev.yml down -v
	docker system prune -f
	
test-env: ## Validate test environment setup
	@echo "🧪 Running environment validation tests..."
	docker-compose -f docker-compose.dev.yml exec netbox python manage.py test netbox_hedgehog.tests.framework.test_environment_setup
```

#### 2.2 Docker Compose Development Configuration
```yaml
# docker-compose.dev.yml - Agent-optimized development environment
version: '3.8'

services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: netbox
      POSTGRES_USER: netbox
      POSTGRES_PASSWORD: netbox
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U netbox"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  netbox:
    build:
      context: .
      dockerfile: Dockerfile.dev
    environment:
      DB_HOST: postgres
      DB_NAME: netbox
      DB_USER: netbox
      DB_PASSWORD: netbox
      REDIS_HOST: redis
      SECRET_KEY: development-secret-key-not-for-production
      DEBUG: "True"
      ALLOWED_HOSTS: "*"
    volumes:
      - ./netbox_hedgehog:/opt/netbox/netbox_hedgehog:ro
      - ./tests:/opt/netbox/tests:ro
      - kubeconfig_volume:/opt/netbox/kubeconfig
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
  kubeconfig_volume:
```

#### 2.3 Test Data Fixtures
```json
# test_fixtures.json - Pre-configured development data
[
  {
    "model": "netbox_hedgehog.hedgehogfabric",
    "pk": 1,
    "fields": {
      "name": "development-cluster",
      "kubeconfig_file_path": "/opt/netbox/kubeconfig/dev-cluster.yaml",
      "sync_interval": 300,
      "sync_status": "synced",
      "description": "Development environment fabric for agent testing"
    }
  },
  {
    "model": "netbox_hedgehog.gitrepository", 
    "pk": 1,
    "fields": {
      "name": "hedgehog-dev-configs",
      "url": "https://github.com/example/dev-configs.git",
      "branch": "main",
      "description": "Development configuration repository"
    }
  },
  {
    "model": "netbox_hedgehog.vpc",
    "pk": 1,
    "fields": {
      "name": "test-vpc-001",
      "fabric": 1,
      "cidr_block": "10.0.0.0/16",
      "description": "Test VPC for development"
    }
  }
]
```

### 3. Contract Enforcement CI Pipeline

#### 3.1 GitHub Actions Workflow
```yaml
# .github/workflows/contract-validation.yml
name: Contract Validation

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  validate-contracts:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install openapi-spec-validator pydantic[email]
    
    - name: Validate OpenAPI Specifications
      run: |
        python -m openapi_spec_validator netbox_hedgehog/contracts/api_contracts.yaml
    
    - name: Validate Pydantic Models
      run: |
        python -c "
        from netbox_hedgehog.contracts.validation_models import *
        print('✅ All Pydantic models validate successfully')
        "
    
    - name: Type Check Service Protocols
      run: |
        pip install mypy
        mypy netbox_hedgehog/contracts/service_protocols.py --strict
    
    - name: Test Contract Implementation Compliance
      run: |
        python manage.py test netbox_hedgehog.tests.framework.test_contract_compliance
```

---

## Implementation Checklist

### Phase 0.1: Contract Framework (Day 1)
- [ ] Create `netbox_hedgehog/contracts/` directory structure
- [ ] Implement OpenAPI 3.0 specifications for existing endpoints
- [ ] Create Pydantic validation models for core entities
- [ ] Define typing.Protocol interfaces for service contracts
- [ ] Implement django-fsm state machine definitions

### Phase 0.2: Development Environment (Day 1-2)
- [ ] Create Makefile with `make dev-setup` command
- [ ] Build Docker Compose development configuration
- [ ] Create test data fixtures for immediate productivity
- [ ] Implement environment health checks
- [ ] Create development documentation

### Phase 0.3: CI Integration (Day 2)
- [ ] Set up GitHub Actions contract validation workflow
- [ ] Implement automated OpenAPI validation
- [ ] Add Pydantic model testing
- [ ] Create type checking pipeline for Protocol interfaces
- [ ] Add contract compliance test suite

---

## Success Validation Criteria

### Agent Productivity Metrics
1. **Environment Setup Time**: <5 minutes (vs 2-4 hours previously)
2. **Contract Discovery Time**: 0 minutes (vs 30-60 minutes reverse-engineering)
3. **Implementation Error Rate**: <10% (vs 60% integration failures)
4. **Agent Success Rate**: 60% (Phase 0 target, up from 30% baseline)

### Technical Quality Metrics
1. **Contract Coverage**: 90% of services have typed interfaces
2. **API Specification Accuracy**: 100% of endpoints documented
3. **Validation Compliance**: Zero runtime validation failures
4. **Type Safety**: Full typing.Protocol coverage for service boundaries

### Implementation Validation Tests
```python
# Test that agents can begin work immediately
def test_agent_productivity_setup():
    # Verify <5 minute setup
    assert environment_setup_time() < 300  # 5 minutes
    
    # Verify contract availability
    assert all_service_contracts_available()
    
    # Verify test data readiness
    assert test_fixtures_loaded()
    
    # Verify API documentation accessible
    assert api_docs_generated()
```

---

## Integration with Existing System

### Backward Compatibility
- All existing functionality remains unchanged
- Contracts supplement, don't replace existing patterns
- Gradual migration path for legacy components
- Zero breaking changes to current API consumers

### Development Workflow Enhancement
- Agents reference machine-readable contracts first
- IDE support through typing.Protocol interfaces  
- Automated validation prevents specification drift
- Self-documenting code through Pydantic models

---

## Next Phase Preparation

Phase 0 establishes the foundation for:
- **Phase 1**: Agent-readable specifications (Days 2-3)
- **Phase 2**: Architecture documentation with contract integration (Week 1)
- **Phase 3**: Contract-first refactoring (Weeks 2-3)
- **Phase 4**: SPARC 2.0 with telemetry validation (Weeks 3-4)

**Phase 0 Success enables**: Agent productivity improvement from 30% to 60%, setting foundation for final 80% target in Phase 4.

---

**Document Status**: Ready for Implementation  
**Approval**: System Architect Approved  
**Priority**: Immediate - Begin Day 1  
**Agent Impact**: Transforms 70% reverse-engineering burden into 0-minute contract-based development