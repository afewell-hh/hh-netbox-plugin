"""
Conflict Resolution Engine
Implements CEO-specified resolution hierarchy for duplicate YAML files.

This service provides intelligent conflict resolution with automated strategies
based on the Issue #16 requirements and directory-based priority rules.
"""

import os
import shutil
import logging
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from django.utils import timezone
from enum import Enum

from .yaml_duplicate_detector import YamlDuplicateDetector
from .git_file_manager import GitFileManager

logger = logging.getLogger(__name__)


class ResolutionStrategy(Enum):
    """Enumeration of conflict resolution strategies."""
    DELETE_DUPLICATE = "delete_duplicate"
    COMMENT_OUT = "comment_out"
    MOVE_TO_UNMANAGED = "move_to_unmanaged"
    PRESERVE_MANAGED = "preserve_managed"
    PREFER_RAW = "prefer_raw"
    PRESERVE_HNP_ANNOTATED = "preserve_hnp_annotated"
    MANUAL_REVIEW = "manual_review"


class ConflictResolutionEngine:
    """
    Intelligent conflict resolution engine implementing CEO-specified hierarchy.
    
    CEO-Specified Resolution Hierarchy (from Issue #16):
    1. Identical files: Delete one intelligently based on directory priority
    2. Different files, one in /managed/: Preserve managed, comment out non-managed
    3. Neither in /managed/: Prefer /raw/ directory files
    4. Both in /managed/: Preserve HNP-annotated file, move other to /unmanaged/
    5. Fallback: Comment out newer file, move to /unmanaged/
    
    Features:
    - Automated conflict resolution with safety measures
    - File operation coordination (comment/move/archive)
    - Post-resolution integrity validation
    - Detailed resolution audit trail
    """
    
    def __init__(self, fabric, base_directory: Path):
        self.fabric = fabric
        self.base_directory = Path(base_directory)
        self.git_file_manager = GitFileManager(fabric)
        
        # Resolution results tracking
        self.resolution_results = {
            'started_at': timezone.now(),
            'fabric_name': fabric.name if fabric else 'unknown',
            'conflicts_processed': 0,
            'conflicts_resolved': 0,
            'conflicts_requiring_manual_review': 0,
            'resolutions': [],
            'errors': [],
            'warnings': []
        }
        
        # Configuration
        self.backup_enabled = True
        self.dry_run = False  # Set to True to simulate without making changes
        self.max_conflicts_per_batch = 50  # Process conflicts in batches
        
        # Resolution strategy counters
        self.strategy_usage = {strategy: 0 for strategy in ResolutionStrategy}
        
        # Safety thresholds
        self.max_files_to_delete = 100
        self.max_files_to_move = 200
        self.deleted_files_count = 0
        self.moved_files_count = 0
    
    def resolve_conflicts(self, duplicate_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Resolve conflicts using CEO-specified hierarchy.
        
        Args:
            duplicate_groups: List of duplicate groups from YamlDuplicateDetector
            
        Returns:
            Dict with resolution results and audit trail
        """
        logger.info(f"Starting conflict resolution for {len(duplicate_groups)} duplicate groups")
        
        try:
            # Pre-resolution validation
            if not self._validate_preconditions(duplicate_groups):
                raise Exception("Pre-resolution validation failed")
            
            # Process conflicts in batches for performance
            batches = self._create_conflict_batches(duplicate_groups)
            
            for batch_num, batch in enumerate(batches, 1):
                logger.info(f"Processing conflict batch {batch_num}/{len(batches)} ({len(batch)} conflicts)")
                
                batch_results = self._process_conflict_batch(batch)
                self.resolution_results['resolutions'].extend(batch_results)
            
            # Post-resolution validation and cleanup
            self._post_resolution_validation()
            
            # Update final results
            self.resolution_results['completed_at'] = timezone.now()
            self.resolution_results['conflicts_processed'] = len(duplicate_groups)
            self.resolution_results['conflicts_resolved'] = len([
                r for r in self.resolution_results['resolutions'] 
                if r['status'] == 'resolved'
            ])
            self.resolution_results['conflicts_requiring_manual_review'] = len([
                r for r in self.resolution_results['resolutions'] 
                if r['status'] == 'manual_review_required'
            ])
            
            # Add strategy usage statistics
            self.resolution_results['strategy_usage'] = {
                strategy.value: count for strategy, count in self.strategy_usage.items()
            }
            
            logger.info(f"Conflict resolution completed: "
                       f"{self.resolution_results['conflicts_resolved']}/{len(duplicate_groups)} resolved")
            
            return self.resolution_results
            
        except Exception as e:
            logger.error(f"Conflict resolution failed: {str(e)}")
            self.resolution_results['error'] = str(e)
            self.resolution_results['completed_at'] = timezone.now()
            return self.resolution_results
    
    def resolve_single_conflict(self, duplicate_group: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve a single conflict group using the resolution hierarchy.
        
        Args:
            duplicate_group: Single duplicate group from detection
            
        Returns:
            Dict with resolution result
        """
        group_id = duplicate_group.get('group_id', 'unknown')
        files = duplicate_group.get('files', [])
        
        logger.info(f"Resolving conflict group {group_id} with {len(files)} files")
        
        resolution = {
            'group_id': group_id,
            'started_at': timezone.now(),
            'status': 'processing',
            'strategy': None,
            'actions_taken': [],
            'files_affected': [],
            'error': None
        }
        
        try:
            # Apply CEO-specified resolution hierarchy
            strategy, actions = self._determine_resolution_strategy(duplicate_group)
            
            resolution['strategy'] = strategy.value
            logger.info(f"Selected strategy {strategy.value} for group {group_id}")
            
            if strategy == ResolutionStrategy.MANUAL_REVIEW:
                resolution['status'] = 'manual_review_required'
                resolution['reason'] = 'Complex conflict requiring manual intervention'
                return resolution
            
            # Execute resolution actions
            if not self.dry_run:
                for action in actions:
                    try:
                        result = self._execute_resolution_action(action)
                        resolution['actions_taken'].append(result)
                        resolution['files_affected'].extend(result.get('files_affected', []))
                        
                    except Exception as action_error:
                        logger.error(f"Action execution failed for group {group_id}: {str(action_error)}")
                        resolution['errors'] = resolution.get('errors', [])
                        resolution['errors'].append(str(action_error))
            else:
                # Dry run - just log what would be done
                for action in actions:
                    logger.info(f"[DRY RUN] Would execute: {action}")
                    resolution['actions_taken'].append({
                        'action': action['type'],
                        'dry_run': True,
                        'description': action.get('description', '')
                    })
            
            # Mark as resolved if no errors
            if not resolution.get('errors'):
                resolution['status'] = 'resolved'
                self.strategy_usage[strategy] += 1
            else:
                resolution['status'] = 'failed'
            
            resolution['completed_at'] = timezone.now()
            return resolution
            
        except Exception as e:
            logger.error(f"Resolution failed for group {group_id}: {str(e)}")
            resolution['status'] = 'failed'
            resolution['error'] = str(e)
            resolution['completed_at'] = timezone.now()
            return resolution
    
    def _validate_preconditions(self, duplicate_groups: List[Dict[str, Any]]) -> bool:
        """Validate preconditions before starting conflict resolution."""
        try:
            # Check if base directory exists and is writable
            if not self.base_directory.exists():
                logger.error(f"Base directory does not exist: {self.base_directory}")
                return False
            
            # Test write permissions
            test_file = self.base_directory / '.write_test'
            try:
                test_file.touch()
                test_file.unlink()
            except Exception:
                logger.error(f"No write permission for directory: {self.base_directory}")
                return False
            
            # Validate duplicate groups structure
            for group in duplicate_groups:
                if not isinstance(group.get('files'), list):
                    logger.error(f"Invalid duplicate group structure: {group.get('group_id', 'unknown')}")
                    return False
                
                if len(group.get('files', [])) < 2:
                    logger.warning(f"Group has less than 2 files: {group.get('group_id', 'unknown')}")
            
            # Check safety thresholds
            total_files = sum(len(group.get('files', [])) for group in duplicate_groups)
            if total_files > 1000:
                logger.warning(f"Large number of files to process: {total_files}")
            
            return True
            
        except Exception as e:
            logger.error(f"Precondition validation failed: {str(e)}")
            return False
    
    def _create_conflict_batches(self, duplicate_groups: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Create batches of conflicts for processing."""
        batches = []
        current_batch = []
        
        for group in duplicate_groups:
            current_batch.append(group)
            
            if len(current_batch) >= self.max_conflicts_per_batch:
                batches.append(current_batch)
                current_batch = []
        
        # Add remaining conflicts
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _process_conflict_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of conflicts."""
        batch_results = []
        
        for duplicate_group in batch:
            try:
                result = self.resolve_single_conflict(duplicate_group)
                batch_results.append(result)
                
            except Exception as e:
                logger.error(f"Batch processing error for group {duplicate_group.get('group_id', 'unknown')}: {str(e)}")
                batch_results.append({
                    'group_id': duplicate_group.get('group_id', 'unknown'),
                    'status': 'failed',
                    'error': str(e),
                    'completed_at': timezone.now()
                })
        
        return batch_results
    
    def _determine_resolution_strategy(self, duplicate_group: Dict[str, Any]) -> Tuple[ResolutionStrategy, List[Dict[str, Any]]]:
        """
        Determine resolution strategy based on CEO-specified hierarchy.
        
        CEO Hierarchy:
        1. Identical files: Delete one intelligently based on directory priority
        2. Different files, one in /managed/: Preserve managed, comment out non-managed
        3. Neither in /managed/: Prefer /raw/ directory files
        4. Both in /managed/: Preserve HNP-annotated file, move other to /unmanaged/
        5. Fallback: Comment out newer file, move to /unmanaged/
        """
        files = duplicate_group.get('files', [])
        detection_method = duplicate_group.get('detection_method')
        
        # Analyze file locations and properties
        analysis = self._analyze_duplicate_files(files)
        
        # Rule 1: Identical files (content hash match)
        if detection_method == 'content_hash':
            return self._resolve_identical_files(files, analysis)
        
        # Rule 2: Different files, one in /managed/
        if analysis['has_managed'] and not analysis['all_managed']:
            return self._resolve_managed_vs_others(files, analysis)
        
        # Rule 3: Neither in /managed/ - prefer /raw/
        if not analysis['has_managed']:
            return self._resolve_prefer_raw(files, analysis)
        
        # Rule 4: Both in /managed/ - preserve HNP-annotated
        if analysis['all_managed']:
            return self._resolve_managed_conflict(files, analysis)
        
        # Rule 5: Fallback - comment out newer, move to /unmanaged/
        return self._resolve_fallback(files, analysis)
    
    def _analyze_duplicate_files(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze duplicate files to determine resolution approach."""
        analysis = {
            'has_managed': False,
            'has_raw': False,
            'has_unmanaged': False,
            'all_managed': True,
            'hnp_annotated_files': [],
            'newest_file': None,
            'oldest_file': None,
            'highest_priority_file': None
        }
        
        managed_count = 0
        
        for file_info in files:
            directory_context = file_info.get('directory_context', {})
            
            if directory_context.get('is_managed'):
                analysis['has_managed'] = True
                managed_count += 1
            else:
                analysis['all_managed'] = False
            
            if directory_context.get('is_raw'):
                analysis['has_raw'] = True
            
            if directory_context.get('is_unmanaged'):
                analysis['has_unmanaged'] = True
            
            # Check for HNP annotations
            if self._has_hnp_annotations(file_info):
                analysis['hnp_annotated_files'].append(file_info)
            
            # Track newest/oldest files
            modified_time = file_info.get('modified_time')
            if modified_time:
                if not analysis['newest_file'] or modified_time > analysis['newest_file']['modified_time']:
                    analysis['newest_file'] = file_info
                if not analysis['oldest_file'] or modified_time < analysis['oldest_file']['modified_time']:
                    analysis['oldest_file'] = file_info
            
            # Track highest priority file
            priority = file_info.get('priority', 0)
            if not analysis['highest_priority_file'] or priority > analysis['highest_priority_file']['priority']:
                analysis['highest_priority_file'] = file_info
        
        analysis['managed_count'] = managed_count
        analysis['all_managed'] = managed_count == len(files)
        
        return analysis
    
    def _has_hnp_annotations(self, file_info: Dict[str, Any]) -> bool:
        """Check if a file has HNP annotations."""
        try:
            parsed_yaml = file_info.get('parsed_yaml')
            if not parsed_yaml:
                return False
            
            for document in parsed_yaml:
                if not isinstance(document, dict):
                    continue
                
                annotations = document.get('metadata', {}).get('annotations', {})
                for key in annotations:
                    if key.startswith('hnp.githedgehog.com/'):
                        return True
            
            return False
            
        except Exception:
            return False
    
    def _resolve_identical_files(self, files: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Tuple[ResolutionStrategy, List[Dict[str, Any]]]:
        """Rule 1: Delete duplicate based on directory priority."""
        # Keep the highest priority file, delete others
        files_to_keep = [analysis['highest_priority_file']]
        files_to_delete = [f for f in files if f != analysis['highest_priority_file']]
        
        # Safety check
        if self.deleted_files_count + len(files_to_delete) > self.max_files_to_delete:
            logger.warning("Approaching deletion safety limit, requiring manual review")
            return ResolutionStrategy.MANUAL_REVIEW, []
        
        actions = []
        for file_to_delete in files_to_delete:
            actions.append({
                'type': 'delete_file',
                'file_path': file_to_delete['path'],
                'reason': f"Identical content, lower priority than {files_to_keep[0]['relative_path']}",
                'backup': self.backup_enabled
            })
            self.deleted_files_count += 1
        
        return ResolutionStrategy.DELETE_DUPLICATE, actions
    
    def _resolve_managed_vs_others(self, files: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Tuple[ResolutionStrategy, List[Dict[str, Any]]]:
        """Rule 2: Preserve managed, comment out non-managed."""
        managed_files = [f for f in files if f.get('directory_context', {}).get('is_managed')]
        non_managed_files = [f for f in files if not f.get('directory_context', {}).get('is_managed')]
        
        actions = []
        for file_to_comment in non_managed_files:
            actions.append({
                'type': 'comment_out_file',
                'file_path': file_to_comment['path'],
                'reason': 'Non-managed file conflicts with managed version',
                'backup': self.backup_enabled
            })
        
        return ResolutionStrategy.PRESERVE_MANAGED, actions
    
    def _resolve_prefer_raw(self, files: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Tuple[ResolutionStrategy, List[Dict[str, Any]]]:
        """Rule 3: Prefer /raw/ directory files."""
        raw_files = [f for f in files if f.get('directory_context', {}).get('is_raw')]
        other_files = [f for f in files if not f.get('directory_context', {}).get('is_raw')]
        
        actions = []
        
        if raw_files:
            # Keep the highest priority raw file, comment out others
            files_to_keep = [max(raw_files, key=lambda f: f.get('priority', 0))]
            files_to_comment = [f for f in files if f not in files_to_keep]
            
            for file_to_comment in files_to_comment:
                actions.append({
                    'type': 'comment_out_file',
                    'file_path': file_to_comment['path'],
                    'reason': 'Preferring raw directory version',
                    'backup': self.backup_enabled
                })
        else:
            # No raw files, fall back to highest priority
            files_to_keep = [analysis['highest_priority_file']]
            files_to_comment = [f for f in files if f != analysis['highest_priority_file']]
            
            for file_to_comment in files_to_comment:
                actions.append({
                    'type': 'comment_out_file',
                    'file_path': file_to_comment['path'],
                    'reason': 'Lower priority, no raw directory preference',
                    'backup': self.backup_enabled
                })
        
        return ResolutionStrategy.PREFER_RAW, actions
    
    def _resolve_managed_conflict(self, files: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Tuple[ResolutionStrategy, List[Dict[str, Any]]]:
        """Rule 4: Preserve HNP-annotated file, move other to /unmanaged/."""
        hnp_files = analysis['hnp_annotated_files']
        
        actions = []
        
        if len(hnp_files) == 1:
            # Keep the HNP annotated file, move others
            files_to_keep = hnp_files
            files_to_move = [f for f in files if f not in hnp_files]
            
            for file_to_move in files_to_move:
                target_path = self._generate_unmanaged_path(file_to_move['path'])
                actions.append({
                    'type': 'move_file',
                    'file_path': file_to_move['path'],
                    'target_path': target_path,
                    'reason': 'Moving non-HNP annotated managed file to unmanaged',
                    'backup': self.backup_enabled
                })
                self.moved_files_count += 1
        
        elif len(hnp_files) == 0:
            # No HNP annotations, prefer highest priority, move others
            files_to_keep = [analysis['highest_priority_file']]
            files_to_move = [f for f in files if f != analysis['highest_priority_file']]
            
            for file_to_move in files_to_move:
                target_path = self._generate_unmanaged_path(file_to_move['path'])
                actions.append({
                    'type': 'move_file',
                    'file_path': file_to_move['path'],
                    'target_path': target_path,
                    'reason': 'Moving lower priority managed file to unmanaged',
                    'backup': self.backup_enabled
                })
                self.moved_files_count += 1
        
        else:
            # Multiple HNP annotated files - manual review needed
            return ResolutionStrategy.MANUAL_REVIEW, []
        
        # Safety check
        if self.moved_files_count > self.max_files_to_move:
            logger.warning("Approaching move safety limit, requiring manual review")
            return ResolutionStrategy.MANUAL_REVIEW, []
        
        return ResolutionStrategy.PRESERVE_HNP_ANNOTATED, actions
    
    def _resolve_fallback(self, files: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Tuple[ResolutionStrategy, List[Dict[str, Any]]]:
        """Rule 5: Fallback - comment out newer file, move to /unmanaged/."""
        if not analysis['newest_file']:
            return ResolutionStrategy.MANUAL_REVIEW, []
        
        files_to_keep = [analysis['oldest_file']] if analysis['oldest_file'] else [files[0]]
        files_to_process = [f for f in files if f not in files_to_keep]
        
        actions = []
        for file_to_process in files_to_process:
            # Comment out first
            actions.append({
                'type': 'comment_out_file',
                'file_path': file_to_process['path'],
                'reason': 'Fallback strategy: newer file in conflict',
                'backup': self.backup_enabled
            })
            
            # Then move to unmanaged
            target_path = self._generate_unmanaged_path(file_to_process['path'])
            actions.append({
                'type': 'move_file',
                'file_path': file_to_process['path'],
                'target_path': target_path,
                'reason': 'Fallback strategy: moving to unmanaged after commenting',
                'backup': self.backup_enabled
            })
            self.moved_files_count += 1
        
        return ResolutionStrategy.MANUAL_REVIEW if self.moved_files_count > self.max_files_to_move else ResolutionStrategy.COMMENT_OUT, actions
    
    def _generate_unmanaged_path(self, original_path: Path) -> Path:
        """Generate target path in /unmanaged/ directory."""
        original_path = Path(original_path)
        
        # Find the unmanaged directory relative to base
        unmanaged_dir = self.base_directory / 'unmanaged'
        unmanaged_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename in unmanaged
        target_name = original_path.name
        target_path = unmanaged_dir / target_name
        
        counter = 1
        while target_path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            target_name = f"{stem}_conflict_{counter}{suffix}"
            target_path = unmanaged_dir / target_name
            counter += 1
        
        return target_path
    
    def _execute_resolution_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single resolution action."""
        action_type = action['type']
        file_path = Path(action['file_path'])
        
        result = {
            'action': action_type,
            'file_path': str(file_path),
            'started_at': timezone.now(),
            'files_affected': [str(file_path)],
            'success': False
        }
        
        try:
            # Create backup if requested
            if action.get('backup', False) and file_path.exists():
                backup_path = self._create_action_backup(file_path)
                result['backup_path'] = str(backup_path)
            
            if action_type == 'delete_file':
                result.update(self._execute_delete_file(file_path, action))
            elif action_type == 'comment_out_file':
                result.update(self._execute_comment_out_file(file_path, action))
            elif action_type == 'move_file':
                target_path = Path(action['target_path'])
                result.update(self._execute_move_file(file_path, target_path, action))
            else:
                raise ValueError(f"Unknown action type: {action_type}")
            
            result['completed_at'] = timezone.now()
            return result
            
        except Exception as e:
            logger.error(f"Action execution failed: {action_type} on {file_path}: {str(e)}")
            result['error'] = str(e)
            result['completed_at'] = timezone.now()
            return result
    
    def _execute_delete_file(self, file_path: Path, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file deletion."""
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted file: {file_path}")
            return {'success': True, 'action_taken': 'file_deleted'}
        else:
            return {'success': True, 'action_taken': 'file_already_missing'}
    
    def _execute_comment_out_file(self, file_path: Path, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file commenting (add comment header)."""
        if not file_path.exists():
            return {'success': False, 'error': 'File does not exist'}
        
        # Read existing content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Add comment header
        comment_header = f"""# COMMENTED OUT BY CONFLICT RESOLUTION ENGINE
# Reason: {action.get('reason', 'Conflict resolution')}
# Original file preserved below
# Commented at: {timezone.now().isoformat()}
# ---
"""
        
        # Write commented content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(comment_header)
            # Comment out each line of original content
            for line in content.split('\n'):
                f.write(f"# {line}\n")
        
        logger.info(f"Commented out file: {file_path}")
        return {'success': True, 'action_taken': 'file_commented'}
    
    def _execute_move_file(self, file_path: Path, target_path: Path, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file move operation."""
        if not file_path.exists():
            return {'success': False, 'error': 'Source file does not exist'}
        
        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move the file
        shutil.move(str(file_path), str(target_path))
        
        logger.info(f"Moved file: {file_path} -> {target_path}")
        return {
            'success': True,
            'action_taken': 'file_moved',
            'target_path': str(target_path),
            'files_affected': [str(file_path), str(target_path)]
        }
    
    def _create_action_backup(self, file_path: Path) -> Path:
        """Create a backup of a file before modification."""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{file_path.name}_{timestamp}.backup"
        
        backup_dir = self.base_directory / '.backups'
        backup_dir.mkdir(exist_ok=True)
        
        backup_path = backup_dir / backup_name
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    def _post_resolution_validation(self):
        """Perform validation after conflict resolution."""
        try:
            # Check for any remaining obvious conflicts
            detector = YamlDuplicateDetector(self.base_directory, self.fabric.name if self.fabric else None)
            remaining_duplicates = detector.detect_duplicates()
            
            remaining_count = remaining_duplicates.get('duplicates_found', 0)
            if remaining_count > 0:
                self.resolution_results['warnings'].append(
                    f"Post-resolution scan found {remaining_count} remaining potential conflicts"
                )
            
            # Validate directory structure integrity
            required_dirs = ['managed', 'raw', 'unmanaged']
            for dir_name in required_dirs:
                dir_path = self.base_directory / dir_name
                if not dir_path.exists():
                    dir_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created missing directory: {dir_path}")
            
            logger.info("Post-resolution validation completed")
            
        except Exception as e:
            logger.warning(f"Post-resolution validation failed: {str(e)}")
            self.resolution_results['warnings'].append(f"Post-resolution validation failed: {str(e)}")


# Convenience functions for integration
def resolve_yaml_conflicts(fabric, base_directory: Path, duplicate_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience function for conflict resolution."""
    engine = ConflictResolutionEngine(fabric, base_directory)
    return engine.resolve_conflicts(duplicate_groups)


def resolve_single_yaml_conflict(fabric, base_directory: Path, duplicate_group: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for single conflict resolution."""
    engine = ConflictResolutionEngine(fabric, base_directory)
    return engine.resolve_single_conflict(duplicate_group)