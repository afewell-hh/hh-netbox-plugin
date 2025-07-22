# Real-Time Monitoring Agent Instructions

## Agent Role: Real-Time Systems Engineer
**Specialization**: WebSocket Integration, Kubernetes APIs, Live Monitoring  
**Project**: Hedgehog NetBox Plugin (HNP) Real-Time Architecture  
**Reporting To**: Lead Architect (Claude)  
**Priority Level**: HIGH - Enterprise User Experience

## Prerequisites & Foundation

### What the Previous Agent Completed
Before you start, the Architectural Cleanup Agent has provided you with:
- ✅ **Clean Architecture**: No circular dependencies, proper layered structure
- ✅ **Service Layer**: Business logic extracted into clean, injectable services
- ✅ **Event System**: Foundation for real-time event publishing and handling
- ✅ **Dependency Injection**: Ready for monitoring service integration
- ✅ **Testing Framework**: Architecture validation and stability testing

### System Context
You're building on a **stable, successful foundation**:
- Git directory sync works perfectly
- All 12 CR types have functional navigation
- Clean architectural patterns established
- System stability verified and tested

## Your Mission: Real-Time Enterprise Monitoring

### Primary Objectives
1. **Live Status Updates**: Real-time visibility into Hedgehog fabric state
2. **WebSocket Integration**: Bidirectional communication for dynamic UI
3. **Kubernetes Watch APIs**: Live monitoring of CRD state changes
4. **Performance Monitoring**: Real-time metrics for Git sync and operations
5. **Event-Driven Updates**: Immediate UI updates when data changes

### Impact
Your work transforms HNP from a static configuration tool into a **live, responsive infrastructure management platform** suitable for enterprise operations teams.

## Technical Architecture

### Real-Time Data Flow
```
Kubernetes Cluster
       ↓ (Watch APIs)
Event Processing Service
       ↓ (Event Bus)
WebSocket Service
       ↓ (WebSocket)
Frontend UI Components
       ↓ (User Actions)
Django Views/Services
       ↓ (Database + K8s APIs)
Live Updates Loop
```

### Key Components to Implement

#### 1. Kubernetes Watch Service
```python
# netbox_hedgehog/services/kubernetes_watch_service.py
class KubernetesWatchService:
    """Monitors live Kubernetes CRD changes"""
    
    async def watch_crd_changes(self, fabric: HedgehogFabric):
        """Watch for VPC and Wiring API CRD changes"""
        
    async def handle_crd_event(self, event_type: str, crd_data: dict):
        """Process CRD creation/update/deletion events"""
        
    def get_fabric_status(self, fabric_id: int) -> dict:
        """Get real-time fabric status"""
```

#### 2. WebSocket Integration
```python
# netbox_hedgehog/websockets/fabric_consumer.py
class FabricConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time fabric updates"""
    
    async def connect(self):
        """Handle WebSocket connections"""
        
    async def fabric_status_update(self, event):
        """Send live status updates to connected clients"""
        
    async def sync_progress_update(self, event):
        """Send Git sync progress updates"""
```

#### 3. Event Bus Architecture
```python
# netbox_hedgehog/services/event_service.py
class EventService:
    """Central event bus for real-time updates"""
    
    async def publish_fabric_event(self, fabric_id: int, event_data: dict):
        """Publish fabric-related events"""
        
    async def publish_cr_event(self, cr_type: str, cr_id: int, event_data: dict):
        """Publish CR-related events"""
        
    def subscribe_to_events(self, event_types: list, callback: callable):
        """Subscribe to specific event types"""
```

#### 4. Real-Time Monitoring Dashboard
```javascript
// Frontend: Real-time status components
class FabricMonitor {
    constructor(fabricId) {
        this.fabricId = fabricId;
        this.websocket = null;
        this.setupWebSocket();
    }
    
    setupWebSocket() {
        // WebSocket connection for live updates
    }
    
    updateFabricStatus(statusData) {
        // Update UI with real-time status
    }
    
    updateSyncProgress(progressData) {
        // Show live Git sync progress
    }
}
```

## Implementation Phases

### Week 1: Kubernetes Watch API Foundation
**Goal**: Live monitoring of CRD changes in Kubernetes clusters

**Tasks**:
- [ ] **Install Kubernetes Python client** and integrate with existing fabric connections
- [ ] **Implement CRD watch streams** for VPC and Wiring API resources
- [ ] **Create event processing pipeline** for handling CRD lifecycle events
- [ ] **Add database tracking** for live vs desired state comparison
- [ ] **Test with live Hedgehog environment** using real CRD changes

**Integration Points**:
- Extend existing `HedgehogFabric` model with watch configuration
- Use clean service layer from Architectural Cleanup Agent
- Integrate with existing Git sync functionality

### Week 2: WebSocket Infrastructure
**Goal**: Real-time bidirectional communication with frontend

**Tasks**:
- [ ] **Add Django Channels** for WebSocket support
- [ ] **Create WebSocket consumers** for different data types (fabrics, CRs, sync status)
- [ ] **Implement authentication** for WebSocket connections
- [ ] **Add connection management** (reconnection, heartbeat, error handling)
- [ ] **Create JavaScript client library** for easy WebSocket integration

**Technical Requirements**:
- Redis backend for channel layers (prepare for Performance Agent)
- Proper authentication and authorization
- Graceful degradation if WebSocket unavailable

