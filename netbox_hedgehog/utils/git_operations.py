"""
Enhanced Git Operations Utility
Provides advanced Git operations for file-level management, smart merge conflict detection,
branch management for GitOps workflows, and integration with existing Git client utilities.
"""

import os
import subprocess
import tempfile
import shutil
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from contextlib import contextmanager
from dataclasses import dataclass

from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class GitBranch:
    """Represents a Git branch with metadata."""
    name: str
    commit_hash: str
    is_current: bool
    is_remote: bool
    last_commit_date: datetime
    author: str
    commit_message: str


@dataclass
class GitCommit:
    """Represents a Git commit with metadata."""
    hash: str
    short_hash: str
    author: str
    author_email: str
    date: datetime
    message: str
    files_changed: List[str]
    insertions: int
    deletions: int


@dataclass
class GitFileChange:
    """Represents a file change in Git."""
    file_path: str
    change_type: str  # 'added', 'modified', 'deleted', 'renamed'
    old_path: Optional[str] = None
    lines_added: int = 0
    lines_removed: int = 0


@dataclass
class MergeConflict:
    """Represents a merge conflict."""
    file_path: str
    conflict_markers: List[Dict[str, Any]]
    conflict_type: str  # 'content', 'rename', 'delete'
    auto_resolvable: bool
    resolution_strategy: Optional[str] = None


