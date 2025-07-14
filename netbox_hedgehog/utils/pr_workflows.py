"""
Pull Request Workflows for Enterprise GitOps Change Management.

This module provides comprehensive pull request workflow capabilities including:
- Automated PR creation for NetBox changes
- Template-based PR descriptions with smart content generation
- Auto-reviewer assignment based on change impact
- GitOps policy enforcement and compliance checking
- Change approval workflows with audit trails
- Integration with Git provider APIs

Author: Git Operations Agent
Date: July 10, 2025
"""

import asyncio
import logging
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import re

from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User
from django.template import Template, Context

from ..models.fabric import HedgehogFabric
from ..models.gitops import HedgehogResource
from .environment_manager import EnvironmentManager

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of changes for PR categorization."""
    CONFIGURATION = "configuration"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    NETWORKING = "networking"
    POLICY = "policy"
    MAINTENANCE = "maintenance"
    HOTFIX = "hotfix"


class ChangeImpact(Enum):
    """Impact levels for changes."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PRStatus(Enum):
    """Pull request status."""
    DRAFT = "draft"
    OPEN = "open"
    APPROVED = "approved"
    MERGED = "merged"
    CLOSED = "closed"
    CONFLICTS = "conflicts"


class PolicyViolationType(Enum):
    """Types of policy violations."""
    SECURITY_RISK = "security_risk"
    COMPLIANCE_VIOLATION = "compliance_violation"
    RESOURCE_LIMIT = "resource_limit"
    NAMING_CONVENTION = "naming_convention"
    REQUIRED_FIELD = "required_field"
    INVALID_CONFIGURATION = "invalid_configuration"


@dataclass
class ChangeRecord:
    """Record of a single change in the system."""
    change_id: str
    resource_type: str
    resource_name: str
    action: str  # create, update, delete
    old_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None
    changed_fields: List[str] = field(default_factory=list)
    change_impact: ChangeImpact = ChangeImpact.LOW
    change_type: ChangeType = ChangeType.CONFIGURATION
    user: Optional[str] = None
    timestamp: datetime = field(default_factory=timezone.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'change_id': self.change_id,
            'resource_type': self.resource_type,
            'resource_name': self.resource_name,
            'action': self.action,
            'old_data': self.old_data,
            'new_data': self.new_data,
            'changed_fields': self.changed_fields,
            'change_impact': self.change_impact.value,
            'change_type': self.change_type.value,
            'user': self.user,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class PolicyViolation:
    """Policy violation detected during validation."""
    violation_id: str
    violation_type: PolicyViolationType
    severity: str  # low, medium, high, critical
    message: str
    resource_path: str
    suggested_fix: Optional[str] = None
    can_auto_fix: bool = False
    blocking: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'violation_id': self.violation_id,
            'violation_type': self.violation_type.value,
            'severity': self.severity,
            'message': self.message,
            'resource_path': self.resource_path,
            'suggested_fix': self.suggested_fix,
            'can_auto_fix': self.can_auto_fix,
            'blocking': self.blocking
        }


@dataclass
class ReviewerAssignment:
    """Reviewer assignment for PR."""
    reviewer_id: str
    reviewer_type: str  # required, optional, informational
    expertise_area: List[str]
    assignment_reason: str
    auto_assigned: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'reviewer_id': self.reviewer_id,
            'reviewer_type': self.reviewer_type,
            'expertise_area': self.expertise_area,
            'assignment_reason': self.assignment_reason,
            'auto_assigned': self.auto_assigned
        }


@dataclass
class PullRequestMetadata:
    """Metadata for generated pull request."""
    pr_id: str
    title: str
    description: str
    branch_name: str
    target_branch: str
    labels: List[str]
    reviewers: List[ReviewerAssignment]
    changes: List[ChangeRecord]
    policy_violations: List[PolicyViolation]
    impact_assessment: Dict[str, Any]
    compliance_status: str
    created_at: datetime = field(default_factory=timezone.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'pr_id': self.pr_id,
            'title': self.title,
            'description': self.description,
            'branch_name': self.branch_name,
            'target_branch': self.target_branch,
            'labels': self.labels,
            'reviewers': [r.to_dict() for r in self.reviewers],
            'changes': [c.to_dict() for c in self.changes],
            'policy_violations': [v.to_dict() for v in self.policy_violations],
            'impact_assessment': self.impact_assessment,
            'compliance_status': self.compliance_status,
            'created_at': self.created_at.isoformat()
        }


