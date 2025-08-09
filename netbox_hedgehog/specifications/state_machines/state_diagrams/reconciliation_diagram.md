# ReconciliationAlert State Diagrams

## Alert Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> ACTIVE
    ACTIVE --> ACKNOWLEDGED : acknowledge()
    ACTIVE --> RESOLVED : resolve(action)
    ACTIVE --> SUPPRESSED : suppress(reason)
    ACKNOWLEDGED --> RESOLVED : resolve(action)
    ACKNOWLEDGED --> SUPPRESSED : suppress(reason)
    
    state ACTIVE {
        [*] --> alert_created
        alert_created --> priority_calculated
        priority_calculated --> queued_for_processing
        queued_for_processing --> awaiting_action
    }
    
    state ACKNOWLEDGED {
        [*] --> user_reviewed
        user_reviewed --> analysis_in_progress
        analysis_in_progress --> action_planned
    }
    
    state RESOLVED {
        [*] --> action_executed
        action_executed --> verification_complete
        verification_complete --> impact_assessed
        impact_assessed --> [*]
    }
    
    state SUPPRESSED {
        [*] --> intentionally_ignored
        intentionally_ignored --> suppression_logged
        suppression_logged --> [*]
    }
```

## Alert Type-Specific Workflows

### Drift Detection Alert Flow

```mermaid
flowchart TD
    DD[Drift Detected] --> CA[Create Alert]
    CA --> AS[Analyze Severity]
    
    AS --> LS{Low Severity?}
    AS --> MS{Medium Severity?}  
    AS --> HS{High Severity?}
    AS --> CS{Critical Severity?}
    
    LS -->|Yes| LSA[Auto-suggest: update_git]
    MS -->|Yes| MSA[Auto-suggest: import_to_git]
    HS -->|Yes| HSA[Auto-suggest: manual_review]
    CS -->|Yes| CSA[Escalate: immediate_review]
    
    LSA --> QP[Queue for Processing]
    MSA --> QP
    HSA --> QP  
    CSA --> IP[Immediate Processing]
    
    QP --> PA[Process Alert]
    IP --> PA
    
    PA --> EA{Execute Action}
    EA -->|update_git| UG[Update Git Repository]
    EA -->|import_to_git| IG[Import to Git]
    EA -->|manual_review| MR[Require Manual Review]
    EA -->|ignore| IA[Ignore Alert]
    
    UG --> VS[Verify Success]
    IG --> VS
    MR --> AUR[Await User Resolution]
    IA --> RA[Resolve Alert]
    
    VS --> RA
    AUR --> RA
    RA --> [*]
```

### Orphaned Resource Alert Flow

```mermaid
sequenceDiagram
    participant M as Monitor
    participant R as Resource
    participant A as Alert System
    participant U as User
    participant G as Git
    participant K as Kubernetes
    
    M->>R: Detect Orphaned Resource
    R->>A: Create Orphan Alert (CRITICAL)
    A->>A: Priority = 10 (Critical)
    A->>U: Immediate Notification
    
    U->>A: Acknowledge Alert
    A->>A: Status: ACKNOWLEDGED
    
    alt User Chooses Import
        U->>A: Resolve with import_to_git
        A->>G: Extract Resource Spec
        G->>G: Create YAML File
        G->>G: Commit to Repository
        G->>A: Import Success
        A->>A: Status: RESOLVED
        A->>R: Update State: ORPHANED → COMMITTED
    else User Chooses Delete
        U->>A: Resolve with delete_from_cluster
        A->>K: Delete Resource
        K->>A: Deletion Success
        A->>A: Status: RESOLVED
        A->>R: Remove Resource Record
    else User Chooses Ignore
        U->>A: Suppress Alert
        A->>A: Status: SUPPRESSED
        A->>R: Mark as Ignored
    end
```

### Sync Failure Alert Flow

```mermaid
stateDiagram-v2
    [*] --> Sync_Failure_Detected
    Sync_Failure_Detected --> Create_Alert
    Create_Alert --> Analyze_Cause
    
    state Analyze_Cause {
        [*] --> Check_Error_Type
        Check_Error_Type --> Permission_Error
        Check_Error_Type --> Network_Error
        Check_Error_Type --> Conflict_Error
        Check_Error_Type --> Unknown_Error
    }
    
    Permission_Error --> Auto_Fix_Permissions : can_auto_fix
    Permission_Error --> Manual_Permissions : cannot_auto_fix
    
    Network_Error --> Retry_With_Backoff
    Retry_With_Backoff --> Success : retry_succeeds
    Retry_With_Backoff --> Escalate : max_retries_exceeded
    
    Conflict_Error --> Manual_Conflict_Resolution
    Unknown_Error --> Manual_Investigation
    
    Auto_Fix_Permissions --> Retry_Sync
    Manual_Permissions --> Await_Admin_Fix
    Manual_Conflict_Resolution --> Await_User_Resolution
    Manual_Investigation --> Await_Admin_Investigation
    
    Retry_Sync --> Success : sync_succeeds
    Retry_Sync --> Failed : sync_fails_again
    
    Success --> Alert_Resolved
    Failed --> Escalate
    Escalate --> Manual_Review
    Await_Admin_Fix --> Retry_Sync
    Await_User_Resolution --> Retry_Sync
    Await_Admin_Investigation --> Manual_Review
    
    Alert_Resolved --> [*]
    Manual_Review --> [*]
