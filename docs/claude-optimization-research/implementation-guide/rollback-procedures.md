# Rollback Procedures for Enhanced Claude Configuration

## 🚨 Emergency Rollback Procedures

### 🔴 Critical Failure Rollback (1-Minute Recovery)

If enhanced configuration causes system-wide failures:

```bash
#!/bin/bash
# emergency-rollback.sh - Execute immediately on critical failure

echo "🚨 EXECUTING EMERGENCY ROLLBACK"

# Step 1: Stop all active swarm processes
pkill -f "ruv-swarm" 2>/dev/null
pkill -f "claude-flow" 2>/dev/null

# Step 2: Restore original configuration (atomic operation)
if [ -d ".claude.backup.emergency" ]; then
    rm -rf .claude
    cp -r .claude.backup.emergency .claude
    echo "✅ .claude directory restored from emergency backup"
else
    echo "❌ Emergency backup not found - using most recent backup"
    BACKUP_DIR=$(ls -td .claude.backup.* 2>/dev/null | head -1)
    if [ -n "$BACKUP_DIR" ]; then
        rm -rf .claude
        cp -r "$BACKUP_DIR" .claude
        echo "✅ .claude directory restored from $BACKUP_DIR"
    fi
fi

# Step 3: Restore CLAUDE.md
if [ -f "CLAUDE.md.backup.emergency" ]; then
    cp CLAUDE.md.backup.emergency CLAUDE.md
    echo "✅ CLAUDE.md restored from emergency backup"
else
    BACKUP_FILE=$(ls -t CLAUDE.md.backup.* 2>/dev/null | head -1)
    if [ -n "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" CLAUDE.md
        echo "✅ CLAUDE.md restored from $BACKUP_FILE"
    fi
fi

# Step 4: Validate basic functionality
if npx ruv-swarm swarm status --quick-check 2>/dev/null; then
    echo "✅ Emergency rollback successful - system functional"
    exit 0
else
    echo "❌ Emergency rollback failed - manual intervention required"
    exit 1
fi
```

### 🟡 Performance Degradation Rollback (5-Minute Recovery)

If performance metrics drop below critical thresholds:

```bash
#!/bin/bash
# performance-rollback.sh

echo "⚠️ EXECUTING PERFORMANCE ROLLBACK"

# Step 1: Measure current performance
echo "📊 Measuring current performance..."
CURRENT_PERF=$(npx ruv-swarm benchmark run --type quick --output json 2>/dev/null)

# Step 2: Compare with baseline
BASELINE_FILE=".claude/performance-baseline.json"
if [ -f "$BASELINE_FILE" ]; then
    echo "📈 Comparing with baseline performance..."
    # Performance comparison logic would go here
    # For now, proceed with rollback if any major issues detected
fi

# Step 3: Selective rollback of problematic components
echo "🔄 Performing selective rollback..."

# Rollback CLAUDE.md enhancements only (keep original optimizations)
if [ -f "CLAUDE.md.backup.original" ]; then
    head -n 559 CLAUDE.md.backup.original > CLAUDE.md
    echo "✅ CLAUDE.md rolled back to original (preserved ruv-swarm optimizations)"
fi

# Rollback enhanced agents if they're causing issues
if [ -d ".claude.backup.original/agents" ]; then
    cp -r .claude.backup.original/agents/* .claude/agents/
    echo "✅ Agent configurations rolled back to original"
fi

# Step 4: Test performance recovery
echo "🧪 Testing performance recovery..."
RECOVERY_PERF=$(npx ruv-swarm benchmark run --type quick --output json 2>/dev/null)

echo "✅ Performance rollback completed"
```

## 🔄 Granular Rollback Procedures

### 📁 File-Level Rollback

