# GitOps API Endpoints Specification

**Document Type**: API Specification  
**Component**: GitOps Bidirectional Sync API  
**Project**: HNP GitOps Bidirectional Synchronization  
**Author**: Backend Technical Specialist  
**Date**: July 30, 2025  
**Version**: 1.0

## API Overview

This document specifies the REST API endpoints for GitOps bidirectional synchronization functionality. The API provides comprehensive control over directory management, synchronization operations, conflict resolution, and monitoring.

## Base URL and Authentication

**Base URL**: `/api/plugins/hedgehog/`  
**Authentication**: NetBox token-based authentication  
**Content-Type**: `application/json`  
**API Version**: `v1`

## Directory Management API

### 1. Initialize GitOps Directory Structure

**Endpoint**: `POST /api/plugins/hedgehog/fabrics/{fabric_id}/gitops-directories/initialize/`

**Purpose**: Initialize or reinitialize GitOps directory structure for a fabric

**Request Parameters**:
```json
{
    "force_recreate": false,
    "backup_existing": true,
    "structure_template": "standard",
    "create_readme_files": true,
    "initial_commit_message": "Initialize GitOps directory structure"
}
```

**Request Fields**:
- `force_recreate` (boolean, optional): Whether to recreate existing directories. Default: `false`
- `backup_existing` (boolean, optional): Whether to backup existing content. Default: `true`
- `structure_template` (string, optional): Directory structure template. Default: `"standard"`
- `create_readme_files` (boolean, optional): Whether to create README files. Default: `true`
- `initial_commit_message` (string, optional): Custom commit message for initialization

**Response (200 OK)**:
```json
{
    "success": true,
    "message": "Directory structure initialized successfully",
    "operation_id": "init_20250730_123456",
    "directories_created": [
        "raw",
        "raw/pending", 
        "raw/processed",
        "raw/errors",
        "unmanaged",
        "unmanaged/external-configs",
        "unmanaged/manual-overrides",
        "managed",
        "managed/vpcs",
        "managed/connections",
        "managed/switches",
        "managed/servers",
        "managed/externals",
        "managed/metadata"
    ],
    "backup_location": "backup/fabric-test_20250730_123456",
    "commit_info": {
        "commit_sha": "abc123def456",
        "commit_url": "https://github.com/user/repo/commit/abc123def456",
        "files_added": 14
    },
    "structure_validation": {
        "valid": true,
        "issues": []
    },
    "timing": {
        "started_at": "2025-07-30T12:34:56Z",
        "completed_at": "2025-07-30T12:35:12Z",
        "duration_seconds": 16
    }
}
```

**Response (400 Bad Request)**:
```json
{
    "success": false,
    "error": "Directory initialization failed",
    "error_code": "INIT_FAILED",
    "details": {
        "reason": "Repository access denied",
        "github_error": "Bad credentials",
        "suggestions": [
            "Verify repository credentials",
            "Check repository permissions"
        ]
    }
}
```

### 2. Validate Directory Structure

**Endpoint**: `GET /api/plugins/hedgehog/fabrics/{fabric_id}/gitops-directories/validate/`

**Purpose**: Validate current GitOps directory structure

**Response (200 OK)**:
```json
{
    "fabric_id": 123,
    "fabric_name": "production-fabric",
    "initialized": true,
    "structure_valid": true,
    "gitops_directory": "gitops/hedgehog/fabric-1",
    "repository_info": {
        "url": "https://github.com/user/repo.git",
        "branch": "main",
        "connection_status": "connected",
        "last_validated": "2025-07-30T10:30:00Z"
    },
    "directories": {
        "raw": {
            "exists": true,
            "is_directory": true,
            "file_count": 3,
            "subdirectories": {
                "pending": {
                    "exists": true,
                    "is_directory": true,
                    "file_count": 2
                },
                "processed": {
                    "exists": true,
                    "is_directory": true,
                    "file_count": 15
                },
                "errors": {
                    "exists": true,
                    "is_directory": true,
                    "file_count": 1
                }
            }
        },
        "unmanaged": {
            "exists": true,
            "is_directory": true,
            "file_count": 5,
            "subdirectories": {
                "external-configs": {
                    "exists": true,
                    "is_directory": true,
                    "file_count": 3
                },
                "manual-overrides": {
                    "exists": true,
                    "is_directory": true,
                    "file_count": 2
                }
            }
        },
        "managed": {
            "exists": true,
            "is_directory": true,
            "file_count": 12,
            "last_sync": "2025-07-30T10:30:00Z",
            "subdirectories": {
                "vpcs": {
                    "exists": true,
                    "is_directory": true,
                    "file_count": 4
                },
                "connections": {
                    "exists": true,
                    "is_directory": true,
                    "file_count": 6
                },
                "switches": {
                    "exists": true,
                    "is_directory": true,
                    "file_count": 2
                }
            }
        }
    },
    "issues": [],
    "recommendations": [],
    "health_score": 100
}
```

