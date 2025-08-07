# FGD Sync System Module Breakdown

**Document Version**: 1.0  
**Created**: 2025-08-02  
**Author**: FGD System Architecture Analyst (Agent ID: fgd_architecture_analyst_001)  
**Purpose**: Detailed module breakdown for independent implementation and testing

## Module Overview

This document breaks down the FGD Synchronization System into independently implementable modules, defining clear boundaries, interfaces, and dependencies to enable parallel development and comprehensive testing.

```
Module Dependency Graph:

┌─────────────────────┐
│   Core Framework    │ (No dependencies)
└──────────┬──────────┘
           │
     ┌─────▼─────┐     ┌───────────────┐
     │Event Bus  │     │State Manager  │
     └─────┬─────┘     └───────┬───────┘
           │                   │
     ┌─────▼───────────────────▼─────┐
     │      Sync Orchestrator        │
     └─────────────┬─────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────┐   ┌────▼─────┐   ┌───▼────┐
│Directory│   │Ingestion │   │GitHub  │
│Manager  │   │Pipeline  │   │Client  │
└─────────┘   └──────────┘   └────────┘
                   │
            ┌──────▼──────┐
            │ HNP Bridge  │
            └─────────────┘
```

## Core Modules

### Module 1: Core Framework
**Purpose**: Base infrastructure and common utilities  
**Priority**: P0 - Must be implemented first  
**Estimated Effort**: 3 days

#### Responsibilities
- Configuration management
- Logging infrastructure
- Base exception classes
- Common utilities and helpers
- Database models for sync operations

#### Interfaces
```python
# Configuration Interface
class FGDConfig:
    """Central configuration for FGD system"""
    
    # Sync settings
    SYNC_TIMEOUT: int = 300  # seconds
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_BACKOFF_FACTOR: float = 2.0
    
    # Performance settings
    BATCH_SIZE: int = 50
    WORKER_POOL_SIZE: int = 4
    CACHE_TTL: int = 300
    
    # Feature flags
    ENABLE_AUTO_REPAIR: bool = True
    ENABLE_PARALLEL_PROCESSING: bool = True
    ENABLE_WEBHOOK_SYNC: bool = False

# Base Exception Classes
class FGDException(Exception):
    """Base exception for FGD system"""
    pass

class FGDValidationError(FGDException):
    """Validation errors"""
    pass

class FGDSyncError(FGDException):
    """Sync operation errors"""
    pass

# Common Utilities
class FGDUtils:
    @staticmethod
    def generate_correlation_id() -> str:
        """Generate unique correlation ID for tracking"""
        
    @staticmethod
    def sanitize_path(path: str) -> Path:
        """Sanitize and validate file paths"""
        
    @staticmethod
    def parse_kubernetes_resource(content: str) -> dict:
        """Parse and validate Kubernetes resource"""
```

#### Dependencies
- Django ORM
- Python standard library
- pydantic for validation

#### Testing Strategy
- Unit tests for all utilities
- Configuration validation tests
- Exception handling tests

---

### Module 2: Event Bus
**Purpose**: Asynchronous event-driven communication  
**Priority**: P0 - Required for orchestration  
**Estimated Effort**: 3 days

#### Responsibilities
- Event publishing and subscription
- Event persistence and replay
- Dead letter queue handling
- Event schema validation

#### Interfaces
```python
# Event Definition
@dataclass
class FGDEvent:
    """Base event class"""
    event_id: str
    event_type: str
    correlation_id: str
    fabric_id: int
    timestamp: datetime
    payload: dict
    metadata: dict = field(default_factory=dict)

# Event Bus Interface
class IEventBus(ABC):
    """Event bus interface for dependency injection"""
    
    @abstractmethod
    async def publish(self, event: FGDEvent) -> None:
        """Publish event to bus"""
        
    @abstractmethod
    async def subscribe(self, event_type: str, handler: Callable) -> str:
        """Subscribe to event type, returns subscription ID"""
        
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events"""

# Event Types
class EventTypes:
    # Lifecycle events
    FABRIC_CREATED = "fabric.created"
    FABRIC_DELETED = "fabric.deleted"
    
    # Sync events
    SYNC_STARTED = "sync.started"
    SYNC_COMPLETED = "sync.completed"
    SYNC_FAILED = "sync.failed"
    
    # Directory events
    DIRECTORY_INITIALIZED = "directory.initialized"
    DIRECTORY_VALIDATED = "directory.validated"
    DIRECTORY_REPAIRED = "directory.repaired"
    
    # File events
    FILES_DISCOVERED = "files.discovered"
    FILE_PROCESSED = "file.processed"
    FILE_FAILED = "file.failed"
```