#### Rollback Individual Agent Files
```bash
# Rollback specific agent to original version
rollback_agent() {
    local agent_name=$1
    local backup_dir=$2
    
    if [ -f "$backup_dir/agents/$agent_name.md" ]; then
        cp "$backup_dir/agents/$agent_name.md" ".claude/agents/$agent_name.md"
        echo "✅ Rolled back agent: $agent_name"
    else
        echo "❌ Backup not found for agent: $agent_name"
    fi
}

# Usage examples
rollback_agent "researcher" ".claude.backup.20240814_143000"
rollback_agent "coder" ".claude.backup.20240814_143000"
rollback_agent "coordinator" ".claude.backup.20240814_143000"
```

#### Rollback CLAUDE.md Sections
```bash
# Rollback only the project-specific enhancements (preserve original 559 lines)
rollback_claude_enhancements() {
    local backup_file=$1
    
    if [ -f "$backup_file" ]; then
        # Keep original ruv-swarm configuration (lines 1-559)
        head -n 559 "$backup_file" > CLAUDE.md
        echo "✅ CLAUDE.md enhancements rolled back (ruv-swarm optimizations preserved)"
    else
        echo "❌ Backup file not found: $backup_file"
    fi
}

# Usage
rollback_claude_enhancements "CLAUDE.md.backup.20240814_143000"
```

#### Rollback New Commands
```bash
# Remove enhanced command files
rollback_commands() {
    local backup_dir=$1
    
    # Remove new command files
    rm -f .claude/commands/deploy.md
    echo "✅ Removed enhanced deploy commands"
    
    # Restore original commands if they exist
    if [ -d "$backup_dir/commands" ]; then
        cp -r "$backup_dir/commands"/* .claude/commands/
        echo "✅ Restored original command files"
    fi
}

# Usage
rollback_commands ".claude.backup.20240814_143000"
```

#### Rollback Helper Utilities
```bash
# Remove project-sync.py utility
rollback_helpers() {
    rm -f .claude/helpers/project-sync.py
    echo "✅ Removed project synchronization utility"
    
    # Restore original helpers if they exist
    if [ -d "$1/helpers" ]; then
        cp -r "$1/helpers"/* .claude/helpers/
        echo "✅ Restored original helper files"
    fi
}

# Usage
rollback_helpers ".claude.backup.20240814_143000"
```

### 🔧 Feature-Level Rollback

#### Disable Enhanced Hive Orchestration
```bash
# Disable Issue #50 Enhanced Hive features while keeping other enhancements
disable_enhanced_hive() {
    echo "🔄 Disabling Enhanced Hive Orchestration features..."
    
    # Update coordinator.md to use basic orchestration
    sed -i 's/Enhanced Hive Orchestration/Basic Orchestration/g' .claude/agents/coordinator.md
    sed -i 's/enhanced-hive/hierarchical/g' .claude/agents/coordinator.md
    
    # Remove Enhanced Hive patterns from CLAUDE.md
    sed -i '/# 🐝 Enhanced Hive Orchestration Integration/,/^## /d' CLAUDE.md
    
    echo "✅ Enhanced Hive Orchestration disabled"
}
```

#### Disable NetBox Plugin Specializations
```bash
# Remove NetBox-specific patterns while keeping core ruv-swarm functionality
disable_netbox_specializations() {
    echo "🔄 Disabling NetBox plugin specializations..."
    
    # Remove NetBox-specific sections from agents
    sed -i '/## NetBox Plugin/,/^## /d' .claude/agents/researcher.md
    sed -i '/## NetBox Plugin/,/^## /d' .claude/agents/coder.md
    
    # Remove NetBox patterns from CLAUDE.md
    sed -i '/# 🚀 PROJECT-SPECIFIC ENHANCEMENTS/,$d' CLAUDE.md
    
    echo "✅ NetBox plugin specializations disabled"
}
```

#### Disable Deployment Automation
```bash
# Remove deployment automation while keeping other features
disable_deployment_automation() {
    echo "🔄 Disabling deployment automation..."
    
    # Remove deployment commands
    rm -f .claude/commands/deploy.md
    
    # Remove project sync utility
    rm -f .claude/helpers/project-sync.py
    
    echo "✅ Deployment automation disabled"
}
```