class GitOperations:
    """
    Enhanced Git operations manager providing advanced Git functionality
    for GitOps file management workflows.
    
    Features:
    - Extended Git operations for file-level management
    - Smart merge conflict detection and resolution
    - Branch management for GitOps workflows
    - Integration with existing Git client utilities
    - Advanced commit and diff analysis
    """
    
    def __init__(self, repository_path: Union[str, Path]):
        self.repository_path = Path(repository_path).resolve()
        self.git_dir = self.repository_path / '.git'
        
        # Validate repository
        if not self._is_git_repository():
            raise ValueError(f"Not a Git repository: {self.repository_path}")
        
        # Configuration
        self.timeout = getattr(settings, 'GIT_OPERATION_TIMEOUT', 300)  # 5 minutes
        self.max_log_entries = getattr(settings, 'GIT_MAX_LOG_ENTRIES', 1000)
        
    def _is_git_repository(self) -> bool:
        """Check if the path is a valid Git repository."""
        return self.git_dir.exists() and self.git_dir.is_dir()
    
    def _run_git_command(self, args: List[str], input_data: Optional[str] = None,
                        capture_output: bool = True, check: bool = True,
                        timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        """
        Execute a Git command with proper error handling and logging.
        
        Args:
            args: Git command arguments
            input_data: Optional input data for the command
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise exception on non-zero exit code
            timeout: Command timeout in seconds
            
        Returns:
            CompletedProcess result
        """
        cmd = ['git'] + args
        timeout = timeout or self.timeout
        
        logger.debug(f"Executing Git command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repository_path,
                input=input_data,
                capture_output=capture_output,
                text=True,
                check=check,
                timeout=timeout
            )
            
            logger.debug(f"Git command completed with return code: {result.returncode}")
            return result
            
        except subprocess.TimeoutExpired as e:
            logger.error(f"Git command timed out after {timeout} seconds: {' '.join(cmd)}")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {' '.join(cmd)}, stderr: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error running Git command: {str(e)}")
            raise
    
    def get_repository_status(self) -> Dict[str, Any]:
        """
        Get comprehensive repository status information.
        
        Returns:
            Dict with repository status details
        """
        try:
            # Get basic status
            status_result = self._run_git_command(['status', '--porcelain=v1'])
            
            # Parse file statuses
            file_changes = []
            for line in status_result.stdout.strip().split('\n'):
                if line:
                    status_code = line[:2]
                    file_path = line[3:]
                    file_changes.append({
                        'file_path': file_path,
                        'status': self._parse_status_code(status_code),
                        'staged': status_code[0] != ' ',
                        'unstaged': status_code[1] != ' '
                    })
            
            # Get current branch
            branch_result = self._run_git_command(['rev-parse', '--abbrev-ref', 'HEAD'])
            current_branch = branch_result.stdout.strip()
            
            # Get commit information
            try:
                commit_result = self._run_git_command(['rev-parse', 'HEAD'])
                current_commit = commit_result.stdout.strip()
                
                log_result = self._run_git_command(['log', '-1', '--format=%an|%ae|%ci|%s'])
                if log_result.stdout.strip():
                    author, email, date_str, message = log_result.stdout.strip().split('|', 3)
                    last_commit = {
                        'hash': current_commit,
                        'author': author,
                        'email': email,
                        'date': date_str,
                        'message': message
                    }
                else:
                    last_commit = None
            except subprocess.CalledProcessError:
                current_commit = None
                last_commit = None
            
            # Check for merge conflicts
            has_conflicts = any(change['status'] in ['both_modified', 'both_added', 'both_deleted'] 
                              for change in file_changes)
            
            # Get remote tracking information
            remote_info = self._get_remote_tracking_info(current_branch)
            
            return {
                'clean': len(file_changes) == 0,
                'current_branch': current_branch,
                'current_commit': current_commit,
                'last_commit': last_commit,
                'file_changes': file_changes,
                'has_conflicts': has_conflicts,
                'remote_info': remote_info,
                'repository_path': str(self.repository_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to get repository status: {str(e)}")
            return {
                'error': str(e),
                'repository_path': str(self.repository_path)
            }
    
    def create_branch(self, branch_name: str, start_point: Optional[str] = None,
                     checkout: bool = True) -> Dict[str, Any]:
        """
        Create a new branch for GitOps workflows.
        
        Args:
            branch_name: Name of the new branch
            start_point: Optional commit/branch to start from
            checkout: Whether to checkout the new branch
            
        Returns:
            Dict with branch creation results
        """
        logger.info(f"Creating branch: {branch_name}")
        
        result = {
            'success': False,
            'branch_name': branch_name,
            'start_point': start_point,
            'checked_out': False
        }
        
        try:
            # Check if branch already exists
            existing_branches = self.list_branches()
            if any(branch.name == branch_name for branch in existing_branches):
                result['error'] = f"Branch '{branch_name}' already exists"
                return result
            
            # Create branch
            create_args = ['branch', branch_name]
            if start_point:
                create_args.append(start_point)
            
            self._run_git_command(create_args)
            result['success'] = True
            
            # Checkout if requested
            if checkout:
                checkout_result = self.checkout_branch(branch_name)
                result['checked_out'] = checkout_result['success']
                if not checkout_result['success']:
                    result['checkout_error'] = checkout_result.get('error')
            
            logger.info(f"Successfully created branch: {branch_name}")
            
        except Exception as e:
            logger.error(f"Failed to create branch {branch_name}: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    def checkout_branch(self, branch_name: str, create_if_not_exists: bool = False) -> Dict[str, Any]:
        """
        Checkout a branch.
        
        Args:
            branch_name: Name of the branch to checkout
            create_if_not_exists: Whether to create the branch if it doesn't exist
            
        Returns:
            Dict with checkout results
        """
        logger.info(f"Checking out branch: {branch_name}")
        
        result = {
            'success': False,
            'branch_name': branch_name,
            'created': False
        }
        
        try:
            checkout_args = ['checkout']
            if create_if_not_exists:
                checkout_args.append('-b')
            checkout_args.append(branch_name)
            
            self._run_git_command(checkout_args)
            result['success'] = True
            
            if create_if_not_exists:
                # Check if branch was created
                existing_branches = self.list_branches()
                result['created'] = any(branch.name == branch_name for branch in existing_branches)
            
            logger.info(f"Successfully checked out branch: {branch_name}")
            
        except Exception as e:
            logger.error(f"Failed to checkout branch {branch_name}: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    def list_branches(self, include_remote: bool = True) -> List[GitBranch]:
        """
        List all branches in the repository.
        
        Args:
            include_remote: Whether to include remote branches
            
        Returns:
            List of GitBranch objects
        """
        branches = []
        
        try:
            # Get local branches
            local_result = self._run_git_command(['branch', '-v', '--format=%(refname:short)|%(objectname:short)|%(upstream:short)|%(committerdate:iso8601)|%(authorname)|%(subject)'])
            
            for line in local_result.stdout.strip().split('\n'):
                if line and '|' in line:
                    parts = line.split('|', 5)
                    if len(parts) >= 6:
                        name, commit_hash, upstream, date_str, author, message = parts
                        is_current = name.startswith('*')
                        if is_current:
                            name = name[1:].strip()
                        
                        try:
                            commit_date = datetime.fromisoformat(date_str.replace(' ', 'T'))
                        except:
                            commit_date = timezone.now()
                        
                        branches.append(GitBranch(
                            name=name.strip(),
                            commit_hash=commit_hash.strip(),
                            is_current=is_current,
                            is_remote=False,
                            last_commit_date=commit_date,
                            author=author.strip(),
                            commit_message=message.strip()
                        ))
            
            # Get remote branches if requested
            if include_remote:
                try:
                    remote_result = self._run_git_command(['branch', '-r', '-v'])
                    
                    for line in remote_result.stdout.strip().split('\n'):
                        if line and not line.strip().startswith('origin/HEAD'):
                            parts = line.strip().split()
                            if len(parts) >= 3:
                                name = parts[0]
                                commit_hash = parts[1]
                                message = ' '.join(parts[2:])
                                
                                branches.append(GitBranch(
                                    name=name,
                                    commit_hash=commit_hash,
                                    is_current=False,
                                    is_remote=True,
                                    last_commit_date=timezone.now(),  # Would need separate call to get actual date
                                    author='',  # Would need separate call to get author
                                    commit_message=message
                                ))
                                
                except subprocess.CalledProcessError:
                    logger.warning("Failed to get remote branches")
            
        except Exception as e:
            logger.error(f"Failed to list branches: {str(e)}")
        
        return branches
    
    def merge_branch(self, branch_name: str, strategy: str = 'recursive',
                    allow_unrelated: bool = False) -> Dict[str, Any]:
        """
        Merge a branch with conflict detection.
        
        Args:
            branch_name: Name of the branch to merge
            strategy: Merge strategy ('recursive', 'ours', 'theirs')
            allow_unrelated: Whether to allow unrelated histories
            
        Returns:
            Dict with merge results
        """
        logger.info(f"Merging branch: {branch_name}")
        
        result = {
            'success': False,
            'branch_name': branch_name,
            'strategy': strategy,
            'conflicts': [],
            'files_merged': []
        }
        
        try:
            # Pre-merge checks
            status = self.get_repository_status()
            if not status['clean']:
                result['error'] = "Repository has uncommitted changes"
                return result
            
            # Build merge command
            merge_args = ['merge', f'--strategy={strategy}']
            if allow_unrelated:
                merge_args.append('--allow-unrelated-histories')
            merge_args.append(branch_name)
            
            try:
                self._run_git_command(merge_args)
                result['success'] = True
                
                # Get merge information
                merge_commit = self._run_git_command(['rev-parse', 'HEAD'])
                result['merge_commit'] = merge_commit.stdout.strip()
                
                # Get files that were merged
                diff_result = self._run_git_command(['diff-tree', '--name-only', '-r', 'HEAD~1', 'HEAD'])
                result['files_merged'] = diff_result.stdout.strip().split('\n') if diff_result.stdout.strip() else []
                
                logger.info(f"Successfully merged branch: {branch_name}")
                
            except subprocess.CalledProcessError:
                # Merge failed, likely due to conflicts
                conflicts = self.detect_merge_conflicts()
                result['conflicts'] = conflicts
                result['has_conflicts'] = len(conflicts) > 0
                
                if conflicts:
                    result['error'] = f"Merge failed with {len(conflicts)} conflicts"
                else:
                    result['error'] = "Merge failed for unknown reason"
            
        except Exception as e:
            logger.error(f"Failed to merge branch {branch_name}: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    def detect_merge_conflicts(self) -> List[MergeConflict]:
        """
        Detect and analyze merge conflicts in the repository.
        
        Returns:
            List of MergeConflict objects
        """
        conflicts = []
        
        try:
            # Get files with conflicts
            status_result = self._run_git_command(['status', '--porcelain'])
            
            for line in status_result.stdout.strip().split('\n'):
                if line and len(line) >= 2:
                    status_code = line[:2]
                    file_path = line[3:]
                    
                    # Check for conflict indicators
                    if status_code in ['UU', 'AA', 'DD', 'AU', 'UA', 'DU', 'UD']:
                        conflict_type = self._determine_conflict_type(status_code)
                        
                        # Analyze conflict markers in the file
                        conflict_markers = []
                        auto_resolvable = False
                        
                        if conflict_type == 'content':
                            file_analysis = self._analyze_conflict_file(file_path)
                            conflict_markers = file_analysis['markers']
                            auto_resolvable = file_analysis['auto_resolvable']
                        
                        conflicts.append(MergeConflict(
                            file_path=file_path,
                            conflict_markers=conflict_markers,
                            conflict_type=conflict_type,
                            auto_resolvable=auto_resolvable
                        ))
            
        except Exception as e:
            logger.error(f"Failed to detect merge conflicts: {str(e)}")
        
        return conflicts
    
    def resolve_conflict(self, conflict: MergeConflict, resolution_strategy: str,
                        custom_content: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolve a merge conflict using specified strategy.
        
        Args:
            conflict: MergeConflict object to resolve
            resolution_strategy: 'ours', 'theirs', 'manual', 'auto'
            custom_content: Custom content for manual resolution
            
        Returns:
            Dict with resolution results
        """
        logger.info(f"Resolving conflict in {conflict.file_path} using strategy: {resolution_strategy}")
        
        result = {
            'success': False,
            'file_path': conflict.file_path,
            'strategy': resolution_strategy
        }
        
        try:
            file_path = self.repository_path / conflict.file_path
            
            if resolution_strategy == 'ours':
                # Use our version
                self._run_git_command(['checkout', '--ours', conflict.file_path])
                
            elif resolution_strategy == 'theirs':
                # Use their version
                self._run_git_command(['checkout', '--theirs', conflict.file_path])
                
            elif resolution_strategy == 'manual' and custom_content is not None:
                # Use custom content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(custom_content)
                
            elif resolution_strategy == 'auto':
                # Attempt automatic resolution
                auto_result = self._auto_resolve_conflict(conflict)
                if not auto_result['success']:
                    result['error'] = f"Auto-resolution failed: {auto_result['error']}"
                    return result
                
            else:
                result['error'] = f"Invalid resolution strategy: {resolution_strategy}"
                return result
            
            # Mark as resolved
            self._run_git_command(['add', conflict.file_path])
            result['success'] = True
            
            logger.info(f"Successfully resolved conflict in {conflict.file_path}")
            
        except Exception as e:
            logger.error(f"Failed to resolve conflict in {conflict.file_path}: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    def get_file_history(self, file_path: str, max_entries: Optional[int] = None) -> List[GitCommit]:
        """
        Get commit history for a specific file.
        
        Args:
            file_path: Path to the file
            max_entries: Maximum number of entries to return
            
        Returns:
            List of GitCommit objects
        """
        max_entries = max_entries or self.max_log_entries
        commits = []
        
        try:
            # Get file history
            log_args = ['log', f'--max-count={max_entries}', '--format=%H|%h|%an|%ae|%ci|%s', '--stat', '--', file_path]
            result = self._run_git_command(log_args)
            
            # Parse commit information
            lines = result.stdout.strip().split('\n')
            i = 0
            
            while i < len(lines):
                line = lines[i]
                if '|' in line and not line.startswith(' '):
                    # This is a commit header line
                    parts = line.split('|', 5)
                    if len(parts) >= 6:
                        hash_full, hash_short, author, email, date_str, message = parts
                        
                        try:
                            commit_date = datetime.fromisoformat(date_str.replace(' ', 'T'))
                        except:
                            commit_date = timezone.now()
                        
                        # Parse stat information
                        files_changed = []
                        insertions = 0
                        deletions = 0
                        
                        # Look ahead for stat lines
                        j = i + 1
                        while j < len(lines) and lines[j].startswith(' '):
                            stat_line = lines[j].strip()
                            if '|' in stat_line and ('+' in stat_line or '-' in stat_line):
                                # This is a file stat line
                                parts = stat_line.split('|')
                                if len(parts) >= 2:
                                    file_name = parts[0].strip()
                                    changes = parts[1].strip()
                                    files_changed.append(file_name)
                                    
                                    # Count insertions and deletions
                                    insertions += changes.count('+')
                                    deletions += changes.count('-')
                            j += 1
                        
                        commits.append(GitCommit(
                            hash=hash_full,
                            short_hash=hash_short,
                            author=author,
                            author_email=email,
                            date=commit_date,
                            message=message,
                            files_changed=files_changed,
                            insertions=insertions,
                            deletions=deletions
                        ))
                        
                        i = j
                    else:
                        i += 1
                else:
                    i += 1
            
        except Exception as e:
            logger.error(f"Failed to get file history for {file_path}: {str(e)}")
        
        return commits
    
    def get_file_diff(self, file_path: str, commit1: str, commit2: str = 'HEAD') -> Dict[str, Any]:
        """
        Get diff for a specific file between two commits.
        
        Args:
            file_path: Path to the file
            commit1: First commit (older)
            commit2: Second commit (newer)
            
        Returns:
            Dict with diff information
        """
        result = {
            'file_path': file_path,
            'commit1': commit1,
            'commit2': commit2,
            'diff_lines': [],
            'additions': 0,
            'deletions': 0
        }
        
        try:
            # Get diff
            diff_result = self._run_git_command(['diff', f'{commit1}..{commit2}', '--', file_path])
            
            if diff_result.stdout:
                lines = diff_result.stdout.split('\n')
                for line in lines:
                    if line.startswith('+') and not line.startswith('+++'):
                        result['additions'] += 1
                    elif line.startswith('-') and not line.startswith('---'):
                        result['deletions'] += 1
                
                result['diff_lines'] = lines
                result['has_changes'] = result['additions'] > 0 or result['deletions'] > 0
            else:
                result['has_changes'] = False
            
        except Exception as e:
            logger.error(f"Failed to get diff for {file_path}: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    def commit_files(self, files: List[str], message: str, author: Optional[str] = None) -> Dict[str, Any]:
        """
        Commit specified files with a message.
        
        Args:
            files: List of file paths to commit
            message: Commit message
            author: Optional author override
            
        Returns:
            Dict with commit results
        """
        logger.info(f"Committing {len(files)} files: {message}")
        
        result = {
            'success': False,
            'files': files,
            'message': message,
            'commit_hash': None
        }
        
        try:
            # Stage files
            for file_path in files:
                self._run_git_command(['add', file_path])
            
            # Commit
            commit_args = ['commit', '-m', message]
            if author:
                commit_args.extend(['--author', author])
            
            self._run_git_command(commit_args)
            
            # Get commit hash
            hash_result = self._run_git_command(['rev-parse', 'HEAD'])
            result['commit_hash'] = hash_result.stdout.strip()
            result['success'] = True
            
            logger.info(f"Successfully committed files: {result['commit_hash']}")
            
        except Exception as e:
            logger.error(f"Failed to commit files: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    def push_to_remote(self, remote: str = 'origin', branch: Optional[str] = None,
                      force: bool = False, set_upstream: bool = False) -> Dict[str, Any]:
        """
        Push commits to remote repository.
        
        Args:
            remote: Remote name (default: origin)
            branch: Branch name (default: current branch)
            force: Whether to force push
            set_upstream: Whether to set upstream tracking
            
        Returns:
            Dict with push results
        """
        if not branch:
            # Get current branch
            branch_result = self._run_git_command(['rev-parse', '--abbrev-ref', 'HEAD'])
            branch = branch_result.stdout.strip()
        
        logger.info(f"Pushing to {remote}/{branch}")
        
        result = {
            'success': False,
            'remote': remote,
            'branch': branch,
            'force': force,
            'set_upstream': set_upstream
        }
        
        try:
            push_args = ['push']
            
            if set_upstream:
                push_args.extend(['-u', remote, branch])
            else:
                push_args.extend([remote, branch])
            
            if force:
                push_args.append('--force')
            
            push_result = self._run_git_command(push_args)
            result['success'] = True
            result['output'] = push_result.stdout
            
            logger.info(f"Successfully pushed to {remote}/{branch}")
            
        except Exception as e:
            logger.error(f"Failed to push to {remote}/{branch}: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    def pull_from_remote(self, remote: str = 'origin', branch: Optional[str] = None,
                        rebase: bool = False) -> Dict[str, Any]:
        """
        Pull changes from remote repository.
        
        Args:
            remote: Remote name (default: origin)
            branch: Branch name (default: current branch)
            rebase: Whether to rebase instead of merge
            
        Returns:
            Dict with pull results
        """
        if not branch:
            # Get current branch
            branch_result = self._run_git_command(['rev-parse', '--abbrev-ref', 'HEAD'])
            branch = branch_result.stdout.strip()
        
        logger.info(f"Pulling from {remote}/{branch}")
        
        result = {
            'success': False,
            'remote': remote,
            'branch': branch,
            'rebase': rebase,
            'files_changed': []
        }
        
        try:
            # Get commit before pull
            before_result = self._run_git_command(['rev-parse', 'HEAD'])
            before_commit = before_result.stdout.strip()
            
            pull_args = ['pull']
            if rebase:
                pull_args.append('--rebase')
            pull_args.extend([remote, branch])
            
            pull_result = self._run_git_command(pull_args)
            
            # Get commit after pull
            after_result = self._run_git_command(['rev-parse', 'HEAD'])
            after_commit = after_result.stdout.strip()
            
            result['success'] = True
            result['output'] = pull_result.stdout
            result['before_commit'] = before_commit
            result['after_commit'] = after_commit
            result['updated'] = before_commit != after_commit
            
            # Get changed files if updated
            if result['updated']:
                diff_result = self._run_git_command(['diff-tree', '--name-only', '-r', before_commit, after_commit])
                result['files_changed'] = diff_result.stdout.strip().split('\n') if diff_result.stdout.strip() else []
            
            logger.info(f"Successfully pulled from {remote}/{branch}")
            
        except Exception as e:
            logger.error(f"Failed to pull from {remote}/{branch}: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    # Private helper methods
    
    def _parse_status_code(self, code: str) -> str:
        """Parse Git status code into readable format."""
        status_map = {
            '??': 'untracked',
            'A ': 'added',
            'M ': 'modified',
            'D ': 'deleted',
            'R ': 'renamed',
            'C ': 'copied',
            'UU': 'both_modified',
            'AA': 'both_added',
            'DD': 'both_deleted',
            'AU': 'added_by_us',
            'UA': 'added_by_them',
            'DU': 'deleted_by_us',
            'UD': 'deleted_by_them'
        }
        return status_map.get(code, code)
    
    def _get_remote_tracking_info(self, branch_name: str) -> Dict[str, Any]:
        """Get remote tracking information for a branch."""
        try:
            # Get upstream branch
            upstream_result = self._run_git_command(['rev-parse', '--abbrev-ref', f'{branch_name}@{{upstream}}'])
            upstream = upstream_result.stdout.strip()
            
            # Get ahead/behind counts
            count_result = self._run_git_command(['rev-list', '--left-right', '--count', f'{branch_name}...{upstream}'])
            ahead, behind = map(int, count_result.stdout.strip().split())
            
            return {
                'upstream': upstream,
                'ahead': ahead,
                'behind': behind,
                'tracking': True
            }
            
        except subprocess.CalledProcessError:
            return {
                'tracking': False
            }
    
    def _determine_conflict_type(self, status_code: str) -> str:
        """Determine the type of conflict from status code."""
        if status_code in ['UU', 'AA']:
            return 'content'
        elif status_code in ['DD']:
            return 'delete'
        elif status_code in ['AU', 'UA', 'DU', 'UD']:
            return 'rename'
        else:
            return 'unknown'
    
    def _analyze_conflict_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze conflict markers in a file."""
        full_path = self.repository_path / file_path
        markers = []
        auto_resolvable = True
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            in_conflict = False
            conflict_start = None
            
            for i, line in enumerate(lines):
                if line.startswith('<<<<<<<'):
                    in_conflict = True
                    conflict_start = i
                    auto_resolvable = False  # Conservative approach
                elif line.startswith('=======') and in_conflict:
                    # Found separator
                    pass
                elif line.startswith('>>>>>>>') and in_conflict:
                    # End of conflict
                    markers.append({
                        'start_line': conflict_start,
                        'end_line': i,
                        'type': 'merge_conflict'
                    })
                    in_conflict = False
                    conflict_start = None
                    
        except Exception as e:
            logger.warning(f"Failed to analyze conflict file {file_path}: {str(e)}")
        
        return {
            'markers': markers,
            'auto_resolvable': auto_resolvable
        }
    
    def _auto_resolve_conflict(self, conflict: MergeConflict) -> Dict[str, Any]:
        """Attempt automatic conflict resolution."""
        # This is a placeholder for intelligent conflict resolution
        # In a real implementation, this would use various strategies
        # based on the conflict type and content
        
        return {
            'success': False,
            'error': 'Automatic conflict resolution not yet implemented'
        }


# Convenience functions for integration with existing code

def create_git_operations(repository_path: Union[str, Path]) -> GitOperations:
    """Factory function to create GitOperations instance."""
    return GitOperations(repository_path)


def get_repository_status(repository_path: Union[str, Path]) -> Dict[str, Any]:
    """Convenience function to get repository status."""
    git_ops = GitOperations(repository_path)
    return git_ops.get_repository_status()


def create_and_checkout_branch(repository_path: Union[str, Path], branch_name: str) -> Dict[str, Any]:
    """Convenience function to create and checkout a branch."""
    git_ops = GitOperations(repository_path)
    return git_ops.create_branch(branch_name, checkout=True)


def commit_and_push_files(repository_path: Union[str, Path], files: List[str], 
                         message: str, remote: str = 'origin') -> Dict[str, Any]:
    """Convenience function to commit and push files."""
    git_ops = GitOperations(repository_path)
    
    # Commit files
    commit_result = git_ops.commit_files(files, message)
    if not commit_result['success']:
        return commit_result
    
    # Push to remote
    push_result = git_ops.push_to_remote(remote)
    
    return {
        'success': push_result['success'],
        'commit_result': commit_result,
        'push_result': push_result
    }