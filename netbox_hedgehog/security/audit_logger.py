"""
Security Audit Logger for GitOps Operations

This module provides comprehensive security event logging and audit trail
functionality for all GitOps operations, credential access, and security events.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass, asdict
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)
User = get_user_model()


class SecurityEventType(Enum):
    """Types of security events"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CREDENTIAL_ACCESS = "credential_access"
    FILE_OPERATION = "file_operation"
    API_ACCESS = "api_access"
    PERMISSION_CHECK = "permission_check"
    SECURITY_VIOLATION = "security_violation"
    CONFIGURATION_CHANGE = "configuration_change"
    DATA_ACCESS = "data_access"


class SecurityEventSeverity(Enum):
    """Security event severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Security event data structure"""
    event_type: SecurityEventType
    severity: SecurityEventSeverity
    user_id: Optional[int]
    username: Optional[str]
    fabric_id: Optional[int]
    fabric_name: Optional[str]
    action: str
    resource: str
    details: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    timestamp: datetime
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            'event_type': self.event_type.value,
            'severity': self.severity.value,
            'user_id': self.user_id,
            'username': self.username,
            'fabric_id': self.fabric_id,
            'fabric_name': self.fabric_name,
            'action': self.action,
            'resource': self.resource,
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'success': self.success,
            'timestamp': self.timestamp.isoformat(),
            'session_id': self.session_id,
            'request_id': self.request_id
        }


