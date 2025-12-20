# Claude Code Agent Instructions

## Project Context

You are working on the **Hedgehog NetBox Plugin** (`hh-netbox-plugin`), a NetBox plugin that provides design and operational management tools for Hedgehog Open Network Fabric deployments.

### Current State (as of 2025-12-19)

- **Project Status**: Revival in progress after period of inactivity
- **Current Sprint**: DIET (Design and Implementation Excellence Tools) - Issue #84
- **Sprint Focus**: Topology Planning Module for pre-sales/design workflows
- **Existing Code**: ~50% complete operational features (mostly read operations)
- **Branch**: `diet-001-reference-data-models`

## Critical Context Documents

Read these issues FIRST before making any changes:

1. **Issue #82** - Comprehensive project analysis (READ THIS FIRST)
   - Project is ~50% complete, not 85%
   - Lists all known issues and technical debt
   - Security concerns (exposed credentials)
   - 62 of 74 issues should be closed

2. **Issue #83** - DIET Feature PRD (Product Requirements Document)
   - Complete data model specifications
   - Calculation engine requirements
   - YAML generation specifications
   - Full technical architecture

3. **Issue #84** - Sprint Planning & Technical Architecture
   - Current sprint scope and goals
   - Success criteria
   - Technical decisions

4. **Issue #85** - Current Task: Reference Data Models
   - Your likely current assignment
   - Detailed implementation steps
   - TDD requirements

## Development Environment

### Location & Structure

```
/home/ubuntu/afewell-hh/
├── hh-netbox-plugin/          # THIS REPOSITORY - mounted as volume
│   ├── netbox_hedgehog/       # Plugin source code
│   ├── tests/                 # Test suite
│   └── dev-setup/             # Docker config files
└── netbox-docker/             # NetBox container environment
    ├── docker-compose.yml
    ├── docker-compose.override.yml
    └── Dockerfile-Plugins
```

### Key Facts

- **Host**: Docker host at `/home/ubuntu/afewell-hh/`
- **NetBox runs in container**: Access at http://localhost:8000
- **Plugin code is volume-mounted**: Changes reflect immediately (Django dev server)
- **Python path**: Plugin installed at `/opt/netbox/netbox/netbox_hedgehog` in container
- **No need to restart** for most Python code changes

### Running Commands

**ALWAYS use `docker compose exec` for Django/Python commands:**

```bash
# From /home/ubuntu/afewell-hh/netbox-docker/

# Run tests
docker compose exec netbox python manage.py test netbox_hedgehog

# Create migrations
docker compose exec netbox python manage.py makemigrations netbox_hedgehog

# Apply migrations
docker compose exec netbox python manage.py migrate netbox_hedgehog

# Django shell
docker compose exec netbox python manage.py shell_plus

# Check logs
docker compose logs -f netbox
```

**DO NOT** run Django commands directly on the host - they must run inside the container.

## Agent Collaboration Model

You are **Agent A** working alongside:
- **Agent C**: Focuses on code quality, NetBox conventions, testing
- **Agent G**: Focuses on architecture, system design, integration

### Communication Protocol

You cannot communicate directly with other agents. To share information:

1. **Ask the human** to pass messages: "Please ask Agent C if..."
2. **Use commit messages** to communicate progress
3. **Use PR comments** for code review
4. **Update issues** with status/questions

### Before Major Decisions

**ASK FOR FEEDBACK** from other agents via the human on:
- Data model design changes
- API design decisions
- Major refactoring
- New dependencies
- Architecture patterns

Example: "Please ask Agent C and Agent G to review my proposed data model before I implement it."

## Mandatory Development Practices

### 1. Test-Driven Development (TDD)

**ABSOLUTELY REQUIRED** - Write tests BEFORE implementation:

```python
# STEP 1: Write failing test (RED)
def test_switch_model_creation(self):
    """Test creating a SwitchModel"""
    switch = SwitchModel.objects.create(
        model_id='DS5000',
        vendor='Dell',
        total_ports=64
    )
    self.assertEqual(switch.model_id, 'DS5000')

# STEP 2: Run test - it should FAIL
docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning.test_reference_data_models.SwitchModelTestCase.test_switch_model_creation

# STEP 3: Implement minimal code to make it pass (GREEN)
# ... implement SwitchModel ...

# STEP 4: Run test - it should PASS
docker compose exec netbox python manage.py test [same test]

# STEP 5: Refactor while keeping tests green
```