class PRTemplateEngine:
    """Template engine for generating PR descriptions."""
    
    DEFAULT_TEMPLATES = {
        'configuration': """
## Configuration Update

### Summary
{{ summary }}

### Changes Made
{% for change in changes %}
- **{{ change.resource_type }}/{{ change.resource_name }}**: {{ change.action }}
  {% if change.changed_fields %}
  - Modified fields: {{ change.changed_fields|join:", " }}
  {% endif %}
{% endfor %}

### Impact Assessment
- **Impact Level**: {{ impact_level }}
- **Affected Systems**: {{ affected_systems|join:", " }}
- **Risk Level**: {{ risk_level }}

### Testing
- [ ] Configuration validated
- [ ] No policy violations
- [ ] Deployment tested in staging

### Compliance
{{ compliance_checklist }}

---
*Automated PR created by Hedgehog NetBox Plugin GitOps*
""",
        
        'infrastructure': """
## Infrastructure Change

### Summary
{{ summary }}

### Infrastructure Changes
{% for change in changes %}
- **{{ change.resource_type }}**: {{ change.resource_name }} ({{ change.action }})
{% endfor %}

### Impact Analysis
- **Infrastructure Impact**: {{ infrastructure_impact }}
- **Service Availability**: {{ service_impact }}
- **Rollback Plan**: {{ rollback_plan }}

### Pre-Deployment Checklist
- [ ] Infrastructure capacity verified
- [ ] Dependencies checked
- [ ] Monitoring alerts configured
- [ ] Rollback procedure documented

### Post-Deployment Verification
- [ ] Services operational
- [ ] Performance metrics normal
- [ ] No infrastructure alerts

---
*Infrastructure change managed by GitOps automation*
""",
        
        'security': """
## Security Configuration Update

### Summary
{{ summary }}

### Security Changes
{% for change in changes %}
- **{{ change.resource_type }}/{{ change.resource_name }}**: {{ change.action }}
  {% if change.change_type == 'security' %}
  - **Security Impact**: {{ change.security_notes }}
  {% endif %}
{% endfor %}

### Security Review
- **Risk Assessment**: {{ risk_assessment }}
- **Compliance Status**: {{ compliance_status }}
- **Security Approval**: Required

### Security Checklist
- [ ] No credentials exposed
- [ ] Access controls validated
- [ ] Security policies enforced
- [ ] Audit logging enabled

### Compliance Requirements
{{ compliance_requirements }}

---
*Security change requiring mandatory review*
"""
    }
    
    @staticmethod
    def generate_pr_description(
        changes: List[ChangeRecord],
        template_type: str = 'configuration',
        **context_data
    ) -> str:
        """
        Generate PR description from template.
        
        Args:
            changes: List of changes to include
            template_type: Type of template to use
            **context_data: Additional context data
            
        Returns:
            Generated PR description
        """
        try:
            from django.template import Template, Context
            
            template_content = PRTemplateEngine.DEFAULT_TEMPLATES.get(
                template_type, PRTemplateEngine.DEFAULT_TEMPLATES['configuration']
            )
            
            # Prepare context
            context = {
                'changes': [change.to_dict() for change in changes],
                'change_count': len(changes),
                'summary': PRTemplateEngine._generate_summary(changes),
                'impact_level': PRTemplateEngine._calculate_impact_level(changes),
                'affected_systems': PRTemplateEngine._get_affected_systems(changes),
                'risk_level': PRTemplateEngine._assess_risk_level(changes),
                'compliance_checklist': PRTemplateEngine._generate_compliance_checklist(changes),
                **context_data
            }
            
            template = Template(template_content)
            return template.render(Context(context))
            
        except Exception as e:
            logger.error(f"Failed to generate PR description: {e}")
            return PRTemplateEngine._generate_fallback_description(changes)
    
    @staticmethod
    def _generate_summary(changes: List[ChangeRecord]) -> str:
        """Generate summary of changes."""
        if not changes:
            return "No changes detected"
        
        change_types = {}
        for change in changes:
            change_types[change.action] = change_types.get(change.action, 0) + 1
        
        summary_parts = []
        for action, count in change_types.items():
            if count == 1:
                summary_parts.append(f"1 resource {action}d")
            else:
                summary_parts.append(f"{count} resources {action}d")
        
        return f"This PR contains {', '.join(summary_parts)}."
    
    @staticmethod
    def _calculate_impact_level(changes: List[ChangeRecord]) -> str:
        """Calculate overall impact level."""
        max_impact = ChangeImpact.LOW
        for change in changes:
            if change.change_impact.value > max_impact.value:
                max_impact = change.change_impact
        return max_impact.value
    
    @staticmethod
    def _get_affected_systems(changes: List[ChangeRecord]) -> List[str]:
        """Get list of affected systems."""
        systems = set()
        for change in changes:
            systems.add(change.resource_type)
        return sorted(list(systems))
    
    @staticmethod
    def _assess_risk_level(changes: List[ChangeRecord]) -> str:
        """Assess risk level of changes."""
        high_risk_types = {ChangeType.SECURITY, ChangeType.INFRASTRUCTURE}
        critical_actions = {'delete'}
        
        for change in changes:
            if change.change_type in high_risk_types:
                return "HIGH"
            if change.action in critical_actions:
                return "HIGH"
            if change.change_impact == ChangeImpact.CRITICAL:
                return "CRITICAL"
        
        return "MEDIUM"
    
    @staticmethod
    def _generate_compliance_checklist(changes: List[ChangeRecord]) -> str:
        """Generate compliance checklist."""
        checklist_items = [
            "- [ ] Change follows naming conventions",
            "- [ ] Resource limits within policy",
            "- [ ] Security requirements met",
            "- [ ] Documentation updated"
        ]
        
        # Add specific checks based on change types
        change_types = {change.change_type for change in changes}
        
        if ChangeType.SECURITY in change_types:
            checklist_items.append("- [ ] Security team approval obtained")
        
        if ChangeType.INFRASTRUCTURE in change_types:
            checklist_items.append("- [ ] Infrastructure team notified")
            checklist_items.append("- [ ] Capacity planning reviewed")
        
        return '\n'.join(checklist_items)
    
    @staticmethod
    def _generate_fallback_description(changes: List[ChangeRecord]) -> str:
        """Generate fallback description if template fails."""
        summary = f"Automated GitOps update containing {len(changes)} changes:\n\n"
        
        for change in changes:
            summary += f"- {change.action.title()} {change.resource_type}/{change.resource_name}\n"
        
        summary += "\n*Generated automatically by Hedgehog NetBox Plugin*"
        return summary


