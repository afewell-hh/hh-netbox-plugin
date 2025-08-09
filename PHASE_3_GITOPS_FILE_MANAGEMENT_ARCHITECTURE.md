# Phase 3: GitOps File Management System Architecture
**Comprehensive Technical Design for Issue #16 Integration**

## Executive Summary

This document presents the comprehensive architecture for Phase 3, integrating advanced GitOps file management capabilities with Issue #16 redundant YAML conflict resolution. The design leverages the existing proven infrastructure while introducing four specialized sub-agents for optimal orchestration.

## Project Context & Objectives

### Current Foundation
- **Phases 0-2 Complete**: Full SPARC methodology infrastructure with GUI testing suite and backend integration
- **Existing Infrastructure**: `GitOpsIngestionService`, Celery task system, Django models, event service
- **Proven Architecture**: Sub-agent orchestration with <30 seconds per task execution
- **Production Target**: Professional-grade GitOps management comparable to GitLab/GitHub

### Enhanced Scope for Phase 3
1. **Core GitOps File Management System** with intelligent synchronization
2. **Issue #16 Redundant YAML Resolution** with CEO-specified hierarchy
3. **Sub-Agent Orchestration** continuing proven micro-task architecture
4. **Seamless FGD Integration** leveraging existing sync processes

## Technical Architecture Overview

### System Components Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    Phase 3 GitOps File Management               │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  File Operations │  │ Conflict Engine │  │ Template Engine │  │
│  │     Sub-Agent   │  │   Sub-Agent     │  │   Sub-Agent     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                                 │
│  ┌─────────────────┐                      ┌─────────────────┐  │
│  │ Integration     │                      │ UI Management   │  │
│  │  Sub-Agent      │                      │   Sub-Agent     │  │
│  └─────────────────┘                      └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                   Issue #16 Integration                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────┐  ┌───────────────────────────────┐  │
│  │ Intelligent Duplicate │  │  CEO-Specified Hierarchy      │  │
│  │     Detection         │  │     Resolution Engine         │  │
│  └───────────────────────┘  └───────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                   Existing Infrastructure                       │
├─────────────────────────────────────────────────────────────────┤
│ GitOpsIngestionService │ Celery Tasks │ Django Models │ Events │
└─────────────────────────────────────────────────────────────────┘
```

## Sub-Agent Architecture Design

### 1. File Operations Sub-Agent

**Responsibility**: Enhanced Git file operations with smart synchronization

**Core Capabilities**:
- **Advanced Git Integration**: Seamless push/pull operations with conflict detection
- **Smart File Monitoring**: Real-time file system watching with change detection
- **Batch Operations**: Efficient handling of multiple file operations
- **Branch Management**: Automated feature branch creation and management

**Technical Implementation**:
```python
# File: netbox_hedgehog/agents/file_operations_agent.py
class FileOperationsAgent:
    """Handles advanced Git file operations with conflict detection"""
    
    def execute_smart_sync(self, fabric_id: int) -> Dict:
        """Execute intelligent synchronization with conflict detection"""
        
    def monitor_file_changes(self, directory_path: str) -> FileChangeEvent:
        """Monitor directory for file changes with debouncing"""
        
    def create_feature_branch(self, branch_name: str) -> BranchResult:
        """Create feature branch for isolated changes"""
```

**Key Files Modified**:
- `/netbox_hedgehog/agents/file_operations_agent.py` (new)
- `/netbox_hedgehog/services/gitops_ingestion_service.py` (enhanced)
- `/netbox_hedgehog/tasks/git_sync_tasks.py` (extended)

### 2. Conflict Engine Sub-Agent

**Responsibility**: Issue #16 redundant YAML conflict resolution with intelligent detection

**Core Capabilities**:
- **Duplicate Detection**: Advanced YAML parsing and semantic comparison
- **Hierarchy Resolution**: CEO-specified conflict resolution strategies
- **Automated Actions**: Comment/move/archive operations based on policies
- **Integrity Validation**: Post-resolution validation and rollback capability

**Technical Implementation**:
```python
# File: netbox_hedgehog/agents/conflict_resolution_agent.py
class ConflictResolutionAgent:
    """Handles Issue #16 redundant YAML resolution"""
    
    def detect_redundant_yamls(self, fgd_path: str) -> List[DuplicateGroup]:
        """Detect duplicate/redundant YAML files across FGD"""
        
    def apply_ceo_hierarchy(self, duplicates: List[DuplicateGroup]) -> ResolutionPlan:
        """Apply CEO-specified resolution hierarchy"""
        
    def execute_file_operations(self, plan: ResolutionPlan) -> ResolutionResult:
        """Execute comment/move/archive operations"""
