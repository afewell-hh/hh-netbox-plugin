"""
Schema Validation Engine

Comprehensive Kubernetes YAML schema validation with custom validation rules
for Hedgehog-specific resources, validation error reporting, and schema
version compatibility checking.

This service is part of the Phase 3 Configuration Template Engine that ensures
all generated YAML configurations are valid and compliant.
"""

import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from django.utils import timezone
from django.conf import settings
import jsonschema
from jsonschema import validate, ValidationError, Draft7Validator

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Validation error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationError:
    """Individual validation error."""
    severity: ValidationSeverity
    message: str
    path: str
    rule: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of schema validation."""
    valid: bool
    file_path: str
    schema_version: str
    errors: List[ValidationError]
    warnings: List[ValidationError]
    resource_type: str
    validation_time: float
    schema_used: str


@dataclass
class SchemaInfo:
    """Information about a validation schema."""
    name: str
    version: str
    resource_type: str
    file_path: str
    description: str
    created_at: datetime
    updated_at: datetime
    compatible_versions: List[str]


class SchemaValidator:
    """
    Comprehensive YAML schema validation engine for Kubernetes resources.
    
    Features:
    - Kubernetes YAML schema validation
    - Custom validation rules for Hedgehog-specific resources
    - Validation error reporting with suggestions
    - Schema version compatibility checking
    - Performance-optimized validation pipeline
    - Multi-document YAML support
    """
    
    def __init__(self, schemas_directory: Union[str, Path] = None):
        self.schemas_directory = Path(schemas_directory) if schemas_directory else self._get_default_schemas_directory()
        
        # Initialize schema registry
        self.schema_registry = {}
        self.custom_validators = {}
        
        # Load schemas
        self._load_schemas()
        
        # Validation configuration
        self.strict_mode = getattr(settings, 'SCHEMA_VALIDATION_STRICT', True)
        self.max_validation_time = getattr(settings, 'SCHEMA_MAX_VALIDATION_TIME', 5.0)  # 5 seconds
        self.enable_suggestions = getattr(settings, 'SCHEMA_ENABLE_SUGGESTIONS', True)
        
        # Performance tracking
        self.validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'average_validation_time': 0.0
        }
        
        # Custom rules registry
        self._register_hedgehog_validators()
        
        logger.info(f"Schema validator initialized with {len(self.schema_registry)} schemas")
    
    def validate_file(self, file_path: Union[str, Path]) -> ValidationResult:
        """
        Validate a YAML file against appropriate schemas.
        
        Args:
            file_path: Path to YAML file to validate
            
        Returns:
            ValidationResult with detailed validation information
        """
        file_path = Path(file_path)
        start_time = timezone.now()
        
        logger.debug(f"Validating file: {file_path}")
        
        result = ValidationResult(
            valid=True,
            file_path=str(file_path),
            schema_version="unknown",
            errors=[],
            warnings=[],
            resource_type="unknown",
            validation_time=0.0,
            schema_used="none"
        )
        
        try:
            # Check if file exists
            if not file_path.exists():
                result.valid = False
                result.errors.append(ValidationError(
                    severity=ValidationSeverity.CRITICAL,
                    message=f"File not found: {file_path}",
                    path=str(file_path),
                    rule="file_existence"
                ))
                return result
            
            # Load and parse YAML
            yaml_documents = self._load_yaml_file(file_path)
            if not yaml_documents:
                result.valid = False
                result.errors.append(ValidationError(
                    severity=ValidationSeverity.ERROR,
                    message="No valid YAML documents found",
                    path=str(file_path),
                    rule="yaml_parsing"
                ))
                return result
            
            # Validate each document
            all_valid = True
            for doc_index, document in enumerate(yaml_documents):
                if document is None:
                    continue
                
                doc_result = self._validate_document(document, file_path, doc_index)
                
                # Merge results
                if not doc_result['valid']:
                    all_valid = False
                
                result.errors.extend(doc_result['errors'])
                result.warnings.extend(doc_result['warnings'])
                
                # Update result metadata from first valid document
                if doc_index == 0 or result.resource_type == "unknown":
                    result.resource_type = doc_result.get('resource_type', 'unknown')
                    result.schema_version = doc_result.get('schema_version', 'unknown')
                    result.schema_used = doc_result.get('schema_used', 'none')
            
            result.valid = all_valid and len([e for e in result.errors if e.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]]) == 0
            result.validation_time = (timezone.now() - start_time).total_seconds()
            
            # Update statistics
            self._update_validation_stats(result)
            
            logger.debug(f"Validation completed for {file_path}: valid={result.valid}, "
                        f"errors={len(result.errors)}, warnings={len(result.warnings)}")
            
            return result
            
        except Exception as e:
            result.valid = False
            result.validation_time = (timezone.now() - start_time).total_seconds()
            result.errors.append(ValidationError(
                severity=ValidationSeverity.CRITICAL,
                message=f"Validation failed: {str(e)}",
                path=str(file_path),
                rule="validation_exception"
            ))
            
            logger.error(f"Validation failed for {file_path}: {str(e)}")
            return result
    
    def validate_content(self, yaml_content: str, content_type: str = "yaml") -> ValidationResult:
        """
        Validate YAML content directly.
        
        Args:
            yaml_content: YAML content as string
            content_type: Type of content (yaml, json)
            
        Returns:
            ValidationResult with validation information
        """
        start_time = timezone.now()
        
        result = ValidationResult(
            valid=True,
            file_path="<content>",
            schema_version="unknown",
            errors=[],
            warnings=[],
            resource_type="unknown",
            validation_time=0.0,
            schema_used="none"
        )
        
        try:
            # Parse content
            if content_type.lower() == "json":
                documents = [json.loads(yaml_content)]
            else:
                documents = list(yaml.safe_load_all(yaml_content))
            
            # Validate each document
            all_valid = True
            for doc_index, document in enumerate(documents):
                if document is None:
                    continue
                
                doc_result = self._validate_document(document, "<content>", doc_index)
                
                if not doc_result['valid']:
                    all_valid = False
                
                result.errors.extend(doc_result['errors'])
                result.warnings.extend(doc_result['warnings'])
                
                if doc_index == 0:
                    result.resource_type = doc_result.get('resource_type', 'unknown')
                    result.schema_version = doc_result.get('schema_version', 'unknown')
                    result.schema_used = doc_result.get('schema_used', 'none')
            
            result.valid = all_valid and len([e for e in result.errors if e.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]]) == 0
            result.validation_time = (timezone.now() - start_time).total_seconds()
            
            return result
            
        except Exception as e:
            result.valid = False
            result.validation_time = (timezone.now() - start_time).total_seconds()
            result.errors.append(ValidationError(
                severity=ValidationSeverity.CRITICAL,
                message=f"Content validation failed: {str(e)}",
                path="<content>",
                rule="content_parsing"
            ))
            return result
    
    def validate_resource(self, resource_dict: Dict[str, Any]) -> ValidationResult:
        """
        Validate a Kubernetes resource dictionary.
        
        Args:
            resource_dict: Resource as dictionary
            
        Returns:
            ValidationResult with validation information
        """
        start_time = timezone.now()
        
        result = ValidationResult(
            valid=True,
            file_path="<resource>",
            schema_version="unknown",
            errors=[],
            warnings=[],
            resource_type="unknown",
            validation_time=0.0,
            schema_used="none"
        )
        
        try:
            doc_result = self._validate_document(resource_dict, "<resource>", 0)
            
            result.valid = doc_result['valid']
            result.errors = doc_result['errors']
            result.warnings = doc_result['warnings']
            result.resource_type = doc_result.get('resource_type', 'unknown')
            result.schema_version = doc_result.get('schema_version', 'unknown')
            result.schema_used = doc_result.get('schema_used', 'none')
            result.validation_time = (timezone.now() - start_time).total_seconds()
            
            return result
            
        except Exception as e:
            result.valid = False
            result.validation_time = (timezone.now() - start_time).total_seconds()
            result.errors.append(ValidationError(
                severity=ValidationSeverity.CRITICAL,
                message=f"Resource validation failed: {str(e)}",
                path="<resource>",
                rule="resource_validation"
            ))
            return result
    
    def get_available_schemas(self) -> List[SchemaInfo]:
        """Get list of available schemas."""
        schemas = []
        for schema_name, schema_data in self.schema_registry.items():
            schema_info = SchemaInfo(
                name=schema_name,
                version=schema_data.get('version', 'unknown'),
                resource_type=schema_data.get('resource_type', 'unknown'),
                file_path=schema_data.get('file_path', ''),
                description=schema_data.get('description', ''),
                created_at=schema_data.get('created_at', timezone.now()),
                updated_at=schema_data.get('updated_at', timezone.now()),
                compatible_versions=schema_data.get('compatible_versions', [])
            )
            schemas.append(schema_info)
        
        return schemas
    
    def register_custom_validator(self, name: str, validator_func) -> bool:
        """
        Register a custom validation function.
        
        Args:
            name: Validator name
            validator_func: Function that takes (document, path) and returns list of ValidationErrors
            
        Returns:
            True if registered successfully
        """
        try:
            self.custom_validators[name] = validator_func
            logger.info(f"Registered custom validator: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to register custom validator {name}: {str(e)}")
            return False
    
    def add_schema(self, name: str, schema_content: Dict[str, Any], 
                   resource_type: str = None) -> bool:
        """
        Add a custom schema to the registry.
        
        Args:
            name: Schema name
            schema_content: JSON schema content
            resource_type: Associated Kubernetes resource type
            
        Returns:
            True if added successfully
        """
        try:
            # Validate the schema itself
            Draft7Validator.check_schema(schema_content)
            
            self.schema_registry[name] = {
                'schema': schema_content,
                'resource_type': resource_type or 'custom',
                'version': schema_content.get('version', '1.0'),
                'description': schema_content.get('description', ''),
                'created_at': timezone.now(),
                'updated_at': timezone.now(),
                'file_path': f'<custom:{name}>',
                'compatible_versions': []
            }
            
            logger.info(f"Added custom schema: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add custom schema {name}: {str(e)}")
            return False
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return self.validation_stats.copy()
    
    def suggest_fixes(self, validation_result: ValidationResult) -> List[Dict[str, Any]]:
        """
        Generate fix suggestions for validation errors.
        
        Args:
            validation_result: Result containing validation errors
            
        Returns:
            List of fix suggestions
        """
        suggestions = []
        
        for error in validation_result.errors:
            if error.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
                suggestion = self._generate_fix_suggestion(error)
                if suggestion:
                    suggestions.append({
                        'error': asdict(error),
                        'suggestion': suggestion
                    })
        
        return suggestions
    
    # Private methods
    
    def _get_default_schemas_directory(self) -> Path:
        """Get default schemas directory."""
        schemas_dir = getattr(settings, 'HEDGEHOG_VALIDATION_SCHEMAS_DIR', None)
        if schemas_dir:
            return Path(schemas_dir)
        
        # Fallback to plugin directory
        plugin_dir = Path(__file__).parent.parent
        return plugin_dir / 'schemas' / 'validation'
    
    def _load_schemas(self):
        """Load validation schemas from directory."""
        try:
            self.schemas_directory.mkdir(parents=True, exist_ok=True)
            
            # Load built-in Kubernetes schemas
            self._load_kubernetes_schemas()
            
            # Load custom schemas from files
            for schema_file in self.schemas_directory.glob('*.json'):
                try:
                    with open(schema_file, 'r', encoding='utf-8') as f:
                        schema_content = json.load(f)
                    
                    schema_name = schema_file.stem
                    self.schema_registry[schema_name] = {
                        'schema': schema_content,
                        'resource_type': schema_content.get('x-kubernetes-group-version-kind', [{}])[0].get('kind', 'unknown'),
                        'version': schema_content.get('version', '1.0'),
                        'description': schema_content.get('description', ''),
                        'created_at': datetime.fromtimestamp(schema_file.stat().st_ctime),
                        'updated_at': datetime.fromtimestamp(schema_file.stat().st_mtime),
                        'file_path': str(schema_file),
                        'compatible_versions': schema_content.get('compatible_versions', [])
                    }
                    
                except Exception as e:
                    logger.warning(f"Failed to load schema from {schema_file}: {str(e)}")
            
            logger.info(f"Loaded {len(self.schema_registry)} validation schemas")
            
        except Exception as e:
            logger.error(f"Failed to load schemas: {str(e)}")
    
    def _load_kubernetes_schemas(self):
        """Load built-in Kubernetes schemas."""
        # Built-in basic Kubernetes resource schema
        basic_k8s_schema = {
            "type": "object",
            "required": ["apiVersion", "kind", "metadata"],
            "properties": {
                "apiVersion": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9]+(/[a-zA-Z0-9]+)*$"
                },
                "kind": {
                    "type": "string",
                    "minLength": 1
                },
                "metadata": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                            "maxLength": 253
                        },
                        "namespace": {
                            "type": "string",
                            "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                            "maxLength": 63
                        },
                        "labels": {
                            "type": "object",
                            "patternProperties": {
                                "^[a-zA-Z0-9]([a-zA-Z0-9._/-]*[a-zA-Z0-9])?$": {
                                    "type": "string",
                                    "maxLength": 63
                                }
                            }
                        },
                        "annotations": {
                            "type": "object",
                            "patternProperties": {
                                "^[a-zA-Z0-9]([a-zA-Z0-9._/-]*[a-zA-Z0-9])?$": {
                                    "type": "string"
                                }
                            }
                        }
                    }
                },
                "spec": {
                    "type": "object"
                },
                "status": {
                    "type": "object"
                }
            }
        }
        
        self.schema_registry['kubernetes-base'] = {
            'schema': basic_k8s_schema,
            'resource_type': 'base',
            'version': '1.0',
            'description': 'Basic Kubernetes resource validation',
            'created_at': timezone.now(),
            'updated_at': timezone.now(),
            'file_path': '<builtin>',
            'compatible_versions': []
        }
        
        # Hedgehog VPC schema
        vpc_schema = {
            "type": "object",
            "required": ["apiVersion", "kind", "metadata", "spec"],
            "properties": {
                "apiVersion": {
                    "type": "string",
                    "enum": ["vpc.githedgehog.com/v1beta1"]
                },
                "kind": {
                    "type": "string",
                    "enum": ["VPC"]
                },
                "metadata": {
                    "$ref": "#/definitions/metadata"
                },
                "spec": {
                    "type": "object",
                    "properties": {
                        "ipv4Namespace": {
                            "type": "string"
                        },
                        "subnets": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["name", "subnet"],
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
                                    },
                                    "subnet": {
                                        "type": "string",
                                        "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$"
                                    },
                                    "gateway": {
                                        "type": "string",
                                        "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}$"
                                    },
                                    "vlan": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 4094
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "definitions": {
                "metadata": basic_k8s_schema["properties"]["metadata"]
            }
        }
        
        self.schema_registry['hedgehog-vpc'] = {
            'schema': vpc_schema,
            'resource_type': 'VPC',
            'version': '1.0',
            'description': 'Hedgehog VPC resource validation',
            'created_at': timezone.now(),
            'updated_at': timezone.now(),
            'file_path': '<builtin>',
            'compatible_versions': []
        }
    
    def _register_hedgehog_validators(self):
        """Register custom validators for Hedgehog resources."""
        
        def validate_hedgehog_annotations(document: Dict[str, Any], path: str) -> List[ValidationError]:
            """Validate Hedgehog-specific annotations."""
            errors = []
            
            annotations = document.get('metadata', {}).get('annotations', {})
            
            # Check for required Hedgehog annotations
            required_annotations = [
                'hnp.githedgehog.com/fabric'
            ]
            
            for required_ann in required_annotations:
                if required_ann not in annotations:
                    errors.append(ValidationError(
                        severity=ValidationSeverity.WARNING,
                        message=f"Missing recommended annotation: {required_ann}",
                        path=f"{path}.metadata.annotations",
                        rule="hedgehog_annotations",
                        suggestion=f"Add annotation: {required_ann}: \"<fabric_name>\""
                    ))
            
            return errors
        
        def validate_resource_naming(document: Dict[str, Any], path: str) -> List[ValidationError]:
            """Validate Kubernetes resource naming conventions."""
            errors = []
            
            name = document.get('metadata', {}).get('name', '')
            if name:
                # Check DNS-1123 compliance
                import re
                if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', name):
                    errors.append(ValidationError(
                        severity=ValidationSeverity.ERROR,
                        message=f"Resource name '{name}' is not DNS-1123 compliant",
                        path=f"{path}.metadata.name",
                        rule="resource_naming",
                        suggestion="Use lowercase alphanumeric characters and hyphens only"
                    ))
                
                if len(name) > 253:
                    errors.append(ValidationError(
                        severity=ValidationSeverity.ERROR,
                        message=f"Resource name too long: {len(name)} characters (max 253)",
                        path=f"{path}.metadata.name",
                        rule="resource_naming",
                        suggestion="Shorten the resource name"
                    ))
            
            return errors
        
        def validate_vpc_subnets(document: Dict[str, Any], path: str) -> List[ValidationError]:
            """Validate VPC subnet configurations."""
            errors = []
            
            if document.get('kind') != 'VPC':
                return errors
            
            subnets = document.get('spec', {}).get('subnets', [])
            subnet_names = set()
            subnet_cidrs = set()
            
            for i, subnet in enumerate(subnets):
                subnet_path = f"{path}.spec.subnets[{i}]"
                
                # Check for duplicate names
                subnet_name = subnet.get('name', '')
                if subnet_name in subnet_names:
                    errors.append(ValidationError(
                        severity=ValidationSeverity.ERROR,
                        message=f"Duplicate subnet name: {subnet_name}",
                        path=f"{subnet_path}.name",
                        rule="vpc_subnets",
                        suggestion="Use unique subnet names"
                    ))
                subnet_names.add(subnet_name)
                
                # Check for overlapping CIDRs
                subnet_cidr = subnet.get('subnet', '')
                if subnet_cidr in subnet_cidrs:
                    errors.append(ValidationError(
                        severity=ValidationSeverity.ERROR,
                        message=f"Duplicate subnet CIDR: {subnet_cidr}",
                        path=f"{subnet_path}.subnet",
                        rule="vpc_subnets",
                        suggestion="Use unique subnet CIDRs"
                    ))
                subnet_cidrs.add(subnet_cidr)
                
                # Validate VLAN range
                vlan = subnet.get('vlan')
                if vlan is not None and (vlan < 1 or vlan > 4094):
                    errors.append(ValidationError(
                        severity=ValidationSeverity.ERROR,
                        message=f"Invalid VLAN ID: {vlan} (must be 1-4094)",
                        path=f"{subnet_path}.vlan",
                        rule="vpc_subnets",
                        suggestion="Use VLAN ID between 1 and 4094"
                    ))
            
            return errors
        
        # Register validators
        self.custom_validators['hedgehog_annotations'] = validate_hedgehog_annotations
        self.custom_validators['resource_naming'] = validate_resource_naming
        self.custom_validators['vpc_subnets'] = validate_vpc_subnets
    
    def _load_yaml_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load and parse YAML file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                documents = list(yaml.safe_load_all(f))
            return [doc for doc in documents if doc is not None]
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {file_path}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Failed to load YAML file {file_path}: {str(e)}")
            return []
    
    def _validate_document(self, document: Dict[str, Any], file_path: str, 
                         doc_index: int) -> Dict[str, Any]:
        """Validate a single YAML document."""
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'resource_type': 'unknown',
            'schema_version': 'unknown',
            'schema_used': 'none'
        }
        
        try:
            # Determine resource type
            kind = document.get('kind', 'unknown')
            api_version = document.get('apiVersion', 'unknown')
            result['resource_type'] = kind
            
            # Find appropriate schema
            schema_info = self._find_schema_for_resource(kind, api_version)
            if schema_info:
                result['schema_used'] = schema_info['name']
                result['schema_version'] = schema_info['version']
                
                # Validate against schema
                schema_errors = self._validate_against_schema(document, schema_info, file_path, doc_index)
                result['errors'].extend(schema_errors)
            else:
                # Use base Kubernetes schema as fallback
                base_schema = self.schema_registry.get('kubernetes-base')
                if base_schema:
                    result['schema_used'] = 'kubernetes-base'
                    result['schema_version'] = base_schema['version']
                    
                    schema_errors = self._validate_against_schema(document, base_schema, file_path, doc_index)
                    result['errors'].extend(schema_errors)
                else:
                    result['warnings'].append(ValidationError(
                        severity=ValidationSeverity.WARNING,
                        message=f"No schema found for resource type: {kind}",
                        path=f"document[{doc_index}]",
                        rule="schema_availability"
                    ))
            
            # Run custom validators
            custom_errors = self._run_custom_validators(document, f"document[{doc_index}]")
            result['errors'].extend(custom_errors)
            
            # Check if validation passed
            critical_errors = [e for e in result['errors'] if e.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]]
            result['valid'] = len(critical_errors) == 0
            
            return result
            
        except Exception as e:
            result['valid'] = False
            result['errors'].append(ValidationError(
                severity=ValidationSeverity.CRITICAL,
                message=f"Document validation failed: {str(e)}",
                path=f"document[{doc_index}]",
                rule="document_validation"
            ))
            return result
    
    def _find_schema_for_resource(self, kind: str, api_version: str) -> Optional[Dict[str, Any]]:
        """Find appropriate schema for a Kubernetes resource."""
        # Try exact match first
        for schema_name, schema_info in self.schema_registry.items():
            if schema_info['resource_type'] == kind:
                schema = schema_info.get('schema', {})
                supported_apis = schema.get('properties', {}).get('apiVersion', {}).get('enum', [])
                if api_version in supported_apis or not supported_apis:
                    return {**schema_info, 'name': schema_name}
        
        # Try partial matches
        for schema_name, schema_info in self.schema_registry.items():
            if kind.lower() in schema_info['resource_type'].lower():
                return {**schema_info, 'name': schema_name}
        
        return None
    
    def _validate_against_schema(self, document: Dict[str, Any], schema_info: Dict[str, Any],
                               file_path: str, doc_index: int) -> List[ValidationError]:
        """Validate document against JSON schema."""
        errors = []
        
        try:
            schema = schema_info['schema']
            validator = Draft7Validator(schema)
            
            # Perform validation
            for error in validator.iter_errors(document):
                severity = ValidationSeverity.ERROR
                
                # Adjust severity based on error type
                if 'required' in error.message.lower():
                    severity = ValidationSeverity.CRITICAL
                elif 'pattern' in error.message.lower():
                    severity = ValidationSeverity.ERROR
                elif 'additional' in error.message.lower():
                    severity = ValidationSeverity.WARNING
                
                validation_error = ValidationError(
                    severity=severity,
                    message=error.message,
                    path=f"document[{doc_index}].{'.'.join(str(p) for p in error.path)}",
                    rule="json_schema",
                    suggestion=self._generate_schema_suggestion(error)
                )
                
                errors.append(validation_error)
            
            return errors
            
        except Exception as e:
            logger.error(f"Schema validation error: {str(e)}")
            return [ValidationError(
                severity=ValidationSeverity.CRITICAL,
                message=f"Schema validation failed: {str(e)}",
                path=f"document[{doc_index}]",
                rule="schema_validation"
            )]
    
    def _run_custom_validators(self, document: Dict[str, Any], path: str) -> List[ValidationError]:
        """Run custom validation functions."""
        errors = []
        
        for validator_name, validator_func in self.custom_validators.items():
            try:
                validator_errors = validator_func(document, path)
                if validator_errors:
                    errors.extend(validator_errors)
            except Exception as e:
                logger.warning(f"Custom validator {validator_name} failed: {str(e)}")
                errors.append(ValidationError(
                    severity=ValidationSeverity.WARNING,
                    message=f"Custom validator failed: {validator_name}",
                    path=path,
                    rule=validator_name
                ))
        
        return errors
    
    def _generate_schema_suggestion(self, schema_error) -> Optional[str]:
        """Generate suggestion for schema validation error."""
        if not self.enable_suggestions:
            return None
        
        error_msg = schema_error.message.lower()
        
        if 'required' in error_msg:
            return "Add the required field to your resource definition"
        elif 'pattern' in error_msg:
            return "Check the field format against the required pattern"
        elif 'additional' in error_msg:
            return "Remove the additional property or check for typos"
        elif 'enum' in error_msg:
            return "Use one of the allowed values"
        elif 'type' in error_msg:
            return "Check the field type (string, number, boolean, etc.)"
        
        return None
    
    def _generate_fix_suggestion(self, error: ValidationError) -> Optional[str]:
        """Generate fix suggestion for validation error."""
        if error.suggestion:
            return error.suggestion
        
        if error.rule == 'resource_naming':
            return "Use lowercase letters, numbers, and hyphens. Start and end with alphanumeric characters."
        elif error.rule == 'hedgehog_annotations':
            return "Add the recommended Hedgehog annotations for proper resource management."
        elif error.rule == 'vpc_subnets':
            return "Check subnet names and CIDR blocks for uniqueness and validity."
        
        return None
    
    def _update_validation_stats(self, result: ValidationResult):
        """Update validation statistics."""
        self.validation_stats['total_validations'] += 1
        
        if result.valid:
            self.validation_stats['successful_validations'] += 1
        else:
            self.validation_stats['failed_validations'] += 1
        
        # Update rolling average validation time
        total = self.validation_stats['total_validations']
        current_avg = self.validation_stats['average_validation_time']
        self.validation_stats['average_validation_time'] = (
            (current_avg * (total - 1) + result.validation_time) / total
        )


# Convenience functions
def validate_yaml_file(file_path: Union[str, Path]) -> ValidationResult:
    """Convenience function to validate a YAML file."""
    validator = SchemaValidator()
    return validator.validate_file(file_path)


def validate_yaml_content(content: str) -> ValidationResult:
    """Convenience function to validate YAML content."""
    validator = SchemaValidator()
    return validator.validate_content(content)


def create_default_schemas(schemas_directory: Path) -> Dict[str, Any]:
    """Create default validation schemas."""
    results = {'created': [], 'errors': []}
    
    try:
        schemas_directory.mkdir(parents=True, exist_ok=True)
        
        # Create basic VPC schema file
        vpc_schema_path = schemas_directory / 'vpc.json'
        if not vpc_schema_path.exists():
            vpc_schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "title": "Hedgehog VPC Resource",
                "type": "object",
                "required": ["apiVersion", "kind", "metadata", "spec"],
                "properties": {
                    "apiVersion": {
                        "type": "string",
                        "enum": ["vpc.githedgehog.com/v1beta1"]
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["VPC"]
                    },
                    "metadata": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {
                                "type": "string",
                                "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                                "maxLength": 253
                            },
                            "namespace": {
                                "type": "string",
                                "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                                "maxLength": 63
                            }
                        }
                    },
                    "spec": {
                        "type": "object",
                        "properties": {
                            "ipv4Namespace": {
                                "type": "string"
                            },
                            "subnets": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["name", "subnet"],
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
                                        },
                                        "subnet": {
                                            "type": "string",
                                            "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$"
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "version": "1.0",
                "description": "Schema for Hedgehog VPC resources"
            }
            
            with open(vpc_schema_path, 'w', encoding='utf-8') as f:
                json.dump(vpc_schema, f, indent=2)
            
            results['created'].append('vpc.json')
        
        return results
        
    except Exception as e:
        results['errors'].append(f"Failed to create schemas: {str(e)}")
        return results