#### Dependencies
- Core Framework
- Redis (for distributed events)
- Django signals

#### Testing Strategy
- Unit tests for event handling
- Integration tests with Redis
- Event replay tests
- Performance tests for high throughput

---

### Module 3: State Manager
**Purpose**: Centralized state management and persistence  
**Priority**: P0 - Required for orchestration  
**Estimated Effort**: 4 days

#### Responsibilities
- Sync state tracking
- State transitions and validation
- State persistence and recovery
- Distributed lock management

#### Interfaces
```python
# State Definition
class SyncState(Enum):
    """Sync workflow states"""
    PENDING = "pending"
    INITIALIZING = "initializing"
    VALIDATING = "validating"
    DISCOVERING = "discovering"
    PROCESSING = "processing"
    SYNCING = "syncing"
    RECONCILING = "reconciling"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

# State Manager Interface
class IStateManager(ABC):
    """State management interface"""
    
    @abstractmethod
    async def get_current_state(self, fabric_id: int) -> SyncState:
        """Get current sync state"""
        
    @abstractmethod
    async def transition_to(
        self, 
        fabric_id: int, 
        new_state: SyncState, 
        context: dict
    ) -> bool:
        """Transition to new state with validation"""
        
    @abstractmethod
    async def get_state_history(
        self, 
        fabric_id: int, 
        limit: int = 10
    ) -> List[StateTransition]:
        """Get state transition history"""

# Lock Manager Interface
class ILockManager(ABC):
    """Distributed lock management"""
    
    @abstractmethod
    async def acquire_lock(
        self, 
        resource_id: str, 
        timeout: int = 30
    ) -> AsyncContextManager:
        """Acquire distributed lock"""
        
    @abstractmethod
    async def is_locked(self, resource_id: str) -> bool:
        """Check if resource is locked"""
```

#### Dependencies
- Core Framework
- PostgreSQL (for state persistence)
- Redis (for distributed locks)

#### Testing Strategy
- State transition tests
- Concurrent access tests
- Lock timeout tests
- State recovery tests

---

### Module 4: Sync Orchestrator
**Purpose**: Central coordination engine  
**Priority**: P1 - Core orchestration logic  
**Estimated Effort**: 5 days

#### Responsibilities
- Workflow orchestration
- Error handling and recovery
- Retry logic implementation
- Progress tracking

#### Interfaces
```python
# Orchestrator Interface
class ISyncOrchestrator(ABC):
    """Sync orchestration interface"""
    
    @abstractmethod
    async def start_sync(
        self, 
        fabric_id: int, 
        trigger: str,
        options: dict = None
    ) -> str:
        """Start sync operation, returns sync_id"""
        
    @abstractmethod
    async def get_sync_status(self, sync_id: str) -> SyncStatus:
        """Get current sync status"""
        
    @abstractmethod
    async def cancel_sync(self, sync_id: str) -> bool:
        """Cancel running sync operation"""

# Sync Context
@dataclass
class SyncContext:
    """Context for sync operation"""
    sync_id: str
    fabric_id: int
    trigger: str
    options: dict
    start_time: datetime
    correlation_id: str
    
    # Runtime state
    current_stage: str = ""
    processed_files: int = 0
    total_files: int = 0
    errors: List[dict] = field(default_factory=list)
    warnings: List[dict] = field(default_factory=list)

# Workflow Stage Interface
class IWorkflowStage(ABC):
    """Interface for workflow stages"""
    
    @abstractmethod
    async def execute(self, context: SyncContext) -> StageResult:
        """Execute workflow stage"""
        
    @abstractmethod
    def can_retry(self, error: Exception) -> bool:
        """Check if stage can be retried"""
```

#### Dependencies
- Core Framework
- Event Bus
- State Manager
- All processing modules

#### Testing Strategy
- Workflow execution tests
- Error recovery tests
- Cancellation tests
- Integration tests with all modules

---

