# FGD Sync System Interface Specifications

**Document Version**: 1.0  
**Created**: 2025-08-02  
**Author**: FGD System Architecture Analyst (Agent ID: fgd_architecture_analyst_001)  
**Purpose**: Detailed interface specifications for all system components

## Overview

This document provides comprehensive interface specifications for the FGD Synchronization System, defining all API contracts, data models, event schemas, and integration points to ensure consistent implementation across all modules.

## API Contracts

### REST API Endpoints

#### Sync Management APIs

```python
# Trigger Sync Operation
POST /api/plugins/hedgehog/fabrics/{fabric_id}/gitops-sync/
Request:
{
    "trigger": "manual",  # "manual", "webhook", "scheduled"
    "options": {
        "force_refresh": false,
        "validate_only": false,
        "include_github_sync": true
    }
}

Response:
{
    "success": true,
    "sync_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "started",
    "message": "Sync operation started",
    "tracking_url": "/api/plugins/hedgehog/sync-status/550e8400-e29b-41d4-a716-446655440000/"
}

# Get Sync Status
GET /api/plugins/hedgehog/sync-status/{sync_id}/
Response:
{
    "sync_id": "550e8400-e29b-41d4-a716-446655440000",
    "fabric_id": 123,
    "state": "processing",
    "progress": {
        "current_stage": "file_ingestion",
        "stages_completed": ["validation", "discovery"],
        "stages_pending": ["github_sync", "reconciliation"],
        "files_processed": 15,
        "total_files": 23,
        "percent_complete": 65
    },
    "started_at": "2025-08-02T10:30:00Z",
    "updated_at": "2025-08-02T10:31:45Z",
    "errors": [],
    "warnings": [
        {
            "code": "INVALID_YAML",
            "message": "File 'config.yaml' contains invalid YAML syntax",
            "file": "/raw/config.yaml"
        }
    ]
}

# Cancel Sync Operation
POST /api/plugins/hedgehog/sync-status/{sync_id}/cancel/
Response:
{
    "success": true,
    "message": "Sync operation cancelled",
    "final_state": "cancelled"
}

# Get Sync History
GET /api/plugins/hedgehog/fabrics/{fabric_id}/sync-history/
Query Parameters:
    - limit: int (default: 10)
    - offset: int (default: 0)
    - status: string (filter by status)
    - start_date: datetime
    - end_date: datetime

Response:
{
    "count": 45,
    "next": "/api/plugins/hedgehog/fabrics/123/sync-history/?limit=10&offset=10",
    "previous": null,
    "results": [
        {
            "sync_id": "550e8400-e29b-41d4-a716-446655440000",
            "trigger": "manual",
            "state": "completed",
            "started_at": "2025-08-02T10:30:00Z",
            "completed_at": "2025-08-02T10:32:15Z",
            "duration_seconds": 135,
            "files_processed": 23,
            "errors": 0,
            "warnings": 1
        }
    ]
}
```

#### Directory Management APIs

```python
# Validate Directory Structure
GET /api/plugins/hedgehog/fabrics/{fabric_id}/gitops-directory/validate/
Response:
{
    "valid": true,
    "issues": [],
    "structure": {
        "raw": {
            "exists": true,
            "file_count": 5,
            "pending_files": 3
        },
        "managed": {
            "exists": true,
            "file_count": 45,
            "subdirectories": ["vpcs", "connections", "switches"]
        },
        "metadata": {
            "exists": true,
            "manifest_valid": true,
            "last_updated": "2025-08-02T09:00:00Z"
        }
    }
}

# Initialize Directory Structure
POST /api/plugins/hedgehog/fabrics/{fabric_id}/gitops-directory/initialize/
Request:
{
    "force": false,  # Force re-initialization
    "create_samples": true  # Create sample files
}

Response:
{
    "success": true,
    "initialized": true,
    "directories_created": [
        "/gitops/raw",
        "/gitops/managed",
        "/gitops/managed/vpcs",
        "/gitops/.hnp"
    ],
    "files_created": [
        "/gitops/.hnp/manifest.yaml",
        "/gitops/raw/README.md"
    ]
}

# Repair Directory Issues
POST /api/plugins/hedgehog/fabrics/{fabric_id}/gitops-directory/repair/
Request:
{
    "issues": ["missing_raw_dir", "invalid_permissions"],
    "auto_detect": true
}

Response:
{
    "success": true,
    "repairs_made": [
        {
            "issue": "missing_raw_dir",
            "action": "created_directory",
            "path": "/gitops/raw"
        }
    ],
    "remaining_issues": []
}
```

