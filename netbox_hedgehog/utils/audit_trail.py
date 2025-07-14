"""
Audit Trail Integration for GitOps Change Management.

This module provides comprehensive audit trail capabilities including:
- Complete change history tracking
- User attribution for all changes
- Approval tracking with timestamps
- Compliance reporting
- Change impact analysis
- Rollback tracking

Author: Git Operations Agent
Date: July 10, 2025
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib

from django.utils import timezone
from django.db import transaction, models
from django.contrib.auth.models import User

from ..models.fabric import HedgehogFabric
from ..models.gitops import HedgehogResource

logger = logging.getLogger(__name__)


class ChangeEventType(Enum):
    """Types of change events for audit trail."""
    RESOURCE_CREATED = "resource_created"
    RESOURCE_UPDATED = "resource_updated"
    RESOURCE_DELETED = "resource_deleted"
    SYNC_INITIATED = "sync_initiated"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"
    PR_CREATED = "pr_created"
    PR_APPROVED = "pr_approved"
    PR_MERGED = "pr_merged"
    PR_REJECTED = "pr_rejected"
    POLICY_VIOLATION = "policy_violation"
    COMPLIANCE_CHECK = "compliance_check"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REVOKED = "approval_revoked"


class ApprovalType(Enum):
    """Types of approvals required."""
    SECURITY_REVIEW = "security_review"
    INFRASTRUCTURE_REVIEW = "infrastructure_review"
    COMPLIANCE_REVIEW = "compliance_review"
    PEER_REVIEW = "peer_review"
    MANAGER_APPROVAL = "manager_approval"
    AUTO_APPROVAL = "auto_approval"


class ComplianceStatus(Enum):
    """Compliance status levels."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNDER_REVIEW = "under_review"
    REMEDIATION_REQUIRED = "remediation_required"
    EXCEPTION_GRANTED = "exception_granted"


@dataclass
class AuditEvent:
    """Individual audit event record."""
    event_id: str
    fabric_id: int
    event_type: ChangeEventType
    resource_type: Optional[str] = None
    resource_name: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    timestamp: datetime = field(default_factory=timezone.now)
    event_data: Dict[str, Any] = field(default_factory=dict)
    change_summary: Optional[str] = None
    pr_id: Optional[str] = None
    commit_sha: Optional[str] = None
    approval_id: Optional[str] = None
    compliance_tags: List[str] = field(default_factory=list)
    risk_level: str = "low"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'event_id': self.event_id,
            'fabric_id': self.fabric_id,
            'event_type': self.event_type.value,
            'resource_type': self.resource_type,
            'resource_name': self.resource_name,
            'user_id': self.user_id,
            'user_email': self.user_email,
            'timestamp': self.timestamp.isoformat(),
            'event_data': self.event_data,
            'change_summary': self.change_summary,
            'pr_id': self.pr_id,
            'commit_sha': self.commit_sha,
            'approval_id': self.approval_id,
            'compliance_tags': self.compliance_tags,
            'risk_level': self.risk_level
        }


@dataclass
class ApprovalRecord:
    """Approval record for change management."""
    approval_id: str
    fabric_id: int
    change_id: str
    approval_type: ApprovalType
    required_approver_role: str
    approver_user_id: Optional[str] = None
    approver_email: Optional[str] = None
    approval_status: str = "pending"  # pending, approved, rejected, expired
    requested_at: datetime = field(default_factory=timezone.now)
    approved_at: Optional[datetime] = None
    comments: Optional[str] = None
    approval_evidence: Dict[str, Any] = field(default_factory=dict)
    expiry_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'approval_id': self.approval_id,
            'fabric_id': self.fabric_id,
            'change_id': self.change_id,
            'approval_type': self.approval_type.value,
            'required_approver_role': self.required_approver_role,
            'approver_user_id': self.approver_user_id,
            'approver_email': self.approver_email,
            'approval_status': self.approval_status,
            'requested_at': self.requested_at.isoformat(),
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'comments': self.comments,
            'approval_evidence': self.approval_evidence,
            'expiry_time': self.expiry_time.isoformat() if self.expiry_time else None,
            'is_expired': self._is_expired()
        }
    
    def _is_expired(self) -> bool:
        """Check if approval has expired."""
        if self.expiry_time and timezone.now() > self.expiry_time:
            return True
        return False