```

**Key Files Modified**:
- `/netbox_hedgehog/agents/conflict_resolution_agent.py` (new)
- `/netbox_hedgehog/utils/conflict_resolution.py` (enhanced)
- `/netbox_hedgehog/models/gitops.py` (extended)

### 3. Template Engine Sub-Agent

**Responsibility**: Advanced configuration management with template processing

**Core Capabilities**:
- **Template Processing**: Jinja2-based YAML template rendering
- **Configuration Validation**: Schema validation and consistency checking
- **Dynamic Generation**: Runtime template generation based on fabric state
- **Version Management**: Template versioning and rollback capabilities

**Technical Implementation**:
```python
# File: netbox_hedgehog/agents/template_engine_agent.py
class TemplateEngineAgent:
    """Handles template processing and configuration management"""
    
    def process_templates(self, template_dir: str, context: Dict) -> ProcessResult:
        """Process templates with fabric context"""
        
    def validate_configuration(self, config_files: List[str]) -> ValidationResult:
        """Validate configuration consistency"""
        
    def generate_dynamic_configs(self, fabric: HedgehogFabric) -> List[ConfigFile]:
        """Generate dynamic configurations based on fabric state"""
```

**Key Files Modified**:
- `/netbox_hedgehog/agents/template_engine_agent.py` (new)
- `/netbox_hedgehog/templates/gitops/` (new directory)
- `/netbox_hedgehog/utils/template_processor.py` (new)

### 4. Integration Sub-Agent

**Responsibility**: Seamless integration with existing FGD sync processes

**Core Capabilities**:
- **FGD Integration**: Seamless integration with existing sync workflows
- **Event Coordination**: Event-driven coordination with existing services
- **Status Synchronization**: Real-time status updates across all components
- **Rollback Management**: Automated rollback on integration failures

**Technical Implementation**:
```python
# File: netbox_hedgehog/agents/integration_agent.py
class IntegrationAgent:
    """Handles integration with existing FGD sync processes"""
    
    def coordinate_fgd_sync(self, fabric_id: int) -> SyncResult:
        """Coordinate with existing FGD sync processes"""
        
    def publish_events(self, event_type: str, payload: Dict) -> None:
        """Publish events to existing event service"""
        
    def synchronize_status(self, components: List[str]) -> StatusSyncResult:
        """Synchronize status across all components"""
```

**Key Files Modified**:
- `/netbox_hedgehog/agents/integration_agent.py` (new)
- `/netbox_hedgehog/services/integration_coordinator.py` (enhanced)
- `/netbox_hedgehog/models/fabric.py` (extended)

## Issue #16 Redundant YAML Resolution

### Duplicate Detection Algorithm

```python
class YAMLDuplicateDetector:
    """Advanced duplicate detection for YAML files"""
    
    def detect_duplicates(self, fgd_directory: str) -> List[DuplicateGroup]:
        """
        Multi-phase duplicate detection:
        1. Content Hash Analysis - Identical file contents
        2. Semantic Comparison - YAML structure and values
        3. Resource Identity - Kubernetes resource identity matching
        4. Hierarchy Analysis - Directory-based priority resolution
        """
        
    def semantic_compare(self, yaml1: Dict, yaml2: Dict) -> ComparisonResult:
        """Compare YAML files semantically ignoring order and formatting"""
        
    def calculate_priority(self, file_path: str) -> int:
        """Calculate file priority based on CEO-specified hierarchy"""