### 3. Ingest Raw Files

**Endpoint**: `POST /api/plugins/hedgehog/fabrics/{fabric_id}/gitops-directories/ingest/`

**Purpose**: Process files from raw/pending directory into managed directory

**Request Parameters**:
```json
{
    "file_patterns": ["*.yaml", "*.yml"],
    "validation_strict": true,
    "archive_processed": true,
    "auto_commit": true,
    "commit_message": "Ingest user-uploaded resources"
}
```

**Response (200 OK)**:
```json
{
    "success": true,
    "message": "File ingestion completed successfully",
    "operation_id": "ingest_20250730_123456",
    "summary": {
        "files_discovered": 3,
        "files_processed": 2,
        "files_archived": 2,
        "files_errored": 1,
        "processing_time_seconds": 4.2
    },
    "results": {
        "processed_files": [
            {
                "source_file": "raw/pending/vpc-config.yaml",
                "target_file": "managed/vpcs/production-vpc.yaml",
                "operation": "created",
                "resources": [
                    {
                        "kind": "VPC",
                        "name": "production-vpc",
                        "action": "created"
                    }
                ]
            },
            {
                "source_file": "raw/pending/connections.yaml", 
                "target_file": "managed/connections/server-connections.yaml",
                "operation": "updated",
                "resources": [
                    {
                        "kind": "Connection",
                        "name": "server-01-connection",
                        "action": "updated"
                    },
                    {
                        "kind": "Connection", 
                        "name": "server-02-connection",
                        "action": "created"
                    }
                ]
            }
        ],
        "errored_files": [
            {
                "source_file": "raw/pending/invalid-config.yaml",
                "error": "YAML parsing error: Invalid syntax at line 5",
                "error_file": "raw/errors/invalid-config_error_20250730_123456.yaml",
                "error_log": "raw/errors/invalid-config_error_20250730_123456.log"
            }
        ]
    },
    "commit_info": {
        "commit_sha": "def456abc789",
        "commit_url": "https://github.com/user/repo/commit/def456abc789",
        "files_changed": 3
    }
}
```

## Synchronization Control API

### 4. Trigger Bidirectional Sync

**Endpoint**: `POST /api/plugins/hedgehog/fabrics/{fabric_id}/sync/`

**Purpose**: Trigger bidirectional synchronization between HNP GUI and GitHub

**Request Parameters**:
```json
{
    "direction": "bidirectional",
    "resource_filters": {
        "kinds": ["VPC", "Connection"],
        "names": ["production-*"],
        "namespaces": ["default"]
    },
    "options": {
        "force_sync": false,
        "create_pr": false,
        "pr_title": "HNP Sync: Update resources",
        "pr_body": "Automated sync from HNP GUI",
        "branch_name": "hnp-sync-20250730"
    },
    "conflict_resolution": {
        "strategy": "user_guided",
        "auto_resolve_simple": true,
        "escalate_complex": true
    },
    "notifications": {
        "email": ["admin@example.com"],
        "webhook_url": "https://api.example.com/webhooks/sync"
    }
}
```

**Request Fields**:
- `direction` (string): `"gui_to_github"`, `"github_to_gui"`, or `"bidirectional"`
- `resource_filters` (object, optional): Filter resources to sync
- `options` (object, optional): Sync operation options
- `conflict_resolution` (object, optional): Conflict resolution configuration
- `notifications` (object, optional): Notification configuration

