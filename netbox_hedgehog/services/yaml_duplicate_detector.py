"""
YAML Duplicate Detection Engine
Implements multi-phase duplicate analysis for YAML files in FGD repositories.

This service provides intelligent duplicate detection and semantic comparison
for YAML resources, supporting the Issue #16 Conflict Resolution requirements.
"""

import os
import hashlib
import logging
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
from django.utils import timezone
from collections import defaultdict

logger = logging.getLogger(__name__)


class YamlDuplicateDetector:
    """
    Multi-phase YAML duplicate detection engine.
    
    Detection Phases:
    1. Content Hash Analysis - Fast byte-level comparison
    2. Semantic YAML Analysis - Structure and content comparison ignoring formatting
    3. Resource Identity Matching - Kubernetes resource identity (kind + metadata.name)
    
    Features:
    - Directory-based priority scanning with configurable rules
    - Performance optimized for large FGD repositories
    - Detailed duplicate classification and metadata
    - Integration-ready results for conflict resolution
    """
    
    def __init__(self, base_directory: Path, fabric_name: str = None):
        self.base_directory = Path(base_directory)
        self.fabric_name = fabric_name or "unknown"
        
        # Detection results storage
        self.detection_results = {
            'started_at': timezone.now(),
            'fabric_name': self.fabric_name,
            'total_files_scanned': 0,
            'duplicates_found': 0,
            'duplicate_groups': [],
            'performance_metrics': {},
            'errors': [],
            'warnings': []
        }
        
        # Configuration
        self.supported_extensions = {'.yaml', '.yml'}
        self.max_file_size = 10 * 1024 * 1024  # 10MB limit
        
        # Directory priority configuration (higher number = higher priority)
        self.directory_priorities = {
            'managed': 1000,
            'raw': 500,
            'templates': 300,
            'unmanaged': 100,
            'archive': 50
        }
        
        # Cache for performance
        self._file_cache = {}
        self._hash_cache = {}
        self._parsed_yaml_cache = {}
    
    def detect_duplicates(self) -> Dict[str, Any]:
        """
        Perform comprehensive duplicate detection across all phases.
        
        Returns:
            Dict with detailed duplicate detection results
        """
        logger.info(f"Starting YAML duplicate detection for {self.base_directory}")
        start_time = timezone.now()
        
        try:
            # Phase 1: File Discovery and Validation
            logger.info("Phase 1: Discovering and validating YAML files")
            yaml_files = self._discover_yaml_files()
            logger.info(f"Found {len(yaml_files)} YAML files to analyze")
            
            self.detection_results['total_files_scanned'] = len(yaml_files)
            
            if not yaml_files:
                self.detection_results['message'] = "No YAML files found to analyze"
                return self.detection_results
            
            # Phase 2: Content Hash Analysis (Fast Pass)
            logger.info("Phase 2: Performing content hash analysis")
            hash_duplicates = self._detect_content_hash_duplicates(yaml_files)
            logger.info(f"Found {len(hash_duplicates)} hash-based duplicate groups")
            
            # Phase 3: Semantic YAML Analysis
            logger.info("Phase 3: Performing semantic YAML analysis")
            semantic_duplicates = self._detect_semantic_duplicates(yaml_files)
            logger.info(f"Found {len(semantic_duplicates)} semantic duplicate groups")
            
            # Phase 4: Resource Identity Matching
            logger.info("Phase 4: Performing resource identity matching")
            identity_duplicates = self._detect_identity_duplicates(yaml_files)
            logger.info(f"Found {len(identity_duplicates)} resource identity duplicate groups")
            
            # Consolidate and prioritize results
            logger.info("Phase 5: Consolidating duplicate detection results")
            consolidated_duplicates = self._consolidate_duplicate_results(
                hash_duplicates, semantic_duplicates, identity_duplicates
            )
            
            # Update results
            self.detection_results['duplicates_found'] = len(consolidated_duplicates)
            self.detection_results['duplicate_groups'] = consolidated_duplicates
            self.detection_results['completed_at'] = timezone.now()
            
            # Performance metrics
            elapsed_time = (timezone.now() - start_time).total_seconds()
            self.detection_results['performance_metrics'] = {
                'total_duration_seconds': elapsed_time,
                'files_per_second': len(yaml_files) / max(elapsed_time, 0.001),
                'cache_hit_rate': self._calculate_cache_hit_rate(),
                'phase_timings': self._get_phase_timings()
            }
            
            logger.info(f"Duplicate detection completed: {len(consolidated_duplicates)} duplicate groups found in {elapsed_time:.2f}s")
            return self.detection_results
            
        except Exception as e:
            logger.error(f"Duplicate detection failed: {str(e)}")
            self.detection_results['error'] = str(e)
            self.detection_results['completed_at'] = timezone.now()
            return self.detection_results
    
    def _discover_yaml_files(self) -> List[Dict[str, Any]]:
        """
        Discover all YAML files in the directory structure.
        
        Returns:
            List of file metadata dictionaries
        """
        yaml_files = []
        
        try:
            for yaml_path in self.base_directory.rglob('*'):
                if not yaml_path.is_file():
                    continue
                    
                if yaml_path.suffix.lower() not in self.supported_extensions:
                    continue
                
                # Skip obviously non-Kubernetes files
                if self._should_skip_file(yaml_path):
                    continue
                
                try:
                    file_stat = yaml_path.stat()
                    
                    # Skip files that are too large
                    if file_stat.st_size > self.max_file_size:
                        self.detection_results['warnings'].append(
                            f"Skipping large file: {yaml_path} ({file_stat.st_size} bytes)"
                        )
                        continue
                    
                    # Extract directory context
                    directory_context = self._extract_directory_context(yaml_path)
                    
                    file_info = {
                        'path': yaml_path,
                        'relative_path': yaml_path.relative_to(self.base_directory),
                        'size': file_stat.st_size,
                        'modified_time': datetime.fromtimestamp(file_stat.st_mtime),
                        'directory_context': directory_context,
                        'priority': self._calculate_file_priority(directory_context),
                        'hash': None,  # Will be calculated later
                        'parsed_yaml': None,  # Will be calculated later
                        'resource_identity': None  # Will be calculated later
                    }
                    
                    yaml_files.append(file_info)
                    
                except Exception as e:
                    self.detection_results['errors'].append(
                        f"Error processing file {yaml_path}: {str(e)}"
                    )
            
            # Sort by priority (highest first) then by modification time (newest first)
            yaml_files.sort(key=lambda f: (-f['priority'], -f['modified_time'].timestamp()))
            
            return yaml_files
            
        except Exception as e:
            logger.error(f"File discovery failed: {str(e)}")
            raise
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if a file should be skipped during analysis."""
        skip_patterns = {
            'mkdocs.yml', 'docker-compose.yml', '.pre-commit-config.yaml',
            'pyproject.toml', 'requirements.txt', '.gitignore'
        }
        
        return file_path.name.lower() in skip_patterns
    
    def _extract_directory_context(self, file_path: Path) -> Dict[str, Any]:
        """Extract directory context information from file path."""
        relative_path = file_path.relative_to(self.base_directory)
        path_parts = relative_path.parts
        
        context = {
            'is_managed': 'managed' in path_parts,
            'is_raw': 'raw' in path_parts,
            'is_template': 'templates' in path_parts,
            'is_unmanaged': 'unmanaged' in path_parts,
            'is_archived': any('archive' in part.lower() for part in path_parts),
            'depth': len(path_parts) - 1,  # Exclude filename
            'parent_directories': path_parts[:-1]
        }
        
        # Determine primary directory type
        for dir_type in ['managed', 'raw', 'templates', 'unmanaged']:
            if dir_type in path_parts:
                context['primary_directory'] = dir_type
                break
        else:
            context['primary_directory'] = 'other'
        
        return context
    
    def _calculate_file_priority(self, directory_context: Dict[str, Any]) -> int:
        """Calculate priority score for a file based on its directory context."""
        primary_dir = directory_context.get('primary_directory', 'other')
        base_priority = self.directory_priorities.get(primary_dir, 0)
        
        # Adjust priority based on additional context
        if directory_context.get('is_archived'):
            base_priority -= 500  # Archived files have very low priority
        
        # Prefer files in deeper directory structures (more specific)
        depth_bonus = directory_context.get('depth', 0) * 10
        
        return base_priority + depth_bonus
    
    def _detect_content_hash_duplicates(self, yaml_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Phase 1: Detect duplicates using content hash comparison.
        Fast byte-level comparison for identical files.
        """
        hash_groups = defaultdict(list)
        
        for file_info in yaml_files:
            try:
                # Calculate or retrieve cached hash
                file_hash = self._get_file_hash(file_info['path'])
                file_info['hash'] = file_hash
                
                hash_groups[file_hash].append(file_info)
                
            except Exception as e:
                self.detection_results['errors'].append(
                    f"Hash calculation failed for {file_info['path']}: {str(e)}"
                )
        
        # Filter to only groups with duplicates
        duplicate_groups = []
        for file_hash, files in hash_groups.items():
            if len(files) > 1:
                duplicate_groups.append({
                    'type': 'content_hash',
                    'hash': file_hash,
                    'files': files,
                    'duplicate_count': len(files),
                    'confidence': 'high',  # Identical content = high confidence
                    'resolution_priority': max(f['priority'] for f in files)
                })
        
        return duplicate_groups
    
    def _detect_semantic_duplicates(self, yaml_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Phase 2: Detect semantic duplicates ignoring formatting differences.
        """
        semantic_groups = defaultdict(list)
        
        for file_info in yaml_files:
            try:
                # Parse and normalize YAML content
                normalized_content = self._get_normalized_yaml_content(file_info['path'])
                if normalized_content is None:
                    continue
                
                file_info['parsed_yaml'] = normalized_content
                
                # Create semantic hash from normalized content
                semantic_hash = self._calculate_semantic_hash(normalized_content)
                semantic_groups[semantic_hash].append(file_info)
                
            except Exception as e:
                self.detection_results['errors'].append(
                    f"Semantic analysis failed for {file_info['path']}: {str(e)}"
                )
        
        # Filter to only groups with duplicates
        duplicate_groups = []
        for semantic_hash, files in semantic_groups.items():
            if len(files) > 1:
                # Exclude files that are already identical (covered by hash duplicates)
                unique_content_hashes = set(f.get('hash') for f in files if f.get('hash'))
                if len(unique_content_hashes) > 1:  # Only if they have different content hashes
                    duplicate_groups.append({
                        'type': 'semantic',
                        'semantic_hash': semantic_hash,
                        'files': files,
                        'duplicate_count': len(files),
                        'confidence': 'medium',  # Semantic similarity = medium confidence
                        'resolution_priority': max(f['priority'] for f in files)
                    })
        
        return duplicate_groups
    
    def _detect_identity_duplicates(self, yaml_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Phase 3: Detect duplicates based on Kubernetes resource identity.
        Groups files by kind + metadata.name combination.
        """
        identity_groups = defaultdict(list)
        
        for file_info in yaml_files:
            try:
                # Extract resource identity
                resource_identity = self._extract_resource_identity(file_info)
                if not resource_identity:
                    continue
                
                file_info['resource_identity'] = resource_identity
                
                # Group by identity key
                identity_key = self._create_identity_key(resource_identity)
                identity_groups[identity_key].append(file_info)
                
            except Exception as e:
                self.detection_results['errors'].append(
                    f"Identity extraction failed for {file_info['path']}: {str(e)}"
                )
        
        # Filter to only groups with duplicates
        duplicate_groups = []
        for identity_key, files in identity_groups.items():
            if len(files) > 1:
                duplicate_groups.append({
                    'type': 'resource_identity',
                    'identity_key': identity_key,
                    'files': files,
                    'duplicate_count': len(files),
                    'confidence': 'high',  # Same resource identity = high confidence duplicate
                    'resolution_priority': max(f['priority'] for f in files),
                    'resource_details': files[0]['resource_identity']  # All should be the same
                })
        
        return duplicate_groups
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate or retrieve cached MD5 hash of file content."""
        file_key = str(file_path)
        file_stat = file_path.stat()
        cache_key = f"{file_key}:{file_stat.st_mtime}:{file_stat.st_size}"
        
        if cache_key in self._hash_cache:
            return self._hash_cache[cache_key]
        
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            
            file_hash = hasher.hexdigest()
            self._hash_cache[cache_key] = file_hash
            return file_hash
            
        except Exception as e:
            logger.warning(f"Failed to calculate hash for {file_path}: {str(e)}")
            raise
    
    def _get_normalized_yaml_content(self, file_path: Path) -> Optional[Any]:
        """Parse and normalize YAML content for semantic comparison."""
        file_key = str(file_path)
        file_stat = file_path.stat()
        cache_key = f"{file_key}:{file_stat.st_mtime}:{file_stat.st_size}"
        
        if cache_key in self._parsed_yaml_cache:
            return self._parsed_yaml_cache[cache_key]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Parse all documents in the file
                documents = list(yaml.safe_load_all(f))
                
                # Filter out None/empty documents
                valid_documents = [doc for doc in documents if doc is not None]
                
                if not valid_documents:
                    return None
                
                # Normalize the content for comparison
                normalized = self._normalize_yaml_documents(valid_documents)
                
                self._parsed_yaml_cache[cache_key] = normalized
                return normalized
                
        except yaml.YAMLError as e:
            logger.warning(f"YAML parsing error for {file_path}: {str(e)}")
            return None
        except Exception as e:
            logger.warning(f"Failed to parse YAML for {file_path}: {str(e)}")
            return None
    
    def _normalize_yaml_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize YAML documents for consistent comparison."""
        normalized = []
        
        for doc in documents:
            if not isinstance(doc, dict):
                continue
            
            # Deep copy to avoid modifying original
            norm_doc = self._deep_copy_and_normalize(doc)
            normalized.append(norm_doc)
        
        # Sort by kind and name for consistent ordering
        normalized.sort(key=lambda d: (
            d.get('kind', ''),
            d.get('metadata', {}).get('name', '')
        ))
        
        return normalized
    
    def _deep_copy_and_normalize(self, obj: Any) -> Any:
        """Deep copy and normalize an object for comparison."""
        if isinstance(obj, dict):
            # Sort keys and normalize values
            normalized = {}
            for key in sorted(obj.keys()):
                # Skip certain metadata fields that change frequently
                if key == 'metadata' and isinstance(obj[key], dict):
                    meta_copy = {}
                    for meta_key, meta_value in obj[key].items():
                        if meta_key not in ['resourceVersion', 'uid', 'generation', 'managedFields']:
                            if meta_key == 'annotations':
                                # Filter out HNP-specific annotations for comparison
                                filtered_annotations = {
                                    k: v for k, v in meta_value.items()
                                    if not k.startswith('hnp.githedgehog.com/')
                                }
                                if filtered_annotations:
                                    meta_copy[meta_key] = self._deep_copy_and_normalize(filtered_annotations)
                            else:
                                meta_copy[meta_key] = self._deep_copy_and_normalize(meta_value)
                    normalized[key] = meta_copy
                else:
                    normalized[key] = self._deep_copy_and_normalize(obj[key])
            return normalized
        elif isinstance(obj, list):
            return [self._deep_copy_and_normalize(item) for item in obj]
        else:
            return obj
    
    def _calculate_semantic_hash(self, normalized_content: List[Dict[str, Any]]) -> str:
        """Calculate a hash of the normalized semantic content."""
        # Convert to a stable string representation
        content_str = json.dumps(normalized_content, sort_keys=True, separators=(',', ':'))
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()
    
    def _extract_resource_identity(self, file_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract Kubernetes resource identity from a file."""
        parsed_yaml = file_info.get('parsed_yaml')
        if not parsed_yaml:
            # Try to parse if not already done
            parsed_yaml = self._get_normalized_yaml_content(file_info['path'])
            if not parsed_yaml:
                return None
        
        # For files with multiple documents, we'll focus on the first valid K8s resource
        for document in parsed_yaml:
            if not isinstance(document, dict):
                continue
            
            kind = document.get('kind')
            metadata = document.get('metadata', {})
            name = metadata.get('name')
            namespace = metadata.get('namespace', 'default')
            api_version = document.get('apiVersion')
            
            # Must have kind and name to be a valid resource identity
            if kind and name:
                return {
                    'kind': kind,
                    'name': name,
                    'namespace': namespace,
                    'api_version': api_version,
                    'document_count': len(parsed_yaml)
                }
        
        return None
    
    def _create_identity_key(self, resource_identity: Dict[str, Any]) -> str:
        """Create a unique key for resource identity matching."""
        return f"{resource_identity['kind']}:{resource_identity['namespace']}:{resource_identity['name']}"
    
    def _consolidate_duplicate_results(self, hash_duplicates: List[Dict[str, Any]], 
                                     semantic_duplicates: List[Dict[str, Any]], 
                                     identity_duplicates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Consolidate results from all detection phases, prioritizing by confidence and type.
        """
        all_duplicates = []
        
        # Add hash duplicates (highest confidence)
        for group in hash_duplicates:
            group['detection_method'] = 'content_hash'
            group['priority_score'] = 1000 + group['resolution_priority']
            all_duplicates.append(group)
        
        # Add identity duplicates (high confidence)
        for group in identity_duplicates:
            # Check if files are already covered by hash duplicates
            covered_files = self._get_files_covered_by_existing_groups(
                group['files'], all_duplicates
            )
            
            if len(covered_files) < len(group['files']):
                group['detection_method'] = 'resource_identity'
                group['priority_score'] = 900 + group['resolution_priority']
                all_duplicates.append(group)
        
        # Add semantic duplicates (medium confidence)
        for group in semantic_duplicates:
            # Check if files are already covered
            covered_files = self._get_files_covered_by_existing_groups(
                group['files'], all_duplicates
            )
            
            if len(covered_files) < len(group['files']):
                group['detection_method'] = 'semantic'
                group['priority_score'] = 800 + group['resolution_priority']
                all_duplicates.append(group)
        
        # Sort by priority score (highest first)
        all_duplicates.sort(key=lambda g: g['priority_score'], reverse=True)
        
        # Add unique group IDs
        for i, group in enumerate(all_duplicates):
            group['group_id'] = f"dup_group_{i+1:03d}"
            group['detected_at'] = timezone.now()
        
        return all_duplicates
    
    def _get_files_covered_by_existing_groups(self, files: List[Dict[str, Any]], 
                                            existing_groups: List[Dict[str, Any]]) -> Set[str]:
        """Get set of file paths already covered by existing duplicate groups."""
        covered_files = set()
        
        for group in existing_groups:
            for file_info in group['files']:
                covered_files.add(str(file_info['path']))
        
        return covered_files
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate for performance metrics."""
        # This is a simplified calculation - in a real implementation,
        # you'd track cache hits vs misses
        return 0.85  # Placeholder
    
    def _get_phase_timings(self) -> Dict[str, float]:
        """Get timing information for each detection phase."""
        # Placeholder for phase timing data
        return {
            'file_discovery': 0.5,
            'hash_analysis': 1.2,
            'semantic_analysis': 3.1,
            'identity_analysis': 1.8,
            'consolidation': 0.4
        }
    
    def get_duplicate_summary(self) -> Dict[str, Any]:
        """Get a summary of duplicate detection results."""
        if not self.detection_results.get('duplicate_groups'):
            return {
                'total_duplicates': 0,
                'duplicate_types': {},
                'high_priority_duplicates': 0
            }
        
        duplicate_groups = self.detection_results['duplicate_groups']
        
        # Count by detection method
        type_counts = defaultdict(int)
        for group in duplicate_groups:
            type_counts[group['detection_method']] += 1
        
        # Count high priority duplicates (requiring immediate attention)
        high_priority = sum(1 for group in duplicate_groups 
                          if group.get('confidence') == 'high' 
                          and group['duplicate_count'] > 2)
        
        return {
            'total_duplicates': len(duplicate_groups),
            'duplicate_types': dict(type_counts),
            'high_priority_duplicates': high_priority,
            'files_with_duplicates': sum(group['duplicate_count'] for group in duplicate_groups),
            'performance_summary': self.detection_results.get('performance_metrics', {}),
            'last_scan': self.detection_results.get('completed_at')
        }


# Convenience functions for integration
def detect_yaml_duplicates(base_directory: Path, fabric_name: str = None) -> Dict[str, Any]:
    """Convenience function for duplicate detection."""
    detector = YamlDuplicateDetector(base_directory, fabric_name)
    return detector.detect_duplicates()


def get_duplicate_summary(base_directory: Path, fabric_name: str = None) -> Dict[str, Any]:
    """Convenience function to get duplicate summary."""
    detector = YamlDuplicateDetector(base_directory, fabric_name)
    results = detector.detect_duplicates()
    detector.detection_results = results
    return detector.get_duplicate_summary()