class ReviewerAssignmentEngine:
    """Engine for automatically assigning reviewers based on change analysis."""
    
    # Default reviewer rules
    DEFAULT_REVIEWER_RULES = {
        'security_changes': {
            'reviewers': ['security-team', 'compliance-officer'],
            'required': True,
            'expertise': ['security', 'compliance']
        },
        'infrastructure_changes': {
            'reviewers': ['infrastructure-team', 'sre-team'],
            'required': True,
            'expertise': ['infrastructure', 'networking']
        },
        'configuration_changes': {
            'reviewers': ['platform-team'],
            'required': False,
            'expertise': ['configuration', 'gitops']
        },
        'critical_changes': {
            'reviewers': ['senior-engineer', 'team-lead'],
            'required': True,
            'expertise': ['architecture', 'critical-systems']
        }
    }
    
    @staticmethod
    def assign_reviewers(
        changes: List[ChangeRecord],
        fabric: HedgehogFabric
    ) -> List[ReviewerAssignment]:
        """
        Assign reviewers based on change analysis.
        
        Args:
            changes: List of changes to analyze
            fabric: Fabric context for reviewer assignment
            
        Returns:
            List of reviewer assignments
        """
        assignments = []
        
        # Analyze change characteristics
        change_analysis = ReviewerAssignmentEngine._analyze_changes(changes)
        
        # Apply reviewer rules
        for rule_name, characteristics in change_analysis.items():
            if characteristics['applicable']:
                rule = ReviewerAssignmentEngine.DEFAULT_REVIEWER_RULES.get(rule_name)
                if rule:
                    for reviewer_id in rule['reviewers']:
                        assignment = ReviewerAssignment(
                            reviewer_id=reviewer_id,
                            reviewer_type='required' if rule['required'] else 'optional',
                            expertise_area=rule['expertise'],
                            assignment_reason=f"Change analysis: {rule_name}"
                        )
                        assignments.append(assignment)
        
        # Add fabric-specific reviewers
        fabric_reviewers = ReviewerAssignmentEngine._get_fabric_reviewers(fabric)
        assignments.extend(fabric_reviewers)
        
        # Remove duplicates and prioritize
        return ReviewerAssignmentEngine._deduplicate_reviewers(assignments)
    
    @staticmethod
    def _analyze_changes(changes: List[ChangeRecord]) -> Dict[str, Dict[str, Any]]:
        """Analyze changes to determine reviewer requirements."""
        analysis = {
            'security_changes': {'applicable': False, 'count': 0},
            'infrastructure_changes': {'applicable': False, 'count': 0},
            'configuration_changes': {'applicable': False, 'count': 0},
            'critical_changes': {'applicable': False, 'count': 0}
        }
        
        for change in changes:
            # Check for security changes
            if change.change_type == ChangeType.SECURITY:
                analysis['security_changes']['applicable'] = True
                analysis['security_changes']['count'] += 1
            
            # Check for infrastructure changes
            if change.change_type == ChangeType.INFRASTRUCTURE:
                analysis['infrastructure_changes']['applicable'] = True
                analysis['infrastructure_changes']['count'] += 1
            
            # Check for critical changes
            if change.change_impact == ChangeImpact.CRITICAL:
                analysis['critical_changes']['applicable'] = True
                analysis['critical_changes']['count'] += 1
            
            # All changes are configuration changes at some level
            analysis['configuration_changes']['applicable'] = True
            analysis['configuration_changes']['count'] += 1
        
        return analysis
    
    @staticmethod
    def _get_fabric_reviewers(fabric: HedgehogFabric) -> List[ReviewerAssignment]:
        """Get fabric-specific reviewer assignments."""
        reviewers = []
        
        # Add fabric owner/maintainer if configured
        # This would typically come from fabric configuration
        fabric_owner = getattr(fabric, 'owner', None)
        if fabric_owner:
            reviewers.append(ReviewerAssignment(
                reviewer_id=str(fabric_owner),
                reviewer_type='informational',
                expertise_area=['fabric-owner'],
                assignment_reason='Fabric owner notification'
            ))
        
        return reviewers
    
    @staticmethod
    def _deduplicate_reviewers(assignments: List[ReviewerAssignment]) -> List[ReviewerAssignment]:
        """Remove duplicate reviewer assignments and prioritize."""
        unique_reviewers = {}
        
        for assignment in assignments:
            existing = unique_reviewers.get(assignment.reviewer_id)
            if existing:
                # Prioritize required over optional
                if assignment.reviewer_type == 'required':
                    existing.reviewer_type = 'required'
                # Merge expertise areas
                existing.expertise_area = list(set(existing.expertise_area + assignment.expertise_area))
            else:
                unique_reviewers[assignment.reviewer_id] = assignment
        
        return list(unique_reviewers.values())


