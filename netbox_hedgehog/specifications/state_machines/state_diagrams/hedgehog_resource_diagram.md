# HedgehogResource State Diagrams

## Six-State GitOps Lifecycle

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> COMMITTED : commit_to_git
    COMMITTED --> PENDING : git_sync_completed
    PENDING --> SYNCED : kubernetes_deployment_success
    SYNCED --> DRIFTED : drift_detected
    DRIFTED --> SYNCED : reconciliation_completed
    SYNCED --> PENDING : new_git_changes
    ORPHANED --> COMMITTED : import_to_git
    ORPHANED --> DRAFT : begin_editing
    SYNCED --> ORPHANED : removed_from_git
    PENDING --> ORPHANED : removed_from_git
    
    state DRAFT {
        [*] --> creating_changes
        creating_changes --> validating_spec
        validating_spec --> ready_for_commit
    }
    
    state COMMITTED {
        [*] --> pushed_to_git
        pushed_to_git --> awaiting_sync
        awaiting_sync --> sync_ready
    }
    
    state PENDING {
        [*] --> deployment_queued
        deployment_queued --> gitops_processing
        gitops_processing --> deploying_to_cluster
    }
    
    state SYNCED {
        [*] --> deployed_successfully
        deployed_successfully --> monitoring_drift
        monitoring_drift --> health_check
    }
    
    state DRIFTED {
        [*] --> drift_analysis
        drift_analysis --> calculating_differences
        calculating_differences --> planning_reconciliation
    }
    
    state ORPHANED {
        [*] --> orphan_detected
        orphan_detected --> analyzing_cluster_state
        analyzing_cluster_state --> awaiting_decision
    }
```

## Full GitOps Workflow Patterns

### Standard Creation Workflow

```mermaid
sequenceDiagram
    participant U as User
    participant R as Resource
    participant G as Git
    participant K as Kubernetes
    participant A as ArgoCD/GitOps
    
    U->>R: Create/Edit Resource
    R->>R: State: DRAFT
    Note over R: draft_spec populated
    
    U->>R: Commit Changes
    R->>G: Push to Repository
    G->>R: Commit Success
    R->>R: State: COMMITTED
    Note over R: desired_spec from draft_spec
    
    A->>G: Detect Changes
    G->>A: New Commit
    A->>K: Deploy Resource
    R->>R: State: PENDING
    Note over R: Waiting for deployment
    
    K->>A: Deployment Success
    A->>R: Update Status
    R->>R: State: SYNCED
    Note over R: actual_spec populated
```

### Drift Detection and Resolution

```mermaid
sequenceDiagram
    participant M as Monitor
    participant R as Resource
    participant K as Kubernetes
    participant A as AlertSystem
    participant U as User
    
    M->>K: Poll Cluster State
    K->>M: Current Resource Spec
    M->>R: Update actual_spec
    R->>R: calculate_drift()
    
    alt Drift Detected
        R->>R: State: SYNCED → DRIFTED
        R->>A: Create Drift Alert
        A->>U: Notify User
        
        U->>R: Choose Resolution
        alt Update Git
            U->>R: Update desired_spec
            R->>R: State: DRIFTED → COMMITTED
        else Reconcile Cluster
            U->>K: Apply desired_spec
            K->>R: Update actual_spec
            R->>R: State: DRIFTED → SYNCED
        end
    else No Drift
        R->>R: State: SYNCED (maintained)
    end
```

### Orphan Resource Adoption

```mermaid
flowchart TD
    OR[Orphaned Resource Detected] --> AS{Analyze Source}
    
    AS --> MA[Manual Creation]
    AS --> LD[Legacy Deployment]
    AS --> ED[External Deployment]
    
    MA --> DA[Decide Action]
    LD --> DA
    ED --> DA
    
    DA --> IG[Import to Git]
    DA --> DC[Delete from Cluster]
    DA --> IN[Ignore/Monitor]
    
    IG --> IG1[Extract Spec]
    IG1 --> IG2[Generate YAML]
    IG2 --> IG3[Create Git Commit]
    IG3 --> IG4[State: ORPHANED → COMMITTED]
    
    DC --> DC1[Confirm Deletion]
    DC1 --> DC2[Delete from Kubernetes]
    DC2 --> DC3[Remove Resource Record]
    
    IN --> IN1[Mark as Ignored]
    IN1 --> IN2[Suppress Alerts]
    IN2 --> IN3[Monitor Only]