```

## Queue Management and Priority System

### Priority Calculation Flow

```mermaid
flowchart TD
    AC[Alert Created] --> CSev[Calculate Severity]
    CSev --> CBP[Calculate Base Priority]
    
    CBP --> CRIT{Critical?}
    CBP --> HIGH{High?}
    CBP --> MED{Medium?}  
    CBP --> LOW{Low?}
    
    CRIT -->|Yes| P10[Priority = 10]
    HIGH -->|Yes| P30[Priority = 30]
    MED -->|Yes| P50[Priority = 50]
    LOW -->|Yes| P70[Priority = 70]
    
    P10 --> AAF[Apply Age Factor]
    P30 --> AAF
    P50 --> AAF
    P70 --> AAF
    
    AAF --> CAH{Calculate Age Hours}
    CAH --> AF[Age Factor = min(age_hours, 20)]
    AF --> FP[Final Priority = Base - Age Factor]
    FP --> MP[Max(Final Priority, 1)]
    MP --> UQ[Update Queue Position]
```

### Batch Processing Workflow

```mermaid
sequenceDiagram
    participant Q as Queue Manager
    participant B as Batch Processor
    participant A1 as Alert 1
    participant A2 as Alert 2
    participant A3 as Alert 3
    participant G as Git
    participant K as Kubernetes
    
    Q->>B: Identify Batch Candidates
    B->>B: Group Similar Alerts
    Note over B: Same type, fabric, related resources
    
    B->>A1: Add to Batch
    B->>A2: Add to Batch
    B->>A3: Add to Batch
    
    B->>B: Generate Batch ID
    B->>Q: Start Batch Processing
    
    par Process Alert 1
        B->>A1: Execute Resolution
        A1->>G: Git Operation
        G->>A1: Success
    and Process Alert 2
        B->>A2: Execute Resolution
        A2->>K: Kubernetes Operation
        K->>A2: Success
    and Process Alert 3
        B->>A3: Execute Resolution
        A3->>G: Git Operation
        G->>A3: Success
    end
    
    B->>B: Collect Results
    B->>Q: Batch Complete
    
    loop Update Each Alert
        B->>A1: Mark Resolved
        B->>A2: Mark Resolved
        B->>A3: Mark Resolved
    end
```

## Resolution Action State Machines

### Import to Git Action

```mermaid
stateDiagram-v2
    [*] --> Validate_Resource
    Validate_Resource --> Extract_Spec : resource_valid
    Validate_Resource --> Action_Failed : resource_invalid
    
    Extract_Spec --> Generate_YAML
    Generate_YAML --> Determine_Path
    Determine_Path --> Check_Git_Connection
    
    Check_Git_Connection --> Clone_Repository : connection_ok
    Check_Git_Connection --> Action_Failed : connection_failed
    
    Clone_Repository --> Write_File
    Write_File --> Stage_Changes
    Stage_Changes --> Create_Commit
    Create_Commit --> Push_Changes
    
    Push_Changes --> Action_Succeeded : push_success
    Push_Changes --> Action_Failed : push_failed
    
    Action_Succeeded --> Update_Resource_State
    Update_Resource_State --> [*]
    
    Action_Failed --> Log_Error
    Log_Error --> [*]
```

### Delete from Cluster Action

```mermaid
stateDiagram-v2
    [*] --> Validate_Deletion
    Validate_Deletion --> Check_Dependencies : safe_to_delete
    Validate_Deletion --> Action_Failed : unsafe_deletion
    
    Check_Dependencies --> Proceed_Delete : no_dependencies
    Check_Dependencies --> Confirm_Cascade : has_dependencies
    
    Confirm_Cascade --> Proceed_Delete : cascade_approved
    Confirm_Cascade --> Action_Failed : cascade_denied
    
    Proceed_Delete --> Connect_Kubernetes
    Connect_Kubernetes --> Execute_Deletion : connection_ok
    Connect_Kubernetes --> Action_Failed : connection_failed
    
    Execute_Deletion --> Verify_Deletion : delete_initiated
    Execute_Deletion --> Action_Failed : delete_failed
    
    Verify_Deletion --> Action_Succeeded : deletion_confirmed
    Verify_Deletion --> Action_Failed : deletion_incomplete
    
    Action_Succeeded --> Update_Records
    Update_Records --> [*]
    
    Action_Failed --> Log_Error
    Log_Error --> [*]
