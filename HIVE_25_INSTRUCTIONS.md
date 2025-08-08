# 🎯 HIVE MIND V25 - PERIODIC SYNC SCHEDULER TDD IMPLEMENTATION

## ⚡ URGENT MISSION: IMPLEMENT SCHEDULER - 2 HOURS MAX

**CONTEXT**: Hive 24 created comprehensive TDD test suite (1,741+ lines). All infrastructure exists (Celery, tasks, models).

**REMAINING WORK**: ONE missing component - periodic scheduler task (~50 lines of code)

**SUCCESS PATTERN**: Hive 22 achieved breakthrough success using TDD implementation pattern. Hive 21 failed with same scope but wrong approach.

**YOUR MISSION**: Apply Hive 22's TDD implementation success to make ALL Hive 24 tests pass.

---

## 🚫 MANDATORY FAILURE PREVENTION

**YOU WILL FAIL IF YOU:**
- Spend more than 30 minutes on analysis
- Try to reimplement any existing infrastructure
- Create comprehensive documentation  
- Work on anything beyond the scheduler
- Skip the TDD validation process

**SUCCESS REQUIRES:**
- Make ALL Hive 24 tests pass within 2 hours
- Implement ONLY the periodic scheduler (no other changes)
- Use existing Celery/task infrastructure
- Validate with real local test environment

---

## 🔍 THE ONE MISSING COMPONENT (FROM HIVE 24 ANALYSIS)

### MISSING: Periodic Sync Scheduler Task
**ROOT CAUSE**: No Celery Beat task checks fabric sync intervals and triggers syncs
**LOCATION NEEDED**: `netbox_hedgehog/tasks/git_sync_tasks.py` and `netbox_hedgehog/celery.py`
**EXACT REQUIREMENT**: ~50 lines of code to connect existing pieces

**CURRENT STATE (PROVEN BY HIVE 24)**:
- ✅ `HedgehogFabric.sync_interval` field exists (default 300 seconds)
- ✅ `HedgehogFabric.last_sync` field exists 
- ✅ `git_sync_fabric()` Celery task exists and works
- ✅ Celery Beat scheduler infrastructure exists
- ❌ **NO task to check intervals and trigger syncs**

**REQUIRED IMPLEMENTATION**:
1. Add `check_fabric_sync_schedules()` task function
2. Add Celery Beat schedule entry (60-second interval)  
3. Implement interval timing logic
4. Trigger existing `git_sync_fabric.delay()` when due

---

## ⚡ EXECUTION PROTOCOL - EXACTLY 2 HOURS

### PHASE 1: ENVIRONMENT SETUP (15 minutes)

#### Step 1.1: Load Environment Variables
```bash
# Navigate to project root
cd /home/ubuntu/cc/hedgehog-netbox-plugin

# Load .env file (NOT pre-loaded)
export $(cat .env | grep -v '^#' | xargs)

# Verify NetBox accessible
curl -I $NETBOX_URL
```

#### Step 1.2: Run Hive 24 Tests (Prove They Fail)
```bash
# Load environment for Django
source /home/ubuntu/cc/hedgehog-netbox-plugin/.env

# Run test suite - should ALL fail (scheduler missing)
python manage.py test netbox_hedgehog.tests.test_periodic_sync_scheduler --verbosity=2
python manage.py test netbox_hedgehog.tests.test_sync_configuration_states --verbosity=2

# EXPECTED RESULT: ALL tests fail (ImportError or AttributeError for missing scheduler)
```

### PHASE 2: IMPLEMENT SCHEDULER TASK (90 minutes)

#### Step 2.1: Add Scheduler Task Function (45 minutes)
Add this function to `netbox_hedgehog/tasks/git_sync_tasks.py`:

```python
@shared_task(name='netbox_hedgehog.tasks.check_fabric_sync_schedules')
def check_fabric_sync_schedules() -> Dict[str, Any]:
    """
    Check all enabled fabrics for sync_interval timing and trigger syncs when due.
    Runs every 60 seconds via Celery Beat.
    """
    from django.utils import timezone
    from datetime import timedelta
    from netbox_hedgehog.models.fabric import HedgehogFabric
    
    fabrics_needing_sync = []
    
    try:
        # Get all enabled fabrics
        enabled_fabrics = HedgehogFabric.objects.filter(sync_enabled=True)
        
        for fabric in enabled_fabrics:
            if should_sync_now(fabric):
                # Trigger sync using existing task
                git_sync_fabric.delay(fabric.id)
                fabrics_needing_sync.append(fabric.id)
                
    except Exception as e:
        # Log error but don't crash scheduler
        logger.error(f"Error in periodic sync scheduler: {e}")
        return {'error': str(e), 'synced_fabrics': []}
    
    return {
        'synced_fabrics': fabrics_needing_sync,
        'total_checked': enabled_fabrics.count() if 'enabled_fabrics' in locals() else 0,
        'timestamp': timezone.now().isoformat()
    }

def should_sync_now(fabric) -> bool:
    """Determine if fabric needs sync based on interval timing"""
    if not fabric.last_sync:
        # Never synced - sync immediately
        return True
        
    interval = timedelta(seconds=fabric.sync_interval or 300)  # Default 5 minutes
    time_since_last = timezone.now() - fabric.last_sync
    
    return time_since_last >= interval
```

#### Step 2.2: Add Celery Beat Schedule Entry (30 minutes)
Add this to the `beat_schedule` dictionary in `netbox_hedgehog/celery.py`:

```python
'check-fabric-sync-intervals': {
    'task': 'netbox_hedgehog.tasks.check_fabric_sync_schedules',
    'schedule': 60.0,  # Check every minute
    'options': {'queue': 'git_sync', 'priority': 6}
},
```

