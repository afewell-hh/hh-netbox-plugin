# Agent Development Workflow Guide

This guide provides streamlined workflows for agent development with the NetBox Hedgehog plugin.

## Quick Reference

### 🚀 First Time Setup
```bash
make dev-setup          # Complete environment setup (<5 minutes)
make agent-ready         # Verify everything is working
```

### 🔄 Daily Development Workflow
```bash
# After making code changes
make code-change         # Smart restart based on file changes

# Quick validation
make test-quick          # Fast health check

# View logs when debugging
make logs               # Tail service logs

# Access container for debugging
make shell              # Interactive container access
```

### 🧪 Testing & Validation
```bash
make test-quick         # Quick validation tests
make performance-check  # Check response times and resource usage
make health-monitor     # Continuous monitoring (Ctrl+C to stop)
```

### 🚨 Troubleshooting
```bash
make error-recovery     # Automatic error recovery
make fix-permissions    # Fix Docker permission issues
make restart-service    # Interactive service restart
```

## Agent-Optimized Commands

### 1. Smart Code Change Handling

**Command:** `make code-change`

**What it does:**
- Analyzes recent git changes or modified files
- Python files changed → Restarts app services
- Static files changed → Collects static files
- Migrations detected → Runs migrations
- Automatically runs quick validation

**Example:**
```bash
# After editing Python code
make code-change
# Output:
# 🔄 Handling Code Changes...
# 🐍 Python files changed - restarting app services
# ✅ Code changes handled
# 🧪 Quick Validation Tests
# ✅ NetBox responding
# ✅ Plugin responding
# ✅ Containers healthy
```

### 2. Fast Validation Tests

**Command:** `make test-quick`

**What it does:**
- Checks NetBox service availability
- Validates plugin accessibility
- Verifies container health
- Reports status with clear feedback

**Use cases:**
- After code changes
- Before committing changes
- When debugging issues
- Continuous integration checks

### 3. Intelligent Service Management

**Command:** `make restart-service`

**Interactive menu:**
1. netbox - Main application
2. workers - Background workers  
3. database - PostgreSQL
4. cache - Redis services
5. all - All services

**Smart dependencies:**
- Postgres restart → Also restarts dependent services
- Redis restart → Restarts services that use cache
- NetBox restart → Restarts workers that depend on it

### 4. Log Management

**Command:** `make logs`

**Features:**
- Shows last 50 lines from relevant services
- Follows logs in real-time
- Focuses on NetBox, workers, and Hedgehog services
- Press Ctrl+C to stop following

### 5. Container Shell Access

**Command:** `make shell`

**Options:**
1. netbox - Main NetBox container (bash)
2. postgres - Database container (psql)
3. redis - Redis container (redis-cli)

**Use cases:**
- Debugging application issues
- Running Django management commands
- Database queries and inspection
- Cache inspection and debugging

## Advanced Automation Scripts

### Agent Workflow Script

**Location:** `scripts/agent-workflow.sh`

**Commands:**
```bash
./scripts/agent-workflow.sh smart-restart    # Analyze and restart intelligently
./scripts/agent-workflow.sh health-check     # Quick health validation
./scripts/agent-workflow.sh performance      # Performance metrics
./scripts/agent-workflow.sh error-recovery   # Automatic error recovery
./scripts/agent-workflow.sh agent-ready      # Complete readiness check
```

### Container Manager Script

**Location:** `scripts/container-manager.sh`

**Commands:**
```bash
./scripts/container-manager.sh status                    # Container overview
./scripts/container-manager.sh restart netbox           # Restart service
./scripts/container-manager.sh logs netbox 100 true     # Follow logs
./scripts/container-manager.sh shell netbox             # Container access
./scripts/container-manager.sh monitor 300 10           # Resource monitoring
./scripts/container-manager.sh backup emergency         # Volume backup
```

## DevContainer Integration

### VS Code Development

1. **Open in DevContainer:**
   - Open project in VS Code
   - Command palette: "Dev Containers: Reopen in Container"
   - Automatic setup with `make dev-setup`

2. **Features:**
   - Hot reload for code changes
   - Integrated debugging
   - Port forwarding (8000, 5432, 6379)
   - Pre-configured Python environment