**Response (202 Accepted)**:
```json
{
    "success": true,
    "message": "Sync operation initiated",
    "operation_id": "sync_20250730_123456",
    "status": "initializing",
    "estimated_duration_seconds": 45,
    "resources_targeted": 24,
    "conflicts_detected": 0,
    "progress": {
        "current_phase": "initialization",
        "phase_progress": 0.1,
        "overall_progress": 0.0
    },
    "monitoring": {
        "status_url": "/api/plugins/hedgehog/sync-operations/sync_20250730_123456/",
        "cancel_url": "/api/plugins/hedgehog/sync-operations/sync_20250730_123456/cancel/",
        "webhook_url": "/api/plugins/hedgehog/sync-operations/sync_20250730_123456/webhook/"
    },
    "next_steps": [
        "Monitor operation status via status_url",
        "Review conflicts if detected",
        "Approve PR if create_pr was enabled"
    ]
}
```

### 5. Get Sync Operation Status

**Endpoint**: `GET /api/plugins/hedgehog/sync-operations/{operation_id}/`

**Purpose**: Get detailed status of a specific sync operation

**Response (200 OK)**:
```json
{
    "operation_id": "sync_20250730_123456",
    "fabric": {
        "id": 123,
        "name": "production-fabric"
    },
    "status": "in_progress",
    "current_phase": "syncing_data",
    "started_at": "2025-07-30T12:34:56Z",
    "estimated_completion": "2025-07-30T12:36:30Z",
    "progress": {
        "overall_progress": 0.65,
        "phase_progress": 0.8,
        "current_operation": "Processing VPC resources",
        "operations_completed": 18,
        "operations_total": 24
    },
    "statistics": {
        "resources_processed": 18,
        "resources_created": 3,
        "resources_updated": 12,
        "resources_deleted": 0,
        "resources_skipped": 3,
        "conflicts_detected": 2,
        "conflicts_resolved": 1,
        "conflicts_pending": 1
    },
    "current_conflicts": [
        {
            "resource_id": 456,
            "resource_name": "production-vpc",
            "conflict_type": "concurrent_modification",
            "severity": "medium",
            "requires_attention": true,
            "resolution_url": "/api/plugins/hedgehog/conflicts/conflict_789/resolve/"
        }
    ],
    "github_integration": {
        "operations_count": 15,
        "rate_limit_remaining": 4985,
        "rate_limit_reset": "2025-07-30T13:00:00Z",
        "commit_sha": "in_progress",
        "branch_name": "hnp-sync-20250730",
        "pull_request_url": null
    },
    "performance_metrics": {
        "api_calls_made": 15,
        "network_transfer_bytes": 245760,
        "memory_usage_mb": 45,
        "processing_time_seconds": 28
    },
    "errors": [],
    "warnings": [
        "Resource server-switch-03 has validation warnings"
    ]
}
```

### 6. Cancel Sync Operation

**Endpoint**: `POST /api/plugins/hedgehog/sync-operations/{operation_id}/cancel/`

**Purpose**: Cancel an active sync operation

**Request Parameters**:
```json
{
    "reason": "User requested cancellation",
    "cleanup_changes": true,
    "notify_users": true
}
```

**Response (200 OK)**:
```json
{
    "success": true,
    "message": "Sync operation cancelled successfully",
    "operation_id": "sync_20250730_123456",
    "cancellation_details": {
        "cancelled_at": "2025-07-30T12:35:30Z",
        "resources_processed_before_cancel": 12,
        "cleanup_performed": true,
        "partial_changes_reverted": true
    },
    "final_status": {
        "status": "cancelled",
        "partial_completion_rate": 0.5,
        "changes_committed": false,
        "rollback_required": false
    }
}
```

### 7. List Sync Operations

**Endpoint**: `GET /api/plugins/hedgehog/fabrics/{fabric_id}/sync-operations/`

**Purpose**: List sync operations for a fabric with filtering and pagination

