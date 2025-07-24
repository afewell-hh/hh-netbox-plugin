# NetBox Docker Operations

**NetBox Version**: 4.3.3  
**Plugin Integration**: Volume mounted at /opt/netbox/netbox/hedgehog-netbox-plugin  
**Access URL**: http://localhost:8000

## Docker Environment

### Container Status Check
```bash
docker ps | grep netbox
```

Expected containers:
- netbox-netbox-1 (main application)
- netbox-postgres-1 (database)
- netbox-redis-1 (cache)
- netbox-redis-cache-1 (cache)
- netbox-netbox-worker-1 (background tasks)
- netbox-netbox-housekeeping-1 (maintenance)

### Plugin Installation Path
```
/gitignore/netbox-docker/              # NetBox Docker root
├── docker-compose.yml                 # Main compose file
├── docker-compose.override.yml        # Plugin volume mount
└── netbox-hedgehog-plugin/           # Plugin source (mounted)
```

### Common Operations

#### Restart NetBox with Plugin Changes
```bash
cd /gitignore/netbox-docker
docker-compose restart netbox netbox-worker
```

#### View Logs
```bash
docker-compose logs -f netbox          # Application logs
docker-compose logs -f postgres        # Database logs
```

#### Access Django Shell
```bash
docker-compose exec netbox python manage.py shell
```

#### Run Migrations
```bash
docker-compose exec netbox python manage.py migrate
```

## Plugin Configuration

### Volume Mount (docker-compose.override.yml)
```yaml
services:
  netbox:
    volumes:
      - ./netbox-hedgehog-plugin:/opt/netbox/netbox/hedgehog-netbox-plugin:ro
```

### Plugin Registration
Located in NetBox configuration.py:
```python
PLUGINS = ['netbox_hedgehog']
```

## Troubleshooting

### Plugin Not Loading
1. Check volume mount: `docker-compose exec netbox ls -la /opt/netbox/netbox/`
2. Verify __init__.py exists in plugin directory
3. Check logs for import errors
4. Restart containers after changes

### Database Connection Issues
- PostgreSQL runs on default port 5432 inside Docker network
- Database name: netbox
- Shared with NetBox core tables

### Static Files
- Collected automatically on container start
- Manual collection: `docker-compose exec netbox python manage.py collectstatic`