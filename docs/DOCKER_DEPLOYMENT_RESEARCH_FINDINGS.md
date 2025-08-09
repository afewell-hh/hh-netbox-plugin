# Docker Deployment Research Findings
**Research Agent Investigation - NetBox Hedgehog Plugin**
*Date: August 9, 2025*

## Executive Summary

**CRITICAL FINDING**: Code changes in the repository ARE NOT automatically deployed to the running Docker containers. This explains why previous agents reported work as "complete" when it wasn't actually deployed.

**DEPLOYMENT GAP CONFIRMED**: 
- Repository template file: `productivity_dashboard.html` exists with recent modifications
- Container: Same file does NOT exist in the container
- Image build date: July 29, 2025 (12 days old)
- Recent changes: Not reflected in running container

## Docker Environment Analysis

### Container Configuration
```bash
# Active containers (as of investigation)
NAMES                                 IMAGE                               STATUS
netbox-docker-netbox-1                netbox-hedgehog:latest              Up About an hour (healthy)   
netbox-docker-netbox-housekeeping-1   netboxcommunity/netbox:v4.3-3.3.0   Up 11 days (healthy)         
netbox-docker-netbox-worker-1         netboxcommunity/netbox:v4.3-3.3.0   Exited (1) 11 days ago       
netbox-docker-postgres-1              postgres:17-alpine                  Up 11 days (healthy)         
netbox-docker-redis-1                 valkey/valkey:8.1-alpine            Up 11 days (healthy)         
netbox-docker-redis-cache-1           valkey/valkey:8.1-alpine            Up 11 days (healthy)         
```

### Current Setup Analysis

#### Docker Configuration Structure
```
/home/ubuntu/cc/hedgehog-netbox-plugin/
├── gitignore/netbox-docker/              # Docker environment root
│   ├── docker-compose.yml               # Base NetBox containers
│   ├── docker-compose.override.yml      # Custom image override
│   ├── Dockerfile                       # Custom build with plugin
│   ├── configuration/
│   │   └── plugins.py                   # Plugin configuration
│   └── build.sh                         # Image build script
├── netbox_hedgehog/                     # Plugin source code
│   ├── templates/                       # Django templates
│   ├── static/                          # CSS/JS files
│   ├── views/                           # Python views
│   └── [other plugin files]
```

#### Key Discovery: Custom Image Build Process

**The plugin is built INTO the Docker image**, not volume mounted:

```dockerfile
# From Dockerfile (lines 89-94):
# Install Hedgehog NetBox Plugin  
COPY netbox_hedgehog /opt/netbox/netbox/netbox_hedgehog
RUN cd /opt/netbox && /opt/netbox/venv/bin/pip install -e ./netbox/netbox_hedgehog

# Update plugin files with latest version
COPY netbox_hedgehog /opt/netbox/netbox/netbox_hedgehog
```

**This means**: Files are copied AT BUILD TIME, not runtime.

## File Path Mapping

### Repository to Container Path Mapping
```
Repository Path                                     → Container Path
/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/     → /opt/netbox/netbox/netbox_hedgehog/templates/
/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/static/         → /opt/netbox/netbox/netbox_hedgehog/static/
/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/          → /opt/netbox/netbox/netbox_hedgehog/views/
/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/models/         → /opt/netbox/netbox/netbox_hedgehog/models/
/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/forms/          → /opt/netbox/netbox/netbox_hedgehog/forms/
/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/api/            → /opt/netbox/netbox/netbox_hedgehog/api/
```

### Volume Mounts (ONLY for specific directories)
```bash
# Current volume mounts (from docker inspect):
- netbox-docker_netbox-media-files     → /opt/netbox/netbox/media
- netbox-docker_netbox-reports-files   → /opt/netbox/netbox/reports  
- netbox-docker_netbox-scripts-files   → /opt/netbox/netbox/scripts
```

**NOTE**: Plugin files are NOT volume mounted - they are baked into the image.

## Deployment Process Analysis

### Current Image Information
- **Image**: `netbox-hedgehog:latest`
- **Build Date**: `2025-07-29T00:39:57.857949606Z` (12 days ago)
- **Base Image**: `netboxcommunity/netbox:v4.3-3.3.0`

### Build Process Location
- **Build Script**: `/home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker/build.sh`
- **Dockerfile**: `/home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker/Dockerfile`
- **Docker Compose**: `/home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker/docker-compose.yml`