**Query Parameters**:
- `status` (string, optional): Filter by status (`pending`, `in_progress`, `completed`, `failed`)
- `operation_type` (string, optional): Filter by operation type
- `started_after` (datetime, optional): Filter operations started after date
- `limit` (integer, optional): Number of results per page. Default: 50
- `offset` (integer, optional): Pagination offset. Default: 0

**Response (200 OK)**:
```json
{
    "count": 127,
    "next": "/api/plugins/hedgehog/fabrics/123/sync-operations/?limit=50&offset=50",
    "previous": null,
    "results": [
        {
            "operation_id": "sync_20250730_123456",
            "operation_type": "bidirectional",
            "status": "completed",
            "started_at": "2025-07-30T12:34:56Z",
            "completed_at": "2025-07-30T12:36:12Z",
            "duration_seconds": 76,
            "resources_processed": 24,
            "success_rate": 0.95,
            "initiated_by": "admin",
            "summary": "Successfully synced 24 resources with 1 conflict resolved"
        },
        {
            "operation_id": "sync_20250730_101234",
            "operation_type": "github_to_gui",
            "status": "failed", 
            "started_at": "2025-07-30T10:12:34Z",
            "completed_at": "2025-07-30T10:14:56Z",
            "duration_seconds": 142,
            "resources_processed": 8,
            "success_rate": 0.33,
            "initiated_by": "auto_scheduler",
            "summary": "Sync failed due to GitHub API rate limits",
            "error_count": 16
        }
    ]
}
```

## Conflict Management API

### 8. List Conflicts

**Endpoint**: `GET /api/plugins/hedgehog/fabrics/{fabric_id}/conflicts/`

**Purpose**: List all detected conflicts for a fabric

**Query Parameters**:
- `status` (string, optional): Filter by status (`detected`, `resolving`, `resolved`)
- `severity` (string, optional): Filter by severity (`low`, `medium`, `high`, `critical`)
- `resource_kind` (string, optional): Filter by resource kind
- `auto_resolvable` (boolean, optional): Filter by auto-resolvable status

**Response (200 OK)**:
```json
{
    "count": 3,
    "active_conflicts": 2,
    "resolved_conflicts": 1,
    "conflicts": [
        {
            "conflict_id": "conflict_789",
            "resource_id": 456,
            "resource_name": "production-vpc",
            "resource_kind": "VPC",
            "conflict_type": "concurrent_modification",
            "severity": "medium",
            "detected_at": "2025-07-30T12:25:00Z",
            "status": "detected",
            "auto_resolvable": false,
            "details": {
                "gui_modification_time": "2025-07-30T12:20:00Z",
                "github_modification_time": "2025-07-30T12:22:00Z",
                "conflicting_fields": ["spec.subnets", "spec.tags"],
                "gui_values": {
                    "spec.subnets": ["10.0.1.0/24", "10.0.2.0/24"],
                    "spec.tags": {"environment": "production", "team": "platform"}
                },
                "github_values": {
                    "spec.subnets": ["10.0.1.0/24", "10.0.3.0/24"],
                    "spec.tags": {"environment": "prod", "team": "platform", "owner": "alice"}
                }
            },
            "resolution_options": [
                {
                    "strategy": "gui_wins",
                    "description": "Use GUI values for all conflicting fields",
                    "recommended": false
                },
                {
                    "strategy": "github_wins", 
                    "description": "Use GitHub values for all conflicting fields",
                    "recommended": false
                },
                {
                    "strategy": "merge",
                    "description": "Intelligent merge of non-conflicting changes",
                    "recommended": true,
                    "merge_preview": {
                        "spec.subnets": ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"],
                        "spec.tags": {"environment": "production", "team": "platform", "owner": "alice"}
                    }
                },
                {
                    "strategy": "manual",
                    "description": "Manual resolution required",
                    "recommended": false
                }
            ],
            "resolution_url": "/api/plugins/hedgehog/conflicts/conflict_789/resolve/"
        }
    ]
}
```

### 9. Resolve Conflict

**Endpoint**: `POST /api/plugins/hedgehog/conflicts/{conflict_id}/resolve/`