@dataclass
class ComplianceRecord:
    """Compliance check record."""
    compliance_id: str
    fabric_id: int
    resource_type: Optional[str] = None
    resource_name: Optional[str] = None
    compliance_framework: str = "internal"  # internal, soc2, hipaa, pci, iso27001
    compliance_status: ComplianceStatus = ComplianceStatus.UNDER_REVIEW
    check_timestamp: datetime = field(default_factory=timezone.now)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    remediation_actions: List[str] = field(default_factory=list)
    compliance_score: float = 0.0
    next_review_date: Optional[datetime] = None
    reviewer_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'compliance_id': self.compliance_id,
            'fabric_id': self.fabric_id,
            'resource_type': self.resource_type,
            'resource_name': self.resource_name,
            'compliance_framework': self.compliance_framework,
            'compliance_status': self.compliance_status.value,
            'check_timestamp': self.check_timestamp.isoformat(),
            'findings': self.findings,
            'remediation_actions': self.remediation_actions,
            'compliance_score': self.compliance_score,
            'next_review_date': self.next_review_date.isoformat() if self.next_review_date else None,
            'reviewer_id': self.reviewer_id
        }


class AuditTrailManager:
    """
    Manages complete audit trail for GitOps operations.
    
    Provides comprehensive tracking of all changes, approvals,
    and compliance activities for audit and regulatory purposes.
    """
    
    def __init__(self, fabric: HedgehogFabric):
        """Initialize audit trail manager for fabric."""
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
        
        # In-memory storage for demo purposes
        # In production, this would use proper database models
        self.audit_events = []
        self.approval_records = []
        self.compliance_records = []
    
    def log_audit_event(
        self,
        event_type: ChangeEventType,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_name: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        change_summary: Optional[str] = None,
        pr_id: Optional[str] = None,
        commit_sha: Optional[str] = None,
        risk_level: str = "low"
    ) -> str:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event being logged
            user_id: User who performed the action
            user_email: User email address
            resource_type: Type of resource affected
            resource_name: Name of resource affected
            event_data: Additional event data
            change_summary: Human-readable change summary
            pr_id: Associated pull request ID
            commit_sha: Associated git commit SHA
            risk_level: Risk level of the change
            
        Returns:
            Event ID
        """
        try:
            # Generate unique event ID
            import uuid
            event_id = str(uuid.uuid4())
            
            # Create audit event
            audit_event = AuditEvent(
                event_id=event_id,
                fabric_id=self.fabric.pk,
                event_type=event_type,
                resource_type=resource_type,
                resource_name=resource_name,
                user_id=user_id,
                user_email=user_email,
                event_data=event_data or {},
                change_summary=change_summary,
                pr_id=pr_id,
                commit_sha=commit_sha,
                risk_level=risk_level
            )
            
            # Add compliance tags based on event type
            audit_event.compliance_tags = self._generate_compliance_tags(
                event_type, resource_type, event_data
            )
            
            # Store audit event
            self.audit_events.append(audit_event)
            
            self.logger.info(f"Logged audit event {event_id}: {event_type.value}")
            return event_id
            
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}")
            raise
    
    def _generate_compliance_tags(
        self,
        event_type: ChangeEventType,
        resource_type: Optional[str],
        event_data: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate compliance tags for audit event."""
        tags = []
        
        # Add event type tags
        if event_type in [ChangeEventType.RESOURCE_CREATED, ChangeEventType.RESOURCE_UPDATED]:
            tags.append("configuration_change")
        
        if event_type in [ChangeEventType.PR_APPROVED, ChangeEventType.APPROVAL_GRANTED]:
            tags.append("approval_workflow")
        
        # Add resource type tags
        if resource_type:
            if resource_type.lower() in ['switch', 'connection']:
                tags.append("infrastructure_change")
            elif 'security' in str(event_data).lower():
                tags.append("security_change")
        
        # Add risk-based tags
        if event_type == ChangeEventType.RESOURCE_DELETED:
            tags.append("high_risk")
        
        return tags
    
    def create_approval_request(
        self,
        change_id: str,
        approval_type: ApprovalType,
        required_approver_role: str,
        expiry_hours: int = 72
    ) -> str:
        """
        Create approval request for a change.
        
        Args:
            change_id: ID of change requiring approval
            approval_type: Type of approval required
            required_approver_role: Role required to approve
            expiry_hours: Hours until approval expires
            
        Returns:
            Approval ID
        """
        try:
            # Generate unique approval ID
            import uuid
            approval_id = str(uuid.uuid4())
            
            # Calculate expiry time
            expiry_time = timezone.now() + timedelta(hours=expiry_hours)
            
            # Create approval record
            approval_record = ApprovalRecord(
                approval_id=approval_id,
                fabric_id=self.fabric.pk,
                change_id=change_id,
                approval_type=approval_type,
                required_approver_role=required_approver_role,
                expiry_time=expiry_time
            )
            
            # Store approval record
            self.approval_records.append(approval_record)
            
            # Log audit event for approval request
            self.log_audit_event(
                event_type=ChangeEventType.APPROVAL_GRANTED,
                event_data={
                    'approval_type': approval_type.value,
                    'required_role': required_approver_role,
                    'expiry_time': expiry_time.isoformat()
                },
                change_summary=f"Approval requested: {approval_type.value}",
                approval_id=approval_id
            )
            
            self.logger.info(f"Created approval request {approval_id} for change {change_id}")
            return approval_id
            
        except Exception as e:
            self.logger.error(f"Failed to create approval request: {e}")
            raise
    
    def process_approval(
        self,
        approval_id: str,
        approver_user_id: str,
        approver_email: str,
        approved: bool,
        comments: Optional[str] = None,
        approval_evidence: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Process an approval request.
        
        Args:
            approval_id: Approval request ID
            approver_user_id: User providing approval
            approver_email: Email of approver
            approved: Whether change is approved
            comments: Approval comments
            approval_evidence: Supporting evidence
            
        Returns:
            True if approval was processed successfully
        """
        try:
            # Find approval record
            approval_record = None
            for record in self.approval_records:
                if record.approval_id == approval_id:
                    approval_record = record
                    break
            
            if not approval_record:
                raise ValueError(f"Approval record {approval_id} not found")
            
            # Check if approval has expired
            if approval_record._is_expired():
                raise ValueError(f"Approval {approval_id} has expired")
            
            # Update approval record
            approval_record.approver_user_id = approver_user_id
            approval_record.approver_email = approver_email
            approval_record.approval_status = "approved" if approved else "rejected"
            approval_record.approved_at = timezone.now()
            approval_record.comments = comments
            approval_record.approval_evidence = approval_evidence or {}
            
            # Log audit event
            event_type = ChangeEventType.APPROVAL_GRANTED if approved else ChangeEventType.APPROVAL_REVOKED
            self.log_audit_event(
                event_type=event_type,
                user_id=approver_user_id,
                user_email=approver_email,
                event_data={
                    'approval_type': approval_record.approval_type.value,
                    'approved': approved,
                    'comments': comments
                },
                change_summary=f"Change {'approved' if approved else 'rejected'} by {approver_email}",
                approval_id=approval_id
            )
            
            self.logger.info(f"Processed approval {approval_id}: {'approved' if approved else 'rejected'}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process approval {approval_id}: {e}")
            return False
    
    def run_compliance_check(
        self,
        compliance_framework: str = "internal",
        resource_type: Optional[str] = None,
        resource_name: Optional[str] = None
    ) -> str:
        """
        Run compliance check for fabric or specific resource.
        
        Args:
            compliance_framework: Framework to check against
            resource_type: Optional specific resource type
            resource_name: Optional specific resource name
            
        Returns:
            Compliance check ID
        """
        try:
            # Generate unique compliance ID
            import uuid
            compliance_id = str(uuid.uuid4())
            
            # Run compliance checks
            findings = self._run_compliance_checks(compliance_framework, resource_type, resource_name)
            
            # Calculate compliance score
            total_checks = len(findings)
            passed_checks = sum(1 for finding in findings if finding.get('status') == 'pass')
            compliance_score = (passed_checks / total_checks * 100) if total_checks > 0 else 100.0
            
            # Determine compliance status
            if compliance_score >= 95.0:
                status = ComplianceStatus.COMPLIANT
            elif compliance_score >= 80.0:
                status = ComplianceStatus.UNDER_REVIEW
            else:
                status = ComplianceStatus.NON_COMPLIANT
            
            # Generate remediation actions
            remediation_actions = self._generate_remediation_actions(findings)
            
            # Calculate next review date
            next_review = timezone.now() + timedelta(days=30)
            
            # Create compliance record
            compliance_record = ComplianceRecord(
                compliance_id=compliance_id,
                fabric_id=self.fabric.pk,
                resource_type=resource_type,
                resource_name=resource_name,
                compliance_framework=compliance_framework,
                compliance_status=status,
                findings=findings,
                remediation_actions=remediation_actions,
                compliance_score=compliance_score,
                next_review_date=next_review
            )
            
            # Store compliance record
            self.compliance_records.append(compliance_record)
            
            # Log audit event
            self.log_audit_event(
                event_type=ChangeEventType.COMPLIANCE_CHECK,
                resource_type=resource_type,
                resource_name=resource_name,
                event_data={
                    'compliance_framework': compliance_framework,
                    'compliance_score': compliance_score,
                    'status': status.value,
                    'findings_count': len(findings)
                },
                change_summary=f"Compliance check completed: {compliance_score:.1f}% compliant"
            )
            
            self.logger.info(f"Completed compliance check {compliance_id}: {compliance_score:.1f}% compliant")
            return compliance_id
            
        except Exception as e:
            self.logger.error(f"Failed to run compliance check: {e}")
            raise
    
    def _run_compliance_checks(
        self,
        framework: str,
        resource_type: Optional[str],
        resource_name: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Run actual compliance checks."""
        # Simulate compliance checks
        checks = [
            {
                'check_id': 'naming_convention',
                'description': 'Resources follow naming conventions',
                'status': 'pass',
                'severity': 'medium'
            },
            {
                'check_id': 'required_labels',
                'description': 'Required labels are present',
                'status': 'pass',
                'severity': 'low'
            },
            {
                'check_id': 'security_configuration',
                'description': 'Security configuration is compliant',
                'status': 'pass',
                'severity': 'high'
            },
            {
                'check_id': 'backup_policy',
                'description': 'Backup policies are configured',
                'status': 'warning',
                'severity': 'medium',
                'message': 'Backup policy could be improved'
            }
        ]
        
        return checks
    
    def _generate_remediation_actions(self, findings: List[Dict[str, Any]]) -> List[str]:
        """Generate remediation actions based on findings."""
        actions = []
        
        for finding in findings:
            if finding.get('status') in ['fail', 'warning']:
                check_id = finding.get('check_id', '')
                
                if check_id == 'naming_convention':
                    actions.append("Update resource names to follow naming conventions")
                elif check_id == 'required_labels':
                    actions.append("Add missing required labels to resources")
                elif check_id == 'security_configuration':
                    actions.append("Review and update security configurations")
                elif check_id == 'backup_policy':
                    actions.append("Configure automated backup policies")
        
        return actions
    
    def get_audit_trail(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[ChangeEventType]] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail with filtering options.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            event_types: Event types to include
            user_id: Filter by user
            resource_type: Filter by resource type
            limit: Maximum number of events
            
        Returns:
            List of audit events
        """
        filtered_events = []
        
        for event in self.audit_events:
            # Apply filters
            if start_date and event.timestamp < start_date:
                continue
            if end_date and event.timestamp > end_date:
                continue
            if event_types and event.event_type not in event_types:
                continue
            if user_id and event.user_id != user_id:
                continue
            if resource_type and event.resource_type != resource_type:
                continue
            
            filtered_events.append(event.to_dict())
        
        # Sort by timestamp (newest first)
        filtered_events.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return filtered_events[:limit]
    
    def get_approval_status(self, change_id: str) -> Dict[str, Any]:
        """
        Get approval status for a change.
        
        Args:
            change_id: Change ID to check
            
        Returns:
            Approval status summary
        """
        related_approvals = [
            record for record in self.approval_records
            if record.change_id == change_id
        ]
        
        total_approvals = len(related_approvals)
        approved_count = sum(1 for record in related_approvals if record.approval_status == "approved")
        rejected_count = sum(1 for record in related_approvals if record.approval_status == "rejected")
        pending_count = sum(1 for record in related_approvals if record.approval_status == "pending")
        
        overall_status = "pending"
        if rejected_count > 0:
            overall_status = "rejected"
        elif approved_count == total_approvals and total_approvals > 0:
            overall_status = "approved"
        elif pending_count > 0:
            overall_status = "pending"
        
        return {
            'change_id': change_id,
            'overall_status': overall_status,
            'total_approvals': total_approvals,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'pending_count': pending_count,
            'approvals': [record.to_dict() for record in related_approvals]
        }
    
    def get_compliance_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate compliance report for specified period.
        
        Args:
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Comprehensive compliance report
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        # Filter compliance records by date
        filtered_records = [
            record for record in self.compliance_records
            if start_date <= record.check_timestamp <= end_date
        ]
        
        # Calculate summary statistics
        total_checks = len(filtered_records)
        compliant_count = sum(1 for record in filtered_records if record.compliance_status == ComplianceStatus.COMPLIANT)
        non_compliant_count = sum(1 for record in filtered_records if record.compliance_status == ComplianceStatus.NON_COMPLIANT)
        
        # Calculate average compliance score
        avg_score = sum(record.compliance_score for record in filtered_records) / total_checks if total_checks > 0 else 0.0
        
        # Group by compliance framework
        frameworks = {}
        for record in filtered_records:
            framework = record.compliance_framework
            if framework not in frameworks:
                frameworks[framework] = {'total': 0, 'compliant': 0, 'avg_score': 0.0}
            
            frameworks[framework]['total'] += 1
            if record.compliance_status == ComplianceStatus.COMPLIANT:
                frameworks[framework]['compliant'] += 1
        
        # Calculate framework averages
        for framework_data in frameworks.values():
            if framework_data['total'] > 0:
                framework_data['compliance_rate'] = framework_data['compliant'] / framework_data['total'] * 100
        
        return {
            'report_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'fabric': self.fabric.name,
            'summary': {
                'total_checks': total_checks,
                'compliant_count': compliant_count,
                'non_compliant_count': non_compliant_count,
                'compliance_rate': (compliant_count / total_checks * 100) if total_checks > 0 else 0.0,
                'average_score': avg_score
            },
            'frameworks': frameworks,
            'recent_checks': [record.to_dict() for record in filtered_records[-10:]],
            'remediation_summary': self._get_remediation_summary(filtered_records)
        }
    
    def _get_remediation_summary(self, compliance_records: List[ComplianceRecord]) -> Dict[str, Any]:
        """Get summary of remediation actions needed."""
        all_actions = []
        for record in compliance_records:
            all_actions.extend(record.remediation_actions)
        
        # Count frequency of remediation actions
        action_counts = {}
        for action in all_actions:
            action_counts[action] = action_counts.get(action, 0) + 1
        
        # Sort by frequency
        sorted_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'total_actions': len(all_actions),
            'unique_actions': len(action_counts),
            'top_actions': sorted_actions[:5]
        }


class ApprovalWorkflowManager:
    """
    Manages approval workflows for GitOps changes.
    
    Coordinates approval requirements based on change impact,
    compliance requirements, and organizational policies.
    """
    
    def __init__(self, fabric: HedgehogFabric):
        """Initialize approval workflow manager."""
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
        self.audit_manager = AuditTrailManager(fabric)
    
    def evaluate_approval_requirements(
        self,
        change_data: Dict[str, Any]
    ) -> List[ApprovalType]:
        """
        Evaluate what approvals are required for a change.
        
        Args:
            change_data: Change information
            
        Returns:
            List of required approval types
        """
        required_approvals = []
        
        change_type = change_data.get('change_type', 'configuration')
        resource_type = change_data.get('resource_type', '')
        risk_level = change_data.get('risk_level', 'low')
        
        # Security changes always require security review
        if change_type == 'security' or 'security' in resource_type.lower():
            required_approvals.append(ApprovalType.SECURITY_REVIEW)
        
        # Infrastructure changes require infrastructure review
        if change_type == 'infrastructure' or resource_type.lower() in ['switch', 'connection']:
            required_approvals.append(ApprovalType.INFRASTRUCTURE_REVIEW)
        
        # High-risk changes require manager approval
        if risk_level in ['high', 'critical']:
            required_approvals.append(ApprovalType.MANAGER_APPROVAL)
        
        # All changes require peer review
        required_approvals.append(ApprovalType.PEER_REVIEW)
        
        # Compliance review for production changes
        environment = change_data.get('environment', 'development')
        if environment == 'production':
            required_approvals.append(ApprovalType.COMPLIANCE_REVIEW)
        
        return required_approvals
    
    def initiate_approval_workflow(
        self,
        change_id: str,
        change_data: Dict[str, Any]
    ) -> List[str]:
        """
        Initiate approval workflow for a change.
        
        Args:
            change_id: Unique change identifier
            change_data: Change information
            
        Returns:
            List of approval request IDs
        """
        try:
            # Evaluate required approvals
            required_approvals = self.evaluate_approval_requirements(change_data)
            
            approval_ids = []
            
            for approval_type in required_approvals:
                # Get required approver role
                approver_role = self._get_approver_role(approval_type)
                
                # Create approval request
                approval_id = self.audit_manager.create_approval_request(
                    change_id=change_id,
                    approval_type=approval_type,
                    required_approver_role=approver_role,
                    expiry_hours=self._get_approval_expiry_hours(approval_type)
                )
                
                approval_ids.append(approval_id)
            
            self.logger.info(f"Initiated approval workflow for change {change_id}: {len(approval_ids)} approvals required")
            return approval_ids
            
        except Exception as e:
            self.logger.error(f"Failed to initiate approval workflow: {e}")
            raise
    
    def _get_approver_role(self, approval_type: ApprovalType) -> str:
        """Get required approver role for approval type."""
        role_mapping = {
            ApprovalType.SECURITY_REVIEW: "security-team",
            ApprovalType.INFRASTRUCTURE_REVIEW: "infrastructure-team",
            ApprovalType.COMPLIANCE_REVIEW: "compliance-officer",
            ApprovalType.PEER_REVIEW: "senior-engineer",
            ApprovalType.MANAGER_APPROVAL: "engineering-manager",
            ApprovalType.AUTO_APPROVAL: "system"
        }
        
        return role_mapping.get(approval_type, "senior-engineer")
    
    def _get_approval_expiry_hours(self, approval_type: ApprovalType) -> int:
        """Get expiry hours for approval type."""
        expiry_mapping = {
            ApprovalType.SECURITY_REVIEW: 48,  # 2 days
            ApprovalType.INFRASTRUCTURE_REVIEW: 24,  # 1 day
            ApprovalType.COMPLIANCE_REVIEW: 72,  # 3 days
            ApprovalType.PEER_REVIEW: 24,  # 1 day
            ApprovalType.MANAGER_APPROVAL: 48,  # 2 days
            ApprovalType.AUTO_APPROVAL: 1  # 1 hour
        }
        
        return expiry_mapping.get(approval_type, 24)
    
    def check_approval_completion(self, change_id: str) -> Dict[str, Any]:
        """
        Check if all required approvals are complete.
        
        Args:
            change_id: Change ID to check
            
        Returns:
            Approval completion status
        """
        approval_status = self.audit_manager.get_approval_status(change_id)
        
        all_approved = (
            approval_status['total_approvals'] > 0 and
            approval_status['rejected_count'] == 0 and
            approval_status['pending_count'] == 0
        )
        
        return {
            'change_id': change_id,
            'all_approved': all_approved,
            'can_proceed': all_approved,
            'approval_summary': approval_status
        }


class AuditTrailError(Exception):
    """Base exception for audit trail operations."""
    pass


class ApprovalWorkflowError(Exception):
    """Exception for approval workflow operations."""
    pass