#### File Management APIs

```python
# List Files in Directory
GET /api/plugins/hedgehog/fabrics/{fabric_id}/gitops-files/
Query Parameters:
    - directory: string ("raw", "managed", "all")
    - file_type: string ("yaml", "yml", "all")
    - include_content: boolean (default: false)

Response:
{
    "files": [
        {
            "path": "/gitops/raw/vpc-config.yaml",
            "directory": "raw",
            "size": 2048,
            "modified": "2025-08-02T10:00:00Z",
            "valid": true,
            "resource_count": 3,
            "resources": [
                {"kind": "VPC", "name": "vpc-1"},
                {"kind": "VPC", "name": "vpc-2"},
                {"kind": "VPCAttachment", "name": "attach-1"}
            ]
        }
    ],
    "summary": {
        "total_files": 15,
        "valid_files": 14,
        "invalid_files": 1,
        "total_resources": 45
    }
}

# Process Single File
POST /api/plugins/hedgehog/fabrics/{fabric_id}/gitops-files/process/
Request:
{
    "file_path": "/gitops/raw/new-config.yaml",
    "validate_only": false
}

Response:
{
    "success": true,
    "file_path": "/gitops/raw/new-config.yaml",
    "documents_found": 3,
    "documents_processed": 3,
    "files_created": [
        "/gitops/managed/vpcs/vpc-1.yaml",
        "/gitops/managed/vpcs/vpc-2.yaml",
        "/gitops/managed/vpc-attachments/attach-1.yaml"
    ],
    "archived_to": "/gitops/raw/new-config.yaml.archived"
}
```

### WebSocket APIs

```python
# Real-time Sync Progress
WS /ws/plugins/hedgehog/sync-progress/{sync_id}/

# Message Format
{
    "type": "sync.progress",
    "sync_id": "550e8400-e29b-41d4-a716-446655440000",
    "data": {
        "state": "processing",
        "stage": "file_ingestion",
        "progress": 65,
        "current_file": "/gitops/raw/config.yaml",
        "files_processed": 15,
        "total_files": 23
    }
}

# Event Types
- sync.started
- sync.progress
- sync.stage_completed
- sync.file_processed
- sync.error
- sync.warning
- sync.completed
- sync.failed
```

## Data Models

### Core Models

```python
# Sync Operation Model
class FGDSyncOperation(models.Model):
    """Tracks sync operations"""
    
    sync_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    fabric = models.ForeignKey(HedgehogFabric, on_delete=models.CASCADE)
    trigger = models.CharField(max_length=50, choices=[
        ('manual', 'Manual'),
        ('webhook', 'Webhook'),
        ('scheduled', 'Scheduled'),
        ('fabric_created', 'Fabric Created')
    ])
    state = models.CharField(max_length=50, default='pending')
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Progress tracking
    current_stage = models.CharField(max_length=100, blank=True)
    stages_data = models.JSONField(default=dict)
    
    # Results
    files_processed = models.IntegerField(default=0)
    files_created = models.IntegerField(default=0)
    errors = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    
    # Metadata
    correlation_id = models.CharField(max_length=100, unique=True)
    options = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'netbox_hedgehog_fgd_sync_operation'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['fabric', '-started_at']),
            models.Index(fields=['state']),
            models.Index(fields=['correlation_id'])
        ]

# Sync State Transition Model
class FGDSyncStateTransition(models.Model):
    """Tracks state transitions"""
    
    sync_operation = models.ForeignKey(
        FGDSyncOperation, 
        on_delete=models.CASCADE,
        related_name='state_transitions'
    )
    from_state = models.CharField(max_length=50)
    to_state = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    context = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'netbox_hedgehog_fgd_sync_state_transition'
        ordering = ['timestamp']

# File Processing Record Model
class FGDFileRecord(models.Model):
    """Tracks file processing"""
    
    sync_operation = models.ForeignKey(
        FGDSyncOperation,
        on_delete=models.CASCADE,
        related_name='file_records'
    )
    file_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=50)
    status = models.CharField(max_length=50, choices=[
        ('discovered', 'Discovered'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped')
    ])
    
    # Processing details
    documents_found = models.IntegerField(default=0)
    documents_extracted = models.IntegerField(default=0)
    target_files = models.JSONField(default=list)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    validation_errors = models.JSONField(default=list)
    
    # Timestamps
    discovered_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'netbox_hedgehog_fgd_file_record'
        unique_together = [['sync_operation', 'file_path']]
```

### Extended Fabric Model

