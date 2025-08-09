# Docker Deployment Guide - NetBox Hedgehog Plugin

## Quick Reference - Deploy Code Changes

### Method 1: Complete Rebuild (RECOMMENDED for Production)
```bash
# Navigate to Docker directory
cd /home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker

# Build new image with latest code
./build.sh main

# Restart containers with new image
docker-compose down
docker-compose up -d

# Verify deployment
curl -f http://localhost:8000/plugins/hedgehog/
```

### Method 2: Hot Copy (DEVELOPMENT/TESTING ONLY)
```bash
# Copy templates (for UI changes)
sudo docker cp /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/ netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/

# Copy static files (for CSS/JS changes)  
sudo docker cp /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/static/ netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/

# For Python code changes, restart container
sudo docker restart netbox-docker-netbox-1

# Verify changes
sudo docker logs netbox-docker-netbox-1 --tail 20
```

---

## Complete Deployment Process

### Pre-Deployment Safety

#### 1. Backup Current Environment
```bash
# Create image backup
sudo docker tag netbox-hedgehog:latest netbox-hedgehog:backup-$(date +%Y%m%d_%H%M%S)

# Backup data volumes
cd /home/ubuntu/cc/hedgehog-netbox-plugin
mkdir -p backups
sudo docker run --rm -v netbox-docker_netbox-media-files:/source -v $(pwd)/backups:/backup alpine tar czf /backup/netbox-media-$(date +%Y%m%d_%H%M%S).tar.gz -C /source .

# Record current state
sudo docker ps > backups/container-state-$(date +%Y%m%d_%H%M%S).txt
```

#### 2. Pre-Deployment Verification
```bash
# Check repository changes
cd /home/ubuntu/cc/hedgehog-netbox-plugin
git status
git diff HEAD~1 --name-only

# Verify Docker environment
cd gitignore/netbox-docker
docker-compose ps
```

### Deployment Execution

#### Option A: Full Image Rebuild (RECOMMENDED)

**Step 1: Build New Image**
```bash
cd /home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker

# Build with latest code
echo "Building NetBox Hedgehog image with latest code..."
./build.sh main

# Check build success
if [ $? -eq 0 ]; then
    echo "✅ Image build successful"
else
    echo "❌ Image build failed - stopping deployment"
    exit 1
fi
```

**Step 2: Deploy New Image**
```bash
# Stop current containers
echo "Stopping containers..."
docker-compose down

# Start with new image
echo "Starting containers with new image..."
docker-compose up -d

# Wait for containers to be healthy
echo "Waiting for containers to start..."
sleep 30
```

**Step 3: Verify Deployment**
```bash
# Check container status
docker-compose ps

# Check application accessibility
timeout=60
echo "Verifying NetBox accessibility..."
while [ $timeout -gt 0 ]; do
    if curl -f http://localhost:8000/login/ >/dev/null 2>&1; then
        echo "✅ NetBox is accessible"
        break
    fi
    echo -n "."
    sleep 2
    timeout=$((timeout-2))
done

if [ $timeout -le 0 ]; then
    echo "❌ NetBox not accessible after 60 seconds"
    exit 1
fi

# Check plugin accessibility
if curl -f http://localhost:8000/plugins/hedgehog/ >/dev/null 2>&1; then
    echo "✅ Hedgehog plugin is accessible"
else
    echo "⚠️ Hedgehog plugin may need additional configuration"
fi
```

#### Option B: Hot Copy (Development Only)

**Step 1: Copy Changed Files**
```bash
# Templates (for UI changes)
echo "Copying template files..."
sudo docker cp /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/ netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/

# Static files (for CSS/JS changes)
echo "Copying static files..."
sudo docker cp /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/static/ netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/

# Python files (requires restart)
echo "Copying Python files..."
sudo docker cp /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/ netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/
sudo docker cp /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/models/ netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/
sudo docker cp /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/forms/ netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/
sudo docker cp /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/api/ netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/
```

**Step 2: Restart for Python Changes**
```bash
# Restart NetBox container
echo "Restarting NetBox container..."
sudo docker restart netbox-docker-netbox-1

# Wait for restart
sleep 15
```

### Post-Deployment Verification

#### 1. Container Health Check
```bash
echo "=== Container Health Check ==="
sudo docker ps | grep netbox

# Check for healthy status
if sudo docker ps | grep "netbox-docker-netbox-1" | grep -q "healthy"; then
    echo "✅ NetBox container is healthy"
else
    echo "⚠️ NetBox container may not be healthy"
    sudo docker logs netbox-docker-netbox-1 --tail 10
fi
```

#### 2. Application Verification
```bash
echo "=== Application Verification ==="

# NetBox web interface
if curl -I http://localhost:8000/login/ 2>/dev/null | grep -q "200 OK"; then
    echo "✅ NetBox web interface: OK"
else
    echo "❌ NetBox web interface: FAILED"
fi

# Plugin endpoints
if curl -I http://localhost:8000/plugins/hedgehog/ 2>/dev/null | grep -q "200\|302"; then
    echo "✅ Hedgehog plugin: OK"
else
    echo "❌ Hedgehog plugin: FAILED"
fi

# Check for specific features (adjust URLs based on actual plugin)
for endpoint in "productivity" "gitops" "dashboard"; do
    if curl -s http://localhost:8000/plugins/hedgehog/$endpoint/ | grep -q "hedgehog\|Hedgehog"; then
        echo "✅ Plugin endpoint /$endpoint/: OK"
    else
        echo "⚠️ Plugin endpoint /$endpoint/: May need verification"
    fi
done
```

