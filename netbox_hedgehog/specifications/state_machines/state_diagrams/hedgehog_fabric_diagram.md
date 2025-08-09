# HedgehogFabric State Diagrams

## Three-Dimensional State Space

HedgehogFabric has three independent state dimensions that work together:

### 1. Configuration Status Flow

```mermaid
stateDiagram-v2
    [*] --> PLANNED
    PLANNED --> ACTIVE : deployment_complete
    ACTIVE --> MAINTENANCE : planned_maintenance
    MAINTENANCE --> ACTIVE : maintenance_complete
    ACTIVE --> DECOMMISSIONED : permanent_shutdown
    MAINTENANCE --> DECOMMISSIONED : shutdown_during_maintenance
    DECOMMISSIONED --> [*]
    
    state PLANNED {
        [*] --> planning
        planning --> ready_for_deployment
    }
    
    state ACTIVE {
        [*] --> operational
        operational --> serving_traffic
    }
    
    state MAINTENANCE {
        [*] --> maintenance_mode
        maintenance_mode --> repair_in_progress
        repair_in_progress --> testing
    }
```

### 2. Connection Status Flow

```mermaid
stateDiagram-v2
    [*] --> UNKNOWN
    UNKNOWN --> TESTING : test_connection()
    TESTING --> CONNECTED : connection_success
    TESTING --> FAILED : connection_failure
    CONNECTED --> TESTING : retest_initiated
    CONNECTED --> FAILED : connection_lost
    FAILED --> TESTING : retry_connection
    
    state TESTING {
        [*] --> authenticating
        authenticating --> validating_cluster
        validating_cluster --> checking_permissions
    }
    
    state CONNECTED {
        [*] --> validated
        validated --> monitoring
        monitoring --> periodic_health_check
    }
    
    state FAILED {
        [*] --> error_detected
        error_detected --> auth_failure
        error_detected --> network_failure
        error_detected --> cluster_unavailable
    }
```

### 3. Sync Status Flow

```mermaid
stateDiagram-v2
    [*] --> NEVER_SYNCED
    NEVER_SYNCED --> SYNCING : first_sync_initiated
    SYNCING --> IN_SYNC : sync_completed_successfully
    SYNCING --> ERROR : sync_failed
    IN_SYNC --> SYNCING : scheduled_sync_started
    IN_SYNC --> OUT_OF_SYNC : drift_detected
    OUT_OF_SYNC --> SYNCING : reconciliation_started
    ERROR --> SYNCING : retry_sync
    
    state SYNCING {
        [*] --> fetching_git_state
        fetching_git_state --> fetching_cluster_state
        fetching_cluster_state --> comparing_states
        comparing_states --> applying_changes
    }
    
    state IN_SYNC {
        [*] --> synchronized
        synchronized --> monitoring_drift
        monitoring_drift --> periodic_validation
    }
    
    state OUT_OF_SYNC {
        [*] --> drift_detected
        drift_detected --> analyzing_differences
        analyzing_differences --> planning_reconciliation
    }
```

## Combined State Interaction Matrix

```mermaid
flowchart TD
    subgraph "Valid State Combinations"
        A[PLANNED + UNKNOWN + NEVER_SYNCED] --> B[PLANNED + CONNECTED + NEVER_SYNCED]
        B --> C[ACTIVE + CONNECTED + IN_SYNC]
        C --> D[ACTIVE + CONNECTED + OUT_OF_SYNC]
        D --> E[ACTIVE + CONNECTED + SYNCING]
        E --> C
        
        C --> F[MAINTENANCE + CONNECTED + IN_SYNC]
        F --> G[MAINTENANCE + UNKNOWN + NEVER_SYNCED]
        
        C --> H[DECOMMISSIONED + UNKNOWN + NEVER_SYNCED]
    end
    
    subgraph "Error Conditions"
        I[ACTIVE + FAILED + IN_SYNC] --> J[Alert: Connection Issue]
        K[DECOMMISSIONED + CONNECTED + SYNCING] --> L[Alert: Invalid State]
    end
    
    style I fill:#ffcccc
    style K fill:#ffcccc
```

