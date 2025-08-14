# .claude Directory Preservation Recommendations

## Critical Priority: Must Preserve

### 1. Core Configuration Files
**Files**: `config.json`, `settings.json`, `settings.local.json`
**Reason**: Contains ruv-swarm specific environment variables and MCP server configurations that enable advanced features.
**Risk**: System will not function without these configurations.

### 2. High-Priority Agents (Queen Agents)
**Files**:
- `agents/swarm/hierarchical-coordinator.md` - Central command coordination
- `agents/consensus/byzantine-coordinator.md` - Fault-tolerant consensus
- `agents/hive-mind/collective-intelligence-coordinator.md` - Hive mind operations
- `agents/hive-mind/swarm-memory-manager.md` - Cross-session persistence
- `agents/templates/sparc-coordinator.md` - SPARC methodology orchestration

**Reason**: These agents provide the core swarm intelligence and coordination capabilities that distinguish ruv-swarm from basic multi-agent systems.
**Risk**: Loss of advanced coordination, consensus, and memory persistence features.

### 3. ruv-swarm Environment Variables
**Settings**: All `RUV_SWARM_*` environment variables in settings.json
```json
"RUV_SWARM_AUTO_COMMIT": "false",
"RUV_SWARM_AUTO_PUSH": "false", 
"RUV_SWARM_HOOKS_ENABLED": "false",
"RUV_SWARM_TELEMETRY_ENABLED": "true",
"RUV_SWARM_REMOTE_EXECUTION": "true"
```
**Reason**: Control ruv-swarm specific optimizations and behaviors.
**Risk**: Performance degradation and feature loss.

### 4. MCP Server Configuration
**Section**: `mcpServers.ruv-swarm` in settings.json
**Reason**: Enables the ruv-swarm MCP server integration that provides advanced tool access.
**Risk**: Loss of timeout-free execution and advanced MCP functionality.

## High Priority: Strongly Recommended

### 5. Consensus Protocol Agents (7 files)
**Files**: All files in `agents/consensus/`
- `byzantine-coordinator.md`
- `raft-manager.md`
- `crdt-synchronizer.md`
- `gossip-coordinator.md`
- `quorum-manager.md`
- `security-manager.md`
- `performance-benchmarker.md`

**Reason**: Provide enterprise-grade distributed coordination and fault tolerance.
**Risk**: Limited scalability and reliability in complex multi-agent scenarios.

### 6. Hook Integration Patterns
**Files**: All 54 agent files with hook sections
**Pattern**:
```yaml
hooks:
  pre: |
    echo "🔍 Agent starting: $TASK"
    memory_store "context_$(date +%s)" "$TASK"
  post: |
    echo "✅ Agent complete"
```
**Reason**: Enable automated execution workflows and memory persistence.
**Risk**: Manual coordination overhead and loss of automation.

### 7. Memory Management Commands
**Files**: All files in `commands/memory/` and `commands/automation/session-memory.md`
**Reason**: Cross-session persistence and learning capabilities.
**Risk**: Loss of contextual awareness and learning between sessions.

### 8. GitHub Swarm Agents (13 files)
**Files**: All files in `agents/github/`
**Reason**: Advanced GitHub integration with multi-repo coordination.
**Risk**: Limited GitHub automation and coordination capabilities.

## Medium Priority: Important for Optimization

### 9. SPARC Methodology Integration
**Files**: 
- All files in `agents/sparc/`
- All files in `commands/sparc/`
- `commands/sparc.md`

**Reason**: Systematic development methodology with TDD integration.
**Risk**: Less structured development workflow.

### 10. Performance Monitoring Commands
**Files**: All files in `commands/monitoring/` and `commands/analysis/`
**Reason**: Real-time performance tracking and bottleneck detection.
**Risk**: Reduced visibility into system performance.

### 11. Automation Helpers
**Files**: All 7 files in `helpers/`
- `quick-start.sh`
- `setup-mcp.sh` 
- `task-classifier.py`
- `checkpoint-manager.sh`
- `github-setup.sh`
- `github-safe.js`
- `standard-checkpoint-hooks.sh`

**Reason**: Automated setup and integration workflows.
**Risk**: Manual setup overhead and configuration errors.

## Low Priority: Nice to Have

### 12. Specialized Domain Agents
**Files**: 
- `agents/specialized/mobile/`
- `agents/development/backend/`
- `agents/devops/ci-cd/`
- `agents/documentation/api-docs/`
- `agents/data/ml/`

**Reason**: Domain-specific optimization patterns.
**Risk**: Less optimized performance for specific use cases.

### 13. Template Agents
**Files**: All files in `agents/templates/`
**Reason**: Rapid agent spawning patterns.
**Risk**: Slower agent initialization.

## Preservation Strategy

### Phase 1: Critical Core (Must Do)
1. **Backup all configuration files** - Zero tolerance for loss
2. **Preserve Queen agents** - Core coordination capabilities
3. **Maintain ruv-swarm environment variables** - Performance optimizations
4. **Keep MCP server configuration** - Advanced tool access

### Phase 2: Advanced Features (Strongly Recommended)
1. **Preserve consensus protocols** - Enterprise coordination
2. **Maintain hook patterns** - Automation workflows
3. **Keep memory management** - Cross-session persistence
4. **Preserve GitHub integration** - Repository coordination

### Phase 3: Optimization (Important)
1. **Retain SPARC methodology** - Structured development
2. **Keep performance monitoring** - System visibility
3. **Maintain automation helpers** - Setup efficiency

### Phase 4: Specialization (Optional)
1. **Domain-specific agents** - Use case optimization
2. **Template patterns** - Rapid spawning

## Migration Approach

### Safe Migration Pattern
1. **Full backup** of entire `.claude` directory
2. **Incremental testing** of each component
3. **Rollback capability** if issues arise
4. **Performance monitoring** during migration
5. **Validation testing** of critical features

### Risk Mitigation
1. **Document dependencies** between components
2. **Test coordination features** thoroughly
3. **Validate memory persistence** across sessions
4. **Verify MCP integration** functionality
5. **Confirm hook execution** works correctly

## Success Metrics

### Functional Metrics
- [ ] Swarm coordination works correctly
- [ ] Memory persistence across sessions
- [ ] Hook automation executes properly
- [ ] MCP tools remain accessible
- [ ] GitHub integration functions
- [ ] Consensus protocols operate

### Performance Metrics
- [ ] Agent spawning speed maintained
- [ ] Memory usage optimized
- [ ] Token efficiency preserved
- [ ] Parallel execution capability
- [ ] Load balancing effectiveness

## Warning Signs

### Critical Issues (Immediate Action Required)
- Swarm coordination failures
- Memory persistence loss
- MCP server connection issues
- Hook execution errors
- Environment variable conflicts

### Performance Degradation (Investigation Needed)
- Slower agent spawning
- Increased memory usage
- Token inefficiency
- Reduced parallelization
- Load balancing problems

This preservation strategy ensures the advanced ruv-swarm optimizations and claude-flow integrations are maintained while allowing for safe migration and testing.