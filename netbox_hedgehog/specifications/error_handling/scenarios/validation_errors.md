# Data Validation Error Scenarios

## Overview

This document covers all data validation error scenarios in the NetBox Hedgehog Plugin, including YAML validation, JSON schema validation, business logic validation, and cross-resource validation errors.

## Validation Error Categories

### Error Types
1. **Schema Validation Errors**: YAML syntax, JSON schema compliance
2. **Business Logic Validation Errors**: State transitions, dependencies, constraints
3. **Format Validation Errors**: Data patterns, ranges, types
4. **Cross-Resource Validation Errors**: Relationships, references, consistency

## Schema Validation Error Scenarios

### Scenario: HH-VAL-001 - YAML Syntax Error

**Description**: YAML file contains syntax errors that prevent proper parsing.

**Common Triggers**:
- Incorrect indentation (mixing tabs and spaces)
- Missing or extra colons, commas, quotes
- Unclosed brackets or braces  
- Invalid Unicode characters
- Malformed multi-line strings

**Error Detection Patterns**:
```python
import yaml
import re

def detect_yaml_syntax_errors(yaml_content, file_path):
    """Detect and classify YAML syntax errors"""
    
    try:
        parsed = yaml.safe_load(yaml_content)
        return {'valid': True, 'parsed': parsed}
        
    except yaml.YAMLError as e:
        error_details = parse_yaml_error(e, yaml_content)
        
        raise ValidationError('HH-VAL-001', 'YAML syntax error', 
                            context={
                                'file_path': file_path,
                                'error_details': error_details,
                                'line': getattr(e, 'problem_mark', {}).get('line'),
                                'column': getattr(e, 'problem_mark', {}).get('column')
                            })

def parse_yaml_error(yaml_error, content):
    """Parse YAML error details for specific error types"""
    
    error_message = str(yaml_error).lower()
    lines = content.split('\n')
    
    error_types = {
        'indentation': ['indentation', 'indent', 'expected'],
        'syntax': ['syntax', 'could not find', 'mapping'],  
        'encoding': ['encoding', 'unicode', 'utf-8'],
        'structure': ['structure', 'unexpected', 'found']
    }
    
    for error_type, keywords in error_types.items():
        if any(keyword in error_message for keyword in keywords):
            return {
                'type': error_type,
                'message': str(yaml_error),
                'suggestions': get_yaml_fix_suggestions(error_type, yaml_error, lines)
            }
    
    return {
        'type': 'unknown',
        'message': str(yaml_error),
        'suggestions': []
    }

def get_yaml_fix_suggestions(error_type, yaml_error, lines):
    """Generate fix suggestions for YAML errors"""
    
    suggestions = []
    
    if error_type == 'indentation':
        suggestions.extend([
            'Check for mixing tabs and spaces',
            'Ensure consistent indentation (recommend 2 spaces)', 
            'Verify parent-child indentation relationships'
        ])
    elif error_type == 'syntax':
        suggestions.extend([
            'Check for missing colons after keys',
            'Verify proper quoting of string values',
            'Ensure proper list and dictionary syntax'
        ])
    elif error_type == 'encoding':
        suggestions.extend([
            'Save file with UTF-8 encoding',
            'Remove or escape special characters',
            'Use proper YAML string escaping'
        ])
    
    return suggestions
```