```

## State Transition Validation

```mermaid
flowchart TD
    subgraph "Valid Transitions"
        VT1[DRAFT → COMMITTED] --> VT1C{Has draft_spec?}
        VT1C -->|Yes| VT1OK[✓ Valid]
        VT1C -->|No| VT1E[✗ Missing draft]
        
        VT2[COMMITTED → PENDING] --> VT2C{Has desired_spec?}
        VT2C -->|Yes| VT2OK[✓ Valid]
        VT2C -->|No| VT2E[✗ Missing desired state]
        
        VT3[PENDING → SYNCED] --> VT3C{Has actual_spec?}
        VT3C -->|Yes| VT3OK[✓ Valid]
        VT3C -->|No| VT3E[✗ Missing actual state]
        
        VT4[SYNCED → DRIFTED] --> VT4C{Has drift_details?}
        VT4C -->|Yes| VT4OK[✓ Valid]
        VT4C -->|No| VT4E[✗ Missing drift analysis]
    end
    
    subgraph "Invalid Transitions"
        IT1[DRAFT → SYNCED] --> IT1E[✗ Cannot skip commit/deploy]
        IT2[COMMITTED → DRIFTED] --> IT2E[✗ Must deploy first]
        IT3[PENDING → DRIFTED] --> IT3E[✗ Must complete deployment]
        IT4[ORPHANED → SYNCED] --> IT4E[✗ Must import or edit first]
    end
    
    style VT1OK fill:#ccffcc
    style VT2OK fill:#ccffcc
    style VT3OK fill:#ccffcc
    style VT4OK fill:#ccffcc
    style VT1E fill:#ffcccc
    style VT2E fill:#ffcccc
    style VT3E fill:#ffcccc
    style VT4E fill:#ffcccc
    style IT1E fill:#ffcccc
    style IT2E fill:#ffcccc
    style IT3E fill:#ffcccc
    style IT4E fill:#ffcccc
```

## Drift Analysis State Machine

```mermaid
stateDiagram-v2
    [*] --> Drift_Check_Initiated
    Drift_Check_Initiated --> Compare_States
    
    state Compare_States {
        [*] --> Check_Desired_Exists
        Check_Desired_Exists --> Check_Actual_Exists
        Check_Actual_Exists --> Perform_Comparison
    }
    
    Perform_Comparison --> No_Drift : specs_match
    Perform_Comparison --> Spec_Drift : specs_differ
    Perform_Comparison --> Desired_Only : no_actual_spec
    Perform_Comparison --> Actual_Only : no_desired_spec
    
    state Spec_Drift {
        [*] --> Calculate_Score
        Calculate_Score --> Categorize_Severity
        Categorize_Severity --> Generate_Diff_Details
    }
    
    state Desired_Only {
        [*] --> Check_Deployment_Status
        Check_Deployment_Status --> Creation_Pending
        Check_Deployment_Status --> Deployment_Failed
    }
    
    state Actual_Only {
        [*] --> Check_Git_Status  
        Check_Git_Status --> Orphaned_Resource
        Check_Git_Status --> Recently_Deleted
    }
    
    No_Drift --> [*] : in_sync
    Spec_Drift --> [*] : spec_drift
    Creation_Pending --> [*] : creation_pending
    Deployment_Failed --> [*] : deployment_failed
    Orphaned_Resource --> [*] : actual_only
    Recently_Deleted --> [*] : deletion_pending
```

## Resource State Dependencies

```mermaid
flowchart TD
    subgraph "Resource Dependencies"
        R1[Resource A] --> R2[Resource B]
        R2 --> R3[Resource C]
        R1 --> R3
        
        R1S[State: SYNCED] --> R2C{B can deploy?}
        R2C -->|Yes| R2D[Deploy B]
        R2C -->|No| R2W[Wait for A]
        
        R2S[B State: SYNCED] --> R3C{C can deploy?}
        R3C -->|Yes| R3D[Deploy C]
        R3C -->|No| R3W[Wait for B]
    end
    
    subgraph "Dependency Impact"
        DR[Dependency Drift] --> DI{Impact Analysis}
        DI --> DI1[Cascade Update Needed]
        DI --> DI2[Independent Change]
        DI --> DI3[Conflict Detected]
        
        DI1 --> CU[Cascade Update]
        DI2 --> IC[Independent Change]
        DI3 --> CR[Conflict Resolution]
    end
