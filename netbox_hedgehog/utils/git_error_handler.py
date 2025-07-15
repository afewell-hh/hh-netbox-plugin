"""
Advanced Git Error Handling and Recovery
Provides comprehensive error handling for git operations with remediation suggestions
"""

import re
import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum

from django.utils import timezone
from django.core.exceptions import ValidationError

logger = logging.getLogger('netbox_hedgehog.git_error_handler')


class ErrorCategory(str, Enum):
    """Categories of git errors"""
    CONNECTION = 'connection'
    AUTHENTICATION = 'authentication'
    PERMISSION = 'permission'
    TIMEOUT = 'timeout'
    REPOSITORY = 'repository'
    NETWORK = 'network'
    CONFIGURATION = 'configuration'
    UNKNOWN = 'unknown'


class ErrorSeverity(str, Enum):
    """Severity levels for errors"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class RemediationLevel(str, Enum):
    """Remediation complexity levels"""
    AUTO = 'auto'
    USER = 'user'
    ADMIN = 'admin'
    MANUAL = 'manual'


@dataclass
class ErrorResponse:
    """Structured error response with remediation"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    original_error: str
    context: Dict[str, Any]
    remediation_suggestions: List[Dict[str, Any]]
    timestamp: datetime
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'error_id': self.error_id,
            'category': self.category,
            'severity': self.severity,
            'message': self.message,
            'original_error': self.original_error,
            'context': self.context,
            'remediation_suggestions': self.remediation_suggestions,
            'timestamp': self.timestamp.isoformat(),
            'correlation_id': self.correlation_id
        }


@dataclass
class RemediationSuggestion:
    """Structured remediation suggestion"""
    action: str
    description: str
    level: RemediationLevel
    priority: int
    automated: bool
    steps: List[str]
    estimated_time: str
    success_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecoveryPlan:
    """Comprehensive recovery plan for multiple errors"""
    plan_id: str
    error_patterns: List[str]
    steps: List[Dict[str, Any]]
    estimated_duration: str
    success_probability: float
    risk_level: str
    prerequisites: List[str]
    generated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'plan_id': self.plan_id,
            'error_patterns': self.error_patterns,
            'steps': self.steps,
            'estimated_duration': self.estimated_duration,
            'success_probability': self.success_probability,
            'risk_level': self.risk_level,
            'prerequisites': self.prerequisites,
            'generated_at': self.generated_at.isoformat()
        }


@dataclass
class ErrorRecord:
    """Record of an error occurrence"""
    timestamp: datetime
    error_category: ErrorCategory
    error_message: str
    context: Dict[str, Any]
    resolution_attempted: bool
    resolved: bool
    resolution_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'error_category': self.error_category,
            'error_message': self.error_message,
            'context': self.context,
            'resolution_attempted': self.resolution_attempted,
            'resolved': self.resolved,
            'resolution_time': self.resolution_time.isoformat() if self.resolution_time else None
        }