### Week 3: Event-Driven Architecture
**Goal**: Seamless integration between Kubernetes events and UI updates

**Tasks**:
- [ ] **Design event schema** for different types of real-time events
- [ ] **Implement event routing** from Kubernetes to WebSocket clients
- [ ] **Add event filtering** (users only see relevant updates)
- [ ] **Create event persistence** for debugging and audit trails
- [ ] **Add rate limiting** to prevent UI flooding

**Event Types to Support**:
- CRD lifecycle events (create, update, delete, status changes)
- Git sync progress and completion
- Fabric connectivity status changes
- Validation errors and warnings

### Week 4: Live UI Components
**Goal**: Dynamic, responsive user interface with real-time updates

**Tasks**:
- [ ] **Create live status indicators** for fabrics and CRs
- [ ] **Implement real-time sync progress** with visual progress bars
- [ ] **Add live validation feedback** for configuration errors
- [ ] **Create notification system** for important events
- [ ] **Add real-time metrics dashboard** showing system health

**UI Components**:
- Live fabric status dashboard
- Real-time Git sync progress
- Dynamic CR status indicators
- Live notification system
- Real-time metrics and health indicators

## Technical Standards

### WebSocket Standards
- **Authentication**: JWT tokens for WebSocket connections
- **Message Format**: JSON with standardized event schema
- **Error Handling**: Graceful degradation and reconnection logic
- **Rate Limiting**: Prevent client flooding and DoS scenarios
- **Security**: Input validation and authorization for all messages

### Kubernetes Integration Standards
- **Client Management**: Proper connection pooling and resource cleanup
- **Watch Resilience**: Handle network interruptions and reconnection
- **Resource Filtering**: Only watch relevant CRDs to minimize overhead
- **Error Recovery**: Robust error handling for cluster connectivity issues
- **Performance**: Efficient event processing to minimize latency

### Event Schema Standards
```json
{
  "event_type": "fabric_status_change",
  "timestamp": "2025-07-22T15:30:00Z",
  "fabric_id": 123,
  "data": {
    "status": "connected",
    "details": "All CRDs synchronized successfully"
  },
  "metadata": {
    "source": "kubernetes_watch",
    "priority": "normal"
  }
}
```

## Integration with Existing Systems

### Git Sync Integration
- **Live progress updates** during Git sync operations
- **Real-time validation** of YAML files during sync
- **Immediate UI updates** when new CRs are imported
- **Error notification** for Git connectivity or parsing issues

### CR Management Integration
- **Live status updates** when CRs are created/modified via UI
- **Real-time validation feedback** for CR configurations
- **Immediate reflection** of Kubernetes state changes in UI
- **Live dependency tracking** when related CRs change

### Database Integration
- **Efficient queries** for real-time status information
- **Change tracking** to determine what updates to send
- **Connection pooling** for high-frequency status queries
- **Read replicas** preparation for Performance Agent

## Success Metrics

### Performance Targets
- **WebSocket latency**: <100ms for status updates
- **Event processing**: <1 second from Kubernetes event to UI update
- **Connection stability**: >99.9% uptime for WebSocket connections
- **Resource usage**: <5% CPU overhead for monitoring services
- **Scalability**: Support 100+ concurrent WebSocket connections

### User Experience Targets
- **Immediate feedback**: Users see changes within 1 second
- **Reliable updates**: No missed critical status changes
- **Graceful degradation**: System works even if real-time features fail
- **Intuitive indicators**: Clear visual feedback for all system states
- **Responsive interface**: No blocking operations in UI

### Technical Quality Gates
- [ ] All existing functionality continues to work
- [ ] Git sync performance maintained
- [ ] No memory leaks in long-running WebSocket connections
- [ ] Proper cleanup of Kubernetes watch connections
- [ ] Clean handoff preparation for Performance Agent

## Handoff to Performance Agent

### Prepare These Integration Points
- **Redis integration points** for caching and message queuing
- **Database query patterns** that need optimization
- **Background processing candidates** for heavy monitoring operations
- **WebSocket scaling concerns** for high connection counts
- **Metrics collection points** for performance monitoring

### Documentation Requirements
- **WebSocket API documentation** for frontend integration
- **Event schema documentation** for all event types
- **Kubernetes watch configuration** and troubleshooting guide
- **Performance baseline measurements** for the Performance Agent
- **Architecture diagrams** showing real-time data flow

## Emergency Protocols

### If Real-Time Features Fail
- **Graceful degradation**: UI continues to work with manual refresh
- **Error logging**: Comprehensive logs for debugging
- **Fallback modes**: Polling-based updates if WebSocket fails
- **User notification**: Clear indication when real-time features unavailable

### Critical Issues to Escalate
- WebSocket connection memory leaks
- Kubernetes watch API failures
- Event processing backlog building up
- Database performance impact from real-time queries

---

## Success Pattern

Study the recent Git sync implementation as your success pattern:
- **Clean service interfaces** that are easy to test and extend
- **Proper error handling** with user-friendly messages
- **Incremental implementation** with thorough testing at each step
- **Integration respect** for existing functionality

Your real-time monitoring layer will transform this from a static tool into a dynamic, responsive enterprise platform. The clean foundation provided by the Architectural Cleanup Agent makes this implementation straightforward and reliable.

**Build on success - make it shine in real-time!**