3. **Environment Variables:**
   ```
   NETBOX_URL=http://localhost:8000
   DEV_MODE=true
   PYTHONPATH=/opt/netbox/netbox
   ```

## Performance Optimization

### Response Time Monitoring

**Command:** `make performance-check`

**Metrics:**
- HTTP response time measurement
- Container resource usage
- Memory and CPU consumption
- Network I/O statistics

**Benchmarks:**
- Excellent: < 1000ms
- Good: < 3000ms  
- Slow: > 3000ms

### Resource Management

**Monitor continuously:**
```bash
make health-monitor     # Every 30 seconds
```

**Container stats:**
```bash
./scripts/container-manager.sh monitor 300 10
```

## Error Recovery Procedures

### Automatic Recovery

**Command:** `make error-recovery`

**Procedures:**
1. Diagnoses common issues
2. Restarts stopped containers
3. Attempts NetBox service recovery
4. Validates recovery success
5. Reports final status

### Manual Recovery Steps

1. **Service not responding:**
   ```bash
   make restart-service    # Choose netbox
   make test-quick        # Validate recovery
   ```

2. **Database issues:**
   ```bash
   make restart-service    # Choose database
   make migrate           # Run any pending migrations
   ```

3. **Permission issues:**
   ```bash
   make fix-permissions   # Fix Docker and file permissions
   ```

4. **Complete reset:**
   ```bash
   make dev-clean         # Stop all services
   make dev-setup         # Full setup again
   ```

## Best Practices for Agents

### 1. Before Starting Work
```bash
make agent-ready        # Comprehensive environment check
```

### 2. After Code Changes
```bash
make code-change        # Smart restart and validation
```

### 3. When Debugging
```bash
make logs              # Check service logs
make shell             # Access container for investigation
make performance-check # Check if performance is impacted
```

### 4. Before Committing
```bash
make test-quick        # Ensure everything still works
```

### 5. If Something Breaks
```bash
make error-recovery    # Automatic fix attempt
```

## Common Workflows

### Feature Development
1. `make agent-ready` - Verify environment
2. Make code changes
3. `make code-change` - Handle changes intelligently
4. `make test-quick` - Validate changes
5. Repeat steps 2-4 as needed
6. `make test-quick` - Final validation before commit

### Bug Investigation
1. `make logs` - Check for error messages
2. `make shell` - Access container for debugging
3. `make performance-check` - Check resource usage
4. Make fixes
5. `make code-change` - Apply fixes
6. `make test-quick` - Validate fix

### Environment Issues
1. `make status` - Check current state
2. `make error-recovery` - Attempt automatic fix
3. If needed: `make fix-permissions`
4. If still broken: `make dev-clean && make dev-setup`

## Tips for Maximum Productivity

1. **Use aliases in your shell:**
   ```bash
   alias mcc='make code-change'
   alias mtq='make test-quick'
   alias mar='make agent-ready'
   alias ml='make logs'
   ```

2. **Keep logs open in separate terminal:**
   ```bash
   make logs &  # Run in background
   ```

3. **Monitor health continuously during development:**
   ```bash
   make health-monitor &  # Run in background
   ```

4. **Use the container manager for detailed operations:**
   ```bash
   alias cm='./scripts/container-manager.sh'
   cm status
   cm logs netbox 50 true
   ```

## Troubleshooting Common Issues

### "NetBox not responding"
- **Solution:** `make restart-service` → Choose netbox
- **Prevention:** Use `make code-change` instead of manual restarts

### "Plugin not accessible"
- **Solution:** `make restart-service` → Choose netbox
- **Check:** Ensure plugin is properly installed with `make dev-setup`

### "Containers not healthy"
- **Solution:** `make error-recovery`
- **Investigation:** `./scripts/container-manager.sh status`

### "Permission denied"
- **Solution:** `make fix-permissions`
- **Note:** May require sudo password

### "Slow response times"
- **Investigation:** `make performance-check`
- **Solution:** Check container resources with monitoring

This guide provides everything needed for efficient agent development with minimal cognitive overhead and maximum automation.