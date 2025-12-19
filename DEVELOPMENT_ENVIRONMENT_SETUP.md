# Development Environment Setup - Complete

## Status: Ready for Development ✅

Date: 2025-12-19
Environment: NetBox Development with Docker

---

## What Was Accomplished

Successfully set up a fully functional NetBox plugin development environment with:

1. **NetBox Docker environment** configured for live code reloading
2. **Volume mounting** of plugin source code for instant changes
3. **Development server** running (Django's runserver with StatReloader)
4. **Plugin loaded successfully** and accessible in NetBox
5. **Documentation created** (CONTRIBUTORS.md, CLAUDE.md, dev-setup files)

---

## Environment Details

### Directory Structure

```
/home/ubuntu/afewell-hh/
├── hh-netbox-plugin/                    # Plugin source code (THIS REPO)
│   ├── netbox_hedgehog/                 # Plugin Python package
│   │   ├── __init__.py                  # Plugin config
│   │   ├── models/                       # Django models
│   │   ├── views/                        # Views
│   │   ├── api/                          # REST API
│   │   └── ...
│   ├── tests/                            # Test suite
│   ├── dev-setup/                        # Docker configuration files
│   ├── CONTRIBUTORS.md                   # Contributor guide
│   ├── CLAUDE.md                         # AI agent instructions
│   └── DEVELOPMENT_ENVIRONMENT_SETUP.md  # This file
│
└── netbox-docker/                        # NetBox Docker environment
    ├── docker-compose.yml                # Base NetBox services
    ├── docker-compose.override.yml       # Development overrides
    ├── Dockerfile-Plugins                # Custom image with plugin
    ├── plugin_requirements.txt           # Plugin dependencies
    └── configuration/
        └── plugins.py                    # Plugin configuration
```

### Volume Mount

```
Host: /home/ubuntu/afewell-hh/hh-netbox-plugin/netbox_hedgehog
  ↓
Container: /opt/netbox/netbox/netbox_hedgehog (read-only)
```

### Running Services

```
Service                    Container                       Port     Status
-------------------------  ----------------------------  -------  --------
NetBox (dev server)        netbox-docker-netbox-1         8000     Running
PostgreSQL                 netbox-docker-postgres-1       5432     Running
Redis                      netbox-docker-redis-1          6379     Running
Redis Cache                netbox-docker-redis-cache-1    6379     Running
```

### Access Points

- **NetBox UI**: http://localhost:8000
- **Admin Credentials**: username `admin`, password `admin`
- **Django Admin**: http://localhost:8000/admin/
- **Plugin Base URL**: http://localhost:8000/plugins/hedgehog/

---

## How the Development Environment Works

### Live Code Reloading

1. **Edit Python files** in `/home/ubuntu/afewell-hh/hh-netbox-plugin/netbox_hedgehog/`
2. **Django detects changes** automatically (via StatReloader)
3. **Server reloads** within 1-2 seconds
4. **Refresh browser** to see changes

No need to restart containers for Python code changes!

### When to Restart

Restart NetBox container only when:
- Changing dependencies in `plugin_requirements.txt`
- Modifying Docker configuration files
- After running database migrations
- If something seems stuck

```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose restart netbox
```

### Database Migrations

After creating or modifying models:

```bash
# Navigate to netbox-docker directory
cd /home/ubuntu/afewell-hh/netbox-docker

# Create migration files
docker compose exec netbox python manage.py makemigrations netbox_hedgehog

# Apply migrations
docker compose exec netbox python manage.py migrate netbox_hedgehog

# Verify migration status
docker compose exec netbox python manage.py showmigrations netbox_hedgehog
```

### Running Tests

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Run all plugin tests
docker compose exec netbox python manage.py test netbox_hedgehog

# Run specific test file
docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning.test_reference_data_models

# Run with coverage
docker compose exec netbox coverage run --source='netbox_hedgehog' manage.py test
docker compose exec netbox coverage report
```

### Django Shell

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Access Django shell with autoloading
docker compose exec netbox python manage.py shell_plus

# Example session:
>>> from netbox_hedgehog.models.topology_planning import SwitchModel
>>> SwitchModel.objects.all()
<QuerySet []>
```

### Viewing Logs

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Follow NetBox logs
docker compose logs -f netbox

# View last 50 lines
docker compose logs --tail=50 netbox

# Check for errors
docker compose logs netbox | grep -i error
```

---

## Configuration Files

### docker-compose.override.yml

Located at: `/home/ubuntu/afewell-hh/netbox-docker/docker-compose.override.yml`

Key features:
- Builds custom image with development tools
- Mounts plugin source code as read-only volume
- Enables DEBUG mode
- Runs Django development server instead of production WSGI
- Exposes port 8000

### Dockerfile-Plugins

Located at: `/home/ubuntu/afewell-hh/netbox-docker/Dockerfile-Plugins`

Installs:
- Development dependencies (ipython, django-extensions, coverage)
- Plugin dependencies (kubernetes, pyyaml, jsonschema)
- Uses `uv` package manager (NetBox's standard)

### plugins.py

Located at: `/home/ubuntu/afewell-hh/netbox-docker/configuration/plugins.py`

```python
PLUGINS = ["netbox_hedgehog"]

PLUGINS_CONFIG = {
    "netbox_hedgehog": {
        # Plugin-specific settings
    }
}
```

---

## Important Notes

### File Permissions

All files in `netbox_hedgehog/` must have proper permissions:
- Directories: `755` (rwxr-xr-x)
- Files: `644` (rw-r--r--)

If you encounter permission errors:
```bash
find /home/ubuntu/afewell-hh/hh-netbox-plugin/netbox_hedgehog -type f -exec chmod 644 {} \;
find /home/ubuntu/afewell-hh/hh-netbox-plugin/netbox_hedgehog -type d -exec chmod 755 {} \;
```

### Docker Hub Authentication

The environment is authenticated with Docker Hub using credentials from `.env`:
- Username: `afewellgmail`
- Token: (stored in .env)

If you encounter Docker pull errors, re-authenticate:
```bash
docker logout
echo "<token-from-env>" | docker login -u afewellgmail --password-stdin
```

### Python Path

The plugin is accessible at `/opt/netbox/netbox/netbox_hedgehog` inside the container. Django can import it as:
```python
import netbox_hedgehog
from netbox_hedgehog.models.topology_planning import SwitchModel
```

---

## Troubleshooting

### Plugin Not Loading

1. Check if plugin is in PLUGINS list:
   ```bash
   docker compose exec netbox python manage.py nbshell -c "from django.conf import settings; print(settings.PLUGINS)"
   ```

2. Check for import errors:
   ```bash
   docker compose logs netbox | grep -i error
   ```

3. Verify volume mount:
   ```bash
   docker compose exec netbox ls -la /opt/netbox/netbox/netbox_hedgehog
   ```

### Changes Not Reflecting

1. Check if StatReloader is running:
   ```bash
   docker compose logs netbox | grep "Watching for file changes"
   ```

2. Hard restart:
   ```bash
   docker compose restart netbox
   ```

3. Clear Python cache:
   ```bash
   find /home/ubuntu/afewell-hh/hh-netbox-plugin/netbox_hedgehog -type d -name __pycache__ -exec rm -rf {} +
   ```

### Container Won't Start

1. Check logs:
   ```bash
   docker compose logs netbox
   ```

2. Verify all containers are running:
   ```bash
   docker compose ps
   ```

3. Start fresh:
   ```bash
   docker compose down
   docker compose up -d
   ```

### Database Issues

Reset database (development only - destroys all data!):
```bash
docker compose down -v  # Removes volumes
docker compose up -d
docker compose exec netbox python manage.py migrate
docker compose exec netbox python manage.py createsuperuser
```

---

## Next Steps

Now that the development environment is ready:

1. **Review CONTRIBUTORS.md** for development workflow
2. **Review CLAUDE.md** for agent-specific instructions
3. **Start working on issue #85** - Reference Data Models
4. **Follow TDD workflow** - write tests first!

### Quick Start for Development

```bash
# 1. Navigate to NetBox Docker directory
cd /home/ubuntu/afewell-hh/netbox-docker

# 2. Ensure containers are running
docker compose ps

# 3. Create a test file
# Edit: /home/ubuntu/afewell-hh/hh-netbox-plugin/tests/test_topology_planning/test_reference_data_models.py

# 4. Run the test (it will fail - that's expected in TDD)
docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning

# 5. Implement the feature
# Edit: /home/ubuntu/afewell-hh/hh-netbox-plugin/netbox_hedgehog/models/topology_planning/reference_data.py

# 6. Run test again (should pass now)
docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning

# 7. Create migrations
docker compose exec netbox python manage.py makemigrations netbox_hedgehog

# 8. Apply migrations
docker compose exec netbox python manage.py migrate netbox_hedgehog

# 9. Commit your changes
cd /home/ubuntu/afewell-hh/hh-netbox-plugin
git add .
git commit -m "[DIET-001] Your commit message"
```

---

## References

- **CONTRIBUTORS.md** - Full contributor guide with workflows
- **CLAUDE.md** - AI agent-specific instructions
- **Issue #82** - Project analysis and context
- **Issue #83** - DIET feature requirements (PRD)
- **Issue #84** - Sprint planning
- **Issue #85** - Current task (Reference Data Models)

---

## Summary

The development environment is fully operational and ready for DIET feature development. All documentation is in place, and the workflow supports:

- ✅ Live code reloading
- ✅ Test-driven development
- ✅ Database migrations
- ✅ Django admin access
- ✅ Debug mode enabled
- ✅ Clean separation of concerns

**You can now begin implementing issue #85!**