#### 3. File Verification
```bash
echo "=== File Verification ==="

# Check that latest files are in container
echo "Checking latest files in container..."

# Template files
if sudo docker exec netbox-docker-netbox-1 ls /opt/netbox/netbox/netbox_hedgehog/templates/netbox_hedgehog/productivity_dashboard.html >/dev/null 2>&1; then
    echo "✅ productivity_dashboard.html: Present in container"
else
    echo "❌ productivity_dashboard.html: Missing from container"
fi

# Compare timestamps (latest files should have recent timestamps)
echo "Comparing file timestamps..."
repo_time=$(stat -c %Y /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/productivity_dashboard.html 2>/dev/null || echo "0")
container_time=$(sudo docker exec netbox-docker-netbox-1 stat -c %Y /opt/netbox/netbox/netbox_hedgehog/templates/netbox_hedgehog/productivity_dashboard.html 2>/dev/null || echo "0")

if [ "$container_time" -ge "$repo_time" ]; then
    echo "✅ Container files are up to date"
else
    echo "❌ Container files are outdated"
fi
```

#### 4. Log Analysis
```bash
echo "=== Log Analysis ==="

# Check for errors in logs
echo "Recent container logs:"
sudo docker logs netbox-docker-netbox-1 --tail 20

# Check for plugin-specific errors
if sudo docker logs netbox-docker-netbox-1 --tail 100 | grep -i "hedgehog\|error\|exception"; then
    echo "⚠️ Found potential issues in logs - review above"
else
    echo "✅ No obvious errors in recent logs"
fi
```

### Rollback Procedure

#### If Deployment Fails
```bash
echo "=== ROLLBACK PROCEDURE ==="

# Find latest backup
backup_tag=$(sudo docker images | grep netbox-hedgehog | grep backup | head -1 | awk '{print $2}')

if [ -n "$backup_tag" ]; then
    echo "Rolling back to: netbox-hedgehog:$backup_tag"
    
    # Tag backup as latest
    sudo docker tag netbox-hedgehog:$backup_tag netbox-hedgehog:latest
    
    # Restart containers
    cd /home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker
    docker-compose down
    docker-compose up -d
    
    # Verify rollback
    sleep 30
    if curl -f http://localhost:8000/login/ >/dev/null 2>&1; then
        echo "✅ Rollback successful"
    else
        echo "❌ Rollback failed - manual intervention needed"
    fi
else
    echo "❌ No backup found - manual recovery needed"
fi
```

## Environment Details

### Key Paths
- **Repository Root**: `/home/ubuntu/cc/hedgehog-netbox-plugin/`
- **Docker Directory**: `/home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker/`
- **Plugin Source**: `/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/`
- **Container Plugin Path**: `/opt/netbox/netbox/netbox_hedgehog/`

### Key Commands
- **Build Script**: `./build.sh main`
- **Container Management**: `docker-compose down/up -d`
- **Container Access**: `sudo docker exec -it netbox-docker-netbox-1 /bin/bash`
- **Logs**: `sudo docker logs netbox-docker-netbox-1 --tail 50`

### URLs
- **NetBox**: `http://localhost:8000`
- **Plugin Base**: `http://localhost:8000/plugins/hedgehog/`
- **Admin**: `http://localhost:8000/admin/`

### Container Names
- **NetBox**: `netbox-docker-netbox-1`
- **PostgreSQL**: `netbox-docker-postgres-1`
- **Redis**: `netbox-docker-redis-1`
- **Redis Cache**: `netbox-docker-redis-cache-1`

## Troubleshooting Common Issues

### Issue: Build Fails
```bash
# Check Docker space
df -h
sudo docker system df

# Clean up if needed
sudo docker system prune -f

# Rebuild with verbose output
cd /home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker
./build.sh main --verbose
```

### Issue: Container Won't Start
```bash
# Check container logs
sudo docker logs netbox-docker-netbox-1

# Check dependencies
sudo docker logs netbox-docker-postgres-1
sudo docker logs netbox-docker-redis-1

# Check Docker Compose
cd /home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker
docker-compose config --quiet && echo "✅ Compose file is valid" || echo "❌ Compose file has errors"
```

### Issue: Plugin Not Loading
```bash
# Check plugin configuration
sudo docker exec netbox-docker-netbox-1 cat /etc/netbox/config/plugins.py

# Check plugin installation
sudo docker exec netbox-docker-netbox-1 pip list | grep hedgehog

# Check plugin directory
sudo docker exec netbox-docker-netbox-1 ls -la /opt/netbox/netbox/netbox_hedgehog/
```

---

## Development Workflow Integration

### For Regular Development
1. Make code changes in repository
2. Use Method 2 (Hot Copy) for quick testing
3. Use Method 1 (Rebuild) before committing changes
4. Always verify deployment with the verification commands

### For Production Releases
1. Always use Method 1 (Complete Rebuild)
2. Run complete verification suite
3. Document deployment with git tags
4. Keep backup images for rollback capability

This deployment guide ensures that all code changes are properly deployed to the Docker containers and provides safety mechanisms for reliable deployments.