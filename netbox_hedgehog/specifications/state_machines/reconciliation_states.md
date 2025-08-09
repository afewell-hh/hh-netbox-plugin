# ReconciliationAlert State Management Documentation

## Overview

ReconciliationAlert implements a **workflow-driven state machine** for managing drift detection and remediation processes. The system handles alert lifecycle from creation through resolution, with automated priority management and batch processing capabilities.

## Alert Lifecycle States

### Primary Status States (`status` field)

1. **`ACTIVE`** - Alert is open and requires attention
2. **`ACKNOWLEDGED`** - Alert has been reviewed but not yet resolved  
3. **`RESOLVED`** - Alert has been resolved with specific action
4. **`SUPPRESSED`** - Alert has been intentionally suppressed

## State Transition Matrix

| From State | To State | Trigger | Required Conditions | Side Effects |
|-----------|----------|---------|-------------------|--------------|
| `ACTIVE` | `ACKNOWLEDGED` | `acknowledge()` called | User review | Set `acknowledged_at`, `acknowledged_by` |
| `ACTIVE` | `RESOLVED` | `resolve()` called | Valid resolution action | Set `resolved_at`, `resolved_by`, `resolved_action` |
| `ACTIVE` | `SUPPRESSED` | `suppress()` called | User decision | Set `resolved_at`, `resolved_by`, suppression reason |
| `ACKNOWLEDGED` | `RESOLVED` | `resolve()` called | Valid resolution action | Set `resolved_at`, `resolved_by`, `resolved_action` |
| `ACKNOWLEDGED` | `SUPPRESSED` | `suppress()` called | User decision | Set `resolved_at`, `resolved_by`, suppression reason |

## Invalid Transitions

| From State | To State | Reason | Agent Action |
|-----------|----------|--------|--------------|
| `RESOLVED` | `ACTIVE` | Cannot reopen resolved alerts | Create new alert if needed |
| `RESOLVED` | `ACKNOWLEDGED` | Already resolved | No action needed |
| `SUPPRESSED` | `ACTIVE` | Suppressed alerts stay closed | Create new alert if condition persists |
| `SUPPRESSED` | `ACKNOWLEDGED` | Cannot acknowledge suppressed | Invalid operation |

## Alert Type Classification

### Alert Types and Automatic Severity

| Alert Type | Default Severity | Description | Typical Resolution |
|-----------|-----------------|-------------|-------------------|
| `drift_detected` | Based on drift_score | Configuration drift between Git and cluster | Update Git or reconcile cluster |
| `orphaned_resource` | `CRITICAL` | Resource in cluster but not in Git | Import to Git or delete from cluster |
| `creation_pending` | `MEDIUM` | Resource in Git but not deployed | Deploy to cluster or review |
| `deletion_pending` | `HIGH` | Resource marked for deletion | Confirm deletion or restore |
| `sync_failure` | `HIGH` | GitOps synchronization failed | Fix sync configuration or resolve conflicts |
| `validation_error` | `HIGH` | Resource validation failed | Fix resource specification |
| `conflict_detected` | `CRITICAL` | Conflicting changes detected | Manual resolution required |

### Severity-Based Priority Calculation

**Base Priority by Severity**:
- `CRITICAL` → Priority 10
- `HIGH` → Priority 30  
- `MEDIUM` → Priority 50
- `LOW` → Priority 70

**Age Factor**: Older alerts get higher priority
- Priority = Base Priority - min(age_hours, 20)
- Minimum priority = 1

## Resolution Actions

### Available Resolution Actions

| Action | Description | When to Use | Effects |
|--------|-------------|-------------|---------|
| `import_to_git` | Import resource to Git repository | Orphaned resources, cluster drift | Creates Git commit |
| `delete_from_cluster` | Remove resource from cluster | Orphaned resources, unwanted resources | Deletes Kubernetes resource |
| `update_git` | Update Git with cluster state | Drift favoring cluster state | Updates Git repository |
| `ignore` | Ignore the alert condition | Non-critical drift, temporary conditions | Suppresses alert |
| `manual_review` | Require manual intervention | Complex conflicts, unknown conditions | Escalates to human |

