# Agent Deployment Verification Guide

## Critical Issue: File Changes vs GUI Visibility

**The Problem**: Agents frequently report "fixed and working" when only files are updated, but changes aren't visible in the GUI. This happens because applications need to be restarted to reload code/templates.

## MANDATORY First Step: Identify Deployment Architecture

Before making ANY code changes, agents MUST run these commands to understand the deployment:

```bash
# Check for Docker containers (REQUIRES SUDO)
sudo docker ps | grep -E "(netbox|hedgehog)"

# Check for docker-compose files  
find . -name "docker-compose*" -o -name "Dockerfile*"

# Check for development servers
ps aux | grep -E "(manage.py runserver|python.*server)"

# Check for systemd services
systemctl list-units | grep -E "(netbox|hedgehog|django)"
```

## Deployment Types & Restart Commands

### 1. Docker Deployment (Most Common)
**Identification**: `sudo docker ps` shows netbox containers
**Location**: Usually has `docker-compose.yml`

**Restart Commands** (ALL REQUIRE SUDO):
```bash
# Navigate to docker-compose directory first
cd /path/to/docker-compose/directory

# Restart specific service
sudo docker compose restart netbox

# Or restart all services  
sudo docker compose restart

# Check container status
sudo docker ps | grep netbox
```

### 2. Development Server
**Identification**: `ps aux | grep "manage.py runserver"`

**Restart Commands**:
```bash
# Kill existing server
pkill -f "manage.py runserver"

# Start new server (in project directory)
python manage.py runserver 0.0.0.0:8000
```

### 3. Production Deployment
**Identification**: `systemctl list-units | grep netbox`

**Restart Commands**:
```bash
sudo systemctl restart netbox
sudo systemctl restart nginx  # if using nginx
```

## Verification Checklist

Agents must complete ALL steps before claiming "fixed and working":

### Phase 1: File Updates
- [ ] Made code/template changes
- [ ] Verified files saved correctly (`grep` or `cat` to confirm)
- [ ] Cleared Python cache if needed (`find . -name "*.pyc" -delete`)

### Phase 2: Application Restart  
- [ ] Identified deployment type using commands above
- [ ] Executed appropriate restart command with sudo if needed
- [ ] Verified restart succeeded (no errors in logs)
- [ ] Waited 10-30 seconds for application to fully reload

### Phase 3: GUI Verification
- [ ] Hard refresh browser (Ctrl+F5 or Cmd+Shift+R)
- [ ] Checked in incognito/private mode to bypass browser cache
- [ ] **ACTUALLY LOOKED AT THE GUI** and confirmed changes are visible
- [ ] Tested functionality if applicable (buttons, forms, etc.)

## Common Mistakes to Avoid

❌ **"Files are updated so it's working"** - Files ≠ Running Application  
❌ **Forgetting `sudo` for docker commands** - Will fail with permission errors  
❌ **Only checking file contents** - Template caching means files != GUI  
❌ **Browser caching assumptions** - Usually it's application restart needed  
❌ **Not waiting after restart** - Applications need time to reload  

## Docker-Specific Notes

- **ALL docker commands require `sudo`** unless user is in docker group
- Volume mounts mean files are shared, but **application restart still required**
- Template caching in Django means mounted files don't auto-reload
- Always check `docker-compose.yml` to understand volume mappings

## Emergency Debugging Commands

If changes still not visible after proper restart:

```bash
# Check container logs
sudo docker logs netbox-docker-netbox-1

# Check if files actually mounted correctly
sudo docker exec netbox-docker-netbox-1 ls -la /opt/netbox/netbox/netbox_hedgehog/templates/

# Force template cache clear (inside container)
sudo docker exec netbox-docker-netbox-1 /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py shell -c "from django.core.cache import cache; cache.clear()"
```

## Success Criteria

An agent can only claim "fixed and working" when:
1. ✅ Files are correctly updated
2. ✅ Application properly restarted (with sudo if needed)
3. ✅ Changes are **visible and functional in GUI**
4. ✅ User has confirmed they can see the changes

**Remember**: If the user says "I don't see any changes", the fix is NOT complete regardless of file status.