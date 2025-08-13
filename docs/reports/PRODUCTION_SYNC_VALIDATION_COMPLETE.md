# 🚀 PRODUCTION SYNC VALIDATION - COMPLETE TESTING GUIDE

## CRITICAL MISSION: Test RQ-based Periodic Sync in REAL Production Environment

**NO THEORETICAL TESTING - Only real validation using actual NetBox containers.**

This guide provides step-by-step commands to validate that the RQ-based periodic sync implementation actually works in the production NetBox container environment.

---

## 📋 TESTING REQUIREMENTS

**EVIDENCE REQUIRED:**
- Before/after fabric state comparison
- Actual command outputs showing sync execution  
- Database state changes with timestamps
- RQ queue status and job execution logs
- Proof that 60-second interval works

**SUCCESS CRITERIA:**
- ✅ Fabric sync_status changes from 'never_synced'
- ✅ last_sync updates with recent timestamps
- ✅ RQ tasks queue and execute successfully
- ✅ Periodic sync runs at ~60-second intervals
- ✅ Database state changes are detected and verified

---

## 🐳 STEP 1: CONTAINER ENVIRONMENT VERIFICATION

First, verify your Docker containers are running:

```bash
# Check container status
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'

# Verify NetBox is accessible
curl -s http://localhost:8000/login/ | grep -i "netbox\|login" || echo "NetBox not accessible"

# Check worker processes
sudo docker exec netbox-docker-netbox-worker-1 ps aux | grep rqworker
```

**VALIDATION:**
- ✅ PASS if: Both containers show 'Up' or 'healthy' status
- ✅ PASS if: NetBox login page is accessible
- ✅ PASS if: RQ worker processes are running

---

## 📦 STEP 2: DEPLOY RQ SYNC IMPLEMENTATION

Deploy the RQ-based sync implementation to the containers:

```bash
# Navigate to project directory
cd /home/ubuntu/cc/hedgehog-netbox-plugin

# Deploy Celery configuration with RQ support
sudo docker cp netbox_hedgehog/celery.py netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/

# Deploy RQ sync tasks
sudo docker cp netbox_hedgehog/tasks/ netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/

# Deploy updated fabric model with scheduler_enabled
sudo docker cp netbox_hedgehog/models/fabric.py netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/models/

# Deploy database migration for scheduler_enabled field
sudo docker cp netbox_hedgehog/migrations/0023_add_scheduler_enabled_field.py netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/migrations/

# Deploy container test script
sudo docker cp container_task_test.py netbox-docker-netbox-1:/opt/netbox/
```

**VALIDATION:**
- ✅ PASS if: All copy commands complete without errors
- ✅ PASS if: Files exist in container after deployment

---

## 🔄 STEP 3: RESTART CONTAINERS

Restart containers to load the new RQ implementation:

```bash
# Restart main NetBox container
sudo docker restart netbox-docker-netbox-1

# Wait for container to start
echo "Waiting 30 seconds for NetBox container to restart..."
sleep 30

# Restart worker container  
sudo docker restart netbox-docker-netbox-worker-1

# Wait for worker to start
echo "Waiting 15 seconds for worker container to restart..."
sleep 15

# Verify both containers are healthy
sudo docker ps | grep netbox-docker
```

**VALIDATION:**
- ✅ PASS if: Both containers restart successfully
- ✅ PASS if: NetBox accessible at http://localhost:8000 after restart
- ✅ PASS if: No critical errors in container logs

---

## 🔧 STEP 4: TEST RQ WORKER PLUGIN LOADING

Verify the RQ worker can load the plugin and tasks:

```bash
# Test RQ worker processes
sudo docker exec netbox-docker-netbox-worker-1 ps aux | grep rqworker

# Test plugin task imports
sudo docker exec netbox-docker-netbox-worker-1 python -c "
import netbox_hedgehog.tasks.sync_tasks
print('✅ Plugin tasks imported successfully')
print('Available tasks:')
print('- master_sync_scheduler')
print('- sync_fabric_task')
print('- collect_performance_metrics') 
print('- check_kubernetes_health')
"

# Test RQ queue configuration
sudo docker exec netbox-docker-netbox-worker-1 python -c "
import django_rq
from django.conf import settings
conn = django_rq.get_connection()
print('RQ Connection:', conn)
queues = list(conn.smembers('rq:queues'))
print('Available Queues:', [q.decode() for q in queues])
"
```

