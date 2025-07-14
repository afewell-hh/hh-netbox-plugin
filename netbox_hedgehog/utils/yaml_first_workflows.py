"""
YAML-First Resource Creation Workflows
====================================

This module provides workflows for creating and managing Hedgehog resources
using YAML-first approach, where users define resources in YAML format
before they are committed to Git or deployed to Kubernetes.
"""

import logging
import yaml
import json
import tempfile
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from ..models import HedgehogFabric, HedgehogResource
from ..models.gitops import ResourceStateChoices
from ..models.reconciliation import ReconciliationAlert, AlertSeverityChoices
from .repository_validator import RepositoryValidator, ResourceInfo, ValidationIssue

logger = logging.getLogger(__name__)


class ResourceAction(Enum):
    """Actions that can be performed on resources"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VALIDATE = "validate"


@dataclass
class ResourceDraft:
    """Represents a draft resource before it's committed"""
    name: str
    kind: str
    namespace: str
    api_version: str
    spec: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    file_path: Optional[str] = None
    yaml_content: Optional[str] = None
    validation_issues: List[ValidationIssue] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class ResourceTemplate:
    """Template for creating resources"""
    name: str
    kind: str
    description: str
    template_yaml: str
    variables: Dict[str, Any] = field(default_factory=dict)
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    author: Optional[str] = None
    version: str = "1.0.0"


