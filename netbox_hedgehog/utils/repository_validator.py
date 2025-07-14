"""
Repository Validation and GitOps Directory Discovery
===================================================

This module provides comprehensive repository validation and automatic discovery
of GitOps directory structures for Hedgehog network fabrics.
"""

import logging
import os
import re
import yaml
import tempfile
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ResourceType(Enum):
    """Supported Hedgehog resource types"""
    VPC = "VPC"
    EXTERNAL = "External"
    EXTERNAL_ATTACHMENT = "ExternalAttachment"
    EXTERNAL_PEERING = "ExternalPeering"
    IPV4_NAMESPACE = "IPv4Namespace"
    VPC_ATTACHMENT = "VPCAttachment"
    VPC_PEERING = "VPCPeering"
    CONNECTION = "Connection"
    SERVER = "Server"
    SWITCH = "Switch"
    SWITCH_GROUP = "SwitchGroup"
    VLAN_NAMESPACE = "VLANNamespace"


@dataclass
class ValidationIssue:
    """Represents a validation issue found in the repository"""
    severity: ValidationSeverity
    category: str
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    resource_name: Optional[str] = None
    resource_kind: Optional[str] = None
    fix_suggestion: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceInfo:
    """Information about a discovered resource"""
    name: str
    kind: str
    namespace: str
    api_version: str
    file_path: str
    line_number: int
    spec: Dict[str, Any]
    metadata: Dict[str, Any]
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    validation_issues: List[ValidationIssue] = field(default_factory=list)


@dataclass
class DirectoryInfo:
    """Information about a discovered directory"""
    path: str
    name: str
    file_count: int
    yaml_file_count: int
    resource_count: int
    subdirectories: List[str] = field(default_factory=list)
    detected_pattern: Optional[str] = None
    purpose: Optional[str] = None


@dataclass
class RepositoryStructure:
    """Complete repository structure information"""
    root_path: str
    total_files: int
    total_yaml_files: int
    total_resources: int
    directories: List[DirectoryInfo] = field(default_factory=list)
    resources: List[ResourceInfo] = field(default_factory=list)
    gitops_directories: List[str] = field(default_factory=list)
    recommended_structure: Dict[str, Any] = field(default_factory=dict)
    validation_issues: List[ValidationIssue] = field(default_factory=list)