**VALIDATION:**
- ✅ PASS if: RQ worker processes are running
- ✅ PASS if: Plugin tasks import without errors
- ✅ PASS if: RQ queues are properly configured

---

## 📊 STEP 5: CAPTURE BASELINE FABRIC STATE

Capture the current state of the test fabric before sync testing:

```bash
# Get baseline fabric state
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py shell -c "
from netbox_hedgehog.models import HedgehogFabric
from django.utils import timezone

print('=== BASELINE FABRIC STATE ===')
try:
    fabric = HedgehogFabric.objects.get(name='Test Lab K3s Cluster')
    print(f'Fabric ID: {fabric.id}')
    print(f'Name: {fabric.name}')
    print(f'Sync Status: {fabric.sync_status}')
    print(f'Sync Enabled: {fabric.sync_enabled}')
    print(f'Sync Interval: {fabric.sync_interval}')
    print(f'Last Sync: {fabric.last_sync}')
    print(f'Sync Error: {fabric.sync_error}')
    print(f'Connection Status: {fabric.connection_status}')
    print(f'Kubernetes Server: {fabric.kubernetes_server}')
    print(f'Scheduler Enabled: {getattr(fabric, \"scheduler_enabled\", True)}')
    print(f'Captured At: {timezone.now()}')
    print('=== BASELINE COMPLETE ===')
except HedgehogFabric.DoesNotExist:
    print('❌ ERROR: Test Lab K3s Cluster fabric not found')
    print('Available fabrics:')
    for f in HedgehogFabric.objects.all():
        print(f'  - {f.name} (ID: {f.id})')
"
```

**VALIDATION:**
- ✅ PASS if: Test fabric is found and state is displayed
- 📝 RECORD: Current sync_status (likely 'never_synced')
- 📝 RECORD: Last sync timestamp (likely None)

**SAVE OUTPUT TO:** `fabric_baseline_state.txt`

---

## 🔄 STEP 6: EXECUTE MANUAL SYNC TEST

Execute a manual sync to verify basic functionality:

```bash
# Execute manual sync test
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py shell -c "
from netbox_hedgehog.models import HedgehogFabric
from django.utils import timezone

print('=== MANUAL SYNC EXECUTION TEST ===')
fabric = HedgehogFabric.objects.get(name='Test Lab K3s Cluster')

print('BEFORE SYNC:')
print(f'  Last sync: {fabric.last_sync}')
print(f'  Sync status: {fabric.sync_status}')
print(f'  Sync error: {fabric.sync_error}')

print('\\nEXECUTING SYNC...')
try:
    from netbox_hedgehog.utils.kubernetes import KubernetesSync
    sync = KubernetesSync(fabric)
    result = sync.sync_fabric()
    print(f'Sync result: {result}')
    
    # Refresh fabric from database
    fabric.refresh_from_db()
    
    print('\\nAFTER SYNC:')
    print(f'  Last sync: {fabric.last_sync}')
    print(f'  Sync status: {fabric.sync_status}') 
    print(f'  Sync error: {fabric.sync_error}')
    print(f'  Connection status: {fabric.connection_status}')
    
    if fabric.last_sync:
        time_diff = timezone.now() - fabric.last_sync
        print(f'  Time since sync: {time_diff.total_seconds()} seconds')
    
    print('=== MANUAL SYNC COMPLETE ===')
    
except Exception as e:
    print(f'❌ SYNC FAILED: {str(e)}')
    import traceback
    traceback.print_exc()
"
```

**VALIDATION:**
- ✅ PASS if: Sync executes without Python errors
- ✅ PASS if: last_sync timestamp updates to current time
- ✅ PASS if: sync_status changes from 'never_synced'
- ❌ FAIL if: Sync throws exceptions

**SAVE OUTPUT TO:** `manual_sync_test_results.txt`

