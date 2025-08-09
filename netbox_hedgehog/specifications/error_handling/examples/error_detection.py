"""
Error Detection Patterns for NetBox Hedgehog Plugin

This module provides standardized error detection patterns and utilities
for identifying specific error conditions across all plugin components.
"""

import re
import logging
import traceback
from typing import Dict, Any, Optional, List, Type
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categories for classification"""
    AUTHENTICATION = "auth"
    GIT = "git"
    KUBERNETES = "k8s"
    VALIDATION = "validation"
    NETWORK = "network"
    STATE = "state"


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorDetector:
    """Base class for error detection"""
    
    def __init__(self):
        self.error_patterns = {}
        self.context_extractors = {}
        self._initialize_patterns()
    
    def _initialize_patterns(self):
        """Initialize error detection patterns - override in subclasses"""
        pass
    
    def detect_error_type(self, exception: Exception, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Detect error type from exception and context
        
        Returns:
            Dict containing error classification and context
        """
        error_info = {
            'detected': False,
            'category': None,
            'code': None,
            'severity': ErrorSeverity.MEDIUM.value,
            'message': str(exception),
            'exception_type': type(exception).__name__,
            'context': context or {}
        }
        
        # Try to match exception to known patterns
        for pattern_name, pattern_config in self.error_patterns.items():
            if self._matches_pattern(exception, pattern_config):
                error_info.update({
                    'detected': True,
                    'pattern': pattern_name,
                    'category': pattern_config['category'],
                    'code': pattern_config['code'],
                    'severity': pattern_config['severity'],
                    'description': pattern_config['description']
                })
                
                # Extract additional context
                if pattern_name in self.context_extractors:
                    additional_context = self.context_extractors[pattern_name](exception, context)
                    error_info['context'].update(additional_context)
                
                break
        
        return error_info
    
    def _matches_pattern(self, exception: Exception, pattern_config: Dict) -> bool:
        """Check if exception matches a specific pattern"""
        
        # Check exception type
        if 'exception_types' in pattern_config:
            if type(exception) not in pattern_config['exception_types']:
                return False
        
        # Check message patterns
        if 'message_patterns' in pattern_config:
            exception_message = str(exception).lower()
            for pattern in pattern_config['message_patterns']:
                if re.search(pattern.lower(), exception_message):
                    return True
            return False
        
        # Check custom condition
        if 'condition' in pattern_config:
            return pattern_config['condition'](exception)
        
        return True
    
    def get_error_context(self, error_code: str, entity: Any = None, operation: str = None) -> Dict[str, Any]:
        """Get contextual information for an error"""
        
        context = {
            'error_code': error_code,
            'timestamp': self._get_timestamp(),
            'operation': operation
        }
        
        if entity:
            context.update({
                'entity_type': entity.__class__.__name__,
                'entity_id': getattr(entity, 'id', None),
                'entity_name': getattr(entity, 'name', None)
            })
        
        return context
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'