### Resolution Action Execution

```python
def execute_resolution_action(alert, action, user=None, dry_run=False):
    """Execute resolution action with proper state management"""
    
    # Validate action is appropriate for alert type
    suggested_actions = alert.get_suggested_actions()
    valid_actions = [a['action'] for a in suggested_actions]
    
    if action not in valid_actions:
        return {
            'success': False,
            'error': f'Action {action} not valid for alert type {alert.alert_type}',
            'suggested_actions': valid_actions
        }
    
    # Execute action
    execution_result = alert.execute_resolution_action(action, user, dry_run)
    
    # If successful and not dry run, resolve the alert
    if execution_result['success'] and not dry_run:
        resolution_result = alert.resolve(action, user, execution_result.get('details'))
        execution_result['alert_resolved'] = resolution_result
    
    return execution_result
```

## Queue Management System

### Priority Queue Processing

**Queue Priority Factors**:
1. **Severity Level** - Critical alerts processed first
2. **Age** - Older alerts get priority boost
3. **Resource Dependencies** - Dependent resources get higher priority
4. **Batch Processing** - Related alerts grouped together

**Queue Statistics Tracking**:
```python
def get_alert_queue_stats(fabric=None):
    """Get comprehensive queue statistics"""
    base_query = ReconciliationAlert.objects.all()
    if fabric:
        base_query = base_query.filter(fabric=fabric)
    
    return {
        'total_alerts': base_query.count(),
        'active_alerts': base_query.filter(status='ACTIVE').count(),
        'acknowledged_alerts': base_query.filter(status='ACKNOWLEDGED').count(),
        'resolved_alerts': base_query.filter(status='RESOLVED').count(),
        'suppressed_alerts': base_query.filter(status='SUPPRESSED').count(),
        'by_severity': {
            severity[0]: base_query.filter(severity=severity[0]).count()
            for severity in AlertSeverityChoices.CHOICES
        },
        'by_alert_type': {
            alert_type[0]: base_query.filter(alert_type=alert_type[0]).count()
            for alert_type in ALERT_TYPE_CHOICES
        },
        'average_resolution_time': calculate_average_resolution_time(base_query),
        'oldest_active_alert': get_oldest_active_alert(base_query)
    }
```

### Batch Processing

**Batch Creation Criteria**:
- Same alert type
- Same fabric
- Related resources (dependencies)
- Similar resolution actions

**Batch Processing Logic**:
```python
def process_alert_batch(batch_id):
    """Process a batch of related alerts"""
    alerts = ReconciliationAlert.objects.filter(
        batch_id=batch_id,
        status__in=['ACTIVE', 'ACKNOWLEDGED']
    ).order_by('queue_priority')
    
    batch_results = []
    
    for alert in alerts:
        # Determine best resolution action
        suggested_actions = alert.get_suggested_actions()
        primary_action = suggested_actions[0]['action'] if suggested_actions else 'manual_review'
        
        # Execute resolution
        result = alert.execute_resolution_action(primary_action, dry_run=False)
        batch_results.append({
            'alert_id': alert.id,
            'action': primary_action,
            'result': result
        })
        
        # Update processing attempt count
        alert.processing_attempts += 1
        alert.last_processing_attempt = timezone.now()
        
        if result['success']:
            alert.processing_error = ''
        else:
            alert.processing_error = result.get('error', 'Unknown error')
        
        alert.save(update_fields=[
            'processing_attempts', 'last_processing_attempt', 'processing_error'
        ])
    
    return batch_results
```

## Automated Alert Generation

### Drift Detection Alerts