class SecurityAuditLogger:
    """
    Comprehensive security audit logging system.
    
    Provides centralized logging for all security-relevant events in the GitOps system,
    including credential access, permission checks, file operations, and security violations.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('hedgehog.security.audit')
        self.event_logger = logging.getLogger('hedgehog.security.events')
        
        # Configure structured logging
        self._configure_logging()
    
    def _configure_logging(self):
        """Configure structured logging for security events"""
        # This would typically configure structured logging to files, 
        # centralized logging systems, or security information and event management (SIEM) systems
        pass
    
    def log_credential_access(
        self, 
        user: Optional[User], 
        repository, 
        action: str,
        details: str = "",
        request=None
    ) -> None:
        """
        Log credential access events.
        
        Args:
            user: User accessing credentials
            repository: Repository being accessed
            action: Type of credential action
            details: Additional details
            request: HTTP request object for context
        """
        try:
            # Determine severity based on action
            severity = SecurityEventSeverity.MEDIUM
            if action in ['credential_decrypted', 'credential_accessed']:
                severity = SecurityEventSeverity.HIGH
            elif action in ['credential_rotation_failed', 'credential_decryption_failed']:
                severity = SecurityEventSeverity.CRITICAL
            
            event = SecurityEvent(
                event_type=SecurityEventType.CREDENTIAL_ACCESS,
                severity=severity,
                user_id=user.id if user else None,
                username=user.username if user else 'system',
                fabric_id=None,
                fabric_name=None,
                action=action,
                resource=f"git_repository:{repository.id}",
                details={
                    'repository_name': repository.name,
                    'repository_url': repository.url,
                    'authentication_type': repository.authentication_type,
                    'action_details': details,
                    'timestamp': timezone.now().isoformat()
                },
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request),
                success='failed' not in action.lower(),
                timestamp=timezone.now(),
                session_id=self._get_session_id(request),
                request_id=self._get_request_id(request)
            )
            
            self._write_security_event(event)
            
        except Exception as e:
            self.logger.error(f"Failed to log credential access event: {str(e)}")
    
    def log_file_operation(
        self, 
        user: User, 
        fabric, 
        file_path: str, 
        operation: str,
        success: bool = True,
        details: Dict[str, Any] = None,
        request=None
    ) -> None:
        """
        Log file manipulation events.
        
        Args:
            user: User performing operation
            fabric: Fabric being modified
            file_path: Path of file being operated on
            operation: Type of operation
            success: Whether operation succeeded
            details: Additional operation details
            request: HTTP request object for context
        """
        try:
            # Determine severity based on operation
            severity = SecurityEventSeverity.LOW
            if operation in ['delete', 'archive']:
                severity = SecurityEventSeverity.MEDIUM
            elif operation in ['credential_file_access', 'config_file_modify']:
                severity = SecurityEventSeverity.HIGH
            
            event = SecurityEvent(
                event_type=SecurityEventType.FILE_OPERATION,
                severity=severity,
                user_id=user.id,
                username=user.username,
                fabric_id=fabric.id if fabric else None,
                fabric_name=fabric.name if fabric else None,
                action=operation,
                resource=f"file:{file_path}",
                details={
                    'file_path': file_path,
                    'operation': operation,
                    'fabric_name': fabric.name if fabric else None,
                    'additional_details': details or {},
                    'timestamp': timezone.now().isoformat()
                },
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request),
                success=success,
                timestamp=timezone.now(),
                session_id=self._get_session_id(request),
                request_id=self._get_request_id(request)
            )
            
            self._write_security_event(event)
            
        except Exception as e:
            self.logger.error(f"Failed to log file operation event: {str(e)}")
    
    def log_permission_check(
        self, 
        user: User, 
        permission: str, 
        granted: bool,
        fabric=None,
        details: str = "",
        request=None
    ) -> None:
        """
        Log permission validation events.
        
        Args:
            user: User being checked
            permission: Permission being checked
            granted: Whether permission was granted
            fabric: Optional fabric context
            details: Additional details
            request: HTTP request object for context
        """
        try:
            # Higher severity for denied permissions
            severity = SecurityEventSeverity.LOW if granted else SecurityEventSeverity.MEDIUM
            
            # Critical severity for admin permission denials
            if not granted and 'admin' in permission.lower():
                severity = SecurityEventSeverity.HIGH
            
            event = SecurityEvent(
                event_type=SecurityEventType.PERMISSION_CHECK,
                severity=severity,
                user_id=user.id,
                username=user.username,
                fabric_id=fabric.id if fabric else None,
                fabric_name=fabric.name if fabric else None,
                action='permission_check',
                resource=f"permission:{permission}",
                details={
                    'permission': permission,
                    'granted': granted,
                    'fabric_context': fabric.name if fabric else None,
                    'check_details': details,
                    'timestamp': timezone.now().isoformat()
                },
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request),
                success=granted,
                timestamp=timezone.now(),
                session_id=self._get_session_id(request),
                request_id=self._get_request_id(request)
            )
            
            self._write_security_event(event)
            
        except Exception as e:
            self.logger.error(f"Failed to log permission check event: {str(e)}")
    
    def log_security_violation(
        self, 
        user: Optional[User], 
        violation_type: str,
        attempted_action: str, 
        reason: str,
        severity: SecurityEventSeverity = SecurityEventSeverity.HIGH,
        fabric=None,
        additional_context: Dict[str, Any] = None,
        request=None
    ) -> None:
        """
        Log security policy violations.
        
        Args:
            user: User who attempted the action
            violation_type: Type of security violation
            attempted_action: Action that was attempted
            reason: Reason for violation
            severity: Severity level
            fabric: Optional fabric context
            additional_context: Additional context information
            request: HTTP request object for context
        """
        try:
            event = SecurityEvent(
                event_type=SecurityEventType.SECURITY_VIOLATION,
                severity=severity,
                user_id=user.id if user else None,
                username=user.username if user else 'anonymous',
                fabric_id=fabric.id if fabric else None,
                fabric_name=fabric.name if fabric else None,
                action=violation_type,
                resource=f"violation:{violation_type}",
                details={
                    'violation_type': violation_type,
                    'attempted_action': attempted_action,
                    'reason': reason,
                    'fabric_context': fabric.name if fabric else None,
                    'additional_context': additional_context or {},
                    'timestamp': timezone.now().isoformat()
                },
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request),
                success=False,
                timestamp=timezone.now(),
                session_id=self._get_session_id(request),
                request_id=self._get_request_id(request)
            )
            
            self._write_security_event(event)
            
            # Also log critical violations at ERROR level
            if severity == SecurityEventSeverity.CRITICAL:
                self.logger.error(
                    f"CRITICAL SECURITY VIOLATION: {violation_type} by {user.username if user else 'anonymous'} - {reason}"
                )
            
        except Exception as e:
            self.logger.error(f"Failed to log security violation event: {str(e)}")
    
    def log_api_access(
        self, 
        user: Optional[User], 
        endpoint: str, 
        method: str,
        success: bool,
        response_code: int,
        fabric=None,
        request_data: Dict[str, Any] = None,
        request=None
    ) -> None:
        """
        Log API access events.
        
        Args:
            user: User making API request
            endpoint: API endpoint accessed
            method: HTTP method
            success: Whether request succeeded
            response_code: HTTP response code
            fabric: Optional fabric context
            request_data: Request data (sanitized)
            request: HTTP request object for context
        """
        try:
            # Determine severity based on response code and endpoint
            severity = SecurityEventSeverity.LOW
            if response_code >= 400:
                severity = SecurityEventSeverity.MEDIUM
            if response_code >= 500 or 'admin' in endpoint.lower():
                severity = SecurityEventSeverity.HIGH
            
            event = SecurityEvent(
                event_type=SecurityEventType.API_ACCESS,
                severity=severity,
                user_id=user.id if user else None,
                username=user.username if user else 'anonymous',
                fabric_id=fabric.id if fabric else None,
                fabric_name=fabric.name if fabric else None,
                action=f"{method} {endpoint}",
                resource=f"api_endpoint:{endpoint}",
                details={
                    'endpoint': endpoint,
                    'method': method,
                    'response_code': response_code,
                    'fabric_context': fabric.name if fabric else None,
                    'request_data': self._sanitize_request_data(request_data) if request_data else {},
                    'timestamp': timezone.now().isoformat()
                },
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request),
                success=success,
                timestamp=timezone.now(),
                session_id=self._get_session_id(request),
                request_id=self._get_request_id(request)
            )
            
            self._write_security_event(event)
            
        except Exception as e:
            self.logger.error(f"Failed to log API access event: {str(e)}")
    
    def log_authentication_event(
        self, 
        username: str, 
        success: bool,
        auth_method: str = "password",
        failure_reason: str = "",
        request=None
    ) -> None:
        """
        Log authentication events.
        
        Args:
            username: Username attempting authentication
            success: Whether authentication succeeded
            auth_method: Authentication method used
            failure_reason: Reason for failure (if any)
            request: HTTP request object for context
        """
        try:
            severity = SecurityEventSeverity.LOW if success else SecurityEventSeverity.MEDIUM
            
            event = SecurityEvent(
                event_type=SecurityEventType.AUTHENTICATION,
                severity=severity,
                user_id=None,  # Don't have user ID yet during auth
                username=username,
                fabric_id=None,
                fabric_name=None,
                action='login_attempt',
                resource=f"authentication:{auth_method}",
                details={
                    'auth_method': auth_method,
                    'failure_reason': failure_reason,
                    'timestamp': timezone.now().isoformat()
                },
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request),
                success=success,
                timestamp=timezone.now(),
                session_id=self._get_session_id(request),
                request_id=self._get_request_id(request)
            )
            
            self._write_security_event(event)
            
        except Exception as e:
            self.logger.error(f"Failed to log authentication event: {str(e)}")
    
    def get_security_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        fabric_id: Optional[int] = None,
        event_type: Optional[SecurityEventType] = None,
        severity: Optional[SecurityEventSeverity] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve security events based on filters.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            user_id: User ID filter
            fabric_id: Fabric ID filter
            event_type: Event type filter
            severity: Severity filter
            limit: Maximum number of events to return
            
        Returns:
            List of security events
        """
        try:
            # This would query a security events database or log aggregation system
            # For now, return empty list as placeholder
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve security events: {str(e)}")
            return []
    
    def generate_security_report(
        self,
        start_date: datetime,
        end_date: datetime,
        report_type: str = "summary"
    ) -> Dict[str, Any]:
        """
        Generate security audit report.
        
        Args:
            start_date: Report start date
            end_date: Report end date
            report_type: Type of report to generate
            
        Returns:
            Security report data
        """
        try:
            events = self.get_security_events(start_date=start_date, end_date=end_date)
            
            report = {
                'report_type': report_type,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'summary': {
                    'total_events': len(events),
                    'critical_events': len([e for e in events if e.get('severity') == 'critical']),
                    'failed_attempts': len([e for e in events if not e.get('success', True)]),
                    'unique_users': len(set(e.get('username') for e in events if e.get('username')))
                },
                'events_by_type': {},
                'events_by_severity': {},
                'top_users': {},
                'generated_at': timezone.now().isoformat()
            }
            
            # Analyze events (placeholder implementation)
            for event in events:
                event_type = event.get('event_type', 'unknown')
                severity = event.get('severity', 'unknown')
                
                report['events_by_type'][event_type] = report['events_by_type'].get(event_type, 0) + 1
                report['events_by_severity'][severity] = report['events_by_severity'].get(severity, 0) + 1
            
            return report
            
        except Exception as e:
            self.logger.error(f"Failed to generate security report: {str(e)}")
            return {
                'error': str(e),
                'generated_at': timezone.now().isoformat()
            }
    
    def _write_security_event(self, event: SecurityEvent) -> None:
        """
        Write security event to appropriate logging destinations.
        
        Args:
            event: Security event to write
        """
        try:
            # Convert event to JSON for structured logging
            event_json = json.dumps(event.to_dict(), cls=DjangoJSONEncoder, indent=None)
            
            # Write to security event log
            self.event_logger.info(event_json)
            
            # Also write to main security log with formatted message
            log_message = f"SECURITY_EVENT: {event.event_type.value.upper()} - {event.action} by {event.username} - {'SUCCESS' if event.success else 'FAILED'}"
            if event.fabric_name:
                log_message += f" (Fabric: {event.fabric_name})"
            
            if event.severity == SecurityEventSeverity.CRITICAL:
                self.logger.critical(log_message)
            elif event.severity == SecurityEventSeverity.HIGH:
                self.logger.error(log_message)
            elif event.severity == SecurityEventSeverity.MEDIUM:
                self.logger.warning(log_message)
            else:
                self.logger.info(log_message)
            
            # In a production environment, you might also:
            # - Send to SIEM system
            # - Store in security events database
            # - Trigger alerts for critical events
            # - Send notifications for policy violations
            
        except Exception as e:
            self.logger.error(f"Failed to write security event: {str(e)}")
    
    def _get_client_ip(self, request) -> Optional[str]:
        """Extract client IP address from request"""
        if not request:
            return None
        
        # Check for forwarded headers first
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        return request.META.get('REMOTE_ADDR')
    
    def _get_user_agent(self, request) -> Optional[str]:
        """Extract user agent from request"""
        if not request:
            return None
        return request.META.get('HTTP_USER_AGENT')
    
    def _get_session_id(self, request) -> Optional[str]:
        """Extract session ID from request"""
        if not request or not hasattr(request, 'session'):
            return None
        return request.session.session_key
    
    def _get_request_id(self, request) -> Optional[str]:
        """Extract or generate request ID"""
        if not request:
            return None
        
        # Check if request ID is set by middleware
        return getattr(request, 'request_id', None)
    
    def _sanitize_request_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize request data for logging (remove sensitive information).
        
        Args:
            data: Request data to sanitize
            
        Returns:
            Sanitized data
        """
        if not data:
            return {}
        
        # Fields to exclude from logging
        sensitive_fields = {
            'password', 'token', 'secret', 'key', 'credential', 
            'private_key', 'passphrase', 'auth', 'authorization'
        }
        
        sanitized = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_request_data(value)
            else:
                sanitized[key] = value
        
        return sanitized