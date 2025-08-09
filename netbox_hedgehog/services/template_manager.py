"""
Template Management System

Advanced template repository with version control, validation, inheritance,
and dynamic loading capabilities for the Configuration Template Engine.

This service manages Jinja2 templates used for generating Kubernetes YAML
configurations from NetBox data with comprehensive versioning and caching.
"""

import os
import yaml
import json
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from jinja2 import Environment, FileSystemLoader, TemplateError, meta

logger = logging.getLogger(__name__)


@dataclass
class TemplateMetadata:
    """Metadata for a template file."""
    name: str
    path: str
    version: str
    description: str
    author: str
    created_at: datetime
    updated_at: datetime
    template_hash: str
    dependencies: List[str]
    variables: List[str]
    required_resources: List[str]
    fabric_filter: Optional[List[str]]
    conditions: List[Dict[str, Any]]
    output_pattern: Optional[str]
    category: str
    tags: List[str]
    validation_schema: Optional[str]


@dataclass
class TemplateVersion:
    """Version information for a template."""
    version: str
    template_hash: str
    created_at: datetime
    author: str
    changelog: str
    compatible_versions: List[str]


@dataclass
class TemplateValidation:
    """Template validation result."""
    valid: bool
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    variables: List[str]
    dependencies: List[str]


