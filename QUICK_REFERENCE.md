# Quick Reference - NetBox Plugin Development

## Essential Commands

### Start/Stop Environment

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart NetBox only
docker compose restart netbox

# View status
docker compose ps
```

### View Logs

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Follow NetBox logs
docker compose logs -f netbox

# Last 50 lines
docker compose logs --tail=50 netbox

# Check for errors
docker compose logs netbox | grep -i error
```

### Run Tests

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# All plugin tests
docker compose exec netbox python manage.py test netbox_hedgehog

# Specific test file
docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning.test_reference_data_models

# With coverage
docker compose exec netbox coverage run --source='netbox_hedgehog' manage.py test
docker compose exec netbox coverage report
```

### Database Migrations

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Create migrations
docker compose exec netbox python manage.py makemigrations netbox_hedgehog

# Apply migrations
docker compose exec netbox python manage.py migrate netbox_hedgehog

# Check migration status
docker compose exec netbox python manage.py showmigrations netbox_hedgehog
```

### Django Shell

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Interactive shell with autoloading
docker compose exec netbox python manage.py shell_plus

# Run single command
docker compose exec netbox python manage.py nbshell -c "from netbox_hedgehog.models import *; print(SwitchModel.objects.all())"
```

### Git Workflow

```bash
cd /home/ubuntu/afewell-hh/hh-netbox-plugin

# Create feature branch
git checkout -b diet-XXX-feature-name

# Add and commit (use [DIET-XXX] prefix)
git add .
git commit -m "[DIET-XXX] Your commit message"

# Push to origin
git push origin diet-XXX-feature-name
```

## File Locations

| What | Path |
|------|------|
| Plugin source code | `/home/ubuntu/afewell-hh/hh-netbox-plugin/netbox_hedgehog/` |
| Tests | `/home/ubuntu/afewell-hh/hh-netbox-plugin/tests/` |
| NetBox Docker | `/home/ubuntu/afewell-hh/netbox-docker/` |
| Docker configs | `/home/ubuntu/afewell-hh/hh-netbox-plugin/dev-setup/` |
| Documentation | `/home/ubuntu/afewell-hh/hh-netbox-plugin/*.md` |

## Access Points

- **NetBox UI**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin/
- **Plugin**: http://localhost:8000/plugins/hedgehog/
- **Credentials**: username `admin`, password `admin`

## Development Workflow (TDD)

1. **Write failing test** in `tests/test_topology_planning/`
2. **Run test** - should fail:
   ```bash
   docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning
   ```
3. **Implement feature** in `netbox_hedgehog/models/` or `netbox_hedgehog/views/`
4. **Run test** - should pass
5. **Create migrations** if models changed:
   ```bash
   docker compose exec netbox python manage.py makemigrations netbox_hedgehog
   docker compose exec netbox python manage.py migrate netbox_hedgehog
   ```
6. **Commit changes**:
   ```bash
   git add .
   git commit -m "[DIET-XXX] Description"
   ```

## Common Issues

### Plugin not loading
```bash
# Check if plugin is registered
docker compose exec netbox python manage.py nbshell -c "from django.conf import settings; print(settings.PLUGINS)"

# Check for errors
docker compose logs netbox | grep -i error
```

### Changes not reflecting
```bash
# Check if autoreload is running
docker compose logs netbox | grep "Watching for file changes"

# Hard restart
docker compose restart netbox
```

### Permission errors
```bash
# Fix file permissions
cd /home/ubuntu/afewell-hh/hh-netbox-plugin
find netbox_hedgehog -type f -exec chmod 644 {} \;
find netbox_hedgehog -type d -exec chmod 755 {} \;
```

## Important Files

- **CONTRIBUTORS.md** - Full development guide
- **CLAUDE.md** - AI agent instructions
- **DEVELOPMENT_ENVIRONMENT_SETUP.md** - Detailed environment info
- **dev-setup/docker-compose.override.yml** - Docker configuration
- **dev-setup/Dockerfile-Plugins** - Custom Docker image
- **Issue #85** - Current task (Reference Data Models)

## TDD Reminder

**ALWAYS write tests BEFORE implementation!**

1. RED - Write failing test
2. GREEN - Implement to make test pass
3. REFACTOR - Clean up while keeping tests green

## Coverage Requirement

Minimum **95% code coverage** for all new code.

Check with:
```bash
docker compose exec netbox coverage run --source='netbox_hedgehog' manage.py test
docker compose exec netbox coverage report
```
