# Django/NetBox Plugin Hot-Reload Development Workflow

## Overview

This document provides a comprehensive analysis and optimization guide for the Django/NetBox plugin hot-reload development workflow for the Hedgehog NetBox Plugin.

## Current Architecture Analysis

### Container Setup
- **Base Image**: `netboxcommunity/netbox:v4.3-3.3.0`
- **Volume Mount**: `./netbox_hedgehog:/opt/netbox/netbox/netbox_hedgehog:rw`
- **Plugin Installation**: Editable mode (`pip install -e .`)

### Service Architecture
- **netbox**: Main web service
- **netbox-worker**: RQ worker for background tasks
- **netbox-rq-worker-hedgehog**: Specialized Hedgehog plugin worker
- **netbox-rq-scheduler**: Periodic task scheduler

## Hot-Reload Capability Matrix

| File Type | Auto-Reload | Restart Required | Notes |
|-----------|-------------|------------------|-------|
| **Python Files** | ✅ | ❌ | Django dev server auto-reloads |
| **Models** | ⚠️ | ✅ | Requires migration + restart |
| **Views** | ✅ | ❌ | Auto-reload with volume mount |
| **URLs** | ✅ | ❌ | Auto-reload |
| **Templates** | ✅ | ❌ | Auto-reload if DEBUG=True |
| **Static Files (CSS/JS)** | ⚠️ | ❌ | Need collectstatic or dev server |
| **Settings** | ❌ | ✅ | Always requires restart |
| **Migrations** | ❌ | ✅ | Requires migrate + restart |
| **Dependencies** | ❌ | ✅ | pip install + restart |
| **Plugin Config** | ❌ | ✅ | Plugin registration changes |

## Development Scenarios & Commands

### Scenario 1: Code Changes (Models, Views, Services)

**Files affected**: `models/`, `views/`, `services/`

```bash
# No action needed - auto-reload works
# Changes are immediately available in container
echo "✅ Changes auto-reloaded"
```

**What happens**:
- Volume mount makes changes instantly available
- Django auto-reload detects Python file changes
- Services restart automatically

### Scenario 2: Template/Static File Changes

**Files affected**: `templates/`, `static/`

```bash
# For templates - no action needed
echo "✅ Template changes auto-reloaded"

# For static files in development
docker compose exec netbox python manage.py collectstatic --noinput
# OR use Django dev server which serves static files directly
```

### Scenario 3: Database Migration Changes

**Files affected**: `migrations/`

```bash
# Create migration
docker compose exec netbox python manage.py makemigrations netbox_hedgehog

# Apply migration
docker compose exec netbox python manage.py migrate

# Restart services to reload model changes
docker compose restart netbox netbox-worker netbox-rq-worker-hedgehog
```

### Scenario 4: New Dependency Additions

**Files affected**: `requirements.txt`, `setup.py`

```bash
# Rebuild container with new dependencies
docker compose build netbox

# Restart all services
docker compose up -d
```

### Scenario 5: Settings/Configuration Changes

**Files affected**: `settings.py`, `__init__.py` (plugin config)

```bash
# Full restart required
docker compose restart netbox netbox-worker netbox-rq-worker-hedgehog netbox-rq-scheduler
```

## Service Restart Matrix

| Change Type | Services to Restart |
|-------------|-------------------|
| Python code | None (auto-reload) |
| Templates | None (auto-reload) |
| Static files | None (if using dev server) |
| Models | `netbox`, `netbox-worker`, `netbox-rq-worker-hedgehog` |
| Settings | All services |
| Dependencies | All services (rebuild required) |
| Migrations | All services |

## Optimized Development Commands

### Quick Development Setup

```bash
# Initialize development environment
./dev-setup.sh

# Start all services
cd gitignore/netbox-docker && docker compose up -d

# Watch logs
docker compose logs -f netbox
```

### Development Loop Commands

```bash
# Check service health
docker compose ps

# Quick restart for model changes
docker compose restart netbox netbox-worker netbox-rq-worker-hedgehog

# Full restart for config changes
docker compose restart

# View logs for debugging
docker compose logs -f netbox netbox-worker

# Execute Django commands
docker compose exec netbox python manage.py shell
docker compose exec netbox python manage.py migrate
docker compose exec netbox python manage.py collectstatic --noinput
```

### Performance Monitoring

```bash
# Check container resource usage
docker stats

# Monitor Django performance
docker compose exec netbox python manage.py performance_test

# Check database performance
docker compose exec postgres pg_stat_activity
```

## Integration Testing Strategy

### 1. Container-based Testing

