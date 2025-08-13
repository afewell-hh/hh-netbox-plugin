"""
Kubernetes Synchronization Test Suite

Test-Driven Development using London School approach for K8s sync functionality.
This test suite MUST fail initially and drive implementation to success.

London School TDD Approach:
- Outside-in development (from user behavior to implementation)
- Mock-driven development (isolate units and define contracts)
- Behavior verification (focus on interactions between objects)
- Contract definition through mock expectations

Test Coverage:
- 7 sync states with precise timing requirements
- K8s cluster integration with vlab-art.l.hhdev.io:6443
- GUI state validation with actual HTML verification
- Error injection and recovery scenarios
- Performance benchmarks and timing validation
- Real cluster connectivity and sync operations
"""

# Test Configuration
K8S_CLUSTER_URL = "https://vlab-art.l.hhdev.io:6443"
SERVICE_ACCOUNT = "hnp-sync"

# Sync States for Testing
SYNC_STATES = [
    'not_configured',
    'disabled', 
    'never_synced',
    'in_sync',
    'out_of_sync',
    'syncing',
    'error'
]

# Timing Requirements (seconds)
TIMING_REQUIREMENTS = {
    'state_detection': 5,
    'gui_update': 2,
    'sync_scheduling': 60,
    'state_transition': 1,
    'api_response': 0.2
}