```python
# Extensions to HedgehogFabric model
class HedgehogFabric(models.Model):
    # Existing fields...
    
    # FGD-specific fields
    gitops_initialized = models.BooleanField(default=False)
    gitops_directory_status = models.CharField(
        max_length=50,
        choices=[
            ('not_initialized', 'Not Initialized'),
            ('initializing', 'Initializing'),
            ('valid', 'Valid'),
            ('invalid', 'Invalid'),
            ('repairing', 'Repairing')
        ],
        default='not_initialized'
    )
    
    # Paths
    raw_directory_path = models.CharField(max_length=500, blank=True)
    managed_directory_path = models.CharField(max_length=500, blank=True)
    
    # Sync tracking
    last_sync_id = models.UUIDField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=50, blank=True)
    
    # Statistics
    total_sync_count = models.IntegerField(default=0)
    successful_sync_count = models.IntegerField(default=0)
    failed_sync_count = models.IntegerField(default=0)
    
    # Configuration
    sync_enabled = models.BooleanField(default=True)
    auto_sync_on_change = models.BooleanField(default=False)
    sync_interval_minutes = models.IntegerField(default=60)
```

## Event Specifications

### Event Schema

```python
# Base Event Schema
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["event_id", "event_type", "timestamp", "fabric_id"],
    "properties": {
        "event_id": {
            "type": "string",
            "format": "uuid"
        },
        "event_type": {
            "type": "string",
            "pattern": "^[a-z]+\\.[a-z]+$"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time"
        },
        "fabric_id": {
            "type": "integer"
        },
        "correlation_id": {
            "type": "string"
        },
        "payload": {
            "type": "object"
        },
        "metadata": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "source": {"type": "string"},
                "version": {"type": "string"}
            }
        }
    }
}
```

### Event Payload Specifications

```python
# sync.started Event
{
    "event_type": "sync.started",
    "payload": {
        "sync_id": "550e8400-e29b-41d4-a716-446655440000",
        "trigger": "manual",
        "options": {
            "force_refresh": false,
            "validate_only": false
        }
    }
}

# directory.validated Event
{
    "event_type": "directory.validated",
    "payload": {
        "valid": true,
        "issues": [],
        "repairs_needed": [],
        "directory_stats": {
            "raw_files": 5,
            "managed_files": 45
        }
    }
}

# file.processed Event
{
    "event_type": "file.processed",
    "payload": {
        "file_path": "/gitops/raw/config.yaml",
        "status": "success",
        "documents_extracted": 3,
        "target_files": [
            "/gitops/managed/vpcs/vpc-1.yaml"
        ],
        "processing_time": 0.245
    }
}

# sync.completed Event
{
    "event_type": "sync.completed",
    "payload": {
        "sync_id": "550e8400-e29b-41d4-a716-446655440000",
        "duration_seconds": 135,
        "files_processed": 23,
        "files_created": 45,
        "errors": 0,
        "warnings": 1,
        "final_state": "completed"
    }
}
```

## Configuration Schema

### FGD Configuration Schema

```yaml
# FGD Configuration Schema (fgd_config.yaml)
fgd:
  # Core settings
  enabled: true
  debug_mode: false
  
  # Sync settings
  sync:
    timeout_seconds: 300
    max_concurrent_syncs: 10
    retry_policy:
      max_attempts: 3
      initial_delay: 1.0
      backoff_factor: 2.0
      max_delay: 60.0
    
  # Directory settings
  directory:
    auto_initialize: true
    auto_repair: true
    validation_mode: "strict"  # "strict", "lenient"
    required_subdirs:
      - "vpcs"
      - "connections"
      - "switches"
    
  # File processing
  ingestion:
    batch_size: 50
    max_file_size_mb: 10
    worker_pool_size: 4
    supported_extensions:
      - ".yaml"
      - ".yml"
    validation_rules:
      enforce_namespaces: true
      require_labels: false
      max_documents_per_file: 100
    
  # GitHub integration
  github:
    enabled: true
    rate_limit_buffer: 100
    connection_timeout: 30
    read_timeout: 60
    webhook_secret: "${GITHUB_WEBHOOK_SECRET}"
    
  # Monitoring
  monitoring:
    metrics_enabled: true
    health_check_interval: 60
    alert_thresholds:
      sync_duration_seconds: 300
      error_rate_percent: 5
      queue_depth: 100
```

### Environment Variables