```

## Error Handling and Recovery

### Alert Processing Failure Recovery

```mermaid
flowchart TD
    APF[Alert Processing Failed] --> AE{Analyze Error}
    
    AE --> TE[Transient Error]
    AE --> PE[Permission Error]  
    AE --> RE[Resource Error]
    AE --> UE[Unknown Error]
    
    TE --> RWB[Retry with Backoff]
    RWB --> RCount{Retry Count < Max?}
    RCount -->|Yes| WAR[Wait and Retry]
    RCount -->|No| ESC[Escalate to Manual]
    
    PE --> FP[Fix Permissions]
    FP --> TRY[Try Again]
    TRY --> SUC[Success]
    TRY --> ESC
    
    RE --> VR[Validate Resource]
    VR --> FR[Fix Resource]
    FR --> TRY
    VR --> ESC
    
    UE --> LOG[Log Detailed Error]
    LOG --> ESC
    
    WAR --> SUC
    SUC --> RA[Resolve Alert]
    ESC --> MR[Manual Review Required]
    
    RA --> [*]
    MR --> [*]
```

### Alert Consistency Validation

```mermaid
flowchart TD
    subgraph "Alert Validation Rules"
        V1{Status = RESOLVED?} --> V2{Has resolved_action?}
        V2 -->|No| E1[ERROR: Missing resolution action]
        V2 -->|Yes| V3{Has resolved_at?}
        V3 -->|No| E2[ERROR: Missing resolution timestamp]
        V3 -->|Yes| OK1[Valid Resolved Alert]
        
        V1 -->|No| V4{Status = ACKNOWLEDGED?}
        V4 -->|Yes| V5{Has acknowledged_at?}
        V5 -->|No| E3[ERROR: Missing acknowledgment timestamp]
        V5 -->|Yes| OK2[Valid Acknowledged Alert]
        
        V4 -->|No| V6{Alert Type = drift_detected?}
        V6 -->|Yes| V7{Has drift_details?}
        V7 -->|No| E4[ERROR: Missing drift details]
        V7 -->|Yes| OK3[Valid Drift Alert]
        
        V6 -->|No| OK4[Valid Alert]
    end
    
    subgraph "Recovery Actions"
        E1 --> R1[Set default resolution action]
        E2 --> R2[Set resolution timestamp to now]
        E3 --> R3[Set acknowledgment timestamp to now]
        E4 --> R4[Recalculate drift details]
        
        R1 --> FIX[Apply Fix]
        R2 --> FIX
        R3 --> FIX
        R4 --> FIX
        
        FIX --> LOG[Log Correction]
        LOG --> VALID[Alert Now Valid]
    end
    
    style E1 fill:#ffcccc
    style E2 fill:#ffcccc
    style E3 fill:#ffcccc
    style E4 fill:#ffcccc
    style OK1 fill:#ccffcc
    style OK2 fill:#ccffcc
    style OK3 fill:#ccffcc
    style OK4 fill:#ccffcc
    style VALID fill:#ccffcc
```

## Monitoring and Analytics

### Alert Queue Analytics

```mermaid
flowchart TD
    subgraph "Alert Metrics"
        AM1[Total Alerts] --> AD[Alert Dashboard]
        AM2[Active Alerts] --> AD
        AM3[Resolution Rate] --> AD
        AM4[Average Resolution Time] --> AD
        AM5[Alert Types Distribution] --> AD
        AM6[Severity Distribution] --> AD
    end
    
    subgraph "Performance Metrics"
        PM1[Processing Success Rate] --> PD[Performance Dashboard]
        PM2[Batch Processing Efficiency] --> PD
        PM3[Error Recovery Rate] --> PD
        PM4[Resource Impact Analysis] --> PD
    end
    
    subgraph "Trend Analysis"
        TA1[Alert Volume Trends] --> TD[Trend Dashboard]
        TA2[Drift Pattern Analysis] --> TD
        TA3[Fabric Health Correlation] --> TD
        TA4[User Action Patterns] --> TD
    end
    
    AD --> RP[Generate Reports]
    PD --> RP
    TD --> RP
    
    RP --> IN[Insights & Recommendations]
    IN --> OPT[Optimize Alert Processing]
```

This comprehensive state diagram documentation provides agents with complete visual understanding of the reconciliation alert workflow, enabling automated drift detection and remediation with proper error handling and recovery mechanisms.