**Purpose**: Resolve a specific conflict with user-specified strategy

**Request Parameters**:
```json
{
    "resolution_strategy": "merge",
    "user_decisions": {
        "spec.subnets": "merge_both",
        "spec.tags.environment": "gui_value",
        "spec.tags.owner": "github_value"
    },
    "options": {
        "create_pr": true,
        "pr_title": "Resolve conflict: production-vpc configuration merge",
        "auto_apply": false,
        "backup_before_resolve": true
    },
    "resolution_notes": "Merged subnet configurations and preserved ownership tags"
}
```

**Response (200 OK)**:
```json
{
    "success": true,
    "message": "Conflict resolved successfully",
    "conflict_id": "conflict_789",
    "resolution_details": {
        "strategy_used": "merge",
        "resolved_at": "2025-07-30T12:45:00Z",
        "resolution_duration_seconds": 3,
        "auto_applied": false,
        "backup_created": "backup/conflict_789_20250730_124500"
    },
    "resolved_state": {
        "spec": {
            "subnets": ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"],
            "tags": {
                "environment": "production",
                "team": "platform", 
                "owner": "alice"
            }
        }
    },
    "next_steps": {
        "pr_created": true,
        "pr_url": "https://github.com/user/repo/pull/42",
        "requires_approval": true,
        "auto_merge_scheduled": false
    },
    "quality_score": 0.95,
    "user_feedback_url": "/api/plugins/hedgehog/conflicts/conflict_789/feedback/"
}
```

### 10. Bulk Conflict Resolution

**Endpoint**: `POST /api/plugins/hedgehog/fabrics/{fabric_id}/conflicts/resolve-bulk/`

**Purpose**: Resolve multiple conflicts with the same strategy

**Request Parameters**:
```json
{
    "conflict_ids": ["conflict_789", "conflict_790", "conflict_791"],
    "resolution_strategy": "gui_wins",
    "options": {
        "create_single_pr": true,
        "pr_title": "Bulk conflict resolution: GUI state preferred",
        "auto_apply": false,
        "skip_manual_conflicts": true
    },
    "resolution_notes": "Bulk resolution preferring GUI state for consistency"
}
```

**Response (202 Accepted)**:
```json
{
    "success": true,
    "message": "Bulk conflict resolution initiated",
    "operation_id": "bulk_resolve_20250730_124500",
    "conflicts_targeted": 3,
    "conflicts_auto_resolvable": 2,
    "conflicts_skipped": 1,
    "estimated_duration_seconds": 15,
    "status_url": "/api/plugins/hedgehog/sync-operations/bulk_resolve_20250730_124500/"
}
```

## Resource and File Management API

### 11. Get Resource File Mapping

**Endpoint**: `GET /api/plugins/hedgehog/resources/{resource_id}/file-mapping/`

**Purpose**: Get file mapping information for a specific resource

**Response (200 OK)**:
```json
{
    "resource_id": 456,
    "resource_name": "production-vpc",
    "resource_kind": "VPC",
    "fabric_id": 123,
    "file_mapping": {
        "managed_file_path": "managed/vpcs/production-vpc.yaml",
        "file_hash": "sha256:a1b2c3d4e5f6...",
        "file_size_bytes": 1024,
        "last_file_sync": "2025-07-30T12:30:00Z",
        "github_info": {
            "branch": "main",
            "commit_sha": "abc123def456",
            "file_url": "https://github.com/user/repo/blob/main/gitops/hedgehog/fabric-1/managed/vpcs/production-vpc.yaml",
            "last_modified": "2025-07-30T12:30:00Z"
        }
    },
    "sync_status": {
        "sync_direction": "bidirectional",
        "auto_sync_enabled": true,
        "sync_healthy": true,
        "needs_github_sync": false,
        "needs_gui_sync": false,
        "last_sync": "2025-07-30T12:30:00Z",
        "sync_errors": 0
    },
    "conflict_status": {
        "status": "none",
        "has_conflicts": false,
        "last_conflict_check": "2025-07-30T12:35:00Z"
    },
    "external_modifications": {
        "count": 0,
        "last_check": "2025-07-30T12:35:00Z",
        "recent_modifications": []
    }
}
```