---

## ⚡ STEP 7: TEST RQ TASK QUEUING

Test that sync tasks can be queued and executed via RQ:

```bash
# Test RQ task queuing and execution
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py shell -c "
import django_rq
from netbox_hedgehog.tasks.sync_tasks import master_sync_scheduler
import time

print('=== RQ TASK QUEUING TEST ===')

# Get default queue
queue = django_rq.get_queue('default')
print(f'Jobs in queue before: {len(queue)}')

# Queue master sync scheduler task
print('\\nQueuing master sync scheduler task...')
job = master_sync_scheduler.delay()
print(f'Job queued with ID: {job.id}')
print(f'Job status: {job.get_status()}')

# Check queue after queuing
print(f'Jobs in queue after queuing: {len(queue)}')

# Wait for job execution
print('\\nWaiting 15 seconds for job execution...')
time.sleep(15)

# Check job status after execution
job.refresh()
print(f'Job status after wait: {job.get_status()}')

if job.is_finished:
    print('✅ JOB COMPLETED SUCCESSFULLY')
    result = job.result
    print(f'Job result: {result}')
elif job.is_failed:
    print('❌ JOB FAILED')
    print(f'Job failure info: {job.exc_info}')
else:
    print('⏳ JOB STILL RUNNING OR QUEUED')
    print(f'Current status: {job.get_status()}')

print('=== RQ TASK TEST COMPLETE ===')
"
```

**VALIDATION:**
- ✅ PASS if: Job is queued successfully with an ID
- ✅ PASS if: Job status progresses from 'queued' → 'started' → 'finished'
- ✅ PASS if: Job completes without exceptions
- 📝 RECORD: Job execution results and fabric processing

**SAVE OUTPUT TO:** `rq_task_queue_test.txt`

---

## ⏰ STEP 8: TEST PERIODIC SYNC CONFIGURATION

Verify the periodic sync is properly configured:

```bash
# Test periodic sync configuration
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py shell -c "
from netbox_hedgehog.celery import app
import json

print('=== PERIODIC SYNC CONFIGURATION ===')

# Check beat schedule configuration
print('Beat Schedule Configuration:')
for name, task_config in app.conf.beat_schedule.items():
    if 'sync' in name.lower():
        print(f'  Task: {name}')
        print(f'    Schedule: {task_config[\"schedule\"]} seconds')
        print(f'    Task Function: {task_config[\"task\"]}')
        queue = task_config.get('options', {}).get('queue', 'default')
        print(f'    Queue: {queue}')
        priority = task_config.get('options', {}).get('priority', 5)
        print(f'    Priority: {priority}')
        print()

# Check registered tasks
print('Registered Hedgehog Tasks:')
for task_name in sorted(app.tasks.keys()):
    if 'netbox_hedgehog' in task_name:
        print(f'  {task_name}')

print('=== CONFIGURATION COMPLETE ===')
"

# Test the container task test script
echo "\\n=== RUNNING CONTAINER TASK TEST ==="
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/container_task_test.py
```

**VALIDATION:**
- ✅ PASS if: 'master-sync-scheduler' task configured for 60.0 second interval
- ✅ PASS if: Hedgehog tasks are registered in Celery app
- ✅ PASS if: Container task test executes successfully

**SAVE OUTPUT TO:** `periodic_sync_configuration.txt`

---

## ⏱️ STEP 9: 60-SECOND TIMING VALIDATION (3-MINUTE MONITOR)

**⚠️ CRITICAL TEST: This monitors sync execution for 3 minutes to validate timing**