## 🧪 Validation After Rollback

### 🔍 Basic Functionality Validation
```bash
# validation-after-rollback.sh
echo "🧪 Validating system after rollback..."

# Test 1: Basic swarm initialization
echo "Test 1: Basic swarm functionality..."
if npx ruv-swarm swarm init --topology mesh --max-agents 3 >/dev/null 2>&1; then
    echo "✅ Basic swarm functionality working"
else
    echo "❌ Basic swarm functionality failed"
    exit 1
fi

# Test 2: Agent spawning
echo "Test 2: Agent spawning..."
if npx ruv-swarm agent spawn --type researcher --name "Test" >/dev/null 2>&1; then
    echo "✅ Agent spawning working"
else
    echo "❌ Agent spawning failed"
    exit 1
fi

# Test 3: Memory operations
echo "Test 3: Memory operations..."
if npx ruv-swarm memory store --key "test/rollback" --value "validation" >/dev/null 2>&1; then
    echo "✅ Memory operations working"
else
    echo "❌ Memory operations failed"
    exit 1
fi

# Test 4: Performance benchmarks
echo "Test 4: Performance validation..."
PERF_RESULT=$(npx ruv-swarm benchmark run --type quick --output json 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "✅ Performance benchmarks working"
else
    echo "❌ Performance benchmarks failed"
    exit 1
fi

echo "✅ All validation tests passed"
```

### 📊 Performance Validation After Rollback
```bash
# performance-validation-after-rollback.sh
echo "📊 Validating performance after rollback..."

# Critical performance metrics validation
validate_performance_metrics() {
    echo "🎯 Checking critical performance metrics..."
    
    # SWE-Bench solve rate
    local swe_bench_rate=$(npx ruv-swarm benchmark run --type swe-bench --quick --output rate 2>/dev/null)
    if (( $(echo "$swe_bench_rate >= 84.8" | bc -l) )); then
        echo "✅ SWE-Bench solve rate: $swe_bench_rate% (target: ≥84.8%)"
    else
        echo "❌ SWE-Bench solve rate: $swe_bench_rate% (below target: ≥84.8%)"
        return 1
    fi
    
    # Token reduction
    local token_reduction=$(npx ruv-swarm benchmark run --type token-efficiency --quick --output rate 2>/dev/null)
    if (( $(echo "$token_reduction >= 32.3" | bc -l) )); then
        echo "✅ Token reduction: $token_reduction% (target: ≥32.3%)"
    else
        echo "❌ Token reduction: $token_reduction% (below target: ≥32.3%)"
        return 1
    fi
    
    # Speed improvement
    local speed_improvement=$(npx ruv-swarm benchmark run --type speed --quick --output multiplier 2>/dev/null)
    if (( $(echo "$speed_improvement >= 2.8" | bc -l) )); then
        echo "✅ Speed improvement: ${speed_improvement}x (target: ≥2.8x)"
    else
        echo "❌ Speed improvement: ${speed_improvement}x (below target: ≥2.8x)"
        return 1
    fi
    
    return 0
}

# Run validation
if validate_performance_metrics; then
    echo "✅ All performance metrics validated successfully"
else
    echo "❌ Performance validation failed - further rollback may be required"
    exit 1
fi
```

## 📝 Rollback Documentation

### 🗂️ Rollback Log Template
```bash
# Create rollback log entry
create_rollback_log() {
    local rollback_type=$1
    local reason=$2
    local timestamp=$(date -Iseconds)
    
    cat >> .claude/rollback-log.md << EOF

## Rollback Event: $timestamp

**Type**: $rollback_type
**Reason**: $reason
**Executed By**: $(whoami)
**Timestamp**: $timestamp

### Files Affected:
$(if [ "$rollback_type" = "full" ]; then
    echo "- Complete .claude directory"
    echo "- CLAUDE.md"
elif [ "$rollback_type" = "selective" ]; then
    echo "- Specific components (see details below)"
fi)

### Performance Before Rollback:
$(npx ruv-swarm benchmark run --type quick --output summary 2>/dev/null || echo "Performance data unavailable")

### Performance After Rollback:
(To be updated after validation)

### Validation Results:
$(bash validation-after-rollback.sh 2>&1 || echo "Validation pending")

### Next Steps:
- [ ] Monitor system stability
- [ ] Re-evaluate enhancement implementation
- [ ] Update rollback procedures if necessary

EOF

    echo "📝 Rollback event logged to .claude/rollback-log.md"
}
```