**Never skip this workflow.** It's not optional.

### 2. Git Workflow

**Branch naming**: `diet-XXX-short-description`
- Example: `diet-001-reference-data-models`

**Commit messages**: `[DIET-XXX] Description`
- Example: `[DIET-001] Add SwitchModel with validation tests`
- Example: `[DIET-001] Implement SwitchPortGroup foreign key relationship`

**Commit frequency**: Commit after each TDD cycle (Red → Green → Refactor)

```bash
# After each feature/test completion
git add tests/test_topology_planning/test_reference_data_models.py
git add netbox_hedgehog/models/topology_planning/reference_data.py
git commit -m "[DIET-001] Add SwitchModel with creation and validation tests"
git push origin diet-001-reference-data-models
```

### 3. Code Quality Requirements

**Minimum Standards:**
- **95% test coverage** for new code
- **PEP 8 compliant** (120 char line limit)
- **Type hints** on function signatures
- **Docstrings** on all classes and non-trivial functions
- **Django conventions** followed (see CONTRIBUTORS.md)

**Before creating PR:**
```bash
# Run all tests
docker compose exec netbox python manage.py test netbox_hedgehog

# Check coverage
docker compose exec netbox coverage run --source='netbox_hedgehog' manage.py test
docker compose exec netbox coverage report

# Must show >= 95% for files you touched
```

### 4. File Organization

**CRITICAL: Keep DIET and Operational code separate**

```
netbox_hedgehog/
├── models/
│   ├── topology_planning/     # NEW - DIET models go here
│   │   ├── __init__.py
│   │   ├── reference_data.py  # SwitchModel, NICModel, etc.
│   │   └── topology_plans.py  # TopologyPlan, PlanServerClass, etc.
│   ├── operational/           # EXISTING - Don't modify unless necessary
│   │   └── crds.py            # Server, Switch, Connection (operational)
│   └── __init__.py
├── views/
│   ├── topology_planning/     # NEW - DIET views
│   └── operational/           # EXISTING - Don't touch
├── tests/
│   ├── test_topology_planning/  # NEW - Your tests here
│   └── test_operational/      # EXISTING
```

**DO NOT mix** DIET and operational features in the same files.

## Common Pitfalls to Avoid

### 1. Running Commands on Host Instead of Container

❌ **WRONG:**
```bash
cd /home/ubuntu/afewell-hh/hh-netbox-plugin
python manage.py test  # This will fail!
```

✅ **CORRECT:**
```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose exec netbox python manage.py test netbox_hedgehog
```

### 2. Skipping TDD Workflow

❌ **WRONG:** Writing implementation first, then adding tests
✅ **CORRECT:** Write failing test → Implement → Make test pass

### 3. Modifying Operational Code

❌ **WRONG:** Changing existing operational models/views for DIET features
✅ **CORRECT:** Create new DIET-specific files in `topology_planning/` directories

### 4. Forgetting Migrations

After adding/changing models:
```bash
# ALWAYS create migrations
docker compose exec netbox python manage.py makemigrations netbox_hedgehog

# ALWAYS apply them
docker compose exec netbox python manage.py migrate netbox_hedgehog

# ALWAYS commit migration files
git add netbox_hedgehog/migrations/000X_*.py
git commit -m "[DIET-001] Add migration for SwitchModel"
```

### 5. Not Registering Models in Admin

After creating models, ALWAYS register in `admin.py`:
```python
from django.contrib import admin
from .models.topology_planning import SwitchModel

@admin.register(SwitchModel)
class SwitchModelAdmin(admin.ModelAdmin):
    list_display = ['model_id', 'vendor', 'total_ports']
```

## Technical Patterns to Follow

### Django Model Pattern

```python
from django.db import models
from django.core.validators import MinValueValidator
from django.urls import reverse

class SwitchModel(models.Model):
    """Physical switch model specifications (reference data)"""

    # Fields with validation
    model_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique switch model identifier"
    )
    total_ports = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Total number of physical ports"
    )

    class Meta:
        ordering = ['vendor', 'model_id']
        verbose_name = "Switch Model"
        verbose_name_plural = "Switch Models"

    def __str__(self):
        return f"{self.vendor} {self.model_id}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:switchmodel', args=[self.pk])
```

### Test Pattern

