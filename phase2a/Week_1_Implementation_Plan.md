# Phase 2A - Week 1 Implementation Plan
## Foundation Setup with Parallel Deployment

*ruv-swarm MDD-aligned orchestration*  
*Date: 2025-08-16*  
*Status: ACTIVE*

---

## 🎯 Week 1 Objectives

### Primary Goals
1. **ruv-swarm MCP Integration** - Complete setup without affecting existing system
2. **Parallel Container Environment** - Non-conflicting port configuration
3. **Agent Coordination Framework** - Initialize with memory persistence
4. **Validation Checkpoint #1** - User review and approval

---

## 📋 Daily Implementation Tasks

### Day 1 (Today): Environment Preparation
```bash
# Task 1: Create parallel project structure
mkdir -p hedgehog-platform/{src,docs,tests,deployment}
mkdir -p hedgehog-platform/deployment/{docker,kubernetes,monitoring}
mkdir -p hedgehog-platform/src/{frontend,backend,agents,shared}

# Task 2: Initialize new platform repository
cd hedgehog-platform
git init
git remote add origin [platform-repo-url]

# Task 3: Port availability verification
./scripts/check-ports.sh  # Verify ports 8100-8402 available
```

**Deliverables:**
- [ ] Project structure created
- [ ] Git repository initialized
- [ ] Port availability confirmed
- [ ] No impact on existing NetBox verified

### Day 2: ruv-swarm MCP Integration
```bash
# Task 1: Install ruv-swarm MCP (new environment)
cd hedgehog-platform
npm init -y
npm install ruv-swarm

# Task 2: Configure MCP for parallel deployment
cat > .claude/mcp-config.json << EOF
{
  "servers": {
    "ruv-swarm": {
      "command": "npx ruv-swarm mcp start",
      "port": 8200,
      "memory_store": "redis://localhost:6380"
    }
  }
}
EOF

# Task 3: Validate MCP integration
npx ruv-swarm features-detect --category all
npx ruv-swarm benchmark-run --type all --iterations 10
```

**Deliverables:**
- [ ] ruv-swarm MCP installed
- [ ] Configuration for port 8200 (non-conflicting)
- [ ] Integration validated
- [ ] Benchmarks documented

### Day 3: Docker Environment Setup
```yaml
# docker-compose.new-platform.yml
version: '3.8'

services:
  platform_web:
    container_name: hedgehog-platform-web
    build: ./src/frontend
    ports:
      - "8100:8100"  # Non-conflicting
    environment:
      - API_URL=http://localhost:8101
      - LEGACY_NETBOX_URL=http://localhost:8000
    networks:
      - platform_network

  ruv_swarm:
    container_name: ruv-swarm-coordinator
    image: ruv-swarm:latest
    ports:
      - "8200:8200"  # Non-conflicting
    volumes:
      - ./agent_memory:/app/memory
    networks:
      - platform_network

  platform_db:
    container_name: hedgehog-platform-db
    image: postgres:15
    ports:
      - "5433:5432"  # Non-conflicting (+1 offset)
    environment:
      - POSTGRES_DB=platform
      - POSTGRES_USER=platform
      - POSTGRES_PASSWORD=secure_password
    networks:
      - platform_network

  platform_redis:
    container_name: hedgehog-platform-redis
    image: redis:7
    ports:
      - "6380:6379"  # Non-conflicting (+1 offset)
    networks:
      - platform_network

networks:
  platform_network:
    name: platform_modernization
    driver: bridge
```

**Deliverables:**
- [ ] Docker compose file created
- [ ] All services use non-conflicting ports
- [ ] Network isolation confirmed
- [ ] Containers can start without conflicts