```bash
# Required Environment Variables
HEDGEHOG_FGD_ENABLED=true
HEDGEHOG_FGD_REDIS_URL=redis://localhost:6379/1
HEDGEHOG_FGD_WORKER_CONCURRENCY=4

# Optional Environment Variables
HEDGEHOG_FGD_DEBUG=false
HEDGEHOG_FGD_SYNC_TIMEOUT=300
HEDGEHOG_FGD_BATCH_SIZE=50
HEDGEHOG_FGD_GITHUB_WEBHOOK_SECRET=your-secret-here
HEDGEHOG_FGD_METRICS_ENABLED=true
```

## Error Contracts

### Error Response Format

```python
# Standard Error Response
{
    "error": {
        "code": "FGD_SYNC_FAILED",
        "message": "Sync operation failed due to GitHub API error",
        "details": {
            "sync_id": "550e8400-e29b-41d4-a716-446655440000",
            "stage": "github_sync",
            "github_error": "API rate limit exceeded"
        },
        "timestamp": "2025-08-02T10:30:00Z",
        "correlation_id": "abc-123-def-456"
    }
}
```

### Error Codes

```python
# FGD Error Codes
class FGDErrorCodes:
    # Validation Errors (1xxx)
    INVALID_YAML = "FGD_1001"
    UNSUPPORTED_RESOURCE = "FGD_1002"
    VALIDATION_FAILED = "FGD_1003"
    SCHEMA_MISMATCH = "FGD_1004"
    
    # Directory Errors (2xxx)
    DIRECTORY_NOT_FOUND = "FGD_2001"
    DIRECTORY_PERMISSION_DENIED = "FGD_2002"
    DIRECTORY_INITIALIZATION_FAILED = "FGD_2003"
    DIRECTORY_REPAIR_FAILED = "FGD_2004"
    
    # Sync Errors (3xxx)
    SYNC_ALREADY_IN_PROGRESS = "FGD_3001"
    SYNC_TIMEOUT = "FGD_3002"
    SYNC_CANCELLED = "FGD_3003"
    SYNC_FAILED = "FGD_3004"
    
    # GitHub Errors (4xxx)
    GITHUB_CONNECTION_FAILED = "FGD_4001"
    GITHUB_AUTHENTICATION_FAILED = "FGD_4002"
    GITHUB_RATE_LIMITED = "FGD_4003"
    GITHUB_NOT_FOUND = "FGD_4004"
    
    # System Errors (5xxx)
    INTERNAL_ERROR = "FGD_5001"
    DATABASE_ERROR = "FGD_5002"
    REDIS_CONNECTION_FAILED = "FGD_5003"
    WORKER_POOL_EXHAUSTED = "FGD_5004"
```

## Integration Contracts

### Django Signal Integration

```python
# FGD Django Signals
from django.dispatch import Signal

# Sync lifecycle signals
fgd_sync_started = Signal()  # sender=FGDSyncOperation
fgd_sync_completed = Signal()  # sender=FGDSyncOperation
fgd_sync_failed = Signal()  # sender=FGDSyncOperation

# Directory management signals
fgd_directory_initialized = Signal()  # sender=HedgehogFabric
fgd_directory_validated = Signal()  # sender=HedgehogFabric
fgd_directory_repaired = Signal()  # sender=HedgehogFabric

# File processing signals
fgd_file_discovered = Signal()  # sender=FGDFileRecord
fgd_file_processed = Signal()  # sender=FGDFileRecord
fgd_file_failed = Signal()  # sender=FGDFileRecord

# Usage Example
@receiver(fgd_sync_completed)
def handle_sync_completed(sender, **kwargs):
    sync_operation = sender
    fabric = sync_operation.fabric
    
    # Update fabric statistics
    fabric.last_sync_at = sync_operation.completed_at
    fabric.last_sync_status = 'completed'
    fabric.successful_sync_count += 1
    fabric.save()
```

### Celery Task Integration

```python
# FGD Celery Tasks
from celery import shared_task

@shared_task(bind=True, max_retries=3)
def trigger_fgd_sync(self, fabric_id: int, trigger: str = 'scheduled'):
    """Trigger FGD sync operation"""
    try:
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        orchestrator = SyncOrchestrator(fabric)
        
        sync_id = orchestrator.start_sync(
            fabric_id=fabric_id,
            trigger=trigger
        )
        
        return {
            'success': True,
            'sync_id': str(sync_id)
        }
        
    except Exception as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

@shared_task
def process_github_webhook(payload: dict):
    """Process GitHub webhook"""
    # Identify affected fabrics
    affected_fabrics = identify_affected_fabrics(payload)
    
    # Trigger sync for each fabric
    for fabric_id in affected_fabrics:
        trigger_fgd_sync.delay(fabric_id, 'webhook')
```