```bash
# 3-minute timing validation test
sudo docker exec netbox-docker-netbox-1 python -c "
import time
from datetime import datetime
from netbox_hedgehog.models import HedgehogFabric

print('=== 60-SECOND TIMING VALIDATION TEST ===')
print('Monitoring sync execution for 3 minutes...')
print('This will check sync status every 10 seconds')
print()

fabric = HedgehogFabric.objects.get(name='Test Lab K3s Cluster')

start_time = datetime.now()
print(f'Test start time: {start_time}')
print(f'Initial fabric state:')
print(f'  Last sync: {fabric.last_sync}')
print(f'  Sync status: {fabric.sync_status}')
print()

sync_events = []
previous_last_sync = fabric.last_sync

# Monitor for 3 minutes (18 checks * 10 seconds = 180 seconds)
for check_num in range(1, 19):
    fabric.refresh_from_db()
    current_time = datetime.now()
    
    # Check if last_sync changed (indicates sync occurred)
    if fabric.last_sync != previous_last_sync:
        sync_events.append({
            'check_number': check_num,
            'time': current_time,
            'last_sync': fabric.last_sync,
            'sync_status': fabric.sync_status
        })
        print(f'🔄 SYNC EVENT DETECTED at check {check_num}:')
        print(f'    Time: {current_time}')
        print(f'    Last sync: {fabric.last_sync}')
        print(f'    Status: {fabric.sync_status}')
        previous_last_sync = fabric.last_sync
    else:
        print(f'⏳ Check {check_num}/18 at {current_time.strftime(\"%H:%M:%S\")}: No sync change detected')
    
    if check_num < 18:  # Don't sleep on last iteration
        time.sleep(10)

end_time = datetime.now()
print()
print('=== TIMING VALIDATION COMPLETE ===')
print(f'Test end time: {end_time}')
print(f'Total test duration: {(end_time - start_time).total_seconds()} seconds')
print(f'Sync events detected: {len(sync_events)}')

if sync_events:
    print('\\nSync Event Summary:')
    for i, event in enumerate(sync_events):
        print(f'  Event {i+1}: {event[\"time\"]} - {event[\"sync_status\"]}')
    
    if len(sync_events) >= 2:
        # Calculate intervals between sync events
        print('\\nSync Intervals:')
        for i in range(1, len(sync_events)):
            prev_event = sync_events[i-1]
            curr_event = sync_events[i]
            interval = (curr_event['time'] - prev_event['time']).total_seconds()
            print(f'  Interval {i}: {interval} seconds')
else:
    print('\\n⚠️  WARNING: No sync events detected during 3-minute test')
    print('This may indicate periodic sync is not running correctly')

print('=== END TIMING VALIDATION ===')
"
```

**VALIDATION:**
- ✅ PASS if: Multiple sync events detected during 3-minute period
- ✅ PASS if: Sync intervals are approximately 60 seconds
- ✅ PASS if: last_sync timestamps show regular updates
- ⚠️ WARN if: No sync events detected (indicates sync not running)

**SAVE OUTPUT TO:** `timing_validation_3min.txt`

---

## 🗄️ STEP 10: DATABASE STATE VERIFICATION

Compare final fabric state with baseline to verify sync functionality:

```bash
# Final database state verification
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py shell -c "
from netbox_hedgehog.models import HedgehogFabric
from django.utils import timezone

print('=== FINAL DATABASE STATE VERIFICATION ===')
fabric = HedgehogFabric.objects.get(name='Test Lab K3s Cluster')

print('Current Fabric State:')
print(f'  Fabric ID: {fabric.id}')
print(f'  Name: {fabric.name}')
print(f'  Sync Status: {fabric.sync_status}')
print(f'  Last Sync: {fabric.last_sync}')
print(f'  Sync Error: {fabric.sync_error}')
print(f'  Connection Status: {fabric.connection_status}')
print(f'  Scheduler Enabled: {getattr(fabric, \"scheduler_enabled\", True)}')

print('\\nCalculated Status Properties:')
print(f'  Calculated Sync Status: {fabric.calculated_sync_status}')
print(f'  Calculated Status Display: {fabric.calculated_sync_status_display}')
print(f'  Needs Sync: {fabric.needs_sync()}')

try:
    health_score = fabric.calculate_scheduler_health_score()
    print(f'  Health Score: {health_score:.2f}')
except:
    print('  Health Score: Unable to calculate')

print()
print('=== COMPARISON ANALYSIS ===')
print('Compare this output with fabric_baseline_state.txt:')

# Time-based analysis
if fabric.last_sync:
    time_since_sync = timezone.now() - fabric.last_sync
    print(f'Time since last sync: {time_since_sync.total_seconds():.1f} seconds')
    if time_since_sync.total_seconds() < 300:  # Less than 5 minutes
        print('✅ RECENT SYNC DETECTED - Sync functionality is working')
    else:
        print('⚠️  Last sync is not recent - May indicate sync issues')
else:
    print('❌ No sync timestamp - Sync may not be working')

# Status analysis
if fabric.sync_status != 'never_synced':
    print('✅ SYNC STATUS CHANGED - No longer \"never_synced\"')
else:
    print('❌ SYNC STATUS UNCHANGED - Still \"never_synced\"')

print(f'\\nVerification completed at: {timezone.now()}')
print('=== VERIFICATION COMPLETE ===')
"
```