class GitOpsDirectoryDiscovery:
    """
    Discovers and analyzes GitOps directory structures in repositories.
    """
    
    def __init__(self, repository_path: str):
        self.repository_path = repository_path
        self.logger = logging.getLogger(__name__)
        
        # Common GitOps directory patterns
        self.gitops_patterns = {
            'hedgehog': r'^hedgehog(/.*)?$',
            'k8s': r'^k8s(/.*)?$',
            'kubernetes': r'^kubernetes(/.*)?$',
            'manifests': r'^manifests(/.*)?$',
            'config': r'^config(/.*)?$',
            'deploy': r'^deploy(/.*)?$',
            'gitops': r'^gitops(/.*)?$',
            'clusters': r'^clusters(/.*)?$',
            'environments': r'^environments(/.*)?$'
        }
        
        # Resource organization patterns
        self.resource_patterns = {
            'by_kind': r'^.*/?(vpc|wiring|fabric|network)/?$',
            'by_namespace': r'^.*/?(default|kube-system|hedgehog-system)/?$',
            'by_environment': r'^.*/?(dev|staging|prod|production)/?$',
            'by_cluster': r'^.*/?(cluster-[a-z0-9-]+)/?$'
        }
    
    def discover_structure(self) -> RepositoryStructure:
        """Discover the complete repository structure"""
        structure = RepositoryStructure(
            root_path=self.repository_path,
            total_files=0,
            total_yaml_files=0,
            total_resources=0
        )
        
        try:
            # Analyze directory structure
            structure.directories = self._analyze_directories()
            
            # Discover GitOps directories
            structure.gitops_directories = self._discover_gitops_directories()
            
            # Analyze resources
            structure.resources = self._discover_resources()
            
            # Calculate totals
            structure.total_files = sum(d.file_count for d in structure.directories)
            structure.total_yaml_files = sum(d.yaml_file_count for d in structure.directories)
            structure.total_resources = len(structure.resources)
            
            # Generate recommended structure
            structure.recommended_structure = self._generate_recommended_structure(structure)
            
            # Validate structure
            structure.validation_issues = self._validate_structure(structure)
            
            self.logger.info(f"Discovered repository structure with {structure.total_resources} resources")
            
        except Exception as e:
            issue = ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="discovery",
                message=f"Failed to discover repository structure: {str(e)}"
            )
            structure.validation_issues.append(issue)
            self.logger.error(f"Structure discovery failed: {e}")
        
        return structure
    
    def _analyze_directories(self) -> List[DirectoryInfo]:
        """Analyze directory structure"""
        directories = []
        
        for root, dirs, files in os.walk(self.repository_path):
            # Skip .git directory
            if '.git' in root:
                continue
            
            rel_path = os.path.relpath(root, self.repository_path)
            if rel_path == '.':
                rel_path = ''
            
            yaml_files = [f for f in files if f.endswith(('.yaml', '.yml'))]
            
            # Count resources in YAML files
            resource_count = 0
            for yaml_file in yaml_files:
                file_path = os.path.join(root, yaml_file)
                try:
                    with open(file_path, 'r') as f:
                        docs = yaml.safe_load_all(f)
                        for doc in docs:
                            if doc and isinstance(doc, dict) and 'kind' in doc:
                                resource_count += 1
                except Exception:
                    pass
            
            directory_info = DirectoryInfo(
                path=rel_path,
                name=os.path.basename(root) if rel_path else 'root',
                file_count=len(files),
                yaml_file_count=len(yaml_files),
                resource_count=resource_count,
                subdirectories=[d for d in dirs if not d.startswith('.')]
            )
            
            # Detect directory pattern
            directory_info.detected_pattern = self._detect_directory_pattern(rel_path)
            directory_info.purpose = self._infer_directory_purpose(directory_info)
            
            directories.append(directory_info)
        
        return directories
    
    def _discover_gitops_directories(self) -> List[str]:
        """Discover GitOps directories using pattern matching"""
        gitops_dirs = []
        
        for root, dirs, files in os.walk(self.repository_path):
            rel_path = os.path.relpath(root, self.repository_path)
            if rel_path == '.':
                rel_path = ''
            
            # Check if directory matches GitOps patterns
            for pattern_name, pattern in self.gitops_patterns.items():
                if re.match(pattern, rel_path, re.IGNORECASE):
                    gitops_dirs.append(rel_path)
                    break
        
        return gitops_dirs
    
    def _discover_resources(self) -> List[ResourceInfo]:
        """Discover all Hedgehog resources in the repository"""
        resources = []
        
        for root, dirs, files in os.walk(self.repository_path):
            # Skip .git directory
            if '.git' in root:
                continue
            
            yaml_files = [f for f in files if f.endswith(('.yaml', '.yml'))]
            
            for yaml_file in yaml_files:
                file_path = os.path.join(root, yaml_file)
                rel_file_path = os.path.relpath(file_path, self.repository_path)
                
                try:
                    file_resources = self._parse_yaml_file(file_path, rel_file_path)
                    resources.extend(file_resources)
                except Exception as e:
                    issue = ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category="parsing",
                        message=f"Failed to parse YAML file: {str(e)}",
                        file_path=rel_file_path
                    )
                    # Add to global validation issues
                    self.logger.error(f"Failed to parse {rel_file_path}: {e}")
        
        return resources
    
    def _parse_yaml_file(self, file_path: str, rel_file_path: str) -> List[ResourceInfo]:
        """Parse a YAML file and extract resource information"""
        resources = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                docs = yaml.safe_load_all(content)
                
                line_number = 1
                for doc in docs:
                    if doc and isinstance(doc, dict) and 'kind' in doc:
                        # Check if it's a Hedgehog resource
                        kind = doc.get('kind', '')
                        api_version = doc.get('apiVersion', '')
                        
                        if self._is_hedgehog_resource(kind, api_version):
                            metadata = doc.get('metadata', {})
                            name = metadata.get('name', '')
                            namespace = metadata.get('namespace', 'default')
                            
                            resource_info = ResourceInfo(
                                name=name,
                                kind=kind,
                                namespace=namespace,
                                api_version=api_version,
                                file_path=rel_file_path,
                                line_number=line_number,
                                spec=doc.get('spec', {}),
                                metadata=metadata,
                                labels=metadata.get('labels', {}),
                                annotations=metadata.get('annotations', {})
                            )
                            
                            # Analyze dependencies
                            resource_info.dependencies = self._analyze_resource_dependencies(resource_info)
                            
                            # Validate resource
                            resource_info.validation_issues = self._validate_resource(resource_info)
                            
                            resources.append(resource_info)
                    
                    # Estimate line number (rough approximation)
                    line_number += content[:content.find(yaml.dump(doc))].count('\n') + 1
        
        except Exception as e:
            self.logger.error(f"Failed to parse YAML file {rel_file_path}: {e}")
        
        return resources
    
    def _is_hedgehog_resource(self, kind: str, api_version: str) -> bool:
        """Check if a resource is a Hedgehog resource"""
        hedgehog_api_groups = [
            'vpc.githedgehog.com',
            'wiring.githedgehog.com',
            'fabric.githedgehog.com',
            'agent.githedgehog.com'
        ]
        
        # Check if API version contains Hedgehog API groups
        for group in hedgehog_api_groups:
            if group in api_version:
                return True
        
        # Check if kind matches known Hedgehog resources
        hedgehog_kinds = {rt.value for rt in ResourceType}
        return kind in hedgehog_kinds
    
    def _analyze_resource_dependencies(self, resource: ResourceInfo) -> List[str]:
        """Analyze resource dependencies"""
        dependencies = []
        
        # Analyze spec for references to other resources
        spec = resource.spec
        
        # Common dependency patterns
        if 'vpc' in spec:
            dependencies.append(f"VPC/{spec['vpc']}")
        
        if 'ipv4Namespace' in spec:
            dependencies.append(f"IPv4Namespace/{spec['ipv4Namespace']}")
        
        if 'vlanNamespace' in spec:
            dependencies.append(f"VLANNamespace/{spec['vlanNamespace']}")
        
        if 'endpoints' in spec:
            for endpoint in spec['endpoints']:
                if isinstance(endpoint, dict) and 'name' in endpoint:
                    # This could be a server or switch reference
                    dependencies.append(f"Server/{endpoint['name']}")
        
        if 'attachment' in spec:
            attachment = spec['attachment']
            if isinstance(attachment, dict) and 'connection' in attachment:
                dependencies.append(f"Connection/{attachment['connection']}")
        
        return dependencies
    
    def _validate_resource(self, resource: ResourceInfo) -> List[ValidationIssue]:
        """Validate a resource"""
        issues = []
        
        # Validate name
        if not resource.name:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="validation",
                message="Resource name is required",
                file_path=resource.file_path,
                line_number=resource.line_number,
                resource_name=resource.name,
                resource_kind=resource.kind
            ))
        elif not self._is_valid_k8s_name(resource.name):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="validation",
                message=f"Invalid resource name '{resource.name}' - must be DNS-1123 compliant",
                file_path=resource.file_path,
                line_number=resource.line_number,
                resource_name=resource.name,
                resource_kind=resource.kind,
                fix_suggestion="Use lowercase letters, numbers, and hyphens only"
            ))
        
        # Validate namespace
        if not self._is_valid_k8s_name(resource.namespace):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="validation",
                message=f"Invalid namespace '{resource.namespace}'",
                file_path=resource.file_path,
                line_number=resource.line_number,
                resource_name=resource.name,
                resource_kind=resource.kind
            ))
        
        # Validate API version
        if not resource.api_version:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="validation",
                message="API version is required",
                file_path=resource.file_path,
                line_number=resource.line_number,
                resource_name=resource.name,
                resource_kind=resource.kind
            ))
        
        # Resource-specific validation
        if resource.kind == 'VPC':
            issues.extend(self._validate_vpc_resource(resource))
        elif resource.kind == 'Connection':
            issues.extend(self._validate_connection_resource(resource))
        
        return issues
    
    def _validate_vpc_resource(self, resource: ResourceInfo) -> List[ValidationIssue]:
        """Validate VPC resource"""
        issues = []
        spec = resource.spec
        
        # Validate required fields
        if 'ipv4Namespace' not in spec:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="validation",
                message="VPC must specify ipv4Namespace",
                file_path=resource.file_path,
                resource_name=resource.name,
                resource_kind=resource.kind
            ))
        
        if 'subnet' not in spec:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="validation",
                message="VPC should specify subnet",
                file_path=resource.file_path,
                resource_name=resource.name,
                resource_kind=resource.kind
            ))
        
        return issues
    
    def _validate_connection_resource(self, resource: ResourceInfo) -> List[ValidationIssue]:
        """Validate Connection resource"""
        issues = []
        spec = resource.spec
        
        # Validate endpoints
        if 'endpoints' not in spec:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="validation",
                message="Connection must specify endpoints",
                file_path=resource.file_path,
                resource_name=resource.name,
                resource_kind=resource.kind
            ))
        else:
            endpoints = spec['endpoints']
            if not isinstance(endpoints, list) or len(endpoints) != 2:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="validation",
                    message="Connection must have exactly 2 endpoints",
                    file_path=resource.file_path,
                    resource_name=resource.name,
                    resource_kind=resource.kind
                ))
        
        return issues
    
    def _detect_directory_pattern(self, path: str) -> Optional[str]:
        """Detect directory organization pattern"""
        for pattern_name, pattern in self.resource_patterns.items():
            if re.match(pattern, path, re.IGNORECASE):
                return pattern_name
        return None
    
    def _infer_directory_purpose(self, directory: DirectoryInfo) -> Optional[str]:
        """Infer the purpose of a directory"""
        name = directory.name.lower()
        
        if name in ['vpc', 'vpcs']:
            return 'VPC resources'
        elif name in ['wiring', 'connections']:
            return 'Wiring and connection resources'
        elif name in ['fabric', 'fabrics']:
            return 'Fabric configuration'
        elif name in ['servers', 'server']:
            return 'Server definitions'
        elif name in ['switches', 'switch']:
            return 'Switch definitions'
        elif name in ['examples', 'example']:
            return 'Example configurations'
        elif name in ['templates', 'template']:
            return 'Configuration templates'
        elif directory.yaml_file_count > 0:
            return 'Kubernetes resources'
        
        return None
    
    def _validate_structure(self, structure: RepositoryStructure) -> List[ValidationIssue]:
        """Validate the overall repository structure"""
        issues = []
        
        # Check for common issues
        if structure.total_resources == 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="structure",
                message="No Hedgehog resources found in repository",
                fix_suggestion="Add YAML files with Hedgehog resource definitions"
            ))
        
        if not structure.gitops_directories:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                category="structure",
                message="No GitOps directories detected",
                fix_suggestion="Consider organizing resources in 'hedgehog/' directory"
            ))
        
        # Check for deeply nested structures
        max_depth = max(len(d.path.split('/')) for d in structure.directories if d.path)
        if max_depth > 4:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="structure",
                message=f"Directory structure is deeply nested (depth: {max_depth})",
                fix_suggestion="Consider flattening directory structure"
            ))
        
        # Check for resource naming conflicts
        resource_names = {}
        for resource in structure.resources:
            key = f"{resource.namespace}/{resource.kind}/{resource.name}"
            if key in resource_names:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="structure",
                    message=f"Duplicate resource: {key}",
                    file_path=resource.file_path,
                    resource_name=resource.name,
                    resource_kind=resource.kind
                ))
            else:
                resource_names[key] = resource
        
        return issues
    
    def _generate_recommended_structure(self, structure: RepositoryStructure) -> Dict[str, Any]:
        """Generate recommended directory structure"""
        return {
            'recommended_layout': {
                'hedgehog/': {
                    'vpc/': 'VPC and networking resources',
                    'wiring/': 'Connections and wiring resources',
                    'fabric/': 'Fabric-level configuration',
                    'examples/': 'Example configurations'
                },
                'README.md': 'Documentation',
                '.gitignore': 'Git ignore file'
            },
            'organization_principles': [
                'Group resources by type (VPC, wiring, fabric)',
                'Use descriptive file names',
                'Keep directory structure shallow (max 3 levels)',
                'Include documentation and examples'
            ],
            'naming_conventions': {
                'files': 'Use kebab-case for file names',
                'resources': 'Use DNS-1123 compliant names',
                'directories': 'Use lowercase with hyphens'
            },
            'best_practices': [
                'One resource per file when possible',
                'Use consistent metadata labels',
                'Include resource dependencies in comments',
                'Validate YAML syntax regularly'
            ]
        }
    
    def _is_valid_k8s_name(self, name: str) -> bool:
        """Validate Kubernetes resource name"""
        if not name:
            return False
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        return bool(re.match(pattern, name)) and len(name) <= 253


