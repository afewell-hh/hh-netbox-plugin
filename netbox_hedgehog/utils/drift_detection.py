"""
Advanced Drift Detection Utilities
Provides sophisticated algorithms for detecting and analyzing configuration drift
between desired state (from Git) and actual state (from Kubernetes).
"""

import json
import yaml
import copy
from typing import Dict, List, Tuple, Any, Set, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Advanced drift detection engine for Kubernetes resources.
    Provides deep comparison of resource specifications with semantic awareness.
    """
    
    def __init__(self):
        self.ignore_fields = {
            # Standard Kubernetes metadata fields that should be ignored
            'metadata.uid',
            'metadata.resourceVersion',
            'metadata.generation',
            'metadata.creationTimestamp',
            'metadata.managedFields',
            'metadata.selfLink',
            'status',  # Status is managed by Kubernetes controllers
        }
        
        self.semantic_comparisons = {
            # Fields that require semantic comparison rather than exact match
            'metadata.labels': self._compare_labels,
            'metadata.annotations': self._compare_annotations,
            'spec.ports': self._compare_ports,
            'spec.selector': self._compare_selectors,
            'spec.replicas': self._compare_numeric,
        }
        
        self.drift_weights = {
            # Weight different types of drift by importance
            'spec': 1.0,           # Spec changes are critical
            'metadata.labels': 0.7,  # Label changes are important
            'metadata.annotations': 0.3,  # Annotation changes are less critical
        }
    
    def detect_drift(self, desired: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect drift between desired and actual resource states.
        
        Args:
            desired: Desired resource state from Git
            actual: Actual resource state from Kubernetes
            
        Returns:
            Dict containing drift analysis results
        """
        if not desired and not actual:
            return self._no_drift_result()
        
        if not desired:
            return self._actual_only_result(actual)
        
        if not actual:
            return self._desired_only_result(desired)
        
        # Perform deep comparison
        differences = self._deep_compare(desired, actual, path='')
        
        if not differences:
            return self._no_drift_result()
        
        # Calculate drift score
        drift_score = self._calculate_drift_score(differences)
        
        # Categorize differences
        categorized_diffs = self._categorize_differences(differences)
        
        return {
            'has_drift': True,
            'drift_score': min(drift_score, 1.0),
            'total_differences': len(differences),
            'differences': differences,
            'categorized_differences': categorized_diffs,
            'summary': self._generate_drift_summary(categorized_diffs),
            'recommendations': self._generate_recommendations(categorized_diffs)
        }
    
    def _deep_compare(self, desired: Any, actual: Any, path: str) -> List[Dict[str, Any]]:
        """
        Perform deep comparison of two objects.
        
        Args:
            desired: Desired value
            actual: Actual value
            path: Current path in the object hierarchy
            
        Returns:
            List of differences found
        """
        differences = []
        
        # Skip ignored fields
        if self._should_ignore_path(path):
            return differences
        
        # Handle None values
        if desired is None and actual is None:
            return differences
        if desired is None:
            differences.append({
                'path': path,
                'type': 'missing_desired',
                'actual': actual,
                'severity': 'medium'
            })
            return differences
        if actual is None:
            differences.append({
                'path': path,
                'type': 'missing_actual',
                'desired': desired,
                'severity': 'high'
            })
            return differences
        
        # Use semantic comparison if available
        if path in self.semantic_comparisons:
            semantic_result = self.semantic_comparisons[path](desired, actual, path)
            if semantic_result:
                differences.extend(semantic_result)
            return differences
        
        # Handle different types
        if type(desired) != type(actual):
            differences.append({
                'path': path,
                'type': 'type_mismatch',
                'desired': desired,
                'actual': actual,
                'desired_type': type(desired).__name__,
                'actual_type': type(actual).__name__,
                'severity': 'high'
            })
            return differences
        
        # Compare based on type
        if isinstance(desired, dict):
            differences.extend(self._compare_dicts(desired, actual, path))
        elif isinstance(desired, list):
            differences.extend(self._compare_lists(desired, actual, path))
        elif desired != actual:
            differences.append({
                'path': path,
                'type': 'value_mismatch',
                'desired': desired,
                'actual': actual,
                'severity': self._determine_severity(path)
            })
        
        return differences
    
    def _compare_dicts(self, desired: Dict, actual: Dict, path: str) -> List[Dict[str, Any]]:
        """Compare two dictionaries recursively"""
        differences = []
        
        # Find keys in desired but not in actual
        for key in desired:
            new_path = f"{path}.{key}" if path else key
            if key not in actual:
                differences.append({
                    'path': new_path,
                    'type': 'missing_key_actual',
                    'desired': desired[key],
                    'severity': self._determine_severity(new_path)
                })
            else:
                differences.extend(self._deep_compare(desired[key], actual[key], new_path))
        
        # Find keys in actual but not in desired
        for key in actual:
            if key not in desired:
                new_path = f"{path}.{key}" if path else key
                differences.append({
                    'path': new_path,
                    'type': 'extra_key_actual',
                    'actual': actual[key],
                    'severity': 'low'
                })
        
        return differences
    
    def _compare_lists(self, desired: List, actual: List, path: str) -> List[Dict[str, Any]]:
        """Compare two lists with smart matching"""
        differences = []
        
        if len(desired) != len(actual):
            differences.append({
                'path': path,
                'type': 'length_mismatch',
                'desired_length': len(desired),
                'actual_length': len(actual),
                'severity': 'medium'
            })
        
        # For small lists, do element-by-element comparison
        if len(desired) <= 20 and len(actual) <= 20:
            max_len = max(len(desired), len(actual))
            for i in range(max_len):
                item_path = f"{path}[{i}]"
                desired_item = desired[i] if i < len(desired) else None
                actual_item = actual[i] if i < len(actual) else None
                differences.extend(self._deep_compare(desired_item, actual_item, item_path))
        else:
            # For large lists, do set-based comparison
            desired_set = set(json.dumps(item, sort_keys=True) if isinstance(item, (dict, list)) else str(item) for item in desired)
            actual_set = set(json.dumps(item, sort_keys=True) if isinstance(item, (dict, list)) else str(item) for item in actual)
            
            missing_in_actual = desired_set - actual_set
            extra_in_actual = actual_set - desired_set
            
            if missing_in_actual:
                differences.append({
                    'path': path,
                    'type': 'missing_list_items',
                    'missing_count': len(missing_in_actual),
                    'severity': 'medium'
                })
            
            if extra_in_actual:
                differences.append({
                    'path': path,
                    'type': 'extra_list_items',
                    'extra_count': len(extra_in_actual),
                    'severity': 'low'
                })
        
        return differences
    
    def _compare_labels(self, desired: Dict, actual: Dict, path: str) -> List[Dict[str, Any]]:
        """Smart comparison for Kubernetes labels"""
        differences = []
        
        # Ignore system labels
        system_prefixes = ['app.kubernetes.io/', 'kubectl.kubernetes.io/', 'kubernetes.io/']
        
        desired_user_labels = {k: v for k, v in (desired or {}).items() 
                              if not any(k.startswith(prefix) for prefix in system_prefixes)}
        actual_user_labels = {k: v for k, v in (actual or {}).items() 
                             if not any(k.startswith(prefix) for prefix in system_prefixes)}
        
        return self._deep_compare(desired_user_labels, actual_user_labels, path)
    
    def _compare_annotations(self, desired: Dict, actual: Dict, path: str) -> List[Dict[str, Any]]:
        """Smart comparison for Kubernetes annotations"""
        differences = []
        
        # Ignore system annotations
        system_prefixes = [
            'kubectl.kubernetes.io/',
            'deployment.kubernetes.io/',
            'kubernetes.io/',
            'control-plane.alpha.kubernetes.io/',
        ]
        
        desired_user_annotations = {k: v for k, v in (desired or {}).items() 
                                   if not any(k.startswith(prefix) for prefix in system_prefixes)}
        actual_user_annotations = {k: v for k, v in (actual or {}).items() 
                                  if not any(k.startswith(prefix) for prefix in system_prefixes)}
        
        return self._deep_compare(desired_user_annotations, actual_user_annotations, path)
    
    def _compare_ports(self, desired: List, actual: List, path: str) -> List[Dict[str, Any]]:
        """Smart comparison for port specifications"""
        # Normalize ports by converting to consistent format
        def normalize_port(port):
            if isinstance(port, dict):
                normalized = copy.deepcopy(port)
                # Ensure protocol is specified (defaults to TCP)
                if 'protocol' not in normalized:
                    normalized['protocol'] = 'TCP'
                return normalized
            return port
        
        desired_normalized = [normalize_port(p) for p in (desired or [])]
        actual_normalized = [normalize_port(p) for p in (actual or [])]
        
        return self._compare_lists(desired_normalized, actual_normalized, path)
    
    def _compare_selectors(self, desired: Dict, actual: Dict, path: str) -> List[Dict[str, Any]]:
        """Smart comparison for Kubernetes selectors"""
        # Selectors are critical for service routing
        differences = self._deep_compare(desired, actual, path)
        
        # Increase severity for selector differences
        for diff in differences:
            if diff['severity'] in ['low', 'medium']:
                diff['severity'] = 'high'
        
        return differences
    
    def _compare_numeric(self, desired: Any, actual: Any, path: str) -> List[Dict[str, Any]]:
        """Smart comparison for numeric values"""
        try:
            desired_num = float(desired) if desired is not None else None
            actual_num = float(actual) if actual is not None else None
            
            if desired_num == actual_num:
                return []
            
            return [{
                'path': path,
                'type': 'numeric_mismatch',
                'desired': desired_num,
                'actual': actual_num,
                'severity': 'medium'
            }]
        except (TypeError, ValueError):
            # Fallback to string comparison
            return self._deep_compare(str(desired), str(actual), path)
    
    def _should_ignore_path(self, path: str) -> bool:
        """Check if a path should be ignored during comparison"""
        for ignore_pattern in self.ignore_fields:
            if path == ignore_pattern or path.startswith(f"{ignore_pattern}."):
                return True
        return False
    
    def _determine_severity(self, path: str) -> str:
        """Determine the severity of a difference based on the path"""
        if path.startswith('spec.'):
            return 'high'
        elif path.startswith('metadata.labels'):
            return 'medium'
        elif path.startswith('metadata.annotations'):
            return 'low'
        elif path.startswith('metadata.'):
            return 'low'
        else:
            return 'medium'
    
    def _calculate_drift_score(self, differences: List[Dict[str, Any]]) -> float:
        """Calculate a numerical drift score from 0.0 to 1.0"""
        if not differences:
            return 0.0
        
        total_weight = 0.0
        weighted_score = 0.0
        
        severity_weights = {
            'high': 1.0,
            'medium': 0.6,
            'low': 0.3
        }
        
        for diff in differences:
            severity = diff.get('severity', 'medium')
            path = diff.get('path', '')
            
            # Get base weight for this type of difference
            base_weight = severity_weights.get(severity, 0.6)
            
            # Apply path-specific weight if available
            path_weight = 1.0
            for pattern, weight in self.drift_weights.items():
                if path.startswith(pattern):
                    path_weight = weight
                    break
            
            final_weight = base_weight * path_weight
            total_weight += final_weight
            weighted_score += final_weight
        
        # Normalize score
        if total_weight == 0:
            return 0.0
        
        # Scale based on number of differences
        base_score = weighted_score / max(total_weight, 1.0)
        
        # Apply diminishing returns for many differences
        num_diffs = len(differences)
        if num_diffs > 5:
            multiplier = 1.0 + (num_diffs - 5) * 0.1
            base_score *= multiplier
        
        return min(base_score, 1.0)
    
    def _categorize_differences(self, differences: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize differences by type and severity"""
        categories = {
            'critical': [],
            'important': [],
            'minor': [],
            'spec_changes': [],
            'metadata_changes': [],
            'structural_changes': []
        }
        
        for diff in differences:
            severity = diff.get('severity', 'medium')
            path = diff.get('path', '')
            diff_type = diff.get('type', 'unknown')
            
            # By severity
            if severity == 'high':
                categories['critical'].append(diff)
            elif severity == 'medium':
                categories['important'].append(diff)
            else:
                categories['minor'].append(diff)
            
            # By location
            if path.startswith('spec.'):
                categories['spec_changes'].append(diff)
            elif path.startswith('metadata.'):
                categories['metadata_changes'].append(diff)
            
            # By type
            if diff_type in ['type_mismatch', 'missing_key_actual', 'extra_key_actual']:
                categories['structural_changes'].append(diff)
        
        return categories
    
    def _generate_drift_summary(self, categorized_diffs: Dict[str, List]) -> str:
        """Generate a human-readable summary of the drift"""
        critical = len(categorized_diffs['critical'])
        important = len(categorized_diffs['important'])
        minor = len(categorized_diffs['minor'])
        
        if critical > 0:
            return f"Critical drift detected: {critical} critical, {important} important, {minor} minor differences"
        elif important > 0:
            return f"Important drift detected: {important} important, {minor} minor differences"
        elif minor > 0:
            return f"Minor drift detected: {minor} minor differences"
        else:
            return "No significant drift detected"
    
    def _generate_recommendations(self, categorized_diffs: Dict[str, List]) -> List[str]:
        """Generate recommendations for resolving drift"""
        recommendations = []
        
        if categorized_diffs['critical']:
            recommendations.append("Immediate action required: Critical spec differences detected")
        
        if categorized_diffs['spec_changes']:
            recommendations.append("Review spec changes carefully before applying")
        
        if categorized_diffs['structural_changes']:
            recommendations.append("Structural changes detected - validate resource compatibility")
        
        if len(categorized_diffs['minor']) > 10:
            recommendations.append("Consider bulk update for many minor differences")
        
        if not recommendations:
            recommendations.append("Drift is minor - consider scheduled sync")
        
        return recommendations
    
    def _no_drift_result(self) -> Dict[str, Any]:
        """Return result for no drift detected"""
        return {
            'has_drift': False,
            'drift_score': 0.0,
            'total_differences': 0,
            'differences': [],
            'summary': 'Resources are in sync'
        }
    
    def _desired_only_result(self, desired: Dict[str, Any]) -> Dict[str, Any]:
        """Return result for resource only in desired state"""
        return {
            'has_drift': True,
            'drift_score': 1.0,
            'total_differences': 1,
            'differences': [{
                'type': 'missing_actual_resource',
                'severity': 'high',
                'desired': desired
            }],
            'summary': 'Resource exists in Git but not in cluster'
        }
    
    def _actual_only_result(self, actual: Dict[str, Any]) -> Dict[str, Any]:
        """Return result for resource only in actual state"""
        return {
            'has_drift': True,
            'drift_score': 1.0,
            'total_differences': 1,
            'differences': [{
                'type': 'orphaned_actual_resource',
                'severity': 'high',
                'actual': actual
            }],
            'summary': 'Resource exists in cluster but not in Git'
        }


class DriftAnalyzer:
    """
    High-level drift analysis coordinator.
    Provides aggregated analysis across multiple resources and fabrics.
    """
    
    def __init__(self):
        self.detector = DriftDetector()
    
    def analyze_fabric_drift(self, fabric) -> Dict[str, Any]:
        """
        Analyze drift across all resources in a fabric.
        
        Args:
            fabric: HedgehogFabric instance
            
        Returns:
            Comprehensive fabric drift analysis
        """
        from ..models import HedgehogResource
        
        resources = HedgehogResource.objects.filter(fabric=fabric)
        
        analysis = {
            'fabric': fabric.name,
            'total_resources': resources.count(),
            'analysis_time': datetime.now().isoformat(),
            'drift_summary': {
                'in_sync': 0,
                'has_drift': 0,
                'critical_drift': 0,
                'avg_drift_score': 0.0
            },
            'by_kind': {},
            'by_severity': {'high': 0, 'medium': 0, 'low': 0},
            'recommendations': []
        }
        
        total_drift_score = 0.0
        drift_scores = []
        
        for resource in resources:
            try:
                # Get current drift analysis or calculate it
                if resource.drift_details and resource.last_drift_check:
                    # Use cached result if recent
                    time_since_check = datetime.now() - resource.last_drift_check.replace(tzinfo=None)
                    if time_since_check.total_seconds() < 300:  # 5 minutes
                        drift_result = resource.drift_details
                    else:
                        drift_result = self._analyze_resource_drift(resource)
                else:
                    drift_result = self._analyze_resource_drift(resource)
                
                # Update analysis
                if drift_result.get('has_drift', False):
                    analysis['drift_summary']['has_drift'] += 1
                    drift_score = drift_result.get('drift_score', 0.0)
                    drift_scores.append(drift_score)
                    total_drift_score += drift_score
                    
                    # Count by severity
                    categorized = drift_result.get('categorized_differences', {})
                    if categorized.get('critical'):
                        analysis['drift_summary']['critical_drift'] += 1
                        analysis['by_severity']['high'] += len(categorized['critical'])
                    analysis['by_severity']['medium'] += len(categorized.get('important', []))
                    analysis['by_severity']['low'] += len(categorized.get('minor', []))
                else:
                    analysis['drift_summary']['in_sync'] += 1
                
                # Count by kind
                kind = resource.kind
                if kind not in analysis['by_kind']:
                    analysis['by_kind'][kind] = {
                        'total': 0,
                        'in_sync': 0,
                        'drifted': 0,
                        'avg_drift_score': 0.0
                    }
                
                analysis['by_kind'][kind]['total'] += 1
                if drift_result.get('has_drift', False):
                    analysis['by_kind'][kind]['drifted'] += 1
                else:
                    analysis['by_kind'][kind]['in_sync'] += 1
                
            except Exception as e:
                logger.error(f"Failed to analyze drift for resource {resource}: {e}")
        
        # Calculate averages
        if drift_scores:
            analysis['drift_summary']['avg_drift_score'] = sum(drift_scores) / len(drift_scores)
        
        # Generate fabric-level recommendations
        analysis['recommendations'] = self._generate_fabric_recommendations(analysis)
        
        return analysis
    
    def _analyze_resource_drift(self, resource) -> Dict[str, Any]:
        """Analyze drift for a single resource"""
        try:
            drift_result = self.detector.detect_drift(
                resource.desired_spec or {},
                resource.actual_spec or {}
            )
            
            # Update resource with latest drift analysis
            resource.drift_details = drift_result
            resource.drift_score = drift_result.get('drift_score', 0.0)
            
            if drift_result.get('has_drift', False):
                resource.drift_status = 'spec_drift'
            else:
                resource.drift_status = 'in_sync'
            
            resource.last_drift_check = datetime.now()
            resource.save(update_fields=['drift_details', 'drift_score', 'drift_status', 'last_drift_check'])
            
            return drift_result
            
        except Exception as e:
            logger.error(f"Drift analysis failed for resource {resource}: {e}")
            return {
                'has_drift': False,
                'error': str(e),
                'drift_score': 0.0
            }
    
    def _generate_fabric_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on fabric-wide analysis"""
        recommendations = []
        
        total = analysis['total_resources']
        drifted = analysis['drift_summary']['has_drift']
        critical = analysis['drift_summary']['critical_drift']
        
        if total == 0:
            recommendations.append("No resources found - consider running initial sync")
            return recommendations
        
        drift_percentage = (drifted / total) * 100
        
        if critical > 0:
            recommendations.append(f"URGENT: {critical} resources have critical drift - immediate attention required")
        
        if drift_percentage > 50:
            recommendations.append("High drift detected - consider full fabric resync")
        elif drift_percentage > 20:
            recommendations.append("Moderate drift detected - schedule sync soon")
        elif drift_percentage > 5:
            recommendations.append("Low drift detected - monitor and sync as needed")
        else:
            recommendations.append("Fabric is mostly in sync - minimal action required")
        
        # Kind-specific recommendations
        for kind, stats in analysis['by_kind'].items():
            if stats['total'] > 0:
                kind_drift_pct = (stats['drifted'] / stats['total']) * 100
                if kind_drift_pct > 75:
                    recommendations.append(f"Consider focused sync for {kind} resources")
        
        return recommendations


# Convenience functions for easy access
def detect_resource_drift(desired_spec: Dict, actual_spec: Dict) -> Dict[str, Any]:
    """Convenience function for single resource drift detection"""
    detector = DriftDetector()
    return detector.detect_drift(desired_spec, actual_spec)


def analyze_fabric_drift(fabric) -> Dict[str, Any]:
    """Convenience function for fabric-wide drift analysis"""
    analyzer = DriftAnalyzer()
    return analyzer.analyze_fabric_drift(fabric)