**Automatic Recovery**:
```python
def recover_yaml_syntax_error(yaml_content, error_context):
    """Attempt automatic YAML syntax repair"""
    
    error_details = error_context.get('error_details', {})
    error_type = error_details.get('type', 'unknown')
    
    recovery_functions = {
        'indentation': fix_yaml_indentation,
        'syntax': fix_yaml_syntax, 
        'encoding': fix_yaml_encoding,
        'structure': fix_yaml_structure
    }
    
    if error_type in recovery_functions:
        try:
            fixed_content = recovery_functions[error_type](yaml_content, error_details)
            
            # Validate the fix
            yaml.safe_load(fixed_content)
            
            return {
                'success': True,
                'recovery_type': 'automatic',
                'fix_applied': error_type,
                'fixed_content': fixed_content,
                'message': f'YAML {error_type} error automatically corrected'
            }
            
        except yaml.YAMLError as e:
            # Fix didn't work
            pass
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'automatic_yaml_fix_failed',
        'suggested_fixes': error_details.get('suggestions', [])
    }

def fix_yaml_indentation(content, error_details):
    """Fix common YAML indentation issues"""
    
    lines = content.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Convert tabs to spaces
        line = line.expandtabs(2)
        
        # Fix common indentation patterns
        if ':' in line and not line.strip().startswith('#'):
            # Ensure space after colon for key-value pairs
            line = re.sub(r':(?!\s)', ': ', line)
        
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def fix_yaml_syntax(content, error_details):
    """Fix common YAML syntax issues"""
    
    fixes = [
        # Add space after colons
        (r':(?=\S)', r': '),
        
        # Fix list syntax
        (r'^\s*-(?=\S)', r'- '),
        
        # Quote unquoted strings that need quoting
        (r':\s*([^"\'\s][^:\n]*[^"\'\s\n])\s*$', r': "\1"'),
        
        # Fix boolean values
        (r':\s*(yes|no)\s*$', lambda m: f': {m.group(1).lower()}'),
    ]
    
    fixed_content = content
    for pattern, replacement in fixes:
        if callable(replacement):
            fixed_content = re.sub(pattern, replacement, fixed_content, flags=re.MULTILINE)
        else:
            fixed_content = re.sub(pattern, replacement, fixed_content, flags=re.MULTILINE)
    
    return fixed_content
```

### Scenario: HH-VAL-002 - Invalid YAML Structure

**Description**: YAML file parses successfully but doesn't match the expected Kubernetes resource structure.

**Common Triggers**:
- Missing required top-level fields (apiVersion, kind, metadata)
- Incorrect nesting of spec sections
- Wrong field names or structure
- Missing or invalid metadata fields

**Error Detection**:
```python
def validate_kubernetes_yaml_structure(parsed_yaml, expected_kind=None):
    """Validate Kubernetes YAML structure"""
    
    required_fields = ['apiVersion', 'kind', 'metadata']
    validation_errors = []
    
    # Check required top-level fields
    for field in required_fields:
        if field not in parsed_yaml:
            validation_errors.append({
                'field': field,
                'type': 'missing_required',
                'message': f'Required field "{field}" is missing'
            })
    
    # Validate metadata structure
    if 'metadata' in parsed_yaml:
        metadata = parsed_yaml['metadata']
        if not isinstance(metadata, dict):
            validation_errors.append({
                'field': 'metadata',
                'type': 'invalid_type',
                'message': 'metadata must be an object'
            })
        elif 'name' not in metadata:
            validation_errors.append({
                'field': 'metadata.name',
                'type': 'missing_required',
                'message': 'metadata.name is required'
            })
    
    # Validate kind if specified
    if expected_kind and parsed_yaml.get('kind') != expected_kind:
        validation_errors.append({
            'field': 'kind',
            'type': 'value_mismatch',
            'message': f'Expected kind "{expected_kind}", got "{parsed_yaml.get("kind")}"'
        })
    
    if validation_errors:
        raise ValidationError('HH-VAL-002', 'Invalid YAML structure',
                            context={'validation_errors': validation_errors})
    
    return {'valid': True, 'structure': 'kubernetes_resource'}
```