@dataclass
class WorkflowResult:
    """Result of a YAML-first workflow operation"""
    success: bool
    action: ResourceAction
    resources_processed: List[str] = field(default_factory=list)
    resources_created: List[HedgehogResource] = field(default_factory=list)
    resources_updated: List[HedgehogResource] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    yaml_content: Optional[str] = None
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class YAMLResourceParser:
    """
    Parses YAML content and creates ResourceDraft objects.
    """
    
    def __init__(self, fabric: HedgehogFabric):
        self.fabric = fabric
        self.logger = logging.getLogger(__name__)
    
    def parse_yaml_content(self, yaml_content: str, file_path: Optional[str] = None) -> List[ResourceDraft]:
        """Parse YAML content and create ResourceDraft objects"""
        drafts = []
        
        try:
            # Parse YAML documents
            documents = list(yaml.safe_load_all(yaml_content))
            
            for doc in documents:
                if not doc or not isinstance(doc, dict):
                    continue
                
                # Check if it's a Kubernetes resource
                if 'kind' not in doc or 'apiVersion' not in doc:
                    continue
                
                # Create ResourceDraft
                draft = self._create_resource_draft(doc, file_path, yaml_content)
                if draft:
                    drafts.append(draft)
            
            self.logger.debug(f"Parsed {len(drafts)} resource drafts from YAML")
            
        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error: {e}")
            raise ValidationError(f"Invalid YAML format: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error parsing YAML: {e}")
            raise
        
        return drafts
    
    def _create_resource_draft(self, doc: Dict[str, Any], file_path: Optional[str], 
                              yaml_content: str) -> Optional[ResourceDraft]:
        """Create a ResourceDraft from a YAML document"""
        try:
            kind = doc.get('kind', '')
            api_version = doc.get('apiVersion', '')
            metadata = doc.get('metadata', {})
            
            # Check if it's a Hedgehog resource
            if not self._is_hedgehog_resource(kind, api_version):
                return None
            
            name = metadata.get('name', '')
            namespace = metadata.get('namespace', 'default')
            
            draft = ResourceDraft(
                name=name,
                kind=kind,
                namespace=namespace,
                api_version=api_version,
                spec=doc.get('spec', {}),
                metadata=metadata,
                labels=metadata.get('labels', {}),
                annotations=metadata.get('annotations', {}),
                file_path=file_path,
                yaml_content=yaml_content,
                created_at=timezone.now()
            )
            
            # Validate the draft
            draft.validation_issues = self._validate_draft(draft)
            
            # Analyze dependencies
            draft.dependencies = self._analyze_dependencies(draft)
            
            return draft
            
        except Exception as e:
            self.logger.error(f"Failed to create resource draft: {e}")
            return None
    
    def _is_hedgehog_resource(self, kind: str, api_version: str) -> bool:
        """Check if a resource is a Hedgehog resource"""
        hedgehog_api_groups = [
            'vpc.githedgehog.com',
            'wiring.githedgehog.com',
            'fabric.githedgehog.com',
            'agent.githedgehog.com'
        ]
        
        return any(group in api_version for group in hedgehog_api_groups)
    
    def _validate_draft(self, draft: ResourceDraft) -> List[ValidationIssue]:
        """Validate a resource draft"""
        issues = []
        
        # Basic validation
        if not draft.name:
            issues.append(ValidationIssue(
                severity="error",
                category="validation",
                message="Resource name is required",
                resource_name=draft.name,
                resource_kind=draft.kind
            ))
        
        if not self._is_valid_k8s_name(draft.name):
            issues.append(ValidationIssue(
                severity="error",
                category="validation",
                message=f"Invalid resource name '{draft.name}' - must be DNS-1123 compliant",
                resource_name=draft.name,
                resource_kind=draft.kind
            ))
        
        if not self._is_valid_k8s_name(draft.namespace):
            issues.append(ValidationIssue(
                severity="error",
                category="validation",
                message=f"Invalid namespace '{draft.namespace}'",
                resource_name=draft.name,
                resource_kind=draft.kind
            ))
        
        # Kind-specific validation
        if draft.kind == 'VPC':
            issues.extend(self._validate_vpc_draft(draft))
        elif draft.kind == 'Connection':
            issues.extend(self._validate_connection_draft(draft))
        
        return issues
    
    def _validate_vpc_draft(self, draft: ResourceDraft) -> List[ValidationIssue]:
        """Validate VPC-specific fields"""
        issues = []
        spec = draft.spec
        
        if 'ipv4Namespace' not in spec:
            issues.append(ValidationIssue(
                severity="error",
                category="validation",
                message="VPC must specify ipv4Namespace",
                resource_name=draft.name,
                resource_kind=draft.kind
            ))
        
        if 'subnet' not in spec:
            issues.append(ValidationIssue(
                severity="warning",
                category="validation",
                message="VPC should specify subnet",
                resource_name=draft.name,
                resource_kind=draft.kind
            ))
        
        return issues
    
    def _validate_connection_draft(self, draft: ResourceDraft) -> List[ValidationIssue]:
        """Validate Connection-specific fields"""
        issues = []
        spec = draft.spec
        
        if 'endpoints' not in spec:
            issues.append(ValidationIssue(
                severity="error",
                category="validation",
                message="Connection must specify endpoints",
                resource_name=draft.name,
                resource_kind=draft.kind
            ))
        else:
            endpoints = spec['endpoints']
            if not isinstance(endpoints, list) or len(endpoints) != 2:
                issues.append(ValidationIssue(
                    severity="error",
                    category="validation",
                    message="Connection must have exactly 2 endpoints",
                    resource_name=draft.name,
                    resource_kind=draft.kind
                ))
        
        return issues
    
    def _analyze_dependencies(self, draft: ResourceDraft) -> List[str]:
        """Analyze resource dependencies"""
        dependencies = []
        spec = draft.spec
        
        # Common dependency patterns
        if 'vpc' in spec:
            dependencies.append(f"VPC/{spec['vpc']}")
        
        if 'ipv4Namespace' in spec:
            dependencies.append(f"IPv4Namespace/{spec['ipv4Namespace']}")
        
        if 'vlanNamespace' in spec:
            dependencies.append(f"VLANNamespace/{spec['vlanNamespace']}")
        
        if 'endpoints' in spec and isinstance(spec['endpoints'], list):
            for endpoint in spec['endpoints']:
                if isinstance(endpoint, dict) and 'name' in endpoint:
                    dependencies.append(f"Server/{endpoint['name']}")
        
        return dependencies
    
    def _is_valid_k8s_name(self, name: str) -> bool:
        """Validate Kubernetes resource name"""
        import re
        if not name:
            return False
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        return bool(re.match(pattern, name)) and len(name) <= 253


