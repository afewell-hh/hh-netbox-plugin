"""
GitOps Directory Validation System
Validates directory assignments and prevents conflicts in GitOps workflows
"""

import os
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum

from django.utils import timezone
from django.db.models import Q

from ..models import GitRepository

logger = logging.getLogger('netbox_hedgehog.gitops_directory_validator')


class ValidationLevel(str, Enum):
    """Validation severity levels"""
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class ConflictType(str, Enum):
    """Types of directory conflicts"""
    DUPLICATE_ASSIGNMENT = 'duplicate_assignment'
    OVERLAPPING_PATHS = 'overlapping_paths'
    INVALID_PATH = 'invalid_path'
    MISSING_DIRECTORY = 'missing_directory'
    PERMISSION_DENIED = 'permission_denied'
    CRD_CONFLICTS = 'crd_conflicts'


@dataclass
class ValidationResult:
    """Result of a directory validation check"""
    is_valid: bool
    level: ValidationLevel
    message: str
    details: Dict[str, Any]
    suggestions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConflictReport:
    """Report of directory conflicts"""
    conflicts: List[Dict[str, Any]]
    affected_fabrics: List[str]
    severity: ValidationLevel
    auto_resolvable: bool
    resolution_suggestions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StructureValidation:
    """Result of directory structure validation"""
    directory_exists: bool
    is_accessible: bool
    crd_files: List[str]
    structure_issues: List[str]
    recommended_structure: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CRDValidationResult:
    """Result of CRD validation in directory"""
    valid_crds: List[str]
    invalid_crds: List[str]
    hedgehog_crds: List[str]
    other_crds: List[str]
    syntax_errors: List[Dict[str, str]]
    schema_warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GitOpsDirectoryValidator:
    """Validate GitOps directory assignments and prevent conflicts"""
    
    # Common GitOps directory patterns
    GITOPS_PATTERNS = [
        'gitops/',
        'k8s/',
        'kubernetes/',
        'manifests/',
        'deployments/',
        'apps/',
        'clusters/',
        'environments/'
    ]
    
    # Hedgehog CRD types and their API versions
    HEDGEHOG_CRDS = {
        'VPC': ['vpc.hedgehog.io/v1beta1', 'vpc.hedgehog.io/v1alpha2'],
        'Connection': ['wiring.hedgehog.io/v1beta1', 'wiring.hedgehog.io/v1alpha2'],
        'Server': ['wiring.hedgehog.io/v1beta1', 'wiring.hedgehog.io/v1alpha2'],
        'Switch': ['wiring.hedgehog.io/v1beta1', 'wiring.hedgehog.io/v1alpha2'],
        'SwitchGroup': ['wiring.hedgehog.io/v1beta1', 'wiring.hedgehog.io/v1alpha2'],
        'External': ['vpc.hedgehog.io/v1beta1', 'vpc.hedgehog.io/v1alpha2'],
        'ExternalAttachment': ['vpc.hedgehog.io/v1beta1', 'vpc.hedgehog.io/v1alpha2'],
        'ExternalPeering': ['vpc.hedgehog.io/v1beta1', 'vpc.hedgehog.io/v1alpha2'],
        'VPCAttachment': ['vpc.hedgehog.io/v1beta1', 'vpc.hedgehog.io/v1alpha2'],
        'VPCPeering': ['vpc.hedgehog.io/v1beta1', 'vpc.hedgehog.io/v1alpha2'],
        'IPv4Namespace': ['vpc.hedgehog.io/v1beta1', 'vpc.hedgehog.io/v1alpha2'],
        'VLANNamespace': ['wiring.hedgehog.io/v1beta1', 'wiring.hedgehog.io/v1alpha2']
    }
    
    def __init__(self):
        self.logger = logger
    
    def validate_directory_availability(
        self,
        repository: GitRepository,
        directory: str
    ) -> ValidationResult:
        """
        Validate if a directory is available for use by a fabric.
        
        Args:
            repository: GitRepository instance
            directory: Directory path to validate
            
        Returns:
            ValidationResult with availability status
        """
        try:
            # Normalize directory path
            normalized_dir = self._normalize_directory_path(directory)
            
            # Check if directory path is valid
            path_validation = self._validate_directory_path(normalized_dir)
            if not path_validation.is_valid:
                return path_validation
            
            # Check for conflicts with existing fabric assignments
            conflict_check = self._check_directory_conflicts(
                repository,
                normalized_dir
            )
            
            if conflict_check.conflicts:
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Directory conflicts detected: {len(conflict_check.conflicts)} conflicts",
                    details=conflict_check.to_dict(),
                    suggestions=conflict_check.resolution_suggestions
                )
            
            # Check if directory exists in repository
            directory_exists = self._check_directory_exists(repository, normalized_dir)
            
            suggestions = []
            if not directory_exists:
                suggestions.append(f"Directory '{normalized_dir}' will be created during first deployment")
            else:
                suggestions.append(f"Directory '{normalized_dir}' already exists and can be used")
            
            # Add best practice suggestions
            suggestions.extend(self._get_directory_best_practices(normalized_dir))
            
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message=f"Directory '{normalized_dir}' is available for use",
                details={
                    'normalized_path': normalized_dir,
                    'exists_in_repository': directory_exists,
                    'conflict_check': conflict_check.to_dict()
                },
                suggestions=suggestions
            )
            
        except Exception as e:
            self.logger.error(f"Directory availability validation error: {str(e)}")
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.CRITICAL,
                message=f"Validation failed: {str(e)}",
                details={'error': str(e)},
                suggestions=["Contact administrator to resolve validation issues"]
            )
    
    def detect_directory_conflicts(
        self,
        repository: GitRepository
    ) -> ConflictReport:
        """
        Detect conflicts in directory assignments for a repository.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            ConflictReport with detected conflicts
        """
        conflicts = []
        affected_fabrics = []
        
        try:
            # Get all fabrics using this repository
            from ..models import HedgehogFabric
            fabrics = HedgehogFabric.objects.filter(git_repository=repository)
            
            # Check for duplicate directory assignments
            directory_usage = {}
            for fabric in fabrics:
                dir_path = self._normalize_directory_path(fabric.gitops_directory)
                
                if dir_path not in directory_usage:
                    directory_usage[dir_path] = []
                directory_usage[dir_path].append(fabric)
            
            # Find duplicates
            for dir_path, using_fabrics in directory_usage.items():
                if len(using_fabrics) > 1:
                    conflicts.append({
                        'type': ConflictType.DUPLICATE_ASSIGNMENT,
                        'directory': dir_path,
                        'fabrics': [f.name for f in using_fabrics],
                        'message': f"Directory '{dir_path}' is used by {len(using_fabrics)} fabrics",
                        'severity': ValidationLevel.ERROR
                    })
                    affected_fabrics.extend([f.name for f in using_fabrics])
            
            # Check for overlapping paths
            overlapping_conflicts = self._detect_overlapping_paths(directory_usage.keys())
            conflicts.extend(overlapping_conflicts)
            
            # Check for invalid paths
            for dir_path in directory_usage.keys():
                path_validation = self._validate_directory_path(dir_path)
                if not path_validation.is_valid:
                    conflicts.append({
                        'type': ConflictType.INVALID_PATH,
                        'directory': dir_path,
                        'message': path_validation.message,
                        'severity': ValidationLevel.ERROR
                    })
            
            # Determine overall severity
            severity_levels = [ValidationLevel.INFO]
            if conflicts:
                conflict_severities = [
                    ValidationLevel(c.get('severity', ValidationLevel.WARNING))
                    for c in conflicts
                ]
                if ValidationLevel.CRITICAL in conflict_severities:
                    severity = ValidationLevel.CRITICAL
                elif ValidationLevel.ERROR in conflict_severities:
                    severity = ValidationLevel.ERROR
                else:
                    severity = ValidationLevel.WARNING
            else:
                severity = ValidationLevel.INFO
            
            # Generate resolution suggestions
            resolution_suggestions = self._generate_conflict_resolutions(conflicts)
            
            return ConflictReport(
                conflicts=conflicts,
                affected_fabrics=list(set(affected_fabrics)),
                severity=severity,
                auto_resolvable=self._check_auto_resolvable(conflicts),
                resolution_suggestions=resolution_suggestions
            )
            
        except Exception as e:
            self.logger.error(f"Conflict detection error: {str(e)}")
            return ConflictReport(
                conflicts=[{
                    'type': 'validation_error',
                    'message': f"Conflict detection failed: {str(e)}",
                    'severity': ValidationLevel.CRITICAL
                }],
                affected_fabrics=[],
                severity=ValidationLevel.CRITICAL,
                auto_resolvable=False,
                resolution_suggestions=["Contact administrator to resolve validation issues"]
            )
    
    def validate_directory_structure(
        self,
        repository: GitRepository,
        directory: str
    ) -> StructureValidation:
        """
        Validate the structure of a directory in the repository.
        
        Args:
            repository: GitRepository instance
            directory: Directory path to validate
            
        Returns:
            StructureValidation with structure details
        """
        normalized_dir = self._normalize_directory_path(directory)
        crd_files = []
        structure_issues = []
        directory_exists = False
        is_accessible = False
        
        try:
            # Clone repository to examine structure
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = repository.clone_repository(temp_dir)
                
                if not clone_result.get('success'):
                    structure_issues.append(f"Failed to access repository: {clone_result.get('error')}")
                    return StructureValidation(
                        directory_exists=False,
                        is_accessible=False,
                        crd_files=[],
                        structure_issues=structure_issues,
                        recommended_structure=self._get_recommended_structure()
                    )
                
                repo_path = clone_result['repository_path']
                target_dir = os.path.join(repo_path, normalized_dir.lstrip('/'))
                
                # Check if directory exists
                if os.path.exists(target_dir):
                    directory_exists = True
                    
                    if os.access(target_dir, os.R_OK):
                        is_accessible = True
                        
                        # Find CRD files
                        crd_files = self._find_crd_files(target_dir)
                        
                        # Validate directory structure
                        structure_issues.extend(
                            self._validate_gitops_structure(target_dir)
                        )
                    else:
                        structure_issues.append("Directory exists but is not accessible")
                else:
                    structure_issues.append("Directory does not exist in repository")
                
                return StructureValidation(
                    directory_exists=directory_exists,
                    is_accessible=is_accessible,
                    crd_files=crd_files,
                    structure_issues=structure_issues,
                    recommended_structure=self._get_recommended_structure()
                )
                
        except Exception as e:
            self.logger.error(f"Directory structure validation error: {str(e)}")
            structure_issues.append(f"Structure validation failed: {str(e)}")
            return StructureValidation(
                directory_exists=False,
                is_accessible=False,
                crd_files=[],
                structure_issues=structure_issues,
                recommended_structure=self._get_recommended_structure()
            )
    
    def suggest_available_directories(
        self,
        repository: GitRepository
    ) -> List[str]:
        """
        Suggest available directory paths for a repository.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            List of suggested directory paths
        """
        suggestions = []
        
        try:
            # Get existing directory usage
            from ..models import HedgehogFabric
            fabrics = HedgehogFabric.objects.filter(git_repository=repository)
            used_dirs = set(
                self._normalize_directory_path(f.gitops_directory)
                for f in fabrics
            )
            
            # Generate suggestions based on common patterns
            base_suggestions = [
                'hedgehog/',
                'fabric/',
                'gitops/',
                'k8s/',
                'manifests/',
                'deployments/',
                'clusters/'
            ]
            
            # Add environment-based suggestions
            env_suggestions = [
                'environments/prod/',
                'environments/staging/',
                'environments/dev/',
                'clusters/prod/',
                'clusters/staging/',
                'clusters/dev/'
            ]
            
            # Add fabric-specific suggestions
            fabric_suggestions = [
                f'fabrics/fabric-{i:02d}/' for i in range(1, 20)
            ]
            
            all_suggestions = base_suggestions + env_suggestions + fabric_suggestions
            
            # Filter out used directories and add available ones
            for suggestion in all_suggestions:
                normalized = self._normalize_directory_path(suggestion)
                if normalized not in used_dirs:
                    suggestions.append(normalized)
            
            # Check repository structure for additional suggestions
            try:
                repo_suggestions = self._analyze_repository_structure(repository)
                for suggestion in repo_suggestions:
                    normalized = self._normalize_directory_path(suggestion)
                    if normalized not in used_dirs and normalized not in suggestions:
                        suggestions.append(normalized)
            except Exception as e:
                self.logger.warning(f"Failed to analyze repository structure: {str(e)}")
            
            # Sort by preference (shorter paths first, then alphabetical)
            suggestions.sort(key=lambda x: (len(x.split('/')), x))
            
            return suggestions[:20]  # Limit to top 20 suggestions
            
        except Exception as e:
            self.logger.error(f"Directory suggestion error: {str(e)}")
            return [
                'hedgehog/',
                'fabric/',
                'gitops/',
                'k8s/',
                'manifests/'
            ]
    
    def validate_hedgehog_crd_presence(
        self,
        repository: GitRepository,
        directory: str
    ) -> CRDValidationResult:
        """
        Validate presence and validity of Hedgehog CRDs in directory.
        
        Args:
            repository: GitRepository instance
            directory: Directory path to check
            
        Returns:
            CRDValidationResult with CRD analysis
        """
        normalized_dir = self._normalize_directory_path(directory)
        valid_crds = []
        invalid_crds = []
        hedgehog_crds = []
        other_crds = []
        syntax_errors = []
        schema_warnings = []
        
        try:
            # Clone repository to examine CRDs
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = repository.clone_repository(temp_dir)
                
                if not clone_result.get('success'):
                    return CRDValidationResult(
                        valid_crds=[],
                        invalid_crds=[],
                        hedgehog_crds=[],
                        other_crds=[],
                        syntax_errors=[{
                            'file': 'repository',
                            'error': f"Failed to access repository: {clone_result.get('error')}"
                        }],
                        schema_warnings=[]
                    )
                
                repo_path = clone_result['repository_path']
                target_dir = os.path.join(repo_path, normalized_dir.lstrip('/'))
                
                if not os.path.exists(target_dir):
                    return CRDValidationResult(
                        valid_crds=[],
                        invalid_crds=[],
                        hedgehog_crds=[],
                        other_crds=[],
                        syntax_errors=[],
                        schema_warnings=[f"Directory '{normalized_dir}' does not exist"]
                    )
                
                # Find and validate YAML files
                yaml_files = self._find_yaml_files(target_dir)
                
                for yaml_file in yaml_files:
                    try:
                        file_path = os.path.join(target_dir, yaml_file)
                        
                        with open(file_path, 'r') as f:
                            docs = list(yaml.safe_load_all(f))
                        
                        for doc_idx, doc in enumerate(docs):
                            if not doc or not isinstance(doc, dict):
                                continue
                            
                            # Check if it's a valid Kubernetes resource
                            api_version = doc.get('apiVersion', '')
                            kind = doc.get('kind', '')
                            
                            if not api_version or not kind:
                                invalid_crds.append(f"{yaml_file}[{doc_idx}]")
                                syntax_errors.append({
                                    'file': yaml_file,
                                    'error': 'Missing apiVersion or kind'
                                })
                                continue
                            
                            # Check if it's a Hedgehog CRD
                            if self._is_hedgehog_crd(doc):
                                hedgehog_crds.append(f"{yaml_file}[{doc_idx}]: {kind}")
                                
                                # Validate Hedgehog CRD schema
                                schema_validation = self._validate_hedgehog_crd_schema(doc)
                                if schema_validation['valid']:
                                    valid_crds.append(f"{yaml_file}[{doc_idx}]: {kind}")
                                else:
                                    invalid_crds.append(f"{yaml_file}[{doc_idx}]: {kind}")
                                    schema_warnings.extend(schema_validation['warnings'])
                            else:
                                other_crds.append(f"{yaml_file}[{doc_idx}]: {kind}")
                                valid_crds.append(f"{yaml_file}[{doc_idx}]: {kind}")
                    
                    except yaml.YAMLError as e:
                        invalid_crds.append(yaml_file)
                        syntax_errors.append({
                            'file': yaml_file,
                            'error': f"YAML syntax error: {str(e)}"
                        })
                    except Exception as e:
                        invalid_crds.append(yaml_file)
                        syntax_errors.append({
                            'file': yaml_file,
                            'error': f"File processing error: {str(e)}"
                        })
                
                return CRDValidationResult(
                    valid_crds=valid_crds,
                    invalid_crds=invalid_crds,
                    hedgehog_crds=hedgehog_crds,
                    other_crds=other_crds,
                    syntax_errors=syntax_errors,
                    schema_warnings=schema_warnings
                )
                
        except Exception as e:
            self.logger.error(f"CRD validation error: {str(e)}")
            return CRDValidationResult(
                valid_crds=[],
                invalid_crds=[],
                hedgehog_crds=[],
                other_crds=[],
                syntax_errors=[{
                    'file': 'validator',
                    'error': f"CRD validation failed: {str(e)}"
                }],
                schema_warnings=[]
            )
    
    # Private helper methods
    
    def _normalize_directory_path(self, directory: str) -> str:
        """Normalize directory path for consistency"""
        if not directory:
            return '/'
        
        # Remove leading/trailing whitespace
        normalized = directory.strip()
        
        # Ensure it starts with /
        if not normalized.startswith('/'):
            normalized = '/' + normalized
        
        # Ensure it ends with /
        if not normalized.endswith('/'):
            normalized = normalized + '/'
        
        # Normalize path separators
        normalized = os.path.normpath(normalized).replace('\\', '/')
        
        # Ensure it still starts and ends with /
        if not normalized.startswith('/'):
            normalized = '/' + normalized
        if not normalized.endswith('/'):
            normalized = normalized + '/'
        
        return normalized
    
    def _validate_directory_path(self, directory: str) -> ValidationResult:
        """Validate directory path format and security"""
        issues = []
        suggestions = []
        
        # Check for dangerous path components
        dangerous_patterns = ['..', './', '~/', '$']
        for pattern in dangerous_patterns:
            if pattern in directory:
                issues.append(f"Potentially dangerous path component: {pattern}")
        
        # Check for reserved names
        reserved_names = ['.git', '.github', '.gitlab-ci', 'node_modules', '__pycache__']
        path_parts = [part for part in directory.split('/') if part]
        for part in path_parts:
            if part in reserved_names:
                issues.append(f"Reserved directory name: {part}")
        
        # Check path length
        if len(directory) > 255:
            issues.append("Directory path is too long (>255 characters)")
        
        # Check for valid characters
        import re
        if not re.match(r'^[a-zA-Z0-9/_-]+$', directory):
            issues.append("Directory path contains invalid characters")
            suggestions.append("Use only letters, numbers, hyphens, underscores, and forward slashes")
        
        # Check for good practices
        if not any(pattern in directory.lower() for pattern in self.GITOPS_PATTERNS):
            suggestions.append("Consider using common GitOps directory patterns like 'gitops/', 'k8s/', or 'manifests/'")
        
        is_valid = len(issues) == 0
        level = ValidationLevel.ERROR if not is_valid else ValidationLevel.INFO
        
        return ValidationResult(
            is_valid=is_valid,
            level=level,
            message="Valid directory path" if is_valid else f"Invalid directory path: {'; '.join(issues)}",
            details={'issues': issues},
            suggestions=suggestions
        )
    
    def _check_directory_conflicts(
        self,
        repository: GitRepository,
        directory: str
    ) -> ConflictReport:
        """Check for conflicts with existing directory assignments"""
        try:
            from ..models import HedgehogFabric
            
            # Find fabrics using the same directory
            conflicting_fabrics = HedgehogFabric.objects.filter(
                git_repository=repository,
                gitops_directory=directory
            ).exclude(pk=getattr(repository, '_current_fabric_pk', None))
            
            conflicts = []
            if conflicting_fabrics.exists():
                conflicts.append({
                    'type': ConflictType.DUPLICATE_ASSIGNMENT,
                    'directory': directory,
                    'fabrics': [f.name for f in conflicting_fabrics],
                    'message': f"Directory '{directory}' is already used by {conflicting_fabrics.count()} fabric(s)",
                    'severity': ValidationLevel.ERROR
                })
            
            # Check for overlapping paths
            all_dirs = HedgehogFabric.objects.filter(
                git_repository=repository
            ).values_list('gitops_directory', flat=True)
            
            for existing_dir in all_dirs:
                if existing_dir != directory:
                    if self._paths_overlap(directory, existing_dir):
                        conflicts.append({
                            'type': ConflictType.OVERLAPPING_PATHS,
                            'directory': directory,
                            'conflicting_directory': existing_dir,
                            'message': f"Directory '{directory}' overlaps with existing '{existing_dir}'",
                            'severity': ValidationLevel.WARNING
                        })
            
            return ConflictReport(
                conflicts=conflicts,
                affected_fabrics=[f.name for f in conflicting_fabrics],
                severity=ValidationLevel.ERROR if conflicts else ValidationLevel.INFO,
                auto_resolvable=len(conflicts) == 0,
                resolution_suggestions=self._generate_conflict_resolutions(conflicts)
            )
            
        except Exception as e:
            return ConflictReport(
                conflicts=[{
                    'type': 'validation_error',
                    'message': f"Conflict check failed: {str(e)}",
                    'severity': ValidationLevel.CRITICAL
                }],
                affected_fabrics=[],
                severity=ValidationLevel.CRITICAL,
                auto_resolvable=False,
                resolution_suggestions=["Contact administrator"]
            )
    
    def _check_directory_exists(
        self,
        repository: GitRepository,
        directory: str
    ) -> bool:
        """Check if directory exists in repository"""
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = repository.clone_repository(temp_dir)
                
                if not clone_result.get('success'):
                    return False
                
                repo_path = clone_result['repository_path']
                target_dir = os.path.join(repo_path, directory.lstrip('/'))
                
                return os.path.exists(target_dir) and os.path.isdir(target_dir)
                
        except Exception:
            return False
    
    def _get_directory_best_practices(self, directory: str) -> List[str]:
        """Get best practice suggestions for directory usage"""
        suggestions = []
        
        # Depth suggestions
        depth = len([p for p in directory.split('/') if p])
        if depth > 4:
            suggestions.append("Consider using a shallower directory structure for easier management")
        
        # Pattern suggestions
        if not any(pattern in directory.lower() for pattern in self.GITOPS_PATTERNS):
            suggestions.append("Consider using established GitOps patterns like 'gitops/', 'k8s/', or 'manifests/'")
        
        # Environment suggestions
        if 'prod' in directory.lower():
            suggestions.append("Production directory detected - ensure proper access controls")
        
        return suggestions
    
    def _detect_overlapping_paths(self, directories: List[str]) -> List[Dict[str, Any]]:
        """Detect overlapping directory paths"""
        conflicts = []
        dir_list = list(directories)
        
        for i, dir1 in enumerate(dir_list):
            for dir2 in dir_list[i+1:]:
                if self._paths_overlap(dir1, dir2):
                    conflicts.append({
                        'type': ConflictType.OVERLAPPING_PATHS,
                        'directory1': dir1,
                        'directory2': dir2,
                        'message': f"Paths '{dir1}' and '{dir2}' overlap",
                        'severity': ValidationLevel.WARNING
                    })
        
        return conflicts
    
    def _paths_overlap(self, path1: str, path2: str) -> bool:
        """Check if two paths overlap (one is parent of the other)"""
        # Normalize paths
        p1 = self._normalize_directory_path(path1)
        p2 = self._normalize_directory_path(path2)
        
        # Check if one is a parent of the other
        return p1.startswith(p2) or p2.startswith(p1)
    
    def _generate_conflict_resolutions(self, conflicts: List[Dict[str, Any]]) -> List[str]:
        """Generate resolution suggestions for conflicts"""
        suggestions = []
        
        for conflict in conflicts:
            conflict_type = conflict.get('type')
            
            if conflict_type == ConflictType.DUPLICATE_ASSIGNMENT:
                suggestions.append(
                    f"Use a unique subdirectory for each fabric, e.g., '{conflict['directory']}fabric-name/'"
                )
            elif conflict_type == ConflictType.OVERLAPPING_PATHS:
                suggestions.append(
                    "Use non-overlapping directory paths for different fabrics"
                )
            elif conflict_type == ConflictType.INVALID_PATH:
                suggestions.append(
                    "Choose a valid directory path using only letters, numbers, and standard separators"
                )
        
        # Add general suggestions
        if conflicts:
            suggestions.append("Consider using environment-based directory structure: environments/{env}/")
            suggestions.append("Use fabric naming: fabrics/{fabric-name}/")
        
        return list(set(suggestions))  # Remove duplicates
    
    def _check_auto_resolvable(self, conflicts: List[Dict[str, Any]]) -> bool:
        """Check if conflicts can be automatically resolved"""
        # For now, conflicts require manual resolution
        # In the future, we could implement auto-resolution for some cases
        return False
    
    def _find_crd_files(self, directory: str) -> List[str]:
        """Find CRD files in directory"""
        crd_files = []
        
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(('.yaml', '.yml')):
                    rel_path = os.path.relpath(
                        os.path.join(root, file),
                        directory
                    )
                    crd_files.append(rel_path)
        
        return crd_files
    
    def _find_yaml_files(self, directory: str) -> List[str]:
        """Find YAML files in directory"""
        yaml_files = []
        
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(('.yaml', '.yml')):
                    rel_path = os.path.relpath(
                        os.path.join(root, file),
                        directory
                    )
                    yaml_files.append(rel_path)
        
        return yaml_files
    
    def _validate_gitops_structure(self, directory: str) -> List[str]:
        """Validate GitOps directory structure"""
        issues = []
        
        # Check for common GitOps files
        expected_files = ['kustomization.yaml', 'kustomization.yml']
        has_kustomization = any(
            os.path.exists(os.path.join(directory, f))
            for f in expected_files
        )
        
        if not has_kustomization:
            issues.append("No kustomization.yaml found - consider using Kustomize for GitOps")
        
        # Check for reasonable file organization
        yaml_files = self._find_yaml_files(directory)
        if len(yaml_files) > 20:
            issues.append("Large number of YAML files - consider organizing into subdirectories")
        
        return issues
    
    def _get_recommended_structure(self) -> Dict[str, Any]:
        """Get recommended directory structure"""
        return {
            'base_structure': {
                'kustomization.yaml': 'Kustomize configuration file',
                'hedgehog/': {
                    'vpcs/': 'VPC CRD definitions',
                    'connections/': 'Connection CRD definitions',
                    'servers/': 'Server CRD definitions',
                    'switches/': 'Switch CRD definitions'
                }
            },
            'best_practices': [
                "Use Kustomize for configuration management",
                "Organize CRDs by type in subdirectories",
                "Include clear naming conventions",
                "Add documentation files"
            ]
        }
    
    def _analyze_repository_structure(self, repository: GitRepository) -> List[str]:
        """Analyze repository structure for directory suggestions"""
        suggestions = []
        
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = repository.clone_repository(temp_dir)
                
                if not clone_result.get('success'):
                    return suggestions
                
                repo_path = clone_result['repository_path']
                
                # Look for existing GitOps directories
                for root, dirs, files in os.walk(repo_path):
                    for dir_name in dirs:
                        if any(pattern.rstrip('/') in dir_name.lower() for pattern in self.GITOPS_PATTERNS):
                            rel_path = os.path.relpath(
                                os.path.join(root, dir_name),
                                repo_path
                            )
                            suggestions.append(rel_path + '/')
                
                # Look for empty directories that could be used
                for root, dirs, files in os.walk(repo_path):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        if not os.listdir(dir_path):  # Empty directory
                            rel_path = os.path.relpath(dir_path, repo_path)
                            suggestions.append(rel_path + '/')
        
        except Exception as e:
            self.logger.warning(f"Repository structure analysis failed: {str(e)}")
        
        return suggestions[:10]  # Limit suggestions
    
    def _is_hedgehog_crd(self, document: Dict[str, Any]) -> bool:
        """Check if a document is a Hedgehog CRD"""
        api_version = document.get('apiVersion', '')
        kind = document.get('kind', '')
        
        # Check API version
        if 'hedgehog.io' in api_version:
            return True
        
        # Check known Hedgehog kinds
        return kind in self.HEDGEHOG_CRDS
    
    def _validate_hedgehog_crd_schema(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Hedgehog CRD schema"""
        warnings = []
        valid = True
        
        # Basic Kubernetes resource validation
        required_fields = ['apiVersion', 'kind', 'metadata']
        for field in required_fields:
            if field not in document:
                warnings.append(f"Missing required field: {field}")
                valid = False
        
        # Metadata validation
        metadata = document.get('metadata', {})
        if not metadata.get('name'):
            warnings.append("Missing metadata.name")
            valid = False
        
        # Spec validation (if present)
        if 'spec' in document:
            spec = document['spec']
            if not isinstance(spec, dict):
                warnings.append("Spec must be an object")
                valid = False
        
        # Hedgehog-specific validation
        kind = document.get('kind', '')
        if kind in self.HEDGEHOG_CRDS:
            expected_api_versions = self.HEDGEHOG_CRDS[kind]
            actual_api_version = document.get('apiVersion', '')
            
            if actual_api_version not in expected_api_versions:
                warnings.append(
                    f"Unexpected API version for {kind}: {actual_api_version}. "
                    f"Expected one of: {', '.join(expected_api_versions)}"
                )
        
        return {
            'valid': valid,
            'warnings': warnings
        }