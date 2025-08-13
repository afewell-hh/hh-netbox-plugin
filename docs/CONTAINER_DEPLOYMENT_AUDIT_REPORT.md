# Container Deployment State Audit Report

## Issue #44 Investigation Results

### Executive Summary
Investigation revealed critical deployment inconsistencies preventing the NetBox container from starting properly. The primary issues are database-related and authentication import problems.

### Critical Issues Discovered

#### 1. Database Migration Index Name Length Violation
**Issue**: PostgreSQL index name exceeds 30-character limit
- **Index Name**: `hnp_syncop_fabric_type_started_idx` (36 characters)
- **Location**: Migration 0021 and models/gitops.py
- **Impact**: Container startup fails with SystemCheckError
- **Status**: CRITICAL - Blocks container startup

#### 2. Container Service Startup Failures
**Container Status**:
- Main NetBox container: STOPPED (Exit code 1)
- RQ Worker: STOPPED (Exit code 1) 
- RQ Scheduler: STOPPED (Exit code 1)
- Housekeeping: RUNNING (healthy)
- Database: RUNNING (healthy)
- Redis: RUNNING (healthy)

#### 3. Import/Module Loading Issues
**RQ Worker Log Error**:
```
ImportError: cannot import name 'GitOpsEditService' from 'netbox_hedgehog.services'
```
**Analysis**: While the service exists in the container files, there may be circular import issues or Python cache problems.

### File Synchronization Analysis

#### Files Successfully Synchronized
- `/netbox_hedgehog/services/__init__.py` - ✅ Timestamps match
- `/netbox_hedgehog/views/gitops_edit_views.py` - ✅ Timestamps match  
- `/netbox_hedgehog/signals.py` - ✅ Host: 605 lines, Container: Same content

#### Container File Structure Verified
- Plugin directory structure: ✅ Complete
- Services directory: ✅ All services present including GitOpsEditService
- Views directory: ✅ All view files present
- Migrations: ✅ All applied (through 0023)

### Database Connection Analysis
- PostgreSQL container: ✅ Healthy and accepting connections
- Database configuration: ✅ Correct environment variables
- Migration status: ✅ All migrations applied successfully

### Root Cause Analysis

#### Primary Cause: Database Schema Validation
The NetBox container fails during startup due to Django's system check identifying the long index name as an error. This prevents the application from starting even though the database connection is healthy.

#### Secondary Issues:
1. **Python Cache**: Old bytecode cache may be causing import conflicts
2. **Startup Timing**: Container may be hitting database connection timeouts during validation

### Impact Assessment

#### Authentication Issues
- **Direct Impact**: Container cannot start, so authentication cannot be tested
- **Indirect Impact**: Previous authentication fixes cannot be validated in containerized environment

#### Sync Functionality
- **Status**: Cannot be tested due to container startup failure
- **Risk**: High - Production deployment would fail

### Immediate Fix Required

#### Priority 1: Fix Index Name Length
```python
# Change from:
name='hnp_syncop_fabric_type_started_idx'  # 36 chars

# To:
name='hnp_syncop_fab_type_start_idx'       # 30 chars
```

#### Priority 2: Clear Python Cache
```bash
sudo docker exec <container> find /opt/netbox -name "*.pyc" -delete
sudo docker exec <container> find /opt/netbox -name "__pycache__" -type d -exec rm -rf {} +
```

### Deployment Verification Checklist
- [ ] Fix index name length in migration 0021
- [ ] Fix index name length in models/gitops.py  
- [ ] Create new migration to rename existing index
- [ ] Clear Python bytecode cache
- [ ] Restart containers and verify startup
- [ ] Test authentication functionality
- [ ] Validate sync button functionality

### Evidence Files Generated
- Container logs captured showing database timeout and import errors
- File comparison showing synchronized timestamps
- Database status verification showing healthy connections
- Migration status showing all applied migrations

## Conclusion

The container deployment is failing due to a database schema validation error (index name too long) rather than file synchronization issues. While the host files are properly synchronized to the container, the application cannot start due to this PostgreSQL constraint violation. This critical issue must be resolved before any authentication or sync functionality can be tested in the containerized environment.