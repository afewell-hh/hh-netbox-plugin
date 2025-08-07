# Hedgehog NetBox Plugin - Quick Reference Guide
*Essential commands and patterns for daily development*

## 🚀 Quick Setup
```bash
# Clone and setup environment
git clone <repository> && cd hedgehog-netbox-plugin
python -m venv venv && source venv/bin/activate
pip install -e . && pip install -r requirements-dev.txt

# Development server
python manage.py migrate && python manage.py runserver
```

## 📝 Common Tasks

### Create New Model
```python
# 1. Add to models.py
class MyModel(NetBoxModel):
    name = models.CharField(max_length=100, unique=True)
    
# 2. Create migration
python manage.py makemigrations netbox_hedgehog

# 3. Apply migration
python manage.py migrate
```

### Add API Endpoint
```python
# 1. Add serializer (api/serializers.py)
class MyModelSerializer(NetBoxModelSerializer):
    class Meta:
        model = MyModel
        fields = '__all__'

# 2. Add viewset (api/views.py)
class MyModelViewSet(NetBoxModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MyModelSerializer

# 3. Add to URLs (api/urls.py)
router.register('mymodels', MyModelViewSet)
```

### Create Form & Views
```python
# 1. Form (forms.py)
class MyModelForm(NetBoxModelForm):
    class Meta:
        model = MyModel
        fields = ['name', 'description']

# 2. Views (views.py)
class MyModelListView(generic.ObjectListView):
    queryset = MyModel.objects.all()
    table = MyModelTable

# 3. URLs (urls.py)
path('mymodels/', views.MyModelListView.as_view(), name='mymodel_list'),
```

## 🧪 Testing Commands
```bash
# Run all tests
python manage.py test

# Specific test file
python manage.py test netbox_hedgehog.tests.test_models

# With coverage
pytest --cov=netbox_hedgehog

# GUI tests
pytest netbox_hedgehog/tests/gui/
```

## 🐳 Docker Commands
```bash
# Build and run
docker-compose build
docker-compose up -d

# View logs
docker-compose logs -f netbox

# Execute commands
docker-compose exec netbox python manage.py migrate
```

## 🔧 Debugging
```bash
# Django shell with models loaded
python manage.py shell_plus

# Check plugin installation
python -c "from netbox.plugins import plugins; print(plugins)"

# Validate configuration
python manage.py check --deploy

# Show all URLs
python manage.py show_urls | grep hedgehog
```

## 📊 Key Patterns

### Model Pattern
```python
from netbox.models import NetBoxModel

class MyModel(NetBoxModel):
    name = models.CharField(max_length=100, unique=True)
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:mymodel', args=[self.pk])
```

### View Pattern
```python
from netbox.views import generic

class MyModelListView(generic.ObjectListView):
    queryset = MyModel.objects.all()
    table = MyModelTable
    filterset_class = MyModelFilterForm
```

### API Pattern
```python
from netbox.api.serializers import NetBoxModelSerializer
from netbox.api.viewsets import NetBoxModelViewSet

class MyModelSerializer(NetBoxModelSerializer):
    class Meta:
        model = MyModel
        fields = '__all__'

class MyModelViewSet(NetBoxModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MyModelSerializer
```

### Test Pattern
```python
from django.test import TestCase

class MyModelTestCase(TestCase):
    def setUp(self):
        self.model = MyModel.objects.create(name='Test')
    
    def test_creation(self):
        self.assertEqual(self.model.name, 'Test')
```

## 📁 File Structure
```
netbox_hedgehog/
├── __init__.py          # Plugin config
├── models.py           # Data models
├── views.py            # Django views
├── urls.py             # URL routing
├── forms.py            # Django forms
├── tables.py           # Django tables
├── api/                # REST API
├── templates/          # HTML templates
├── static/             # CSS/JS/Images
└── tests/              # Test suite
```

## 🔑 Environment Variables
```bash
# Essential .env variables
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost/netbox
NETBOX_API_TOKEN=your-token
```

## 🚨 Troubleshooting
```bash
# Plugin not loading
pip list | grep netbox-hedgehog

# Migration issues
python manage.py showmigrations netbox_hedgehog

# Static files
python manage.py collectstatic --noinput

# Clear cache
python manage.py clear_cache
```

---
*Generated from comprehensive Hive Mind analysis*