```bash
# Run tests in container environment
docker compose exec netbox python manage.py test netbox_hedgehog

# Run specific test modules
docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_models

# Run with coverage
docker compose exec netbox coverage run --source='.' manage.py test netbox_hedgehog
docker compose exec netbox coverage report
```

### 2. Database State Management

```bash
# Create test database snapshot
docker compose exec postgres pg_dump -U netbox netbox > test_snapshot.sql

# Restore test database
docker compose exec -T postgres psql -U netbox netbox < test_snapshot.sql

# Reset to clean state
docker compose exec netbox python manage.py flush --noinput
docker compose exec netbox python manage.py migrate
```

### 3. Automated Testing Integration

```bash
# Pre-commit testing
docker compose exec netbox python manage.py test netbox_hedgehog --keepdb

# Integration test suite
docker compose exec netbox python manage.py run_e2e_workflow_test

# Performance regression testing
docker compose exec netbox python manage.py performance_test --baseline
```

## Performance Optimization Recommendations

### 1. Development Server Optimization

```python
# In development settings
DEBUG = True
DEVELOPER = True

# Enable Django debug toolbar
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

# Optimize static file serving
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
```

### 2. Container Optimization

```dockerfile
# Use multi-stage builds for faster rebuilds
FROM netboxcommunity/netbox:v4.3-3.3.0 as base

# Add development dependencies only in dev stage
FROM base as development
RUN pip install django-debug-toolbar pytest-django
```

### 3. Volume Mount Optimization

```yaml
# Use bind mounts for better performance on Linux
volumes:
  - ./netbox_hedgehog:/opt/netbox/netbox/netbox_hedgehog:rw,cached
  
# For macOS/Windows, consider volume optimizations
volumes:
  - ./netbox_hedgehog:/opt/netbox/netbox/netbox_hedgehog:rw,delegated
```

### 4. Database Optimization for Development

```python
# Development database settings
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {
            'sslmode': 'disable',
            'connection_timeout': 5,
        }
    }
}

# Cache configuration for development
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
        }
    }
}
```

## Development Workflow Best Practices

### 1. Fast Development Loop

1. **Code changes**: Edit Python files - auto-reload (0 seconds)
2. **Template changes**: Edit templates - auto-reload (0 seconds)
3. **Model changes**: Create migration → apply → restart (10-15 seconds)
4. **Static changes**: Use dev server or collectstatic (2-5 seconds)

### 2. Debugging Strategy

```bash
# Enable Django debug mode
export DJANGO_DEBUG=True

# Use Django shell for interactive debugging
docker compose exec netbox python manage.py shell

# View detailed logs
docker compose logs -f netbox | grep -i error

# Database debugging
docker compose exec netbox python manage.py dbshell
```

### 3. Performance Monitoring

```bash
# Monitor container resources
docker stats netbox netbox-worker

# Check Django query performance
docker compose exec netbox python manage.py debug_sql

# Profile specific operations
docker compose exec netbox python manage.py diagnostic_fgd_ingestion --profile
```

## Troubleshooting Common Issues

### Issue: Changes Not Reflected

**Symptoms**: Code changes don't appear in the application

**Solutions**:
```bash
# Check volume mount
docker compose exec netbox ls -la /opt/netbox/netbox/netbox_hedgehog/

# Restart Django process
docker compose restart netbox

# Check file permissions
docker compose exec netbox chown -R unit:root /opt/netbox/netbox/netbox_hedgehog/
```

### Issue: Static Files Not Loading

**Symptoms**: CSS/JS changes not visible

**Solutions**:
```bash
# Collect static files
docker compose exec netbox python manage.py collectstatic --noinput

# Check static file configuration
docker compose exec netbox python manage.py findstatic hedgehog.css

# Use development server for automatic static file serving
# (already configured with DEBUG=True)
```

### Issue: Database Migration Errors

**Symptoms**: Migration fails or models out of sync

**Solutions**:
```bash
# Check migration status
docker compose exec netbox python manage.py showmigrations netbox_hedgehog

# Create missing migrations
docker compose exec netbox python manage.py makemigrations netbox_hedgehog

# Reset migrations (development only)
docker compose exec netbox python manage.py migrate netbox_hedgehog zero
docker compose exec netbox python manage.py migrate netbox_hedgehog
```

## Summary

The current setup provides excellent hot-reload capabilities for most development scenarios:

- **Immediate feedback** for Python code and template changes
- **Fast restart** (10-15 seconds) for model changes
- **Efficient testing** with containerized environment
- **Good performance** with optimized volume mounts

The volume mount strategy `./netbox_hedgehog:/opt/netbox/netbox/netbox_hedgehog:rw` is optimal for development, providing instant file synchronization while maintaining proper permissions.