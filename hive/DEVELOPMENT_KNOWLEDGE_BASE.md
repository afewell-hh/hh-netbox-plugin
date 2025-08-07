# Hedgehog NetBox Plugin - Development Knowledge Base
*Synthesized from Hive Mind Agent Findings*

## Table of Contents
1. [Development Setup Guide](#development-setup-guide)
2. [Common Development Tasks](#common-development-tasks)
3. [Architecture Patterns](#architecture-patterns)
4. [Code Style Guidelines](#code-style-guidelines)
5. [Testing Guidelines](#testing-guidelines)
6. [Deployment Procedures](#deployment-procedures)
7. [Troubleshooting Guide](#troubleshooting-guide)

---

## Development Setup Guide

### Environment Configuration

#### Required Dependencies
```bash
# Core Dependencies (from setup.py analysis)
Django>=4.1,<5.0
netbox>=3.4.0
djangorestframework
django-mptt
PyYAML
requests
jsonschema

# Development Dependencies
pytest>=7.0
pytest-django
pytest-cov
black
flake8
mypy
```

#### Environment Variables
```bash
# Essential Configuration (.env template)
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost/netbox

# NetBox Integration
NETBOX_API_URL=http://localhost:8000
NETBOX_API_TOKEN=your-token-here

# Plugin Configuration
HEDGEHOG_ENABLE_FABRIC_WORKFLOWS=True
HEDGEHOG_ENABLE_PROGRESSIVE_DISCLOSURE=True
HEDGEHOG_ENABLE_DARK_THEME=True
```

#### Development Setup Commands
```bash
# Clone and setup
git clone <repository>
cd hedgehog-netbox-plugin

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -e .
pip install -r requirements-dev.txt

# Initialize database
python manage.py migrate
python manage.py collectstatic --noinput

# Run development server
python manage.py runserver
```

---

## Common Development Tasks

### CRUD Operations Pattern

#### Model Definition
```python
# models.py pattern
from django.db import models
from netbox.models import NetBoxModel

class MyModel(NetBoxModel):
    """Standard NetBox model pattern"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'My Models'
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:mymodel', args=[self.pk])
```

#### API Serializer
```python
# api/serializers.py pattern
from rest_framework import serializers
from netbox.api.serializers import NetBoxModelSerializer
from ..models import MyModel

class MyModelSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_hedgehog-api:mymodel-detail'
    )
    
    class Meta:
        model = MyModel
        fields = ['id', 'url', 'display', 'name', 'description', 'created', 'last_updated']
```

#### View Pattern
```python
# views.py pattern
from netbox.views import generic
from ..models import MyModel
from ..forms import MyModelForm, MyModelFilterForm
from ..tables import MyModelTable

class MyModelListView(generic.ObjectListView):
    queryset = MyModel.objects.all()
    table = MyModelTable
    filterset_class = MyModelFilterForm

class MyModelView(generic.ObjectView):
    queryset = MyModel.objects.all()

class MyModelEditView(generic.ObjectEditView):
    queryset = MyModel.objects.all()
    form = MyModelForm

class MyModelDeleteView(generic.ObjectDeleteView):
    queryset = MyModel.objects.all()
```

### URL Pattern Configuration
```python
# urls.py pattern (455+ URL patterns analyzed)
from django.urls import path
from . import views

app_name = 'netbox_hedgehog'

urlpatterns = [
    # List/Detail patterns
    path('mymodels/', views.MyModelListView.as_view(), name='mymodel_list'),
    path('mymodels/<int:pk>/', views.MyModelView.as_view(), name='mymodel'),
    path('mymodels/add/', views.MyModelEditView.as_view(), name='mymodel_add'),
    path('mymodels/<int:pk>/edit/', views.MyModelEditView.as_view(), name='mymodel_edit'),
    path('mymodels/<int:pk>/delete/', views.MyModelDeleteView.as_view(), name='mymodel_delete'),
    
    # Bulk operations
    path('mymodels/edit/', views.MyModelBulkEditView.as_view(), name='mymodel_bulk_edit'),
    path('mymodels/delete/', views.MyModelBulkDeleteView.as_view(), name='mymodel_bulk_delete'),
]
```

### Template Patterns
```django
<!-- Standard template structure (80+ templates) -->
{% extends 'generic/object.html' %}
{% load render_table from django_tables2 %}
{% load buttons %}

{% block title %}{{ object }}{% endblock %}

{% block breadcrumbs %}
  {{ block.super }}
  <li class="breadcrumb-item"><a href="{% url 'plugins:netbox_hedgehog:mymodel_list' %}">My Models</a></li>
{% endblock %}

{% block content %}
  <div class="row">
    <div class="col col-md-6">
      <div class="card">
        <h5 class="card-header">My Model</h5>
        <div class="card-body">
          <!-- Object details -->
        </div>
      </div>
    </div>
  </div>
{% endblock %}
```

---

## Architecture Patterns

### Plugin Architecture
```python
# __init__.py - Plugin configuration
from netbox.plugins import PluginConfig

class HedgehogConfig(PluginConfig):
    name = 'netbox_hedgehog'
    verbose_name = 'Hedgehog'
    description = 'NetBox plugin for Hedgehog fabric management'
    version = '1.0.0'
    author = 'Your Name'
    author_email = 'your@email.com'
    base_url = 'hedgehog'
    required_settings = []
    default_settings = {
        'enable_fabric_workflows': True,
        'enable_progressive_disclosure': True,
    }

config = HedgehogConfig
```

### Service Layer Pattern
```python
# services.py - Business logic layer
from typing import Dict, List, Optional
from django.db import transaction
from .models import MyModel

class MyModelService:
    """Service layer for business logic"""
    
    @staticmethod
    @transaction.atomic
    def create_with_validation(data: Dict) -> MyModel:
        """Create model with business logic validation"""
        # Business logic validation
        if MyModel.objects.filter(name=data['name']).exists():
            raise ValueError("Name already exists")
        
        return MyModel.objects.create(**data)
    
    @staticmethod
    def bulk_update(queryset, updates: Dict) -> int:
        """Bulk update with validation"""
        count = queryset.count()
        queryset.update(**updates)
        return count
```

### GitOps Workflow Integration
```python
# gitops/workflows.py
from typing import Dict, Any
import yaml
from pathlib import Path

class GitOpsWorkflow:
    """GitOps workflow management"""
    
    def __init__(self, workflow_path: Path):
        self.workflow_path = workflow_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load workflow configuration"""
        with open(self.workflow_path) as f:
            return yaml.safe_load(f)
    
    def execute_workflow(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute GitOps workflow"""
        steps = self.config.get('steps', [])
        results = {}
        
        for step in steps:
            step_name = step['name']
            results[step_name] = self._execute_step(step, context)
        
        return results
    
    def _execute_step(self, step: Dict, context: Dict) -> Any:
        """Execute individual workflow step"""
        # Implementation based on step type
        pass
```

---

## Code Style Guidelines

### Python Code Style (Black + Flake8)
```python
# Standard imports order
import os
import sys
from typing import Dict, List, Optional

import django
from django.db import models
from django.urls import reverse

from netbox.models import NetBoxModel
from netbox.plugins import PluginConfigBase

# Local imports
from .constants import MY_CONSTANTS
from .utils import my_utility_function


class MyClass:
    """Class with proper docstring.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    """
    
    def __init__(self, param1: str, param2: Optional[int] = None):
        self.param1 = param1
        self.param2 = param2
    
    def my_method(self) -> Dict[str, Any]:
        """Method with type hints and docstring."""
        return {"key": "value"}
```

### Django Best Practices
```python
# Use Django ORM efficiently
# Good - single query with select_related
devices = Device.objects.select_related('device_type', 'site').all()

# Good - prefetch_related for many-to-many
devices = Device.objects.prefetch_related('tags').all()

# Good - bulk operations
Device.objects.bulk_create([
    Device(name=f'device-{i}', device_type=device_type)
    for i in range(100)
])

# Good - use F expressions for database-level operations
from django.db.models import F
Device.objects.update(position=F('position') + 1)
```

### Frontend Guidelines
```css
/* CSS Architecture (from 71 CSS files analysis) */
/* Use BEM methodology */
.hedgehog-component {}
.hedgehog-component__element {}
.hedgehog-component__element--modifier {}

/* Progressive disclosure pattern */
.progressive-disclosure {
    --disclosure-transition: 0.3s ease-in-out;
}

.progressive-disclosure__content {
    max-height: 0;
    overflow: hidden;
    transition: max-height var(--disclosure-transition);
}

.progressive-disclosure__content--expanded {
    max-height: 1000px; /* Large value for animation */
}

/* Dark theme support */
:root {
    --hedgehog-primary: #007bff;
    --hedgehog-secondary: #6c757d;
    --hedgehog-background: #ffffff;
    --hedgehog-text: #212529;
}

[data-theme="dark"] {
    --hedgehog-primary: #0d6efd;
    --hedgehog-secondary: #6c757d;
    --hedgehog-background: #212529;
    --hedgehog-text: #ffffff;
}
```

```javascript
// JavaScript patterns
class HedgehogComponent {
    constructor(element, options = {}) {
        this.element = element;
        this.options = { ...this.defaults, ...options };
        this.init();
    }
    
    get defaults() {
        return {
            autoInit: true,
            theme: 'light'
        };
    }
    
    init() {
        this.bindEvents();
        if (this.options.autoInit) {
            this.render();
        }
    }
    
    bindEvents() {
        this.element.addEventListener('click', this.handleClick.bind(this));
    }
    
    handleClick(event) {
        event.preventDefault();
        // Handle click logic
    }
    
    render() {
        // Render component
    }
}
```

---

## Testing Guidelines

### Test Structure (164 test files analyzed)
```python
# Standard test structure
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from netbox.testing import APITestCase

from ..models import MyModel

User = get_user_model()

class MyModelTestCase(TestCase):
    """Test suite for MyModel"""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for the entire test class"""
        cls.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
    
    def setUp(self):
        """Set up test data for each test method"""
        self.model_instance = MyModel.objects.create(
            name='Test Model',
            description='Test description'
        )
    
    def test_model_creation(self):
        """Test model creation"""
        self.assertEqual(self.model_instance.name, 'Test Model')
        self.assertEqual(str(self.model_instance), 'Test Model')
    
    def test_model_validation(self):
        """Test model validation"""
        with self.assertRaises(ValidationError):
            MyModel.objects.create(name='')  # Empty name should fail
```

### API Testing Pattern
```python
class MyModelAPITestCase(APITestCase):
    """API test suite"""
    
    def setUp(self):
        super().setUp()
        self.model_data = {
            'name': 'Test Model',
            'description': 'Test description'
        }
    
    def test_create_model_via_api(self):
        """Test model creation via API"""
        url = reverse('plugins-api:netbox_hedgehog-api:mymodel-list')
        response = self.client.post(url, self.model_data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['name'], 'Test Model')
    
    def test_list_models_via_api(self):
        """Test model listing via API"""
        MyModel.objects.create(**self.model_data)
        url = reverse('plugins-api:netbox_hedgehog-api:mymodel-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
```

### GUI Testing Pattern (71 GUI tests)
```python
from django.test import LiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class GUITestCase(LiveServerTestCase):
    """GUI testing with Selenium"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = webdriver.Chrome()  # or Firefox()
        cls.selenium.implicitly_wait(10)
    
    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()
    
    def test_model_list_page(self):
        """Test model list page functionality"""
        self.selenium.get(f'{self.live_server_url}/plugins/hedgehog/mymodels/')
        
        # Wait for page to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'table'))
        )
        
        # Test add button
        add_button = self.selenium.find_element(By.LINK_TEXT, 'Add')
        self.assertTrue(add_button.is_displayed())
```

### Performance Testing
```python
import time
from django.test import TestCase
from django.test.utils import override_settings

class PerformanceTestCase(TestCase):
    """Performance testing"""
    
    def test_bulk_creation_performance(self):
        """Test bulk creation performance"""
        start_time = time.time()
        
        # Create 1000 objects
        MyModel.objects.bulk_create([
            MyModel(name=f'model-{i}')
            for i in range(1000)
        ])
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Assert reasonable performance (adjust threshold as needed)
        self.assertLess(execution_time, 5.0, "Bulk creation took too long")
    
    @override_settings(DEBUG=False)
    def test_query_performance(self):
        """Test query performance"""
        # Create test data
        for i in range(100):
            MyModel.objects.create(name=f'model-{i}')
        
        start_time = time.time()
        
        # Perform complex query
        results = list(MyModel.objects.select_related().all()[:50])
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        self.assertLess(execution_time, 1.0, "Query took too long")
        self.assertEqual(len(results), 50)
```

---

## Deployment Procedures

### Docker Configuration
```dockerfile
# Dockerfile pattern
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash netbox
RUN chown -R netbox:netbox /app
USER netbox

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Start command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

### Docker Compose Configuration
```yaml
# docker-compose.yml
version: '3.8'

services:
  netbox:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgresql://netbox:${DB_PASSWORD}@postgres:5432/netbox
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - ./media:/app/media
      - ./static:/app/static
    restart: unless-stopped

  postgres:
    image: postgres:14
    environment:
      - POSTGRES_DB=netbox
      - POSTGRES_USER=netbox
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Environment Configuration
```bash
# Production environment setup
# .env.production
DEBUG=False
SECRET_KEY=your-super-secret-production-key
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/netbox_prod

# Cache
REDIS_URL=redis://localhost:6379/0

# Email (optional)
EMAIL_HOST=smtp.your-email-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@domain.com
EMAIL_HOST_PASSWORD=your-email-password

# Static files
STATIC_ROOT=/var/www/netbox/static
MEDIA_ROOT=/var/www/netbox/media

# Security
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

### Deployment Script
```bash
#!/bin/bash
# deploy.sh - Production deployment script

set -e  # Exit on any error

echo "Starting deployment..."

# Pull latest code
git pull origin main

# Build Docker images
docker-compose build --no-cache

# Run database migrations
docker-compose run --rm netbox python manage.py migrate

# Collect static files
docker-compose run --rm netbox python manage.py collectstatic --noinput

# Run tests
docker-compose run --rm netbox python manage.py test

# Start services
docker-compose up -d

# Health check
sleep 10
if curl -f http://localhost:8000/health/; then
    echo "Deployment successful!"
else
    echo "Deployment failed - health check failed"
    exit 1
fi
```

---

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. Plugin Not Loading
```bash
# Check plugin installation
pip list | grep netbox-hedgehog

# Check Django settings
python manage.py shell -c "from django.conf import settings; print(settings.INSTALLED_APPS)"

# Check plugin configuration
python manage.py shell -c "from netbox.plugins import plugins; print(plugins)"
```

#### 2. Database Migration Issues
```bash
# Check migration status
python manage.py showmigrations netbox_hedgehog

# Create migration if needed
python manage.py makemigrations netbox_hedgehog

# Apply migrations with verbose output
python manage.py migrate netbox_hedgehog --verbosity=2

# Reset migrations (development only)
python manage.py migrate netbox_hedgehog zero
```

#### 3. Static Files Not Loading
```bash
# Collect static files
python manage.py collectstatic --noinput

# Check static files configuration
python manage.py shell -c "from django.conf import settings; print(settings.STATIC_ROOT, settings.STATIC_URL)"

# Check file permissions
ls -la /path/to/static/files/
```

#### 4. API Issues
```bash
# Test API endpoint
curl -H "Authorization: Token YOUR_TOKEN" http://localhost:8000/api/plugins/hedgehog/

# Check API routing
python manage.py show_urls | grep hedgehog

# Debug API serialization
python manage.py shell
>>> from netbox_hedgehog.api.serializers import MyModelSerializer
>>> serializer = MyModelSerializer()
>>> print(serializer.fields)
```

#### 5. Performance Issues
```bash
# Enable Django debug toolbar
DEBUG=True
INSTALLED_APPS += ['debug_toolbar']

# Check database queries
python manage.py shell
>>> from django.db import connection
>>> connection.queries

# Profile view performance
python -m cProfile manage.py runserver
```

### Debugging Commands
```bash
# Django shell with useful imports
python manage.py shell_plus

# Run specific test with verbose output
python manage.py test netbox_hedgehog.tests.test_models.MyModelTestCase.test_creation -v 2

# Check plugin health
python manage.py check --deploy

# Validate models
python manage.py validate

# Show all URLs
python manage.py show_urls

# Clear cache
python manage.py clear_cache
```

### Log Analysis
```python
# settings.py - Enhanced logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': '/path/to/netbox.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'netbox_hedgehog': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

---

## Quick Reference

### Useful Commands
```bash
# Development
python manage.py runserver
python manage.py shell_plus
python manage.py test
python manage.py makemigrations
python manage.py migrate

# Production
python manage.py check --deploy
python manage.py collectstatic --noinput
docker-compose up -d
docker-compose logs -f netbox

# Debugging
python manage.py validate
python manage.py show_urls
python -m pytest -v
black --check .
flake8 .
```

### Key File Locations
```
netbox_hedgehog/
├── __init__.py              # Plugin configuration
├── models.py               # Data models
├── views.py                # View classes
├── urls.py                 # URL routing
├── forms.py                # Django forms
├── tables.py               # Django tables
├── api/                    # API components
│   ├── serializers.py      # API serializers
│   ├── views.py           # API views
│   └── urls.py            # API URLs
├── templates/              # Django templates
├── static/                 # CSS, JS, images
└── tests/                  # Test files
```

---

*This knowledge base is synthesized from comprehensive analysis of 455+ URL patterns, 80+ templates, 164 test files, and extensive architecture analysis by the Hive Mind swarm.*