**VALIDATION:**
- ✅ PASS if: sync_status is NOT 'never_synced'
- ✅ PASS if: last_sync has a recent timestamp
- ✅ PASS if: calculated_sync_status shows recent activity
- ✅ PASS if: State changes detected compared to baseline

**SAVE OUTPUT TO:** `final_database_state_verification.txt`

---

## 📋 STEP 11: COLLECT PRODUCTION EVIDENCE

Gather comprehensive evidence of sync functionality:

```bash
# Collect container logs
sudo docker logs --tail 100 netbox-docker-netbox-1 > netbox_container_logs.txt
sudo docker logs --tail 100 netbox-docker-netbox-worker-1 > worker_container_logs.txt

# Collect RQ system status
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py shell -c "
import django_rq
from datetime import datetime

print('=== RQ SYSTEM STATUS ===')
print(f'Collection time: {datetime.now()}')

conn = django_rq.get_connection()
print(f'RQ Connection: {conn}')

# Get all queues
queues = list(conn.smembers('rq:queues'))
print(f'Available Queues: {[q.decode() for q in queues]}')

# Check each queue
for queue_name in queues:
    queue = django_rq.get_queue(queue_name.decode())
    jobs_count = len(queue)
    print(f'\\nQueue \"{queue_name.decode()}\": {jobs_count} jobs')
    
    # Show recent jobs
    for i, job in enumerate(queue.jobs[:3]):  # Show first 3 jobs
        print(f'  Job {i+1}: {job.id} - {job.func_name} - {job.get_status()}')
        if hasattr(job, 'created_at'):
            print(f'    Created: {job.created_at}')

print('=== RQ STATUS COMPLETE ===')
" > rq_system_status.txt

# Collect Celery configuration
sudo docker exec netbox-docker-netbox-1 python -c "
from netbox_hedgehog.celery import app
from datetime import datetime

print('=== CELERY CONFIGURATION ===')
print(f'Collection time: {datetime.now()}')
print(f'Celery App: {app}')
print(f'Broker URL: {app.conf.broker_url}')

print('\\nHedgehog Tasks:')
hedgehog_tasks = [name for name in app.tasks.keys() if 'netbox_hedgehog' in name]
for task in sorted(hedgehog_tasks):
    print(f'  {task}')

print('\\nBeat Schedule (Periodic Tasks):')
for name, config in app.conf.beat_schedule.items():
    if 'sync' in name.lower():
        print(f'  {name}:')
        print(f'    Schedule: {config[\"schedule\"]} seconds')
        print(f'    Task: {config[\"task\"]}')
        print(f'    Options: {config.get(\"options\", {})}')

print('=== CELERY CONFIG COMPLETE ===')
" > celery_configuration.txt

echo "✅ Evidence collection complete!"
echo "Files generated:"
ls -la *_logs.txt *_status.txt *_configuration.txt 2>/dev/null || echo "Some files may not exist"
```

**VALIDATION:**
- ✅ PASS if: All evidence files are generated
- ✅ PASS if: Container logs show sync-related activity
- ✅ PASS if: RQ system is operational with job processing
- ✅ PASS if: Celery configuration includes hedgehog tasks

---

## 📊 STEP 12: GENERATE FINAL ASSESSMENT

Create final assessment of sync functionality:

```bash
# Generate final test assessment
cat > final_sync_test_assessment.txt << 'EOF'
=== PRODUCTION SYNC VALIDATION ASSESSMENT ===
Test Date: $(date)
Test Duration: Complete testing cycle
Test Environment: Production NetBox Container
Test Target: RQ-based Periodic Sync Implementation

CRITICAL VALIDATIONS:
[ ] sync_status changed from 'never_synced'
[ ] last_sync updated with recent timestamps  
[ ] RQ tasks execute successfully
[ ] 60-second intervals observed
[ ] Database state changes detected

EVIDENCE FILES COLLECTED:
- fabric_baseline_state.txt
- manual_sync_test_results.txt
- rq_task_queue_test.txt
- periodic_sync_configuration.txt
- timing_validation_3min.txt
- final_database_state_verification.txt
- netbox_container_logs.txt
- worker_container_logs.txt
- rq_system_status.txt
- celery_configuration.txt

FINAL VERDICT: [MANUAL ASSESSMENT REQUIRED]

Compare baseline vs final states manually:
1. Check fabric_baseline_state.txt vs final_database_state_verification.txt
2. Verify timing_validation_3min.txt shows regular sync events
3. Confirm manual_sync_test_results.txt shows successful sync execution
4. Review container logs for any errors or issues

NEXT STEPS:
- If all validations pass: ✅ RQ-based periodic sync is VALIDATED
- If validations fail: ❌ Review logs and fix implementation
- Document any issues found for further investigation

=== ASSESSMENT COMPLETE ===
EOF

echo "📄 Final assessment template created: final_sync_test_assessment.txt"
echo "👤 MANUAL REVIEW REQUIRED: Compare all evidence files and fill out assessment"
```

---

## 🎯 FINAL VALIDATION CHECKLIST

**BEFORE CONCLUDING TESTING, VERIFY:**

### ✅ Critical Success Criteria

1. **Fabric State Changes:**
   - [ ] Compare `fabric_baseline_state.txt` vs `final_database_state_verification.txt`
   - [ ] Verify `sync_status` changed from 'never_synced'
   - [ ] Confirm `last_sync` has recent timestamps

2. **RQ Task Execution:**
   - [ ] Review `rq_task_queue_test.txt` for successful job completion
   - [ ] Check `rq_system_status.txt` for active queue processing
   - [ ] Verify no critical errors in worker logs

3. **Timing Validation:**
   - [ ] Analyze `timing_validation_3min.txt` for sync events
   - [ ] Calculate intervals between sync events (~60 seconds)
   - [ ] Confirm multiple sync cycles during 3-minute test

4. **Container Functionality:**
   - [ ] Both containers running and healthy throughout test
   - [ ] No deployment errors during file copying
   - [ ] Plugin tasks importable in worker container

### 📋 Evidence Files Verification

**MUST EXIST and contain relevant data:**
- `fabric_baseline_state.txt` - Initial fabric state
- `manual_sync_test_results.txt` - Manual sync execution proof  
- `rq_task_queue_test.txt` - RQ task execution evidence
- `timing_validation_3min.txt` - 60-second interval proof
- `final_database_state_verification.txt` - Final state comparison
- Container logs and system status files

### 🏆 FINAL VERDICT

**✅ SYNC IMPLEMENTATION VALIDATED** if:
- All critical success criteria met
- Database state changes documented  
- RQ tasks execute successfully
- Timing intervals approximately 60 seconds
- No critical errors in logs

**❌ IMPLEMENTATION NEEDS FIXES** if:
- Sync status remains 'never_synced'
- No timing events detected
- RQ task execution failures
- Critical errors in container logs

---

## 🚨 IMPORTANT NOTES

1. **Run ALL steps in sequence** - Each step builds on previous results
2. **Save ALL command outputs** - Evidence is critical for validation
3. **Monitor timing carefully** - Step 9 requires 3 minutes of observation
4. **Compare baseline vs final** - State changes prove sync functionality
5. **Review logs for errors** - Container logs reveal operational issues

**This testing validates REAL production sync functionality - no theoretical assumptions.**

---

*Generated by Production Sync Testing Framework*
*Date: $(date)*
*Environment: NetBox Container Production Deployment*