**Automatic Recovery**:
```python
def recover_invalid_yaml_structure(parsed_yaml, expected_kind, error_context):
    """Automatic YAML structure repair"""
    
    validation_errors = error_context.get('validation_errors', [])
    fixed_yaml = parsed_yaml.copy()
    fixes_applied = []
    
    for error in validation_errors:
        field = error.get('field', '')
        error_type = error.get('type', '')
        
        if error_type == 'missing_required':
            if field == 'apiVersion':
                fixed_yaml['apiVersion'] = determine_api_version(expected_kind)
                fixes_applied.append('added_api_version')
            elif field == 'kind':
                fixed_yaml['kind'] = expected_kind
                fixes_applied.append('added_kind')
            elif field == 'metadata':
                fixed_yaml['metadata'] = {'name': 'default-resource'}
                fixes_applied.append('added_metadata')
            elif field == 'metadata.name':
                if 'metadata' not in fixed_yaml:
                    fixed_yaml['metadata'] = {}
                fixed_yaml['metadata']['name'] = generate_default_name(expected_kind)
                fixes_applied.append('added_metadata_name')
        
        elif error_type == 'value_mismatch' and field == 'kind':
            fixed_yaml['kind'] = expected_kind
            fixes_applied.append('corrected_kind')
    
    if fixes_applied:
        # Validate the fixed structure
        try:
            validate_kubernetes_yaml_structure(fixed_yaml, expected_kind)
            
            return {
                'success': True,
                'recovery_type': 'automatic',
                'fixes_applied': fixes_applied,
                'fixed_yaml': fixed_yaml,
                'message': 'YAML structure automatically corrected'
            }
            
        except ValidationError:
            # Still not valid after fixes
            pass
    
    return {
        'success': False,
        'escalate': 'manual',
        'validation_errors': validation_errors,
        'suggested_fixes': generate_structure_fix_suggestions(validation_errors)
    }

def determine_api_version(kind):
    """Determine appropriate API version for resource kind"""
    
    api_versions = {
        'VPC': 'vpc.githedgehog.com/v1alpha2',
        'External': 'vpc.githedgehog.com/v1alpha2',
        'ExternalAttachment': 'vpc.githedgehog.com/v1alpha2',
        'Connection': 'wiring.githedgehog.com/v1alpha2',
        'Switch': 'wiring.githedgehog.com/v1alpha2',
        'Server': 'wiring.githedgehog.com/v1alpha2'
    }
    
    return api_versions.get(kind, 'v1')
```

## Business Logic Validation Error Scenarios

### Scenario: HH-VAL-010 - Invalid State Transition

**Description**: Attempted state transition violates business rules or state machine constraints.

**Common Triggers**:
- Skipping required intermediate states
- Attempting transitions without meeting prerequisites  
- Concurrent state modifications
- Invalid trigger for current state

**Error Detection**:
```python
def validate_state_transition(entity, from_state, to_state, trigger, context=None):
    """Validate business logic for state transitions"""
    
    # Get valid transitions for entity type
    state_machine = get_state_machine(entity.__class__)
    valid_transitions = state_machine.get_valid_transitions(from_state)
    
    if to_state not in valid_transitions:
        raise ValidationError('HH-VAL-010', 'Invalid state transition',
                            context={
                                'entity_type': entity.__class__.__name__,
                                'entity_id': entity.id,
                                'from_state': from_state,
                                'to_state': to_state,
                                'valid_transitions': valid_transitions,
                                'trigger': trigger
                            })
    
    # Check transition conditions
    conditions = state_machine.get_transition_conditions(from_state, to_state)
    failed_conditions = []
    
    for condition in conditions:
        if not condition.check(entity, context):
            failed_conditions.append({
                'condition': condition.name,
                'description': condition.description,
                'current_value': condition.get_current_value(entity),
                'required_value': condition.required_value
            })
    
    if failed_conditions:
        raise ValidationError('HH-VAL-011', 'State transition conditions not met',
                            context={
                                'entity_type': entity.__class__.__name__,
                                'entity_id': entity.id,
                                'from_state': from_state,
                                'to_state': to_state,
                                'failed_conditions': failed_conditions
                            })
    
    return {'valid': True, 'transition_allowed': True}
```