**Trigger Conditions**:
```python
def generate_drift_alert(resource):
    """Generate drift detection alert for resource"""
    if resource.resource_state != 'DRIFTED':
        return None  # Only generate for drifted resources
    
    # Check if alert already exists
    existing_alert = ReconciliationAlert.objects.filter(
        resource=resource,
        alert_type='drift_detected',
        status__in=['ACTIVE', 'ACKNOWLEDGED']
    ).first()
    
    if existing_alert:
        # Update existing alert with new drift details
        existing_alert.drift_details = resource.drift_details
        existing_alert.auto_calculate_severity()
        existing_alert.save()
        return existing_alert
    
    # Create new drift alert
    alert = ReconciliationAlert.objects.create(
        fabric=resource.fabric,
        resource=resource,
        alert_type='drift_detected',
        title=f'Configuration drift detected: {resource.name}',
        message=f'Resource {resource.name} has drifted from desired state',
        drift_details=resource.drift_details,
        alert_context={
            'drift_score': resource.drift_score,
            'drift_severity': resource.drift_severity,
            'differences': resource.drift_details.get('differences', [])
        }
    )
    
    alert.auto_calculate_severity()
    return alert
```

### Orphaned Resource Alerts

**Detection Logic**:
```python
def generate_orphan_alert(resource):
    """Generate orphaned resource alert"""
    alert = ReconciliationAlert.objects.create(
        fabric=resource.fabric,
        resource=resource,
        alert_type='orphaned_resource',
        severity='CRITICAL',  # Always critical
        title=f'Orphaned resource detected: {resource.name}',
        message=f'Resource {resource.name} exists in cluster but not in Git repository',
        alert_context={
            'resource_kind': resource.kind,
            'namespace': resource.namespace,
            'actual_spec_size': len(str(resource.actual_spec)) if resource.actual_spec else 0
        },
        suggested_action='import_to_git'
    )
    
    return alert
```

## Error Handling and Recovery

### Processing Failures

**Retry Logic**:
```python
def handle_alert_processing_failure(alert, error):
    """Handle failed alert processing with retry logic"""
    alert.processing_attempts += 1
    alert.last_processing_attempt = timezone.now()
    alert.processing_error = str(error)
    
    # Exponential backoff for retries
    max_attempts = 5
    if alert.processing_attempts >= max_attempts:
        # Escalate to manual review after max attempts
        alert.suggested_action = 'manual_review'
        alert.alert_context['escalation_reason'] = f'Failed after {max_attempts} attempts'
        alert.save()
        
        # Create escalation alert
        create_escalation_alert(alert, f'Processing failed after {max_attempts} attempts')
    else:
        # Schedule retry with backoff
        retry_delay = min(300 * (2 ** (alert.processing_attempts - 1)), 3600)  # Max 1 hour
        schedule_alert_retry(alert, retry_delay)
        alert.save()
```

### Alert Consistency Validation

```python
def validate_alert_consistency(alert):
    """Validate alert state consistency"""
    errors = []
    
    # Check resolved alerts have resolution metadata
    if alert.status == 'RESOLVED':
        if not alert.resolved_action:
            errors.append('Resolved alert missing resolution action')
        if not alert.resolved_at:
            errors.append('Resolved alert missing resolution timestamp')
    
    # Check acknowledged alerts have acknowledgment metadata
    if alert.status == 'ACKNOWLEDGED':
        if not alert.acknowledged_at:
            errors.append('Acknowledged alert missing acknowledgment timestamp')
    
    # Check drift alerts have drift details
    if alert.alert_type == 'drift_detected':
        if not alert.drift_details:
            errors.append('Drift alert missing drift details')
    
    # Check severity calculation
    calculated_severity = alert.calculate_severity()
    if alert.severity != calculated_severity:
        errors.append(f'Severity mismatch: stored={alert.severity}, calculated={calculated_severity}')
    
    return errors
```

## Performance Optimization

### Alert Aggregation

