# Kubernetes Integration Context

## CRD Development Patterns
- **Custom Resource Definitions**: 12 ONF/FGD resource types
- **Controller Implementation**: Reconciliation loop patterns
- **Operator Framework**: Kubebuilder/Operator SDK integration
- **RBAC Configuration**: Service accounts and role definitions

## GitOps Workflow Patterns
- **Bidirectional Sync**: NetBox ↔ Git ↔ Kubernetes coordination
- **Conflict Resolution**: Automated merge strategies with fallback
- **Drift Detection**: Real-time configuration variance monitoring
- **Rollback Procedures**: Safe deployment reversal capabilities

## Enhanced Hive Orchestration
- **Fabric Synchronization**: Multi-cluster configuration management
- **Periodic Jobs**: RQ-based synchronization scheduling
- **State Validation**: Cross-system consistency verification
- **Performance Optimization**: Connection pooling and caching

## Quality Gates
- Cluster connectivity verification
- CRD registration success
- Operator functionality validation
- GitOps workflow operational status