```

### CEO-Specified Hierarchy Implementation

```python
class ResolutionHierarchy:
    """Implements CEO-specified conflict resolution hierarchy"""
    
    HIERARCHY_RULES = {
        'directory_priority': [
            '/production/',     # Highest priority
            '/environments/',   
            '/templates/',
            '/examples/',      # Lowest priority
        ],
        'file_name_priority': [
            'main.yaml',       # Highest priority
            'default.yaml',
            'template.yaml',
            'example.yaml'     # Lowest priority
        ],
        'metadata_priority': [
            'created_by=admin',
            'environment=production',
            'managed=true'
        ]
    }
```

### Automated File Operations

```python
class FileOperationExecutor:
    """Execute automated file operations based on resolution decisions"""
    
    def comment_file(self, file_path: str, reason: str) -> None:
        """Add comment header explaining why file is being managed"""
        
    def move_to_archive(self, file_path: str, archive_dir: str) -> str:
        """Move file to archive directory with metadata preservation"""
        
    def create_backup(self, file_path: str) -> str:
        """Create timestamped backup before any operations"""
```

## Data Flow Architecture

### File Processing Pipeline

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   File Change   │───▶│   File Ops      │───▶│   Duplicate     │
│   Detection     │    │   Sub-Agent     │    │   Detection     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
┌─────────────────┐    ┌─────────────────┐    ┌───────▼─────────┐
│  Template       │◀───│   Integration   │◀───│  Conflict       │
│  Processing     │    │   Sub-Agent     │    │  Resolution     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Event-Driven Coordination

```python
class EventCoordinator:
    """Coordinates events between sub-agents"""
    
    EVENT_FLOWS = {
        'file_changed': ['file_ops', 'conflict_engine'],
        'duplicate_detected': ['conflict_engine', 'integration'],
        'template_updated': ['template_engine', 'file_ops'],
        'resolution_complete': ['integration', 'ui_management']
    }
```

## API Design Specifications

### RESTful API Endpoints

```python
# File: netbox_hedgehog/api/gitops_file_management.py

class GitOpsFileManagementViewSet(ViewSet):
    """API endpoints for GitOps file management"""
    
    @action(detail=True, methods=['post'])
    def process_duplicates(self, request, pk=None):
        """Process duplicate YAML files for a fabric"""
        
    @action(detail=True, methods=['get'])
    def duplicate_status(self, request, pk=None):
        """Get status of duplicate processing"""
        
    @action(detail=True, methods=['post'])
    def resolve_conflicts(self, request, pk=None):
        """Manually resolve detected conflicts"""
```

### WebSocket Integration

```python
# File: netbox_hedgehog/websockets/gitops_consumer.py

class GitOpsFileManagementConsumer(AsyncWebsocketConsumer):
    """Real-time updates for file management operations"""
    
    async def send_duplicate_detection_update(self, event):
        """Send duplicate detection progress updates"""
        
    async def send_resolution_progress(self, event):
        """Send conflict resolution progress"""
```

## Database Schema Extensions

### New Models for Phase 3

```python
# File: netbox_hedgehog/models/gitops_file_management.py

class YAMLDuplicateGroup(models.Model):
    """Group of duplicate YAML files detected in FGD"""
    fabric = models.ForeignKey(HedgehogFabric, on_delete=models.CASCADE)
    detection_timestamp = models.DateTimeField(auto_now_add=True)
    resolution_status = models.CharField(max_length=20, choices=RESOLUTION_STATUS_CHOICES)
    resolution_strategy = models.CharField(max_length=30, choices=RESOLUTION_STRATEGY_CHOICES)
    
class YAMLDuplicateFile(models.Model):
    """Individual file within a duplicate group"""
    duplicate_group = models.ForeignKey(YAMLDuplicateGroup, on_delete=models.CASCADE)
    file_path = models.CharField(max_length=1000)
    file_hash = models.CharField(max_length=64)
    priority_score = models.IntegerField()
    resolution_action = models.CharField(max_length=20, choices=ACTION_CHOICES)