### Module 5: Enhanced Directory Manager
**Purpose**: GitOps directory structure management  
**Priority**: P1 - Required for sync operations  
**Estimated Effort**: 4 days

#### Responsibilities
- Directory structure validation
- Automatic repair capabilities
- Directory initialization
- Change detection

#### Interfaces
```python
# Directory Manager Interface
class IDirectoryManager(ABC):
    """Directory management interface"""
    
    @abstractmethod
    async def validate_structure(self, fabric_id: int) -> ValidationResult:
        """Validate directory structure"""
        
    @abstractmethod
    async def initialize_structure(self, fabric_id: int) -> InitResult:
        """Initialize directory structure"""
        
    @abstractmethod
    async def repair_structure(
        self, 
        fabric_id: int, 
        issues: List[str]
    ) -> RepairResult:
        """Repair directory structure issues"""
        
    @abstractmethod
    async def detect_changes(
        self, 
        fabric_id: int, 
        since: datetime = None
    ) -> List[FileChange]:
        """Detect file changes since timestamp"""

# Validation Result
@dataclass
class ValidationResult:
    """Directory validation result"""
    is_valid: bool
    issues: List[ValidationIssue]
    directory_stats: dict
    
@dataclass
class ValidationIssue:
    """Single validation issue"""
    severity: str  # "error", "warning", "info"
    path: str
    message: str
    can_auto_repair: bool
```

#### Dependencies
- Core Framework
- Event Bus
- File system access

#### Testing Strategy
- Structure validation tests
- Repair capability tests
- Concurrent access tests
- Permission handling tests

---

### Module 6: File Ingestion Pipeline
**Purpose**: Process YAML files from raw/ to managed/  
**Priority**: P1 - Core processing logic  
**Estimated Effort**: 5 days

#### Responsibilities
- File discovery and scanning
- YAML parsing and validation
- Content normalization
- File movement and archival

#### Interfaces
```python
# Ingestion Pipeline Interface
class IIngestionPipeline(ABC):
    """File ingestion interface"""
    
    @abstractmethod
    async def discover_files(self, fabric_id: int) -> List[Path]:
        """Discover files for processing"""
        
    @abstractmethod
    async def process_file(
        self, 
        file_path: Path, 
        context: SyncContext
    ) -> FileResult:
        """Process single file"""
        
    @abstractmethod
    async def process_batch(
        self, 
        files: List[Path], 
        context: SyncContext
    ) -> BatchResult:
        """Process batch of files"""

# File Processing Result
@dataclass
class FileResult:
    """Result of file processing"""
    file_path: Path
    status: str  # "success", "failed", "skipped"
    documents_extracted: int
    target_files: List[Path]
    errors: List[str]
    processing_time: float

# Validation Rules
class ValidationRules:
    """Configurable validation rules"""
    
    REQUIRED_FIELDS = ["apiVersion", "kind", "metadata"]
    SUPPORTED_KINDS = {
        "VPC", "Connection", "Switch", "Server",
        "External", "VPCAttachment", "VPCPeering"
    }
    MAX_DOCUMENT_SIZE = 1024 * 1024  # 1MB
```

#### Dependencies
- Core Framework
- Event Bus
- PyYAML
- File system access

#### Testing Strategy
- YAML parsing tests
- Validation rule tests
- Multi-document file tests
- Error handling tests
- Performance tests with large files

---

### Module 7: GitHub Sync Client
**Purpose**: GitHub repository integration  
**Priority**: P2 - Required for GitHub sync  
**Estimated Effort**: 4 days

#### Responsibilities
- GitHub API integration
- File CRUD operations
- Change detection
- Commit management

#### Interfaces
```python
# GitHub Client Interface
class IGitHubClient(ABC):
    """GitHub integration interface"""
    
    @abstractmethod
    async def test_connection(self, fabric_id: int) -> bool:
        """Test GitHub connectivity"""
        
    @abstractmethod
    async def get_files(
        self, 
        path: str, 
        branch: str = None
    ) -> List[FileInfo]:
        """Get files from repository"""
        
    @abstractmethod
    async def create_or_update_file(
        self, 
        path: str, 
        content: str, 
        message: str
    ) -> CommitResult:
        """Create or update file"""
        
    @abstractmethod
    async def detect_changes(
        self, 
        since_commit: str
    ) -> ChangeSet:
        """Detect changes since commit"""

# Change Detection
@dataclass
class ChangeSet:
    """Set of detected changes"""
    added_files: List[str]
    modified_files: List[str]
    deleted_files: List[str]
    base_commit: str
    head_commit: str
```

