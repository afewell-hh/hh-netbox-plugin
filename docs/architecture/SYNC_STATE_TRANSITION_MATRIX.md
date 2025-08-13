# Kubernetes Sync State Transition Matrix
## Complete State Coverage & Transition Validation

### State Transition Matrix

| From State | To State | Trigger | Conditions | Duration | Validation Required |
|-----------|----------|---------|------------|----------|-------------------|
| `not_configured` | `disabled` | Admin sets K8s server | `kubernetes_server != null`, `sync_enabled = False` | Immediate | K8s connectivity test |
| `not_configured` | `never_synced` | Admin configures & enables | `kubernetes_server != null`, `sync_enabled = True` | Immediate | K8s auth test |
| `disabled` | `never_synced` | Admin enables sync | `sync_enabled = True`, `last_sync = null` | Immediate | Scheduler pickup |
| `disabled` | `in_sync` | Admin enables with recent sync | `sync_enabled = True`, `last_sync < interval` | Immediate | State consistency |
| `never_synced` | `syncing` | Scheduler trigger | First sync starts | < 60 seconds | Task queue entry |
| `never_synced` | `error` | Initial sync fails | Auth/network/API errors | Variable | Error categorization |
| `syncing` | `in_sync` | Sync completes successfully | All CRDs processed | 30s - 5min | K8s state verification |
| `syncing` | `error` | Sync fails | Various error conditions | Variable | Error handling |
| `syncing` | `syncing` | Progress update | Intermediate status | Continuous | Progress tracking |
| `in_sync` | `out_of_sync` | Time passes | `current_time > last_sync + interval` | Variable | Timer accuracy |
| `in_sync` | `syncing` | Manual trigger | User-initiated sync | Immediate | Concurrent prevention |
| `in_sync` | `error` | System failure | Connection/auth loss | Variable | Health monitoring |
| `out_of_sync` | `syncing` | Scheduler trigger | Auto sync due | < 60 seconds | Scheduler precision |
| `out_of_sync` | `error` | Sync attempt fails | System unreachable | Variable | Retry logic |
| `error` | `syncing` | Retry mechanism | Auto/manual retry | Variable | Backoff strategy |
| `error` | `disabled` | Critical failure | Admin intervention | Manual | State reset |
| `error` | `in_sync` | Direct recovery | System self-heals | Variable | Recovery validation |

### State Validation Requirements

#### not_configured
- **Detection**: `kubernetes_server` is null or empty
- **GUI Display**: ❌ "Not Configured" with setup wizard link
- **Actions**: No sync possible, show configuration help
- **Tests**: Verify no sync tasks created, GUI shows config prompt

#### disabled  
- **Detection**: `sync_enabled = False`
- **GUI Display**: ⏸️ "Sync Disabled" with enable button
- **Actions**: Skip all sync operations
- **Tests**: Verify scheduler ignores, GUI shows disabled state

#### never_synced
- **Detection**: `sync_enabled = True` AND `last_sync = null`
- **GUI Display**: 🔄 "Pending First Sync" with progress indicator
- **Actions**: Highest priority sync scheduling
- **Tests**: Verify immediate scheduling (< 60 seconds)

#### in_sync
- **Detection**: `last_sync + sync_interval > current_time` AND last sync successful
- **GUI Display**: ✅ "In Sync" with last sync timestamp
- **Actions**: No sync required
- **Tests**: Verify no unnecessary sync tasks, accurate timestamp display

#### out_of_sync
- **Detection**: `last_sync + sync_interval <= current_time`
- **GUI Display**: ⚠️ "Out of Sync" with overdue duration
- **Actions**: Schedule sync with normal priority
- **Tests**: Verify timer accuracy, overdue calculation correct

#### syncing
- **Detection**: Active sync task exists for fabric
- **GUI Display**: 🔄 "Syncing..." with progress bar
- **Actions**: Monitor progress, prevent concurrent syncs
- **Tests**: Verify task status correlation, progress accuracy