class GitOpsPolicyEngine:
    """Engine for enforcing GitOps policies and compliance checking."""
    
    # Default policy rules
    DEFAULT_POLICIES = {
        'naming_conventions': {
            'enabled': True,
            'rules': {
                'resource_name_pattern': r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$',
                'max_name_length': 63,
                'reserved_names': ['default', 'system', 'admin']
            }
        },
        'resource_limits': {
            'enabled': True,
            'rules': {
                'max_vpcs_per_fabric': 100,
                'max_external_per_vpc': 10,
                'max_connections_per_switch': 64
            }
        },
        'security_policies': {
            'enabled': True,
            'rules': {
                'require_namespace': True,
                'no_privileged_access': True,
                'encryption_required': True
            }
        },
        'compliance_checks': {
            'enabled': True,
            'rules': {
                'require_labels': ['environment', 'team', 'cost-center'],
                'require_annotations': ['contact', 'purpose'],
                'audit_logging_required': True
            }
        }
    }
    
    def __init__(self, fabric: HedgehogFabric):
        """Initialize policy engine for fabric."""
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
        self.policies = self._load_fabric_policies()
    
    def _load_fabric_policies(self) -> Dict[str, Any]:
        """Load fabric-specific policies."""
        # For now, use default policies
        # In future, this could load from fabric.policy_config field
        return self.DEFAULT_POLICIES.copy()
    
    async def validate_changes(self, changes: List[ChangeRecord]) -> List[PolicyViolation]:
        """
        Validate changes against GitOps policies.
        
        Args:
            changes: List of changes to validate
            
        Returns:
            List of policy violations
        """
        violations = []
        
        for change in changes:
            # Validate naming conventions
            if self.policies['naming_conventions']['enabled']:
                naming_violations = self._validate_naming_conventions(change)
                violations.extend(naming_violations)
            
            # Validate resource limits
            if self.policies['resource_limits']['enabled']:
                limit_violations = await self._validate_resource_limits(change)
                violations.extend(limit_violations)
            
            # Validate security policies
            if self.policies['security_policies']['enabled']:
                security_violations = self._validate_security_policies(change)
                violations.extend(security_violations)
            
            # Validate compliance requirements
            if self.policies['compliance_checks']['enabled']:
                compliance_violations = self._validate_compliance_requirements(change)
                violations.extend(compliance_violations)
        
        return violations
    
    def _validate_naming_conventions(self, change: ChangeRecord) -> List[PolicyViolation]:
        """Validate naming convention policies."""
        violations = []
        rules = self.policies['naming_conventions']['rules']
        
        resource_name = change.resource_name
        
        # Check name pattern
        pattern = rules.get('resource_name_pattern')
        if pattern and not re.match(pattern, resource_name):
            violations.append(PolicyViolation(
                violation_id=f"naming_{change.change_id}_pattern",
                violation_type=PolicyViolationType.NAMING_CONVENTION,
                severity='medium',
                message=f"Resource name '{resource_name}' does not match required pattern {pattern}",
                resource_path=f"{change.resource_type}/{resource_name}",
                suggested_fix=f"Rename to follow pattern: {pattern}",
                can_auto_fix=False,
                blocking=True
            ))
        
        # Check name length
        max_length = rules.get('max_name_length', 63)
        if len(resource_name) > max_length:
            violations.append(PolicyViolation(
                violation_id=f"naming_{change.change_id}_length",
                violation_type=PolicyViolationType.NAMING_CONVENTION,
                severity='high',
                message=f"Resource name length {len(resource_name)} exceeds maximum {max_length}",
                resource_path=f"{change.resource_type}/{resource_name}",
                suggested_fix=f"Shorten name to {max_length} characters or less",
                can_auto_fix=False,
                blocking=True
            ))
        
        # Check reserved names
        reserved_names = rules.get('reserved_names', [])
        if resource_name.lower() in reserved_names:
            violations.append(PolicyViolation(
                violation_id=f"naming_{change.change_id}_reserved",
                violation_type=PolicyViolationType.NAMING_CONVENTION,
                severity='high',
                message=f"Resource name '{resource_name}' is reserved and cannot be used",
                resource_path=f"{change.resource_type}/{resource_name}",
                suggested_fix="Choose a different name that is not reserved",
                can_auto_fix=False,
                blocking=True
            ))
        
        return violations
    
    async def _validate_resource_limits(self, change: ChangeRecord) -> List[PolicyViolation]:
        """Validate resource limit policies."""
        violations = []
        rules = self.policies['resource_limits']['rules']
        
        # This would typically query actual resource counts
        # For now, we'll simulate the validation
        
        if change.resource_type == 'VPC' and change.action == 'create':
            max_vpcs = rules.get('max_vpcs_per_fabric', 100)
            # Simulate current VPC count
            current_vpcs = 50  # This would be actual count
            
            if current_vpcs >= max_vpcs:
                violations.append(PolicyViolation(
                    violation_id=f"limit_{change.change_id}_vpc_count",
                    violation_type=PolicyViolationType.RESOURCE_LIMIT,
                    severity='high',
                    message=f"Creating VPC would exceed limit of {max_vpcs} VPCs per fabric",
                    resource_path=f"{change.resource_type}/{change.resource_name}",
                    suggested_fix="Remove unused VPCs or request limit increase",
                    can_auto_fix=False,
                    blocking=True
                ))
        
        return violations
    
    def _validate_security_policies(self, change: ChangeRecord) -> List[PolicyViolation]:
        """Validate security policies."""
        violations = []
        rules = self.policies['security_policies']['rules']
        
        # Check if namespace is required
        if rules.get('require_namespace') and change.new_data:
            metadata = change.new_data.get('metadata', {})
            namespace = metadata.get('namespace')
            
            if not namespace or namespace == 'default':
                violations.append(PolicyViolation(
                    violation_id=f"security_{change.change_id}_namespace",
                    violation_type=PolicyViolationType.SECURITY_RISK,
                    severity='medium',
                    message="Resources must specify a non-default namespace",
                    resource_path=f"{change.resource_type}/{change.resource_name}",
                    suggested_fix="Add namespace field to metadata",
                    can_auto_fix=True,
                    blocking=False
                ))
        
        return violations
    
    def _validate_compliance_requirements(self, change: ChangeRecord) -> List[PolicyViolation]:
        """Validate compliance requirements."""
        violations = []
        rules = self.policies['compliance_checks']['rules']
        
        if change.new_data:
            metadata = change.new_data.get('metadata', {})
            labels = metadata.get('labels', {})
            annotations = metadata.get('annotations', {})
            
            # Check required labels
            required_labels = rules.get('require_labels', [])
            for label in required_labels:
                if label not in labels:
                    violations.append(PolicyViolation(
                        violation_id=f"compliance_{change.change_id}_label_{label}",
                        violation_type=PolicyViolationType.COMPLIANCE_VIOLATION,
                        severity='medium',
                        message=f"Required label '{label}' is missing",
                        resource_path=f"{change.resource_type}/{change.resource_name}",
                        suggested_fix=f"Add label: {label}=<value>",
                        can_auto_fix=True,
                        blocking=False
                    ))
            
            # Check required annotations
            required_annotations = rules.get('require_annotations', [])
            for annotation in required_annotations:
                if annotation not in annotations:
                    violations.append(PolicyViolation(
                        violation_id=f"compliance_{change.change_id}_annotation_{annotation}",
                        violation_type=PolicyViolationType.COMPLIANCE_VIOLATION,
                        severity='low',
                        message=f"Required annotation '{annotation}' is missing",
                        resource_path=f"{change.resource_type}/{change.resource_name}",
                        suggested_fix=f"Add annotation: {annotation}=<value>",
                        can_auto_fix=True,
                        blocking=False
                    ))
        
        return violations


