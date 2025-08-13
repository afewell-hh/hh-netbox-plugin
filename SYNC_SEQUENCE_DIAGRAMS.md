# Periodic Sync System - Sequence Diagrams

## Expected Flow (How It Should Work)

```mermaid
sequenceDiagram
    participant Django as Django App
    participant Plugin as Hedgehog Plugin
    participant Scheduler as RQ Scheduler
    participant Worker as RQ Worker
    participant Redis as Redis Queue
    participant K8s as Kubernetes

    Note over Django,K8s: Plugin Initialization Phase
    Django->>Plugin: ready() signal
    Plugin->>Plugin: import signals
    Plugin->>Plugin: _bootstrap_sync_schedules()
    Plugin->>Scheduler: bootstrap_all_fabric_schedules()
    Scheduler->>Redis: schedule(func=execute_fabric_sync, interval=300s)
    Note right of Redis: Job scheduled successfully

    Note over Django,K8s: Runtime Execution Phase (Every 5 minutes)
    Scheduler->>Redis: Enqueue fabric_sync_35 job
    Redis->>Worker: Dequeue job for execution
    Worker->>Worker: execute_fabric_sync(fabric_id=35)
    Worker->>K8s: Sync CRDs with cluster
    K8s-->>Worker: Sync results
    Worker->>Plugin: Update fabric.last_sync
    Worker->>Scheduler: Schedule next execution
    Scheduler->>Redis: schedule(next_run=now+300s)

    Note over Django,K8s: Continuous Loop Every 5 Minutes
    loop Every sync_interval
        Scheduler->>Redis: Enqueue job
        Worker->>Worker: Execute sync
        Worker->>Plugin: Update fabric state
        Worker->>Scheduler: Schedule next run
    end
```

## Actual Flow (Current Broken State)

```mermaid
sequenceDiagram
    participant Django as Django App
    participant Plugin as Hedgehog Plugin
    participant Scheduler as RQ Scheduler
    participant Worker as RQ Worker (MISSING)
    participant Redis as Redis Queue
    participant K8s as Kubernetes

    Note over Django,K8s: Plugin Initialization Phase ✅ WORKS
    Django->>Plugin: ready() signal
    Plugin->>Plugin: import signals
    Plugin->>Plugin: _bootstrap_sync_schedules()
    Plugin->>Scheduler: bootstrap_all_fabric_schedules()
    Scheduler->>Redis: schedule(func=execute_fabric_sync, interval=300s)
    Note right of Redis: Job scheduled successfully

    Note over Django,K8s: Runtime Execution Phase ❌ FAILS
    Scheduler->>Redis: Enqueue fabric_sync_35 job
    Note right of Redis: Job sits in queue forever
    
    rect rgb(255, 200, 200)
        Note over Worker: RQ Worker Service NOT RUNNING
        Note over Worker: No process to dequeue jobs
        Note over Worker: Jobs accumulate in Redis queue
    end
    
    Note over Plugin,K8s: No Sync Occurs
    Plugin->>Plugin: fabric.last_sync = NULL (never updated)
    Plugin->>Plugin: sync_status = "never_synced"
    
    Note over Django,K8s: Result: Zero Sync Operations
    Note right of K8s: Kubernetes state never synchronized
    Note right of Plugin: Fabric data becomes stale
```

## Infrastructure Architecture (Current vs Required)

### Current Architecture (BROKEN)

```mermaid
graph TB
    subgraph "Docker Deployment"
        NetBox["NetBox Container<br/>netbox-hedgehog:latest<br/>Port 8000:8080"]
        Redis["Redis Container<br/>redis:alpine"]
        Postgres["PostgreSQL Container<br/>postgres:13"]
    end
    
    subgraph "NetBox Process"
        Django["Django WSGI<br/>Web Server"]
        Plugin["Hedgehog Plugin<br/>✅ Loaded"]
        Scheduler["RQ Scheduler<br/>✅ Available"]
    end
    
    subgraph "Missing Services"
        Worker1["❌ RQ Worker<br/>NOT DEPLOYED"]
        Worker2["❌ RQ Scheduler Process<br/>NOT RUNNING"]
    end
    
    Django --> Plugin
    Plugin --> Scheduler
    Scheduler --> Redis
    Redis -.->|"Jobs Queue Up"| Worker1
    Redis -.->|"Never Consumed"| Worker2
    
    style Worker1 fill:#ffcccc
    style Worker2 fill:#ffcccc
    style NetBox fill:#cce5ff
```

