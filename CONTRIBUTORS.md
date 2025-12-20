# Contributors Guide - Hedgehog NetBox Plugin

## Project Overview

This NetBox plugin provides design and operational management tools for Hedgehog Open Network Fabric deployments.

**Current Sprint Focus:** DIET (Design and Implementation Excellence Tools) - Topology Planning Module

## Quick Start for Contributors

### Prerequisites

- Docker and Docker Compose installed on your development host
- Git configured with your credentials
- Basic understanding of Django, NetBox, and Hedgehog fabric concepts

### Initial Setup

1. **Clone this repository** (if not already done):
   ```bash
   cd /home/ubuntu/afewell-hh
   git clone https://github.com/afewell-hh/hh-netbox-plugin.git
   cd hh-netbox-plugin
   ```

2. **Set up the NetBox development environment**:
   ```bash
   # Clone netbox-docker in a sibling directory
   cd /home/ubuntu/afewell-hh
   git clone https://github.com/netbox-community/netbox-docker.git
   cd netbox-docker

   # Check out a stable version (v4.3 recommended)
   git checkout release
   ```

3. **Configure the development environment**:
   ```bash
   # Create docker-compose.override.yml (see Development Environment section below)
   cp /home/ubuntu/afewell-hh/hh-netbox-plugin/dev-setup/docker-compose.override.yml ./

   # Create Dockerfile-Plugins
   cp /home/ubuntu/afewell-hh/hh-netbox-plugin/dev-setup/Dockerfile-Plugins ./

   # Create plugin_requirements.txt
   echo "-e /plugins/hh-netbox-plugin" > plugin_requirements.txt
   ```

4. **Start NetBox with your plugin**:
   ```bash
   # From the netbox-docker directory
   docker compose up -d

   # Wait for containers to initialize (first run takes ~2-3 minutes)
   docker compose logs -f netbox

   # Access NetBox at http://localhost:8000
   # Default credentials: admin / admin
   ```

5. **Verify plugin is loaded**:
   - Navigate to http://localhost:8000/plugins/hedgehog/
   - You should see the Hedgehog plugin interface

## Development Environment Details

### Directory Structure

```
/home/ubuntu/afewell-hh/
├── hh-netbox-plugin/          # This repository (your plugin code)
│   ├── netbox_hedgehog/       # Plugin source code
│   ├── tests/                 # Test suite
│   ├── dev-setup/             # Development configuration files
│   └── ...
└── netbox-docker/             # NetBox Docker environment
    ├── docker-compose.yml     # Base configuration
    ├── docker-compose.override.yml  # Development overrides
    ├── Dockerfile-Plugins     # Custom image with plugin
    ├── configuration/         # NetBox config files
    └── plugin_requirements.txt
```

### Docker Compose Override Configuration

Create `/home/ubuntu/afewell-hh/netbox-docker/docker-compose.override.yml`:

```yaml
version: '3.4'
services:
  netbox:
    build:
      context: .
      dockerfile: Dockerfile-Plugins
    image: netbox:latest-plugins-dev
    pull_policy: never
    volumes:
      # Mount the plugin source code for live reloading
      - /home/ubuntu/afewell-hh/hh-netbox-plugin:/opt/netbox/netbox/netbox_hedgehog:ro
    environment:
      - DEBUG=true
      - DEVELOPER=true
    command: python manage.py runserver 0.0.0.0:8000
    ports:
      - "8000:8000"

  netbox-worker:
    build:
      context: .
      dockerfile: Dockerfile-Plugins
    image: netbox:latest-plugins-dev
    pull_policy: never
    volumes:
      - /home/ubuntu/afewell-hh/hh-netbox-plugin:/opt/netbox/netbox/netbox_hedgehog:ro
    environment:
      - DEBUG=true
      - DEVELOPER=true

  netbox-housekeeping:
    image: netbox:latest-plugins-dev
    pull_policy: never
    volumes:
      - /home/ubuntu/afewell-hh/hh-netbox-plugin:/opt/netbox/netbox/netbox_hedgehog:ro
```

### Custom Dockerfile

Create `/home/ubuntu/afewell-hh/netbox-docker/Dockerfile-Plugins`:

```dockerfile
FROM netboxcommunity/netbox:latest

# Install development dependencies
RUN /opt/netbox/venv/bin/pip install --no-cache-dir \
    ipython \
    django-extensions \
    coverage

# Copy and install plugin requirements
COPY ./plugin_requirements.txt /opt/netbox/
RUN /opt/netbox/venv/bin/pip install --no-cache-dir -r /opt/netbox/plugin_requirements.txt

# The plugin itself is mounted as a volume for live development
```

