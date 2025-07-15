"""
GitOps Path Validation Utilities
Provides utilities for validating and sanitizing GitOps directory paths
"""

import os
import re
import logging
from pathlib import Path, PurePosixPath
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass

logger = logging.getLogger('netbox_hedgehog.gitops_path_validator')


@dataclass
class PathValidationResult:
    """Result of path validation"""
    is_valid: bool
    normalized_path: str
    issues: List[str]
    warnings: List[str]
    suggestions: List[str]
    
    def to_dict(self) -> Dict:
        return {
            'is_valid': self.is_valid,
            'normalized_path': self.normalized_path,
            'issues': self.issues,
            'warnings': self.warnings,
            'suggestions': self.suggestions
        }


class GitOpsPathValidator:
    """Utilities for validating GitOps directory paths"""
    
    # Security patterns to block
    DANGEROUS_PATTERNS = {
        '..': 'Path traversal attempt',
        '../': 'Path traversal attempt',
        './': 'Relative path reference',
        '~/': 'Home directory reference',
        '$': 'Variable expansion attempt',
        '${': 'Variable expansion attempt',
        '`': 'Command substitution attempt',
        ';': 'Command separator',
        '|': 'Pipe operator',
        '&': 'Command operator',
        '<': 'Redirection operator',
        '>': 'Redirection operator',
        '*': 'Wildcard character',
        '?': 'Wildcard character',
        '[': 'Character class',
        ']': 'Character class'
    }
    
    # Reserved directory names
    RESERVED_NAMES = {
        '.git',
        '.github',
        '.gitlab',
        '.gitlab-ci',
        '.gitignore',
        '.gitmodules',
        'node_modules',
        '__pycache__',
        '.pytest_cache',
        '.tox',
        '.venv',
        'venv',
        '.env',
        'env',
        'tmp',
        'temp',
        'cache',
        '.cache',
        'build',
        'dist',
        'target',
        'bin',
        'obj',
        '.DS_Store',
        'Thumbs.db'
    }
    
    # Common GitOps directory patterns
    GITOPS_PATTERNS = {
        'gitops': 'GitOps root directory',
        'k8s': 'Kubernetes manifests',
        'kubernetes': 'Kubernetes manifests',
        'manifests': 'Kubernetes manifests',
        'deployments': 'Deployment configurations',
        'apps': 'Application definitions',
        'clusters': 'Cluster configurations',
        'environments': 'Environment-specific configs',
        'env': 'Environment-specific configs',
        'overlays': 'Kustomize overlays',
        'base': 'Kustomize base configurations',
        'components': 'Reusable components',
        'charts': 'Helm charts',
        'templates': 'Template files',
        'config': 'Configuration files',
        'configs': 'Configuration files'
    }
    
    # Maximum path length
    MAX_PATH_LENGTH = 255
    MAX_COMPONENT_LENGTH = 255
    MAX_DEPTH = 10
    
    def __init__(self):
        self.logger = logger
    
    def validate_path(
        self,
        path: str,
        context: Optional[str] = None
    ) -> PathValidationResult:
        """
        Validate a GitOps directory path.
        
        Args:
            path: Path to validate
            context: Optional context for validation (e.g., 'fabric', 'environment')
            
        Returns:
            PathValidationResult with validation details
        """
        issues = []
        warnings = []
        suggestions = []
        
        # Initial path cleanup
        original_path = path
        normalized_path = self._normalize_path(path)
        
        # Basic validation
        if not path or not path.strip():
            issues.append("Path cannot be empty")
            return PathValidationResult(
                is_valid=False,
                normalized_path='/',
                issues=issues,
                warnings=warnings,
                suggestions=['Use a meaningful directory path like "gitops/" or "k8s/"']
            )
        
        # Length validation
        if len(normalized_path) > self.MAX_PATH_LENGTH:
            issues.append(f"Path too long ({len(normalized_path)} > {self.MAX_PATH_LENGTH} characters)")
        
        # Security validation
        security_issues = self._check_security_patterns(normalized_path)
        issues.extend(security_issues)
        
        # Component validation
        component_issues, component_warnings, component_suggestions = self._validate_components(normalized_path)
        issues.extend(component_issues)
        warnings.extend(component_warnings)
        suggestions.extend(component_suggestions)
        
        # Structure validation
        structure_warnings, structure_suggestions = self._validate_structure(normalized_path, context)
        warnings.extend(structure_warnings)
        suggestions.extend(structure_suggestions)
        
        # Platform compatibility
        platform_warnings = self._check_platform_compatibility(normalized_path)
        warnings.extend(platform_warnings)
        
        is_valid = len(issues) == 0
        
        return PathValidationResult(
            is_valid=is_valid,
            normalized_path=normalized_path,
            issues=issues,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def normalize_path(self, path: str) -> str:
        """
        Normalize a path for consistent usage.
        
        Args:
            path: Raw path string
            
        Returns:
            Normalized path string
        """
        return self._normalize_path(path)
    
    def suggest_alternatives(
        self,
        invalid_path: str,
        context: Optional[str] = None
    ) -> List[str]:
        """
        Suggest alternative paths for an invalid path.
        
        Args:
            invalid_path: Path that failed validation
            context: Optional context for suggestions
            
        Returns:
            List of suggested alternative paths
        """
        suggestions = []
        
        # Clean up the path
        cleaned = self._clean_invalid_path(invalid_path)
        
        # Context-based suggestions
        if context == 'fabric':
            suggestions.extend([
                f'fabrics/{cleaned}/',
                f'hedgehog/{cleaned}/',
                f'environments/prod/{cleaned}/',
                f'gitops/fabrics/{cleaned}/'
            ])
        elif context == 'environment':
            suggestions.extend([
                f'environments/{cleaned}/',
                f'env/{cleaned}/',
                f'clusters/{cleaned}/',
                f'gitops/{cleaned}/'
            ])
        else:
            # Generic suggestions
            suggestions.extend([
                f'gitops/{cleaned}/',
                f'k8s/{cleaned}/',
                f'manifests/{cleaned}/',
                f'deployments/{cleaned}/'
            ])
        
        # Pattern-based suggestions
        for pattern, description in self.GITOPS_PATTERNS.items():
            if cleaned and cleaned not in pattern:
                suggestions.append(f'{pattern}/{cleaned}/')
        
        # Remove duplicates and invalid suggestions
        valid_suggestions = []
        for suggestion in set(suggestions):
            validation = self.validate_path(suggestion, context)
            if validation.is_valid:
                valid_suggestions.append(suggestion)
        
        return valid_suggestions[:10]  # Limit to 10 suggestions
    
    def generate_unique_path(
        self,
        base_path: str,
        used_paths: Set[str],
        context: Optional[str] = None
    ) -> str:
        """
        Generate a unique path based on a base path.
        
        Args:
            base_path: Base path to make unique
            used_paths: Set of already used paths
            context: Optional context for path generation
            
        Returns:
            Unique path string
        """
        # Normalize base path
        normalized_base = self._normalize_path(base_path)
        
        # If not used, return as-is
        if normalized_base not in used_paths:
            validation = self.validate_path(normalized_base, context)
            if validation.is_valid:
                return normalized_base
        
        # Generate variations
        base_name = normalized_base.rstrip('/')
        
        for i in range(2, 100):  # Try suffixes 2-99
            candidate = f'{base_name}-{i:02d}/'
            if candidate not in used_paths:
                validation = self.validate_path(candidate, context)
                if validation.is_valid:
                    return candidate
        
        # Fallback to timestamp-based unique path
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        fallback = f'{base_name}-{timestamp}/'
        
        return fallback
    
    def extract_path_components(self, path: str) -> Dict[str, any]:
        """
        Extract meaningful components from a path.
        
        Args:
            path: Path to analyze
            
        Returns:
            Dictionary with path analysis
        """
        normalized = self._normalize_path(path)
        parts = [p for p in normalized.split('/') if p]
        
        return {
            'normalized_path': normalized,
            'parts': parts,
            'depth': len(parts),
            'is_root': len(parts) == 0,
            'parent_path': '/'.join(parts[:-1]) + '/' if len(parts) > 1 else '/',
            'directory_name': parts[-1] if parts else '',
            'gitops_patterns': [
                pattern for pattern in self.GITOPS_PATTERNS.keys()
                if any(pattern in part.lower() for part in parts)
            ],
            'potential_environment': self._extract_environment(parts),
            'potential_app_name': self._extract_app_name(parts)
        }
    
    def check_path_conflicts(
        self,
        path: str,
        existing_paths: List[str]
    ) -> Dict[str, any]:
        """
        Check for path conflicts with existing paths.
        
        Args:
            path: Path to check
            existing_paths: List of existing paths
            
        Returns:
            Dictionary with conflict analysis
        """
        normalized = self._normalize_path(path)
        conflicts = {
            'exact_matches': [],
            'parent_conflicts': [],
            'child_conflicts': [],
            'similar_paths': []
        }
        
        for existing in existing_paths:
            existing_normalized = self._normalize_path(existing)
            
            # Exact match
            if normalized == existing_normalized:
                conflicts['exact_matches'].append(existing_normalized)
            
            # Parent/child relationships
            elif normalized.startswith(existing_normalized):
                conflicts['parent_conflicts'].append(existing_normalized)
            elif existing_normalized.startswith(normalized):
                conflicts['child_conflicts'].append(existing_normalized)
            
            # Similar paths (edit distance)
            elif self._calculate_similarity(normalized, existing_normalized) > 0.8:
                conflicts['similar_paths'].append(existing_normalized)
        
        return {
            'has_conflicts': any(conflicts.values()),
            'conflicts': conflicts,
            'conflict_severity': self._assess_conflict_severity(conflicts)
        }
    
    # Private helper methods
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for consistent usage"""
        if not path:
            return '/'
        
        # Clean up the path
        cleaned = path.strip()
        
        # Convert backslashes to forward slashes
        cleaned = cleaned.replace('\\', '/')
        
        # Remove multiple slashes
        cleaned = re.sub(r'/+', '/', cleaned)
        
        # Ensure it starts with /
        if not cleaned.startswith('/'):
            cleaned = '/' + cleaned
        
        # Ensure it ends with / (for directories)
        if not cleaned.endswith('/'):
            cleaned = cleaned + '/'
        
        # Use PurePosixPath for normalization
        try:
            posix_path = PurePosixPath(cleaned)
            normalized = str(posix_path)
            
            # Ensure trailing slash for directories
            if not normalized.endswith('/'):
                normalized = normalized + '/'
                
            return normalized
        except Exception:
            # Fallback normalization
            return cleaned
    
    def _check_security_patterns(self, path: str) -> List[str]:
        """Check for security-related patterns in path"""
        issues = []
        
        for pattern, description in self.DANGEROUS_PATTERNS.items():
            if pattern in path:
                issues.append(f"Security issue: {description} (contains '{pattern}')")
        
        return issues
    
    def _validate_components(self, path: str) -> Tuple[List[str], List[str], List[str]]:
        """Validate individual path components"""
        issues = []
        warnings = []
        suggestions = []
        
        parts = [p for p in path.split('/') if p]
        
        # Check depth
        if len(parts) > self.MAX_DEPTH:
            issues.append(f"Path too deep ({len(parts)} > {self.MAX_DEPTH} levels)")
        elif len(parts) > 5:
            warnings.append("Deep directory structure may be hard to manage")
        
        # Check each component
        for i, part in enumerate(parts):
            # Length check
            if len(part) > self.MAX_COMPONENT_LENGTH:
                issues.append(f"Component '{part}' too long ({len(part)} > {self.MAX_COMPONENT_LENGTH})")
            
            # Reserved names
            if part.lower() in self.RESERVED_NAMES:
                issues.append(f"Reserved directory name: '{part}'")
            
            # Character validation
            if not re.match(r'^[a-zA-Z0-9._-]+$', part):
                issues.append(f"Invalid characters in component '{part}' (use only letters, numbers, dots, hyphens, underscores)")
            
            # Naming conventions
            if part.startswith('.') and part not in ['.git', '.github', '.gitlab']:
                warnings.append(f"Hidden directory '{part}' may cause issues")
            
            if part.startswith('-') or part.endswith('-'):
                warnings.append(f"Component '{part}' should not start or end with hyphen")
            
            if '__' in part:
                warnings.append(f"Double underscores in '{part}' may cause issues")
        
        # Suggest improvements
        if not any(pattern in path.lower() for pattern in self.GITOPS_PATTERNS):
            suggestions.append("Consider using established GitOps patterns like 'gitops/', 'k8s/', or 'manifests/'")
        
        return issues, warnings, suggestions
    
    def _validate_structure(
        self,
        path: str,
        context: Optional[str]
    ) -> Tuple[List[str], List[str]]:
        """Validate path structure and provide suggestions"""
        warnings = []
        suggestions = []
        
        parts = [p for p in path.split('/') if p]
        
        # Context-specific validation
        if context == 'fabric':
            if not any(word in path.lower() for word in ['fabric', 'hedgehog', 'gitops']):
                suggestions.append("Consider including 'fabric' or 'hedgehog' in the path for clarity")
        
        elif context == 'environment':
            if not any(word in path.lower() for word in ['env', 'environment', 'cluster']):
                suggestions.append("Consider including 'env' or 'environment' in the path")
        
        # Structure suggestions
        if len(parts) == 1:
            suggestions.append("Consider using hierarchical structure: category/name/")
        
        if len(parts) > 4:
            suggestions.append("Consider flattening deep directory structures")
        
        # Pattern recommendations
        gitops_patterns_found = [
            pattern for pattern in self.GITOPS_PATTERNS.keys()
            if any(pattern in part.lower() for part in parts)
        ]
        
        if not gitops_patterns_found:
            warnings.append("No recognized GitOps patterns found in path")
            suggestions.append("Use common GitOps patterns: gitops/, k8s/, manifests/, environments/")
        
        return warnings, suggestions
    
    def _check_platform_compatibility(self, path: str) -> List[str]:
        """Check for platform-specific compatibility issues"""
        warnings = []
        
        # Windows compatibility
        if len(path) > 260:
            warnings.append("Path may exceed Windows path length limits")
        
        # Case sensitivity issues
        parts = [p for p in path.split('/') if p]
        lower_parts = [p.lower() for p in parts]
        if len(set(lower_parts)) != len(lower_parts):
            warnings.append("Path contains components that differ only in case")
        
        # Special characters that may cause issues
        problematic_chars = [':', '"', "'", ' ']
        for char in problematic_chars:
            if char in path:
                warnings.append(f"Character '{char}' may cause issues on some platforms")
        
        return warnings
    
    def _clean_invalid_path(self, path: str) -> str:
        """Clean up an invalid path to make it usable"""
        # Remove dangerous patterns
        cleaned = path
        for pattern in self.DANGEROUS_PATTERNS.keys():
            cleaned = cleaned.replace(pattern, '')
        
        # Remove invalid characters
        cleaned = re.sub(r'[^a-zA-Z0-9._/-]', '-', cleaned)
        
        # Remove multiple hyphens/underscores
        cleaned = re.sub(r'[-_]+', '-', cleaned)
        
        # Remove leading/trailing special chars
        cleaned = cleaned.strip('.-_/')
        
        # Ensure it's not empty
        if not cleaned:
            cleaned = 'path'
        
        return cleaned
    
    def _extract_environment(self, parts: List[str]) -> Optional[str]:
        """Extract potential environment name from path parts"""
        env_indicators = ['env', 'environment', 'environments']
        
        for i, part in enumerate(parts):
            if part.lower() in env_indicators and i + 1 < len(parts):
                return parts[i + 1]
            
            # Common environment names
            env_names = ['prod', 'production', 'staging', 'stage', 'dev', 'development', 'test', 'qa']
            if part.lower() in env_names:
                return part
        
        return None
    
    def _extract_app_name(self, parts: List[str]) -> Optional[str]:
        """Extract potential application name from path parts"""
        app_indicators = ['app', 'apps', 'application', 'applications', 'service', 'services']
        
        for i, part in enumerate(parts):
            if part.lower() in app_indicators and i + 1 < len(parts):
                return parts[i + 1]
        
        # Last non-environment part might be app name
        if parts:
            return parts[-1]
        
        return None
    
    def _calculate_similarity(self, path1: str, path2: str) -> float:
        """Calculate similarity between two paths (0.0 to 1.0)"""
        # Simple similarity based on common characters
        set1 = set(path1.lower())
        set2 = set(path2.lower())
        
        if not set1 and not set2:
            return 1.0
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _assess_conflict_severity(self, conflicts: Dict[str, List]) -> str:
        """Assess the severity of path conflicts"""
        if conflicts['exact_matches']:
            return 'critical'
        elif conflicts['parent_conflicts'] or conflicts['child_conflicts']:
            return 'high'
        elif conflicts['similar_paths']:
            return 'medium'
        else:
            return 'low'


# Convenience functions for common use cases

def validate_gitops_path(path: str, context: Optional[str] = None) -> PathValidationResult:
    """
    Convenience function to validate a GitOps path.
    
    Args:
        path: Path to validate
        context: Optional context ('fabric', 'environment', etc.)
        
    Returns:
        PathValidationResult
    """
    validator = GitOpsPathValidator()
    return validator.validate_path(path, context)


def normalize_gitops_path(path: str) -> str:
    """
    Convenience function to normalize a GitOps path.
    
    Args:
        path: Path to normalize
        
    Returns:
        Normalized path string
    """
    validator = GitOpsPathValidator()
    return validator.normalize_path(path)


def suggest_gitops_paths(invalid_path: str, context: Optional[str] = None) -> List[str]:
    """
    Convenience function to suggest alternative GitOps paths.
    
    Args:
        invalid_path: Invalid path to suggest alternatives for
        context: Optional context for suggestions
        
    Returns:
        List of suggested paths
    """
    validator = GitOpsPathValidator()
    return validator.suggest_alternatives(invalid_path, context)