```

## Batch State Operations

```mermaid
sequenceDiagram
    participant B as BatchProcessor
    participant R1 as Resource 1
    participant R2 as Resource 2
    participant R3 as Resource 3
    participant G as Git
    participant K as Kubernetes
    
    B->>B: Start Transaction
    B->>R1: Check State
    B->>R2: Check State
    B->>R3: Check State
    
    Note over B: Validate all transitions are valid
    
    alt All Valid
        B->>G: Batch Git Operations
        G->>B: Success
        B->>R1: Update State
        B->>R2: Update State
        B->>R3: Update State
        B->>B: Commit Transaction
    else Any Invalid
        B->>B: Rollback Transaction
        B->>B: Report Errors
    end
    
    B->>K: Trigger Kubernetes Sync
    K->>B: Deployment Status
    
    loop Monitor Deployment
        B->>K: Check Status
        K->>B: Current State
        B->>R1: Update if needed
        B->>R2: Update if needed
        B->>R3: Update if needed
    end
```

## Error Recovery Patterns

### State Inconsistency Recovery

```mermaid
flowchart TD
    SI[State Inconsistency Detected] --> AT{Analyze Type}
    
    AT --> MD[Missing Data]
    AT --> TS[Timestamp Issues]
    AT --> DS[Drift Score Mismatch]
    AT --> IS[Invalid State Combination]
    
    MD --> MD1[SYNCED without actual_spec]
    MD --> MD2[DRIFTED without drift_details]
    MD --> MD3[COMMITTED without desired_spec]
    
    MD1 --> FAS[Fetch Actual State]
    MD2 --> CDC[Calculate Drift]
    MD3 --> RGS[Restore Git State]
    
    TS --> TS1[actual_updated > desired_updated in SYNCED]
    TS1 --> RTS[Recalculate Timestamps]
    
    DS --> DS1[SYNCED with drift_score > 0]
    DS --> DS2[DRIFTED with drift_score = 0]
    DS1 --> CTS[Change to DRIFTED]
    DS2 --> CTS2[Change to SYNCED]
    
    IS --> IS1[Validate Transition Rules]
    IS1 --> FVS[Force Valid State]
    
    FAS --> VR[Validation Complete]
    CDC --> VR
    RGS --> VR
    RTS --> VR
    CTS --> VR
    CTS2 --> VR
    FVS --> VR
    
    VR --> LS[Log State Fix]
    LS --> NS[Notify Systems]
```

### Deployment Failure Recovery

```mermaid
stateDiagram-v2
    [*] --> Deployment_Failed
    Deployment_Failed --> Analyze_Failure
    
    state Analyze_Failure {
        [*] --> Check_Error_Type
        Check_Error_Type --> Resource_Conflict
        Check_Error_Type --> Permission_Error
        Check_Error_Type --> Validation_Error
        Check_Error_Type --> Network_Error
    }
    
    Resource_Conflict --> Manual_Resolution
    Permission_Error --> Fix_Permissions
    Validation_Error --> Fix_Specification
    Network_Error --> Retry_Deployment
    
    Fix_Permissions --> Retry_Deployment
    Fix_Specification --> Update_Git
    Update_Git --> Retry_Deployment
    
    Retry_Deployment --> Success : deployment_succeeds
    Retry_Deployment --> Max_Retries_Reached : retry_limit_exceeded
    
    Success --> SYNCED
    Manual_Resolution --> PENDING
    Max_Retries_Reached --> DRAFT
    
    SYNCED --> [*]
    PENDING --> [*]
    DRAFT --> [*]
```

This comprehensive state diagram documentation enables agents to understand and implement the complete HedgehogResource GitOps lifecycle with proper error handling and recovery mechanisms.