### Plugin Configuration

The plugin is automatically configured via NetBox's plugin discovery. Ensure your `netbox_hedgehog/__init__.py` contains:

```python
from netbox.plugins import PluginConfig

class HedgehogConfig(PluginConfig):
    name = 'netbox_hedgehog'
    verbose_name = 'Hedgehog Open Network Fabric'
    description = 'Design and operational management tools for Hedgehog fabric'
    version = '0.2.0'
    author = 'Hedgehog Team'
    author_email = 'support@githedgehog.com'
    base_url = 'hedgehog'
    required_settings = []
    default_settings = {}

config = HedgehogConfig
```

## Development Workflow

### Branch Strategy

All development follows the **feature branch workflow**:

1. **Create a feature branch** from `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b diet-XXX-feature-description
   ```

2. **Name branches** using the pattern: `diet-XXX-short-description`
   - Example: `diet-001-reference-data-models`
   - Example: `diet-002-topology-plan-models`

3. **Commit messages** follow the pattern: `[DIET-XXX] Description`
   - Example: `[DIET-001] Add SwitchModel and SwitchPortGroup models`
   - Example: `[DIET-001] Add unit tests for reference data models`

### Test-Driven Development (TDD)

**CRITICAL: All new features must follow TDD workflow**

1. **Red**: Write a failing test
   ```bash
   # Create test file
   touch tests/test_topology_planning/test_new_feature.py

   # Write test that fails
   python manage.py test netbox_hedgehog.tests.test_topology_planning.test_new_feature
   ```

2. **Green**: Implement minimum code to make test pass
   ```bash
   # Implement feature
   vim netbox_hedgehog/models/topology_planning/new_feature.py

   # Run test until it passes
   python manage.py test netbox_hedgehog.tests.test_topology_planning.test_new_feature
   ```

3. **Refactor**: Clean up code while keeping tests passing
   ```bash
   # Improve code quality
   # Re-run tests after each change
   python manage.py test
   ```

### Common Development Tasks

#### Running Tests

```bash
# Run all tests for the plugin
docker compose exec netbox python manage.py test netbox_hedgehog

# Run specific test file
docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning.test_reference_data_models

# Run with coverage
docker compose exec netbox coverage run --source='netbox_hedgehog' manage.py test
docker compose exec netbox coverage report
docker compose exec netbox coverage html
```

#### Database Migrations

```bash
# Create new migration after model changes
docker compose exec netbox python manage.py makemigrations netbox_hedgehog

# Apply migrations
docker compose exec netbox python manage.py migrate netbox_hedgehog

# Show migration status
docker compose exec netbox python manage.py showmigrations netbox_hedgehog

# Rollback migration (if needed)
docker compose exec netbox python manage.py migrate netbox_hedgehog 000X
```

#### Django Shell

```bash
# Access Django shell for debugging
docker compose exec netbox python manage.py shell_plus

# Example session:
>>> from netbox_hedgehog.models.topology_planning import SwitchModel
>>> SwitchModel.objects.all()
>>> sw = SwitchModel.objects.create(model_id='TEST', vendor='Test', total_ports=32)
>>> sw.save()
```

#### Viewing Logs

```bash
# Follow all container logs
docker compose logs -f

# Follow NetBox application logs only
docker compose logs -f netbox

# View last 100 lines
docker compose logs --tail=100 netbox
```

#### Restarting After Code Changes

**Most code changes are automatically detected via Django's development server.**

If you need to restart:
```bash
# Restart just the NetBox container
docker compose restart netbox

# Rebuild if you changed dependencies
docker compose down
docker compose build --no-cache
docker compose up -d
```

#### Accessing Django Admin

Navigate to http://localhost:8000/admin/
- Username: admin
- Password: admin

All plugin models should be registered and accessible here.

### Code Quality Standards

#### Python Style

- Follow **PEP 8** style guide
- Use **4 spaces** for indentation
- Maximum line length: **120 characters**
- Use **type hints** where appropriate

#### Django Conventions

- Model names: `CamelCase` singular (e.g., `SwitchModel`)
- Field names: `snake_case` (e.g., `model_id`)
- Always define `__str__()` method for models
- Always include `Meta` class with `ordering` and `verbose_name`

#### Documentation