class ResourceTemplateManager:
    """
    Manages resource templates for common Hedgehog resources.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.templates = self._load_builtin_templates()
    
    def _load_builtin_templates(self) -> Dict[str, ResourceTemplate]:
        """Load built-in resource templates"""
        templates = {}
        
        # VPC template
        vpc_template = ResourceTemplate(
            name="basic-vpc",
            kind="VPC",
            description="Basic VPC template",
            template_yaml="""
apiVersion: vpc.githedgehog.com/v1beta1
kind: VPC
metadata:
  name: "{{ name }}"
  namespace: "{{ namespace | default('default') }}"
  labels:
    app: hedgehog
    component: vpc
spec:
  ipv4Namespace: "{{ ipv4_namespace | default('default') }}"
  subnet: "{{ subnet | default('10.0.0.0/16') }}"
  vlanNamespace: "{{ vlan_namespace | default('default') }}"
""",
            variables={
                "name": {"type": "string", "required": True, "description": "VPC name"},
                "namespace": {"type": "string", "default": "default", "description": "Kubernetes namespace"},
                "ipv4_namespace": {"type": "string", "default": "default", "description": "IPv4 namespace"},
                "subnet": {"type": "string", "default": "10.0.0.0/16", "description": "VPC subnet"},
                "vlan_namespace": {"type": "string", "default": "default", "description": "VLAN namespace"}
            },
            category="networking",
            tags=["vpc", "networking"]
        )
        templates["basic-vpc"] = vpc_template
        
        # Connection template
        connection_template = ResourceTemplate(
            name="basic-connection",
            kind="Connection",
            description="Basic connection template",
            template_yaml="""
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: "{{ name }}"
  namespace: "{{ namespace | default('default') }}"
  labels:
    app: hedgehog
    component: connection
spec:
  endpoints:
    - name: "{{ endpoint1_name }}"
      port: "{{ endpoint1_port | default('eth0') }}"
    - name: "{{ endpoint2_name }}"
      port: "{{ endpoint2_port | default('Ethernet1') }}"
  type: "{{ connection_type | default('unbundled') }}"