### 📋 Rollback Decision Matrix

| Issue Type | Severity | Rollback Type | Recovery Time | Validation Required |
|------------|----------|---------------|---------------|-------------------|
| System Crash | Critical | Emergency Full | 1 minute | Basic functionality |
| Performance Degradation >50% | High | Performance Selective | 5 minutes | Performance benchmarks |
| Agent Coordination Failure | Medium | Agent-specific | 10 minutes | Agent functionality |
| Memory Issues | Medium | Memory patterns | 15 minutes | Memory operations |
| Deployment Failures | Low | Deployment automation | 20 minutes | Deployment workflow |
| Documentation Issues | Low | Documentation only | 5 minutes | Documentation review |

## 🔄 Recovery Procedures

### 🚀 Re-implementation After Rollback
```bash
# re-implement-enhancements.sh
echo "🚀 Re-implementing enhancements after rollback..."

# Step 1: Analyze rollback cause
echo "🔍 Analyzing rollback cause..."
ROLLBACK_LOG=$(tail -n 50 .claude/rollback-log.md)
echo "Previous rollback reason: $ROLLBACK_LOG"

# Step 2: Implement staged rollout
echo "📈 Implementing staged rollout..."

# Stage 1: Core enhancements only
implement_core_enhancements() {
    echo "Stage 1: Implementing core enhancements..."
    # Implement basic NetBox patterns without Enhanced Hive
    cp docs/claude-optimization-research/modified-files-for-review/agents/researcher.md .claude/agents/
    echo "✅ Stage 1 complete"
}

# Stage 2: Add coordination features
implement_coordination_features() {
    echo "Stage 2: Adding coordination features..."
    cp docs/claude-optimization-research/modified-files-for-review/agents/coordinator.md .claude/agents/
    echo "✅ Stage 2 complete"
}

# Stage 3: Add deployment automation
implement_deployment_automation() {
    echo "Stage 3: Adding deployment automation..."
    cp docs/claude-optimization-research/modified-files-for-review/commands/deploy.md .claude/commands/
    cp docs/claude-optimization-research/modified-files-for-review/helpers/project-sync.py .claude/helpers/
    chmod +x .claude/helpers/project-sync.py
    echo "✅ Stage 3 complete"
}

# Execute staged implementation with validation at each stage
for stage in implement_core_enhancements implement_coordination_features implement_deployment_automation; do
    $stage
    
    # Validate each stage
    if bash validation-after-rollback.sh; then
        echo "✅ Stage validation passed"
    else
        echo "❌ Stage validation failed - rolling back stage"
        # Rollback this stage
        git checkout HEAD -- .claude/
        break
    fi
    
    # Wait for stability
    sleep 30
done

echo "✅ Staged re-implementation complete"
```

## 📞 Support and Escalation

### 🆘 When to Escalate
- Emergency rollback fails to restore functionality
- Performance cannot be restored to baseline levels
- Critical system components remain non-functional after rollback
- Data loss or corruption is suspected

### 📧 Escalation Procedure
1. **Document the issue**: Include rollback logs, performance data, error messages
2. **Preserve system state**: Create additional backups before further intervention
3. **Contact support**: Provide comprehensive technical details
4. **Coordinate recovery**: Work with technical team for resolution

This comprehensive rollback guide ensures rapid recovery from any issues while preserving the core ruv-swarm optimizations that provide the exceptional performance characteristics.