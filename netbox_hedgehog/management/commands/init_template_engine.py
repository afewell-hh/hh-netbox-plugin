"""
Django management command to initialize the Configuration Template Engine.

This command sets up the template engine infrastructure including:
- Creating default directory structure
- Installing default templates
- Setting up validation schemas
- Running initial validation tests
"""

import logging
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from ...services.configuration_template_engine import ConfigurationTemplateEngine
from ...services.template_manager import create_default_templates
from ...services.schema_validator import create_default_schemas
from ...models.fabric import HedgehogFabric

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize the Configuration Template Engine with default templates and schemas'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--base-directory',
            type=str,
            help='Base directory for template engine (default: from settings)',
        )
        
        parser.add_argument(
            '--fabric',
            type=str,
            help='Initialize for specific fabric only (by name)',
        )
        
        parser.add_argument(
            '--create-defaults',
            action='store_true',
            help='Create default templates and schemas',
        )
        
        parser.add_argument(
            '--validate-setup',
            action='store_true',
            help='Validate the setup after initialization',
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force initialization even if directories exist',
        )
    
    def handle(self, *args, **options):
        verbosity = options['verbosity']
        if verbosity >= 2:
            logging.basicConfig(level=logging.DEBUG)
        elif verbosity >= 1:
            logging.basicConfig(level=logging.INFO)
        
        try:
            # Determine base directory
            base_directory = options.get('base_directory')
            if not base_directory:
                base_directory = getattr(settings, 'HEDGEHOG_CONFIG_TEMPLATE_BASE', '/tmp/hedgehog-templates')
            
            base_path = Path(base_directory)
            
            self.stdout.write(f"Initializing Configuration Template Engine at: {base_path}")
            
            # Check if specific fabric is requested
            fabric = None
            if options.get('fabric'):
                try:
                    fabric = HedgehogFabric.objects.get(name=options['fabric'])
                    self.stdout.write(f"Initializing for fabric: {fabric.name}")
                except HedgehogFabric.DoesNotExist:
                    raise CommandError(f"Fabric not found: {options['fabric']}")
            
            # Initialize directory structure
            self._initialize_directories(base_path, fabric, options.get('force', False))
            
            # Create default templates and schemas if requested
            if options.get('create_defaults'):
                self._create_defaults(base_path)
            
            # Initialize template engine
            if fabric:
                engines = [ConfigurationTemplateEngine(fabric)]
                self.stdout.write(f"Template engine initialized for fabric: {fabric.name}")
            else:
                # Initialize for all fabrics
                engines = []
                for fabric_obj in HedgehogFabric.objects.all():
                    engine = ConfigurationTemplateEngine(fabric_obj)
                    engines.append(engine)
                    
                self.stdout.write(f"Template engine initialized for {len(engines)} fabrics")
            
            # Validate setup if requested
            if options.get('validate_setup'):
                self._validate_setup(engines)
            
            self.stdout.write(
                self.style.SUCCESS("Configuration Template Engine initialization completed successfully!")
            )
            
        except Exception as e:
            logger.exception("Template engine initialization failed")
            raise CommandError(f"Initialization failed: {str(e)}")
    
    def _initialize_directories(self, base_path: Path, fabric: HedgehogFabric = None, force: bool = False):
        """Initialize directory structure."""
        self.stdout.write("Creating directory structure...")
        
        if fabric:
            fabric_base = base_path / 'fabrics' / fabric.name
            directories = [
                fabric_base / 'templates',
                fabric_base / 'templates' / 'includes',
                fabric_base / 'generated',
                fabric_base / 'schemas',
                fabric_base / 'metadata',
                fabric_base / 'versions',
            ]
        else:
            directories = [
                base_path / 'global' / 'templates',
                base_path / 'global' / 'templates' / 'includes',
                base_path / 'global' / 'generated',
                base_path / 'global' / 'schemas',
                base_path / 'global' / 'metadata',
                base_path / 'global' / 'versions',
                base_path / 'fabrics',
            ]
        
        for directory in directories:
            if directory.exists() and not force:
                self.stdout.write(f"Directory already exists: {directory}")
            else:
                directory.mkdir(parents=True, exist_ok=True)
                self.stdout.write(f"Created directory: {directory}")
    
    def _create_defaults(self, base_path: Path):
        """Create default templates and schemas."""
        self.stdout.write("Creating default templates and schemas...")
        
        # Create default templates
        templates_dir = base_path / 'global' / 'templates'
        template_results = create_default_templates(base_path / 'global')
        
        if template_results['created']:
            for template_name in template_results['created']:
                self.stdout.write(f"Created template: {template_name}")
        
        if template_results['errors']:
            for error in template_results['errors']:
                self.stdout.write(self.style.WARNING(f"Template creation error: {error}"))
        
        # Create default schemas
        schemas_dir = base_path / 'global' / 'schemas'
        schema_results = create_default_schemas(schemas_dir)
        
        if schema_results['created']:
            for schema_name in schema_results['created']:
                self.stdout.write(f"Created schema: {schema_name}")
        
        if schema_results['errors']:
            for error in schema_results['errors']:
                self.stdout.write(self.style.WARNING(f"Schema creation error: {error}"))
    
    def _validate_setup(self, engines: list):
        """Validate the template engine setup."""
        self.stdout.write("Validating template engine setup...")
        
        for engine in engines:
            fabric_name = engine.fabric.name if engine.fabric else 'global'
            self.stdout.write(f"Validating engine for fabric: {fabric_name}")
            
            try:
                # Get engine status
                status = engine.get_engine_status()
                
                # Check services
                services_ok = all(status['services'].values())
                if services_ok:
                    self.stdout.write(f"✓ All services initialized for {fabric_name}")
                else:
                    missing_services = [k for k, v in status['services'].items() if not v]
                    self.stdout.write(
                        self.style.WARNING(f"✗ Missing services for {fabric_name}: {missing_services}")
                    )
                
                # Check templates
                templates = engine.template_manager.list_templates()
                if templates:
                    self.stdout.write(f"✓ Found {len(templates)} templates for {fabric_name}")
                else:
                    self.stdout.write(
                        self.style.WARNING(f"✗ No templates found for {fabric_name}")
                    )
                
                # Validate templates
                validation_results = engine.validate_templates()
                valid_count = len(validation_results['valid_templates'])
                invalid_count = len(validation_results['invalid_templates'])
                
                if invalid_count == 0:
                    self.stdout.write(f"✓ All {valid_count} templates are valid for {fabric_name}")
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠ {invalid_count} invalid templates found for {fabric_name} "
                            f"({valid_count} valid)"
                        )
                    )
                    
                    for invalid_template in validation_results['invalid_templates']:
                        self.stdout.write(f"  - {invalid_template['name']}: {len(invalid_template['errors'])} errors")
                
                # Check schemas
                schemas = engine.schema_validator.get_available_schemas()
                if schemas:
                    self.stdout.write(f"✓ Found {len(schemas)} validation schemas for {fabric_name}")
                else:
                    self.stdout.write(
                        self.style.WARNING(f"✗ No validation schemas found for {fabric_name}")
                    )
                
                # Test configuration generation if fabric has resources
                if engine.fabric and engine.fabric.gitops_resources.exists():
                    self.stdout.write(f"Testing configuration generation for {fabric_name}...")
                    
                    try:
                        result = engine.generate_fabric_configuration(force_regenerate=False)
                        
                        if result.success:
                            self.stdout.write(
                                f"✓ Configuration generation test successful for {fabric_name}: "
                                f"{len(result.files_generated + result.files_updated)} files"
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"⚠ Configuration generation test failed for {fabric_name}: "
                                    f"{result.error_message}"
                                )
                            )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"⚠ Configuration generation test error for {fabric_name}: {str(e)}"
                            )
                        )
                else:
                    self.stdout.write(f"ℹ No resources found for {fabric_name}, skipping generation test")
                
                self.stdout.write("")
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Validation failed for {fabric_name}: {str(e)}")
                )
        
        self.stdout.write("Validation completed.")
    
    def _check_dependencies(self):
        """Check if required dependencies are available."""
        try:
            import jinja2
            import jsonschema
            import yaml
            self.stdout.write("✓ All required dependencies are available")
        except ImportError as e:
            raise CommandError(f"Missing required dependency: {str(e)}")
    
    def _show_usage_examples(self):
        """Show usage examples."""
        self.stdout.write("""
Usage Examples:

# Initialize with defaults for all fabrics
python manage.py init_template_engine --create-defaults --validate-setup

# Initialize for specific fabric only
python manage.py init_template_engine --fabric my-fabric --create-defaults

# Initialize with custom base directory
python manage.py init_template_engine --base-directory /custom/path --create-defaults

# Force re-initialization
python manage.py init_template_engine --force --create-defaults --validate-setup

# Validate existing setup
python manage.py init_template_engine --validate-setup
        """)


# Example usage in views or other Django code:
"""
from django.core.management import call_command

# Initialize template engine programmatically
call_command('init_template_engine', create_defaults=True, validate_setup=True)

# Initialize for specific fabric
call_command('init_template_engine', fabric='production', create_defaults=True)
"""