class AuthenticationErrorDetector(ErrorDetector):
    """Detect authentication and authorization errors"""
    
    def _initialize_patterns(self):
        self.error_patterns = {
            'github_token_invalid': {
                'category': ErrorCategory.AUTHENTICATION.value,
                'code': 'HH-AUTH-001',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'GitHub token is invalid or malformed',
                'message_patterns': [
                    r'bad credentials',
                    r'invalid token',
                    r'authentication failed',
                    r'401.*unauthorized'
                ]
            },
            'github_token_expired': {
                'category': ErrorCategory.AUTHENTICATION.value,
                'code': 'HH-AUTH-002',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'GitHub token has expired',
                'message_patterns': [
                    r'token.*expired',
                    r'credentials.*expired',
                    r'authentication.*expired'
                ]
            },
            'github_insufficient_permissions': {
                'category': ErrorCategory.AUTHENTICATION.value,
                'code': 'HH-AUTH-010',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'GitHub token lacks required permissions',
                'message_patterns': [
                    r'permission.*denied',
                    r'insufficient.*permissions',
                    r'403.*forbidden',
                    r'requires.*push.*access'
                ]
            },
            'kubernetes_token_invalid': {
                'category': ErrorCategory.AUTHENTICATION.value,
                'code': 'HH-AUTH-004',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Kubernetes token is invalid',
                'message_patterns': [
                    r'unauthorized.*401',
                    r'invalid.*bearer.*token',
                    r'authentication.*failed'
                ]
            },
            'kubernetes_rbac_denied': {
                'category': ErrorCategory.AUTHENTICATION.value,
                'code': 'HH-AUTH-012',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Kubernetes RBAC permissions denied',
                'message_patterns': [
                    r'forbidden.*403',
                    r'rbac.*denied',
                    r'is.*forbidden'
                ]
            }
        }
        
        self.context_extractors = {
            'github_token_invalid': self._extract_github_context,
            'github_token_expired': self._extract_github_context,
            'github_insufficient_permissions': self._extract_github_permissions_context,
            'kubernetes_token_invalid': self._extract_kubernetes_context,
            'kubernetes_rbac_denied': self._extract_kubernetes_rbac_context
        }
    
    def _extract_github_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract GitHub-specific context"""
        
        additional_context = {}
        
        # Try to extract repository URL from context or exception
        if hasattr(exception, 'response') and hasattr(exception.response, 'url'):
            additional_context['api_url'] = exception.response.url
        
        # Extract rate limit information if available
        if hasattr(exception, 'response') and hasattr(exception.response, 'headers'):
            headers = exception.response.headers
            if 'X-RateLimit-Remaining' in headers:
                additional_context['rate_limit_remaining'] = headers['X-RateLimit-Remaining']
            if 'X-RateLimit-Reset' in headers:
                additional_context['rate_limit_reset'] = headers['X-RateLimit-Reset']
        
        return additional_context
    
    def _extract_github_permissions_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract GitHub permissions context"""
        
        additional_context = self._extract_github_context(exception, context)
        
        # Extract required permissions from error message
        error_message = str(exception).lower()
        required_permissions = []
        
        if 'push' in error_message:
            required_permissions.append('push')
        if 'admin' in error_message:
            required_permissions.append('admin')
        if 'write' in error_message:
            required_permissions.append('write')
        
        if required_permissions:
            additional_context['required_permissions'] = required_permissions
        
        return additional_context
    
    def _extract_kubernetes_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract Kubernetes-specific context"""
        
        additional_context = {}
        
        # Extract cluster information
        if context and 'cluster_endpoint' in context:
            additional_context['cluster_endpoint'] = context['cluster_endpoint']
        
        # Extract namespace information
        if context and 'namespace' in context:
            additional_context['namespace'] = context['namespace']
        
        return additional_context
    
    def _extract_kubernetes_rbac_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract Kubernetes RBAC context"""
        
        additional_context = self._extract_kubernetes_context(exception, context)
        
        # Extract resource and verb information from error message
        error_message = str(exception)
        
        # Parse RBAC error format: 'user "system:serviceaccount:namespace:name" cannot "verb" resource "resource" in API group "group"'
        rbac_pattern = r'cannot "([^"]+)" resource "([^"]+)"'
        match = re.search(rbac_pattern, error_message)
        
        if match:
            additional_context['missing_verb'] = match.group(1)
            additional_context['resource'] = match.group(2)
        
        return additional_context


