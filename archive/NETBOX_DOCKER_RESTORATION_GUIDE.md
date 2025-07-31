# NetBox Docker Environment Restoration Guide

## Issue Description
During Phase 6 cleanup (commit `4fa45be266abb4270d7bd26d798debeb16e3a5d3`), the `gitignore/netbox-docker/` directory was accidentally deleted. This directory contains critical infrastructure files needed to restart the NetBox development environment.

## What Was Lost
The cleanup removed the entire `gitignore/` directory containing:
- **docker-compose.yml**: Main Docker Compose configuration
- **docker/**: Directory with Docker scripts and configurations
- **env/**: Environment configuration files
- **Other infrastructure files**: VERSION, Dockerfile, build scripts

## What Was Restored (2025-07-25)
✅ **docker-compose.yml**: Main compose file restored from upstream
✅ **docker/ directory**: All Docker scripts and configurations
✅ **env/ directory**: Environment configuration  
✅ **configuration/plugins.py**: Updated with `netbox_hedgehog` plugin configuration
✅ **Supporting files**: Dockerfile, VERSION, build scripts, etc.

## Current Status
- ✅ NetBox containers continue running normally
- ✅ Environment can now be restarted if needed
- ✅ Critical files committed to git to prevent future loss

## Testing the Restoration

### Verify Files Are Present:
```bash
ls -la gitignore/netbox-docker/
# Should show: docker-compose.yml, docker/, env/, configuration/, etc.
```

### Test Docker Compose (CAUTION - Only if containers are stopped):
```bash
cd gitignore/netbox-docker/
docker-compose ps  # Check current status
# docker-compose up -d  # Only run if environment is down
```

### Verify Plugin Configuration:
```bash
sudo docker exec netbox-docker-netbox-1 python manage.py shell -c "from django.conf import settings; print('PLUGINS:', settings.PLUGINS)"
# Should show: PLUGINS: ['netbox_hedgehog']
```

## Source Repository
The files were restored from the official NetBox Docker repository:
- **Repository**: https://github.com/netbox-community/netbox-docker
- **Commit**: Latest as of 2025-07-25

## Customizations Made
1. **plugins.py**: Added `netbox_hedgehog` to PLUGINS list
2. **Preserved existing configuration files**: The existing configuration/ directory was kept to preserve any HNP-specific settings

## Prevention Measures
1. ✅ Critical files now tracked in git (forced add despite .gitignore)
2. ✅ This restoration guide documents the process
3. ✅ Cleanup procedures should verify infrastructure dependencies before removal

## Container Information
Current running containers (as of restoration):
```
netbox-docker-netbox-1                netbox-hedgehog:latest
netbox-docker-netbox-worker-1         netboxcommunity/netbox:v4.3-3.3.0
netbox-docker-netbox-housekeeping-1   netboxcommunity/netbox:v4.3-3.3.0
netbox-docker-postgres-1              postgres:17-alpine
netbox-docker-redis-1                 valkey/valkey:8.1-alpine
netbox-docker-redis-cache-1           valkey/valkey:8.1-alpine
```

## Recovery Commands Summary
If this happens again, use these commands to restore:

```bash
# Clone the official repository
git clone https://github.com/netbox-community/netbox-docker.git netbox-docker-restore

# Restore critical files (preserve existing configuration/)
sudo cp netbox-docker-restore/docker-compose.yml gitignore/netbox-docker/
sudo cp -r netbox-docker-restore/docker gitignore/netbox-docker/
sudo cp -r netbox-docker-restore/env gitignore/netbox-docker/
sudo cp netbox-docker-restore/docker-compose.override.yml.example gitignore/netbox-docker/
sudo cp netbox-docker-restore/Dockerfile netbox-docker-restore/*.sh netbox-docker-restore/VERSION gitignore/netbox-docker/

# Update plugins.py to include Hedgehog plugin
sudo tee gitignore/netbox-docker/configuration/plugins.py > /dev/null << 'EOF'
PLUGINS = ["netbox_hedgehog"]
PLUGINS_CONFIG = {
    "netbox_hedgehog": {
        # Add your Hedgehog plugin settings here
    }
}
EOF

# Commit to prevent future loss
git add -f gitignore/netbox-docker/docker-compose.yml gitignore/netbox-docker/configuration/plugins.py
git commit -m "restore: recover netbox-docker infrastructure files"

# Cleanup
rm -rf netbox-docker-restore
```

## Lessons Learned
1. **Infrastructure directories should be identified before cleanup**: The gitignore/netbox-docker directory was critical infrastructure, not just development artifacts
2. **Docker compose files are essential**: Without docker-compose.yml, the environment cannot be restarted
3. **Plugin configurations need preservation**: Custom plugin settings in configuration/ files must be maintained
4. **Backup critical infrastructure**: Development environment setup files should be backed up or documented

## Related Issues
- Original deletion: Commit `4fa45be` - "Phase 6 cleanup: Remove safe development artifacts (batch 1)"
- Restoration: Commit `7ae3b9a` - "restore: recover deleted netbox-docker infrastructure files"