**Automatic Recovery**:
```python
def recover_invalid_state_transition(entity, error_context):
    """Attempt state transition recovery"""
    
    from_state = error_context.get('from_state')
    to_state = error_context.get('to_state')
    valid_transitions = error_context.get('valid_transitions', [])
    
    # Strategy 1: Find intermediate transition path
    transition_path = find_transition_path(from_state, to_state, entity.__class__)
    
    if transition_path and len(transition_path) > 2:  # More than direct transition
        try:
            # Execute transition sequence
            for i in range(len(transition_path) - 1):
                current_state = transition_path[i]
                next_state = transition_path[i + 1]
                
                entity.transition_to(next_state, 'automatic_recovery')
                logger.info(f"Transitioned {entity} from {current_state} to {next_state}")
            
            return {
                'success': True,
                'recovery_type': 'automatic',
                'method': 'intermediate_transitions',
                'transition_path': transition_path,
                'message': f'State transition completed via path: {" -> ".join(transition_path)}'
            }
            
        except Exception as e:
            logger.error(f"Intermediate transition failed: {e}")
    
    # Strategy 2: Reset to safe state and retry
    if hasattr(entity, 'get_safe_state'):
        safe_state = entity.get_safe_state()
        if safe_state and safe_state != from_state:
            try:
                entity.reset_to_state(safe_state, 'recovery_reset')
                
                # Try transition from safe state
                entity.transition_to(to_state, 'recovery_retry')
                
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'method': 'reset_and_retry',
                    'safe_state': safe_state,
                    'message': f'Reset to {safe_state} and successfully transitioned to {to_state}'
                }
                
            except Exception as e:
                logger.error(f"Reset and retry failed: {e}")
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'no_valid_transition_path',
        'suggestions': [
            f'Manually transition to intermediate state: {valid_transitions}',
            'Check and resolve any blocking conditions',
            'Consider resetting entity to known good state'
        ]
    }

def find_transition_path(from_state, to_state, entity_class):
    """Find valid transition path between states using BFS"""
    
    from collections import deque
    
    state_machine = get_state_machine(entity_class)
    queue = deque([(from_state, [from_state])])
    visited = {from_state}
    
    while queue:
        current_state, path = queue.popleft()
        
        if current_state == to_state:
            return path
        
        valid_transitions = state_machine.get_valid_transitions(current_state)
        
        for next_state in valid_transitions:
            if next_state not in visited:
                visited.add(next_state)
                queue.append((next_state, path + [next_state]))
    
    return None  # No path found
```

### Scenario: HH-VAL-012 - Dependency Violation

**Description**: Operation violates dependency relationships between resources.

**Common Triggers**:
- Deleting resource that others depend on
- Creating resource without required dependencies
- Circular dependency creation
- Dependency version mismatches

**Error Detection and Recovery**:
```python
def validate_resource_dependencies(resource, operation, context=None):
    """Validate resource dependency constraints"""
    
    dependency_errors = []
    
    if operation == 'delete':
        # Check what depends on this resource
        dependents = find_dependent_resources(resource)
        
        if dependents:
            dependency_errors.append({
                'type': 'has_dependents',
                'resource': resource,
                'dependents': dependents,
                'message': f'Cannot delete {resource} - it has dependent resources'
            })
    
    elif operation in ['create', 'update']:
        # Check required dependencies exist
        required_deps = get_required_dependencies(resource)
        
        for dep in required_deps:
            if not dependency_exists(dep):
                dependency_errors.append({
                    'type': 'missing_dependency',
                    'resource': resource,
                    'dependency': dep,
                    'message': f'Required dependency {dep} does not exist'
                })
        
        # Check for circular dependencies
        circular_deps = detect_circular_dependencies(resource, context)
        if circular_deps:
            dependency_errors.append({
                'type': 'circular_dependency',
                'resource': resource,
                'cycle': circular_deps,
                'message': f'Circular dependency detected: {" -> ".join(circular_deps)}'
            })
    
    if dependency_errors:
        raise ValidationError('HH-VAL-012', 'Dependency constraint violation',
                            context={'dependency_errors': dependency_errors})
    
    return {'valid': True, 'dependencies_satisfied': True}

def recover_dependency_violation(resource, error_context):
    """Attempt dependency violation recovery"""
    
    dependency_errors = error_context.get('dependency_errors', [])
    recovery_actions = []
    
    for error in dependency_errors:
        error_type = error.get('type')
        
        if error_type == 'missing_dependency':
            # Attempt to create missing dependency
            dependency = error.get('dependency')
            
            if can_auto_create_dependency(dependency):
                try:
                    created_dep = create_dependency_resource(dependency)
                    recovery_actions.append({
                        'action': 'created_dependency',
                        'dependency': dependency,
                        'created_resource': created_dep
                    })
                except Exception as e:
                    recovery_actions.append({
                        'action': 'create_dependency_failed',
                        'dependency': dependency,
                        'error': str(e)
                    })
        
        elif error_type == 'has_dependents':
            # Attempt cascade delete or dependent resource update
            dependents = error.get('dependents', [])
            
            if resource.cascade_delete_allowed:
                try:
                    for dependent in dependents:
                        dependent.delete()
                    recovery_actions.append({
                        'action': 'cascade_deleted_dependents',
                        'dependents': [str(d) for d in dependents]
                    })
                except Exception as e:
                    recovery_actions.append({
                        'action': 'cascade_delete_failed',
                        'error': str(e)
                    })
        
        elif error_type == 'circular_dependency':
            # Break circular dependency by removing one reference
            cycle = error.get('cycle', [])
            
            if len(cycle) >= 2:
                try:
                    break_circular_dependency(cycle)
                    recovery_actions.append({
                        'action': 'broke_circular_dependency',
                        'cycle': cycle
                    })
                except Exception as e:
                    recovery_actions.append({
                        'action': 'break_circular_failed',
                        'error': str(e)
                    })
    
    successful_actions = [a for a in recovery_actions if not a.get('error')]
    
    if successful_actions:
        return {
            'success': True,
            'recovery_type': 'automatic',
            'actions_taken': successful_actions,
            'message': 'Dependency violations automatically resolved'
        }
    else:
        return {
            'success': False,
            'escalate': 'manual',
            'attempted_actions': recovery_actions,
            'dependency_errors': dependency_errors
        }
```

