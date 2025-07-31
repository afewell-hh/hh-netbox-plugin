"""
GitHub Sync Client

This module provides direct GitHub API integration for file management and
commit operations, enabling seamless bidirectional synchronization between
HNP and GitHub repositories.
"""

import json
import base64
import logging
import requests
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger(__name__)


class FileOperationResult:
    """Result of file operation (create, update, delete)"""
    
    def __init__(self, success: bool, message: str = '', commit_sha: str = None,
                 file_path: str = None, error: str = None):
        self.success = success
        self.message = message
        self.commit_sha = commit_sha
        self.file_path = file_path
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'commit_sha': self.commit_sha,
            'file_path': self.file_path,
            'error': self.error
        }


class BranchResult:
    """Result of branch operation"""
    
    def __init__(self, success: bool, branch_name: str = '', commit_sha: str = None,
                 message: str = '', error: str = None):
        self.success = success
        self.branch_name = branch_name
        self.commit_sha = commit_sha
        self.message = message
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'branch_name': self.branch_name,
            'commit_sha': self.commit_sha,
            'message': self.message,
            'error': self.error
        }


class PRResult:
    """Result of pull request operation"""
    
    def __init__(self, success: bool, pr_number: int = None, pr_url: str = None,
                 message: str = '', error: str = None):
        self.success = success
        self.pr_number = pr_number
        self.pr_url = pr_url
        self.message = message
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'pr_number': self.pr_number,
            'pr_url': self.pr_url,
            'message': self.message,
            'error': self.error
        }


class FileContent:
    """File content from GitHub"""
    
    def __init__(self, content: str, sha: str, path: str, size: int = 0,
                 encoding: str = 'utf-8'):
        self.content = content
        self.sha = sha
        self.path = path
        self.size = size
        self.encoding = encoding
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'content': self.content,
            'sha': self.sha,
            'path': self.path,
            'size': self.size,
            'encoding': self.encoding
        }


class ChangeSet:
    """Set of changes detected in repository"""
    
    def __init__(self, changed_files: List[str] = None, new_files: List[str] = None,
                 deleted_files: List[str] = None, base_commit: str = None,
                 head_commit: str = None):
        self.changed_files = changed_files or []
        self.new_files = new_files or []
        self.deleted_files = deleted_files or []
        self.base_commit = base_commit
        self.head_commit = head_commit
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'changed_files': self.changed_files,
            'new_files': self.new_files,
            'deleted_files': self.deleted_files,
            'base_commit': self.base_commit,
            'head_commit': self.head_commit,
            'total_changes': len(self.changed_files) + len(self.new_files) + len(self.deleted_files)
        }