## State Transition Triggers

```mermaid
flowchart LR
    subgraph "Automatic Triggers"
        AT1[Kubernetes API Errors] --> CS1[CONNECTED → FAILED]
        AT2[Drift Detection] --> SS1[IN_SYNC → OUT_OF_SYNC]
        AT3[ArgoCD Installation Complete] --> CF1[PLANNED → ACTIVE]
        AT4[Real-time Watch Events] --> SS2[State Validation]
    end
    
    subgraph "Manual Triggers"
        MT1[Update Credentials] --> CS2[current → TESTING]
        MT2[Manual Sync] --> SS3[current → SYNCING]
        MT3[Fabric Activation] --> CF2[PLANNED → ACTIVE]
        MT4[Maintenance Mode] --> CF3[ACTIVE → MAINTENANCE]
    end
    
    subgraph "Recovery Actions"
        RA1[Connection Retry] --> CS3[FAILED → TESTING]
        RA2[Reconciliation] --> SS4[OUT_OF_SYNC → SYNCING]
        RA3[Maintenance Complete] --> CF4[MAINTENANCE → ACTIVE]
    end
```

## Error Recovery Flows

```mermaid
stateDiagram-v2
    [*] --> Normal_Operation
    Normal_Operation --> Connection_Failure : kubernetes_api_error
    Normal_Operation --> Sync_Failure : sync_error
    Normal_Operation --> Drift_Detected : configuration_drift
    
    state Connection_Failure {
        [*] --> Retry_Connection
        Retry_Connection --> Update_Credentials : auth_error
        Retry_Connection --> Wait_For_Network : network_error
        Update_Credentials --> Test_Connection
        Wait_For_Network --> Test_Connection
        Test_Connection --> Success
        Test_Connection --> Escalate : max_retries_exceeded
    }
    
    state Sync_Failure {
        [*] --> Analyze_Error
        Analyze_Error --> Fix_Permissions : permission_error
        Analyze_Error --> Resolve_Conflicts : conflict_error
        Analyze_Error --> Retry_Sync : transient_error
        Fix_Permissions --> Retry_Sync
        Resolve_Conflicts --> Retry_Sync
        Retry_Sync --> Success
        Retry_Sync --> Escalate : persistent_failure
    }
    
    state Drift_Detected {
        [*] --> Create_Alert
        Create_Alert --> Analyze_Drift
        Analyze_Drift --> Auto_Reconcile : simple_drift
        Analyze_Drift --> Manual_Review : complex_drift
        Auto_Reconcile --> Success
        Manual_Review --> Success
    }
    
    Success --> Normal_Operation
    Escalate --> Manual_Intervention
    Manual_Intervention --> Normal_Operation
```

## State Validation Rules

```mermaid
flowchart TD
    subgraph "Validation Rules"
        V1{Status = DECOMMISSIONED?}
        V1 -->|Yes| V2{Sync Status = SYNCING or IN_SYNC?}
        V2 -->|Yes| E1[ERROR: Decommissioned fabric cannot sync]
        V2 -->|No| OK1[Valid State]
        
        V1 -->|No| V3{Connection Status = FAILED?}
        V3 -->|Yes| V4{Sync Status = IN_SYNC?}
        V4 -->|Yes| E2[ERROR: Cannot be in sync without connection]
        V4 -->|No| OK2[Valid State]
        
        V3 -->|No| V5{Status = ACTIVE and Connection = FAILED?}
        V5 -->|Yes| W1[WARNING: Active fabric with connection issues]
        V5 -->|No| OK3[Valid State]
    end
    
    style E1 fill:#ffcccc
    style E2 fill:#ffcccc
    style W1 fill:#fff2cc
    style OK1 fill:#ccffcc
    style OK2 fill:#ccffcc
    style OK3 fill:#ccffcc
```

This comprehensive state diagram documentation provides agents with visual understanding of all HedgehogFabric state transitions and interactions.