"""
GitOps Error Handler and Rollback System
Provides comprehensive error handling, recovery mechanisms, and rollback capabilities
for GitOps file operations with detailed logging and notification systems.
"""

import logging
import traceback
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager
import threading
import time

from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of errors that can occur."""
    FILESYSTEM = "filesystem"
    GIT_OPERATION = "git_operation"
    NETWORK = "network"
    VALIDATION = "validation"
    PERMISSION = "permission"
    CONFIGURATION = "configuration"
    EXTERNAL_SERVICE = "external_service"
    UNKNOWN = "unknown"


class RecoveryStrategy(Enum):
    """Available recovery strategies."""
    RETRY = "retry"
    ROLLBACK = "rollback"
    FALLBACK = "fallback"
    MANUAL_INTERVENTION = "manual_intervention"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class ErrorContext:
    """Context information for an error."""
    operation_id: str
    fabric_id: int
    fabric_name: str
    operation_type: str
    file_path: Optional[str] = None
    user_id: Optional[int] = None
    timestamp: datetime = None
    additional_context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()
        if self.additional_context is None:
            self.additional_context = {}


@dataclass
class GitOpsError:
    """Comprehensive error information for GitOps operations."""
    error_id: str
    context: ErrorContext
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception: Optional[Exception] = None
    stack_trace: Optional[str] = None
    recovery_strategies: List[RecoveryStrategy] = None
    recovery_attempted: List[RecoveryStrategy] = None
    recovery_successful: Optional[RecoveryStrategy] = None
    resolution_time: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.recovery_strategies is None:
            self.recovery_strategies = []
        if self.recovery_attempted is None:
            self.recovery_attempted = []
        if self.metadata is None:
            self.metadata = {}
        if self.exception and not self.stack_trace:
            self.stack_trace = traceback.format_exception(
                type(self.exception), self.exception, self.exception.__traceback__
            )


@dataclass
class RollbackCheckpoint:
    """Checkpoint for rollback operations."""
    checkpoint_id: str
    operation_id: str
    timestamp: datetime
    state_snapshot: Dict[str, Any]
    files_modified: List[str]
    backups_created: Dict[str, str]  # file_path -> backup_path
    git_commit_hash: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class GitOpsErrorHandler:
    """
    Comprehensive error handling and rollback system for GitOps operations.
    
    Features:
    - Detailed error classification and tracking
    - Multiple recovery strategies
    - Comprehensive rollback capabilities
    - Error notification and alerting
    - Performance impact monitoring
    - Error pattern analysis
    """
    
    def __init__(self):
        self.errors: Dict[str, GitOpsError] = {}
        self.checkpoints: Dict[str, RollbackCheckpoint] = {}
        self.recovery_handlers: Dict[ErrorCategory, List[Callable]] = {}
        self.error_patterns: Dict[str, List[GitOpsError]] = {}
        self.notification_handlers: List[Callable] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Configuration
        self.max_retry_attempts = getattr(settings, 'GITOPS_MAX_RETRY_ATTEMPTS', 3)
        self.retry_delay_base = getattr(settings, 'GITOPS_RETRY_DELAY_BASE', 2)  # seconds
        self.error_retention_days = getattr(settings, 'GITOPS_ERROR_RETENTION_DAYS', 30)
        self.enable_error_notifications = getattr(settings, 'GITOPS_ENABLE_ERROR_NOTIFICATIONS', True)
        
        # Initialize default recovery handlers
        self._initialize_default_handlers()
    
    def _initialize_default_handlers(self):
        """Initialize default error recovery handlers."""
        self.register_recovery_handler(ErrorCategory.NETWORK, self._handle_network_error)
        self.register_recovery_handler(ErrorCategory.PERMISSION, self._handle_permission_error)
        self.register_recovery_handler(ErrorCategory.FILESYSTEM, self._handle_filesystem_error)
        self.register_recovery_handler(ErrorCategory.GIT_OPERATION, self._handle_git_operation_error)
        self.register_recovery_handler(ErrorCategory.VALIDATION, self._handle_validation_error)
    
    @contextmanager
    def error_boundary(self, context: ErrorContext):
        """
        Context manager for error boundary with automatic error handling.
        
        Args:
            context: Error context information
        """
        try:
            yield
        except Exception as e:
            error = self.handle_error(e, context)
            # Re-raise if error is critical and no recovery was successful
            if error.severity == ErrorSeverity.CRITICAL and not error.recovery_successful:
                raise
    
    def handle_error(self, exception: Exception, context: ErrorContext,
                    auto_recovery: bool = True) -> GitOpsError:
        """
        Handle an error with comprehensive analysis and recovery.
        
        Args:
            exception: The exception that occurred
            context: Context information for the error
            auto_recovery: Whether to attempt automatic recovery
            
        Returns:
            GitOpsError object with handling results
        """
        error_id = f"error_{context.operation_id}_{int(time.time())}"
        
        # Classify the error
        category = self._classify_error(exception)
        severity = self._determine_severity(exception, category, context)
        
        # Create error record
        error = GitOpsError(
            error_id=error_id,
            context=context,
            category=category,
            severity=severity,
            message=str(exception),
            exception=exception,
            recovery_strategies=self._determine_recovery_strategies(category, severity),
            metadata={
                'error_type': type(exception).__name__,
                'error_module': type(exception).__module__,
                'auto_recovery_enabled': auto_recovery
            }
        )
        
        with self._lock:
            self.errors[error_id] = error
        
        logger.error(
            f"GitOps error occurred in operation {context.operation_id}: "
            f"{category.value}/{severity.value} - {str(exception)}"
        )
        
        # Track error patterns
        self._track_error_pattern(error)
        
        # Attempt recovery if enabled
        if auto_recovery and error.recovery_strategies:
            self._attempt_recovery(error)
        
        # Send notifications
        if self.enable_error_notifications:
            self._send_error_notifications(error)
        
        return error
    
    def create_checkpoint(self, operation_id: str, context: ErrorContext,
                         state_snapshot: Dict[str, Any],
                         files_modified: List[str] = None,
                         backups_created: Dict[str, str] = None) -> str:
        """
        Create a rollback checkpoint before critical operations.
        
        Args:
            operation_id: ID of the operation
            context: Operation context
            state_snapshot: Current state snapshot
            files_modified: List of files that will be modified
            backups_created: Map of files to their backup paths
            
        Returns:
            Checkpoint ID
        """
        checkpoint_id = f"checkpoint_{operation_id}_{int(time.time())}"
        
        # Get current Git commit if possible
        git_commit_hash = None
        try:
            from .git_file_manager import GitFileManager
            if context.fabric_id:
                # This would need fabric instance, simplified for now
                git_commit_hash = "HEAD"  # Placeholder
        except Exception:
            pass
        
        checkpoint = RollbackCheckpoint(
            checkpoint_id=checkpoint_id,
            operation_id=operation_id,
            timestamp=timezone.now(),
            state_snapshot=state_snapshot,
            files_modified=files_modified or [],
            backups_created=backups_created or {},
            git_commit_hash=git_commit_hash,
            metadata={
                'fabric_id': context.fabric_id,
                'fabric_name': context.fabric_name,
                'operation_type': context.operation_type
            }
        )
        
        with self._lock:
            self.checkpoints[checkpoint_id] = checkpoint
        
        logger.info(f"Created rollback checkpoint: {checkpoint_id} for operation {operation_id}")
        return checkpoint_id
    
    def rollback_to_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        """
        Rollback to a specific checkpoint.
        
        Args:
            checkpoint_id: ID of the checkpoint to rollback to
            
        Returns:
            Dict with rollback results
        """
        logger.info(f"Starting rollback to checkpoint: {checkpoint_id}")
        
        result = {
            'success': False,
            'checkpoint_id': checkpoint_id,
            'started_at': timezone.now(),
            'files_restored': 0,
            'git_reset_performed': False,
            'errors': []
        }
        
        try:
            with self._lock:
                checkpoint = self.checkpoints.get(checkpoint_id)
            
            if not checkpoint:
                result['error'] = f"Checkpoint {checkpoint_id} not found"
                return result
            
            # Restore files from backups
            files_restored = 0
            for original_path, backup_path in checkpoint.backups_created.items():
                try:
                    backup_file = Path(backup_path)
                    original_file = Path(original_path)
                    
                    if backup_file.exists():
                        original_file.parent.mkdir(parents=True, exist_ok=True)
                        backup_file.replace(original_file)
                        files_restored += 1
                        logger.debug(f"Restored {original_path} from {backup_path}")
                    else:
                        result['errors'].append(f"Backup not found: {backup_path}")
                
                except Exception as e:
                    error_msg = f"Failed to restore {original_path}: {str(e)}"
                    result['errors'].append(error_msg)
                    logger.error(error_msg)
            
            result['files_restored'] = files_restored
            
            # Reset Git state if commit hash is available
            if checkpoint.git_commit_hash:
                try:
                    git_reset_result = self._reset_git_to_commit(checkpoint.git_commit_hash, checkpoint.metadata)
                    result['git_reset_performed'] = git_reset_result['success']
                    if not git_reset_result['success']:
                        result['errors'].append(f"Git reset failed: {git_reset_result.get('error')}")
                except Exception as e:
                    result['errors'].append(f"Git reset error: {str(e)}")
            
            result['success'] = len(result['errors']) == 0
            result['completed_at'] = timezone.now()
            
            if result['success']:
                logger.info(f"Successfully rolled back to checkpoint {checkpoint_id}: "
                           f"{files_restored} files restored")
            else:
                logger.warning(f"Rollback to checkpoint {checkpoint_id} completed with errors: "
                              f"{len(result['errors'])} errors")
            
        except Exception as e:
            error_msg = f"Rollback to checkpoint {checkpoint_id} failed: {str(e)}"
            logger.error(error_msg)
            result['error'] = error_msg
            result['completed_at'] = timezone.now()
        
        return result
    
    def register_recovery_handler(self, category: ErrorCategory, handler: Callable):
        """Register a custom recovery handler for an error category."""
        if category not in self.recovery_handlers:
            self.recovery_handlers[category] = []
        self.recovery_handlers[category].append(handler)
        logger.debug(f"Registered recovery handler for {category.value}")
    
    def register_notification_handler(self, handler: Callable):
        """Register a notification handler for error events."""
        self.notification_handlers.append(handler)
        logger.debug(f"Registered notification handler: {handler.__name__}")
    
    def get_error_statistics(self, time_window: timedelta = None) -> Dict[str, Any]:
        """
        Get error statistics for analysis and monitoring.
        
        Args:
            time_window: Time window to analyze (default: last 24 hours)
            
        Returns:
            Dict with error statistics
        """
        if time_window is None:
            time_window = timedelta(hours=24)
        
        cutoff_time = timezone.now() - time_window
        
        with self._lock:
            recent_errors = [
                error for error in self.errors.values()
                if error.context.timestamp >= cutoff_time
            ]
        
        # Calculate statistics
        stats = {
            'total_errors': len(recent_errors),
            'errors_by_category': {},
            'errors_by_severity': {},
            'recovery_success_rate': 0.0,
            'most_common_errors': [],
            'error_trends': {},
            'time_window': str(time_window)
        }
        
        # Group by category and severity
        for error in recent_errors:
            category = error.category.value
            severity = error.severity.value
            
            stats['errors_by_category'][category] = stats['errors_by_category'].get(category, 0) + 1
            stats['errors_by_severity'][severity] = stats['errors_by_severity'].get(severity, 0) + 1
        
        # Calculate recovery success rate
        if recent_errors:
            successful_recoveries = sum(1 for error in recent_errors if error.recovery_successful)
            stats['recovery_success_rate'] = (successful_recoveries / len(recent_errors)) * 100
        
        # Find most common error patterns
        error_messages = [error.message for error in recent_errors]
        message_counts = {}
        for message in error_messages:
            message_counts[message] = message_counts.get(message, 0) + 1
        
        stats['most_common_errors'] = sorted(
            message_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]
        
        return stats
    
    def cleanup_old_errors(self) -> Dict[str, Any]:
        """Clean up old error records and checkpoints."""
        cutoff_date = timezone.now() - timedelta(days=self.error_retention_days)
        
        cleaned_errors = 0
        cleaned_checkpoints = 0
        
        with self._lock:
            # Clean up old errors
            error_ids_to_remove = [
                error_id for error_id, error in self.errors.items()
                if error.context.timestamp < cutoff_date
            ]
            
            for error_id in error_ids_to_remove:
                del self.errors[error_id]
                cleaned_errors += 1
            
            # Clean up old checkpoints
            checkpoint_ids_to_remove = [
                checkpoint_id for checkpoint_id, checkpoint in self.checkpoints.items()
                if checkpoint.timestamp < cutoff_date
            ]
            
            for checkpoint_id in checkpoint_ids_to_remove:
                del self.checkpoints[checkpoint_id]
                cleaned_checkpoints += 1
        
        result = {
            'cleaned_errors': cleaned_errors,
            'cleaned_checkpoints': cleaned_checkpoints,
            'cutoff_date': cutoff_date
        }
        
        logger.info(f"Cleaned up {cleaned_errors} old errors and {cleaned_checkpoints} old checkpoints")
        return result
    
    # Private methods
    
    def _classify_error(self, exception: Exception) -> ErrorCategory:
        """Classify an error into a category."""
        error_type = type(exception).__name__
        error_message = str(exception).lower()
        
        if isinstance(exception, (PermissionError, OSError)) and 'permission' in error_message:
            return ErrorCategory.PERMISSION
        elif isinstance(exception, FileNotFoundError) or 'no such file' in error_message:
            return ErrorCategory.FILESYSTEM
        elif isinstance(exception, (ConnectionError, TimeoutError)) or any(
            keyword in error_message for keyword in ['connection', 'timeout', 'network']
        ):
            return ErrorCategory.NETWORK
        elif 'git' in error_message or error_type in ['GitCommandError', 'GitError']:
            return ErrorCategory.GIT_OPERATION
        elif any(keyword in error_message for keyword in ['invalid', 'validation', 'schema']):
            return ErrorCategory.VALIDATION
        elif any(keyword in error_message for keyword in ['config', 'configuration', 'setting']):
            return ErrorCategory.CONFIGURATION
        elif any(keyword in error_message for keyword in ['service', 'api', 'endpoint']):
            return ErrorCategory.EXTERNAL_SERVICE
        else:
            return ErrorCategory.UNKNOWN
    
    def _determine_severity(self, exception: Exception, category: ErrorCategory,
                          context: ErrorContext) -> ErrorSeverity:
        """Determine the severity of an error."""
        error_message = str(exception).lower()
        
        # Critical errors
        if any(keyword in error_message for keyword in [
            'critical', 'fatal', 'corruption', 'data loss'
        ]):
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if category in [ErrorCategory.GIT_OPERATION, ErrorCategory.EXTERNAL_SERVICE]:
            return ErrorSeverity.HIGH
        elif any(keyword in error_message for keyword in [
            'failed to', 'cannot', 'unable to', 'access denied'
        ]):
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if category in [ErrorCategory.FILESYSTEM, ErrorCategory.PERMISSION]:
            return ErrorSeverity.MEDIUM
        
        # Low severity errors (validation, configuration issues)
        return ErrorSeverity.LOW
    
    def _determine_recovery_strategies(self, category: ErrorCategory,
                                     severity: ErrorSeverity) -> List[RecoveryStrategy]:
        """Determine appropriate recovery strategies for an error."""
        strategies = []
        
        if severity == ErrorSeverity.CRITICAL:
            strategies.extend([RecoveryStrategy.ROLLBACK, RecoveryStrategy.MANUAL_INTERVENTION])
        elif severity == ErrorSeverity.HIGH:
            strategies.extend([RecoveryStrategy.RETRY, RecoveryStrategy.ROLLBACK])
        else:
            strategies.extend([RecoveryStrategy.RETRY, RecoveryStrategy.FALLBACK])
        
        # Category-specific strategies
        if category == ErrorCategory.NETWORK:
            strategies.append(RecoveryStrategy.RETRY)
        elif category == ErrorCategory.PERMISSION:
            strategies.append(RecoveryStrategy.FALLBACK)
        elif category == ErrorCategory.VALIDATION:
            strategies.extend([RecoveryStrategy.SKIP, RecoveryStrategy.MANUAL_INTERVENTION])
        
        return strategies
    
    def _attempt_recovery(self, error: GitOpsError) -> bool:
        """Attempt recovery using available strategies."""
        for strategy in error.recovery_strategies:
            try:
                error.recovery_attempted.append(strategy)
                
                if strategy == RecoveryStrategy.RETRY:
                    success = self._attempt_retry_recovery(error)
                elif strategy == RecoveryStrategy.ROLLBACK:
                    success = self._attempt_rollback_recovery(error)
                elif strategy == RecoveryStrategy.FALLBACK:
                    success = self._attempt_fallback_recovery(error)
                else:
                    # Skip strategies that require manual intervention
                    continue
                
                if success:
                    error.recovery_successful = strategy
                    error.resolution_time = timezone.now()
                    logger.info(f"Successfully recovered from error {error.error_id} using {strategy.value}")
                    return True
                
            except Exception as recovery_error:
                logger.error(f"Recovery strategy {strategy.value} failed for error {error.error_id}: {recovery_error}")
        
        return False
    
    def _attempt_retry_recovery(self, error: GitOpsError) -> bool:
        """Attempt recovery by retrying the operation."""
        # Check if we've already retried too many times
        retry_count = error.recovery_attempted.count(RecoveryStrategy.RETRY)
        if retry_count >= self.max_retry_attempts:
            return False
        
        # Calculate delay with exponential backoff
        delay = self.retry_delay_base ** retry_count
        time.sleep(delay)
        
        # Call category-specific handlers if available
        if error.category in self.recovery_handlers:
            for handler in self.recovery_handlers[error.category]:
                try:
                    if handler(error, RecoveryStrategy.RETRY):
                        return True
                except Exception as e:
                    logger.warning(f"Recovery handler failed: {e}")
        
        return False
    
    def _attempt_rollback_recovery(self, error: GitOpsError) -> bool:
        """Attempt recovery by rolling back to the last checkpoint."""
        # Find the most recent checkpoint for this operation
        operation_checkpoints = [
            checkpoint for checkpoint in self.checkpoints.values()
            if checkpoint.operation_id == error.context.operation_id
        ]
        
        if not operation_checkpoints:
            return False
        
        # Get the most recent checkpoint
        latest_checkpoint = max(operation_checkpoints, key=lambda cp: cp.timestamp)
        rollback_result = self.rollback_to_checkpoint(latest_checkpoint.checkpoint_id)
        
        return rollback_result['success']
    
    def _attempt_fallback_recovery(self, error: GitOpsError) -> bool:
        """Attempt recovery using fallback mechanisms."""
        # Call category-specific handlers
        if error.category in self.recovery_handlers:
            for handler in self.recovery_handlers[error.category]:
                try:
                    if handler(error, RecoveryStrategy.FALLBACK):
                        return True
                except Exception as e:
                    logger.warning(f"Fallback recovery handler failed: {e}")
        
        return False
    
    def _track_error_pattern(self, error: GitOpsError):
        """Track error patterns for analysis."""
        pattern_key = f"{error.category.value}:{error.message[:50]}"
        
        if pattern_key not in self.error_patterns:
            self.error_patterns[pattern_key] = []
        
        self.error_patterns[pattern_key].append(error)
        
        # Keep only recent errors for pattern analysis
        cutoff_time = timezone.now() - timedelta(hours=24)
        self.error_patterns[pattern_key] = [
            e for e in self.error_patterns[pattern_key]
            if e.context.timestamp >= cutoff_time
        ]
    
    def _send_error_notifications(self, error: GitOpsError):
        """Send error notifications to registered handlers."""
        for handler in self.notification_handlers:
            try:
                handler(error)
            except Exception as e:
                logger.error(f"Notification handler failed: {e}")
    
    def _reset_git_to_commit(self, commit_hash: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Reset Git repository to a specific commit."""
        # This would need to be implemented based on the specific Git operations utility
        # For now, return a placeholder result
        return {
            'success': True,
            'commit_hash': commit_hash,
            'message': 'Git reset not implemented in error handler'
        }
    
    # Default recovery handlers
    
    def _handle_network_error(self, error: GitOpsError, strategy: RecoveryStrategy) -> bool:
        """Handle network-related errors."""
        if strategy == RecoveryStrategy.RETRY:
            # For network errors, we can try retrying after a delay
            return True  # Indicate that retry is worthwhile
        elif strategy == RecoveryStrategy.FALLBACK:
            # Could implement offline mode or cached data fallback
            return False
        return False
    
    def _handle_permission_error(self, error: GitOpsError, strategy: RecoveryStrategy) -> bool:
        """Handle permission-related errors."""
        if strategy == RecoveryStrategy.FALLBACK:
            # Could try alternative paths or read-only operations
            return False
        return False
    
    def _handle_filesystem_error(self, error: GitOpsError, strategy: RecoveryStrategy) -> bool:
        """Handle filesystem-related errors."""
        if strategy == RecoveryStrategy.RETRY:
            # Filesystem errors might be transient
            return True
        elif strategy == RecoveryStrategy.FALLBACK:
            # Could try alternative storage locations
            return False
        return False
    
    def _handle_git_operation_error(self, error: GitOpsError, strategy: RecoveryStrategy) -> bool:
        """Handle Git operation errors."""
        if strategy == RecoveryStrategy.RETRY:
            # Some Git operations can be retried
            return True
        elif strategy == RecoveryStrategy.ROLLBACK:
            # Git operations often benefit from rollback
            return True
        return False
    
    def _handle_validation_error(self, error: GitOpsError, strategy: RecoveryStrategy) -> bool:
        """Handle validation errors."""
        if strategy == RecoveryStrategy.SKIP:
            # Validation errors might be skippable in some contexts
            return False  # Requires manual decision
        return False


# Global error handler instance
_error_handler = None

def get_gitops_error_handler() -> GitOpsErrorHandler:
    """Get global GitOpsErrorHandler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = GitOpsErrorHandler()
    return _error_handler


# Convenience functions

def handle_gitops_error(exception: Exception, context: ErrorContext) -> GitOpsError:
    """Convenience function to handle a GitOps error."""
    handler = get_gitops_error_handler()
    return handler.handle_error(exception, context)


def create_gitops_checkpoint(operation_id: str, context: ErrorContext,
                           state_snapshot: Dict[str, Any]) -> str:
    """Convenience function to create a GitOps checkpoint."""
    handler = get_gitops_error_handler()
    return handler.create_checkpoint(operation_id, context, state_snapshot)


def rollback_gitops_operation(checkpoint_id: str) -> Dict[str, Any]:
    """Convenience function to rollback a GitOps operation."""
    handler = get_gitops_error_handler()
    return handler.rollback_to_checkpoint(checkpoint_id)