- **Docstrings** for all classes and non-trivial functions
- **Inline comments** for complex logic
- **README** updates for new features
- **Migration comments** explaining schema changes

#### Testing Requirements

- **Minimum 95% code coverage** for new code
- **Unit tests** for all models
- **Integration tests** for views and API endpoints
- **Test fixtures** for common scenarios

### Pull Request Process

1. **Ensure all tests pass**:
   ```bash
   docker compose exec netbox python manage.py test netbox_hedgehog
   ```

2. **Check code coverage**:
   ```bash
   docker compose exec netbox coverage run --source='netbox_hedgehog' manage.py test
   docker compose exec netbox coverage report
   # Ensure >= 95% coverage for changed files
   ```

3. **Verify migrations**:
   ```bash
   docker compose exec netbox python manage.py makemigrations --check --dry-run
   ```

4. **Create pull request** with template:
   ```markdown
   ## Summary
   [Brief description of changes]

   ## Changes
   - [Detailed change 1]
   - [Detailed change 2]

   ## Testing
   - [ ] All unit tests pass
   - [ ] Code coverage >= 95%
   - [ ] Migrations apply cleanly
   - [ ] Manual testing completed

   ## Checklist
   - [ ] Follows TDD approach
   - [ ] Documentation updated
   - [ ] Commit messages follow [DIET-XXX] format

   Closes #XX
   ```

5. **Request review** from other team members (agents A, C, G)

6. **Address feedback** and push updates

7. **Merge** only after approval and passing CI/CD

## Project-Specific Guidelines

### Current Sprint: DIET Tools

The current sprint focuses on **Design and Implementation Excellence Tools (DIET)** for topology planning:

1. **Reference Data Layer** (#85)
   - SwitchModel, SwitchPortGroup, NICModel, BreakoutOption models

2. **Topology Plan Layer** (#86)
   - TopologyPlan, PlanServerClass, PlanSwitchClass, PlanServerConnection models

3. **Calculation Engine** (#87)
   - Switch quantity calculations with breakout math
   - Rail-optimized topology support

4. **YAML Generation** (#88)
   - Generate Hedgehog wiring diagrams from topology plans

### Separation of Concerns

**IMPORTANT:** DIET tools are separate from operational features:

- **DIET models** live in `models/topology_planning/`
- **Operational models** live in `models/operational/` or root `models/`
- **Do NOT mix** DIET and operational code paths
- DIET features work **offline** (no Kubernetes connection required)

### Hedgehog Environment

A Hedgehog vlab is available on an adjacent host with IP reachability for testing operational features (future work). The current DIET sprint does not require this environment.

## Troubleshooting

### Plugin not appearing in NetBox

1. Check plugin is listed:
   ```bash
   docker compose exec netbox python manage.py nbshell
   >>> from django.conf import settings
   >>> settings.PLUGINS
   ['netbox_hedgehog']
   ```

2. Check for import errors:
   ```bash
   docker compose logs netbox | grep -i error
   ```

3. Verify volume mount:
   ```bash
   docker compose exec netbox ls -la /opt/netbox/netbox/netbox_hedgehog
   ```

### Changes not reflecting

1. Ensure Django development server is running:
   ```bash
   docker compose logs netbox | grep runserver
   ```

2. Check for Python syntax errors:
   ```bash
   docker compose exec netbox python -m py_compile /opt/netbox/netbox/netbox_hedgehog/models/your_file.py
   ```

3. Hard restart:
   ```bash
   docker compose restart netbox
   ```

### Migration issues

1. Check for conflicts:
   ```bash
   docker compose exec netbox python manage.py showmigrations
   ```

2. Reset database (development only!):
   ```bash
   docker compose down -v
   docker compose up -d
   docker compose exec netbox python manage.py migrate
   ```

## Resources

- [NetBox Plugin Development Tutorial](https://github.com/netbox-community/netbox-plugin-tutorial)
- [NetBox Documentation](https://docs.netbox.dev/)
- [Django Documentation](https://docs.djangoproject.com/)
- [Hedgehog Fabric Documentation](https://docs.githedgehog.com/)
- Project Issues: https://github.com/afewell-hh/hh-netbox-plugin/issues

## Getting Help

- **Issue #82**: Comprehensive project analysis
- **Issue #83**: DIET feature requirements (PRD)
- **Issue #84**: Current sprint planning
- **CLAUDE.md**: AI agent-specific instructions

For questions, create a GitHub issue with the `question` label.