class GitHubSyncClient:
    """
    Direct GitHub API integration for file management and commit operations.
    
    This client provides comprehensive GitHub API access for bidirectional
    synchronization, including file CRUD operations, branch management,
    and pull request workflows.
    """
    
    def __init__(self, git_repository):
        """Initialize GitHub client for specified repository"""
        self.git_repository = git_repository
        self.base_url = 'https://api.github.com'
        
        # Parse repository information
        self._parse_repository_info()
        
        # Get authentication credentials
        self.credentials = git_repository.get_credentials()
        self.headers = self._build_auth_headers()
    
    def _parse_repository_info(self):
        """Parse GitHub repository information from URL"""
        try:
            # Parse GitHub URL to extract owner and repo
            # Supports both HTTPS and SSH URLs
            url = self.git_repository.url
            
            if url.startswith('git@github.com:'):
                # SSH format: git@github.com:owner/repo.git
                repo_path = url.replace('git@github.com:', '').replace('.git', '')
            elif 'github.com' in url:
                # HTTPS format: https://github.com/owner/repo.git
                parsed = urlparse(url)
                repo_path = parsed.path.strip('/').replace('.git', '')
            else:
                raise ValueError(f"Unsupported repository URL format: {url}")
            
            parts = repo_path.split('/')
            if len(parts) != 2:
                raise ValueError(f"Invalid GitHub repository path: {repo_path}")
            
            self.owner = parts[0]
            self.repo = parts[1]
            
            logger.debug(f"Parsed GitHub repository: {self.owner}/{self.repo}")
            
        except Exception as e:
            logger.error(f"Failed to parse repository info: {e}")
            raise ValueError(f"Invalid GitHub repository URL: {e}")
    
    def _build_auth_headers(self) -> Dict[str, str]:
        """Build authentication headers for GitHub API"""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'hedgehog-netbox-plugin/1.0'
        }
        
        if self.credentials.get('token'):
            headers['Authorization'] = f"token {self.credentials['token']}"
        elif self.credentials.get('access_token'):
            headers['Authorization'] = f"token {self.credentials['access_token']}"
        
        return headers
    
    def _make_request(self, method: str, url: str, data: Dict[str, Any] = None,
                     params: Dict[str, Any] = None) -> Tuple[bool, Dict[str, Any]]:
        """Make authenticated request to GitHub API"""
        try:
            full_url = f"{self.base_url}{url}" if url.startswith('/') else url
            
            response = requests.request(
                method=method,
                url=full_url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 403 and 'rate limit' in response.text.lower():
                logger.warning("GitHub API rate limit exceeded")
                return False, {'error': 'GitHub API rate limit exceeded'}
            
            # Success status codes
            if response.status_code in [200, 201, 204]:
                return True, response.json() if response.content else {}
            
            # Error handling
            error_info = {
                'status_code': response.status_code,
                'error': response.text
            }
            
            try:
                error_json = response.json()
                error_info.update(error_json)
            except:
                pass
            
            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
            return False, error_info
        
        except requests.exceptions.Timeout:
            return False, {'error': 'Request timeout'}
        except requests.exceptions.RequestException as e:
            return False, {'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error in GitHub API request: {e}")
            return False, {'error': str(e)}
    
    def get_file_content(self, path: str, branch: str = None) -> Dict[str, Any]:
        """
        Get file content from GitHub repository.
        
        Args:
            path: File path within repository
            branch: Branch name (defaults to default branch)
            
        Returns:
            Dictionary with file content and metadata
        """
        try:
            branch = branch or self.git_repository.default_branch
            url = f"/repos/{self.owner}/{self.repo}/contents/{path.lstrip('/')}"
            params = {'ref': branch}
            
            success, response = self._make_request('GET', url, params=params)
            
            if not success:
                return {
                    'success': False,
                    'error': response.get('error', 'Failed to get file content')
                }
            
            # Decode base64 content
            if response.get('encoding') == 'base64':
                content = base64.b64decode(response['content']).decode('utf-8')
            else:
                content = response['content']
            
            file_content = FileContent(
                content=content,
                sha=response['sha'],
                path=response['path'],
                size=response['size'],
                encoding=response.get('encoding', 'utf-8')
            )
            
            return {
                'success': True,
                'file_content': file_content.to_dict()
            }
        
        except Exception as e:
            logger.error(f"Failed to get file content for {path}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_file(self, path: str, content: str, message: str,
                   branch: str = None) -> FileOperationResult:
        """
        Create new file in GitHub repository.
        
        Args:
            path: File path within repository
            content: File content
            message: Commit message
            branch: Branch name (defaults to default branch)
            
        Returns:
            FileOperationResult with operation details
        """
        try:
            branch = branch or self.git_repository.default_branch
            url = f"/repos/{self.owner}/{self.repo}/contents/{path.lstrip('/')}"
            
            # Encode content as base64
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            
            # Get commit author info
            commit_info = self.git_repository.create_commit_info()
            
            data = {
                'message': message,
                'content': encoded_content,
                'branch': branch,
                'committer': commit_info,
                'author': commit_info
            }
            
            success, response = self._make_request('PUT', url, data=data)
            
            if success:
                commit_sha = response.get('commit', {}).get('sha', '')
                return FileOperationResult(
                    success=True,
                    message=f"File {path} created successfully",
                    commit_sha=commit_sha,
                    file_path=path
                )
            else:
                return FileOperationResult(
                    success=False,
                    error=response.get('error', 'Failed to create file'),
                    file_path=path
                )
        
        except Exception as e:
            logger.error(f"Failed to create file {path}: {e}")
            return FileOperationResult(
                success=False,
                error=str(e),
                file_path=path
            )
    
    def update_file(self, path: str, content: str, message: str,
                   branch: str = None) -> FileOperationResult:
        """
        Update existing file in GitHub repository.
        
        Args:
            path: File path within repository
            content: New file content
            message: Commit message
            branch: Branch name (defaults to default branch)
            
        Returns:
            FileOperationResult with operation details
        """
        try:
            # First get current file to get its SHA
            current_file = self.get_file_content(path, branch)
            
            if not current_file['success']:
                # File doesn't exist, create it instead
                return self.create_file(path, content, message, branch)
            
            file_sha = current_file['file_content']['sha']
            
            branch = branch or self.git_repository.default_branch
            url = f"/repos/{self.owner}/{self.repo}/contents/{path.lstrip('/')}"
            
            # Encode content as base64
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            
            # Get commit author info
            commit_info = self.git_repository.create_commit_info()
            
            data = {
                'message': message,
                'content': encoded_content,
                'sha': file_sha,
                'branch': branch,
                'committer': commit_info,
                'author': commit_info
            }
            
            success, response = self._make_request('PUT', url, data=data)
            
            if success:
                commit_sha = response.get('commit', {}).get('sha', '')
                return FileOperationResult(
                    success=True,
                    message=f"File {path} updated successfully",
                    commit_sha=commit_sha,
                    file_path=path
                )
            else:
                return FileOperationResult(
                    success=False,
                    error=response.get('error', 'Failed to update file'),
                    file_path=path
                )
        
        except Exception as e:
            logger.error(f"Failed to update file {path}: {e}")
            return FileOperationResult(
                success=False,
                error=str(e),
                file_path=path
            )
    
    def create_or_update_file(self, path: str, content: str, message: str,
                             branch: str = None) -> FileOperationResult:
        """
        Create or update file (smart operation that checks existence).
        
        Args:
            path: File path within repository
            content: File content
            message: Commit message
            branch: Branch name (defaults to default branch)
            
        Returns:
            FileOperationResult with operation details
        """
        # Check if file exists
        current_file = self.get_file_content(path, branch)
        
        if current_file['success']:
            # File exists, update it
            return self.update_file(path, content, message, branch)
        else:
            # File doesn't exist, create it
            return self.create_file(path, content, message, branch)
    
    def delete_file(self, path: str, message: str, branch: str = None) -> FileOperationResult:
        """
        Delete file from GitHub repository.
        
        Args:
            path: File path within repository
            message: Commit message
            branch: Branch name (defaults to default branch)
            
        Returns:
            FileOperationResult with operation details
        """
        try:
            # First get current file to get its SHA
            current_file = self.get_file_content(path, branch)
            
            if not current_file['success']:
                return FileOperationResult(
                    success=False,
                    error="File does not exist",
                    file_path=path
                )
            
            file_sha = current_file['file_content']['sha']
            
            branch = branch or self.git_repository.default_branch
            url = f"/repos/{self.owner}/{self.repo}/contents/{path.lstrip('/')}"
            
            # Get commit author info
            commit_info = self.git_repository.create_commit_info()
            
            data = {
                'message': message,
                'sha': file_sha,
                'branch': branch,
                'committer': commit_info,
                'author': commit_info
            }
            
            success, response = self._make_request('DELETE', url, data=data)
            
            if success:
                commit_sha = response.get('commit', {}).get('sha', '')
                return FileOperationResult(
                    success=True,
                    message=f"File {path} deleted successfully",
                    commit_sha=commit_sha,
                    file_path=path
                )
            else:
                return FileOperationResult(
                    success=False,
                    error=response.get('error', 'Failed to delete file'),
                    file_path=path
                )
        
        except Exception as e:
            logger.error(f"Failed to delete file {path}: {e}")
            return FileOperationResult(
                success=False,
                error=str(e),
                file_path=path
            )
    
    def get_latest_commit(self, branch: str = None) -> Dict[str, Any]:
        """
        Get latest commit SHA for branch.
        
        Args:
            branch: Branch name (defaults to default branch)
            
        Returns:
            Dictionary with commit information
        """
        try:
            branch = branch or self.git_repository.default_branch
            url = f"/repos/{self.owner}/{self.repo}/commits/{branch}"
            
            success, response = self._make_request('GET', url)
            
            if success:
                return {
                    'success': True,
                    'commit_sha': response['sha'],
                    'commit_message': response['commit']['message'],
                    'author': response['commit']['author'],
                    'committed_at': response['commit']['committer']['date']
                }
            else:
                return {
                    'success': False,
                    'error': response.get('error', 'Failed to get latest commit')
                }
        
        except Exception as e:
            logger.error(f"Failed to get latest commit: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_file_changes(self, base_commit: str, head_commit: str,
                        directory_path: str = None) -> Dict[str, Any]:
        """
        Get file changes between two commits.
        
        Args:
            base_commit: Base commit SHA
            head_commit: Head commit SHA
            directory_path: Optional directory path to filter changes
            
        Returns:
            Dictionary with file changes
        """
        try:
            url = f"/repos/{self.owner}/{self.repo}/compare/{base_commit}...{head_commit}"
            
            success, response = self._make_request('GET', url)
            
            if not success:
                return {
                    'success': False,
                    'error': response.get('error', 'Failed to get file changes')
                }
            
            # Process files from comparison
            changed_files = []
            new_files = []
            deleted_files = []
            
            for file_info in response.get('files', []):
                file_path = file_info['filename']
                
                # Filter by directory if specified
                if directory_path and not file_path.startswith(directory_path.strip('/')):
                    continue
                
                status = file_info['status']
                
                if status == 'added':
                    new_files.append(file_path)
                elif status == 'removed':
                    deleted_files.append(file_path)
                elif status in ['modified', 'renamed']:
                    changed_files.append(file_path)
            
            changeset = ChangeSet(
                changed_files=changed_files,
                new_files=new_files,
                deleted_files=deleted_files,
                base_commit=base_commit,
                head_commit=head_commit
            )
            
            return {
                'success': True,
                'changeset': changeset.to_dict(),
                'changed_files': changed_files,
                'new_files': new_files,
                'deleted_files': deleted_files
            }
        
        except Exception as e:
            logger.error(f"Failed to get file changes: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_branch(self, branch_name: str, base_branch: str = None) -> BranchResult:
        """
        Create new branch in repository.
        
        Args:
            branch_name: Name for new branch
            base_branch: Base branch to create from (defaults to default branch)
            
        Returns:
            BranchResult with operation details
        """
        try:
            base_branch = base_branch or self.git_repository.default_branch
            
            # Get base branch SHA
            base_commit = self.get_latest_commit(base_branch)
            if not base_commit['success']:
                return BranchResult(
                    success=False,
                    error=f"Failed to get base branch {base_branch}"
                )
            
            # Create branch
            url = f"/repos/{self.owner}/{self.repo}/git/refs"
            data = {
                'ref': f'refs/heads/{branch_name}',
                'sha': base_commit['commit_sha']
            }
            
            success, response = self._make_request('POST', url, data=data)
            
            if success:
                return BranchResult(
                    success=True,
                    branch_name=branch_name,
                    commit_sha=base_commit['commit_sha'],
                    message=f"Branch {branch_name} created successfully"
                )
            else:
                return BranchResult(
                    success=False,
                    error=response.get('error', 'Failed to create branch')
                )
        
        except Exception as e:
            logger.error(f"Failed to create branch {branch_name}: {e}")
            return BranchResult(
                success=False,
                error=str(e)
            )
    
    def create_pull_request(self, title: str, body: str, head_branch: str,
                           base_branch: str = None) -> PRResult:
        """
        Create pull request.
        
        Args:
            title: PR title
            body: PR body/description
            head_branch: Branch with changes
            base_branch: Target branch (defaults to default branch)
            
        Returns:
            PRResult with operation details
        """
        try:
            base_branch = base_branch or self.git_repository.default_branch
            
            url = f"/repos/{self.owner}/{self.repo}/pulls"
            data = {
                'title': title,
                'body': body,
                'head': head_branch,
                'base': base_branch
            }
            
            success, response = self._make_request('POST', url, data=data)
            
            if success:
                return PRResult(
                    success=True,
                    pr_number=response['number'],
                    pr_url=response['html_url'],
                    message=f"Pull request #{response['number']} created successfully"
                )
            else:
                return PRResult(
                    success=False,
                    error=response.get('error', 'Failed to create pull request')
                )
        
        except Exception as e:
            logger.error(f"Failed to create pull request: {e}")
            return PRResult(
                success=False,
                error=str(e)
            )
    
    def validate_push_permissions(self) -> Dict[str, Any]:
        """
        Validate that credentials have push permissions.
        
        Returns:
            Dictionary with validation results
        """
        try:
            # Get repository info to check permissions
            url = f"/repos/{self.owner}/{self.repo}"
            success, response = self._make_request('GET', url)
            
            if not success:
                return {
                    'success': False,
                    'error': response.get('error', 'Cannot access repository')
                }
            
            permissions = response.get('permissions', {})
            
            return {
                'success': True,
                'can_push': permissions.get('push', False),
                'can_admin': permissions.get('admin', False),
                'can_pull': permissions.get('pull', False),
                'permissions': permissions,
                'repository_info': {
                    'full_name': response['full_name'],
                    'private': response['private'],
                    'default_branch': response['default_branch']
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to validate push permissions: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def commit_directory_changes(self, directory_path: str, message: str,
                                branch: str = None) -> Dict[str, Any]:
        """
        Commit all changes in a directory structure.
        
        Args:
            directory_path: Local directory path with changes
            message: Commit message
            branch: Branch name (defaults to default branch)
            
        Returns:
            Dictionary with commit results
        """
        try:
            from pathlib import Path
            
            directory = Path(directory_path)
            if not directory.exists():
                return {
                    'success': False,
                    'error': f"Directory {directory_path} does not exist"
                }
            
            branch = branch or self.git_repository.default_branch
            files_committed = []
            errors = []
            
            # Process all files in directory
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    # Calculate relative path from gitops directory
                    relative_path = file_path.relative_to(directory.parent)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Create or update file
                        result = self.create_or_update_file(
                            path=str(relative_path),
                            content=content,
                            message=message,
                            branch=branch
                        )
                        
                        if result.success:
                            files_committed.append(str(relative_path))
                        else:
                            errors.append(f"Failed to commit {relative_path}: {result.error}")
                    
                    except Exception as e:
                        errors.append(f"Error processing {relative_path}: {str(e)}")
            
            return {
                'success': len(errors) == 0,
                'message': f"Committed {len(files_committed)} files",
                'files_committed': files_committed,
                'errors': errors
            }
        
        except Exception as e:
            logger.error(f"Failed to commit directory changes: {e}")
            return {
                'success': False,
                'error': str(e)
            }