## Format Validation Error Scenarios

### Scenario: HH-VAL-020 - Invalid Format

**Description**: Data doesn't match expected format patterns (URLs, emails, IP addresses, etc.).

**Common Triggers**:
- Malformed URLs or email addresses
- Invalid IP address or CIDR notation
- Wrong date/time formats
- Invalid resource naming patterns

**Error Detection and Recovery**:
```python
def validate_field_formats(resource_data, field_definitions):
    """Validate field formats against defined patterns"""
    
    format_errors = []
    
    for field_name, field_def in field_definitions.items():
        if field_name not in resource_data:
            continue
            
        field_value = resource_data[field_name]
        field_format = field_def.get('format')
        
        if field_format:
            validation_result = validate_format(field_value, field_format, field_name)
            
            if not validation_result['valid']:
                format_errors.append(validation_result['error'])
    
    if format_errors:
        raise ValidationError('HH-VAL-020', 'Invalid field format',
                            context={'format_errors': format_errors})
    
    return {'valid': True, 'format_validation_passed': True}

def validate_format(value, format_type, field_name):
    """Validate specific format types"""
    
    validators = {
        'url': validate_url_format,
        'email': validate_email_format,
        'ipv4': validate_ipv4_format,
        'cidr': validate_cidr_format,
        'kubernetes_name': validate_kubernetes_name_format,
        'dns_name': validate_dns_name_format
    }
    
    if format_type in validators:
        return validators[format_type](value, field_name)
    else:
        return {'valid': True}  # Unknown format, skip validation

def validate_url_format(value, field_name):
    """Validate URL format"""
    
    import re
    from urllib.parse import urlparse
    
    if not isinstance(value, str):
        return {
            'valid': False,
            'error': {
                'field': field_name,
                'type': 'invalid_format',
                'format': 'url',
                'value': value,
                'message': 'URL must be a string'
            }
        }
    
    try:
        parsed = urlparse(value)
        
        if not parsed.scheme:
            return {
                'valid': False,
                'error': {
                    'field': field_name,
                    'type': 'invalid_format',
                    'format': 'url',
                    'value': value,
                    'message': 'URL must include scheme (http:// or https://)'
                }
            }
        
        if not parsed.netloc:
            return {
                'valid': False,
                'error': {
                    'field': field_name,
                    'type': 'invalid_format',
                    'format': 'url', 
                    'value': value,
                    'message': 'URL must include hostname'
                }
            }
        
        return {'valid': True}
        
    except Exception as e:
        return {
            'valid': False,
            'error': {
                'field': field_name,
                'type': 'invalid_format',
                'format': 'url',
                'value': value,
                'message': f'Invalid URL format: {str(e)}'
            }
        }

def recover_invalid_format(resource_data, error_context):
    """Attempt automatic format correction"""
    
    format_errors = error_context.get('format_errors', [])
    fixed_data = resource_data.copy()
    fixes_applied = []
    
    for error in format_errors:
        field_name = error.get('field')
        format_type = error.get('format')
        original_value = error.get('value')
        
        fix_result = attempt_format_fix(original_value, format_type, field_name)
        
        if fix_result.get('success'):
            fixed_data[field_name] = fix_result['fixed_value']
            fixes_applied.append({
                'field': field_name,
                'format': format_type,
                'original': original_value,
                'fixed': fix_result['fixed_value'],
                'fix_type': fix_result['fix_type']
            })
    
    if fixes_applied:
        return {
            'success': True,
            'recovery_type': 'automatic',
            'fixes_applied': fixes_applied,
            'fixed_data': fixed_data,
            'message': 'Field formats automatically corrected'
        }
    else:
        return {
            'success': False,
            'escalate': 'manual',
            'format_errors': format_errors,
            'fix_suggestions': generate_format_fix_suggestions(format_errors)
        }

def attempt_format_fix(value, format_type, field_name):
    """Attempt to fix common format issues"""
    
    if format_type == 'url':
        # Common URL fixes
        fixed_value = str(value).strip()
        
        # Add scheme if missing
        if not fixed_value.startswith(('http://', 'https://')):
            if 'github.com' in fixed_value or 'gitlab.com' in fixed_value:
                fixed_value = 'https://' + fixed_value.lstrip('/')
            else:
                fixed_value = 'http://' + fixed_value.lstrip('/')
        
        # Remove trailing slash for consistency
        fixed_value = fixed_value.rstrip('/')
        
        # Validate the fix
        if validate_url_format(fixed_value, field_name)['valid']:
            return {
                'success': True,
                'fixed_value': fixed_value,
                'fix_type': 'added_scheme_and_cleanup'
            }
    
    elif format_type == 'kubernetes_name':
        # Fix Kubernetes name format
        fixed_value = str(value).lower()
        fixed_value = re.sub(r'[^a-z0-9-]', '-', fixed_value)
        fixed_value = fixed_value.strip('-')
        
        if len(fixed_value) > 63:
            fixed_value = fixed_value[:63].rstrip('-')
        
        if validate_kubernetes_name_format(fixed_value, field_name)['valid']:
            return {
                'success': True,
                'fixed_value': fixed_value,
                'fix_type': 'normalized_kubernetes_name'
            }
    
    return {'success': False}
```