```python
from django.test import TestCase
from django.core.exceptions import ValidationError
from netbox_hedgehog.models.topology_planning import SwitchModel

class SwitchModelTestCase(TestCase):
    """Test suite for SwitchModel"""

    def test_create_switch_model(self):
        """Test basic SwitchModel creation"""
        switch = SwitchModel.objects.create(
            model_id='DS5000',
            vendor='Dell',
            total_ports=64
        )
        self.assertEqual(switch.model_id, 'DS5000')
        self.assertEqual(switch.total_ports, 64)

    def test_str_representation(self):
        """Test __str__ returns readable name"""
        switch = SwitchModel.objects.create(
            model_id='DS5000',
            vendor='Dell',
            total_ports=64
        )
        self.assertIn('DS5000', str(switch))
        self.assertIn('Dell', str(switch))

    def test_total_ports_validation(self):
        """Test total_ports must be positive"""
        with self.assertRaises(ValidationError):
            switch = SwitchModel(
                model_id='TEST',
                vendor='Test',
                total_ports=-1
            )
            switch.full_clean()  # Triggers validation
```

## When You Get Stuck

### Check This Order:

1. **Read the error message carefully** - Django errors are usually helpful
2. **Check logs**: `docker compose logs netbox | tail -50`
3. **Verify container is running**: `docker compose ps`
4. **Test in Django shell**: `docker compose exec netbox python manage.py shell_plus`
5. **Review issue #83** for data model specifications
6. **Check CONTRIBUTORS.md** for troubleshooting section

### Ask for Help:

"I'm encountering [specific error]. I've tried [what you tried]. The error message says [exact error]. Can you help me understand what's wrong?"

**Be specific** - include error messages, file paths, what you were trying to do.

## Quick Reference Commands

```bash
# Navigate to NetBox Docker directory
cd /home/ubuntu/afewell-hh/netbox-docker

# Start environment
docker compose up -d

# Stop environment
docker compose down

# View logs
docker compose logs -f netbox

# Run tests
docker compose exec netbox python manage.py test netbox_hedgehog

# Create migrations
docker compose exec netbox python manage.py makemigrations netbox_hedgehog

# Apply migrations
docker compose exec netbox python manage.py migrate netbox_hedgehog

# Django shell (for debugging)
docker compose exec netbox python manage.py shell_plus

# Check plugin status
docker compose exec netbox python manage.py nbshell
>>> from django.conf import settings
>>> settings.PLUGINS

# Restart NetBox (if needed)
docker compose restart netbox
```

## Environment Variables

Available credentials (from `.env` file):
- `GITHUB_USERNAME` - For GitHub API access
- `GITHUB_TOKEN` - For authenticated GitHub operations
- NetBox admin: username `admin`, password `admin`

**IMPORTANT:** Never commit the `.env` file. It's in `.gitignore`.

## Current Sprint Goals (DIET)

From issue #84, the success criteria are:

- [ ] All core features have passing tests
- [ ] Can create a topology plan from scratch
- [ ] Can input server quantities and see auto-calculated switch requirements
- [ ] Can override calculated values
- [ ] Can generate valid Hedgehog wiring YAML
- [ ] UI is functional for all core workflows
- [ ] Documentation for using the tools

You are currently working on the **foundation** (issue #85) which blocks all other features.

## Remember

1. **Read issue #82, #83, #84, #85** before making changes
2. **Always use TDD** - tests first, implementation second
3. **Run commands in container** via `docker compose exec`
4. **Keep DIET separate** from operational code
5. **Commit frequently** with `[DIET-XXX]` format
6. **Ask for feedback** from other agents via the human
7. **95% test coverage** minimum
8. **Django conventions** matter - follow NetBox patterns

## Success Indicators

You're on the right track if:
- ✅ Tests are written before implementation
- ✅ All tests pass before committing
- ✅ Code coverage is >= 95%
- ✅ Models appear in Django admin
- ✅ Migrations apply cleanly
- ✅ Commit messages follow `[DIET-XXX]` format
- ✅ Files are organized in `topology_planning/` directories

You need to course-correct if:
- ❌ Implementing features without tests
- ❌ Modifying operational code files
- ❌ Running Django commands on host instead of container
- ❌ Test coverage below 95%
- ❌ Not asking for feedback on major decisions

---

**Most Important:** When in doubt, ask the human. They can coordinate with other agents and provide clarification.

Good luck, and remember: Test-driven development is not negotiable on this project!
