"""
Database State Validators for GUI Testing

This module provides comprehensive database validation utilities for verifying
UI operations against database state. It includes CRUD operation validators,
relationship integrity checkers, and state comparison utilities for all models.
"""

from typing import Dict, Any, List, Optional, Tuple, Union, Set
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q, F, Count
import json
import copy
from datetime import datetime


class DatabaseStateValidator:
    """
    Main validator class for database state verification during GUI testing.
    Provides comprehensive CRUD operation validation and relationship integrity checking.
    """

    def __init__(self):
        """Initialize validator with model registry."""
        self.model_registry = self._build_model_registry()
        self.validation_history = []

    def _build_model_registry(self) -> Dict[str, Any]:
        """Build registry of all Hedgehog models for validation."""
        from netbox_hedgehog.models.base import BaseCRD
        from netbox_hedgehog.models.fabric import HedgehogFabric
        from netbox_hedgehog.models.git_repository import GitRepository
        from netbox_hedgehog.models.gitops import HedgehogResource, StateTransitionHistory
        from netbox_hedgehog.models.reconciliation import ReconciliationAlert
        from netbox_hedgehog.models.vpc_api import (
            VPC, External, ExternalAttachment, ExternalPeering,
            IPv4Namespace, VPCAttachment, VPCPeering
        )
        from netbox_hedgehog.models.wiring_api import (
            Connection, Server, Switch, SwitchGroup, VLANNamespace
        )

        return {
            'BaseCRD': BaseCRD,
            'HedgehogFabric': HedgehogFabric,
            'GitRepository': GitRepository,
            'HedgehogResource': HedgehogResource,
            'StateTransitionHistory': StateTransitionHistory,
            'ReconciliationAlert': ReconciliationAlert,
            'VPC': VPC,
            'External': External,
            'ExternalAttachment': ExternalAttachment,
            'ExternalPeering': ExternalPeering,
            'IPv4Namespace': IPv4Namespace,
            'VPCAttachment': VPCAttachment,
            'VPCPeering': VPCPeering,
            'Connection': Connection,
            'Server': Server,
            'Switch': Switch,
            'SwitchGroup': SwitchGroup,
            'VLANNamespace': VLANNamespace,
        }

    def capture_database_state(self) -> Dict[str, Any]:
        """Capture complete database state for all models."""
        state = {
            'timestamp': datetime.now().isoformat(),
            'models': {},
            'counts': {}
        }

        for model_name, model_class in self.model_registry.items():
            try:
                objects = list(model_class.objects.all().values())
                state['models'][model_name] = objects
                state['counts'][model_name] = len(objects)
            except Exception as e:
                state['models'][model_name] = f"Error: {str(e)}"
                state['counts'][model_name] = 0

        return state

    def compare_database_states(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two database states and return differences."""
        comparison = {
            'timestamp': datetime.now().isoformat(),
            'changes_detected': False,
            'count_changes': {},
            'model_changes': {},
            'summary': {}
        }

        # Compare counts
        for model_name in self.model_registry.keys():
            before_count = before['counts'].get(model_name, 0)
            after_count = after['counts'].get(model_name, 0)
            
            if before_count != after_count:
                comparison['changes_detected'] = True
                comparison['count_changes'][model_name] = {
                    'before': before_count,
                    'after': after_count,
                    'diff': after_count - before_count
                }

        # Compare model data
        for model_name in self.model_registry.keys():
            before_objects = before['models'].get(model_name, [])
            after_objects = after['models'].get(model_name, [])
            
            if isinstance(before_objects, list) and isinstance(after_objects, list):
                changes = self._compare_object_lists(before_objects, after_objects)
                if changes['has_changes']:
                    comparison['changes_detected'] = True
                    comparison['model_changes'][model_name] = changes

        # Generate summary
        comparison['summary'] = {
            'models_changed': len(comparison['model_changes']),
            'count_changes': len(comparison['count_changes']),
            'total_changes': len(comparison['model_changes']) + len(comparison['count_changes'])
        }

        return comparison

    def _compare_object_lists(self, before: List[Dict], after: List[Dict]) -> Dict[str, Any]:
        """Compare two lists of object dictionaries."""
        changes = {
            'has_changes': False,
            'created': [],
            'updated': [],
            'deleted': [],
            'field_changes': {}
        }

        # Convert to dictionaries keyed by ID for easier comparison
        before_dict = {obj.get('id'): obj for obj in before if obj.get('id')}
        after_dict = {obj.get('id'): obj for obj in after if obj.get('id')}

        # Find created objects
        created_ids = set(after_dict.keys()) - set(before_dict.keys())
        for obj_id in created_ids:
            changes['has_changes'] = True
            changes['created'].append(after_dict[obj_id])

        # Find deleted objects  
        deleted_ids = set(before_dict.keys()) - set(after_dict.keys())
        for obj_id in deleted_ids:
            changes['has_changes'] = True
            changes['deleted'].append(before_dict[obj_id])

        # Find updated objects
        common_ids = set(before_dict.keys()) & set(after_dict.keys())
        for obj_id in common_ids:
            before_obj = before_dict[obj_id]
            after_obj = after_dict[obj_id]
            
            field_diffs = self._compare_objects(before_obj, after_obj)
            if field_diffs:
                changes['has_changes'] = True
                changes['updated'].append({
                    'id': obj_id,
                    'changes': field_diffs
                })
                changes['field_changes'][obj_id] = field_diffs

        return changes

    def _compare_objects(self, before: Dict, after: Dict) -> Dict[str, Any]:
        """Compare two object dictionaries and return field differences."""
        differences = {}
        
        all_keys = set(before.keys()) | set(after.keys())
        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)
            
            if before_val != after_val:
                differences[key] = {
                    'before': before_val,
                    'after': after_val
                }
        
        return differences


class CRUDOperationValidator:
    """Validator for CRUD operations on database models."""

    def __init__(self, database_validator: DatabaseStateValidator):
        self.db_validator = database_validator
        self.model_registry = database_validator.model_registry

    def validate_create_operation(self, model_name: str, expected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that a create operation was successful."""
        if model_name not in self.model_registry:
            return {'success': False, 'error': f'Unknown model: {model_name}'}

        model_class = self.model_registry[model_name]
        
        try:
            # Find the created object
            created_obj = self._find_created_object(model_class, expected_data)
            if not created_obj:
                return {'success': False, 'error': 'Created object not found'}

            # Validate field values
            validation_result = self._validate_object_fields(created_obj, expected_data)
            
            return {
                'success': True,
                'object_id': created_obj.id,
                'field_validation': validation_result,
                'created_object': self._serialize_object(created_obj)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def validate_update_operation(self, model_name: str, object_id: int, 
                                 expected_changes: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that an update operation was successful."""
        if model_name not in self.model_registry:
            return {'success': False, 'error': f'Unknown model: {model_name}'}

        model_class = self.model_registry[model_name]
        
        try:
            # Get the updated object
            updated_obj = model_class.objects.get(id=object_id)
            
            # Validate updated field values
            validation_result = self._validate_object_fields(updated_obj, expected_changes)
            
            return {
                'success': True,
                'object_id': object_id,
                'field_validation': validation_result,
                'updated_object': self._serialize_object(updated_obj)
            }
            
        except ObjectDoesNotExist:
            return {'success': False, 'error': 'Object not found after update'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def validate_delete_operation(self, model_name: str, object_id: int) -> Dict[str, Any]:
        """Validate that a delete operation was successful."""
        if model_name not in self.model_registry:
            return {'success': False, 'error': f'Unknown model: {model_name}'}

        model_class = self.model_registry[model_name]
        
        try:
            # Verify object is deleted
            model_class.objects.get(id=object_id)
            return {'success': False, 'error': 'Object still exists after delete'}
            
        except ObjectDoesNotExist:
            return {'success': True, 'object_id': object_id}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _find_created_object(self, model_class: models.Model, expected_data: Dict[str, Any]) -> Optional[models.Model]:
        """Find a recently created object based on expected data."""
        # Try to find by unique fields first
        unique_fields = getattr(model_class._meta, 'unique_together', [])
        
        if unique_fields:
            filter_kwargs = {}
            for field_set in unique_fields:
                if isinstance(field_set, (list, tuple)):
                    for field in field_set:
                        if field in expected_data:
                            filter_kwargs[field] = expected_data[field]
                    break
            
            if filter_kwargs:
                return model_class.objects.filter(**filter_kwargs).first()

        # Fall back to name-based search
        if 'name' in expected_data:
            return model_class.objects.filter(name=expected_data['name']).first()

        # Last resort: most recent object
        return model_class.objects.last()

    def _validate_object_fields(self, obj: models.Model, expected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate object fields against expected data."""
        validation_result = {
            'valid_fields': [],
            'invalid_fields': [],
            'missing_fields': [],
            'success': True
        }

        for field_name, expected_value in expected_data.items():
            if hasattr(obj, field_name):
                actual_value = getattr(obj, field_name)
                
                # Handle foreign key relationships
                if hasattr(actual_value, 'id'):
                    actual_value = actual_value.id

                if actual_value == expected_value:
                    validation_result['valid_fields'].append(field_name)
                else:
                    validation_result['invalid_fields'].append({
                        'field': field_name,
                        'expected': expected_value,
                        'actual': actual_value
                    })
                    validation_result['success'] = False
            else:
                validation_result['missing_fields'].append(field_name)

        return validation_result

    def _serialize_object(self, obj: models.Model) -> Dict[str, Any]:
        """Serialize a model object to dictionary."""
        data = {}
        for field in obj._meta.fields:
            value = getattr(obj, field.name)
            
            # Handle foreign keys
            if hasattr(value, 'id'):
                data[field.name] = value.id
            # Handle datetime fields
            elif hasattr(value, 'isoformat'):
                data[field.name] = value.isoformat()
            else:
                data[field.name] = value
                
        return data


class RelationshipValidator:
    """Validator for relationship integrity between models."""

    def __init__(self, database_validator: DatabaseStateValidator):
        self.db_validator = database_validator
        self.model_registry = database_validator.model_registry

    def validate_fabric_relationships(self, fabric_id: int) -> Dict[str, Any]:
        """Validate all relationships for a HedgehogFabric."""
        try:
            fabric = self.model_registry['HedgehogFabric'].objects.get(id=fabric_id)
            
            validation_result = {
                'fabric_id': fabric_id,
                'fabric_name': fabric.name,
                'relationships': {},
                'success': True,
                'errors': []
            }

            # Check GitRepository relationship
            if fabric.git_repository:
                validation_result['relationships']['git_repository'] = {
                    'exists': True,
                    'repository_id': fabric.git_repository.id,
                    'repository_name': fabric.git_repository.name
                }
            else:
                validation_result['relationships']['git_repository'] = {'exists': False}

            # Check related models
            related_models = [
                ('vpc_set', 'VPC'),
                ('server_set', 'Server'),
                ('switch_set', 'Switch'),
                ('connection_set', 'Connection'),
                ('gitops_resources', 'HedgehogResource'),
                ('reconciliation_alerts', 'ReconciliationAlert')
            ]

            for relation_name, model_name in related_models:
                try:
                    related_objects = getattr(fabric, relation_name).all()
                    validation_result['relationships'][relation_name] = {
                        'count': related_objects.count(),
                        'ids': [obj.id for obj in related_objects]
                    }
                except Exception as e:
                    validation_result['relationships'][relation_name] = {
                        'error': str(e)
                    }
                    validation_result['success'] = False
                    validation_result['errors'].append(f"{relation_name}: {str(e)}")

            return validation_result

        except ObjectDoesNotExist:
            return {'success': False, 'error': 'Fabric not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def validate_git_repository_relationships(self, repository_id: int) -> Dict[str, Any]:
        """Validate all relationships for a GitRepository."""
        try:
            repository = self.model_registry['GitRepository'].objects.get(id=repository_id)
            
            validation_result = {
                'repository_id': repository_id,
                'repository_name': repository.name,
                'relationships': {},
                'success': True,
                'errors': []
            }

            # Check Fabric relationships
            fabrics = repository.fabrics.all()
            validation_result['relationships']['fabrics'] = {
                'count': fabrics.count(),
                'fabric_ids': [fabric.id for fabric in fabrics],
                'fabric_names': [fabric.name for fabric in fabrics]
            }

            # Check created_by relationship
            if repository.created_by:
                validation_result['relationships']['created_by'] = {
                    'exists': True,
                    'user_id': repository.created_by.id,
                    'username': repository.created_by.username
                }
            else:
                validation_result['relationships']['created_by'] = {'exists': False}

            return validation_result

        except ObjectDoesNotExist:
            return {'success': False, 'error': 'Repository not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def validate_bidirectional_relationships(self, model_name: str, object_id: int) -> Dict[str, Any]:
        """Validate bidirectional relationship integrity."""
        if model_name not in self.model_registry:
            return {'success': False, 'error': f'Unknown model: {model_name}'}

        model_class = self.model_registry[model_name]
        
        try:
            obj = model_class.objects.get(id=object_id)
            validation_result = {
                'model': model_name,
                'object_id': object_id,
                'relationships': {},
                'success': True,
                'errors': []
            }

            # Check each foreign key field
            for field in obj._meta.fields:
                if field.is_relation and hasattr(obj, field.name):
                    related_obj = getattr(obj, field.name)
                    if related_obj:
                        # Verify reverse relationship
                        reverse_relation_name = field.related_query_name()
                        if hasattr(related_obj, reverse_relation_name):
                            reverse_objects = getattr(related_obj, reverse_relation_name).all()
                            
                            validation_result['relationships'][field.name] = {
                                'forward_exists': True,
                                'reverse_exists': obj in reverse_objects,
                                'related_id': related_obj.id,
                                'reverse_count': reverse_objects.count()
                            }
                            
                            if obj not in reverse_objects:
                                validation_result['success'] = False
                                validation_result['errors'].append(
                                    f"Bidirectional relationship broken: {field.name}"
                                )

            return validation_result

        except ObjectDoesNotExist:
            return {'success': False, 'error': 'Object not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class DataConsistencyValidator:
    """Validator for data consistency and constraint validation."""

    def __init__(self, database_validator: DatabaseStateValidator):
        self.db_validator = database_validator
        self.model_registry = database_validator.model_registry

    def validate_unique_constraints(self, model_name: str) -> Dict[str, Any]:
        """Validate unique constraints for a model."""
        if model_name not in self.model_registry:
            return {'success': False, 'error': f'Unknown model: {model_name}'}

        model_class = self.model_registry[model_name]
        
        validation_result = {
            'model': model_name,
            'constraint_violations': [],
            'success': True,
            'total_objects': 0
        }

        try:
            all_objects = model_class.objects.all()
            validation_result['total_objects'] = all_objects.count()

            # Check unique_together constraints
            unique_together = getattr(model_class._meta, 'unique_together', [])
            for constraint in unique_together:
                violations = self._check_unique_together_violation(all_objects, constraint)
                if violations:
                    validation_result['constraint_violations'].extend(violations)
                    validation_result['success'] = False

            # Check individual unique fields
            for field in model_class._meta.fields:
                if field.unique:
                    violations = self._check_unique_field_violation(all_objects, field.name)
                    if violations:
                        validation_result['constraint_violations'].extend(violations)
                        validation_result['success'] = False

            return validation_result

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def validate_foreign_key_integrity(self, model_name: str) -> Dict[str, Any]:
        """Validate foreign key integrity for a model."""
        if model_name not in self.model_registry:
            return {'success': False, 'error': f'Unknown model: {model_name}'}

        model_class = self.model_registry[model_name]
        
        validation_result = {
            'model': model_name,
            'broken_references': [],
            'success': True,
            'total_objects': 0
        }

        try:
            all_objects = model_class.objects.all()
            validation_result['total_objects'] = all_objects.count()

            # Check each foreign key field
            for field in model_class._meta.fields:
                if field.is_relation and field.many_to_one:
                    field_name = field.name
                    related_model = field.related_model
                    
                    for obj in all_objects:
                        fk_value = getattr(obj, f"{field_name}_id")
                        if fk_value is not None:
                            # Check if referenced object exists
                            if not related_model.objects.filter(id=fk_value).exists():
                                validation_result['broken_references'].append({
                                    'object_id': obj.id,
                                    'field': field_name,
                                    'referenced_id': fk_value,
                                    'referenced_model': related_model.__name__
                                })
                                validation_result['success'] = False

            return validation_result

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _check_unique_together_violation(self, queryset: models.QuerySet, 
                                        constraint: Tuple[str, ...]) -> List[Dict[str, Any]]:
        """Check for unique_together constraint violations."""
        violations = []
        
        # Group by the constraint fields
        grouped = {}
        for obj in queryset:
            key = tuple(getattr(obj, field) for field in constraint)
            if key in grouped:
                grouped[key].append(obj)
            else:
                grouped[key] = [obj]

        # Find violations (groups with more than one object)
        for key, objects in grouped.items():
            if len(objects) > 1:
                violations.append({
                    'constraint': constraint,
                    'key_values': dict(zip(constraint, key)),
                    'violating_ids': [obj.id for obj in objects],
                    'count': len(objects)
                })

        return violations

    def _check_unique_field_violation(self, queryset: models.QuerySet, 
                                     field_name: str) -> List[Dict[str, Any]]:
        """Check for unique field constraint violations."""
        violations = []
        
        # Group by field value
        field_values = {}
        for obj in queryset:
            value = getattr(obj, field_name)
            if value is not None:  # Skip None values
                if value in field_values:
                    field_values[value].append(obj)
                else:
                    field_values[value] = [obj]

        # Find violations
        for value, objects in field_values.items():
            if len(objects) > 1:
                violations.append({
                    'field': field_name,
                    'value': value,
                    'violating_ids': [obj.id for obj in objects],
                    'count': len(objects)
                })

        return violations


class ModelSpecificValidators:
    """Model-specific validation methods for all Hedgehog models."""

    def __init__(self, database_validator: DatabaseStateValidator):
        self.db_validator = database_validator
        self.model_registry = database_validator.model_registry

    def validate_hedgehog_fabric(self, fabric_id: int) -> Dict[str, Any]:
        """Validate HedgehogFabric specific business logic."""
        try:
            fabric = self.model_registry['HedgehogFabric'].objects.get(id=fabric_id)
            
            validation = {
                'fabric_id': fabric_id,
                'validations': {},
                'success': True,
                'errors': []
            }

            # Validate status transitions
            valid_statuses = ['PLANNED', 'ACTIVE', 'DECOMMISSIONED']
            if fabric.status not in valid_statuses:
                validation['errors'].append(f"Invalid status: {fabric.status}")
                validation['success'] = False

            # Validate sync settings consistency
            if fabric.sync_enabled and fabric.sync_interval == 0:
                validation['errors'].append("Sync enabled but interval is 0")
                validation['success'] = False

            # Validate Git repository consistency
            if fabric.git_repository:
                if not fabric.gitops_directory:
                    validation['errors'].append("Git repository set but no GitOps directory")
                    validation['success'] = False

            validation['validations']['status'] = fabric.status in valid_statuses
            validation['validations']['sync_consistency'] = not (fabric.sync_enabled and fabric.sync_interval == 0)
            validation['validations']['git_consistency'] = not (fabric.git_repository and not fabric.gitops_directory)

            return validation

        except ObjectDoesNotExist:
            return {'success': False, 'error': 'Fabric not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def validate_git_repository(self, repository_id: int) -> Dict[str, Any]:
        """Validate GitRepository specific business logic."""
        try:
            repository = self.model_registry['GitRepository'].objects.get(id=repository_id)
            
            validation = {
                'repository_id': repository_id,
                'validations': {},
                'success': True,
                'errors': []
            }

            # Validate URL format
            valid_url_schemes = ['https://', 'git@']
            if not any(repository.url.startswith(scheme) for scheme in valid_url_schemes):
                validation['errors'].append(f"Invalid URL scheme: {repository.url}")
                validation['success'] = False

            # Validate authentication consistency
            if repository.authentication_type == 'TOKEN' and not repository.encrypted_credentials:
                validation['errors'].append("Token auth selected but no credentials")
                validation['success'] = False

            # Validate provider consistency
            provider_urls = {
                'GITHUB': 'github.com',
                'GITLAB': 'gitlab.com',
                'BITBUCKET': 'bitbucket.org'
            }
            
            if repository.provider in provider_urls:
                expected_domain = provider_urls[repository.provider]
                if expected_domain not in repository.url:
                    validation['errors'].append(f"Provider {repository.provider} doesn't match URL domain")
                    validation['success'] = False

            validation['validations']['url_format'] = any(repository.url.startswith(scheme) for scheme in valid_url_schemes)
            validation['validations']['auth_consistency'] = not (repository.authentication_type == 'TOKEN' and not repository.encrypted_credentials)
            validation['validations']['provider_consistency'] = repository.provider == 'GENERIC' or provider_urls.get(repository.provider, '') in repository.url

            return validation

        except ObjectDoesNotExist:
            return {'success': False, 'error': 'Repository not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def validate_hedgehog_resource(self, resource_id: int) -> Dict[str, Any]:
        """Validate HedgehogResource specific business logic."""
        try:
            resource = self.model_registry['HedgehogResource'].objects.get(id=resource_id)
            
            validation = {
                'resource_id': resource_id,
                'validations': {},
                'success': True,
                'errors': []
            }

            # Validate state consistency
            valid_states = ['draft', 'committed', 'synced', 'drifted', 'orphaned', 'pending']
            if resource.resource_state not in valid_states:
                validation['errors'].append(f"Invalid resource state: {resource.resource_state}")
                validation['success'] = False

            # Validate drift status consistency
            valid_drift_statuses = ['in_sync', 'spec_drift', 'desired_only', 'actual_only', 'creation_pending', 'deletion_pending']
            if resource.drift_status not in valid_drift_statuses:
                validation['errors'].append(f"Invalid drift status: {resource.drift_status}")
                validation['success'] = False

            # Validate spec consistency
            if resource.resource_state == 'committed' and not resource.desired_spec:
                validation['errors'].append("Resource committed but no desired spec")
                validation['success'] = False

            validation['validations']['state_valid'] = resource.resource_state in valid_states
            validation['validations']['drift_status_valid'] = resource.drift_status in valid_drift_statuses
            validation['validations']['spec_consistency'] = not (resource.resource_state == 'committed' and not resource.desired_spec)

            return validation

        except ObjectDoesNotExist:
            return {'success': False, 'error': 'Resource not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# Integration helper functions
def validate_ui_crud_operation(operation_type: str, model_name: str, 
                              before_state: Dict[str, Any], after_state: Dict[str, Any],
                              expected_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    High-level function to validate UI CRUD operations.
    
    Args:
        operation_type: 'create', 'update', 'delete'
        model_name: Name of the model being operated on
        before_state: Database state before operation
        after_state: Database state after operation
        expected_data: Expected field values for create/update operations
    
    Returns:
        Comprehensive validation result
    """
    db_validator = DatabaseStateValidator()
    crud_validator = CRUDOperationValidator(db_validator)
    
    # Compare states
    state_comparison = db_validator.compare_database_states(before_state, after_state)
    
    result = {
        'operation_type': operation_type,
        'model_name': model_name,
        'state_comparison': state_comparison,
        'operation_validation': {},
        'success': False
    }

    # Validate specific operation
    if operation_type == 'create' and expected_data:
        result['operation_validation'] = crud_validator.validate_create_operation(model_name, expected_data)
        result['success'] = result['operation_validation'].get('success', False)
        
    elif operation_type == 'update' and expected_data:
        # Find the object ID from state changes
        model_changes = state_comparison.get('model_changes', {}).get(model_name, {})
        updated_objects = model_changes.get('updated', [])
        
        if updated_objects:
            object_id = updated_objects[0]['id']
            result['operation_validation'] = crud_validator.validate_update_operation(model_name, object_id, expected_data)
            result['success'] = result['operation_validation'].get('success', False)
            
    elif operation_type == 'delete':
        # Find deleted object ID from state changes
        model_changes = state_comparison.get('model_changes', {}).get(model_name, {})
        deleted_objects = model_changes.get('deleted', [])
        
        if deleted_objects:
            object_id = deleted_objects[0]['id']
            result['operation_validation'] = crud_validator.validate_delete_operation(model_name, object_id)
            result['success'] = result['operation_validation'].get('success', False)

    return result


def validate_relationship_integrity_after_ui_operation(model_name: str, object_id: int) -> Dict[str, Any]:
    """
    Validate relationship integrity after a UI operation.
    
    Args:
        model_name: Name of the model
        object_id: ID of the object to validate
    
    Returns:
        Relationship validation result
    """
    db_validator = DatabaseStateValidator()
    relationship_validator = RelationshipValidator(db_validator)
    
    return relationship_validator.validate_bidirectional_relationships(model_name, object_id)