### Required Architecture (FIXED)

```mermaid
graph TB
    subgraph "Docker Deployment"
        NetBox["NetBox Container<br/>netbox-hedgehog:latest<br/>Port 8000:8080"]
        Worker["RQ Worker Container<br/>netbox-hedgehog:latest<br/>Command: rqworker hedgehog_sync"]
        SchedulerSvc["RQ Scheduler Container<br/>netbox-hedgehog:latest<br/>Command: rqscheduler"]
        Redis["Redis Container<br/>redis:alpine"]
        Postgres["PostgreSQL Container<br/>postgres:13"]
    end
    
    subgraph "NetBox Process"
        Django["Django WSGI<br/>Web Server"]
        Plugin["Hedgehog Plugin<br/>✅ Loaded"]
    end
    
    subgraph "RQ Worker Process"
        WorkerProc["RQ Worker Process<br/>✅ Consumes Jobs"]
        SyncJob["Fabric Sync Job<br/>execute_fabric_sync()"]
    end
    
    subgraph "RQ Scheduler Process"
        SchedulerProc["RQ Scheduler Process<br/>✅ Manages Schedule"]
        Timer["Periodic Timer<br/>Every sync_interval"]
    end
    
    Django --> Plugin
    Plugin --> SchedulerProc
    SchedulerProc --> Timer
    Timer --> Redis
    Redis --> WorkerProc
    WorkerProc --> SyncJob
    SyncJob --> Kubernetes["Kubernetes API<br/>CRD Synchronization"]
    
    NetBox -.-> Postgres
    Worker -.-> Postgres
    SchedulerSvc -.-> Postgres
    NetBox -.-> Redis
    Worker -.-> Redis
    SchedulerSvc -.-> Redis
    
    style NetBox fill:#cce5ff
    style Worker fill:#ccffcc
    style SchedulerSvc fill:#ccffcc
    style WorkerProc fill:#ccffcc
    style SchedulerProc fill:#ccffcc
```

## Data Flow Analysis

### Configuration to Execution Flow

```mermaid
graph LR
    subgraph "Configuration Layer"
        Fabric["HedgehogFabric<br/>sync_enabled=True<br/>sync_interval=300"]
        Migration["Migration 0023<br/>scheduler_enabled field"]
    end
    
    subgraph "Plugin Bootstrap"
        Ready["Plugin.ready()"]
        Bootstrap["_bootstrap_sync_schedules()"]
        Validate["RQ_SCHEDULER_AVAILABLE<br/>✅ True"]
    end
    
    subgraph "Scheduling Layer ✅ WORKING"
        GetFabrics["Get sync-enabled fabrics"]
        Schedule["scheduler.schedule()"]
        Redis1["Redis Queue<br/>hedgehog_sync"]
    end
    
    subgraph "Execution Layer ❌ BROKEN"
        Worker["RQ Worker Process<br/>❌ NOT RUNNING"]
        Execute["execute_fabric_sync()<br/>❌ NEVER CALLED"]
        K8sSync["Kubernetes Sync<br/>❌ NO EXECUTION"]
    end
    
    Fabric --> Ready
    Migration --> Ready
    Ready --> Bootstrap
    Bootstrap --> Validate
    Validate --> GetFabrics
    GetFabrics --> Schedule
    Schedule --> Redis1
    Redis1 -.->|"Queue Jobs"| Worker
    Worker -.->|"Would Execute"| Execute
    Execute -.->|"Would Sync"| K8sSync
    
    style Worker fill:#ffcccc
    style Execute fill:#ffcccc
    style K8sSync fill:#ffcccc
```

## Error Propagation Analysis

### What Happens Without Workers