""",
            variables={
                "name": {"type": "string", "required": True, "description": "Connection name"},
                "namespace": {"type": "string", "default": "default", "description": "Kubernetes namespace"},
                "endpoint1_name": {"type": "string", "required": True, "description": "First endpoint name"},
                "endpoint1_port": {"type": "string", "default": "eth0", "description": "First endpoint port"},
                "endpoint2_name": {"type": "string", "required": True, "description": "Second endpoint name"},
                "endpoint2_port": {"type": "string", "default": "Ethernet1", "description": "Second endpoint port"},
                "connection_type": {"type": "string", "default": "unbundled", "description": "Connection type"}
            },
            category="wiring",
            tags=["connection", "wiring"]
        )
        templates["basic-connection"] = connection_template
        
        return templates
    
    def get_template(self, template_name: str) -> Optional[ResourceTemplate]:
        """Get a template by name"""
        return self.templates.get(template_name)
    
    def list_templates(self, category: Optional[str] = None, kind: Optional[str] = None) -> List[ResourceTemplate]:
        """List available templates"""
        templates = list(self.templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        if kind:
            templates = [t for t in templates if t.kind == kind]
        
        return templates
    
    def render_template(self, template_name: str, variables: Dict[str, Any]) -> str:
        """Render a template with variables"""
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")
        
        try:
            from jinja2 import Template
            jinja_template = Template(template.template_yaml)
            return jinja_template.render(**variables)
        except Exception as e:
            self.logger.error(f"Template rendering failed: {e}")
            raise
    
    def validate_template_variables(self, template_name: str, variables: Dict[str, Any]) -> List[str]:
        """Validate template variables"""
        template = self.get_template(template_name)
        if not template:
            return [f"Template '{template_name}' not found"]
        
        errors = []
        
        # Check required variables
        for var_name, var_config in template.variables.items():
            if var_config.get('required', False) and var_name not in variables:
                errors.append(f"Required variable '{var_name}' is missing")
        
        # Check variable types
        for var_name, value in variables.items():
            if var_name in template.variables:
                expected_type = template.variables[var_name].get('type', 'string')
                if expected_type == 'string' and not isinstance(value, str):
                    errors.append(f"Variable '{var_name}' must be a string")
                elif expected_type == 'number' and not isinstance(value, (int, float)):
                    errors.append(f"Variable '{var_name}' must be a number")
                elif expected_type == 'boolean' and not isinstance(value, bool):
                    errors.append(f"Variable '{var_name}' must be a boolean")
        
        return errors


class YAMLFirstWorkflowManager:
    """
    Manages YAML-first workflows for resource creation and management.
    """
    
    def __init__(self, fabric: HedgehogFabric):
        self.fabric = fabric
        self.logger = logging.getLogger(__name__)
        self.parser = YAMLResourceParser(fabric)
        self.template_manager = ResourceTemplateManager()
    
    def create_from_yaml(self, yaml_content: str, file_path: Optional[str] = None,
                        created_by: Optional[str] = None) -> WorkflowResult:
        """Create resources from YAML content"""
        start_time = timezone.now()
        
        result = WorkflowResult(
            success=False,
            action=ResourceAction.CREATE,
            yaml_content=yaml_content
        )
        
        try:
            # Parse YAML content
            drafts = self.parser.parse_yaml_content(yaml_content, file_path)
            
            # Validate all drafts
            validation_errors = []
            for draft in drafts:
                for issue in draft.validation_issues:
                    if issue.severity == "error":
                        validation_errors.append(f"{draft.name}: {issue.message}")
            
            if validation_errors:
                result.validation_errors = validation_errors
                return result
            
            # Create resources
            created_resources = []
            with transaction.atomic():
                for draft in drafts:
                    resource = self._create_resource_from_draft(draft, created_by)
                    created_resources.append(resource)
            
            result.resources_created = created_resources
            result.resources_processed = [r.name for r in created_resources]
            result.success = True
            
            # Calculate processing time
            end_time = timezone.now()
            result.processing_time = (end_time - start_time).total_seconds()
            
            result.metadata = {
                'resources_created': len(created_resources),
                'fabric': self.fabric.name,
                'processing_time': result.processing_time
            }
            
            self.logger.info(f"Created {len(created_resources)} resources from YAML")
            
        except Exception as e:
            result.validation_errors.append(f"Failed to create resources: {str(e)}")
            self.logger.error(f"Resource creation failed: {e}")
        
        return result
    
    def create_from_template(self, template_name: str, variables: Dict[str, Any],
                           created_by: Optional[str] = None) -> WorkflowResult:
        """Create resources from template"""
        result = WorkflowResult(
            success=False,
            action=ResourceAction.CREATE
        )
        
        try:
            # Validate template variables
            validation_errors = self.template_manager.validate_template_variables(template_name, variables)
            if validation_errors:
                result.validation_errors = validation_errors
                return result
            
            # Render template
            yaml_content = self.template_manager.render_template(template_name, variables)
            
            # Create resources from rendered YAML
            create_result = self.create_from_yaml(yaml_content, created_by=created_by)
            
            # Copy results
            result.success = create_result.success
            result.resources_created = create_result.resources_created
            result.resources_processed = create_result.resources_processed
            result.validation_errors = create_result.validation_errors
            result.warnings = create_result.warnings
            result.yaml_content = yaml_content
            result.processing_time = create_result.processing_time
            
            result.metadata = create_result.metadata.copy()
            result.metadata['template_name'] = template_name
            result.metadata['template_variables'] = variables
            
            self.logger.info(f"Created resources from template '{template_name}'")
            
        except Exception as e:
            result.validation_errors.append(f"Template creation failed: {str(e)}")
            self.logger.error(f"Template creation failed: {e}")
        
        return result
    
    def validate_yaml(self, yaml_content: str, file_path: Optional[str] = None) -> WorkflowResult:
        """Validate YAML content without creating resources"""
        result = WorkflowResult(
            success=False,
            action=ResourceAction.VALIDATE,
            yaml_content=yaml_content
        )
        
        try:
            # Parse YAML content
            drafts = self.parser.parse_yaml_content(yaml_content, file_path)
            
            # Collect validation issues
            validation_errors = []
            warnings = []
            
            for draft in drafts:
                for issue in draft.validation_issues:
                    if issue.severity == "error":
                        validation_errors.append(f"{draft.name}: {issue.message}")
                    elif issue.severity == "warning":
                        warnings.append(f"{draft.name}: {issue.message}")
            
            result.validation_errors = validation_errors
            result.warnings = warnings
            result.resources_processed = [draft.name for draft in drafts]
            result.success = len(validation_errors) == 0
            
            result.metadata = {
                'resources_validated': len(drafts),
                'validation_errors': len(validation_errors),
                'warnings': len(warnings),
                'fabric': self.fabric.name
            }
            
            self.logger.info(f"Validated {len(drafts)} resources from YAML")
            
        except Exception as e:
            result.validation_errors.append(f"Validation failed: {str(e)}")
            self.logger.error(f"YAML validation failed: {e}")
        
        return result
    
    def _create_resource_from_draft(self, draft: ResourceDraft, created_by: Optional[str] = None) -> HedgehogResource:
        """Create a HedgehogResource from a ResourceDraft"""
        # Check if resource already exists
        existing = HedgehogResource.objects.filter(
            fabric=self.fabric,
            namespace=draft.namespace,
            name=draft.name,
            kind=draft.kind
        ).first()
        
        if existing:
            # Update existing resource
            existing.desired_spec = draft.spec
            existing.desired_updated = timezone.now()
            existing.resource_state = ResourceStateChoices.DRAFT
            existing.labels = draft.labels
            existing.annotations = draft.annotations
            existing.save()
            
            return existing
        else:
            # Create new resource
            resource = HedgehogResource.objects.create(
                fabric=self.fabric,
                name=draft.name,
                namespace=draft.namespace,
                kind=draft.kind,
                api_version=draft.api_version,
                desired_spec=draft.spec,
                desired_updated=timezone.now(),
                resource_state=ResourceStateChoices.DRAFT,
                labels=draft.labels,
                annotations=draft.annotations,
                created_by=created_by,
                last_modified_by=created_by
            )
            
            return resource
    
    def get_resource_yaml(self, resource: HedgehogResource) -> str:
        """Generate YAML for a resource"""
        return resource.generate_yaml_content()
    
    def export_fabric_yaml(self, include_drafts: bool = True) -> str:
        """Export all fabric resources as YAML"""
        resources = HedgehogResource.objects.filter(fabric=self.fabric)
        
        if not include_drafts:
            resources = resources.exclude(resource_state=ResourceStateChoices.DRAFT)
        
        yaml_documents = []
        
        for resource in resources:
            yaml_content = self.get_resource_yaml(resource)
            if yaml_content:
                yaml_documents.append(yaml_content)
        
        return "---\n".join(yaml_documents)
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get summary of YAML-first workflow usage"""
        resources = HedgehogResource.objects.filter(fabric=self.fabric)
        
        summary = {
            'total_resources': resources.count(),
            'by_state': {},
            'by_kind': {},
            'recent_activity': []
        }
        
        # Group by state
        for state in ResourceStateChoices.CHOICES:
            summary['by_state'][state[0]] = resources.filter(resource_state=state[0]).count()
        
        # Group by kind
        for resource in resources:
            kind = resource.kind
            summary['by_kind'][kind] = summary['by_kind'].get(kind, 0) + 1
        
        # Get recent activity
        recent = resources.order_by('-last_updated')[:10]
        summary['recent_activity'] = [
            {
                'resource': f"{r.kind}/{r.name}",
                'state': r.resource_state,
                'updated': r.last_updated.isoformat() if r.last_updated else None
            } for r in recent
        ]
        
        return summary