class GitErrorHandler:
    """Comprehensive error handling for git operations"""
    
    # Error pattern mapping
    ERROR_PATTERNS = {
        # Connection errors
        r'connection.*refused|refused.*connection': {
            'category': ErrorCategory.CONNECTION,
            'severity': ErrorSeverity.HIGH,
            'message': 'Connection refused by remote server'
        },
        r'connection.*timeout|timeout.*connection': {
            'category': ErrorCategory.TIMEOUT,
            'severity': ErrorSeverity.MEDIUM,
            'message': 'Connection timeout'
        },
        r'could not resolve hostname|hostname.*not.*found': {
            'category': ErrorCategory.NETWORK,
            'severity': ErrorSeverity.HIGH,
            'message': 'DNS resolution failed'
        },
        r'network.*unreachable|no route to host': {
            'category': ErrorCategory.NETWORK,
            'severity': ErrorSeverity.HIGH,
            'message': 'Network unreachable'
        },
        
        # Authentication errors
        r'authentication.*failed|failed.*authenticate': {
            'category': ErrorCategory.AUTHENTICATION,
            'severity': ErrorSeverity.HIGH,
            'message': 'Authentication failed'
        },
        r'invalid.*credentials|credentials.*invalid': {
            'category': ErrorCategory.AUTHENTICATION,
            'severity': ErrorSeverity.HIGH,
            'message': 'Invalid credentials'
        },
        r'access.*denied|permission.*denied': {
            'category': ErrorCategory.PERMISSION,
            'severity': ErrorSeverity.HIGH,
            'message': 'Access denied'
        },
        r'forbidden|403': {
            'category': ErrorCategory.PERMISSION,
            'severity': ErrorSeverity.HIGH,
            'message': 'Forbidden access'
        },
        r'unauthorized|401': {
            'category': ErrorCategory.AUTHENTICATION,
            'severity': ErrorSeverity.HIGH,
            'message': 'Unauthorized access'
        },
        
        # Repository errors
        r'repository.*not.*found|not.*found.*repository': {
            'category': ErrorCategory.REPOSITORY,
            'severity': ErrorSeverity.HIGH,
            'message': 'Repository not found'
        },
        r'repository.*does.*not.*exist': {
            'category': ErrorCategory.REPOSITORY,
            'severity': ErrorSeverity.HIGH,
            'message': 'Repository does not exist'
        },
        r'empty.*repository|repository.*empty': {
            'category': ErrorCategory.REPOSITORY,
            'severity': ErrorSeverity.MEDIUM,
            'message': 'Repository is empty'
        },
        r'branch.*not.*found|not.*found.*branch': {
            'category': ErrorCategory.REPOSITORY,
            'severity': ErrorSeverity.MEDIUM,
            'message': 'Branch not found'
        },
        
        # SSL/TLS errors
        r'ssl.*certificate|certificate.*ssl': {
            'category': ErrorCategory.CONFIGURATION,
            'severity': ErrorSeverity.MEDIUM,
            'message': 'SSL certificate issue'
        },
        r'certificate.*verify.*failed': {
            'category': ErrorCategory.CONFIGURATION,
            'severity': ErrorSeverity.MEDIUM,
            'message': 'SSL certificate verification failed'
        },
        
        # Token/key errors
        r'token.*expired|expired.*token': {
            'category': ErrorCategory.AUTHENTICATION,
            'severity': ErrorSeverity.HIGH,
            'message': 'Authentication token expired'
        },
        r'key.*not.*found|ssh.*key': {
            'category': ErrorCategory.AUTHENTICATION,
            'severity': ErrorSeverity.HIGH,
            'message': 'SSH key issue'
        },
        
        # Rate limiting
        r'rate.*limit|too.*many.*requests': {
            'category': ErrorCategory.NETWORK,
            'severity': ErrorSeverity.MEDIUM,
            'message': 'Rate limit exceeded'
        }
    }
    
    # Remediation templates
    REMEDIATION_TEMPLATES = {
        ErrorCategory.CONNECTION: [
            {
                'action': 'check_network_connectivity',
                'description': 'Verify network connectivity to the git server',
                'level': RemediationLevel.USER,
                'priority': 1,
                'automated': False,
                'steps': [
                    'Check if the server URL is accessible',
                    'Verify firewall settings',
                    'Test network connectivity'
                ],
                'estimated_time': '5-10 minutes',
                'success_rate': 0.7
            },
            {
                'action': 'retry_with_backoff',
                'description': 'Retry the operation with exponential backoff',
                'level': RemediationLevel.AUTO,
                'priority': 2,
                'automated': True,
                'steps': [
                    'Wait 1 second and retry',
                    'If fails, wait 2 seconds and retry',
                    'Continue with exponential backoff up to 30 seconds'
                ],
                'estimated_time': '1-2 minutes',
                'success_rate': 0.5
            }
        ],
        
        ErrorCategory.AUTHENTICATION: [
            {
                'action': 'verify_credentials',
                'description': 'Verify and update authentication credentials',
                'level': RemediationLevel.USER,
                'priority': 1,
                'automated': False,
                'steps': [
                    'Check if credentials are correct',
                    'Verify token has not expired',
                    'Test credentials manually',
                    'Update credentials if needed'
                ],
                'estimated_time': '5-15 minutes',
                'success_rate': 0.8
            },
            {
                'action': 'rotate_credentials',
                'description': 'Generate new authentication credentials',
                'level': RemediationLevel.USER,
                'priority': 2,
                'automated': False,
                'steps': [
                    'Generate new token/key',
                    'Update repository configuration',
                    'Test new credentials'
                ],
                'estimated_time': '10-20 minutes',
                'success_rate': 0.9
            }
        ],
        
        ErrorCategory.PERMISSION: [
            {
                'action': 'check_permissions',
                'description': 'Verify repository access permissions',
                'level': RemediationLevel.USER,
                'priority': 1,
                'automated': False,
                'steps': [
                    'Check if user has access to repository',
                    'Verify required permissions (read/write)',
                    'Contact repository administrator if needed'
                ],
                'estimated_time': '10-30 minutes',
                'success_rate': 0.6
            }
        ],
        
        ErrorCategory.TIMEOUT: [
            {
                'action': 'increase_timeout',
                'description': 'Increase connection timeout settings',
                'level': RemediationLevel.AUTO,
                'priority': 1,
                'automated': True,
                'steps': [
                    'Increase timeout from 30s to 60s',
                    'Retry the operation'
                ],
                'estimated_time': '1-2 minutes',
                'success_rate': 0.7
            },
            {
                'action': 'check_server_load',
                'description': 'Check if git server is under heavy load',
                'level': RemediationLevel.USER,
                'priority': 2,
                'automated': False,
                'steps': [
                    'Check server status page',
                    'Try again during off-peak hours',
                    'Contact server administrator'
                ],
                'estimated_time': '5-10 minutes',
                'success_rate': 0.4
            }
        ],
        
        ErrorCategory.REPOSITORY: [
            {
                'action': 'verify_repository_url',
                'description': 'Verify repository URL and accessibility',
                'level': RemediationLevel.USER,
                'priority': 1,
                'automated': False,
                'steps': [
                    'Check repository URL for typos',
                    'Verify repository exists',
                    'Check if repository was moved/renamed'
                ],
                'estimated_time': '5-10 minutes',
                'success_rate': 0.8
            }
        ],
        
        ErrorCategory.NETWORK: [
            {
                'action': 'check_dns_resolution',
                'description': 'Verify DNS resolution for git server',
                'level': RemediationLevel.USER,
                'priority': 1,
                'automated': False,
                'steps': [
                    'Test DNS resolution: nslookup <hostname>',
                    'Try alternative DNS servers',
                    'Check if hostname is correct'
                ],
                'estimated_time': '5-10 minutes',
                'success_rate': 0.7
            },
            {
                'action': 'wait_and_retry',
                'description': 'Wait for rate limit to reset',
                'level': RemediationLevel.AUTO,
                'priority': 2,
                'automated': True,
                'steps': [
                    'Wait for rate limit window to reset',
                    'Retry operation'
                ],
                'estimated_time': '1-60 minutes',
                'success_rate': 0.9
            }
        ],
        
        ErrorCategory.CONFIGURATION: [
            {
                'action': 'fix_ssl_config',
                'description': 'Fix SSL/TLS configuration issues',
                'level': RemediationLevel.USER,
                'priority': 1,
                'automated': False,
                'steps': [
                    'Check SSL certificate validity',
                    'Update CA certificates',
                    'Configure SSL verification settings'
                ],
                'estimated_time': '10-20 minutes',
                'success_rate': 0.8
            }
        ]
    }
    
    def __init__(self):
        self.logger = logger
        self._error_history: List[ErrorRecord] = []
        self._correlation_id = self._generate_correlation_id()
    
    def handle_connection_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> ErrorResponse:
        """
        Handle connection-related errors.
        
        Args:
            error: The exception that occurred
            context: Context information about the operation
            
        Returns:
            ErrorResponse with remediation suggestions
        """
        error_str = str(error).lower()
        
        # Analyze error patterns
        error_info = self._analyze_error(error_str, ErrorCategory.CONNECTION)
        
        # Generate remediation suggestions
        suggestions = self._generate_suggestions(
            ErrorCategory.CONNECTION,
            error_str,
            context
        )
        
        # Create error response
        response = ErrorResponse(
            error_id=self._generate_error_id(),
            category=error_info['category'],
            severity=error_info['severity'],
            message=error_info['message'],
            original_error=str(error),
            context=context,
            remediation_suggestions=[s.to_dict() for s in suggestions],
            timestamp=timezone.now(),
            correlation_id=self._correlation_id
        )
        
        # Record error
        self._record_error(response)
        
        return response
    
    def handle_authentication_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> ErrorResponse:
        """
        Handle authentication-related errors.
        
        Args:
            error: The exception that occurred
            context: Context information about the operation
            
        Returns:
            ErrorResponse with remediation suggestions
        """
        error_str = str(error).lower()
        
        # Analyze error patterns
        error_info = self._analyze_error(error_str, ErrorCategory.AUTHENTICATION)
        
        # Generate authentication-specific suggestions
        suggestions = self._generate_auth_suggestions(error_str, context)
        
        # Create error response
        response = ErrorResponse(
            error_id=self._generate_error_id(),
            category=error_info['category'],
            severity=error_info['severity'],
            message=error_info['message'],
            original_error=str(error),
            context=context,
            remediation_suggestions=[s.to_dict() for s in suggestions],
            timestamp=timezone.now(),
            correlation_id=self._correlation_id
        )
        
        # Record error
        self._record_error(response)
        
        return response
    
    def handle_permission_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> ErrorResponse:
        """
        Handle permission-related errors.
        
        Args:
            error: The exception that occurred
            context: Context information about the operation
            
        Returns:
            ErrorResponse with remediation suggestions
        """
        error_str = str(error).lower()
        
        # Analyze error patterns
        error_info = self._analyze_error(error_str, ErrorCategory.PERMISSION)
        
        # Generate permission-specific suggestions
        suggestions = self._generate_permission_suggestions(error_str, context)
        
        # Create error response
        response = ErrorResponse(
            error_id=self._generate_error_id(),
            category=error_info['category'],
            severity=error_info['severity'],
            message=error_info['message'],
            original_error=str(error),
            context=context,
            remediation_suggestions=[s.to_dict() for s in suggestions],
            timestamp=timezone.now(),
            correlation_id=self._correlation_id
        )
        
        # Record error
        self._record_error(response)
        
        return response
    
    def handle_timeout_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> ErrorResponse:
        """
        Handle timeout-related errors.
        
        Args:
            error: The exception that occurred
            context: Context information about the operation
            
        Returns:
            ErrorResponse with remediation suggestions
        """
        error_str = str(error).lower()
        
        # Analyze error patterns
        error_info = self._analyze_error(error_str, ErrorCategory.TIMEOUT)
        
        # Generate timeout-specific suggestions
        suggestions = self._generate_timeout_suggestions(error_str, context)
        
        # Create error response
        response = ErrorResponse(
            error_id=self._generate_error_id(),
            category=error_info['category'],
            severity=error_info['severity'],
            message=error_info['message'],
            original_error=str(error),
            context=context,
            remediation_suggestions=[s.to_dict() for s in suggestions],
            timestamp=timezone.now(),
            correlation_id=self._correlation_id
        )
        
        # Record error
        self._record_error(response)
        
        return response
    
    def suggest_remediation(
        self,
        error_type: str,
        context: Dict[str, Any]
    ) -> RemediationSuggestion:
        """
        Suggest remediation for a specific error type.
        
        Args:
            error_type: Type of error (category)
            context: Context information
            
        Returns:
            RemediationSuggestion with recommended actions
        """
        try:
            category = ErrorCategory(error_type)
        except ValueError:
            category = ErrorCategory.UNKNOWN
        
        suggestions = self._generate_suggestions(category, '', context)
        
        # Return the highest priority suggestion
        if suggestions:
            return suggestions[0]
        
        # Fallback suggestion
        return RemediationSuggestion(
            action='contact_support',
            description='Contact system administrator for assistance',
            level=RemediationLevel.ADMIN,
            priority=99,
            automated=False,
            steps=['Contact your system administrator', 'Provide error details and context'],
            estimated_time='Varies',
            success_rate=1.0
        )
    
    def create_recovery_plan(
        self,
        error_history: List[ErrorRecord]
    ) -> RecoveryPlan:
        """
        Create a comprehensive recovery plan based on error history.
        
        Args:
            error_history: List of error records
            
        Returns:
            RecoveryPlan with step-by-step recovery process
        """
        # Analyze error patterns
        patterns = self._analyze_error_patterns(error_history)
        
        # Generate recovery steps
        steps = self._generate_recovery_steps(patterns, error_history)
        
        # Estimate success probability
        success_prob = self._estimate_success_probability(patterns, steps)
        
        # Assess risk level
        risk_level = self._assess_risk_level(patterns, error_history)
        
        # Calculate estimated duration
        duration = self._estimate_recovery_duration(steps)
        
        # Determine prerequisites
        prerequisites = self._determine_prerequisites(patterns, steps)
        
        return RecoveryPlan(
            plan_id=self._generate_plan_id(),
            error_patterns=patterns,
            steps=steps,
            estimated_duration=duration,
            success_probability=success_prob,
            risk_level=risk_level,
            prerequisites=prerequisites,
            generated_at=timezone.now()
        )
    
    # Private helper methods
    
    def _analyze_error(
        self,
        error_str: str,
        default_category: ErrorCategory
    ) -> Dict[str, Any]:
        """Analyze error string against known patterns"""
        
        for pattern, info in self.ERROR_PATTERNS.items():
            if re.search(pattern, error_str, re.IGNORECASE):
                return info
        
        # Default fallback
        return {
            'category': default_category,
            'severity': ErrorSeverity.MEDIUM,
            'message': 'Unrecognized error pattern'
        }
    
    def _generate_suggestions(
        self,
        category: ErrorCategory,
        error_str: str,
        context: Dict[str, Any]
    ) -> List[RemediationSuggestion]:
        """Generate remediation suggestions for error category"""
        
        suggestions = []
        templates = self.REMEDIATION_TEMPLATES.get(category, [])
        
        for template in templates:
            suggestion = RemediationSuggestion(**template)
            
            # Customize suggestion based on context
            suggestion = self._customize_suggestion(suggestion, error_str, context)
            suggestions.append(suggestion)
        
        # Sort by priority
        suggestions.sort(key=lambda x: x.priority)
        
        return suggestions
    
    def _generate_auth_suggestions(
        self,
        error_str: str,
        context: Dict[str, Any]
    ) -> List[RemediationSuggestion]:
        """Generate authentication-specific suggestions"""
        
        suggestions = self._generate_suggestions(
            ErrorCategory.AUTHENTICATION,
            error_str,
            context
        )
        
        # Add specific auth suggestions based on error
        if 'token' in error_str:
            token_suggestion = RemediationSuggestion(
                action='regenerate_token',
                description='Regenerate authentication token',
                level=RemediationLevel.USER,
                priority=0,  # High priority
                automated=False,
                steps=[
                    'Go to your git provider settings',
                    'Generate a new personal access token',
                    'Update the token in NetBox',
                    'Test the connection'
                ],
                estimated_time='5-10 minutes',
                success_rate=0.9
            )
            suggestions.insert(0, token_suggestion)
        
        elif 'ssh' in error_str or 'key' in error_str:
            ssh_suggestion = RemediationSuggestion(
                action='fix_ssh_key',
                description='Fix SSH key configuration',
                level=RemediationLevel.USER,
                priority=0,
                automated=False,
                steps=[
                    'Check SSH key format and validity',
                    'Verify key is added to git provider',
                    'Test SSH connection manually',
                    'Update key if necessary'
                ],
                estimated_time='10-15 minutes',
                success_rate=0.8
            )
            suggestions.insert(0, ssh_suggestion)
        
        return suggestions
    
    def _generate_permission_suggestions(
        self,
        error_str: str,
        context: Dict[str, Any]
    ) -> List[RemediationSuggestion]:
        """Generate permission-specific suggestions"""
        
        suggestions = self._generate_suggestions(
            ErrorCategory.PERMISSION,
            error_str,
            context
        )
        
        # Add context-specific suggestions
        repo_url = context.get('repository_url', '')
        if 'github.com' in repo_url:
            github_suggestion = RemediationSuggestion(
                action='check_github_permissions',
                description='Check GitHub repository permissions',
                level=RemediationLevel.USER,
                priority=0,
                automated=False,
                steps=[
                    'Go to repository settings on GitHub',
                    'Check if you have read/write access',
                    'Request access from repository owner if needed',
                    'Verify token has required scopes'
                ],
                estimated_time='10-30 minutes',
                success_rate=0.7
            )
            suggestions.insert(0, github_suggestion)
        
        return suggestions
    
    def _generate_timeout_suggestions(
        self,
        error_str: str,
        context: Dict[str, Any]
    ) -> List[RemediationSuggestion]:
        """Generate timeout-specific suggestions"""
        
        suggestions = self._generate_suggestions(
            ErrorCategory.TIMEOUT,
            error_str,
            context
        )
        
        # Add repository size considerations
        if context.get('operation') == 'clone':
            clone_suggestion = RemediationSuggestion(
                action='use_shallow_clone',
                description='Use shallow clone for large repositories',
                level=RemediationLevel.AUTO,
                priority=0,
                automated=True,
                steps=[
                    'Enable shallow clone (depth=1)',
                    'Retry clone operation',
                    'Consider using sparse checkout for very large repos'
                ],
                estimated_time='2-5 minutes',
                success_rate=0.8
            )
            suggestions.insert(0, clone_suggestion)
        
        return suggestions
    
    def _customize_suggestion(
        self,
        suggestion: RemediationSuggestion,
        error_str: str,
        context: Dict[str, Any]
    ) -> RemediationSuggestion:
        """Customize suggestion based on specific context"""
        
        # Adjust success rate based on context
        if context.get('previous_attempts', 0) > 2:
            suggestion.success_rate *= 0.8  # Lower success rate after multiple failures
        
        # Adjust time estimates for complex repositories
        if context.get('repository_size', 'small') == 'large':
            if 'clone' in suggestion.action:
                suggestion.estimated_time = '10-30 minutes'
        
        return suggestion
    
    def _record_error(self, error_response: ErrorResponse) -> None:
        """Record error in history"""
        record = ErrorRecord(
            timestamp=error_response.timestamp,
            error_category=error_response.category,
            error_message=error_response.message,
            context=error_response.context,
            resolution_attempted=False,
            resolved=False
        )
        
        self._error_history.append(record)
        
        # Keep only recent errors (last 100)
        self._error_history = self._error_history[-100:]
    
    def _analyze_error_patterns(
        self,
        error_history: List[ErrorRecord]
    ) -> List[str]:
        """Analyze patterns in error history"""
        patterns = []
        
        # Group errors by category
        category_counts = {}
        for error in error_history:
            category = error.error_category
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Identify dominant patterns
        total_errors = len(error_history)
        for category, count in category_counts.items():
            if count / total_errors > 0.3:  # More than 30% of errors
                patterns.append(f'recurring_{category}_errors')
        
        # Check for time-based patterns
        recent_errors = [
            e for e in error_history
            if e.timestamp > timezone.now() - timedelta(hours=1)
        ]
        
        if len(recent_errors) > 5:
            patterns.append('error_burst')
        
        # Check for specific error patterns
        auth_errors = [e for e in error_history if e.error_category == ErrorCategory.AUTHENTICATION]
        if len(auth_errors) > 3:
            patterns.append('persistent_auth_issues')
        
        return patterns
    
    def _generate_recovery_steps(
        self,
        patterns: List[str],
        error_history: List[ErrorRecord]
    ) -> List[Dict[str, Any]]:
        """Generate recovery steps based on patterns"""
        steps = []
        
        # Basic diagnostics
        steps.append({
            'step': 1,
            'action': 'basic_diagnostics',
            'description': 'Run basic connectivity and configuration checks',
            'estimated_time': '5 minutes',
            'automated': True
        })
        
        # Pattern-specific steps
        if 'recurring_authentication_errors' in patterns:
            steps.append({
                'step': 2,
                'action': 'credential_reset',
                'description': 'Reset and reconfigure authentication credentials',
                'estimated_time': '15 minutes',
                'automated': False
            })
        
        if 'persistent_auth_issues' in patterns:
            steps.append({
                'step': 3,
                'action': 'full_auth_review',
                'description': 'Comprehensive authentication configuration review',
                'estimated_time': '30 minutes',
                'automated': False
            })
        
        if 'error_burst' in patterns:
            steps.append({
                'step': 2,
                'action': 'cooling_period',
                'description': 'Wait for rate limits and temporary issues to resolve',
                'estimated_time': '10-30 minutes',
                'automated': True
            })
        
        # Final verification
        steps.append({
            'step': len(steps) + 1,
            'action': 'verification',
            'description': 'Test all repository operations to verify recovery',
            'estimated_time': '5 minutes',
            'automated': True
        })
        
        return steps
    
    def _estimate_success_probability(
        self,
        patterns: List[str],
        steps: List[Dict[str, Any]]
    ) -> float:
        """Estimate probability of successful recovery"""
        base_probability = 0.7
        
        # Adjust based on patterns
        if 'recurring_authentication_errors' in patterns:
            base_probability *= 0.9  # Auth issues are usually fixable
        
        if 'error_burst' in patterns:
            base_probability *= 0.8  # Burst may indicate systemic issues
        
        if 'persistent_auth_issues' in patterns:
            base_probability *= 0.6  # Persistent issues are harder to fix
        
        # Adjust based on number of steps
        complexity_factor = max(0.5, 1.0 - (len(steps) - 3) * 0.1)
        base_probability *= complexity_factor
        
        return max(0.1, min(0.95, base_probability))
    
    def _assess_risk_level(
        self,
        patterns: List[str],
        error_history: List[ErrorRecord]
    ) -> str:
        """Assess risk level of recovery operations"""
        
        if 'persistent_auth_issues' in patterns:
            return 'high'
        
        if len(error_history) > 10:
            return 'medium'
        
        if 'error_burst' in patterns:
            return 'medium'
        
        return 'low'
    
    def _estimate_recovery_duration(self, steps: List[Dict[str, Any]]) -> str:
        """Estimate total recovery duration"""
        total_minutes = 0
        
        for step in steps:
            time_str = step.get('estimated_time', '5 minutes')
            # Extract minutes from time string
            minutes = re.findall(r'(\d+)', time_str)
            if minutes:
                total_minutes += int(minutes[0])
        
        if total_minutes < 30:
            return f'{total_minutes} minutes'
        elif total_minutes < 120:
            hours = total_minutes / 60
            return f'{hours:.1f} hours'
        else:
            hours = total_minutes / 60
            return f'{hours:.0f} hours'
    
    def _determine_prerequisites(
        self,
        patterns: List[str],
        steps: List[Dict[str, Any]]
    ) -> List[str]:
        """Determine prerequisites for recovery"""
        prerequisites = []
        
        if any('auth' in pattern for pattern in patterns):
            prerequisites.append('Access to git provider account for credential management')
        
        if any(step.get('automated') is False for step in steps):
            prerequisites.append('Administrative access to repository configuration')
        
        prerequisites.append('Network connectivity to git provider')
        
        return prerequisites
    
    def _generate_correlation_id(self) -> str:
        """Generate correlation ID for error tracking"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _generate_error_id(self) -> str:
        """Generate unique error ID"""
        import uuid
        return f'git-error-{uuid.uuid4().hex[:8]}'
    
    def _generate_plan_id(self) -> str:
        """Generate unique recovery plan ID"""
        import uuid
        return f'recovery-{uuid.uuid4().hex[:8]}'


# Convenience functions

def handle_git_error(
    error: Exception,
    operation: str,
    context: Optional[Dict[str, Any]] = None
) -> ErrorResponse:
    """
    Convenience function to handle any git error.
    
    Args:
        error: The exception that occurred
        operation: The operation that failed (e.g., 'clone', 'fetch')
        context: Optional context information
        
    Returns:
        ErrorResponse with remediation suggestions
    """
    handler = GitErrorHandler()
    
    if context is None:
        context = {}
    
    context['operation'] = operation
    
    error_str = str(error).lower()
    
    # Route to appropriate handler based on error content
    if any(pattern in error_str for pattern in ['connection', 'network', 'resolve']):
        return handler.handle_connection_error(error, context)
    elif any(pattern in error_str for pattern in ['auth', 'credential', 'token', 'key']):
        return handler.handle_authentication_error(error, context)
    elif any(pattern in error_str for pattern in ['permission', 'forbidden', 'access']):
        return handler.handle_permission_error(error, context)
    elif any(pattern in error_str for pattern in ['timeout', 'time']):
        return handler.handle_timeout_error(error, context)
    else:
        # Generic error handling
        return handler.handle_connection_error(error, context)