#### Step 2.3: Import and Error Handling (15 minutes)
Add these imports to `git_sync_tasks.py` if missing:

```python
from typing import Dict, Any
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)
```

### PHASE 3: VALIDATION WITH LOCAL TEST ENVIRONMENT (15 minutes)

#### Step 3.1: Run Tests Again (Should Pass)
```bash
# Run the same tests - should now PASS
python manage.py test netbox_hedgehog.tests.test_periodic_sync_scheduler --verbosity=2
python manage.py test netbox_hedgehog.tests.test_sync_configuration_states --verbosity=2

# SUCCESS CRITERIA: ALL tests pass (scheduler now exists and works)
```

#### Step 3.2: Validate Celery Beat Registration
```python
# Check Celery Beat recognizes new task
from netbox_hedgehog.celery import app
print(app.conf.beat_schedule.keys())

# Should show 'check-fabric-sync-intervals' in list
```

---

## 📋 SUCCESS VALIDATION GATES

### GATE 1: All Hive 24 Tests Pass ✅
```bash
# EXACT COMMANDS TO PROVE SUCCESS:
python manage.py test netbox_hedgehog.tests.test_periodic_sync_scheduler
python manage.py test netbox_hedgehog.tests.test_sync_configuration_states  
python manage.py test netbox_hedgehog.tests.test_scheduler_execution_states
python manage.py test netbox_hedgehog.tests.test_sync_error_handling

# RESULT REQUIRED: All tests pass with 0 failures
```

### GATE 2: Scheduler Runs in Local Environment ✅
```bash
# Test scheduler function directly
python manage.py shell -c "
from netbox_hedgehog.tasks.git_sync_tasks import check_fabric_sync_schedules
result = check_fabric_sync_schedules()
print('Scheduler result:', result)
"

# RESULT REQUIRED: Function executes without error, returns fabric count
```

### GATE 3: Integration with Local NetBox ✅
```bash  
# Check fabric sync intervals display correctly in GUI
curl -s $NETBOX_URL/plugins/hedgehog/fabrics/ | grep -i "sync.*interval"

# Create test fabric and verify scheduler would trigger sync
curl -X POST $NETBOX_URL/api/plugins/hedgehog/fabrics/ \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"test-scheduler","sync_interval":60,"sync_enabled":true}'

# RESULT REQUIRED: Scheduler identifies fabric needs sync (null last_sync)
```

---

## 🚨 CRITICAL SUCCESS RULES

### Rule 1: TDD Implementation Only
- Implement EXACTLY what Hive 24 tests require
- Change NO existing infrastructure 
- Add ONLY the missing scheduler task
- Use existing `git_sync_fabric()` task

### Rule 2: Local Environment Testing Required
- Load `.env` file variables (NOT pre-loaded)
- Test against local NetBox installation at `$NETBOX_URL`
- Use environment docs in `/project_management/06_onboarding_system/04_environment_mastery/`
- Validate with real fabric data

### Rule 3: All Tests Must Pass
- Success only when ALL Hive 24 tests pass
- No partial implementation accepted
- 23/24 tests passing = 0% success rate

### Rule 4: 2-Hour Maximum
- Phase 1: 15 minutes (setup)
- Phase 2: 90 minutes (implementation)  
- Phase 3: 15 minutes (validation)
- Exceed = automatic failure

---

## 📊 WHY THIS WILL SUCCEED

### Hive 22 Success Pattern Applied:
- **TDD Implementation**: Use existing test suite vs creating new tests
- **Focused Mission**: ONE missing component vs comprehensive overhaul
- **Concrete Specifications**: Exact code provided vs abstract requirements
- **Proven Infrastructure**: Build on working Celery/task system
- **Local Environment**: Test in actual NetBox vs theoretical validation

### Hive 21 Failure Patterns Avoided:
- **No Analysis Paralysis**: 15-minute setup max vs multi-hour research  
- **No Scope Creep**: ONLY scheduler task vs entire system changes
- **No Architecture Redesign**: Use existing patterns vs new approaches
- **TDD Focus**: Make tests pass vs creating new comprehensive solution

### Technical Confidence Based on Hive 24:
- **Complete Test Coverage**: 24+ test cases covering all scenarios
- **Proven Test Validity**: All tests fail appropriately (scheduler missing)
- **Clear Implementation Guide**: Exact specifications provided
- **Infrastructure Confirmed**: Celery, tasks, models all exist and work

**PROBABILITY OF SUCCESS: 95%** (based on TDD implementation vs greenfield development)

---

## 🎯 LOCAL ENVIRONMENT INTEGRATION

### Environment Setup Requirements:
```bash
# .env file location (NOT pre-loaded):
/home/ubuntu/cc/hedgehog-netbox-plugin/.env

# Key variables for testing:
NETBOX_URL="http://localhost:8000/"
NETBOX_TOKEN="ced6a3e0a978db0ad4de39cd66af4868372d7dd0"

# Environment mastery docs:
/project_management/06_onboarding_system/04_environment_mastery/
```

### Local Test Validation:
- NetBox GUI at `http://localhost:8000/` 
- API endpoints for fabric management
- Django management commands for testing
- Real fabric data for scheduler validation

---

## 🎯 EXECUTE NOW - 2 HOURS TO SUCCESS

**Time Started**: ________________
**Time Limit**: ________________ + 2 hours  
**Success Definition**: ALL Hive 24 tests pass + scheduler running

**REMEMBER**: You have comprehensive TDD tests from Hive 24. This is implementation ONLY.

**NO ANALYSIS. NO NEW TESTS. NO ARCHITECTURE CHANGES.**

**IMPLEMENT. TEST. VALIDATE. SUCCEED.**