class GitErrorDetector(ErrorDetector):
    """Detect Git and GitHub integration errors"""
    
    def _initialize_patterns(self):
        self.error_patterns = {
            'repository_not_found': {
                'category': ErrorCategory.GIT.value,
                'code': 'HH-GIT-001',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Git repository not found or inaccessible',
                'message_patterns': [
                    r'repository.*not found',
                    r'remote.*not found',
                    r'404.*not found',
                    r'fatal.*repository.*not found'
                ]
            },
            'authentication_failed': {
                'category': ErrorCategory.GIT.value,
                'code': 'HH-GIT-002',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Git repository authentication failed',
                'message_patterns': [
                    r'authentication failed',
                    r'invalid username or password',
                    r'permission denied.*publickey',
                    r'401.*unauthorized'
                ]
            },
            'clone_failed': {
                'category': ErrorCategory.GIT.value,
                'code': 'HH-GIT-010',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Git clone operation failed',
                'message_patterns': [
                    r'clone.*failed',
                    r'could not clone',
                    r'fatal.*clone'
                ]
            },
            'merge_conflict': {
                'category': ErrorCategory.GIT.value,
                'code': 'HH-GIT-014',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Git merge conflict detected',
                'message_patterns': [
                    r'merge conflict',
                    r'automatic merge failed',
                    r'conflict.*merge'
                ]
            },
            'rate_limit_exceeded': {
                'category': ErrorCategory.GIT.value,
                'code': 'HH-GIT-020',
                'severity': ErrorSeverity.MEDIUM.value,
                'description': 'GitHub API rate limit exceeded',
                'message_patterns': [
                    r'rate limit exceeded',
                    r'429.*too many requests',
                    r'api rate limit'
                ]
            },
            'file_not_found': {
                'category': ErrorCategory.GIT.value,
                'code': 'HH-GIT-030',
                'severity': ErrorSeverity.MEDIUM.value,
                'description': 'File not found in repository',
                'message_patterns': [
                    r'file not found',
                    r'404.*not found',
                    r'path.*not found'
                ]
            }
        }
        
        self.context_extractors = {
            'repository_not_found': self._extract_repository_context,
            'authentication_failed': self._extract_auth_context,
            'clone_failed': self._extract_clone_context,
            'merge_conflict': self._extract_merge_context,
            'rate_limit_exceeded': self._extract_rate_limit_context,
            'file_not_found': self._extract_file_context
        }
    
    def _extract_repository_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract repository-specific context"""
        
        additional_context = {}
        
        if context and 'repository_url' in context:
            additional_context['repository_url'] = context['repository_url']
            
            # Parse owner/repo from URL
            import re
            url_pattern = r'github\.com[:/]([^/]+)/([^/\.]+)'
            match = re.search(url_pattern, context['repository_url'])
            if match:
                additional_context['owner'] = match.group(1)
                additional_context['repository'] = match.group(2)
        
        return additional_context
    
    def _extract_auth_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract authentication context"""
        
        additional_context = self._extract_repository_context(exception, context)
        
        # Determine authentication method
        error_message = str(exception).lower()
        if 'publickey' in error_message:
            additional_context['auth_method'] = 'ssh'
        elif 'username' in error_message or 'password' in error_message:
            additional_context['auth_method'] = 'https'
        elif 'token' in error_message:
            additional_context['auth_method'] = 'token'
        
        return additional_context
    
    def _extract_clone_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract clone operation context"""
        
        additional_context = self._extract_repository_context(exception, context)
        
        # Extract clone destination if available
        if context and 'local_path' in context:
            additional_context['local_path'] = context['local_path']
        
        # Check for disk space issues
        error_message = str(exception).lower()
        if 'disk' in error_message or 'space' in error_message:
            additional_context['likely_cause'] = 'insufficient_disk_space'
        elif 'permission' in error_message:
            additional_context['likely_cause'] = 'permission_denied'
        elif 'timeout' in error_message:
            additional_context['likely_cause'] = 'network_timeout'
        
        return additional_context
    
    def _extract_merge_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract merge conflict context"""
        
        additional_context = self._extract_repository_context(exception, context)
        
        # Extract conflicted files if available in error message
        error_message = str(exception)
        file_pattern = r'CONFLICT.*in (.+)'
        conflicts = re.findall(file_pattern, error_message)
        
        if conflicts:
            additional_context['conflicted_files'] = conflicts
        
        return additional_context
    
    def _extract_rate_limit_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract rate limit context"""
        
        additional_context = {}
        
        # Extract rate limit headers if available
        if hasattr(exception, 'response') and hasattr(exception.response, 'headers'):
            headers = exception.response.headers
            for header_name in ['X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Reset']:
                if header_name in headers:
                    key = header_name.lower().replace('x-ratelimit-', 'rate_limit_').replace('-', '_')
                    additional_context[key] = headers[header_name]
        
        return additional_context
    
    def _extract_file_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract file operation context"""
        
        additional_context = self._extract_repository_context(exception, context)
        
        if context and 'file_path' in context:
            additional_context['file_path'] = context['file_path']
        
        return additional_context