### Prometheus Metrics

```python
# FGD Prometheus Metrics
from prometheus_client import Counter, Histogram, Gauge

# Counters
fgd_sync_total = Counter(
    'fgd_sync_total',
    'Total number of sync operations',
    ['fabric_id', 'trigger', 'status']
)

fgd_files_processed_total = Counter(
    'fgd_files_processed_total',
    'Total number of files processed',
    ['fabric_id', 'file_type', 'status']
)

# Histograms
fgd_sync_duration_seconds = Histogram(
    'fgd_sync_duration_seconds',
    'Duration of sync operations',
    ['fabric_id', 'trigger'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

fgd_file_processing_duration_seconds = Histogram(
    'fgd_file_processing_duration_seconds',
    'Duration of file processing',
    ['fabric_id', 'file_type']
)

# Gauges
fgd_active_syncs = Gauge(
    'fgd_active_syncs',
    'Number of active sync operations'
)

fgd_queue_depth = Gauge(
    'fgd_queue_depth',
    'Number of sync operations in queue'
)
```

## Security Contracts

### Authentication & Authorization

```python
# Permission Classes
class FGDPermissions:
    # View permissions
    VIEW_SYNC_STATUS = 'netbox_hedgehog.view_fgd_sync'
    VIEW_SYNC_HISTORY = 'netbox_hedgehog.view_fgd_history'
    
    # Action permissions
    TRIGGER_SYNC = 'netbox_hedgehog.trigger_fgd_sync'
    CANCEL_SYNC = 'netbox_hedgehog.cancel_fgd_sync'
    CONFIGURE_SYNC = 'netbox_hedgehog.configure_fgd_sync'
    
    # Admin permissions
    REPAIR_DIRECTORY = 'netbox_hedgehog.repair_fgd_directory'
    FORCE_SYNC = 'netbox_hedgehog.force_fgd_sync'

# API View Permission Check
class FGDSyncView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, fabric_id):
        fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
        
        # Check permissions
        if not request.user.has_perm(FGDPermissions.TRIGGER_SYNC, fabric):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
```

### Audit Logging

```python
# Audit Log Entry
class FGDAuditLog(models.Model):
    """Security audit log for FGD operations"""
    
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fabric = models.ForeignKey(HedgehogFabric, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    
    # Request details
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500)
    
    # Operation details
    sync_id = models.UUIDField(null=True, blank=True)
    details = models.JSONField(default=dict)
    
    # Result
    success = models.BooleanField()
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'netbox_hedgehog_fgd_audit_log'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['fabric', '-timestamp'])
        ]
```

## Testing Contracts

### Test Fixtures

```python
# Test Fixture Format
{
    "test_name": "valid_vpc_ingestion",
    "description": "Test ingestion of valid VPC YAML file",
    "input": {
        "file_path": "/gitops/raw/vpc-test.yaml",
        "content": "apiVersion: v1\nkind: VPC\nmetadata:\n  name: test-vpc\nspec:\n  cidr: 10.0.0.0/16"
    },
    "expected": {
        "status": "success",
        "documents_extracted": 1,
        "files_created": ["/gitops/managed/vpcs/test-vpc.yaml"],
        "errors": []
    }
}
```

### Mock Services

```python
# Mock Service Interfaces
class MockGitHubClient:
    """Mock GitHub client for testing"""
    
    def __init__(self, test_scenario='success'):
        self.test_scenario = test_scenario
        self.calls = []
    
    async def get_files(self, path: str, branch: str = None):
        self.calls.append(('get_files', path, branch))
        
        if self.test_scenario == 'success':
            return [
                FileInfo(path=f"{path}/test.yaml", size=1024)
            ]
        elif self.test_scenario == 'rate_limited':
            raise GitHubRateLimitError()
        else:
            raise GitHubConnectionError()

class MockEventBus:
    """Mock event bus for testing"""
    
    def __init__(self):
        self.events = []
    
    async def publish(self, event: FGDEvent):
        self.events.append(event)
    
    def assert_event_published(self, event_type: str):
        assert any(e.event_type == event_type for e in self.events)
```

## Conclusion

These interface specifications provide a complete contract for implementing the FGD Synchronization System. All components must adhere to these specifications to ensure proper integration and functionality. The contracts are designed to be:

- **Type-safe**: With clear data types and validation
- **Versioned**: Supporting future evolution
- **Testable**: With mock interfaces and fixtures
- **Secure**: With proper authentication and audit trails
- **Observable**: With comprehensive metrics and logging

Implementations should reference these specifications and ensure compliance through comprehensive testing.