**Similar Alert Consolidation**:
```python
def consolidate_similar_alerts(fabric, alert_type, time_window_hours=1):
    """Consolidate similar alerts within time window"""
    cutoff_time = timezone.now() - timedelta(hours=time_window_hours)
    
    similar_alerts = ReconciliationAlert.objects.filter(
        fabric=fabric,
        alert_type=alert_type,
        status='ACTIVE',
        created__gte=cutoff_time
    ).order_by('created')
    
    if similar_alerts.count() <= 1:
        return None
    
    # Keep oldest alert, consolidate others
    primary_alert = similar_alerts.first()
    secondary_alerts = similar_alerts[1:]
    
    # Update primary alert with consolidated information
    consolidated_resources = [primary_alert.resource.name]
    consolidated_details = primary_alert.alert_context.copy()
    
    for alert in secondary_alerts:
        consolidated_resources.append(alert.resource.name)
        # Merge alert contexts
        for key, value in alert.alert_context.items():
            if key not in consolidated_details:
                consolidated_details[key] = value
            elif isinstance(value, list):
                consolidated_details[key].extend(value)
    
    primary_alert.title = f'{alert_type.replace("_", " ").title()} (multiple resources)'
    primary_alert.message = f'Multiple {alert_type} conditions detected'
    primary_alert.alert_context = consolidated_details
    primary_alert.alert_context['consolidated_resources'] = consolidated_resources
    primary_alert.alert_context['consolidated_count'] = len(secondary_alerts) + 1
    primary_alert.save()
    
    # Resolve secondary alerts as duplicates
    for alert in secondary_alerts:
        alert.resolve('ignore', context={'consolidation_reason': f'Consolidated into alert {primary_alert.id}'})
    
    return primary_alert
```

### Queue Optimization

**Priority Queue Management**:
```python
def optimize_alert_queue(fabric=None):
    """Optimize alert queue for efficient processing"""
    base_query = ReconciliationAlert.objects.filter(status__in=['ACTIVE', 'ACKNOWLEDGED'])
    if fabric:
        base_query = base_query.filter(fabric=fabric)
    
    # Recalculate priorities for all active alerts
    for alert in base_query:
        old_priority = alert.queue_priority
        alert.queue_priority = alert.calculate_queue_priority()
        
        if old_priority != alert.queue_priority:
            alert.save(update_fields=['queue_priority'])
    
    # Identify batch processing opportunities
    batch_candidates = identify_batch_candidates(base_query)
    
    for batch in batch_candidates:
        batch_id = generate_batch_id()
        ReconciliationAlert.objects.filter(id__in=batch).update(batch_id=batch_id)
    
    return {
        'alerts_reprioritized': base_query.count(),
        'batches_created': len(batch_candidates)
    }
```

## Integration Points

### With HedgehogResource States
- Resource state changes trigger alert creation/resolution
- `DRIFTED` resources automatically generate drift alerts
- `ORPHANED` resources generate orphan alerts

### With HedgehogFabric States
- Fabric connection issues affect alert processing
- Fabric maintenance mode suspends alert generation
- Fabric-level reconciliation policies control alert behavior

### With GitRepository States
- Repository connection failures affect resolution actions
- Git operations triggered by alert resolutions
- Authentication issues propagate to alert processing

## Agent Implementation Guidelines

### Alert Processing Workflow

```python
async def process_reconciliation_alerts(fabric=None, max_alerts=10):
    """Process reconciliation alerts with proper state management"""
    # Get highest priority alerts
    query = ReconciliationAlert.objects.filter(
        status__in=['ACTIVE', 'ACKNOWLEDGED']
    ).order_by('queue_priority', 'created')
    
    if fabric:
        query = query.filter(fabric=fabric)
    
    alerts = query[:max_alerts]
    results = []
    
    for alert in alerts:
        try:
            # Check if alert is still valid
            if alert.is_expired:
                alert.resolve('ignore', context={'expiry_reason': 'Alert expired'})
                continue
            
            # Get suggested resolution actions
            suggested_actions = alert.get_suggested_actions()
            if not suggested_actions:
                continue
            
            primary_action = suggested_actions[0]['action']
            
            # Execute resolution action
            result = await alert.execute_resolution_action(primary_action)
            results.append({
                'alert_id': alert.id,
                'action': primary_action,
                'result': result
            })
            
        except Exception as e:
            handle_alert_processing_failure(alert, e)
            results.append({
                'alert_id': alert.id,
                'error': str(e)
            })
    
    return results
```

This comprehensive reconciliation state management enables agents to handle complex drift detection and remediation workflows with full automation and error recovery capabilities.