class KubernetesErrorDetector(ErrorDetector):
    """Detect Kubernetes API and resource errors"""
    
    def _initialize_patterns(self):
        self.error_patterns = {
            'connection_failed': {
                'category': ErrorCategory.KUBERNETES.value,
                'code': 'HH-K8S-001',
                'severity': ErrorSeverity.CRITICAL.value,
                'description': 'Kubernetes cluster connection failed',
                'message_patterns': [
                    r'connection.*failed',
                    r'unable to connect',
                    r'connection refused',
                    r'no route to host'
                ]
            },
            'authentication_failed': {
                'category': ErrorCategory.KUBERNETES.value,
                'code': 'HH-K8S-002',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Kubernetes authentication failed',
                'message_patterns': [
                    r'unauthorized.*401',
                    r'authentication failed',
                    r'invalid.*token'
                ]
            },
            'timeout': {
                'category': ErrorCategory.KUBERNETES.value,
                'code': 'HH-K8S-004',
                'severity': ErrorSeverity.MEDIUM.value,
                'description': 'Kubernetes API timeout',
                'message_patterns': [
                    r'timeout',
                    r'timed out',
                    r'deadline exceeded'
                ]
            },
            'crd_not_found': {
                'category': ErrorCategory.KUBERNETES.value,
                'code': 'HH-K8S-010',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Custom Resource Definition not found',
                'message_patterns': [
                    r'no matches for kind',
                    r'crd.*not found',
                    r'the server doesn\'t have a resource type'
                ]
            },
            'crd_validation_failed': {
                'category': ErrorCategory.KUBERNETES.value,
                'code': 'HH-K8S-011',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'CRD validation failed',
                'message_patterns': [
                    r'validation.*failed',
                    r'422.*unprocessable entity',
                    r'invalid.*spec'
                ]
            },
            'resource_creation_failed': {
                'category': ErrorCategory.KUBERNETES.value,
                'code': 'HH-K8S-020',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Kubernetes resource creation failed',
                'message_patterns': [
                    r'failed to create',
                    r'creation.*failed',
                    r'could not create'
                ]
            },
            'resource_quota_exceeded': {
                'category': ErrorCategory.KUBERNETES.value,
                'code': 'HH-K8S-025',
                'severity': ErrorSeverity.MEDIUM.value,
                'description': 'Resource quota exceeded',
                'message_patterns': [
                    r'quota.*exceeded',
                    r'resource quota',
                    r'exceeds.*quota'
                ]
            },
            'rbac_denied': {
                'category': ErrorCategory.KUBERNETES.value,
                'code': 'HH-K8S-033',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'RBAC permission denied',
                'message_patterns': [
                    r'forbidden.*403',
                    r'cannot.*verb.*resource',
                    r'rbac.*denied'
                ]
            }
        }
        
        self.context_extractors = {
            'connection_failed': self._extract_connection_context,
            'authentication_failed': self._extract_auth_context,
            'timeout': self._extract_timeout_context,
            'crd_not_found': self._extract_crd_context,
            'crd_validation_failed': self._extract_validation_context,
            'resource_creation_failed': self._extract_resource_context,
            'resource_quota_exceeded': self._extract_quota_context,
            'rbac_denied': self._extract_rbac_context
        }
    
    def _extract_connection_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract connection context"""
        
        additional_context = {}
        
        if context and 'cluster_endpoint' in context:
            additional_context['cluster_endpoint'] = context['cluster_endpoint']
        
        return additional_context
    
    def _extract_auth_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract authentication context"""
        
        additional_context = self._extract_connection_context(exception, context)
        
        if context and 'service_account' in context:
            additional_context['service_account'] = context['service_account']
        
        return additional_context
    
    def _extract_timeout_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract timeout context"""
        
        additional_context = self._extract_connection_context(exception, context)
        
        if context and 'timeout' in context:
            additional_context['timeout'] = context['timeout']
        
        if context and 'operation' in context:
            additional_context['operation'] = context['operation']
        
        return additional_context
    
    def _extract_crd_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract CRD context"""
        
        additional_context = {}
        
        # Extract CRD name from error message
        error_message = str(exception)
        
        # Look for kind in error message
        kind_pattern = r'no matches for kind "([^"]+)"'
        match = re.search(kind_pattern, error_message)
        if match:
            additional_context['missing_kind'] = match.group(1)
        
        # Look for resource type
        resource_pattern = r'doesn\'t have a resource type "([^"]+)"'
        match = re.search(resource_pattern, error_message)
        if match:
            additional_context['missing_resource_type'] = match.group(1)
        
        return additional_context
    
    def _extract_validation_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract validation context"""
        
        additional_context = {}
        
        # Parse validation errors from exception
        if hasattr(exception, 'body') and exception.body:
            try:
                import json
                error_body = json.loads(exception.body)
                if 'details' in error_body and 'causes' in error_body['details']:
                    validation_errors = []
                    for cause in error_body['details']['causes']:
                        validation_errors.append({
                            'field': cause.get('field', ''),
                            'reason': cause.get('reason', ''),
                            'message': cause.get('message', '')
                        })
                    additional_context['validation_errors'] = validation_errors
            except:
                pass
        
        return additional_context
    
    def _extract_resource_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract resource context"""
        
        additional_context = {}
        
        if context:
            for key in ['resource_name', 'namespace', 'resource_kind']:
                if key in context:
                    additional_context[key] = context[key]
        
        return additional_context
    
    def _extract_quota_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract quota context"""
        
        additional_context = self._extract_resource_context(exception, context)
        
        # Extract quota information from error message
        error_message = str(exception)
        
        # Look for specific quota limits
        quota_patterns = [
            r'requested: (.+), used: (.+), limited: (.+)',
            r'exceeds quota: (.+)'
        ]
        
        for pattern in quota_patterns:
            match = re.search(pattern, error_message)
            if match:
                additional_context['quota_details'] = match.groups()
                break
        
        return additional_context
    
    def _extract_rbac_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract RBAC context"""
        
        additional_context = self._extract_resource_context(exception, context)
        
        # Parse RBAC error details
        error_message = str(exception)
        
        rbac_pattern = r'cannot "([^"]+)" resource "([^"]+)".*in API group "([^"]*)"'
        match = re.search(rbac_pattern, error_message)
        
        if match:
            additional_context.update({
                'required_verb': match.group(1),
                'resource_type': match.group(2),
                'api_group': match.group(3)
            })
        
        return additional_context