#### Dependencies
- Core Framework
- Event Bus
- requests/httpx
- PyGithub (optional)

#### Testing Strategy
- API integration tests
- Mock GitHub responses
- Rate limiting tests
- Error handling tests

---

### Module 8: HNP Integration Bridge
**Purpose**: Integration with existing HNP systems  
**Priority**: P2 - Required for HNP integration  
**Estimated Effort**: 3 days

#### Responsibilities
- Fabric model integration
- Signal handling
- View integration
- Database record management

#### Interfaces
```python
# HNP Bridge Interface
class IHNPBridge(ABC):
    """HNP integration interface"""
    
    @abstractmethod
    def register_fabric_signals(self) -> None:
        """Register Django signals for fabric events"""
        
    @abstractmethod
    async def update_fabric_sync_status(
        self, 
        fabric_id: int, 
        status: dict
    ) -> None:
        """Update fabric sync status"""
        
    @abstractmethod
    async def create_hedgehog_resources(
        self, 
        fabric_id: int, 
        resources: List[dict]
    ) -> List[int]:
        """Create HedgehogResource records"""

# Signal Handlers
def handle_fabric_created(sender, instance, created, **kwargs):
    """Handle fabric creation signal"""
    if created and instance.git_repository:
        # Trigger FGD initialization
        trigger_fgd_sync.delay(instance.id, 'fabric_created')

def handle_fabric_deleted(sender, instance, **kwargs):
    """Handle fabric deletion signal"""
    # Cleanup FGD resources
    cleanup_fgd_resources.delay(instance.id)
```

#### Dependencies
- Core Framework
- Django models
- Celery

#### Testing Strategy
- Signal handling tests
- Database integration tests
- Transaction tests
- View integration tests

---

### Module 9: Monitoring & Health
**Purpose**: System monitoring and health checks  
**Priority**: P3 - Production readiness  
**Estimated Effort**: 3 days

#### Responsibilities
- Health check endpoints
- Metrics collection
- Performance monitoring
- Alerting integration

#### Interfaces
```python
# Health Check Interface
class IHealthChecker(ABC):
    """Health checking interface"""
    
    @abstractmethod
    async def check_health(self) -> HealthStatus:
        """Perform comprehensive health check"""
        
    @abstractmethod
    async def check_component(
        self, 
        component: str
    ) -> ComponentHealth:
        """Check specific component health"""

# Metrics Interface
class IMetricsCollector(ABC):
    """Metrics collection interface"""
    
    @abstractmethod
    def record_sync_duration(
        self, 
        fabric_id: int, 
        duration: float
    ) -> None:
        """Record sync operation duration"""
        
    @abstractmethod
    def increment_counter(
        self, 
        metric: str, 
        labels: dict = None
    ) -> None:
        """Increment counter metric"""
```

#### Dependencies
- Core Framework
- Prometheus client
- Django health check

#### Testing Strategy
- Health check endpoint tests
- Metrics collection tests
- Alert condition tests

---

### Module 10: Error Recovery System
**Purpose**: Comprehensive error handling and recovery  
**Priority**: P3 - Production hardening  
**Estimated Effort**: 3 days

#### Responsibilities
- Error classification
- Retry policies
- Circuit breaker implementation
- Recovery strategies

#### Interfaces
```python
# Error Handler Interface
class IErrorHandler(ABC):
    """Error handling interface"""
    
    @abstractmethod
    def classify_error(self, error: Exception) -> ErrorClass:
        """Classify error type"""
        
    @abstractmethod
    async def handle_error(
        self, 
        error: Exception, 
        context: dict
    ) -> ErrorResult:
        """Handle error with recovery"""

# Retry Policy
@dataclass
class RetryPolicy:
    """Configurable retry policy"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    retryable_errors: List[Type[Exception]] = field(
        default_factory=lambda: [
            ConnectionError,
            TimeoutError,
            FGDTransientError
        ]
    )
```

#### Dependencies
- Core Framework
- Event Bus