class RepositoryValidator:
    """
    Main validator that orchestrates repository validation and discovery.
    """
    
    def __init__(self, repository_path: str):
        self.repository_path = repository_path
        self.logger = logging.getLogger(__name__)
    
    def validate_repository(self) -> RepositoryStructure:
        """Perform complete repository validation"""
        self.logger.info(f"Starting repository validation for: {self.repository_path}")
        
        # Discover structure
        discovery = GitOpsDirectoryDiscovery(self.repository_path)
        structure = discovery.discover_structure()
        
        # Additional validation
        additional_issues = self._perform_additional_validation(structure)
        structure.validation_issues.extend(additional_issues)
        
        # Generate summary
        self._log_validation_summary(structure)
        
        return structure
    
    def _perform_additional_validation(self, structure: RepositoryStructure) -> List[ValidationIssue]:
        """Perform additional validation checks"""
        issues = []
        
        # Check for security issues
        security_issues = self._check_security_issues(structure)
        issues.extend(security_issues)
        
        # Check for performance issues
        performance_issues = self._check_performance_issues(structure)
        issues.extend(performance_issues)
        
        return issues
    
    def _check_security_issues(self, structure: RepositoryStructure) -> List[ValidationIssue]:
        """Check for security-related issues"""
        issues = []
        
        # Check for sensitive data in resources
        sensitive_patterns = [
            r'password\s*:\s*[^"\s]+',
            r'token\s*:\s*[^"\s]+',
            r'secret\s*:\s*[^"\s]+',
            r'key\s*:\s*[^"\s]+',
        ]
        
        for resource in structure.resources:
            spec_str = str(resource.spec)
            for pattern in sensitive_patterns:
                if re.search(pattern, spec_str, re.IGNORECASE):
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="security",
                        message="Potential sensitive data found in resource spec",
                        file_path=resource.file_path,
                        resource_name=resource.name,
                        resource_kind=resource.kind,
                        fix_suggestion="Use Kubernetes secrets or external secret management"
                    ))
        
        return issues
    
    def _check_performance_issues(self, structure: RepositoryStructure) -> List[ValidationIssue]:
        """Check for performance-related issues"""
        issues = []
        
        # Check for very large files
        large_file_threshold = 100  # KB
        
        for root, dirs, files in os.walk(structure.root_path):
            for file in files:
                if file.endswith(('.yaml', '.yml')):
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path) / 1024  # KB
                    
                    if file_size > large_file_threshold:
                        rel_path = os.path.relpath(file_path, structure.root_path)
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            category="performance",
                            message=f"Large YAML file detected ({file_size:.1f} KB)",
                            file_path=rel_path,
                            fix_suggestion="Consider splitting large files into smaller ones"
                        ))
        
        return issues
    
    def _log_validation_summary(self, structure: RepositoryStructure):
        """Log validation summary"""
        error_count = sum(1 for issue in structure.validation_issues if issue.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for issue in structure.validation_issues if issue.severity == ValidationSeverity.WARNING)
        info_count = sum(1 for issue in structure.validation_issues if issue.severity == ValidationSeverity.INFO)
        
        self.logger.info(f"Validation completed: {structure.total_resources} resources, "
                        f"{error_count} errors, {warning_count} warnings, {info_count} info")
        
        if error_count > 0:
            self.logger.warning(f"Repository has {error_count} validation errors that should be fixed")
        
        if warning_count > 0:
            self.logger.info(f"Repository has {warning_count} warnings that should be reviewed")