### 12. Update Resource Sync Configuration

**Endpoint**: `PATCH /api/plugins/hedgehog/resources/{resource_id}/sync-config/`

**Purpose**: Update synchronization configuration for a specific resource

**Request Parameters**:
```json
{
    "sync_direction": "bidirectional",
    "auto_sync_enabled": true,
    "sync_priority": 50,
    "conflict_resolution_preference": "user_guided",
    "notification_settings": {
        "notify_on_conflict": true,
        "notify_on_sync_error": true,
        "email_recipients": ["admin@example.com"]
    }
}
```

**Response (200 OK)**:
```json
{
    "success": true,
    "message": "Sync configuration updated successfully",
    "resource_id": 456,
    "updated_config": {
        "sync_direction": "bidirectional",
        "auto_sync_enabled": true,
        "sync_priority": 50,
        "conflict_resolution_preference": "user_guided",
        "notification_settings": {
            "notify_on_conflict": true,
            "notify_on_sync_error": true,
            "email_recipients": ["admin@example.com"]
        }
    },
    "effective_immediately": true,
    "next_sync_scheduled": "2025-07-30T13:00:00Z"
}
```

### 13. Force Resource Sync

**Endpoint**: `POST /api/plugins/hedgehog/resources/{resource_id}/sync/`

**Purpose**: Force immediate synchronization for a specific resource

**Request Parameters**:
```json
{
    "direction": "gui_to_github",
    "force_overwrite": false,
    "create_pr": false,
    "ignore_conflicts": false,
    "custom_commit_message": "Force sync: production-vpc configuration update"
}
```

**Response (200 OK)**:
```json
{
    "success": true,
    "message": "Resource sync completed successfully",
    "resource_id": 456,
    "sync_details": {
        "direction": "gui_to_github",
        "operation": "update",
        "file_path": "managed/vpcs/production-vpc.yaml",
        "commit_sha": "def456abc789",
        "commit_url": "https://github.com/user/repo/commit/def456abc789",
        "sync_duration_seconds": 2.3
    },
    "file_changes": {
        "lines_added": 5,
        "lines_removed": 2,
        "fields_changed": ["spec.subnets", "metadata.labels"]
    },
    "validation_results": {
        "schema_valid": true,
        "lint_warnings": 0,
        "recommendations": []
    }
}
```

## Monitoring and Analytics API

### 14. Get Fabric Sync Health

**Endpoint**: `GET /api/plugins/hedgehog/fabrics/{fabric_id}/sync-health/`

**Purpose**: Get comprehensive sync health status for a fabric

**Response (200 OK)**:
```json
{
    "fabric_id": 123,
    "fabric_name": "production-fabric",
    "overall_health_score": 85,
    "health_status": "good",
    "last_updated": "2025-07-30T12:40:00Z",
    "metrics": {
        "sync_operations": {
            "total_operations_24h": 12,
            "successful_operations_24h": 10,
            "failed_operations_24h": 2,
            "success_rate_24h": 0.83,
            "average_duration_seconds": 45,
            "last_successful_sync": "2025-07-30T12:36:12Z"
        },
        "resources": {
            "total_resources": 156,
            "synced_resources": 152,
            "resources_with_conflicts": 2,
            "resources_with_errors": 2,
            "sync_coverage": 0.97
        },
        "conflicts": {
            "active_conflicts": 2,
            "resolved_conflicts_24h": 3,
            "average_resolution_time_seconds": 120,
            "auto_resolution_rate": 0.60
        },
        "github_integration": {
            "api_calls_24h": 245,
            "rate_limit_usage": 0.15,
            "connection_healthy": true,
            "last_api_error": null
        },
        "performance": {
            "average_sync_time_seconds": 45,
            "resources_per_second": 2.1,
            "api_calls_per_sync": 8.5,
            "memory_usage_trend": "stable"
        }
    },
    "alerts": [
        {
            "level": "warning",
            "message": "2 resources have unresolved conflicts",
            "action_required": "Review and resolve conflicts",
            "alert_url": "/api/plugins/hedgehog/fabrics/123/conflicts/"
        }
    ],
    "recommendations": [
        "Consider increasing sync frequency for high-priority resources",
        "Review and resolve pending conflicts to improve health score"
    ]
}
```