class TemplateManager:
    """
    Advanced template management system with versioning and caching.
    
    Features:
    - Template repository with version control
    - Template validation and linting
    - Template inheritance and composition
    - Dynamic template loading and caching
    - Template dependency tracking
    - Performance optimization with intelligent caching
    """
    
    def __init__(self, base_directory: Union[str, Path]):
        self.base_directory = Path(base_directory).resolve()
        self.templates_directory = self.base_directory / 'templates'
        self.metadata_directory = self.base_directory / 'metadata'
        self.versions_directory = self.base_directory / 'versions'
        self.includes_directory = self.templates_directory / 'includes'
        self.schemas_directory = self.base_directory / 'schemas'
        
        # Initialize directories
        self._initialize_directories()
        
        # Template cache
        self.template_cache = {}
        self.metadata_cache = {}
        self.cache_ttl = getattr(settings, 'TEMPLATE_CACHE_TTL', 3600)  # 1 hour
        self.max_cache_size = getattr(settings, 'TEMPLATE_MAX_CACHE_SIZE', 200)
        
        # Template registry
        self.template_registry = {}
        self.dependency_graph = {}
        
        # Load existing templates
        self._load_template_registry()
        
        logger.info(f"Template manager initialized with base directory: {self.base_directory}")
    
    def create_template(self, name: str, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a new template with metadata and validation.
        
        Args:
            name: Template name (unique identifier)
            content: Template content (Jinja2 syntax)
            metadata: Optional metadata dict
            
        Returns:
            Dict with creation results
        """
        logger.info(f"Creating template: {name}")
        
        result = {
            'success': False,
            'template_name': name,
            'template_path': None,
            'validation_result': None,
            'error': None
        }
        
        try:
            # Validate template name
            if not self._is_valid_template_name(name):
                result['error'] = f"Invalid template name: {name}"
                return result
            
            # Check if template already exists
            if self._template_exists(name):
                result['error'] = f"Template already exists: {name}"
                return result
            
            # Validate template content
            validation_result = self._validate_template_content(content)
            result['validation_result'] = validation_result
            
            if not validation_result['valid']:
                result['error'] = f"Template validation failed: {validation_result['errors']}"
                return result
            
            # Generate template path
            template_path = self._generate_template_path(name)
            result['template_path'] = str(template_path)
            
            # Create template metadata
            template_metadata = self._create_template_metadata(
                name, template_path, content, metadata or {}
            )
            
            # Save template file
            template_path.parent.mkdir(parents=True, exist_ok=True)
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Save metadata
            self._save_template_metadata(template_metadata)
            
            # Create initial version
            self._create_template_version(template_metadata, "Initial version", "system")
            
            # Update registry
            self.template_registry[name] = template_metadata
            
            # Update dependency graph
            self._update_dependency_graph(template_metadata)
            
            result['success'] = True
            logger.info(f"Template created successfully: {name} -> {template_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"Template creation failed for {name}: {str(e)}")
            result['error'] = str(e)
            return result
    
    def update_template(self, name: str, content: str, changelog: str = "", 
                       author: str = "system") -> Dict[str, Any]:
        """
        Update an existing template with versioning.
        
        Args:
            name: Template name
            content: New template content
            changelog: Description of changes
            author: Author of the update
            
        Returns:
            Dict with update results
        """
        logger.info(f"Updating template: {name}")
        
        result = {
            'success': False,
            'template_name': name,
            'old_version': None,
            'new_version': None,
            'validation_result': None,
            'error': None
        }
        
        try:
            # Check if template exists
            if not self._template_exists(name):
                result['error'] = f"Template does not exist: {name}"
                return result
            
            # Get current metadata
            current_metadata = self.template_registry[name]
            result['old_version'] = current_metadata.version
            
            # Validate new content
            validation_result = self._validate_template_content(content)
            result['validation_result'] = validation_result
            
            if not validation_result['valid']:
                result['error'] = f"Template validation failed: {validation_result['errors']}"
                return result
            
            # Check if content actually changed
            new_hash = self._calculate_template_hash(content)
            if new_hash == current_metadata.template_hash:
                result['success'] = True
                result['new_version'] = current_metadata.version
                result['error'] = "No changes detected"
                return result
            
            # Generate new version
            new_version = self._generate_next_version(current_metadata.version)
            result['new_version'] = new_version
            
            # Create backup of current version
            self._backup_template_version(current_metadata)
            
            # Update template file
            template_path = Path(current_metadata.path)
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update metadata
            updated_metadata = self._update_template_metadata(
                current_metadata, content, new_version, validation_result
            )
            
            # Save updated metadata
            self._save_template_metadata(updated_metadata)
            
            # Create version record
            self._create_template_version(updated_metadata, changelog, author)
            
            # Update registry and caches
            self.template_registry[name] = updated_metadata
            self._invalidate_template_cache(name)
            self._update_dependency_graph(updated_metadata)
            
            result['success'] = True
            logger.info(f"Template updated successfully: {name} (v{new_version})")
            
            return result
            
        except Exception as e:
            logger.error(f"Template update failed for {name}: {str(e)}")
            result['error'] = str(e)
            return result
    
    def delete_template(self, name: str, archive: bool = True) -> Dict[str, Any]:
        """
        Delete a template with optional archiving.
        
        Args:
            name: Template name
            archive: Whether to archive the template instead of permanent deletion
            
        Returns:
            Dict with deletion results
        """
        logger.info(f"Deleting template: {name} (archive={archive})")
        
        result = {
            'success': False,
            'template_name': name,
            'archived': archive,
            'archive_path': None,
            'error': None
        }
        
        try:
            # Check if template exists
            if not self._template_exists(name):
                result['error'] = f"Template does not exist: {name}"
                return result
            
            template_metadata = self.template_registry[name]
            template_path = Path(template_metadata.path)
            
            # Check for dependent templates
            dependents = self._find_dependent_templates(name)
            if dependents:
                result['error'] = f"Cannot delete template with dependencies: {dependents}"
                return result
            
            if archive:
                # Archive template and metadata
                archive_path = self._archive_template(template_metadata)
                result['archive_path'] = str(archive_path)
            else:
                # Permanent deletion
                if template_path.exists():
                    template_path.unlink()
                
                # Remove metadata file
                metadata_path = self._get_metadata_path(name)
                if metadata_path.exists():
                    metadata_path.unlink()
                
                # Remove version history
                self._remove_version_history(name)
            
            # Remove from registry and caches
            del self.template_registry[name]
            self._invalidate_template_cache(name)
            self._update_dependency_graph_for_deletion(name)
            
            result['success'] = True
            logger.info(f"Template deleted successfully: {name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Template deletion failed for {name}: {str(e)}")
            result['error'] = str(e)
            return result
    
    def get_template(self, name: str, use_cache: bool = True) -> Optional[str]:
        """
        Get template content by name with caching.
        
        Args:
            name: Template name
            use_cache: Whether to use cache
            
        Returns:
            Template content or None if not found
        """
        try:
            # Check cache first
            if use_cache and name in self.template_cache:
                cache_entry = self.template_cache[name]
                if self._is_cache_valid(cache_entry):
                    return cache_entry['content']
            
            # Check if template exists
            if not self._template_exists(name):
                return None
            
            # Load from filesystem
            template_metadata = self.template_registry[name]
            template_path = Path(template_metadata.path)
            
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update cache
            if use_cache:
                self._cache_template(name, content)
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to get template {name}: {str(e)}")
            return None
    
    def list_templates(self, category: Optional[str] = None, 
                      tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        List available templates with optional filtering.
        
        Args:
            category: Optional category filter
            tags: Optional tags filter
            
        Returns:
            List of template information dicts
        """
        templates = []
        
        for name, metadata in self.template_registry.items():
            # Apply filters
            if category and metadata.category != category:
                continue
            
            if tags and not any(tag in metadata.tags for tag in tags):
                continue
            
            template_info = {
                'name': metadata.name,
                'path': metadata.path,
                'version': metadata.version,
                'description': metadata.description,
                'author': metadata.author,
                'created_at': metadata.created_at,
                'updated_at': metadata.updated_at,
                'category': metadata.category,
                'tags': metadata.tags,
                'required_resources': metadata.required_resources,
                'fabric_filter': metadata.fabric_filter,
                'conditions': metadata.conditions,
                'output_pattern': metadata.output_pattern,
                'variables': metadata.variables,
                'dependencies': metadata.dependencies
            }
            templates.append(template_info)
        
        # Sort by name
        templates.sort(key=lambda x: x['name'])
        return templates
    
    def validate_template(self, name: str) -> TemplateValidation:
        """
        Validate a template comprehensively.
        
        Args:
            name: Template name
            
        Returns:
            TemplateValidation object with validation results
        """
        if not self._template_exists(name):
            return TemplateValidation(
                valid=False,
                errors=[{'type': 'not_found', 'message': f'Template not found: {name}'}],
                warnings=[],
                variables=[],
                dependencies=[]
            )
        
        try:
            content = self.get_template(name, use_cache=False)
            return self._validate_template_content(content)
            
        except Exception as e:
            return TemplateValidation(
                valid=False,
                errors=[{'type': 'validation_error', 'message': str(e)}],
                warnings=[],
                variables=[],
                dependencies=[]
            )
    
    def get_template_metadata(self, name: str) -> Optional[TemplateMetadata]:
        """Get metadata for a template."""
        return self.template_registry.get(name)
    
    def get_template_versions(self, name: str) -> List[TemplateVersion]:
        """Get version history for a template."""
        try:
            versions_file = self.versions_directory / f"{name}.json"
            if not versions_file.exists():
                return []
            
            with open(versions_file, 'r', encoding='utf-8') as f:
                versions_data = json.load(f)
            
            versions = []
            for version_data in versions_data['versions']:
                version = TemplateVersion(
                    version=version_data['version'],
                    template_hash=version_data['template_hash'],
                    created_at=datetime.fromisoformat(version_data['created_at']),
                    author=version_data['author'],
                    changelog=version_data['changelog'],
                    compatible_versions=version_data.get('compatible_versions', [])
                )
                versions.append(version)
            
            return versions
            
        except Exception as e:
            logger.error(f"Failed to get template versions for {name}: {str(e)}")
            return []
    
    def restore_template_version(self, name: str, version: str) -> Dict[str, Any]:
        """
        Restore a template to a specific version.
        
        Args:
            name: Template name
            version: Version to restore to
            
        Returns:
            Dict with restoration results
        """
        logger.info(f"Restoring template {name} to version {version}")
        
        result = {
            'success': False,
            'template_name': name,
            'target_version': version,
            'previous_version': None,
            'error': None
        }
        
        try:
            # Check if template exists
            if not self._template_exists(name):
                result['error'] = f"Template does not exist: {name}"
                return result
            
            current_metadata = self.template_registry[name]
            result['previous_version'] = current_metadata.version
            
            # Find version backup
            version_backup = self._find_version_backup(name, version)
            if not version_backup:
                result['error'] = f"Version backup not found: {version}"
                return result
            
            # Read version content
            with open(version_backup, 'r', encoding='utf-8') as f:
                version_content = f.read()
            
            # Update template using standard update process
            update_result = self.update_template(
                name, 
                version_content, 
                f"Restored to version {version}",
                "system"
            )
            
            if update_result['success']:
                result['success'] = True
                logger.info(f"Template {name} restored to version {version}")
            else:
                result['error'] = update_result['error']
            
            return result
            
        except Exception as e:
            logger.error(f"Template restoration failed for {name}: {str(e)}")
            result['error'] = str(e)
            return result
    
    def export_template(self, name: str, include_metadata: bool = True) -> Dict[str, Any]:
        """
        Export template with optional metadata.
        
        Args:
            name: Template name
            include_metadata: Whether to include metadata in export
            
        Returns:
            Dict with export data
        """
        if not self._template_exists(name):
            return {'error': f'Template not found: {name}'}
        
        try:
            content = self.get_template(name, use_cache=False)
            
            export_data = {
                'name': name,
                'content': content,
                'exported_at': timezone.now().isoformat()
            }
            
            if include_metadata:
                metadata = self.template_registry[name]
                export_data['metadata'] = asdict(metadata)
                
                # Include version history
                versions = self.get_template_versions(name)
                export_data['versions'] = [asdict(v) for v in versions]
            
            return export_data
            
        except Exception as e:
            logger.error(f"Template export failed for {name}: {str(e)}")
            return {'error': str(e)}
    
    def import_template(self, export_data: Dict[str, Any], 
                       overwrite: bool = False) -> Dict[str, Any]:
        """
        Import template from export data.
        
        Args:
            export_data: Template export data
            overwrite: Whether to overwrite existing template
            
        Returns:
            Dict with import results
        """
        name = export_data.get('name')
        content = export_data.get('content')
        
        if not name or not content:
            return {'success': False, 'error': 'Invalid export data'}
        
        logger.info(f"Importing template: {name}")
        
        try:
            # Check if template exists
            if self._template_exists(name) and not overwrite:
                return {'success': False, 'error': f'Template exists and overwrite=False: {name}'}
            
            # Import metadata if available
            metadata = export_data.get('metadata', {})
            
            if self._template_exists(name):
                # Update existing template
                result = self.update_template(name, content, "Imported update", "import")
            else:
                # Create new template
                result = self.create_template(name, content, metadata)
            
            if result['success']:
                logger.info(f"Template imported successfully: {name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Template import failed for {name}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get the complete template dependency graph."""
        return self.dependency_graph.copy()
    
    def find_template_dependents(self, name: str) -> List[str]:
        """Find templates that depend on the given template."""
        return self._find_dependent_templates(name)
    
    def clear_cache(self):
        """Clear all caches."""
        self.template_cache.clear()
        self.metadata_cache.clear()
        logger.info("Template caches cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'template_cache_size': len(self.template_cache),
            'metadata_cache_size': len(self.metadata_cache),
            'total_templates': len(self.template_registry),
            'cache_hit_ratio': self._calculate_cache_hit_ratio()
        }
    
    def optimize_templates(self) -> Dict[str, Any]:
        """
        Optimize templates by removing unused includes and variables.
        
        Returns:
            Dict with optimization results
        """
        logger.info("Starting template optimization")
        
        results = {
            'optimized_templates': [],
            'unused_includes': [],
            'unused_variables': [],
            'warnings': []
        }
        
        try:
            for name, metadata in self.template_registry.items():
                # Analyze template usage
                content = self.get_template(name, use_cache=False)
                
                # Find unused includes
                unused_includes = self._find_unused_includes(content, metadata.dependencies)
                if unused_includes:
                    results['unused_includes'].extend([
                        {'template': name, 'include': inc} for inc in unused_includes
                    ])
                
                # Find unused variables (this would need runtime analysis)
                # For now, just report declared but potentially unused variables
                declared_vars = metadata.variables
                used_vars = self._extract_used_variables(content)
                unused_vars = set(declared_vars) - set(used_vars)
                
                if unused_vars:
                    results['unused_variables'].extend([
                        {'template': name, 'variable': var} for var in unused_vars
                    ])
            
            logger.info(f"Template optimization completed: "
                       f"{len(results['unused_includes'])} unused includes, "
                       f"{len(results['unused_variables'])} unused variables")
            
            return results
            
        except Exception as e:
            logger.error(f"Template optimization failed: {str(e)}")
            results['error'] = str(e)
            return results
    
    # Private methods
    
    def _initialize_directories(self):
        """Initialize required directories."""
        directories = [
            self.templates_directory,
            self.metadata_directory,
            self.versions_directory,
            self.includes_directory,
            self.schemas_directory
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Initialized directory: {directory}")
    
    def _load_template_registry(self):
        """Load template registry from metadata files."""
        try:
            if not self.metadata_directory.exists():
                return
            
            for metadata_file in self.metadata_directory.glob('*.json'):
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata_data = json.load(f)
                    
                    # Convert datetime strings back to datetime objects
                    for field in ['created_at', 'updated_at']:
                        if field in metadata_data:
                            metadata_data[field] = datetime.fromisoformat(metadata_data[field])
                    
                    metadata = TemplateMetadata(**metadata_data)
                    self.template_registry[metadata.name] = metadata
                    
                except Exception as e:
                    logger.warning(f"Failed to load template metadata from {metadata_file}: {str(e)}")
            
            logger.info(f"Loaded {len(self.template_registry)} templates from registry")
            
            # Build dependency graph
            self._build_dependency_graph()
            
        except Exception as e:
            logger.error(f"Failed to load template registry: {str(e)}")
    
    def _is_valid_template_name(self, name: str) -> bool:
        """Validate template name."""
        import re
        # Must be valid filename and not contain path separators
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', name)) and len(name) <= 100
    
    def _template_exists(self, name: str) -> bool:
        """Check if template exists."""
        return name in self.template_registry
    
    def _generate_template_path(self, name: str) -> Path:
        """Generate file path for template."""
        return self.templates_directory / f"{name}.j2"
    
    def _calculate_template_hash(self, content: str) -> str:
        """Calculate hash of template content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _create_template_metadata(self, name: str, path: Path, content: str, 
                                metadata: Dict[str, Any]) -> TemplateMetadata:
        """Create metadata object for template."""
        # Extract template information
        validation = self._validate_template_content(content)
        
        return TemplateMetadata(
            name=name,
            path=str(path),
            version="1.0.0",
            description=metadata.get('description', ''),
            author=metadata.get('author', 'system'),
            created_at=timezone.now(),
            updated_at=timezone.now(),
            template_hash=self._calculate_template_hash(content),
            dependencies=validation['dependencies'],
            variables=validation['variables'],
            required_resources=metadata.get('required_resources', []),
            fabric_filter=metadata.get('fabric_filter'),
            conditions=metadata.get('conditions', []),
            output_pattern=metadata.get('output_pattern'),
            category=metadata.get('category', 'general'),
            tags=metadata.get('tags', []),
            validation_schema=metadata.get('validation_schema')
        )
    
    def _validate_template_content(self, content: str) -> TemplateValidation:
        """Validate template content comprehensively."""
        validation = TemplateValidation(
            valid=True,
            errors=[],
            warnings=[],
            variables=[],
            dependencies=[]
        )
        
        try:
            from jinja2 import Environment, meta, TemplateError
            
            # Create temporary environment for parsing
            env = Environment()
            
            # Parse template
            try:
                ast = env.parse(content)
            except TemplateError as e:
                validation.valid = False
                validation.errors.append({
                    'type': 'template_syntax',
                    'message': str(e),
                    'line': getattr(e, 'lineno', None)
                })
                return validation
            
            # Extract variables
            variables = meta.find_undeclared_variables(ast)
            validation.variables = list(variables)
            
            # Extract dependencies (includes/extends)
            import re
            includes = re.findall(r'{%\s*include\s+["\']([^"\']+)["\']', content)
            extends = re.findall(r'{%\s*extends\s+["\']([^"\']+)["\']', content)
            validation.dependencies = includes + extends
            
            # Check for common issues
            self._check_template_quality(content, validation)
            
            return validation
            
        except Exception as e:
            validation.valid = False
            validation.errors.append({
                'type': 'validation_error',
                'message': str(e)
            })
            return validation
    
    def _check_template_quality(self, content: str, validation: TemplateValidation):
        """Check template for quality issues."""
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for very long lines
            if len(line) > 200:
                validation.warnings.append({
                    'type': 'long_line',
                    'message': f'Line {i} is very long ({len(line)} characters)',
                    'line': i
                })
            
            # Check for hardcoded values that should be variables
            import re
            if re.search(r':\s*"[^"]*\.(com|net|org)"', line):
                validation.warnings.append({
                    'type': 'hardcoded_domain',
                    'message': f'Line {i} contains hardcoded domain',
                    'line': i
                })
    
    def _save_template_metadata(self, metadata: TemplateMetadata):
        """Save template metadata to file."""
        metadata_file = self.metadata_directory / f"{metadata.name}.json"
        
        # Convert to dict and handle datetime serialization
        metadata_dict = asdict(metadata)
        metadata_dict['created_at'] = metadata.created_at.isoformat()
        metadata_dict['updated_at'] = metadata.updated_at.isoformat()
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, indent=2, ensure_ascii=False)
    
    def _get_metadata_path(self, name: str) -> Path:
        """Get path to metadata file."""
        return self.metadata_directory / f"{name}.json"
    
    def _create_template_version(self, metadata: TemplateMetadata, changelog: str, author: str):
        """Create version record for template."""
        versions_file = self.versions_directory / f"{metadata.name}.json"
        
        new_version = TemplateVersion(
            version=metadata.version,
            template_hash=metadata.template_hash,
            created_at=timezone.now(),
            author=author,
            changelog=changelog,
            compatible_versions=[]
        )
        
        # Load existing versions
        versions_data = {'versions': []}
        if versions_file.exists():
            with open(versions_file, 'r', encoding='utf-8') as f:
                versions_data = json.load(f)
        
        # Add new version
        version_dict = asdict(new_version)
        version_dict['created_at'] = new_version.created_at.isoformat()
        versions_data['versions'].append(version_dict)
        
        # Keep only last 20 versions
        versions_data['versions'] = versions_data['versions'][-20:]
        
        # Save updated versions
        with open(versions_file, 'w', encoding='utf-8') as f:
            json.dump(versions_data, f, indent=2, ensure_ascii=False)
    
    def _generate_next_version(self, current_version: str) -> str:
        """Generate next version number."""
        try:
            # Simple semantic versioning
            parts = current_version.split('.')
            if len(parts) >= 3:
                # Increment patch version
                parts[2] = str(int(parts[2]) + 1)
            else:
                # Fallback: append .1
                parts.append('1')
            
            return '.'.join(parts[:3])  # Major.Minor.Patch
            
        except Exception:
            # Fallback: timestamp-based version
            return f"{current_version}.{int(timezone.now().timestamp())}"
    
    def _update_template_metadata(self, current_metadata: TemplateMetadata, 
                                new_content: str, new_version: str, 
                                validation: TemplateValidation) -> TemplateMetadata:
        """Update template metadata with new information."""
        updated_metadata = TemplateMetadata(
            name=current_metadata.name,
            path=current_metadata.path,
            version=new_version,
            description=current_metadata.description,
            author=current_metadata.author,
            created_at=current_metadata.created_at,
            updated_at=timezone.now(),
            template_hash=self._calculate_template_hash(new_content),
            dependencies=validation['dependencies'],
            variables=validation['variables'],
            required_resources=current_metadata.required_resources,
            fabric_filter=current_metadata.fabric_filter,
            conditions=current_metadata.conditions,
            output_pattern=current_metadata.output_pattern,
            category=current_metadata.category,
            tags=current_metadata.tags,
            validation_schema=current_metadata.validation_schema
        )
        
        return updated_metadata
    
    def _backup_template_version(self, metadata: TemplateMetadata):
        """Backup current template version."""
        template_path = Path(metadata.path)
        if not template_path.exists():
            return
        
        backup_dir = self.versions_directory / metadata.name
        backup_dir.mkdir(exist_ok=True)
        
        backup_filename = f"{metadata.version}_{metadata.template_hash[:8]}.j2"
        backup_path = backup_dir / backup_filename
        
        shutil.copy2(template_path, backup_path)
        logger.debug(f"Backed up template version: {backup_path}")
    
    def _find_version_backup(self, name: str, version: str) -> Optional[Path]:
        """Find backup file for specific template version."""
        backup_dir = self.versions_directory / name
        if not backup_dir.exists():
            return None
        
        for backup_file in backup_dir.glob(f"{version}_*.j2"):
            return backup_file
        
        return None
    
    def _cache_template(self, name: str, content: str):
        """Cache template content."""
        self.template_cache[name] = {
            'content': content,
            'cached_at': timezone.now(),
            'hits': 0
        }
        
        # Cleanup old cache entries if needed
        if len(self.template_cache) > self.max_cache_size:
            self._cleanup_template_cache()
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        cache_age = timezone.now() - cache_entry['cached_at']
        return cache_age.total_seconds() < self.cache_ttl
    
    def _invalidate_template_cache(self, name: str):
        """Invalidate cache for specific template."""
        self.template_cache.pop(name, None)
    
    def _cleanup_template_cache(self):
        """Cleanup old cache entries."""
        # Remove oldest 20% of entries
        sorted_entries = sorted(
            self.template_cache.items(),
            key=lambda x: x[1]['cached_at']
        )
        
        cleanup_count = max(1, len(sorted_entries) // 5)
        for name, _ in sorted_entries[:cleanup_count]:
            del self.template_cache[name]
    
    def _calculate_cache_hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        if not self.template_cache:
            return 0.0
        
        total_hits = sum(entry.get('hits', 0) for entry in self.template_cache.values())
        total_requests = len(self.template_cache)
        
        return total_hits / max(total_requests, 1)
    
    def _build_dependency_graph(self):
        """Build dependency graph for all templates."""
        self.dependency_graph = {}
        
        for name, metadata in self.template_registry.items():
            self.dependency_graph[name] = metadata.dependencies
    
    def _update_dependency_graph(self, metadata: TemplateMetadata):
        """Update dependency graph for specific template."""
        self.dependency_graph[metadata.name] = metadata.dependencies
    
    def _update_dependency_graph_for_deletion(self, name: str):
        """Update dependency graph when template is deleted."""
        self.dependency_graph.pop(name, None)
    
    def _find_dependent_templates(self, name: str) -> List[str]:
        """Find templates that depend on the given template."""
        dependents = []
        
        for template_name, dependencies in self.dependency_graph.items():
            if name in dependencies:
                dependents.append(template_name)
        
        return dependents
    
    def _archive_template(self, metadata: TemplateMetadata) -> Path:
        """Archive template and metadata."""
        archive_dir = self.base_directory / 'archive' / metadata.name
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        # Archive template file
        template_path = Path(metadata.path)
        if template_path.exists():
            archive_template_path = archive_dir / f"template_{timestamp}.j2"
            shutil.copy2(template_path, archive_template_path)
            template_path.unlink()
        
        # Archive metadata
        metadata_path = self._get_metadata_path(metadata.name)
        if metadata_path.exists():
            archive_metadata_path = archive_dir / f"metadata_{timestamp}.json"
            shutil.copy2(metadata_path, archive_metadata_path)
            metadata_path.unlink()
        
        return archive_dir
    
    def _remove_version_history(self, name: str):
        """Remove version history for template."""
        versions_file = self.versions_directory / f"{name}.json"
        if versions_file.exists():
            versions_file.unlink()
        
        # Remove version backups
        backup_dir = self.versions_directory / name
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
    
    def _find_unused_includes(self, content: str, dependencies: List[str]) -> List[str]:
        """Find includes that are declared but not used."""
        # This is a simplified implementation
        # In practice, this would need more sophisticated analysis
        import re
        
        actual_includes = re.findall(r'{%\s*include\s+["\']([^"\']+)["\']', content)
        unused = [dep for dep in dependencies if dep not in actual_includes]
        
        return unused
    
    def _extract_used_variables(self, content: str) -> List[str]:
        """Extract variables actually used in template."""
        # This is a simplified implementation
        # In practice, this would need AST analysis
        import re
        
        # Find variable references like {{ var }} or {{ var.attr }}
        variables = re.findall(r'{{\s*([a-zA-Z_][a-zA-Z0-9_]*)', content)
        
        return list(set(variables))


# Convenience functions
def create_default_templates(base_directory: Path) -> Dict[str, Any]:
    """Create default templates for common Kubernetes resources."""
    manager = TemplateManager(base_directory)
    
    results = {'created': [], 'errors': []}
    
    # Default VPC template
    vpc_template = """apiVersion: vpc.githedgehog.com/v1beta1
kind: VPC
metadata:
  name: {{ vpc.name | k8s_name }}
  namespace: {{ fabric.name | k8s_name }}
  annotations:
    hnp.githedgehog.com/fabric: "{{ fabric.name }}"
    hnp.githedgehog.com/generated: "{{ now().isoformat() }}"
spec:
  ipv4Namespace: {{ vpc.ipv4_namespace | default('default') }}
  {% if vpc.subnets %}
  subnets:
  {% for subnet in vpc.subnets %}
  - name: {{ subnet.name | k8s_name }}
    subnet: {{ subnet.prefix | format_cidr }}
    {% if subnet.gateway %}
    gateway: {{ subnet.gateway | format_ip }}
    {% endif %}
    {% if subnet.vlan %}
    vlan: {{ subnet.vlan }}
    {% endif %}
  {% endfor %}
  {% endif %}
"""
    
    try:
        result = manager.create_template(
            'vpc-basic',
            vpc_template,
            {
                'description': 'Basic VPC template for Hedgehog fabrics',
                'author': 'system',
                'category': 'vpc',
                'required_resources': ['VPC'],
                'output_pattern': '{{ fabric_name }}/vpcs/{{ vpc.name | k8s_name }}.yaml',
                'tags': ['vpc', 'networking', 'basic']
            }
        )
        
        if result['success']:
            results['created'].append('vpc-basic')
        else:
            results['errors'].append(f"vpc-basic: {result['error']}")
    
    except Exception as e:
        results['errors'].append(f"vpc-basic: {str(e)}")
    
    return results