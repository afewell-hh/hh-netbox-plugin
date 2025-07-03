# Development Guide

## Setup Development Environment

### Prerequisites
- Python 3.8+
- NetBox 3.4+ (for development)
- Kubernetes cluster (for testing)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd hedgehog-netbox-plugin
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -e .
```

4. Install pre-commit hooks:
```bash
pre-commit install
```

## Development Workflow

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=netbox_hedgehog

# Run specific test file
pytest tests/test_models.py
```

### Code Formatting
```bash
# Format code with Black
black netbox_hedgehog/

# Check code style
flake8 netbox_hedgehog/

# Sort imports
isort netbox_hedgehog/
```

### Database Migrations
```bash
# Create new migration
python manage.py makemigrations netbox_hedgehog

# Apply migrations
python manage.py migrate netbox_hedgehog
```

## Project Structure

```
netbox_hedgehog/
├── __init__.py           # Plugin configuration
├── choices.py            # Choice sets for fields
├── navigation.py         # Navigation menu
├── urls.py              # URL routing
├── models/              # Data models
│   ├── __init__.py
│   ├── fabric.py        # HedgehogFabric model
│   ├── base.py          # BaseCRD model
│   ├── vpc_api.py       # VPC API models
│   └── wiring_api.py    # Wiring API models
├── views/               # View classes
├── forms/               # Form classes
├── tables/              # Table classes
├── api/                 # REST API
├── utils/               # Utility functions
├── templates/           # HTML templates
├── static/              # CSS/JS files
└── migrations/          # Database migrations
```

## Adding New Features

### Adding a New CRD Type

1. **Define the model** in the appropriate file (`vpc_api.py` or `wiring_api.py`)
2. **Create database migration** with `makemigrations`
3. **Add views** for list, detail, create, edit, delete operations
4. **Create forms** for data input and validation
5. **Add table** for displaying lists of objects
6. **Update navigation** to include new menu items
7. **Add URL patterns** to route requests
8. **Create API endpoints** for REST access
9. **Add tests** for all new functionality

### Example: Adding ExternalAttachment

```python
# models/vpc_api.py
class ExternalAttachment(BaseCRD):
    """Hedgehog ExternalAttachment CRD"""
    
    class Meta:
        verbose_name = "External Attachment"
        verbose_name_plural = "External Attachments"
    
    def __str__(self):
        return f"{self.name} ({self.fabric})"
```

## Testing

### Unit Tests
Place tests in `tests/` directory:
- `test_models.py` - Model tests
- `test_views.py` - View tests
- `test_api.py` - API tests
- `test_utils.py` - Utility tests

### Integration Tests
- Test Kubernetes integration with mock clusters
- Test form validation and submission
- Test API endpoints

### Manual Testing
1. Install plugin in development NetBox instance
2. Create test fabric configurations
3. Test all CRUD operations
4. Verify Kubernetes synchronization

## Contributing

1. Create feature branch from `main`
2. Make changes following code style guidelines
3. Add tests for new functionality
4. Update documentation as needed
5. Submit pull request

## Debugging

### Enable Debug Mode
```python
# In NetBox settings
DEBUG = True
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'netbox_hedgehog': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### Common Issues
- **Import errors**: Check PYTHONPATH and virtual environment
- **Migration errors**: Ensure database is accessible
- **Kubernetes connection**: Verify kubeconfig and cluster access
- **Template errors**: Check template syntax and context variables