# Production Operations Guide: RQ-Based Periodic Sync

**Issue**: #40 - Periodic sync not triggering  
**Status**: ✅ **RESOLVED**  
**Date**: January 11, 2025

---

## 🚀 Quick Start (Immediate Resolution)

Your fabric sync issue is **RESOLVED**. To immediately fix the "Never Synced" problem:

```bash
# 1. Bootstrap sync schedules for all fabrics
python manage.py hedgehog_sync bootstrap

# 2. Verify your fabric is now scheduled
python manage.py hedgehog_sync status

# 3. Watch sync activity (optional)
python manage.py hedgehog_sync schedule
```

**Expected Result**: Your fabric with `sync_interval=60` will start syncing every 60 seconds, with status changing from "Never Synced" to "In Sync".

---

## 📋 Daily Operations

### Check Sync Status
```bash
# View all fabrics
python manage.py hedgehog_sync status

# View specific fabric  
python manage.py hedgehog_sync status --fabric "your-fabric-name"
```

### Monitor Scheduled Jobs
```bash
# View all scheduled sync jobs
python manage.py hedgehog_sync schedule
```

### Manual Sync Trigger
```bash
# Manually trigger sync for testing
python manage.py hedgehog_sync trigger "fabric-name"
```

### Test Sync Functionality
```bash
# Comprehensive sync test for specific fabric
python manage.py hedgehog_sync test-sync "fabric-name"
```

---

## 🔧 Troubleshooting Guide

### Problem: Sync Stopped Working
**Symptoms**: No sync activity, status stuck on old timestamp

**Solution**:
```bash
# Re-bootstrap all sync schedules
python manage.py hedgehog_sync bootstrap --force

# Verify schedules are active
python manage.py hedgehog_sync schedule
```

### Problem: "Never Synced" Status Persists
**Symptoms**: Fabric shows "Never Synced" despite sync_enabled=True

**Diagnosis**:
```bash
# Check if fabric needs sync
python manage.py hedgehog_sync status --fabric "problem-fabric"

# Verify configuration
python manage.py shell -c "
from netbox_hedgehog.models import HedgehogFabric
f = HedgehogFabric.objects.get(name='problem-fabric')
print(f'Enabled: {f.sync_enabled}, Interval: {f.sync_interval}')
print(f'Needs Sync: {f.needs_sync()}')
"
```

**Solution**:
```bash
# Manual trigger to jumpstart
python manage.py hedgehog_sync trigger "problem-fabric"

# Then re-bootstrap to ensure scheduling
python manage.py hedgehog_sync bootstrap
```

### Problem: Redis Connection Issues
**Symptoms**: Jobs not scheduling, RQ errors in logs

**Diagnosis**:
```bash
# Check Redis connectivity
redis-cli ping
# Should return: PONG
```

**Solution**:
```bash
# Start Redis service
sudo service redis-server start

# Or restart Redis
sudo service redis-server restart

# Re-bootstrap after Redis is running
python manage.py hedgehog_sync bootstrap
```

### Problem: Sync Errors
**Symptoms**: Fabric status shows "Error", sync_error field populated

**Diagnosis**:
```bash
# Check error details
python manage.py shell -c "
from netbox_hedgehog.models import HedgehogFabric
f = HedgehogFabric.objects.get(name='error-fabric')
print(f'Error: {f.sync_error}')
print(f'Connection Error: {f.connection_error}')
"
```

**Common Solutions**:
- **K8s Connection**: Verify `kubernetes_server`, `kubernetes_token`, `kubernetes_ca_cert`
- **Network Issues**: Check firewall, DNS resolution for K8s server
- **Authentication**: Validate K8s service account token is not expired

---

## 📊 Monitoring & Health Checks

### Sync Health Dashboard
```bash
# Quick health overview
python manage.py hedgehog_sync status | grep -E "(SUCCESS|ERROR|WARNING)"

# Detailed fabric analysis  
python manage.py hedgehog_sync status
```

### Performance Monitoring
```bash
# Check sync timing precision
python manage.py shell -c "
from netbox_hedgehog.models import HedgehogFabric
from django.utils import timezone
from datetime import timedelta

for f in HedgehogFabric.objects.filter(sync_enabled=True):
    if f.last_sync:
        expected_next = f.last_sync + timedelta(seconds=f.sync_interval)
        time_until = (expected_next - timezone.now()).total_seconds()
        status = 'ON TIME' if abs(time_until) < 10 else 'DRIFT DETECTED'
        print(f'{f.name}: {status} (next in {int(time_until)}s)')
"
```

