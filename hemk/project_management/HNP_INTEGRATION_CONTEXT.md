# HNP Integration Context for HEMK Project Manager

**Document Purpose**: Provide HEMK Project Manager with essential context about the parent Hedgehog NetBox Plugin (HNP) project to inform integration requirements and design decisions.

**Target Audience**: HEMK Project Manager Agent  
**Last Updated**: Based on MVP2 completion status  
**Integration Level**: Critical - HEMK success depends on proper HNP integration

---

## HNP Project Status Overview

### Current State: MVP2 Complete
The Hedgehog NetBox Plugin has successfully completed MVP2, achieving a revolutionary transformation from Kubernetes-first sync model to comprehensive Git-first GitOps platform. The project is currently ready for User Acceptance Testing with production-ready capabilities.

**Key MVP2 Achievements**:
- Complete Git-first architecture implementation
- Six-state resource lifecycle management (DRAFT → COMMITTED → SYNCED → LIVE → DRIFTED → ORPHANED)
- Progressive disclosure UI for GitOps workflows
- Multi-repository Git authentication and management
- Zero regressions from MVP1 functionality

### HNP Core Capabilities (Relevant to HEMK)

**GitOps Workflow Engine**:
- Multi-repository authentication and access management
- Fabric-to-GitOps directory mapping (any-to-any relationship)
- Automated CRD discovery and synchronization
- Drift detection and reconciliation workflows
- Alert queue management for configuration conflicts

**External Integration Points**:
- GitOps tool API integration (ArgoCD/Flux)
- Prometheus metrics collection and analysis
- Grafana dashboard integration
- Kubernetes cluster connectivity (multiple clusters)
- Git provider integration (GitHub, GitLab, etc.)

---

## HEMK Integration Requirements

### Critical Integration Points

**1. GitOps Tool Integration**
```python
# Conceptual API pattern HNP expects
class GitOpsIntegration:
    def get_application_status(self, app_name: str) -> dict
    def trigger_sync(self, app_name: str) -> dict
    def get_sync_history(self, app_name: str) -> list
    def validate_repository_access(self, repo_url: str) -> bool
```

**HNP Dependencies**:
- GitOps tool (ArgoCD or Flux) must be accessible via HTTPS API
- Authentication mechanism (service account, API tokens)
- Repository access validation capabilities
- Application deployment and status monitoring
- Sync operation triggering and monitoring

**2. Monitoring Integration**
```python
# Conceptual API pattern HNP expects
class MonitoringIntegration:
    def query_metrics(self, query: str, timerange: str) -> dict
    def get_fabric_health(self, fabric_id: str) -> dict
    def create_alert_rule(self, rule_config: dict) -> bool
    def get_dashboard_url(self, dashboard_id: str) -> str
```

**HNP Dependencies**:
- Prometheus API access for metrics queries
- Hedgehog-specific metrics collection
- Grafana dashboard access and embedding
- Alert rule management and notification
- Custom dashboard creation and management

### Integration Architecture Patterns

**Multi-Cluster Management**:
- HNP manages connections to multiple Kubernetes clusters
- Each fabric in HNP maps to one Hedgehog Controller Kubernetes Cluster (HCKC)
- Each fabric may also connect to external management components
- HEMK provides one possible deployment pattern for external components

**Authentication Flow**:
```
HNP ←→ Git Repositories (multiple, any-to-any with fabrics)
HNP ←→ HCKC (per fabric, Hedgehog controller clusters)
HNP ←→ HEMK/External Tools (GitOps, monitoring)
```

**Configuration Management**:
- HNP stores fabric-to-GitOps directory mappings
- HNP manages authentication credentials for external systems
- HNP tracks external component availability and health
- HNP provides UI for managing external component connections

---

## HNP User Workflow Context

### Target User Profile
**Traditional Enterprise Network Engineers**:
- Strong background in switching, routing, VLANs, network protocols
- Limited or no experience with Kubernetes operations
- Familiar with CLI and GUI management tools
- Expectation of enterprise-grade reliability and support
- Need for guided, step-by-step operational procedures

### Current User Journey (Post-MVP2)
1. **Repository Setup**: User configures Git repository for GitOps workflows
2. **Fabric Creation**: User creates fabric in HNP with GitOps directory mapping
3. **External Tool Connection**: User configures connections to GitOps and monitoring tools
4. **CRD Management**: User manages Hedgehog CRDs through Git-first workflows
5. **Monitoring and Operations**: User monitors fabric health through integrated dashboards

### HEMK Integration Points in User Journey
**Where HEMK Adds Value**:
- **Step 3**: Simplify external tool deployment and configuration
- **Pre-Step 1**: Enable users to deploy required infrastructure before starting GitOps workflows
- **Ongoing Operations**: Provide simplified management of external infrastructure

**User Experience Requirements**:
- HEMK deployment should be simpler than manual external tool setup
- HEMK should integrate seamlessly with existing HNP workflows
- Users should have choice between HEMK and manual external tool deployment
- HEMK should provide operational guidance for non-Kubernetes experts

---

## Technical Integration Specifications

### API Integration Requirements

**GitOps Integration APIs**:
```python
# HNP expects these capabilities from GitOps tools
class GitOpsToolAPI:
    def authenticate(self, credentials: dict) -> bool
    def create_application(self, app_config: dict) -> str
    def get_application_status(self, app_id: str) -> dict
    def sync_application(self, app_id: str) -> dict
    def get_sync_events(self, app_id: str) -> list
    def validate_git_repository(self, repo_url: str, path: str) -> dict
```