#### Testing Strategy
- Error classification tests
- Retry mechanism tests
- Circuit breaker tests
- Recovery strategy tests

## Implementation Phases

### Phase 1: Foundation (Week 1)
1. **Core Framework** - Base infrastructure
2. **Event Bus** - Communication layer
3. **State Manager** - State tracking

### Phase 2: Core Logic (Week 2)
4. **Sync Orchestrator** - Workflow engine
5. **Directory Manager** - Structure management
6. **Ingestion Pipeline** - File processing

### Phase 3: Integration (Week 3)
7. **GitHub Client** - External integration
8. **HNP Bridge** - System integration

### Phase 4: Production (Week 4)
9. **Monitoring & Health** - Observability
10. **Error Recovery** - Resilience

## Testing Strategy

### Unit Testing
- Each module has comprehensive unit tests
- Minimum 80% code coverage
- Mock external dependencies

### Integration Testing
```python
# Example integration test
async def test_full_sync_workflow():
    """Test complete sync workflow"""
    # 1. Setup test fabric with GitHub repo
    fabric = create_test_fabric()
    
    # 2. Initialize FGD structure
    orchestrator = SyncOrchestrator(fabric)
    sync_id = await orchestrator.start_sync(
        fabric.id, 
        'test_trigger'
    )
    
    # 3. Wait for completion
    status = await wait_for_sync_completion(sync_id)
    
    # 4. Verify results
    assert status.state == SyncState.COMPLETED
    assert status.files_processed > 0
    assert status.errors == []
```

### Performance Testing
- Load testing with 100+ concurrent syncs
- Stress testing with large file sets
- Memory leak detection
- Response time validation

### Chaos Testing
- Network failure simulation
- GitHub API unavailability
- Database connection loss
- Concurrent modification conflicts

## Module Communication

### Event Flow Example
```
User triggers sync → HNP Bridge
    ↓
    publishes SYNC_REQUESTED event
    ↓
Event Bus → Sync Orchestrator
    ↓
    starts workflow, publishes SYNC_STARTED
    ↓
Directory Manager validates structure
    ↓
    publishes DIRECTORY_VALIDATED
    ↓
Ingestion Pipeline processes files
    ↓
    publishes FILE_PROCESSED events
    ↓
GitHub Client syncs changes
    ↓
    publishes SYNC_COMPLETED
    ↓
HNP Bridge updates fabric status
```

## Configuration Management

### Module Configuration
```yaml
# fgd_config.yaml
core:
  log_level: INFO
  correlation_id_header: X-Correlation-ID

event_bus:
  backend: redis
  redis_url: redis://localhost:6379/1
  max_retries: 3

state_manager:
  state_timeout: 300
  lock_timeout: 30
  history_retention_days: 30

sync_orchestrator:
  max_concurrent_syncs: 10
  default_timeout: 300
  enable_auto_retry: true

directory_manager:
  enable_auto_repair: true
  validation_strict_mode: false

ingestion_pipeline:
  batch_size: 50
  worker_pool_size: 4
  max_file_size_mb: 10

github_client:
  rate_limit_buffer: 100
  connection_timeout: 30
  read_timeout: 60
```

## Deployment Considerations

### Module Dependencies
- Each module packaged as separate Django app
- Clear dependency declarations in setup.py
- Version compatibility matrix maintained

### Database Migrations
```python
# Each module provides migrations
class Migration(migrations.Migration):
    dependencies = [
        ('netbox_hedgehog', '0001_initial'),
        ('fgd_core', '0001_initial'),
    ]
    
    operations = [
        migrations.CreateModel(
            name='SyncState',
            fields=[
                # State tracking fields
            ],
        ),
    ]
```

### Service Registration
```python
# In Django app config
class FGDSyncConfig(AppConfig):
    name = 'netbox_hedgehog.fgd_sync'
    
    def ready(self):
        # Register event handlers
        from . import signals
        
        # Initialize services
        from .services import initialize_fgd_services
        initialize_fgd_services()
```

## Conclusion

This modular breakdown enables:
- Parallel development by multiple teams
- Independent testing of each module
- Gradual rollout with feature flags
- Easy maintenance and updates
- Clear ownership boundaries

Each module is designed to be self-contained with well-defined interfaces, making the system maintainable and extensible for future enhancements.