### 15. Get Sync Analytics

**Endpoint**: `GET /api/plugins/hedgehog/fabrics/{fabric_id}/sync-analytics/`

**Purpose**: Get detailed analytics and trends for sync operations

**Query Parameters**:
- `period` (string): Time period (`24h`, `7d`, `30d`, `90d`)
- `metrics` (string[]): Specific metrics to include
- `group_by` (string): Group results by (`hour`, `day`, `week`)

**Response (200 OK)**:
```json
{
    "fabric_id": 123,
    "period": "7d",
    "generated_at": "2025-07-30T12:40:00Z",
    "summary": {
        "total_operations": 84,
        "success_rate": 0.89,
        "average_duration_seconds": 52,
        "total_resources_synced": 1248,
        "total_conflicts_resolved": 18
    },
    "trends": {
        "sync_volume": [
            {"date": "2025-07-24", "operations": 15, "success_rate": 0.93},
            {"date": "2025-07-25", "operations": 12, "success_rate": 0.83},
            {"date": "2025-07-26", "operations": 8, "success_rate": 1.0},
            {"date": "2025-07-27", "operations": 14, "success_rate": 0.86},
            {"date": "2025-07-28", "operations": 11, "success_rate": 0.91},
            {"date": "2025-07-29", "operations": 13, "success_rate": 0.85},
            {"date": "2025-07-30", "operations": 11, "success_rate": 0.91}
        ],
        "performance": [
            {"date": "2025-07-24", "avg_duration": 48, "resources_per_second": 2.3},
            {"date": "2025-07-25", "avg_duration": 62, "resources_per_second": 1.8},
            {"date": "2025-07-26", "avg_duration": 41, "resources_per_second": 2.7},
            {"date": "2025-07-27", "avg_duration": 55, "resources_per_second": 2.1},
            {"date": "2025-07-28", "avg_duration": 49, "resources_per_second": 2.4},
            {"date": "2025-07-29", "avg_duration": 58, "resources_per_second": 2.0},
            {"date": "2025-07-30", "avg_duration": 51, "resources_per_second": 2.2}
        ]
    },
    "breakdown": {
        "by_operation_type": {
            "bidirectional": {"count": 45, "success_rate": 0.91},
            "gui_to_github": {"count": 23, "success_rate": 0.87},
            "github_to_gui": {"count": 16, "success_rate": 0.88}
        },
        "by_resource_kind": {
            "VPC": {"synced": 280, "conflicts": 3, "errors": 1},
            "Connection": {"synced": 658, "conflicts": 8, "errors": 2},
            "Switch": {"synced": 210, "conflicts": 4, "errors": 1},
            "Server": {"synced": 100, "conflicts": 3, "errors": 1}
        }
    }
}
```

## Webhook Integration API

### 16. Configure Sync Webhooks

**Endpoint**: `POST /api/plugins/hedgehog/fabrics/{fabric_id}/webhooks/`

**Purpose**: Configure webhooks for sync events

**Request Parameters**:
```json
{
    "webhook_url": "https://api.example.com/webhooks/sync",
    "events": [
        "sync_started",
        "sync_completed", 
        "sync_failed",
        "conflict_detected",
        "conflict_resolved"
    ],
    "authentication": {
        "type": "bearer_token",
        "token": "webhook_token_abc123"
    },
    "filters": {
        "operation_types": ["bidirectional"],
        "resource_kinds": ["VPC", "Connection"],
        "min_severity": "medium"
    },
    "retry_config": {
        "max_retries": 3,
        "retry_delay_seconds": 60,
        "timeout_seconds": 30
    }
}
```