**Monitoring Integration APIs**:
```python
# HNP expects these capabilities from monitoring tools
class MonitoringToolAPI:
    def authenticate(self, credentials: dict) -> bool
    def query_prometheus(self, query: str, time_range: str) -> dict
    def get_grafana_dashboard(self, dashboard_id: str) -> dict
    def create_alert_rule(self, rule_config: dict) -> str
    def get_alert_status(self, alert_id: str) -> dict
```

### Network Connectivity Requirements

**Network Access Patterns**:
- HNP → HEMK: HTTPS API calls (ports 443, custom ports)
- HNP → Git Repositories: HTTPS/SSH (ports 443, 22)
- HEMK → Git Repositories: HTTPS/SSH for GitOps synchronization
- HEMK → HCKC: Kubernetes API access (port 6443) for monitoring

**Security Requirements**:
- All communication encrypted (TLS 1.2+)
- Service account-based authentication preferred
- Token rotation and credential management
- Network policies for traffic isolation
- Firewall rules documentation for enterprise environments

### Configuration Management Integration

**HNP Configuration Storage**:
```python
# HNP stores these configurations for external tools
class ExternalToolConfiguration:
    tool_type: str          # 'argocd', 'flux', 'prometheus', 'grafana'
    endpoint_url: str       # HTTPS endpoint for API access
    authentication: dict    # Credentials, tokens, certificates
    capabilities: list      # Supported operations
    health_check_url: str   # Endpoint for availability checking
    fabric_associations: list  # Which fabrics use this tool
```

**HEMK Integration Points**:
- HEMK should provide standardized configuration outputs
- Configuration should be importable into HNP
- Health checking and availability monitoring
- Credential management and rotation support

---

## HNP Architecture Constraints

### Existing Architectural Decisions

**Database Integration**:
- HNP uses NetBox database (PostgreSQL)
- All configuration stored in NetBox data models
- Integration with NetBox RBAC and user management
- Plugin architecture constraints and capabilities

**UI Framework**:
- NetBox template system and design patterns
- Django-based backend with standard NetBox UI components
- JavaScript integration for dynamic functionality
- Progressive disclosure UI patterns implemented

**Security Model**:
- NetBox authentication and authorization
- Plugin security framework
- External API credential management
- Enterprise integration requirements (LDAP, SAML)

### Integration Constraints for HEMK

**What HEMK Must Accommodate**:
- HNP credential storage and management patterns
- HNP API integration expectations
- HNP user interface integration requirements
- HNP operational workflow patterns

**What HEMK Can Influence**:
- External tool deployment and configuration patterns
- Operational tooling selection and standardization
- Infrastructure automation and management approaches
- User experience for external infrastructure management

---

## Success Criteria for HEMK Integration

### Technical Integration Success
1. **Seamless Connectivity**: HNP can discover and connect to HEMK-deployed tools automatically
2. **Configuration Import**: HEMK can export configurations in HNP-compatible format
3. **Health Monitoring**: HNP can monitor HEMK-deployed component health and availability
4. **Credential Management**: Secure credential sharing between HNP and HEMK components
5. **API Compatibility**: All HNP-expected APIs available from HEMK-deployed components

### User Experience Success
1. **Simplified Setup**: HEMK deployment reduces complexity compared to manual setup
2. **Guided Configuration**: Users can easily configure HNP to use HEMK-deployed tools
3. **Operational Transparency**: Users understand the relationship between HNP and HEMK
4. **Troubleshooting Support**: Clear guidance when integration issues occur
5. **Choice Preservation**: Users can still choose manual deployment over HEMK

### Business Integration Success
1. **Adoption Enablement**: HEMK reduces barriers to HNP adoption
2. **Support Efficiency**: HEMK reduces support burden for external infrastructure issues
3. **Ecosystem Value**: HEMK enhances overall Hedgehog ecosystem value proposition
4. **Future Compatibility**: HEMK design supports future HNP enhancements
5. **Customer Satisfaction**: Positive feedback on simplified deployment experience

---

## HNP Documentation and Resources

### Key HNP Project Documents
**For deeper understanding of parent project**:
- `/project_management/CURRENT_STATUS.md` - Current project state and capabilities
- `/project_management/TASK_TRACKING.md` - Development progress and achievements
- `/gitignore/project_management/orchestrator_mvp2_status_update.md` - Executive status summary

**For technical integration details**:
- `/netbox_hedgehog/utils/kubernetes.py` - Kubernetes integration patterns
- `/netbox_hedgehog/utils/gitops_integration.py` - GitOps integration implementation
- `/netbox_hedgehog/models/gitops.py` - Data models for external tool integration
- `/netbox_hedgehog/views/gitops_onboarding_views.py` - User interface patterns

### HNP Contact Points
**For questions about integration requirements**:
- **Orchestrator**: Strategic guidance and project coordination
- **HNP Documentation**: Comprehensive technical documentation available in project directories
- **MVP2 Completion Reports**: Detailed implementation details in `/gitignore/project_status/`

---

**HEMK Project Manager Action Items**:
1. Review HNP current status documentation to understand integration context
2. Identify specific API and configuration requirements for HEMK components
3. Design HEMK architecture to support seamless HNP integration
4. Plan HEMK deployment patterns that enhance HNP user experience
5. Coordinate with orchestrator on any HNP integration design questions

**Integration Philosophy**: HEMK should enhance and simplify the HNP user experience while maintaining the flexibility for customers to choose their own external infrastructure deployment approaches.