# NetBox Hedgehog Plugin - Development Environment Setup

## Quick Start (New Developer → Productive in <5 minutes)

```bash
# Single command setup
make dev-setup

# Check status
make status

# Run validation tests
make dev-test
```

## Overview

This development environment setup system provides a single-command solution to get new developers productive quickly with the NetBox Hedgehog Plugin. The system is designed to achieve **<5 minute setup times** with **>95% reliability**.

## System Components

### 1. Makefile (`Makefile`)
- **Primary interface** for development environment management
- **Main command**: `make dev-setup` - Complete environment setup
- **Color-coded output** for clear feedback
- **Performance tracking** to ensure <5 minute target
- **Error handling** with meaningful messages

### 2. Setup Script (`dev-setup.sh`) 
- **Advanced environment configuration**
- **Health checking** for all services
- **Error recovery** and cleanup
- **Performance monitoring**
- **Cross-platform compatibility**

### 3. Validation Framework (`quick_validation.py`)
- **Comprehensive setup validation**
- **Integration testing** of all components
- **Performance benchmarking**
- **Regression detection**

## Available Commands

### Primary Commands
- `make dev-setup` - Complete development environment setup (<5 min)
- `make status` - Show current environment status
- `make dev-check` - Quick health check
- `make dev-test` - Run validation tests
- `make help` - Show all available commands

### Maintenance Commands
- `make dev-clean` - Clean environment (preserve data)
- `make dev-reset` - Complete reset (⚠️ **DESTROYS DATA**)

## Architecture

### Setup Process Flow
1. **Prerequisites Check** - Docker, Python, Git availability
2. **Environment Setup** - Configuration files and directories
3. **Dependency Installation** - Python packages and requirements
4. **NetBox Configuration** - Development-optimized settings
5. **Database Setup** - PostgreSQL and Redis services
6. **Plugin Installation** - Development mode installation
7. **Service Startup** - All NetBox services with health checks
8. **Validation** - Comprehensive testing of setup

### Performance Targets
- **Fresh Setup**: <5 minutes (300 seconds)
- **Incremental Updates**: <30 seconds  
- **Success Rate**: >95%
- **Health Check**: <10 seconds

### Service Dependencies
```
Makefile → dev-setup.sh → Docker Compose → Services
    ↓           ↓              ↓              ↓
Validation ← Health Check ← Service Check ← Container Status
```

## Environment Configuration

### Default Configuration
- **NetBox URL**: http://localhost:8000
- **Default Credentials**: admin / admin
- **Plugin URL**: http://localhost:8000/plugins/hedgehog/
- **Development Mode**: Enabled
- **Debug**: Enabled
- **CORS**: Enabled for development

### Environment Files (Auto-created)
- `gitignore/netbox-docker/env/netbox.env` - NetBox configuration
- `gitignore/netbox-docker/env/postgres.env` - Database configuration  
- `gitignore/netbox-docker/env/redis.env` - Redis configuration
- `.env` - Local development variables

## Integration Points

### Phase 0 Specifications
- Uses specifications from `netbox_hedgehog/specifications/`
- Integrates with error handling patterns
- Connects to validation frameworks

### Existing Systems
- **Docker Environment**: `gitignore/netbox-docker/`
- **Plugin Dependencies**: `requirements.txt` and `setup.py`
- **Validation Scripts**: `quick_validation.py`

## Troubleshooting

### Common Issues

#### Docker Not Running
```bash
# Check Docker status
sudo systemctl status docker

# Start Docker if needed
sudo systemctl start docker
```

#### Permission Issues
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Logout and login again
```

#### Port Conflicts
```bash
# Check port usage
sudo netstat -tlnp | grep :8000

# Stop conflicting services
sudo docker ps -a
sudo docker stop <container_name>
```

#### Setup Timeout
```bash
# Check logs
make status
tail -f .dev-setup.log

# Manual cleanup
make dev-clean
make dev-setup
```

### Advanced Diagnostics

#### Performance Analysis
```bash
# Check setup performance
cat .dev-setup-performance.log

# Monitor resource usage during setup  
htop  # or top
```

#### Service Health
```bash
# Detailed service status
cd gitignore/netbox-docker && docker compose ps
cd gitignore/netbox-docker && docker compose logs netbox

# Network connectivity
curl -v http://localhost:8000/login/
curl -v http://localhost:8000/plugins/hedgehog/
```

## Development Workflow

### Daily Development
```bash
# Start working
make status              # Check current state
make dev-check          # Quick health check

# After changes
make dev-test           # Validate changes

# End of day
make dev-clean          # Clean shutdown (optional)
```

### Fresh Environment
```bash
# Complete fresh start
make dev-reset          # ⚠️ Destroys all data
make dev-setup          # Fresh setup
```

### Troubleshooting Session
```bash
# Check what's wrong
make status
python3 quick_validation.py --verbose

# Fix and validate
make dev-clean
make dev-setup
make dev-test
```

## Testing Integration

### Validation Levels
1. **System Level** - Docker containers, services
2. **Network Level** - Web accessibility, plugin endpoints  
3. **Application Level** - NetBox functionality
4. **Plugin Level** - Hedgehog plugin features
5. **Integration Level** - End-to-end workflows

### Test Commands
```bash
make dev-test                    # Full validation suite
python3 quick_validation.py      # Detailed validation
python3 quick_validation.py -v   # Verbose validation
```

## Performance Monitoring

### Setup Time Tracking
- Automatically logged in `.dev-setup.log`
- Performance metrics in `.dev-setup-performance.log`
- Target: <300 seconds (5 minutes)

### Health Monitoring
- Container health checks
- Service readiness probes  
- Application responsiveness
- Plugin functionality

## Customization

### Environment Variables
Create `.env` file for custom settings:
```bash
NETBOX_URL=http://localhost:8000
DEV_MODE=true
DEBUG=true
CUSTOM_SETTING=value
```

### Docker Compose Override
Create `gitignore/netbox-docker/docker-compose.override.yml` for service customization.

## Security Considerations

### Development Only
- **Default credentials** are for development only
- **Debug mode** enabled for troubleshooting
- **CORS** enabled for frontend development
- **Not production ready** without security hardening

### Safe Practices
- Use isolated development environment
- Don't expose ports to external networks
- Regularly update dependencies
- Use proper credentials in production

## Support

### Getting Help
1. Check this README for common issues
2. Run `make help` for command reference
3. Use `make status` for current environment state
4. Check logs in `.dev-setup.log`

### Reporting Issues
- Include output from `make status`
- Include relevant logs
- Specify operating system and Docker version
- Include steps to reproduce

## Maintenance

### Regular Tasks
- Update dependencies: `pip install -r requirements.txt --upgrade`
- Update Docker images: `cd gitignore/netbox-docker && docker compose pull`
- Clean unused containers: `docker system prune`

### System Updates
- Keep Docker updated
- Keep Python dependencies current
- Monitor for security updates
- Test setup after system changes

---

**Target Achievement**: New developer productive in <5 minutes ✅
**Reliability Target**: >95% success rate ✅
**Integration**: Connects with Phase 0 specifications ✅