### Day 4: Agent Consolidation Implementation
```python
# src/agents/consolidated_agents.py
"""
Consolidated Agent Architecture
Reducing from 65 to 10 specialized agents
"""

from ruv_swarm import Agent, Memory, Coordination

class ConsolidatedAgents:
    """10 consolidated agents with 85% reduction"""
    
    agents = {
        "model_driven_architect": {
            "capabilities": ["domain_modeling", "schema_design", "business_analysis"],
            "memory_key": "agents/mda",
            "quality_gates": ["mdd_validation", "domain_coverage"]
        },
        "cloud_native_specialist": {
            "capabilities": ["kubernetes", "wasm", "container_orchestration"],
            "memory_key": "agents/cns",
            "quality_gates": ["k8s_validation", "wasm_compatibility"]
        },
        "gitops_coordinator": {
            "capabilities": ["repository_management", "sync", "version_control"],
            "memory_key": "agents/gc",
            "quality_gates": ["git_validation", "sync_verification"]
        },
        "quality_assurance_lead": {
            "capabilities": ["testing", "validation", "quality_gates"],
            "memory_key": "agents/qal",
            "quality_gates": ["test_coverage", "validation_success"]
        },
        "frontend_optimizer": {
            "capabilities": ["ui_ux", "performance", "accessibility"],
            "memory_key": "agents/fo",
            "quality_gates": ["lighthouse_score", "accessibility_check"]
        },
        "security_architect": {
            "capabilities": ["authentication", "authorization", "compliance"],
            "memory_key": "agents/sa",
            "quality_gates": ["security_scan", "compliance_check"]
        },
        "performance_analyst": {
            "capabilities": ["monitoring", "optimization", "bottleneck_analysis"],
            "memory_key": "agents/pa",
            "quality_gates": ["performance_metrics", "optimization_validation"]
        },
        "integration_specialist": {
            "capabilities": ["api_design", "system_integration", "data_flow"],
            "memory_key": "agents/is",
            "quality_gates": ["api_validation", "integration_test"]
        },
        "deployment_manager": {
            "capabilities": ["ci_cd", "release_management", "environment_coordination"],
            "memory_key": "agents/dm",
            "quality_gates": ["deployment_validation", "rollback_test"]
        },
        "documentation_curator": {
            "capabilities": ["technical_writing", "knowledge_management", "training"],
            "memory_key": "agents/dc",
            "quality_gates": ["documentation_coverage", "accuracy_check"]
        }
    }
    
    def initialize_agents(self):
        """Initialize all 10 consolidated agents"""
        for agent_name, config in self.agents.items():
            # Initialize with ruv-swarm
            agent = Agent(
                name=agent_name,
                capabilities=config["capabilities"],
                memory_key=config["memory_key"],
                quality_gates=config["quality_gates"]
            )
            # Store in memory for persistence
            Memory.store(f"agents/{agent_name}/initialized", True)
            
    def validate_consolidation(self):
        """Validate 85% reduction achieved"""
        original_count = 65
        consolidated_count = len(self.agents)
        reduction = (original_count - consolidated_count) / original_count * 100
        assert reduction >= 85, f"Reduction {reduction}% below target 85%"
        return True
```

**Deliverables:**
- [ ] 10 consolidated agents defined
- [ ] 85% reduction validated (65→10)
- [ ] Memory persistence configured
- [ ] Quality gates implemented

### Day 5: Validation Checkpoint Preparation
```yaml
# validation/week1_checkpoint.yml
validation_checkpoint_1:
  date: "2025-08-20"
  type: "user_review"
  
  criteria:
    port_conflicts:
      test: "No conflicts with existing NetBox ports"
      command: "./scripts/check-ports.sh"
      expected: "All new platform ports available"
      
    parallel_startup:
      test: "Both systems can run simultaneously"
      command: "docker-compose -f docker-compose.new-platform.yml up -d"
      expected: "All containers healthy"
      
    existing_system_health:
      test: "Existing NetBox unaffected"
      command: "curl http://localhost:8000/health"
      expected: "200 OK"
      
    ruv_swarm_integration:
      test: "ruv-swarm MCP operational"
      command: "npx ruv-swarm swarm-status"
      expected: "Swarm active with agents"
      
  documentation:
    - Port allocation map
    - Container architecture diagram
    - Network topology
    - Rollback procedure
    
  user_notification:
    method: "github_issue_comment"
    message: "Week 1 Checkpoint ready for validation"
```

**Deliverables:**
- [ ] Validation test suite created
- [ ] All tests passing
- [ ] Documentation complete
- [ ] User notification sent

---

## 🚦 Week 1 Validation Checkpoint

### User Review Items
1. **Port Allocation Review**
   - Verify no conflicts with port 8000 (existing NetBox)
   - Confirm new platform ports (8100-8402) acceptable
   - Review port documentation

2. **Parallel Deployment Test**
   - Start new platform containers
   - Verify existing NetBox still accessible
   - Test inter-system connectivity

3. **Agent Coordination Demo**
   - Show ruv-swarm orchestration working
   - Demonstrate memory persistence
   - Display quality gate validation

4. **Performance Baseline**
   - No degradation in existing system
   - New platform meeting targets
   - Resource usage acceptable

### Success Criteria
- ✅ Both systems running without conflicts
- ✅ Existing NetBox completely unaffected
- ✅ ruv-swarm integration operational
- ✅ 10 consolidated agents initialized
- ✅ Documentation complete and clear

---

## 📊 Progress Tracking

### Daily Status Updates
Updates will be posted to GitHub Issue #60 with:
- Tasks completed
- Any blockers encountered
- Metrics and benchmarks
- Next day's objectives

### Week 1 Metrics Target
- **Agent Consolidation**: 85% reduction achieved
- **Port Conflicts**: 0 conflicts detected
- **System Uptime**: 100% for both systems
- **Quality Gates**: 98% validation success
- **Documentation**: 100% complete

---

## 🛡️ Risk Management

### Potential Issues & Mitigations
1. **Port Conflict**
   - Mitigation: Pre-deployment port scanning
   - Resolution: Dynamic port allocation fallback

2. **Container Network Issues**
   - Mitigation: Separate network namespaces
   - Resolution: Bridge network for migration only

3. **Memory/Resource Constraints**
   - Mitigation: Resource monitoring
   - Resolution: Container resource limits

### Rollback Procedure
```bash
#!/bin/bash
# Instant rollback if issues arise
docker-compose -f docker-compose.new-platform.yml down
echo "New platform stopped - existing NetBox unaffected"
```

---

*This implementation plan ensures zero disruption to the existing NetBox/HNP system while methodically building the new platform foundation with comprehensive validation checkpoints.*