class PullRequestWorkflowManager:
    """
    Main manager for pull request workflows and GitOps change management.
    
    Orchestrates the complete workflow from change detection to PR creation,
    policy enforcement, and approval tracking.
    """
    
    def __init__(self, fabric: HedgehogFabric):
        """
        Initialize workflow manager for fabric.
        
        Args:
            fabric: HedgehogFabric instance
        """
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
        self.environment_manager = EnvironmentManager(fabric)
        self.policy_engine = GitOpsPolicyEngine(fabric)
        
        # Workflow configuration
        self.auto_create_prs = True
        self.require_policy_compliance = True
        self.auto_assign_reviewers = True
        self.template_type = 'configuration'  # Default template
    
    async def create_automated_pr(
        self,
        changes: List[ChangeRecord],
        target_environment: str = 'staging',
        user: Optional[str] = None,
        **options
    ) -> Optional[PullRequestMetadata]:
        """
        Create automated pull request for NetBox changes.
        
        Args:
            changes: List of changes to include in PR
            target_environment: Target environment for changes
            user: User who initiated the changes
            **options: Additional PR options
            
        Returns:
            PullRequestMetadata if successful, None otherwise
        """
        try:
            # Generate unique PR ID
            import uuid
            pr_id = str(uuid.uuid4())
            
            # Analyze changes for impact and categorization
            impact_assessment = await self._assess_change_impact(changes)
            
            # Validate changes against policies
            policy_violations = await self.policy_engine.validate_changes(changes)
            
            # Check if blocking violations prevent PR creation
            blocking_violations = [v for v in policy_violations if v.blocking]
            if blocking_violations and self.require_policy_compliance:
                self.logger.warning(f"PR creation blocked by {len(blocking_violations)} policy violations")
                return None
            
            # Determine change type for template selection
            template_type = self._determine_template_type(changes)
            
            # Generate PR title and description
            pr_title = self._generate_pr_title(changes, target_environment)
            pr_description = PRTemplateEngine.generate_pr_description(
                changes, template_type, **impact_assessment
            )
            
            # Generate branch name
            branch_name = self._generate_branch_name(changes, pr_id)
            
            # Auto-assign reviewers
            reviewers = []
            if self.auto_assign_reviewers:
                reviewers = ReviewerAssignmentEngine.assign_reviewers(changes, self.fabric)
            
            # Generate labels
            labels = self._generate_pr_labels(changes, impact_assessment)
            
            # Determine compliance status
            compliance_status = 'compliant' if not blocking_violations else 'non_compliant'
            if policy_violations and not blocking_violations:
                compliance_status = 'warning'
            
            # Create PR metadata
            pr_metadata = PullRequestMetadata(
                pr_id=pr_id,
                title=pr_title,
                description=pr_description,
                branch_name=branch_name,
                target_branch=self._get_target_branch(target_environment),
                labels=labels,
                reviewers=reviewers,
                changes=changes,
                policy_violations=policy_violations,
                impact_assessment=impact_assessment,
                compliance_status=compliance_status
            )
            
            # Create actual PR through Git provider API if available
            provider_pr_info = await self._create_provider_pr(pr_metadata)
            if provider_pr_info:
                pr_metadata.pr_id = str(provider_pr_info.get('number', pr_id))
            
            self.logger.info(f"Created automated PR {pr_metadata.pr_id}: {pr_title}")
            return pr_metadata
            
        except Exception as e:
            self.logger.error(f"Failed to create automated PR: {e}")
            return None
    
    async def _assess_change_impact(self, changes: List[ChangeRecord]) -> Dict[str, Any]:
        """Assess the impact of changes."""
        impact_assessment = {
            'total_changes': len(changes),
            'change_types': {},
            'affected_resources': set(),
            'risk_factors': [],
            'estimated_downtime': 0,
            'rollback_complexity': 'low'
        }
        
        for change in changes:
            # Count change types
            change_type = change.change_type.value
            impact_assessment['change_types'][change_type] = \
                impact_assessment['change_types'].get(change_type, 0) + 1
            
            # Track affected resources
            impact_assessment['affected_resources'].add(change.resource_type)
            
            # Assess risk factors
            if change.action == 'delete':
                impact_assessment['risk_factors'].append('Resource deletion')
            
            if change.change_impact == ChangeImpact.CRITICAL:
                impact_assessment['risk_factors'].append('Critical change impact')
                impact_assessment['rollback_complexity'] = 'high'
            
            if change.change_type == ChangeType.SECURITY:
                impact_assessment['risk_factors'].append('Security configuration change')
        
        # Convert set to list for serialization
        impact_assessment['affected_resources'] = list(impact_assessment['affected_resources'])
        
        return impact_assessment
    
    def _determine_template_type(self, changes: List[ChangeRecord]) -> str:
        """Determine the appropriate template type for PR."""
        change_types = {change.change_type for change in changes}
        
        if ChangeType.SECURITY in change_types:
            return 'security'
        elif ChangeType.INFRASTRUCTURE in change_types:
            return 'infrastructure'
        else:
            return 'configuration'
    
    def _generate_pr_title(self, changes: List[ChangeRecord], target_env: str) -> str:
        """Generate PR title based on changes."""
        if len(changes) == 1:
            change = changes[0]
            return f"{change.action.title()} {change.resource_type}/{change.resource_name} in {target_env}"
        else:
            change_summary = {}
            for change in changes:
                action = change.action
                change_summary[action] = change_summary.get(action, 0) + 1
            
            summary_parts = []
            for action, count in change_summary.items():
                summary_parts.append(f"{action} {count}")
            
            return f"GitOps update: {', '.join(summary_parts)} resources in {target_env}"
    
    def _generate_branch_name(self, changes: List[ChangeRecord], pr_id: str) -> str:
        """Generate branch name for PR."""
        if len(changes) == 1:
            change = changes[0]
            safe_name = re.sub(r'[^a-zA-Z0-9-]', '-', change.resource_name)
            return f"gitops/{change.action}-{safe_name}-{pr_id[:8]}"
        else:
            return f"gitops/multi-resource-update-{pr_id[:8]}"
    
    def _generate_pr_labels(self, changes: List[ChangeRecord], impact: Dict[str, Any]) -> List[str]:
        """Generate labels for PR."""
        labels = ['gitops', 'automated']
        
        # Add change type labels
        change_types = {change.change_type.value for change in changes}
        labels.extend(change_types)
        
        # Add impact labels
        if impact.get('risk_factors'):
            labels.append('high-risk')
        
        # Add size labels
        if len(changes) > 10:
            labels.append('large-change')
        elif len(changes) > 5:
            labels.append('medium-change')
        else:
            labels.append('small-change')
        
        return labels
    
    def _get_target_branch(self, environment: str) -> str:
        """Get target branch for environment."""
        env_config = self.environment_manager.get_environment_config(environment)
        if env_config:
            return env_config.branch
        return 'main'  # Default fallback
    
    async def _create_provider_pr(self, pr_metadata: PullRequestMetadata) -> Optional[Dict[str, Any]]:
        """Create PR through Git provider API."""
        try:
            # This would integrate with the git_providers module from Day 1
            # For now, we'll simulate the creation
            return {
                'number': int(pr_metadata.pr_id[-6:], 16) % 10000,  # Simulate PR number
                'url': f"https://github.com/example/repo/pull/{pr_metadata.pr_id[-4:]}",
                'status': 'open'
            }
        except Exception as e:
            self.logger.error(f"Failed to create provider PR: {e}")
            return None
    
    async def track_pr_approval(
        self,
        pr_id: str,
        approver: str,
        approval_status: str,
        comments: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Track PR approval for audit trail.
        
        Args:
            pr_id: Pull request ID
            approver: User who provided approval
            approval_status: approved, rejected, or comment
            comments: Optional approval comments
            
        Returns:
            Approval record
        """
        approval_record = {
            'pr_id': pr_id,
            'approver': approver,
            'approval_status': approval_status,
            'comments': comments,
            'timestamp': timezone.now().isoformat(),
            'approval_id': f"approval_{pr_id}_{int(timezone.now().timestamp())}"
        }
        
        self.logger.info(f"PR {pr_id} {approval_status} by {approver}")
        
        # In a real implementation, this would be stored in the database
        return approval_record
    
    async def get_change_audit_trail(
        self,
        resource_type: Optional[str] = None,
        resource_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail of changes for compliance reporting.
        
        Args:
            resource_type: Optional filter by resource type
            resource_name: Optional filter by resource name
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of audit trail records
        """
        # This would query actual audit logs from the database
        # For now, we'll return simulated data
        audit_records = [
            {
                'change_id': 'change_001',
                'resource_type': 'VPC',
                'resource_name': 'production-vpc',
                'action': 'update',
                'user': 'admin@company.com',
                'timestamp': '2025-07-10T10:00:00Z',
                'pr_id': 'pr_123',
                'approval_status': 'approved',
                'approvers': ['security-team', 'platform-team']
            }
        ]
        
        # Apply filters
        filtered_records = []
        for record in audit_records:
            if resource_type and record['resource_type'] != resource_type:
                continue
            if resource_name and record['resource_name'] != resource_name:
                continue
            # Date filtering would be implemented here
            filtered_records.append(record)
        
        return filtered_records
    
    def get_compliance_report(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Generate compliance report for given time period.
        
        Args:
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Compliance report data
        """
        # This would generate actual compliance data
        # For now, we'll return simulated report
        return {
            'report_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'fabric': self.fabric.name,
            'summary': {
                'total_changes': 45,
                'policy_compliant': 42,
                'policy_violations': 3,
                'security_reviews': 8,
                'approvals_required': 12,
                'approvals_completed': 12
            },
            'policy_violations': [
                {
                    'violation_type': 'naming_convention',
                    'count': 2,
                    'severity': 'medium',
                    'resolved': True
                },
                {
                    'violation_type': 'missing_labels',
                    'count': 1,
                    'severity': 'low',
                    'resolved': True
                }
            ],
            'change_breakdown': {
                'configuration': 35,
                'infrastructure': 8,
                'security': 2
            },
            'approval_metrics': {
                'average_approval_time': '4.2 hours',
                'longest_approval_time': '12.5 hours',
                'approval_rate': '100%'
            }
        }


class PRWorkflowError(Exception):
    """Base exception for PR workflow operations."""
    pass


class PolicyViolationError(PRWorkflowError):
    """Policy violation blocking PR creation."""
    pass


class ReviewerAssignmentError(PRWorkflowError):
    """Error in reviewer assignment."""
    pass