**Response (201 Created)**:
```json
{
    "success": true,
    "message": "Webhook configured successfully",
    "webhook_id": "webhook_456",
    "webhook_config": {
        "webhook_url": "https://api.example.com/webhooks/sync",
        "events": [
            "sync_started",
            "sync_completed",
            "sync_failed", 
            "conflict_detected",
            "conflict_resolved"
        ],
        "authentication": {
            "type": "bearer_token",
            "token": "***masked***"
        },
        "filters": {
            "operation_types": ["bidirectional"],
            "resource_kinds": ["VPC", "Connection"],
            "min_severity": "medium"
        },
        "retry_config": {
            "max_retries": 3,
            "retry_delay_seconds": 60,
            "timeout_seconds": 30
        },
        "status": "active",
        "created_at": "2025-07-30T12:45:00Z"
    },
    "test_webhook_url": "/api/plugins/hedgehog/webhooks/webhook_456/test/"
}
```

## Error Handling and Status Codes

### Standard HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully  
- `202 Accepted`: Request accepted for processing
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., operation already in progress)
- `422 Unprocessable Entity`: Validation errors
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

### Error Response Format

```json
{
    "success": false,
    "error": "Human-readable error message",
    "error_code": "MACHINE_READABLE_CODE",
    "details": {
        "field_errors": {
            "sync_direction": ["Invalid sync direction: 'invalid_direction'"]
        },
        "validation_errors": [
            "Resource name must be DNS-compliant"
        ],
        "suggestions": [
            "Check the sync_direction parameter",
            "Ensure resource names follow Kubernetes naming conventions"
        ]
    },
    "request_id": "req_20250730_123456",
    "timestamp": "2025-07-30T12:34:56Z",
    "documentation_url": "https://docs.example.com/api/errors/MACHINE_READABLE_CODE"
}
```

### Common Error Codes

- `FABRIC_NOT_FOUND`: Specified fabric does not exist
- `REPOSITORY_ACCESS_DENIED`: Cannot access Git repository
- `OPERATION_IN_PROGRESS`: Another sync operation is already running
- `DIRECTORY_NOT_INITIALIZED`: GitOps directories not initialized
- `CONFLICT_RESOLUTION_FAILED`: Unable to resolve resource conflicts
- `GITHUB_RATE_LIMITED`: GitHub API rate limit exceeded
- `VALIDATION_FAILED`: Resource validation failed
- `PERMISSION_DENIED`: Insufficient permissions for operation
- `NETWORK_ERROR`: Network connectivity issues
- `TIMEOUT_ERROR`: Operation timed out

## Rate Limiting

### Rate Limit Headers

All API responses include rate limiting headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1625097600
X-RateLimit-Resource: sync-operations
```

### Rate Limits by Endpoint Category

- **Directory Management**: 30 requests per minute
- **Sync Operations**: 10 requests per minute
- **Conflict Resolution**: 60 requests per minute  
- **Resource Management**: 120 requests per minute
- **Monitoring/Analytics**: 180 requests per minute
- **Webhooks**: 60 requests per minute

## Authentication and Permissions

### Token-Based Authentication

```bash
curl -H "Authorization: Token YOUR_API_TOKEN" \
     -H "Content-Type: application/json" \
     https://netbox.example.com/api/plugins/hedgehog/fabrics/123/sync/
```

### Required Permissions

- `netbox_hedgehog.view_hedgehogfabric`: View fabric information
- `netbox_hedgehog.change_hedgehogfabric`: Modify fabric configuration
- `netbox_hedgehog.add_syncoperation`: Create sync operations
- `netbox_hedgehog.view_syncoperation`: View sync operation status
- `netbox_hedgehog.change_hedgehogresource`: Modify resource sync configuration
- `netbox_hedgehog.resolve_conflicts`: Resolve conflicts

## API Versioning

### Version Strategy

- **Current Version**: `v1`
- **URL Pattern**: `/api/plugins/hedgehog/v1/...`
- **Header**: `Accept: application/vnd.hedgehog.v1+json`
- **Backward Compatibility**: 2 major versions supported

### Version Migration

When upgrading API versions:

1. Add version parameter to requests
2. Update client libraries
3. Test compatibility with new version
4. Migrate gradually with fallback support

This comprehensive API specification provides complete control over GitOps bidirectional synchronization functionality while maintaining consistency with NetBox API patterns and ensuring robust error handling and monitoring capabilities.