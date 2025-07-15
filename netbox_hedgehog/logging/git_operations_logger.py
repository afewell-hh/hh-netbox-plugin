"""
Structured Logging for Git Operations
Provides comprehensive logging with correlation IDs, performance metrics, and audit trails
"""

import json
import time
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager

from django.utils import timezone
from django.contrib.auth.models import User

logger = logging.getLogger('netbox_hedgehog.git_operations')


class LogLevel(str, Enum):
    """Log levels for git operations"""
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class OperationType(str, Enum):
    """Types of git operations"""
    CONNECTION_TEST = 'connection_test'
    CLONE = 'clone'
    FETCH = 'fetch'
    PUSH = 'push'
    PULL = 'pull'
    CREDENTIAL_ROTATION = 'credential_rotation'
    HEALTH_CHECK = 'health_check'
    VALIDATION = 'validation'
    DIRECTORY_CHECK = 'directory_check'
    BRANCH_CHECK = 'branch_check'
    PERMISSION_CHECK = 'permission_check'


class OperationStatus(str, Enum):
    """Status of git operations"""
    STARTED = 'started'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    RETRYING = 'retrying'


@dataclass
class LogContext:
    """Context information for logging"""
    correlation_id: str
    operation_id: str
    repository_id: Optional[int]
    repository_name: Optional[str]
    repository_url: Optional[str]
    user_id: Optional[int]
    user_name: Optional[str]
    session_id: Optional[str]
    request_id: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations"""
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[int]
    network_time_ms: Optional[int]
    processing_time_ms: Optional[int]
    bytes_transferred: Optional[int]
    retry_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms,
            'network_time_ms': self.network_time_ms,
            'processing_time_ms': self.processing_time_ms,
            'bytes_transferred': self.bytes_transferred,
            'retry_count': self.retry_count
        }


@dataclass
class AuditEntry:
    """Audit trail entry"""
    timestamp: datetime
    action: str
    user_id: Optional[int]
    user_name: Optional[str]
    resource_type: str
    resource_id: Optional[int]
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    client_ip: Optional[str]
    user_agent: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'action': self.action,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'client_ip': self.client_ip,
            'user_agent': self.user_agent
        }


class GitOperationsLogger:
    """Structured logger for git operations with audit trail and performance tracking"""
    
    def __init__(self, logger_name: str = 'netbox_hedgehog.git_operations'):
        self.logger = logging.getLogger(logger_name)
        self._operation_stack: List[Dict[str, Any]] = []
        self._audit_entries: List[AuditEntry] = []
        self._performance_history: List[PerformanceMetrics] = []
    
    def create_context(
        self,
        repository_id: Optional[int] = None,
        repository_name: Optional[str] = None,
        repository_url: Optional[str] = None,
        user: Optional[User] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> LogContext:
        """
        Create logging context for operations.
        
        Args:
            repository_id: Repository ID
            repository_name: Repository name
            repository_url: Repository URL
            user: User performing operation
            session_id: Session ID
            request_id: Request ID
            
        Returns:
            LogContext instance
        """
        correlation_id = self._generate_correlation_id()
        operation_id = self._generate_operation_id()
        
        return LogContext(
            correlation_id=correlation_id,
            operation_id=operation_id,
            repository_id=repository_id,
            repository_name=repository_name,
            repository_url=repository_url,
            user_id=user.id if user else None,
            user_name=user.username if user else None,
            session_id=session_id,
            request_id=request_id
        )
    
    @contextmanager
    def operation_context(
        self,
        operation_type: OperationType,
        context: LogContext,
        **kwargs
    ):
        """
        Context manager for tracking git operations.
        
        Args:
            operation_type: Type of operation
            context: Logging context
            **kwargs: Additional operation parameters
        """
        operation = {
            'operation_type': operation_type,
            'context': context,
            'start_time': timezone.now(),
            'metrics': PerformanceMetrics(
                start_time=timezone.now(),
                end_time=None,
                duration_ms=None,
                network_time_ms=None,
                processing_time_ms=None,
                bytes_transferred=None,
                retry_count=0
            ),
            'kwargs': kwargs
        }
        
        self._operation_stack.append(operation)
        
        # Log operation start
        self.log_operation_start(operation_type, context, **kwargs)
        
        try:
            yield operation
            
            # Log successful completion
            self.log_operation_success(operation_type, context, operation['metrics'])
            
        except Exception as e:
            # Log operation failure
            self.log_operation_error(operation_type, context, e, operation['metrics'])
            raise
            
        finally:
            # Finalize metrics
            operation['metrics'].end_time = timezone.now()
            operation['metrics'].duration_ms = int(
                (operation['metrics'].end_time - operation['metrics'].start_time).total_seconds() * 1000
            )
            
            # Store performance history
            self._performance_history.append(operation['metrics'])
            self._performance_history = self._performance_history[-1000:]  # Keep last 1000
            
            # Remove from stack
            if self._operation_stack and self._operation_stack[-1] == operation:
                self._operation_stack.pop()
    
    def log_operation_start(
        self,
        operation_type: OperationType,
        context: LogContext,
        **kwargs
    ) -> None:
        """Log the start of a git operation"""
        log_data = {
            'event': 'operation_start',
            'operation_type': operation_type,
            'status': OperationStatus.STARTED,
            'context': context.to_dict(),
            'parameters': self._sanitize_parameters(kwargs),
            'timestamp': timezone.now().isoformat()
        }
        
        self.logger.info(
            f"Git operation started: {operation_type}",
            extra={'structured_data': json.dumps(log_data)}
        )
    
    def log_operation_success(
        self,
        operation_type: OperationType,
        context: LogContext,
        metrics: PerformanceMetrics,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log successful completion of a git operation"""
        log_data = {
            'event': 'operation_success',
            'operation_type': operation_type,
            'status': OperationStatus.COMPLETED,
            'context': context.to_dict(),
            'metrics': metrics.to_dict(),
            'result': self._sanitize_result(result),
            'timestamp': timezone.now().isoformat()
        }
        
        self.logger.info(
            f"Git operation completed: {operation_type} ({metrics.duration_ms}ms)",
            extra={'structured_data': json.dumps(log_data)}
        )
    
    def log_operation_error(
        self,
        operation_type: OperationType,
        context: LogContext,
        error: Exception,
        metrics: PerformanceMetrics
    ) -> None:
        """Log failed git operation"""
        log_data = {
            'event': 'operation_error',
            'operation_type': operation_type,
            'status': OperationStatus.FAILED,
            'context': context.to_dict(),
            'metrics': metrics.to_dict(),
            'error': {
                'type': type(error).__name__,
                'message': str(error),
                'traceback': traceback.format_exc()
            },
            'timestamp': timezone.now().isoformat()
        }
        
        self.logger.error(
            f"Git operation failed: {operation_type} - {str(error)}",
            extra={'structured_data': json.dumps(log_data)}
        )
    
    def log_retry_attempt(
        self,
        operation_type: OperationType,
        context: LogContext,
        attempt_number: int,
        reason: str
    ) -> None:
        """Log retry attempt"""
        log_data = {
            'event': 'operation_retry',
            'operation_type': operation_type,
            'status': OperationStatus.RETRYING,
            'context': context.to_dict(),
            'retry_attempt': attempt_number,
            'retry_reason': reason,
            'timestamp': timezone.now().isoformat()
        }
        
        self.logger.warning(
            f"Git operation retry attempt {attempt_number}: {operation_type} - {reason}",
            extra={'structured_data': json.dumps(log_data)}
        )
    
    def log_credential_access(
        self,
        context: LogContext,
        action: str,
        credential_type: str,
        success: bool
    ) -> None:
        """Log credential access for audit trail"""
        log_data = {
            'event': 'credential_access',
            'action': action,
            'credential_type': credential_type,
            'success': success,
            'context': context.to_dict(),
            'timestamp': timezone.now().isoformat()
        }
        
        level = logging.INFO if success else logging.WARNING
        self.logger.log(
            level,
            f"Credential access: {action} {credential_type} - {'success' if success else 'failed'}",
            extra={'structured_data': json.dumps(log_data)}
        )
        
        # Add to audit trail
        audit_entry = AuditEntry(
            timestamp=timezone.now(),
            action=f"credential_{action}",
            user_id=context.user_id,
            user_name=context.user_name,
            resource_type='git_repository',
            resource_id=context.repository_id,
            old_values=None,
            new_values={'credential_type': credential_type},
            client_ip=None,
            user_agent=None
        )
        self._audit_entries.append(audit_entry)
    
    def log_configuration_change(
        self,
        context: LogContext,
        resource_type: str,
        resource_id: Optional[int],
        old_values: Optional[Dict[str, Any]],
        new_values: Optional[Dict[str, Any]],
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Log configuration changes for audit trail"""
        log_data = {
            'event': 'configuration_change',
            'resource_type': resource_type,
            'resource_id': resource_id,
            'context': context.to_dict(),
            'changes': {
                'old_values': self._sanitize_sensitive_data(old_values),
                'new_values': self._sanitize_sensitive_data(new_values)
            },
            'client_info': {
                'ip': client_ip,
                'user_agent': user_agent
            },
            'timestamp': timezone.now().isoformat()
        }
        
        self.logger.info(
            f"Configuration change: {resource_type}#{resource_id}",
            extra={'structured_data': json.dumps(log_data)}
        )
        
        # Add to audit trail
        audit_entry = AuditEntry(
            timestamp=timezone.now(),
            action='configuration_change',
            user_id=context.user_id,
            user_name=context.user_name,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=self._sanitize_sensitive_data(old_values),
            new_values=self._sanitize_sensitive_data(new_values),
            client_ip=client_ip,
            user_agent=user_agent
        )
        self._audit_entries.append(audit_entry)
    
    def log_performance_metrics(
        self,
        context: LogContext,
        metrics: Dict[str, Any]
    ) -> None:
        """Log performance metrics"""
        log_data = {
            'event': 'performance_metrics',
            'context': context.to_dict(),
            'metrics': metrics,
            'timestamp': timezone.now().isoformat()
        }
        
        self.logger.info(
            "Performance metrics recorded",
            extra={'structured_data': json.dumps(log_data)}
        )
    
    def log_security_event(
        self,
        context: LogContext,
        event_type: str,
        severity: str,
        details: Dict[str, Any]
    ) -> None:
        """Log security-related events"""
        log_data = {
            'event': 'security_event',
            'event_type': event_type,
            'severity': severity,
            'context': context.to_dict(),
            'details': details,
            'timestamp': timezone.now().isoformat()
        }
        
        level = getattr(logging, severity.upper(), logging.WARNING)
        self.logger.log(
            level,
            f"Security event: {event_type} ({severity})",
            extra={'structured_data': json.dumps(log_data)}
        )
    
    def get_operation_history(
        self,
        context: Optional[LogContext] = None,
        operation_type: Optional[OperationType] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get operation history with filtering"""
        # In a real implementation, this would query a persistent log store
        # For now, return recent metrics
        
        filtered_metrics = self._performance_history
        
        if since:
            filtered_metrics = [
                m for m in filtered_metrics
                if m.start_time >= since
            ]
        
        # Convert to dict format
        history = [m.to_dict() for m in filtered_metrics[-limit:]]
        
        return history
    
    def get_audit_trail(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        user_id: Optional[int] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit trail with filtering"""
        filtered_entries = self._audit_entries
        
        if resource_type:
            filtered_entries = [
                e for e in filtered_entries
                if e.resource_type == resource_type
            ]
        
        if resource_id:
            filtered_entries = [
                e for e in filtered_entries
                if e.resource_id == resource_id
            ]
        
        if user_id:
            filtered_entries = [
                e for e in filtered_entries
                if e.user_id == user_id
            ]
        
        if since:
            filtered_entries = [
                e for e in filtered_entries
                if e.timestamp >= since
            ]
        
        # Convert to dict format and return most recent
        audit_trail = [e.to_dict() for e in filtered_entries[-limit:]]
        
        return audit_trail
    
    def get_performance_summary(
        self,
        operation_type: Optional[OperationType] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get performance summary statistics"""
        metrics = self._performance_history
        
        if since:
            metrics = [
                m for m in metrics
                if m.start_time >= since
            ]
        
        if not metrics:
            return {
                'total_operations': 0,
                'average_duration_ms': 0,
                'success_rate': 0,
                'error_rate': 0
            }
        
        # Calculate statistics
        durations = [m.duration_ms for m in metrics if m.duration_ms is not None]
        total_operations = len(metrics)
        
        return {
            'total_operations': total_operations,
            'average_duration_ms': sum(durations) / len(durations) if durations else 0,
            'min_duration_ms': min(durations) if durations else 0,
            'max_duration_ms': max(durations) if durations else 0,
            'retry_rate': sum(m.retry_count for m in metrics) / total_operations if total_operations > 0 else 0,
            'period_start': metrics[0].start_time.isoformat() if metrics else None,
            'period_end': metrics[-1].start_time.isoformat() if metrics else None
        }
    
    def update_operation_metrics(
        self,
        operation: Dict[str, Any],
        **metric_updates
    ) -> None:
        """Update metrics for current operation"""
        if operation and 'metrics' in operation:
            metrics = operation['metrics']
            
            for key, value in metric_updates.items():
                if hasattr(metrics, key):
                    setattr(metrics, key, value)
    
    # Private helper methods
    
    def _generate_correlation_id(self) -> str:
        """Generate correlation ID for tracking related operations"""
        import uuid
        return str(uuid.uuid4())[:12]
    
    def _generate_operation_id(self) -> str:
        """Generate unique operation ID"""
        import uuid
        return f"op-{uuid.uuid4().hex[:8]}"
    
    def _sanitize_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize parameters to remove sensitive data"""
        sanitized = {}
        
        for key, value in params.items():
            if any(sensitive in key.lower() for sensitive in ['password', 'token', 'key', 'secret']):
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_sensitive_data(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_result(self, result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Sanitize result data to remove sensitive information"""
        if result is None:
            return None
        
        return self._sanitize_sensitive_data(result)
    
    def _sanitize_sensitive_data(self, data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Remove sensitive data from dictionaries"""
        if data is None:
            return None
        
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        sensitive_keys = ['password', 'token', 'key', 'secret', 'credential', 'passphrase']
        
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if value:
                    sanitized[key] = f"[REDACTED-{len(str(value))} chars]"
                else:
                    sanitized[key] = '[REDACTED]'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_sensitive_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized


# Singleton logger instance
git_operations_logger = GitOperationsLogger()


# Convenience functions

def log_git_operation(
    operation_type: OperationType,
    repository_id: Optional[int] = None,
    repository_name: Optional[str] = None,
    user: Optional[User] = None
):
    """
    Decorator for logging git operations.
    
    Args:
        operation_type: Type of git operation
        repository_id: Repository ID
        repository_name: Repository name
        user: User performing operation
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            context = git_operations_logger.create_context(
                repository_id=repository_id,
                repository_name=repository_name,
                user=user
            )
            
            with git_operations_logger.operation_context(operation_type, context, **kwargs):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def create_git_log_context(
    repository_id: Optional[int] = None,
    repository_name: Optional[str] = None,
    user: Optional[User] = None
) -> LogContext:
    """
    Create a logging context for git operations.
    
    Args:
        repository_id: Repository ID
        repository_name: Repository name
        user: User performing operation
        
    Returns:
        LogContext instance
    """
    return git_operations_logger.create_context(
        repository_id=repository_id,
        repository_name=repository_name,
        user=user
    )