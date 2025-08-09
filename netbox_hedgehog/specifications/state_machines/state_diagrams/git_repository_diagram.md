# GitRepository State Diagrams

## Connection Status State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> TESTING : test_connection()
    TESTING --> CONNECTED : authentication_success
    TESTING --> FAILED : authentication_failure
    CONNECTED --> TESTING : manual_retest / scheduled_check
    CONNECTED --> FAILED : token_expiry / revocation
    FAILED --> TESTING : retry_connection
    
    state TESTING {
        [*] --> validating_url
        validating_url --> checking_credentials
        checking_credentials --> testing_repository_access
        testing_repository_access --> verifying_permissions
    }
    
    state CONNECTED {
        [*] --> authenticated
        authenticated --> monitoring_health
        monitoring_health --> periodic_validation
        periodic_validation --> ready_for_operations
    }
    
    state FAILED {
        [*] --> error_analysis
        error_analysis --> auth_error
        error_analysis --> network_error
        error_analysis --> repository_error
        auth_error --> awaiting_fix
        network_error --> awaiting_fix
        repository_error --> awaiting_fix
    }
```

## Authentication Type Workflows

### Token Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant R as Repository
    participant G as Git Provider
    participant S as System
    
    U->>R: set_credentials(token)
    R->>S: encrypt_credentials()
    S->>R: encrypted_data
    R->>R: status = TESTING
    R->>G: test_connection(token)
    
    alt Token Valid
        G->>R: connection_success + metadata
        R->>R: status = CONNECTED
        R->>R: update last_validated
    else Token Invalid/Expired
        G->>R: auth_failure
        R->>R: status = FAILED
        R->>R: set validation_error
    end
```

### SSH Key Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant R as Repository
    participant G as Git Provider
    participant S as System
    
    U->>R: set_credentials(private_key, passphrase)
    R->>S: encrypt_credentials()
    S->>R: encrypted_data
    R->>R: status = TESTING
    R->>G: test_ssh_connection(private_key)
    
    alt SSH Key Valid
        G->>R: connection_success
        R->>R: status = CONNECTED
    else SSH Key Invalid/No Access
        G->>R: auth_failure
        R->>R: status = FAILED
    end
```

### OAuth Authentication Flow

```mermaid
stateDiagram-v2
    [*] --> Initial_Auth
    Initial_Auth --> Token_Valid : oauth_flow_complete
    Token_Valid --> Token_Expired : token_expiry_detected
    Token_Valid --> Testing_Connection : periodic_check
    Token_Expired --> Refresh_Attempt : auto_refresh
    Refresh_Attempt --> Token_Valid : refresh_success
    Refresh_Attempt --> Auth_Failed : refresh_failed
    Testing_Connection --> Token_Valid : connection_success
    Testing_Connection --> Token_Expired : token_invalid
    Auth_Failed --> Manual_Reauth : user_intervention
    Manual_Reauth --> Token_Valid : reauth_success
```

## Error Handling and Recovery Patterns

### Connection Failure Recovery

```mermaid
flowchart TD
    CF[Connection Failure] --> AT{Analyze Error Type}
    
    AT --> AE[Authentication Error]
    AT --> NE[Network Error]
    AT --> RE[Repository Error]
    AT --> UE[Unknown Error]
    
    AE --> AE1{Token Expired?}
    AE1 -->|Yes| AE2[Generate New Token]
    AE1 -->|No| AE3[Check Token Permissions]
    AE2 --> RT[Retry Test]
    AE3 --> RT
    
    NE --> NE1{Transient Network Issue?}
    NE1 -->|Yes| NE2[Wait and Retry]
    NE1 -->|No| NE3[Check Network Configuration]
    NE2 --> RT
    NE3 --> MI[Manual Intervention]
    
    RE --> RE1{Repository Exists?}
    RE1 -->|Yes| RE2[Check Repository Permissions]
    RE1 -->|No| RE3[Verify Repository URL]
    RE2 --> RT
    RE3 --> MI
    
    UE --> UE1[Log Error Details]
    UE1 --> MI
    
    RT --> TC{Test Connection}
    TC -->|Success| CS[CONNECTED State]
    TC -->|Failure| FC{Failure Count < Max?}
    FC -->|Yes| EB[Exponential Backoff]
    FC -->|No| MI
    EB --> RT
    
    MI --> MS[Manual State]
    CS --> [*]
    MS --> [*]