#### error
- **Detection**: Sync failed with various error types
- **GUI Display**: ❌ "Error" with specific error message
- **Actions**: Retry logic, admin notification
- **Tests**: Verify error categorization, recovery paths

### Critical State Transitions

#### 1. never_synced → syncing (Priority: CRITICAL)
```python
def test_never_synced_immediate_scheduling():
    """
    CRITICAL: Never-synced fabrics must sync within 60 seconds
    """
    # Create never-synced fabric
    fabric = create_test_fabric(
        sync_enabled=True,
        last_sync=None,
        kubernetes_server="https://vlab-art.l.hhdev.io:6443"
    )
    
    # Start timing
    start_time = time.time()
    
    # Trigger scheduler
    trigger_scheduler()
    
    # Verify sync task created within 60 seconds
    sync_task = wait_for_sync_task(fabric.id, timeout=60)
    assert sync_task is not None
    assert time.time() - start_time < 60
    
    # Verify GUI shows syncing state
    gui_state = get_gui_state(fabric.id)
    assert gui_state['status'] == 'syncing'
    assert gui_state['icon'] == '🔄'
```

#### 2. in_sync → out_of_sync (Priority: HIGH)
```python
def test_sync_interval_expiration_accuracy():
    """
    HIGH: Accurate detection when sync interval expires
    """
    current_time = datetime.now(timezone.utc)
    sync_interval = 300  # 5 minutes
    
    # Create fabric with last sync exactly at interval boundary
    fabric = create_test_fabric(
        sync_enabled=True,
        last_sync=current_time - timedelta(seconds=sync_interval),
        sync_interval=sync_interval
    )
    
    # At boundary-1 second: should be in_sync
    with freeze_time(current_time - timedelta(seconds=1)):
        state = get_sync_state(fabric)
        assert state == SyncState.IN_SYNC
    
    # At exact boundary: should be out_of_sync
    with freeze_time(current_time):
        state = get_sync_state(fabric)
        assert state == SyncState.OUT_OF_SYNC
    
    # GUI must reflect change
    gui_state = get_gui_state(fabric.id)
    assert gui_state['status'] == 'out_of_sync'
    assert '⚠️' in gui_state['display']
```

#### 3. syncing → in_sync (Priority: HIGH)
```python
def test_sync_completion_state_update():
    """
    HIGH: Sync completion must update state immediately
    """
    fabric = create_test_fabric_in_syncing_state()
    
    # Mock successful sync completion
    with mock_successful_sync():
        complete_sync_task(fabric.id)
    
    # State should update immediately
    state = get_sync_state(fabric)
    assert state == SyncState.IN_SYNC
    
    # last_sync should be updated
    fabric.refresh_from_db()
    assert fabric.last_sync is not None
    assert fabric.last_sync > datetime.now(timezone.utc) - timedelta(seconds=5)
    
    # GUI should reflect new state within 5 seconds
    gui_state = poll_gui_state_change(fabric.id, timeout=5)
    assert gui_state['status'] == 'in_sync'
    assert '✅' in gui_state['display']
```

#### 4. error → syncing (Priority: MEDIUM)
```python
def test_error_recovery_retry_logic():
    """
    MEDIUM: Error states should have proper retry mechanisms
    """
    fabric = create_test_fabric_in_error_state(
        error_type='network_timeout',
        retry_count=0
    )
    
    # Should retry after exponential backoff
    expected_retry_time = calculate_exponential_backoff(0)  # First retry
    
    with mock_network_recovery():
        trigger_retry_logic(fabric.id)
        
        # Should transition to syncing
        wait_for_state_change(fabric.id, SyncState.SYNCING, timeout=expected_retry_time + 30)
        
        state = get_sync_state(fabric)
        assert state == SyncState.SYNCING
        
        # GUI should show retry progress
        gui_state = get_gui_state(fabric.id)
        assert 'Retrying' in gui_state['message']
```

### Edge Case State Transitions