```

### Enhanced Existing Models

```python
# Extensions to existing models
class HedgehogFabric:
    # New fields for Phase 3
    duplicate_detection_enabled = models.BooleanField(default=True)
    resolution_hierarchy_config = models.JSONField(default=dict)
    last_duplicate_scan = models.DateTimeField(null=True, blank=True)
    duplicate_scan_interval = models.PositiveIntegerField(default=3600)  # 1 hour
```

## Implementation Roadmap

### Phase 3.1: Foundation (Week 1)
1. **File Operations Sub-Agent Setup**
   - Create base agent infrastructure
   - Implement enhanced Git operations
   - Add file monitoring capabilities

2. **Conflict Engine Sub-Agent Foundation**
   - Implement basic duplicate detection
   - Create semantic YAML comparison
   - Set up hierarchy resolution framework

### Phase 3.2: Core Features (Week 2)
3. **Template Engine Sub-Agent**
   - Implement Jinja2 template processing
   - Add configuration validation
   - Create dynamic template generation

4. **Integration Sub-Agent**
   - FGD sync integration
   - Event coordination setup
   - Status synchronization

### Phase 3.3: Issue #16 Implementation (Week 3)
5. **Advanced Duplicate Resolution**
   - CEO hierarchy implementation
   - Automated file operations
   - Post-resolution validation

6. **UI Integration**
   - Visual diff browser
   - Conflict resolution interface
   - Real-time progress updates

### Phase 3.4: Testing & Optimization (Week 4)
7. **Comprehensive Testing**
   - Unit tests for all sub-agents
   - Integration testing with existing FGD
   - Performance optimization

8. **Production Readiness**
   - Error handling enhancement
   - Monitoring and alerting
   - Documentation completion

## Success Metrics & Validation

### Technical Metrics
- **Sub-Agent Performance**: Each sub-agent task completes in <30 seconds
- **Duplicate Detection Accuracy**: >95% accuracy in semantic duplicate detection
- **Resolution Success Rate**: >90% of conflicts resolved automatically
- **FGD Integration**: Zero disruption to existing sync processes

### Functional Metrics  
- **File Management**: Complete YAML file lifecycle management
- **Conflict Resolution**: Automated resolution of Issue #16 redundant files
- **Template Processing**: Dynamic configuration generation
- **User Experience**: Visual diff and conflict resolution UI

### Production Readiness Metrics
- **Reliability**: 99.9% uptime for file management operations
- **Performance**: <5 second response time for duplicate detection
- **Scalability**: Support for 1000+ YAML files per fabric
- **Maintainability**: Comprehensive documentation and test coverage

## Risk Mitigation Strategies

### Technical Risks
1. **FGD Integration Conflicts**
   - Mitigation: Comprehensive integration testing with existing services
   - Rollback: Immediate rollback capability for all file operations

2. **Performance Impact**
   - Mitigation: Asynchronous processing and intelligent batching
   - Monitoring: Real-time performance metrics and alerting

3. **Data Loss Prevention**
   - Mitigation: Atomic operations with backup creation
   - Validation: Post-operation integrity checks

### Operational Risks
1. **CEO Hierarchy Changes**
   - Mitigation: Configurable hierarchy rules with versioning
   - Flexibility: Easy rule updates without code changes

2. **Scale Challenges**
   - Mitigation: Horizontal scaling architecture
   - Optimization: Intelligent file scanning and caching

## Conclusion

Phase 3 represents a comprehensive enhancement to the existing GitOps infrastructure, seamlessly integrating advanced file management capabilities with Issue #16 redundant YAML resolution. The sub-agent architecture ensures optimal performance while maintaining the proven <30 second task execution pattern.

The design leverages existing infrastructure investments while adding professional-grade capabilities comparable to GitLab/GitHub. With careful attention to FGD integration and CEO-specified hierarchy implementation, this architecture provides a solid foundation for production-grade GitOps file management.

The four specialized sub-agents work in harmony to deliver:
- **Advanced Git file operations** with conflict detection
- **Intelligent duplicate YAML resolution** addressing Issue #16 directly
- **Dynamic template processing** for configuration management
- **Seamless integration** with existing FGD sync processes

This architecture ensures Phase 3 delivers on its promise of professional GitOps file management while maintaining the high-performance standards established in previous phases.