```

### Credential Rotation Workflow

```mermaid
sequenceDiagram
    participant S as System
    participant R as Repository  
    participant CM as CredentialManager
    participant G as Git Provider
    participant B as Backup
    
    S->>R: rotate_credentials()
    R->>B: backup_current_credentials()
    B->>R: backup_created
    
    R->>CM: set_new_credentials()
    CM->>R: credentials_encrypted
    
    R->>R: status = TESTING
    R->>G: test_new_credentials()
    
    alt Credentials Valid
        G->>R: test_success
        R->>R: status = CONNECTED
        R->>B: confirm_rotation()
        B->>B: cleanup_old_backup
    else Credentials Invalid
        G->>R: test_failure
        R->>B: restore_from_backup()
        B->>R: old_credentials_restored
        R->>R: status = FAILED
        R->>S: rotation_failed
    end
```

## Health Monitoring State Flow

```mermaid
stateDiagram-v2
    [*] --> Monitoring_Active
    
    state Monitoring_Active {
        [*] --> Periodic_Check
        Periodic_Check --> Health_Good : connection_ok
        Periodic_Check --> Health_Warning : minor_issues
        Periodic_Check --> Health_Critical : major_issues
        
        Health_Good --> Periodic_Check : wait_interval
        Health_Warning --> Investigate_Issues
        Health_Critical --> Emergency_Response
        
        Investigate_Issues --> Auto_Fix : fixable_issue
        Investigate_Issues --> Alert_Admin : manual_fix_required
        
        Auto_Fix --> Periodic_Check : fix_applied
        Alert_Admin --> Awaiting_Resolution
        Awaiting_Resolution --> Periodic_Check : admin_resolved
        
        Emergency_Response --> Fail_Safe_Mode
        Fail_Safe_Mode --> Alert_Admin
    }
```

## Repository State Dependencies

```mermaid
flowchart TD
    subgraph "Repository State Dependencies"
        RS[Repository State] --> FS[Fabric States]
        RS --> GS[GitOps Operations]
        RS --> AS[Alert Generation]
        
        FS --> F1[Fabric Sync Status]
        FS --> F2[Fabric Connection Health]
        
        GS --> G1[Clone Operations]
        GS --> G2[Push Operations]  
        GS --> G3[Sync Operations]
        
        AS --> A1[Connection Alerts]
        AS --> A2[Authentication Alerts]
        AS --> A3[Health Alerts]
    end
    
    subgraph "State Propagation"
        CONNECTED --> Enable_Operations[Enable All Operations]
        FAILED --> Disable_Operations[Disable Git Operations]
        TESTING --> Suspend_Operations[Suspend Operations]
        PENDING --> Wait_For_Validation[Wait for Validation]
        
        Enable_Operations --> Normal_Fabric_Operation
        Disable_Operations --> Fabric_Sync_Disabled
        Suspend_Operations --> Temporary_Hold
        Wait_For_Validation --> Initial_Setup
    end
```

## Multi-Fabric Repository Sharing

```mermaid
flowchart TD
    subgraph "Shared Repository Pattern"
        GR[GitRepository] --> F1[Fabric A]
        GR --> F2[Fabric B]  
        GR --> F3[Fabric C]
        
        F1 --> D1[Directory: /fabric-a/]
        F2 --> D2[Directory: /fabric-b/]
        F3 --> D3[Directory: /fabric-c/]
        
        GR --> CS{Connection Status}
        CS -->|CONNECTED| AS[All Fabrics Active]
        CS -->|FAILED| NS[All Fabrics Suspended]
        CS -->|TESTING| WS[All Fabrics Waiting]
    end
    
    subgraph "Impact Analysis"
        AS --> Enable_All[Enable All Fabric Operations]
        NS --> Alert_All[Generate Alerts for All Fabrics]
        WS --> Suspend_All[Suspend All Fabric Operations]
    end
```

## State Validation and Consistency

```mermaid
flowchart TD
    subgraph "Repository State Validation"
        V1{Status = CONNECTED?} --> V2{Has last_validated?}
        V2 -->|No| E1[ERROR: Connected without validation]
        V2 -->|Yes| V3{Validation recent?}
        V3 -->|No| W1[WARNING: Stale validation]
        V3 -->|Yes| OK1[Valid State]
        
        V1 -->|No| V4{Status = FAILED?}
        V4 -->|Yes| V5{Has validation_error?}
        V5 -->|No| E2[ERROR: Failed without error message]
        V5 -->|Yes| OK2[Valid State]
        
        V4 -->|No| V6{Status = TESTING?}
        V6 -->|Yes| V7{Testing duration < threshold?}
        V7 -->|No| W2[WARNING: Stuck in testing]
        V7 -->|Yes| OK3[Valid State]
        
        V6 -->|No| OK4[Valid Pending State]
    end
    
    style E1 fill:#ffcccc
    style E2 fill:#ffcccc
    style W1 fill:#fff2cc
    style W2 fill:#fff2cc
    style OK1 fill:#ccffcc
    style OK2 fill:#ccffcc
    style OK3 fill:#ccffcc
    style OK4 fill:#ccffcc
```

This comprehensive state diagram documentation provides agents with complete visual understanding of GitRepository authentication and connection management workflows.