class ValidationErrorDetector(ErrorDetector):
    """Detect data validation errors"""
    
    def _initialize_patterns(self):
        self.error_patterns = {
            'yaml_syntax_error': {
                'category': ErrorCategory.VALIDATION.value,
                'code': 'HH-VAL-001',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'YAML syntax error',
                'message_patterns': [
                    r'yaml.*error',
                    r'yaml.*syntax',
                    r'could not find expected',
                    r'mapping values are not allowed'
                ]
            },
            'yaml_structure_invalid': {
                'category': ErrorCategory.VALIDATION.value,
                'code': 'HH-VAL-002',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Invalid YAML structure',
                'message_patterns': [
                    r'invalid.*structure',
                    r'missing.*required.*field',
                    r'invalid.*kubernetes.*resource'
                ]
            },
            'invalid_state_transition': {
                'category': ErrorCategory.VALIDATION.value,
                'code': 'HH-VAL-010',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Invalid state transition',
                'message_patterns': [
                    r'invalid.*transition',
                    r'cannot transition.*from.*to',
                    r'transition.*not allowed'
                ]
            },
            'dependency_violation': {
                'category': ErrorCategory.VALIDATION.value,
                'code': 'HH-VAL-012',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Dependency constraint violation',
                'message_patterns': [
                    r'dependency.*violation',
                    r'missing.*dependency',
                    r'circular.*dependency'
                ]
            },
            'invalid_format': {
                'category': ErrorCategory.VALIDATION.value,
                'code': 'HH-VAL-020',
                'severity': ErrorSeverity.MEDIUM.value,
                'description': 'Invalid data format',
                'message_patterns': [
                    r'invalid.*format',
                    r'format.*error',
                    r'does not match.*pattern'
                ]
            }
        }
        
        self.context_extractors = {
            'yaml_syntax_error': self._extract_yaml_context,
            'yaml_structure_invalid': self._extract_structure_context,
            'invalid_state_transition': self._extract_transition_context,
            'dependency_violation': self._extract_dependency_context,
            'invalid_format': self._extract_format_context
        }
    
    def _extract_yaml_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract YAML context"""
        
        additional_context = {}
        
        # Extract line/column information if available
        if hasattr(exception, 'problem_mark'):
            mark = exception.problem_mark
            additional_context.update({
                'line': mark.line + 1 if mark else None,
                'column': mark.column + 1 if mark else None
            })
        
        if context and 'file_path' in context:
            additional_context['file_path'] = context['file_path']
        
        return additional_context
    
    def _extract_structure_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract structure validation context"""
        
        additional_context = self._extract_yaml_context(exception, context)
        
        if context and 'expected_kind' in context:
            additional_context['expected_kind'] = context['expected_kind']
        
        return additional_context
    
    def _extract_transition_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract state transition context"""
        
        additional_context = {}
        
        if context:
            for key in ['from_state', 'to_state', 'trigger', 'entity_type']:
                if key in context:
                    additional_context[key] = context[key]
        
        return additional_context
    
    def _extract_dependency_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract dependency context"""
        
        additional_context = {}
        
        if context:
            for key in ['resource', 'dependencies', 'dependents']:
                if key in context:
                    additional_context[key] = context[key]
        
        return additional_context
    
    def _extract_format_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract format validation context"""
        
        additional_context = {}
        
        if context:
            for key in ['field_name', 'field_value', 'expected_format']:
                if key in context:
                    additional_context[key] = context[key]
        
        return additional_context


class NetworkErrorDetector(ErrorDetector):
    """Detect network and connectivity errors"""
    
    def _initialize_patterns(self):
        import requests.exceptions
        
        self.error_patterns = {
            'connection_timeout': {
                'category': ErrorCategory.NETWORK.value,
                'code': 'HH-NET-001',
                'severity': ErrorSeverity.MEDIUM.value,
                'description': 'Connection timeout',
                'exception_types': [
                    requests.exceptions.ConnectTimeout,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.Timeout
                ]
            },
            'connection_refused': {
                'category': ErrorCategory.NETWORK.value,
                'code': 'HH-NET-002',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Connection refused',
                'message_patterns': [
                    r'connection refused',
                    r'connection.*rejected'
                ]
            },
            'dns_resolution_failed': {
                'category': ErrorCategory.NETWORK.value,
                'code': 'HH-NET-003',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'DNS resolution failed',
                'message_patterns': [
                    r'name or service not known',
                    r'nodename nor servname provided',
                    r'temporary failure in name resolution',
                    r'no such host'
                ]
            },
            'tls_handshake_failed': {
                'category': ErrorCategory.NETWORK.value,
                'code': 'HH-NET-010',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'TLS handshake failed',
                'message_patterns': [
                    r'ssl.*handshake.*failed',
                    r'certificate.*verify.*failed',
                    r'tls.*handshake.*timeout',
                    r'bad handshake'
                ]
            },
            'service_unavailable': {
                'category': ErrorCategory.NETWORK.value,
                'code': 'HH-NET-020',
                'severity': ErrorSeverity.MEDIUM.value,
                'description': 'Service unavailable',
                'condition': lambda e: (
                    hasattr(e, 'response') and 
                    hasattr(e.response, 'status_code') and 
                    e.response.status_code in [502, 503, 504]
                )
            }
        }
        
        self.context_extractors = {
            'connection_timeout': self._extract_timeout_context,
            'connection_refused': self._extract_connection_context,
            'dns_resolution_failed': self._extract_dns_context,
            'tls_handshake_failed': self._extract_tls_context,
            'service_unavailable': self._extract_service_context
        }
    
    def _extract_timeout_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract timeout context"""
        
        additional_context = {}
        
        if context:
            for key in ['timeout', 'target_url', 'operation']:
                if key in context:
                    additional_context[key] = context[key]
        
        # Determine timeout type
        exception_name = type(exception).__name__
        if 'Connect' in exception_name:
            additional_context['timeout_type'] = 'connect'
        elif 'Read' in exception_name:
            additional_context['timeout_type'] = 'read'
        else:
            additional_context['timeout_type'] = 'general'
        
        return additional_context
    
    def _extract_connection_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract connection context"""
        
        additional_context = {}
        
        if context and 'target_url' in context:
            additional_context['target_url'] = context['target_url']
            
            # Parse URL components
            from urllib.parse import urlparse
            parsed = urlparse(context['target_url'])
            additional_context.update({
                'hostname': parsed.hostname,
                'port': parsed.port or (443 if parsed.scheme == 'https' else 80),
                'scheme': parsed.scheme
            })
        
        return additional_context
    
    def _extract_dns_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract DNS context"""
        
        additional_context = {}
        
        if context and 'target_url' in context:
            from urllib.parse import urlparse
            parsed = urlparse(context['target_url'])
            additional_context['hostname'] = parsed.hostname
        
        return additional_context
    
    def _extract_tls_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract TLS context"""
        
        additional_context = self._extract_connection_context(exception, context)
        
        # Analyze TLS error type
        error_message = str(exception).lower()
        
        if 'certificate' in error_message:
            additional_context['tls_error_type'] = 'certificate'
        elif 'handshake' in error_message:
            additional_context['tls_error_type'] = 'handshake'
        elif 'version' in error_message:
            additional_context['tls_error_type'] = 'version'
        
        return additional_context
    
    def _extract_service_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract service unavailability context"""
        
        additional_context = self._extract_connection_context(exception, context)
        
        if hasattr(exception, 'response'):
            response = exception.response
            additional_context['status_code'] = response.status_code
            
            # Extract Retry-After header if present
            if 'Retry-After' in response.headers:
                additional_context['retry_after'] = response.headers['Retry-After']
        
        return additional_context


