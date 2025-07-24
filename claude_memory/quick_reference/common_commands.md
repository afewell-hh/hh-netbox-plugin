# Common Commands Quick Reference

## NetBox Docker Operations

```bash
# Navigate to NetBox Docker
cd /gitignore/netbox-docker

# Restart NetBox after plugin changes
docker-compose restart netbox netbox-worker

# View live logs
docker-compose logs -f netbox

# Access Django shell
docker-compose exec netbox python manage.py shell

# Run migrations
docker-compose exec netbox python manage.py migrate

# Collect static files
docker-compose exec netbox python manage.py collectstatic --noinput
```

## Kubernetes Operations

```bash
# Check cluster connectivity
kubectl cluster-info

# List Hedgehog CRDs
kubectl get crds | grep fabric8s.com

# Get all connections
kubectl get connections.vpc.fabric8s.com

# Describe a specific resource
kubectl describe server.wiring.fabric8s.com <name>

# Watch for changes
kubectl get servers.wiring.fabric8s.com -w
```

## Development Commands

```bash
# Run tests
python -m pytest netbox_hedgehog/tests/

# Format code
black netbox_hedgehog/

# Lint code
flake8 netbox_hedgehog/

# Type checking
mypy netbox_hedgehog/
```

## Git Operations

```bash
# Create feature branch
git checkout -b feature/description

# Stage and commit
git add -A
git commit -m "feat: implement new functionality"

# Push to remote
git push -u origin feature/description
```

## Plugin Development

```bash
# Create new migration
docker-compose exec netbox python manage.py makemigrations netbox_hedgehog

# Test specific view
docker-compose exec netbox python manage.py test netbox_hedgehog.tests.test_views

# Debug template loading
docker-compose exec netbox python manage.py findstatic netbox_hedgehog/fabric_detail.html
```

## Useful URLs

- NetBox UI: http://localhost:8000
- Admin Panel: http://localhost:8000/admin/
- Plugin Dashboard: http://localhost:8000/plugins/hedgehog/
- API Root: http://localhost:8000/api/
- Plugin API: http://localhost:8000/api/plugins/hedgehog/