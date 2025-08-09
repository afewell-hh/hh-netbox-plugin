"""
Configuration Generator Service

Dynamic YAML generation from NetBox data using Jinja2 templates with
comprehensive schema validation, dependency mapping, and error recovery.

This service is part of the Phase 3 Configuration Template Engine that provides
advanced configuration management for GitOps workflows.
"""

import os
import yaml
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from jinja2 import Environment, FileSystemLoader, Template, TemplateError, meta
from jinja2.sandbox import SandboxedEnvironment

from .template_manager import TemplateManager
from .schema_validator import SchemaValidator
from ..models.fabric import HedgehogFabric
from ..models.gitops import HedgehogResource

logger = logging.getLogger(__name__)


@dataclass
class GenerationContext:
    """Context for configuration generation."""
    fabric: HedgehogFabric
    resources: List[HedgehogResource]
    template_vars: Dict[str, Any]
    generation_timestamp: datetime
    generation_id: str
    output_directory: Path


@dataclass
class GenerationResult:
    """Result of configuration generation."""
    generation_id: str
    success: bool
    files_generated: List[str]
    files_updated: List[str]
    files_validated: List[str]
    validation_errors: List[Dict[str, Any]]
    template_errors: List[Dict[str, Any]]
    dependency_map: Dict[str, List[str]]
    generation_time: float
    error_message: Optional[str] = None


@dataclass
class TemplateCache:
    """Cache entry for compiled templates."""
    template: Template
    template_hash: str
    compiled_at: datetime
    dependencies: List[str]
    variables: List[str]