class StateErrorDetector(ErrorDetector):
    """Detect state management errors"""
    
    def _initialize_patterns(self):
        self.error_patterns = {
            'transition_not_allowed': {
                'category': ErrorCategory.STATE.value,
                'code': 'HH-STATE-001',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'State transition not allowed',
                'message_patterns': [
                    r'transition.*not.*allowed',
                    r'cannot transition.*from.*to',
                    r'invalid.*transition'
                ]
            },
            'condition_not_met': {
                'category': ErrorCategory.STATE.value,
                'code': 'HH-STATE-002',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Transition condition not met',
                'message_patterns': [
                    r'condition.*not.*met',
                    r'prerequisite.*not.*satisfied',
                    r'requirement.*not.*fulfilled'
                ]
            },
            'inconsistent_state': {
                'category': ErrorCategory.STATE.value,
                'code': 'HH-STATE-010',
                'severity': ErrorSeverity.HIGH.value,
                'description': 'Inconsistent entity state',
                'message_patterns': [
                    r'inconsistent.*state',
                    r'state.*corruption',
                    r'invalid.*state.*combination'
                ]
            },
            'state_persistence_failed': {
                'category': ErrorCategory.STATE.value,
                'code': 'HH-STATE-012',
                'severity': ErrorSeverity.CRITICAL.value,
                'description': 'State persistence failed',
                'message_patterns': [
                    r'failed.*to.*save.*state',
                    r'state.*persistence.*failed',
                    r'database.*error'
                ]
            }
        }
        
        self.context_extractors = {
            'transition_not_allowed': self._extract_transition_context,
            'condition_not_met': self._extract_condition_context,
            'inconsistent_state': self._extract_consistency_context,
            'state_persistence_failed': self._extract_persistence_context
        }
    
    def _extract_transition_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract transition context"""
        
        additional_context = {}
        
        if context:
            for key in ['entity_type', 'current_state', 'target_state', 'trigger']:
                if key in context:
                    additional_context[key] = context[key]
        
        return additional_context
    
    def _extract_condition_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract condition context"""
        
        additional_context = self._extract_transition_context(exception, context)
        
        if context and 'failed_conditions' in context:
            additional_context['failed_conditions'] = context['failed_conditions']
        
        return additional_context
    
    def _extract_consistency_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract consistency context"""
        
        additional_context = {}
        
        if context:
            for key in ['entity_type', 'entity_id', 'inconsistent_fields']:
                if key in context:
                    additional_context[key] = context[key]
        
        return additional_context
    
    def _extract_persistence_context(self, exception: Exception, context: Dict) -> Dict:
        """Extract persistence context"""
        
        additional_context = {}
        
        if context:
            for key in ['entity_type', 'entity_id', 'operation', 'database_error']:
                if key in context:
                    additional_context[key] = context[key]
        
        return additional_context


# Composite error detector that uses all specialized detectors
class CompositeErrorDetector:
    """Composite error detector that tries all specialized detectors"""
    
    def __init__(self):
        self.detectors = [
            AuthenticationErrorDetector(),
            GitErrorDetector(),
            KubernetesErrorDetector(),
            ValidationErrorDetector(),
            NetworkErrorDetector(),
            StateErrorDetector()
        ]
    
    def detect_error_type(self, exception: Exception, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Detect error type using all available detectors
        
        Returns:
            Dict containing error classification and context
        """
        for detector in self.detectors:
            error_info = detector.detect_error_type(exception, context)
            
            if error_info.get('detected'):
                return error_info
        
        # No specific pattern matched - return generic error info
        return {
            'detected': True,
            'category': 'unknown',
            'code': 'HH-UNK-001',
            'severity': ErrorSeverity.MEDIUM.value,
            'message': str(exception),
            'exception_type': type(exception).__name__,
            'context': context or {},
            'description': 'Unknown error type'
        }
    
    def get_error_context(self, error_code: str, entity: Any = None, operation: str = None) -> Dict[str, Any]:
        """Get contextual information for an error"""
        
        # Use first detector's context method (they're all similar)
        return self.detectors[0].get_error_context(error_code, entity, operation)


# Convenience function for easy usage
def detect_error_type(exception: Exception, context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Convenience function to detect error type
    
    Args:
        exception: The exception to analyze
        context: Optional context information
        
    Returns:
        Dict containing error classification and context
    """
    detector = CompositeErrorDetector()
    return detector.detect_error_type(exception, context)


def get_error_context(error_code: str, entity: Any = None, operation: str = None) -> Dict[str, Any]:
    """
    Convenience function to get error context
    
    Args:
        error_code: The error code
        entity: Optional entity involved in error
        operation: Optional operation being performed
        
    Returns:
        Dict containing contextual information
    """
    detector = CompositeErrorDetector()
    return detector.get_error_context(error_code, entity, operation)