## Testing Validation Error Scenarios

```python
class ValidationErrorTests:
    
    def test_yaml_syntax_error_recovery(self):
        """Test HH-VAL-001 automatic recovery"""
        
        invalid_yaml = """
        apiVersion: v1
        kind: Pod
        metadata:
        name: test-pod  # Wrong indentation
          namespace: default
        """
        
        result = recover_yaml_syntax_error(invalid_yaml, {
            'error_details': {'type': 'indentation'}
        })
        
        self.assertTrue(result['success'])
        self.assertEqual(result['fix_applied'], 'indentation')
        
        # Validate fixed YAML parses correctly
        yaml.safe_load(result['fixed_content'])
    
    def test_invalid_state_transition_recovery(self):
        """Test HH-VAL-010 transition path recovery"""
        
        fabric = self.create_test_fabric(status='PLANNED')
        
        # Attempt invalid direct transition
        with self.assertRaises(ValidationError) as context:
            fabric.transition_to('SYNCED', 'invalid_direct')
        
        # Test recovery with intermediate transitions
        result = recover_invalid_state_transition(fabric, context.exception.context)
        
        self.assertTrue(result['success'])
        self.assertIn('transition_path', result)
    
    def test_format_validation_recovery(self):
        """Test HH-VAL-020 format correction"""
        
        invalid_data = {
            'git_repository_url': 'github.com/owner/repo',  # Missing scheme
            'name': 'Invalid Name With Spaces'  # Invalid k8s name
        }
        
        field_definitions = {
            'git_repository_url': {'format': 'url'},
            'name': {'format': 'kubernetes_name'}
        }
        
        with self.assertRaises(ValidationError) as context:
            validate_field_formats(invalid_data, field_definitions)
        
        result = recover_invalid_format(invalid_data, context.exception.context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['fixed_data']['git_repository_url'], 
                        'https://github.com/owner/repo')
        self.assertEqual(result['fixed_data']['name'], 
                        'invalid-name-with-spaces')
```

This comprehensive validation error scenario documentation provides agents with detailed knowledge for handling all data validation failures in the NetBox Hedgehog Plugin.