## Evidence of Deployment Gap

### Timestamp Analysis
```bash
# Repository files (newer)
productivity_dashboard.html: Thu Jul 31 01:13:11 UTC 2025

# Container files (older)  
externalpeering_detail.html: Fri Jul 25 15:01:34 UTC 2025
```

### Missing Files Confirmed
```bash
# Repository has this file:
/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/productivity_dashboard.html

# Container does NOT have this file:
/opt/netbox/netbox/netbox_hedgehog/templates/netbox_hedgehog/productivity_dashboard.html
# Result: No such file or directory
```

## Root Cause Analysis

1. **Plugin Integration Method**: Plugin is built into Docker image, not volume mounted
2. **Build Frequency**: Image was last built 12 days ago
3. **Change Detection**: No automatic rebuild triggers for code changes
4. **Development Workflow**: Developers making changes without rebuilding container

## Recommended Deployment Solution

### Option 1: Rebuild Docker Image (RECOMMENDED)
**Pros**: Clean, matches production, fully tested
**Cons**: Takes 5-10 minutes, requires restart

**Process**:
```bash
cd /home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker
./build.sh main --push
docker-compose down
docker-compose up -d
```

### Option 2: Hot Copy Files (DEVELOPMENT ONLY)
**Pros**: Fast, no restart needed for templates/static
**Cons**: Incomplete, doesn't work for Python code changes

**Process**:
```bash
# Copy changed files
sudo docker cp /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/ netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/

# Restart for Python changes only
sudo docker restart netbox-docker-netbox-1
```

### Option 3: Volume Mount Development (FUTURE IMPROVEMENT)
**Pros**: Instant reflection of changes
**Cons**: Requires Docker configuration changes

**Implementation**:
```yaml
# Add to docker-compose.override.yml
services:
  netbox:
    volumes:
      - ../../netbox_hedgehog:/opt/netbox/netbox/netbox_hedgehog:ro
```

## Success Verification Commands

```bash
# 1. Check if container has latest files
sudo docker exec netbox-docker-netbox-1 ls -la /opt/netbox/netbox/netbox_hedgehog/templates/netbox_hedgehog/productivity_dashboard.html

# 2. Verify plugin is loaded
curl -I http://localhost:8000/plugins/hedgehog/productivity/

# 3. Check container logs for errors
sudo docker logs netbox-docker-netbox-1 --tail 20

# 4. Verify timestamp match
sudo docker exec netbox-docker-netbox-1 stat /opt/netbox/netbox/netbox_hedgehog/templates/netbox_hedgehog/productivity_dashboard.html
stat /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/productivity_dashboard.html
```

## Safety Procedures

### Pre-Deployment Backup
```bash
# 1. Backup current image
sudo docker tag netbox-hedgehog:latest netbox-hedgehog:backup-$(date +%Y%m%d_%H%M%S)

# 2. Export container data
sudo docker run --rm -v netbox-docker_netbox-media-files:/source -v $(pwd):/backup alpine tar czf /backup/netbox-media-backup-$(date +%Y%m%d_%H%M%S).tar.gz -C /source .
```

### Rollback Procedure
```bash
# 1. If new image fails, rollback
sudo docker tag netbox-hedgehog:backup-YYYYMMDD_HHMMSS netbox-hedgehog:latest

# 2. Restart with old image
cd /home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker
docker-compose down
docker-compose up -d

# 3. Verify rollback success
curl -f http://localhost:8000/login/
```

## Recommendations for Development Process

1. **Immediate Action**: Use Option 1 (rebuild) to deploy all pending changes
2. **Development Workflow**: Implement Option 3 (volume mount) for faster development
3. **CI/CD Integration**: Automate image rebuilds on code changes
4. **Documentation**: Update all agent playbooks with correct deployment procedures

## Tools and Environment Details

- **Docker Compose Directory**: `/home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker/`
- **Build Script**: `./build.sh main`  
- **Container Name**: `netbox-docker-netbox-1`
- **Plugin Path in Container**: `/opt/netbox/netbox/netbox_hedgehog/`
- **NetBox URL**: `http://localhost:8000`
- **Plugin URL**: `http://localhost:8000/plugins/hedgehog/`

---

**Next Action Required**: Execute Option 1 deployment to get all pending changes into the running environment.