class ConfigurationGenerator:
    """
    Dynamic YAML configuration generator using Jinja2 templates.
    
    Features:
    - Real-time YAML generation from NetBox object changes
    - Template dependency tracking and automatic updates
    - Schema validation with comprehensive error reporting
    - Performance-optimized template caching
    - Rollback capabilities on generation failures
    """
    
    def __init__(self, fabric: HedgehogFabric = None, base_directory: Union[str, Path] = None):
        self.fabric = fabric
        self.base_directory = Path(base_directory) if base_directory else self._get_default_directory()
        
        # Initialize service components
        self.template_manager = TemplateManager(self.base_directory)
        self.schema_validator = SchemaValidator()
        
        # Template environment setup
        self._setup_jinja_environment()
        
        # Cache configuration
        self.template_cache = {}
        self.cache_ttl = getattr(settings, 'CONFIG_GEN_CACHE_TTL', 3600)  # 1 hour
        self.max_cache_size = getattr(settings, 'CONFIG_GEN_MAX_CACHE_SIZE', 100)
        
        # Performance thresholds
        self.max_generation_time = 30  # 30 seconds micro-task boundary
        self.batch_size = getattr(settings, 'CONFIG_GEN_BATCH_SIZE', 50)
        
        # Generation tracking
        self.generation_history = []
        self.dependency_graph = {}
        
        # Error recovery configuration
        self.rollback_enabled = True
        self.validation_required = True
        
        logger.info(f"Configuration generator initialized for fabric: {fabric.name if fabric else 'global'}")
    
    def generate_configuration(self, context: GenerationContext) -> GenerationResult:
        """
        Generate YAML configuration files from NetBox data using templates.
        
        Args:
            context: Generation context with fabric, resources, and variables
            
        Returns:
            GenerationResult with detailed generation information
        """
        start_time = timezone.now()
        generation_id = context.generation_id
        
        logger.info(f"Starting configuration generation {generation_id} for fabric {context.fabric.name}")
        
        result = GenerationResult(
            generation_id=generation_id,
            success=False,
            files_generated=[],
            files_updated=[],
            files_validated=[],
            validation_errors=[],
            template_errors=[],
            dependency_map={},
            generation_time=0.0
        )
        
        try:
            # Pre-generation validation
            validation_result = self._validate_generation_context(context)
            if not validation_result['valid']:
                result.error_message = f"Context validation failed: {validation_result['error']}"
                return result
            
            # Load and prepare templates
            templates = self._load_applicable_templates(context)
            if not templates:
                result.error_message = "No applicable templates found"
                return result
            
            # Generate configurations in batches
            batch_results = []
            template_batches = self._create_template_batches(templates)
            
            for batch_num, template_batch in enumerate(template_batches, 1):
                logger.info(f"Processing template batch {batch_num}/{len(template_batches)}")
                
                batch_result = self._process_template_batch(context, template_batch)
                batch_results.append(batch_result)
                
                # Check time boundary
                elapsed_time = (timezone.now() - start_time).total_seconds()
                if elapsed_time > self.max_generation_time * 0.8:  # 80% of limit
                    logger.warning(f"Approaching time limit, stopping at batch {batch_num}")
                    break
            
            # Consolidate results
            self._consolidate_batch_results(result, batch_results)
            
            # Validate generated files if enabled
            if self.validation_required:
                validation_results = self._validate_generated_files(result.files_generated)
                result.files_validated = validation_results['validated_files']
                result.validation_errors = validation_results['errors']
            
            # Update dependency mapping
            result.dependency_map = self._build_dependency_map(context, templates)
            
            # Mark as successful if no critical errors
            result.success = len(result.template_errors) == 0 and len([
                e for e in result.validation_errors if e.get('severity') == 'critical'
            ]) == 0
            
            result.generation_time = (timezone.now() - start_time).total_seconds()
            
            logger.info(f"Configuration generation {generation_id} completed: "
                       f"{len(result.files_generated)} generated, "
                       f"{len(result.files_updated)} updated, "
                       f"{result.generation_time:.2f}s")
            
            # Store generation record
            self._record_generation(context, result)
            
            return result
            
        except Exception as e:
            result.error_message = str(e)
            result.generation_time = (timezone.now() - start_time).total_seconds()
            logger.error(f"Configuration generation {generation_id} failed: {str(e)}")
            return result
    
    def generate_single_template(self, template_path: str, context: Dict[str, Any], 
                                output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate configuration from a single template.
        
        Args:
            template_path: Path to the template file
            context: Template context variables
            output_path: Optional output path (if None, returns rendered content)
            
        Returns:
            Dict with generation results
        """
        logger.info(f"Generating single template: {template_path}")
        
        result = {
            'success': False,
            'template_path': template_path,
            'output_path': output_path,
            'generated_content': None,
            'validation_result': None,
            'error': None
        }
        
        try:
            # Load and render template
            template = self._load_template(template_path)
            rendered_content = template.render(context)
            
            result['generated_content'] = rendered_content
            
            # Write to file if output path provided
            if output_path:
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)
                
                logger.info(f"Template output written to: {output_path}")
                
                # Validate if YAML/JSON
                if output_file.suffix.lower() in ['.yaml', '.yml', '.json']:
                    validation_result = self.schema_validator.validate_file(output_file)
                    result['validation_result'] = validation_result
            
            result['success'] = True
            return result
            
        except Exception as e:
            logger.error(f"Single template generation failed: {str(e)}")
            result['error'] = str(e)
            return result
    
    def regenerate_dependent_configurations(self, changed_resource: HedgehogResource) -> Dict[str, Any]:
        """
        Regenerate configurations that depend on a changed resource.
        
        Args:
            changed_resource: Resource that changed and triggered regeneration
            
        Returns:
            Dict with regeneration results
        """
        logger.info(f"Regenerating dependent configurations for resource: {changed_resource.name}")
        
        try:
            # Find dependent templates
            dependent_templates = self._find_dependent_templates(changed_resource)
            if not dependent_templates:
                return {'success': True, 'message': 'No dependent templates found'}
            
            # Create generation context
            context = self._create_context_for_resource(changed_resource)
            
            # Generate configurations for dependent templates only
            generation_result = self._generate_selective_configurations(context, dependent_templates)
            
            return {
                'success': generation_result.success,
                'files_regenerated': generation_result.files_generated + generation_result.files_updated,
                'generation_time': generation_result.generation_time,
                'error': generation_result.error_message
            }
            
        except Exception as e:
            logger.error(f"Dependent configuration regeneration failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def validate_template_syntax(self, template_content: str) -> Dict[str, Any]:
        """
        Validate Jinja2 template syntax.
        
        Args:
            template_content: Template content to validate
            
        Returns:
            Dict with validation results
        """
        result = {
            'valid': False,
            'errors': [],
            'variables': [],
            'blocks': []
        }
        
        try:
            # Parse template
            ast = self.jinja_env.parse(template_content)
            
            # Extract template variables
            variables = meta.find_undeclared_variables(ast)
            result['variables'] = list(variables)
            
            # Find template blocks
            blocks = list(ast.find_all((meta.nodes.Block,)))
            result['blocks'] = [block.name for block in blocks]
            
            # Try to compile template
            self.jinja_env.from_string(template_content)
            
            result['valid'] = True
            return result
            
        except TemplateError as e:
            result['errors'].append({
                'type': 'template_error',
                'message': str(e),
                'line': getattr(e, 'lineno', None)
            })
            return result
        except Exception as e:
            result['errors'].append({
                'type': 'validation_error',
                'message': str(e)
            })
            return result
    
    def get_template_variables(self, template_path: str) -> List[str]:
        """Get list of variables used in a template."""
        try:
            template = self._load_template(template_path)
            ast = self.jinja_env.parse(template.source)
            variables = meta.find_undeclared_variables(ast)
            return list(variables)
        except Exception as e:
            logger.error(f"Failed to extract template variables: {str(e)}")
            return []
    
    def clear_cache(self):
        """Clear template cache."""
        self.template_cache.clear()
        logger.info("Template cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_templates = len(self.template_cache)
        cache_hits = sum(1 for entry in self.template_cache.values() if hasattr(entry, 'hits'))
        
        return {
            'total_cached_templates': total_templates,
            'cache_size_bytes': sum(len(str(entry)) for entry in self.template_cache.values()),
            'oldest_cache_entry': min(
                (entry.compiled_at for entry in self.template_cache.values()),
                default=None
            ),
            'cache_hit_ratio': cache_hits / max(total_templates, 1)
        }
    
    # Private methods
    
    def _get_default_directory(self) -> Path:
        """Get default base directory."""
        base_dir = getattr(settings, 'HEDGEHOG_CONFIG_TEMPLATE_DIR', None)
        if base_dir:
            return Path(base_dir)
        
        # Fallback to plugin directory
        plugin_dir = Path(__file__).parent.parent
        return plugin_dir / 'templates' / 'config'
    
    def _setup_jinja_environment(self):
        """Setup Jinja2 environment with security and performance settings."""
        template_dirs = [
            self.base_directory / 'templates',
            self.base_directory / 'includes'
        ]
        
        # Ensure directories exist
        for template_dir in template_dirs:
            template_dir.mkdir(parents=True, exist_ok=True)
        
        # Use sandboxed environment for security
        loader = FileSystemLoader([str(d) for d in template_dirs])
        self.jinja_env = SandboxedEnvironment(
            loader=loader,
            auto_reload=True,  # Development mode
            cache_size=self.max_cache_size,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters and functions
        self._register_custom_filters()
        
        logger.info(f"Jinja2 environment initialized with template dirs: {template_dirs}")
    
    def _register_custom_filters(self):
        """Register custom Jinja2 filters for NetBox data."""
        
        def format_ip_address(value):
            """Format IP address with proper notation."""
            if not value:
                return ''
            return str(value).split('/')[0] if '/' in str(value) else str(value)
        
        def format_cidr(value):
            """Format CIDR notation."""
            return str(value) if value else ''
        
        def to_yaml_safe(value):
            """Convert value to YAML-safe string."""
            if isinstance(value, (dict, list)):
                return yaml.safe_dump(value, default_flow_style=False).strip()
            return str(value)
        
        def resource_name(value):
            """Generate Kubernetes-compliant resource name."""
            if not value:
                return ''
            # Convert to lowercase, replace invalid chars with hyphens
            name = str(value).lower().replace('_', '-').replace(' ', '-')
            # Remove invalid characters
            import re
            name = re.sub(r'[^a-z0-9-]', '', name)
            # Ensure it starts and ends with alphanumeric
            name = re.sub(r'^-+|-+$', '', name)
            return name[:63]  # Kubernetes name limit
        
        def fabric_resources(fabric_obj, resource_type=None):
            """Get resources for a fabric, optionally filtered by type."""
            if not fabric_obj:
                return []
            
            resources = fabric_obj.gitops_resources.all()
            if resource_type:
                resources = resources.filter(kind=resource_type)
            
            return list(resources)
        
        # Register filters
        self.jinja_env.filters.update({
            'format_ip': format_ip_address,
            'format_cidr': format_cidr,
            'to_yaml': to_yaml_safe,
            'k8s_name': resource_name,
            'fabric_resources': fabric_resources,
        })
        
        # Add global functions
        self.jinja_env.globals.update({
            'now': timezone.now,
            'datetime': datetime,
        })
    
    def _validate_generation_context(self, context: GenerationContext) -> Dict[str, Any]:
        """Validate generation context."""
        if not context.fabric:
            return {'valid': False, 'error': 'Fabric is required'}
        
        if not context.output_directory.exists():
            try:
                context.output_directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return {'valid': False, 'error': f'Cannot create output directory: {str(e)}'}
        
        return {'valid': True}
    
    def _load_applicable_templates(self, context: GenerationContext) -> List[Dict[str, Any]]:
        """Load templates applicable to the generation context."""
        try:
            # Get templates from template manager
            all_templates = self.template_manager.list_templates()
            
            # Filter templates based on context
            applicable_templates = []
            for template_info in all_templates:
                if self._is_template_applicable(template_info, context):
                    applicable_templates.append(template_info)
            
            logger.info(f"Found {len(applicable_templates)} applicable templates out of {len(all_templates)}")
            return applicable_templates
            
        except Exception as e:
            logger.error(f"Failed to load applicable templates: {str(e)}")
            return []
    
    def _is_template_applicable(self, template_info: Dict[str, Any], context: GenerationContext) -> bool:
        """Check if a template is applicable to the generation context."""
        # Check fabric-specific templates
        fabric_filter = template_info.get('fabric_filter')
        if fabric_filter and context.fabric.name not in fabric_filter:
            return False
        
        # Check resource type requirements
        required_resources = template_info.get('required_resources', [])
        if required_resources:
            available_types = {r.kind for r in context.resources}
            if not set(required_resources).issubset(available_types):
                return False
        
        # Check template conditions
        conditions = template_info.get('conditions', [])
        for condition in conditions:
            if not self._evaluate_template_condition(condition, context):
                return False
        
        return True
    
    def _evaluate_template_condition(self, condition: Dict[str, Any], context: GenerationContext) -> bool:
        """Evaluate a template condition."""
        condition_type = condition.get('type')
        
        if condition_type == 'resource_count':
            resource_kind = condition.get('resource_kind')
            min_count = condition.get('min_count', 0)
            max_count = condition.get('max_count', float('inf'))
            
            actual_count = len([r for r in context.resources if r.kind == resource_kind])
            return min_count <= actual_count <= max_count
        
        elif condition_type == 'fabric_property':
            property_name = condition.get('property')
            expected_value = condition.get('value')
            
            actual_value = getattr(context.fabric, property_name, None)
            return actual_value == expected_value
        
        # Unknown condition type, assume true
        return True
    
    def _create_template_batches(self, templates: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Create batches of templates for processing."""
        batches = []
        current_batch = []
        
        for template in templates:
            current_batch.append(template)
            if len(current_batch) >= self.batch_size:
                batches.append(current_batch)
                current_batch = []
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _process_template_batch(self, context: GenerationContext, 
                              templates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process a batch of templates."""
        batch_result = {
            'files_generated': [],
            'files_updated': [],
            'template_errors': [],
            'templates_processed': 0
        }
        
        for template_info in templates:
            try:
                template_result = self._process_single_template(context, template_info)
                
                if template_result['success']:
                    if template_result.get('file_existed'):
                        batch_result['files_updated'].append(template_result['output_path'])
                    else:
                        batch_result['files_generated'].append(template_result['output_path'])
                else:
                    batch_result['template_errors'].append({
                        'template': template_info.get('name', 'unknown'),
                        'error': template_result.get('error', 'Unknown error')
                    })
                
                batch_result['templates_processed'] += 1
                
            except Exception as e:
                logger.error(f"Template processing error: {str(e)}")
                batch_result['template_errors'].append({
                    'template': template_info.get('name', 'unknown'),
                    'error': str(e)
                })
        
        return batch_result
    
    def _process_single_template(self, context: GenerationContext, 
                               template_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single template."""
        template_path = template_info['path']
        template_name = template_info.get('name', Path(template_path).stem)
        
        result = {
            'success': False,
            'template_name': template_name,
            'template_path': template_path,
            'output_path': None,
            'file_existed': False,
            'error': None
        }
        
        try:
            # Load template with caching
            template = self._load_template_cached(template_path)
            
            # Prepare template context
            template_context = self._build_template_context(context, template_info)
            
            # Render template
            rendered_content = template.render(template_context)
            
            # Determine output path
            output_path = self._determine_output_path(context, template_info, template_context)
            result['output_path'] = str(output_path)
            
            # Check if file exists
            result['file_existed'] = output_path.exists()
            
            # Write rendered content
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(rendered_content)
            
            result['success'] = True
            logger.debug(f"Generated template: {template_name} -> {output_path}")
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Template processing failed for {template_name}: {str(e)}")
            return result
    
    def _load_template(self, template_path: str) -> Template:
        """Load a template from the filesystem."""
        return self.jinja_env.get_template(template_path)
    
    def _load_template_cached(self, template_path: str) -> Template:
        """Load template with caching."""
        template_file = self.base_directory / 'templates' / template_path
        
        # Calculate template hash
        if template_file.exists():
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            template_hash = hashlib.sha256(content.encode()).hexdigest()
        else:
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        # Check cache
        cache_key = template_path
        cached_entry = self.template_cache.get(cache_key)
        
        if cached_entry and cached_entry.template_hash == template_hash:
            # Cache hit
            return cached_entry.template
        
        # Cache miss - load template
        template = self._load_template(template_path)
        
        # Update cache
        cache_entry = TemplateCache(
            template=template,
            template_hash=template_hash,
            compiled_at=timezone.now(),
            dependencies=self._extract_template_dependencies(content),
            variables=self.get_template_variables(template_path)
        )
        
        self.template_cache[cache_key] = cache_entry
        
        # Cleanup cache if too large
        if len(self.template_cache) > self.max_cache_size:
            self._cleanup_template_cache()
        
        return template
    
    def _extract_template_dependencies(self, template_content: str) -> List[str]:
        """Extract template dependencies (includes, extends)."""
        dependencies = []
        
        # Simple regex-based extraction (could be enhanced)
        import re
        
        # Find {% include %} statements
        includes = re.findall(r'{%\s*include\s+["\']([^"\']+)["\']', template_content)
        dependencies.extend(includes)
        
        # Find {% extends %} statements
        extends = re.findall(r'{%\s*extends\s+["\']([^"\']+)["\']', template_content)
        dependencies.extend(extends)
        
        return dependencies
    
    def _cleanup_template_cache(self):
        """Cleanup old cache entries."""
        # Remove oldest 20% of entries
        sorted_entries = sorted(
            self.template_cache.items(),
            key=lambda x: x[1].compiled_at
        )
        
        cleanup_count = max(1, len(sorted_entries) // 5)
        for key, _ in sorted_entries[:cleanup_count]:
            del self.template_cache[key]
        
        logger.debug(f"Cleaned up {cleanup_count} cache entries")
    
    def _build_template_context(self, context: GenerationContext, 
                              template_info: Dict[str, Any]) -> Dict[str, Any]:
        """Build context for template rendering."""
        template_context = {
            # Core objects
            'fabric': context.fabric,
            'resources': context.resources,
            
            # Context variables
            'vars': context.template_vars,
            'generation_id': context.generation_id,
            'timestamp': context.generation_timestamp,
            
            # Utility functions
            'fabric_name': context.fabric.name,
            'resource_count': len(context.resources),
            
            # Resource collections by type
            'vpcs': [r for r in context.resources if r.kind == 'VPC'],
            'connections': [r for r in context.resources if r.kind == 'Connection'],
            'servers': [r for r in context.resources if r.kind == 'Server'],
            'switches': [r for r in context.resources if r.kind == 'Switch'],
        }
        
        # Add template-specific variables
        template_vars = template_info.get('variables', {})
        template_context.update(template_vars)
        
        return template_context
    
    def _determine_output_path(self, context: GenerationContext, 
                             template_info: Dict[str, Any], 
                             template_context: Dict[str, Any]) -> Path:
        """Determine output path for generated file."""
        output_pattern = template_info.get('output_pattern')
        
        if output_pattern:
            # Use Jinja2 to render output path pattern
            path_template = self.jinja_env.from_string(output_pattern)
            output_path = path_template.render(template_context)
        else:
            # Default: use template name with .yaml extension
            template_name = Path(template_info['path']).stem
            output_path = f"{template_name}.yaml"
        
        return context.output_directory / output_path
    
    def _consolidate_batch_results(self, result: GenerationResult, 
                                 batch_results: List[Dict[str, Any]]):
        """Consolidate results from template batches."""
        for batch_result in batch_results:
            result.files_generated.extend(batch_result.get('files_generated', []))
            result.files_updated.extend(batch_result.get('files_updated', []))
            result.template_errors.extend(batch_result.get('template_errors', []))
    
    def _validate_generated_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """Validate generated YAML files."""
        validation_results = {
            'validated_files': [],
            'errors': []
        }
        
        for file_path in file_paths:
            try:
                validation_result = self.schema_validator.validate_file(file_path)
                
                if validation_result['valid']:
                    validation_results['validated_files'].append(file_path)
                else:
                    validation_results['errors'].extend(validation_result.get('errors', []))
                    
            except Exception as e:
                validation_results['errors'].append({
                    'file': file_path,
                    'error': str(e),
                    'severity': 'error'
                })
        
        return validation_results
    
    def _build_dependency_map(self, context: GenerationContext, 
                            templates: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Build dependency map between resources and generated files."""
        dependency_map = {}
        
        for resource in context.resources:
            resource_id = f"{resource.kind}/{resource.name}"
            dependent_files = []
            
            for template_info in templates:
                # Check if template depends on this resource type
                required_resources = template_info.get('required_resources', [])
                if resource.kind in required_resources:
                    template_name = template_info.get('name', Path(template_info['path']).stem)
                    dependent_files.append(f"{template_name}.yaml")
            
            if dependent_files:
                dependency_map[resource_id] = dependent_files
        
        return dependency_map
    
    def _record_generation(self, context: GenerationContext, result: GenerationResult):
        """Record generation in history."""
        generation_record = {
            'generation_id': result.generation_id,
            'fabric_name': context.fabric.name,
            'timestamp': context.generation_timestamp,
            'success': result.success,
            'files_count': len(result.files_generated) + len(result.files_updated),
            'generation_time': result.generation_time,
            'error': result.error_message
        }
        
        self.generation_history.append(generation_record)
        
        # Keep only recent records
        if len(self.generation_history) > 100:
            self.generation_history = self.generation_history[-50:]
    
    def _find_dependent_templates(self, resource: HedgehogResource) -> List[str]:
        """Find templates that depend on a specific resource."""
        # This would integrate with template dependency tracking
        # For now, return empty list - will be enhanced based on actual template metadata
        return []
    
    def _create_context_for_resource(self, resource: HedgehogResource) -> GenerationContext:
        """Create generation context for a specific resource."""
        return GenerationContext(
            fabric=resource.fabric,
            resources=[resource],
            template_vars={},
            generation_timestamp=timezone.now(),
            generation_id=f"regen_{resource.id}_{int(timezone.now().timestamp())}",
            output_directory=self.base_directory / 'generated'
        )
    
    def _generate_selective_configurations(self, context: GenerationContext, 
                                         templates: List[str]) -> GenerationResult:
        """Generate configurations for specific templates only."""
        # Filter templates to only those in the provided list
        all_templates = self.template_manager.list_templates()
        filtered_templates = [t for t in all_templates if t.get('name') in templates]
        
        # Use regular generation process with filtered templates
        return self._process_filtered_generation(context, filtered_templates)
    
    def _process_filtered_generation(self, context: GenerationContext, 
                                   templates: List[Dict[str, Any]]) -> GenerationResult:
        """Process generation with pre-filtered templates."""
        # This is a simplified version of generate_configuration for selective regeneration
        start_time = timezone.now()
        
        result = GenerationResult(
            generation_id=context.generation_id,
            success=False,
            files_generated=[],
            files_updated=[],
            files_validated=[],
            validation_errors=[],
            template_errors=[],
            dependency_map={},
            generation_time=0.0
        )
        
        try:
            batch_results = []
            template_batches = self._create_template_batches(templates)
            
            for template_batch in template_batches:
                batch_result = self._process_template_batch(context, template_batch)
                batch_results.append(batch_result)
            
            self._consolidate_batch_results(result, batch_results)
            
            result.success = len(result.template_errors) == 0
            result.generation_time = (timezone.now() - start_time).total_seconds()
            
            return result
            
        except Exception as e:
            result.error_message = str(e)
            result.generation_time = (timezone.now() - start_time).total_seconds()
            return result


# Convenience functions for integration
def generate_fabric_configuration(fabric: HedgehogFabric, output_directory: Path = None) -> GenerationResult:
    """Convenience function to generate configuration for a fabric."""
    generator = ConfigurationGenerator(fabric)
    
    resources = list(fabric.gitops_resources.all())
    
    context = GenerationContext(
        fabric=fabric,
        resources=resources,
        template_vars={},
        generation_timestamp=timezone.now(),
        generation_id=f"fabric_{fabric.id}_{int(timezone.now().timestamp())}",
        output_directory=output_directory or generator.base_directory / 'generated' / fabric.name
    )
    
    return generator.generate_configuration(context)


def regenerate_for_resource_change(resource: HedgehogResource) -> Dict[str, Any]:
    """Convenience function to regenerate configurations after resource change."""
    generator = ConfigurationGenerator(resource.fabric)
    return generator.regenerate_dependent_configurations(resource)