#### Concurrent Sync Prevention
```python
def test_concurrent_sync_prevention():
    """
    EDGE CASE: Multiple sync attempts must be prevented
    """
    fabric = create_test_fabric(sync_enabled=True, last_sync=None)
    
    # Start first sync
    sync_task_1 = trigger_sync(fabric.id)
    assert get_sync_state(fabric) == SyncState.SYNCING
    
    # Attempt second sync - should be blocked
    sync_task_2 = trigger_sync(fabric.id)
    assert sync_task_2 is None  # Should be blocked
    
    # State should remain syncing (not duplicate)
    assert get_sync_state(fabric) == SyncState.SYNCING
    
    # GUI should show single sync operation
    gui_state = get_gui_state(fabric.id)
    assert gui_state['active_tasks'] == 1
```

#### State Corruption Recovery
```python
def test_state_corruption_recovery():
    """
    EDGE CASE: Handle corrupted state data
    """
    fabric = create_test_fabric()
    
    # Corrupt state data
    corrupt_fabric_state(fabric.id, {
        'sync_status': 'invalid_state',
        'last_sync': 'invalid_timestamp',
        'connection_status': None
    })
    
    # System should detect and recover
    recovery_result = trigger_state_recovery(fabric.id)
    assert recovery_result['success'] == True
    
    # Should reset to safe state
    fabric.refresh_from_db()
    assert fabric.sync_status in VALID_SYNC_STATES
    assert fabric.connection_status in VALID_CONNECTION_STATES
    
    # GUI should show recovery message
    gui_state = get_gui_state(fabric.id)
    assert 'State recovered' in gui_state['message']
```

### Performance State Transitions

#### High-Volume State Changes
```python
def test_rapid_state_transitions():
    """
    PERFORMANCE: Handle rapid state changes without corruption
    """
    fabric = create_test_fabric()
    
    # Generate 100 rapid state changes
    for i in range(100):
        # Alternate between different triggers
        if i % 3 == 0:
            trigger_manual_sync(fabric.id)
        elif i % 3 == 1:
            simulate_sync_completion(fabric.id)
        else:
            simulate_network_error(fabric.id)
        
        time.sleep(0.01)  # 10ms intervals
    
    # Final state should be consistent
    final_state = get_sync_state(fabric)
    assert final_state in VALID_SYNC_STATES
    
    # Database should be consistent
    assert_database_consistency(fabric.id)
    
    # GUI should show correct final state
    gui_state = get_gui_state(fabric.id)
    assert gui_state['status'] == final_state.value
```

### State Validation Test Matrix

| Test Type | State From | State To | Validation Method | Expected Result |
|-----------|------------|----------|------------------|----------------|
| **Immediate** | not_configured | never_synced | K8s connectivity | < 1 second |
| **Scheduled** | never_synced | syncing | Task queue | < 60 seconds |
| **Timed** | in_sync | out_of_sync | Interval expiry | Exact timing |
| **Recovery** | error | syncing | Retry logic | Exponential backoff |
| **Manual** | any | syncing | User trigger | < 5 seconds |
| **Completion** | syncing | in_sync | Sync success | Immediate |
| **Failure** | syncing | error | Sync failure | Error categorization |
| **Prevention** | syncing | syncing | Concurrent block | No duplicate tasks |

### GUI State Display Requirements

Each state transition must update the GUI within **5 seconds** with:

1. **Status Icon**: Correct emoji/icon for state
2. **Status Text**: Clear, actionable text description  
3. **Timestamp**: When state changed (if applicable)
4. **Progress**: For syncing states, show progress
5. **Error Details**: For error states, show specific error
6. **Actions**: Available actions (retry, configure, etc.)

### Test Evidence Requirements

Every state transition test must provide:

1. **Before State**: Verified initial state
2. **Trigger**: Exact condition that causes transition
3. **After State**: Verified final state
4. **Timing**: Measured transition duration
5. **GUI Evidence**: Screenshot or HTML verification
6. **Database Evidence**: Direct DB state verification
7. **K8s Evidence**: Independent cluster state check

This matrix ensures **100% coverage** of all possible state transitions with **bulletproof validation** and **extreme QA** to catch any implementation errors.