### Log Analysis
```bash
# Monitor NetBox logs for sync activity
tail -f /path/to/netbox/logs/netbox.log | grep -i "fabric.*sync"

# Check deployment logs
tail -f /home/ubuntu/cc/hedgehog-netbox-plugin/deployment_*.log
```

---

## ⚙️ Configuration Management

### Add New Fabric for Sync
```python
# In Django shell or management command
from netbox_hedgehog.models import HedgehogFabric

fabric = HedgehogFabric.objects.create(
    name="new-fabric",
    kubernetes_server="https://k8s.example.com:6443",
    sync_enabled=True,
    sync_interval=300,  # 5 minutes
    kubernetes_namespace="default"
)

# Bootstrap schedules to include new fabric
# Run: python manage.py hedgehog_sync bootstrap
```

### Modify Sync Interval
```python
# Change sync frequency
fabric = HedgehogFabric.objects.get(name="fabric-name")
fabric.sync_interval = 120  # Change to 2 minutes
fabric.save()

# Re-bootstrap to apply new interval
# Run: python manage.py hedgehog_sync bootstrap
```

### Disable Sync for Maintenance
```python
# Temporarily disable sync
fabric = HedgehogFabric.objects.get(name="fabric-name")
fabric.sync_enabled = False
fabric.save()

# Re-enable when ready
fabric.sync_enabled = True
fabric.save()
# Run: python manage.py hedgehog_sync bootstrap
```

---

## 🔄 Backup & Recovery

### Backup Current State
```bash
# Manual backup before changes
cp -r netbox_hedgehog/jobs/ backup_jobs_$(date +%Y%m%d)/
cp netbox_hedgehog/models/fabric.py backup_fabric_$(date +%Y%m%d).py
```

### Restore from Backup
```bash
# Restore from automatic deployment backup
cp -r backups/backup_20250811_100741/* netbox_hedgehog/

# Or restore specific files
cp backups/backup_*/fabric.py netbox_hedgehog/models/
```

### Emergency Rollback
```bash
# If sync system fails completely
# 1. Stop all sync jobs
python manage.py shell -c "
import django_rq
scheduler = django_rq.get_scheduler('hedgehog_sync')
for job in scheduler.get_jobs():
    if 'fabric_sync' in job.id:
        scheduler.cancel(job.id)
"

# 2. Restore from backup
cp -r backups/backup_*/. netbox_hedgehog/

# 3. Restart NetBox service
sudo systemctl restart netbox
```

---

## 🎯 Success Validation

### Verify Issue Resolution
```bash
# Check the original problem is fixed
python manage.py shell -c "
from netbox_hedgehog.models import HedgehogFabric

# Find fabrics that previously showed 'Never Synced'
fabrics = HedgehogFabric.objects.filter(sync_enabled=True, sync_interval=60)
for f in fabrics:
    print(f'{f.name}: Status={f.calculated_sync_status}, Last={f.last_sync}')
    print(f'  Needs Sync: {f.needs_sync()}')
"
```

### Timing Precision Test
```bash
# Verify 60-second interval works precisely
python manage.py hedgehog_sync test-sync "fabric-with-60s-interval"
# Should complete in <5 seconds and schedule next run for +60s
```

### End-to-End Validation
```bash
# Run comprehensive validation
python validate_rq_sync_implementation.py
# Should show 100% success rate
```

---

## 📞 Support & Escalation

### Common Issues Resolution
1. **Sync never starts**: Run `bootstrap` command
2. **Timing drift**: Check Redis performance and server load  
3. **Authentication errors**: Verify K8s credentials and permissions
4. **Performance issues**: Check sync_interval isn't too aggressive

### When to Escalate
- Multiple fabrics showing sync errors simultaneously
- RQ scheduler completely unresponsive
- Database integrity issues with fabric records
- Performance degradation affecting NetBox overall

### Support Information
- **Log Files**: `/home/ubuntu/cc/hedgehog-netbox-plugin/deployment_*.log`
- **Backup Location**: `/home/ubuntu/cc/hedgehog-netbox-plugin/backups/`
- **Validation Script**: `validate_rq_sync_implementation.py`
- **Management Commands**: `python manage.py hedgehog_sync --help`

---

**Resolution Confirmed**: Your original issue where "fabric sync status shows 'Never Synced' despite sync_enabled=Yes and sync_interval=60 seconds" is now completely resolved with this RQ-based implementation.