```mermaid
sequenceDiagram
    participant User as User/Admin
    participant NetBox as NetBox UI
    participant Plugin as Hedgehog Plugin
    participant Redis as Redis Queue
    participant Worker as Missing RQ Worker

    Note over User,Worker: User Creates Fabric with sync_enabled=True
    User->>NetBox: Create fabric with sync_interval=300
    NetBox->>Plugin: Save fabric (triggers signals)
    Plugin->>Plugin: Bootstrap schedules
    Plugin->>Redis: Schedule periodic sync jobs
    Note right of Redis: Jobs scheduled but never executed

    Note over User,Worker: Time Passes (5+ minutes)
    User->>NetBox: Check fabric sync status
    NetBox->>Plugin: Get fabric.last_sync
    Plugin-->>NetBox: last_sync = NULL
    NetBox-->>User: Status: "Never Synced"
    Note right of User: User sees "never synced" despite enabled sync

    Note over User,Worker: User Tries Manual Sync
    User->>NetBox: Click "Sync Now" button
    NetBox->>Plugin: Trigger manual sync
    Plugin->>Redis: Queue immediate sync job
    Note right of Redis: Manual job also queued, never executed
    
    rect rgb(255, 200, 200)
        Note over Worker: NO WORKER TO PROCESS JOBS
        Redis->>Worker: Job waiting...
        Worker-->>Redis: (No response - worker doesn't exist)
    end
    
    Plugin-->>NetBox: Sync appears successful (job queued)
    NetBox-->>User: "Sync triggered" (misleading)
    Note right of User: User thinks sync worked, but it didn't
```

## Fix Verification Flow

### Post-Fix Validation Sequence

```mermaid
sequenceDiagram
    participant Admin as Admin
    participant Docker as Docker Compose
    participant Worker as RQ Worker
    participant Scheduler as RQ Scheduler
    participant Redis as Redis Queue
    participant Plugin as Plugin
    
    Note over Admin,Plugin: Deploy RQ Services
    Admin->>Docker: docker-compose up -d
    Docker->>Worker: Start rqworker hedgehog_sync
    Docker->>Scheduler: Start rqscheduler
    
    Note over Admin,Plugin: Bootstrap Schedules  
    Admin->>Plugin: python manage.py hedgehog_sync bootstrap
    Plugin->>Redis: Schedule all fabric sync jobs
    
    Note over Admin,Plugin: Verify Execution
    Redis->>Worker: Dequeue fabric_sync job
    Worker->>Worker: execute_fabric_sync(fabric_id)
    Worker->>Plugin: Update fabric.last_sync
    Worker-->>Admin: Sync completed successfully
    
    Note over Admin,Plugin: Continuous Operation
    loop Every sync_interval
        Scheduler->>Redis: Enqueue next job
        Worker->>Worker: Execute sync
        Worker->>Plugin: Update state
    end
    
    Admin->>Plugin: Check fabric status
    Plugin-->>Admin: last_sync = [recent timestamp]
    Plugin-->>Admin: sync_status = "in_sync"
```

## Critical Path Analysis

### Bottleneck Identification

```mermaid
graph TD
    Start([Plugin Initialization]) --> Check{RQ_SCHEDULER_AVAILABLE?}
    Check -->|Yes ✅| Bootstrap[Bootstrap Schedules]
    Check -->|No ❌| Skip[Skip Bootstrap]
    
    Bootstrap --> Schedule[Schedule Jobs in Redis]
    Schedule --> Queue{Job Queue Status}
    
    Queue -->|Jobs Queued ✅| WorkerCheck{RQ Worker Running?}
    WorkerCheck -->|Yes ✅| Execute[Execute Sync Jobs]
    WorkerCheck -->|No ❌| Accumulate[Jobs Accumulate in Queue]
    
    Execute --> Success[Sync Successful]
    Accumulate --> Failure[Sync Never Executes]
    
    Skip --> NoSync[No Sync Scheduling]
    
    style Check fill:#e1f5fe
    style WorkerCheck fill:#ffecb3
    style Accumulate fill:#ffcdd2
    style Failure fill:#ffcdd2
    style Success fill:#c8e6c9
    
    Note1[CRITICAL BOTTLENECK:<br/>Missing RQ Worker Service]
    WorkerCheck -.-> Note1
```

---

*Sequence diagrams generated for forensic analysis on: 2025-08-11*