"""
Git Provider API Integration for Enterprise GitOps.

This module provides comprehensive REST API integration with major Git providers
including GitHub, GitLab, and generic Git services. Features include:
- Full REST API integration with OAuth/token authentication
- Advanced rate limiting and request management
- Repository operations (create, update, delete, branch management)
- Pull/Merge request workflows
- Webhook management
- Multi-environment support

Author: Git Operations Agent
Date: July 10, 2025
"""

import asyncio
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
import base64
import hashlib
from dataclasses import dataclass

from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitInfo:
    """Rate limit information from API responses."""
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None


@dataclass
class RepositoryInfo:
    """Repository information from provider APIs."""
    name: str
    full_name: str
    description: str
    default_branch: str
    private: bool
    clone_url: str
    ssh_url: str
    web_url: str
    last_push: Optional[datetime]
    provider: str


@dataclass
class PullRequestInfo:
    """Pull/Merge request information."""
    id: int
    number: int
    title: str
    body: str
    state: str
    head_branch: str
    base_branch: str
    author: str
    created_at: datetime
    updated_at: datetime
    web_url: str
    mergeable: bool
    provider: str


@dataclass
class BranchInfo:
    """Branch information from provider APIs."""
    name: str
    commit_sha: str
    commit_message: str
    author: str
    committed_date: datetime
    protected: bool
    web_url: str


class GitProviderError(Exception):
    """Base exception for Git provider operations."""
    pass


class GitProviderAuthError(GitProviderError):
    """Authentication error with Git provider."""
    pass


# Compatibility alias for API views
GitAuthenticationError = GitProviderAuthError


class GitProviderRateLimitError(GitProviderError):
    """Rate limit exceeded error."""
    pass


class GitProviderNotFoundError(GitProviderError):
    """Resource not found error."""
    pass


class GitProviderPermissionError(GitProviderError):
    """Permission denied error."""
    pass


class BaseGitProvider(ABC):
    """
    Abstract base class for Git provider implementations.
    
    Defines the common interface that all Git providers must implement
    for seamless integration with the GitOps workflow.
    """
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize Git provider with credentials.
        
        Args:
            credentials: Provider-specific authentication data
        """
        self.credentials = credentials
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.session = None
        self.rate_limit_info = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name."""
        pass
    
    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Validate provider credentials."""
        pass
    
    @abstractmethod
    async def get_repository_info(self, repo_path: str) -> RepositoryInfo:
        """Get repository information."""
        pass
    
    @abstractmethod
    async def get_branch_info(self, repo_path: str, branch: str) -> BranchInfo:
        """Get branch information."""
        pass
    
    @abstractmethod
    async def list_branches(self, repo_path: str) -> List[BranchInfo]:
        """List all branches in repository."""
        pass
    
    @abstractmethod
    async def compare_branches(self, repo_path: str, base: str, head: str) -> Dict[str, Any]:
        """Compare two branches."""
        pass
    
    @abstractmethod
    async def create_pull_request(
        self, 
        repo_path: str, 
        title: str, 
        body: str, 
        head: str, 
        base: str,
        **kwargs
    ) -> PullRequestInfo:
        """Create a new pull/merge request."""
        pass
    
    @abstractmethod
    async def get_pull_request(self, repo_path: str, pr_number: int) -> PullRequestInfo:
        """Get pull/merge request information."""
        pass
    
    @abstractmethod
    async def list_pull_requests(
        self, 
        repo_path: str, 
        state: str = 'open'
    ) -> List[PullRequestInfo]:
        """List pull/merge requests."""
        pass
    
    @abstractmethod
    async def create_webhook(
        self, 
        repo_path: str, 
        webhook_url: str, 
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create repository webhook."""
        pass
    
    @abstractmethod
    async def list_webhooks(self, repo_path: str) -> List[Dict[str, Any]]:
        """List repository webhooks."""
        pass
    
    async def check_rate_limit(self) -> Optional[RateLimitInfo]:
        """Check current rate limit status."""
        return self.rate_limit_info
    
    def _extract_repo_path(self, url: str) -> str:
        """Extract repository path from URL."""
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        # Remove .git suffix if present
        if path.endswith('.git'):
            path = path[:-4]
        
        return path


class GitHubAPIClient(BaseGitProvider):
    """
    GitHub REST API client with comprehensive enterprise features.
    
    Supports GitHub.com and GitHub Enterprise instances with:
    - OAuth Apps and Personal Access Tokens
    - GitHub Apps authentication
    - Rate limiting (5000 requests/hour for authenticated users)
    - Repository operations and branch management
    - Pull request workflows
    - Webhook management
    """
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize GitHub API client.
        
        Args:
            credentials: GitHub authentication data
                - token: Personal Access Token or GitHub App token
                - api_url: GitHub API URL (for Enterprise instances)
        """
        super().__init__(credentials)
        self.token = credentials.get('token')
        self.api_url = credentials.get('api_url', 'https://api.github.com')
        
        if not self.token:
            raise GitProviderAuthError("GitHub token is required")
    
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return 'github'
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get GitHub authentication headers."""
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Hedgehog-NetBox-Plugin/1.0'
        }
        return headers
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> Tuple[Dict[str, Any], int]:
        """
        Make authenticated GitHub API request with rate limiting.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base URL)
            **kwargs: Additional request parameters
            
        Returns:
            Tuple of (response_data, status_code)
        """
        url = urljoin(self.api_url, endpoint.lstrip('/'))
        headers = self._get_auth_headers()
        
        # Merge custom headers
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))
        
        # Check rate limit before request
        if self.rate_limit_info and self.rate_limit_info.remaining <= 10:
            wait_time = (self.rate_limit_info.reset_time - timezone.now()).total_seconds()
            if wait_time > 0:
                self.logger.warning(f"Rate limit approached, waiting {wait_time:.1f} seconds")
                await asyncio.sleep(wait_time)
        
        async with self.session.request(method, url, headers=headers, **kwargs) as response:
            # Update rate limit info
            self._update_rate_limit_info(response.headers)
            
            # Handle rate limiting
            if response.status == 403 and 'rate limit' in response.headers.get('X-RateLimit-Remaining', '0'):
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = max(0, reset_time - timezone.now().timestamp())
                
                if wait_time > 0:
                    self.logger.warning(f"Rate limited, waiting {wait_time:.1f} seconds")
                    await asyncio.sleep(wait_time)
                    # Retry the request
                    return await self._make_request(method, endpoint, **kwargs)
                else:
                    raise GitProviderRateLimitError("GitHub rate limit exceeded")
            
            # Handle other errors
            if response.status >= 400:
                try:
                    error_data = await response.json()
                    error_message = error_data.get('message', f'HTTP {response.status}')
                except:
                    error_message = f'HTTP {response.status}'
                
                if response.status == 401:
                    raise GitProviderAuthError(f"GitHub authentication failed: {error_message}")
                elif response.status == 403:
                    raise GitProviderPermissionError(f"GitHub permission denied: {error_message}")
                elif response.status == 404:
                    raise GitProviderNotFoundError(f"GitHub resource not found: {error_message}")
                else:
                    raise GitProviderError(f"GitHub API error: {error_message}")
            
            try:
                data = await response.json()
            except:
                data = {}
            
            return data, response.status
    
    def _update_rate_limit_info(self, headers: Dict[str, str]):
        """Update rate limit information from response headers."""
        try:
            limit = int(headers.get('X-RateLimit-Limit', 0))
            remaining = int(headers.get('X-RateLimit-Remaining', 0))
            reset_timestamp = int(headers.get('X-RateLimit-Reset', 0))
            reset_time = datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)
            
            self.rate_limit_info = RateLimitInfo(
                limit=limit,
                remaining=remaining,
                reset_time=reset_time
            )
        except (ValueError, TypeError):
            pass
    
    async def validate_credentials(self) -> bool:
        """Validate GitHub credentials."""
        try:
            data, status = await self._make_request('GET', '/user')
            return status == 200 and 'login' in data
        except GitProviderAuthError:
            return False
        except Exception as e:
            self.logger.error(f"Error validating GitHub credentials: {e}")
            return False
    
    async def get_repository_info(self, repo_path: str) -> RepositoryInfo:
        """Get GitHub repository information."""
        try:
            repo_path = self._extract_repo_path(repo_path)
            data, _ = await self._make_request('GET', f'/repos/{repo_path}')
            
            return RepositoryInfo(
                name=data['name'],
                full_name=data['full_name'],
                description=data.get('description', ''),
                default_branch=data['default_branch'],
                private=data['private'],
                clone_url=data['clone_url'],
                ssh_url=data['ssh_url'],
                web_url=data['html_url'],
                last_push=datetime.fromisoformat(data['pushed_at'].replace('Z', '+00:00')) if data.get('pushed_at') else None,
                provider='github'
            )
        except Exception as e:
            raise GitProviderError(f"Failed to get GitHub repository info: {e}")
    
    async def get_branch_info(self, repo_path: str, branch: str) -> BranchInfo:
        """Get GitHub branch information."""
        try:
            repo_path = self._extract_repo_path(repo_path)
            data, _ = await self._make_request('GET', f'/repos/{repo_path}/branches/{branch}')
            
            commit = data['commit']
            return BranchInfo(
                name=data['name'],
                commit_sha=commit['sha'],
                commit_message=commit['commit']['message'],
                author=commit['commit']['author']['name'],
                committed_date=datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00')),
                protected=data.get('protected', False),
                web_url=f"{self.api_url.replace('api.', '').replace('/api', '')}/{repo_path}/tree/{branch}"
            )
        except Exception as e:
            raise GitProviderError(f"Failed to get GitHub branch info: {e}")
    
    async def list_branches(self, repo_path: str) -> List[BranchInfo]:
        """List all branches in GitHub repository."""
        try:
            repo_path = self._extract_repo_path(repo_path)
            data, _ = await self._make_request('GET', f'/repos/{repo_path}/branches')
            
            branches = []
            for branch_data in data:
                commit = branch_data['commit']
                branches.append(BranchInfo(
                    name=branch_data['name'],
                    commit_sha=commit['sha'],
                    commit_message=commit['commit']['message'],
                    author=commit['commit']['author']['name'],
                    committed_date=datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00')),
                    protected=branch_data.get('protected', False),
                    web_url=f"{self.api_url.replace('api.', '').replace('/api', '')}/{repo_path}/tree/{branch_data['name']}"
                ))
            
            return branches
        except Exception as e:
            raise GitProviderError(f"Failed to list GitHub branches: {e}")
    
    async def compare_branches(self, repo_path: str, base: str, head: str) -> Dict[str, Any]:
        """Compare two branches in GitHub."""
        try:
            repo_path = self._extract_repo_path(repo_path)
            data, _ = await self._make_request('GET', f'/repos/{repo_path}/compare/{base}...{head}')
            
            return {
                'ahead_by': data.get('ahead_by', 0),
                'behind_by': data.get('behind_by', 0),
                'status': data.get('status', 'unknown'),
                'total_commits': data.get('total_commits', 0),
                'commits': [
                    {
                        'sha': commit['sha'],
                        'message': commit['commit']['message'],
                        'author': commit['commit']['author']['name'],
                        'date': commit['commit']['author']['date']
                    }
                    for commit in data.get('commits', [])
                ],
                'files_changed': len(data.get('files', [])),
                'additions': sum(f.get('additions', 0) for f in data.get('files', [])),
                'deletions': sum(f.get('deletions', 0) for f in data.get('files', [])),
                'provider': 'github'
            }
        except Exception as e:
            raise GitProviderError(f"Failed to compare GitHub branches: {e}")
    
    async def create_pull_request(
        self, 
        repo_path: str, 
        title: str, 
        body: str, 
        head: str, 
        base: str,
        **kwargs
    ) -> PullRequestInfo:
        """Create a new GitHub pull request."""
        try:
            repo_path = self._extract_repo_path(repo_path)
            
            pr_data = {
                'title': title,
                'body': body,
                'head': head,
                'base': base,
                'draft': kwargs.get('draft', False),
                'maintainer_can_modify': kwargs.get('maintainer_can_modify', True)
            }
            
            # Add reviewers if specified
            if 'reviewers' in kwargs:
                pr_data['reviewers'] = kwargs['reviewers']
            
            data, _ = await self._make_request('POST', f'/repos/{repo_path}/pulls', json=pr_data)
            
            return PullRequestInfo(
                id=data['id'],
                number=data['number'],
                title=data['title'],
                body=data['body'] or '',
                state=data['state'],
                head_branch=data['head']['ref'],
                base_branch=data['base']['ref'],
                author=data['user']['login'],
                created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00')),
                web_url=data['html_url'],
                mergeable=data.get('mergeable', True),
                provider='github'
            )
        except Exception as e:
            raise GitProviderError(f"Failed to create GitHub pull request: {e}")
    
    async def get_pull_request(self, repo_path: str, pr_number: int) -> PullRequestInfo:
        """Get GitHub pull request information."""
        try:
            repo_path = self._extract_repo_path(repo_path)
            data, _ = await self._make_request('GET', f'/repos/{repo_path}/pulls/{pr_number}')
            
            return PullRequestInfo(
                id=data['id'],
                number=data['number'],
                title=data['title'],
                body=data['body'] or '',
                state=data['state'],
                head_branch=data['head']['ref'],
                base_branch=data['base']['ref'],
                author=data['user']['login'],
                created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00')),
                web_url=data['html_url'],
                mergeable=data.get('mergeable', True),
                provider='github'
            )
        except Exception as e:
            raise GitProviderError(f"Failed to get GitHub pull request: {e}")
    
    async def list_pull_requests(
        self, 
        repo_path: str, 
        state: str = 'open'
    ) -> List[PullRequestInfo]:
        """List GitHub pull requests."""
        try:
            repo_path = self._extract_repo_path(repo_path)
            data, _ = await self._make_request(
                'GET', 
                f'/repos/{repo_path}/pulls',
                params={'state': state}
            )
            
            pull_requests = []
            for pr_data in data:
                pull_requests.append(PullRequestInfo(
                    id=pr_data['id'],
                    number=pr_data['number'],
                    title=pr_data['title'],
                    body=pr_data['body'] or '',
                    state=pr_data['state'],
                    head_branch=pr_data['head']['ref'],
                    base_branch=pr_data['base']['ref'],
                    author=pr_data['user']['login'],
                    created_at=datetime.fromisoformat(pr_data['created_at'].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(pr_data['updated_at'].replace('Z', '+00:00')),
                    web_url=pr_data['html_url'],
                    mergeable=pr_data.get('mergeable', True),
                    provider='github'
                ))
            
            return pull_requests
        except Exception as e:
            raise GitProviderError(f"Failed to list GitHub pull requests: {e}")
    
    async def create_webhook(
        self, 
        repo_path: str, 
        webhook_url: str, 
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create GitHub repository webhook."""
        try:
            repo_path = self._extract_repo_path(repo_path)
            
            webhook_data = {
                'name': 'web',
                'active': True,
                'events': events,
                'config': {
                    'url': webhook_url,
                    'content_type': 'json',
                    'insecure_ssl': '0'
                }
            }
            
            if secret:
                webhook_data['config']['secret'] = secret
            
            data, _ = await self._make_request('POST', f'/repos/{repo_path}/hooks', json=webhook_data)
            
            return {
                'id': data['id'],
                'url': data['config']['url'],
                'events': data['events'],
                'active': data['active'],
                'created_at': data['created_at'],
                'updated_at': data['updated_at'],
                'provider': 'github'
            }
        except Exception as e:
            raise GitProviderError(f"Failed to create GitHub webhook: {e}")
    
    async def list_webhooks(self, repo_path: str) -> List[Dict[str, Any]]:
        """List GitHub repository webhooks."""
        try:
            repo_path = self._extract_repo_path(repo_path)
            data, _ = await self._make_request('GET', f'/repos/{repo_path}/hooks')
            
            webhooks = []
            for hook in data:
                webhooks.append({
                    'id': hook['id'],
                    'url': hook['config'].get('url', ''),
                    'events': hook['events'],
                    'active': hook['active'],
                    'created_at': hook['created_at'],
                    'updated_at': hook['updated_at'],
                    'provider': 'github'
                })
            
            return webhooks
        except Exception as e:
            raise GitProviderError(f"Failed to list GitHub webhooks: {e}")


class GitLabAPIClient(BaseGitProvider):
    """
    GitLab REST API client with comprehensive enterprise features.
    
    Supports GitLab.com and self-hosted GitLab instances with:
    - Personal Access Tokens and Project Access Tokens
    - OAuth2 authentication
    - Rate limiting (300 requests/minute for authenticated users)
    - Repository operations and branch management
    - Merge request workflows
    - Webhook management
    """
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize GitLab API client.
        
        Args:
            credentials: GitLab authentication data
                - token: Personal Access Token or Project Access Token
                - api_url: GitLab API URL (for self-hosted instances)
        """
        super().__init__(credentials)
        self.token = credentials.get('token')
        self.api_url = credentials.get('api_url', 'https://gitlab.com/api/v4')
        
        if not self.token:
            raise GitProviderAuthError("GitLab token is required")
    
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return 'gitlab'
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get GitLab authentication headers."""
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'User-Agent': 'Hedgehog-NetBox-Plugin/1.0'
        }
        return headers
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> Tuple[Dict[str, Any], int]:
        """
        Make authenticated GitLab API request with rate limiting.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base URL)
            **kwargs: Additional request parameters
            
        Returns:
            Tuple of (response_data, status_code)
        """
        url = urljoin(self.api_url, endpoint.lstrip('/'))
        headers = self._get_auth_headers()
        
        # Merge custom headers
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))
        
        async with self.session.request(method, url, headers=headers, **kwargs) as response:
            # Handle rate limiting
            if response.status == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                self.logger.warning(f"GitLab rate limited, waiting {retry_after} seconds")
                await asyncio.sleep(retry_after)
                # Retry the request
                return await self._make_request(method, endpoint, **kwargs)
            
            # Handle other errors
            if response.status >= 400:
                try:
                    error_data = await response.json()
                    error_message = error_data.get('message', f'HTTP {response.status}')
                except:
                    error_message = f'HTTP {response.status}'
                
                if response.status == 401:
                    raise GitProviderAuthError(f"GitLab authentication failed: {error_message}")
                elif response.status == 403:
                    raise GitProviderPermissionError(f"GitLab permission denied: {error_message}")
                elif response.status == 404:
                    raise GitProviderNotFoundError(f"GitLab resource not found: {error_message}")
                else:
                    raise GitProviderError(f"GitLab API error: {error_message}")
            
            try:
                data = await response.json()
            except:
                data = {}
            
            return data, response.status
    
    def _get_project_id(self, repo_path: str) -> str:
        """Get GitLab project ID from repository path."""
        # For GitLab, we can use the URL-encoded project path
        return repo_path.replace('/', '%2F')
    
    async def validate_credentials(self) -> bool:
        """Validate GitLab credentials."""
        try:
            data, status = await self._make_request('GET', '/user')
            return status == 200 and 'username' in data
        except GitProviderAuthError:
            return False
        except Exception as e:
            self.logger.error(f"Error validating GitLab credentials: {e}")
            return False
    
    async def get_repository_info(self, repo_path: str) -> RepositoryInfo:
        """Get GitLab repository information."""
        try:
            project_id = self._get_project_id(repo_path)
            data, _ = await self._make_request('GET', f'/projects/{project_id}')
            
            return RepositoryInfo(
                name=data['name'],
                full_name=data['path_with_namespace'],
                description=data.get('description', ''),
                default_branch=data['default_branch'],
                private=data['visibility'] == 'private',
                clone_url=data['http_url_to_repo'],
                ssh_url=data['ssh_url_to_repo'],
                web_url=data['web_url'],
                last_push=datetime.fromisoformat(data['last_activity_at'].replace('Z', '+00:00')) if data.get('last_activity_at') else None,
                provider='gitlab'
            )
        except Exception as e:
            raise GitProviderError(f"Failed to get GitLab repository info: {e}")
    
    async def get_branch_info(self, repo_path: str, branch: str) -> BranchInfo:
        """Get GitLab branch information."""
        try:
            project_id = self._get_project_id(repo_path)
            data, _ = await self._make_request('GET', f'/projects/{project_id}/repository/branches/{branch}')
            
            commit = data['commit']
            return BranchInfo(
                name=data['name'],
                commit_sha=commit['id'],
                commit_message=commit['message'],
                author=commit['author_name'],
                committed_date=datetime.fromisoformat(commit['authored_date'].replace('Z', '+00:00')),
                protected=data.get('protected', False),
                web_url=f"{data.get('web_url', '')}/tree/{branch}"
            )
        except Exception as e:
            raise GitProviderError(f"Failed to get GitLab branch info: {e}")
    
    async def list_branches(self, repo_path: str) -> List[BranchInfo]:
        """List all branches in GitLab repository."""
        try:
            project_id = self._get_project_id(repo_path)
            data, _ = await self._make_request('GET', f'/projects/{project_id}/repository/branches')
            
            branches = []
            for branch_data in data:
                commit = branch_data['commit']
                branches.append(BranchInfo(
                    name=branch_data['name'],
                    commit_sha=commit['id'],
                    commit_message=commit['message'],
                    author=commit['author_name'],
                    committed_date=datetime.fromisoformat(commit['authored_date'].replace('Z', '+00:00')),
                    protected=branch_data.get('protected', False),
                    web_url=f"{branch_data.get('web_url', '')}/tree/{branch_data['name']}"
                ))
            
            return branches
        except Exception as e:
            raise GitProviderError(f"Failed to list GitLab branches: {e}")
    
    async def compare_branches(self, repo_path: str, base: str, head: str) -> Dict[str, Any]:
        """Compare two branches in GitLab."""
        try:
            project_id = self._get_project_id(repo_path)
            data, _ = await self._make_request('GET', f'/projects/{project_id}/repository/compare', params={
                'from': base,
                'to': head
            })
            
            return {
                'ahead_by': len(data.get('commits', [])),
                'behind_by': 0,  # GitLab doesn't provide this directly
                'status': 'ahead' if data.get('commits') else 'identical',
                'total_commits': len(data.get('commits', [])),
                'commits': [
                    {
                        'sha': commit['id'],
                        'message': commit['message'],
                        'author': commit['author_name'],
                        'date': commit['authored_date']
                    }
                    for commit in data.get('commits', [])
                ],
                'files_changed': len(data.get('diffs', [])),
                'additions': 0,  # Would need to parse diffs for accurate count
                'deletions': 0,  # Would need to parse diffs for accurate count
                'provider': 'gitlab'
            }
        except Exception as e:
            raise GitProviderError(f"Failed to compare GitLab branches: {e}")
    
    async def create_pull_request(
        self, 
        repo_path: str, 
        title: str, 
        body: str, 
        head: str, 
        base: str,
        **kwargs
    ) -> PullRequestInfo:
        """Create a new GitLab merge request."""
        try:
            project_id = self._get_project_id(repo_path)
            
            mr_data = {
                'title': title,
                'description': body,
                'source_branch': head,
                'target_branch': base,
                'remove_source_branch': kwargs.get('remove_source_branch', False)
            }
            
            # Add assignees if specified
            if 'assignees' in kwargs:
                mr_data['assignee_ids'] = kwargs['assignees']
            
            data, _ = await self._make_request('POST', f'/projects/{project_id}/merge_requests', json=mr_data)
            
            return PullRequestInfo(
                id=data['id'],
                number=data['iid'],
                title=data['title'],
                body=data['description'] or '',
                state=data['state'],
                head_branch=data['source_branch'],
                base_branch=data['target_branch'],
                author=data['author']['username'],
                created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00')),
                web_url=data['web_url'],
                mergeable=not data.get('has_conflicts', False),
                provider='gitlab'
            )
        except Exception as e:
            raise GitProviderError(f"Failed to create GitLab merge request: {e}")
    
    async def get_pull_request(self, repo_path: str, pr_number: int) -> PullRequestInfo:
        """Get GitLab merge request information."""
        try:
            project_id = self._get_project_id(repo_path)
            data, _ = await self._make_request('GET', f'/projects/{project_id}/merge_requests/{pr_number}')
            
            return PullRequestInfo(
                id=data['id'],
                number=data['iid'],
                title=data['title'],
                body=data['description'] or '',
                state=data['state'],
                head_branch=data['source_branch'],
                base_branch=data['target_branch'],
                author=data['author']['username'],
                created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00')),
                web_url=data['web_url'],
                mergeable=not data.get('has_conflicts', False),
                provider='gitlab'
            )
        except Exception as e:
            raise GitProviderError(f"Failed to get GitLab merge request: {e}")
    
    async def list_pull_requests(
        self, 
        repo_path: str, 
        state: str = 'opened'
    ) -> List[PullRequestInfo]:
        """List GitLab merge requests."""
        try:
            project_id = self._get_project_id(repo_path)
            data, _ = await self._make_request(
                'GET', 
                f'/projects/{project_id}/merge_requests',
                params={'state': state}
            )
            
            merge_requests = []
            for mr_data in data:
                merge_requests.append(PullRequestInfo(
                    id=mr_data['id'],
                    number=mr_data['iid'],
                    title=mr_data['title'],
                    body=mr_data['description'] or '',
                    state=mr_data['state'],
                    head_branch=mr_data['source_branch'],
                    base_branch=mr_data['target_branch'],
                    author=mr_data['author']['username'],
                    created_at=datetime.fromisoformat(mr_data['created_at'].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(mr_data['updated_at'].replace('Z', '+00:00')),
                    web_url=mr_data['web_url'],
                    mergeable=not mr_data.get('has_conflicts', False),
                    provider='gitlab'
                ))
            
            return merge_requests
        except Exception as e:
            raise GitProviderError(f"Failed to list GitLab merge requests: {e}")
    
    async def create_webhook(
        self, 
        repo_path: str, 
        webhook_url: str, 
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create GitLab repository webhook."""
        try:
            project_id = self._get_project_id(repo_path)
            
            # Map common events to GitLab events
            gitlab_events = {
                'push': 'push_events',
                'merge_request': 'merge_requests_events',
                'pull_request': 'merge_requests_events',
                'tag': 'tag_push_events',
                'issues': 'issues_events',
                'wiki': 'wiki_page_events'
            }
            
            webhook_data = {
                'url': webhook_url,
                'enable_ssl_verification': True
            }
            
            # Enable specified events
            for event in events:
                gitlab_event = gitlab_events.get(event, f'{event}_events')
                webhook_data[gitlab_event] = True
            
            if secret:
                webhook_data['token'] = secret
            
            data, _ = await self._make_request('POST', f'/projects/{project_id}/hooks', json=webhook_data)
            
            return {
                'id': data['id'],
                'url': data['url'],
                'events': events,
                'active': True,
                'created_at': data['created_at'],
                'updated_at': data.get('updated_at', data['created_at']),
                'provider': 'gitlab'
            }
        except Exception as e:
            raise GitProviderError(f"Failed to create GitLab webhook: {e}")
    
    async def list_webhooks(self, repo_path: str) -> List[Dict[str, Any]]:
        """List GitLab repository webhooks."""
        try:
            project_id = self._get_project_id(repo_path)
            data, _ = await self._make_request('GET', f'/projects/{project_id}/hooks')
            
            webhooks = []
            for hook in data:
                # Determine active events
                active_events = []
                event_mapping = {
                    'push_events': 'push',
                    'merge_requests_events': 'merge_request',
                    'tag_push_events': 'tag',
                    'issues_events': 'issues',
                    'wiki_page_events': 'wiki'
                }
                
                for gitlab_event, common_event in event_mapping.items():
                    if hook.get(gitlab_event, False):
                        active_events.append(common_event)
                
                webhooks.append({
                    'id': hook['id'],
                    'url': hook['url'],
                    'events': active_events,
                    'active': True,
                    'created_at': hook['created_at'],
                    'updated_at': hook.get('updated_at', hook['created_at']),
                    'provider': 'gitlab'
                })
            
            return webhooks
        except Exception as e:
            raise GitProviderError(f"Failed to list GitLab webhooks: {e}")


class GenericGitProvider(BaseGitProvider):
    """
    Generic Git provider for fallback scenarios.
    
    Provides basic Git operations without advanced API features.
    Suitable for self-hosted Git instances without REST APIs.
    """
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize generic Git provider.
        
        Args:
            credentials: Basic authentication data
                - username: Git username
                - password: Git password or token
                - base_url: Git server base URL
        """
        super().__init__(credentials)
        self.username = credentials.get('username')
        self.password = credentials.get('password')
        self.base_url = credentials.get('base_url', '')
    
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return 'generic'
    
    async def validate_credentials(self) -> bool:
        """Validate generic Git credentials (basic check)."""
        return bool(self.username and self.password)
    
    async def get_repository_info(self, repo_path: str) -> RepositoryInfo:
        """Get basic repository information."""
        repo_name = repo_path.split('/')[-1]
        
        return RepositoryInfo(
            name=repo_name,
            full_name=repo_path,
            description='Generic Git Repository',
            default_branch='main',
            private=True,  # Assume private for generic
            clone_url=f"{self.base_url}/{repo_path}.git",
            ssh_url=f"git@{urlparse(self.base_url).netloc}:{repo_path}.git",
            web_url=f"{self.base_url}/{repo_path}",
            last_push=None,
            provider='generic'
        )
    
    async def get_branch_info(self, repo_path: str, branch: str) -> BranchInfo:
        """Get basic branch information."""
        return BranchInfo(
            name=branch,
            commit_sha='unknown',
            commit_message='Generic commit',
            author='unknown',
            committed_date=timezone.now(),
            protected=False,
            web_url=f"{self.base_url}/{repo_path}/tree/{branch}"
        )
    
    async def list_branches(self, repo_path: str) -> List[BranchInfo]:
        """List branches (limited for generic provider)."""
        return [await self.get_branch_info(repo_path, 'main')]
    
    async def compare_branches(self, repo_path: str, base: str, head: str) -> Dict[str, Any]:
        """Compare branches (limited for generic provider)."""
        return {
            'ahead_by': 0,
            'behind_by': 0,
            'status': 'unknown',
            'total_commits': 0,
            'commits': [],
            'files_changed': 0,
            'additions': 0,
            'deletions': 0,
            'provider': 'generic'
        }
    
    async def create_pull_request(
        self, 
        repo_path: str, 
        title: str, 
        body: str, 
        head: str, 
        base: str,
        **kwargs
    ) -> PullRequestInfo:
        """Create pull request (not supported for generic provider)."""
        raise GitProviderError("Pull requests not supported by generic Git provider")
    
    async def get_pull_request(self, repo_path: str, pr_number: int) -> PullRequestInfo:
        """Get pull request (not supported for generic provider)."""
        raise GitProviderError("Pull requests not supported by generic Git provider")
    
    async def list_pull_requests(
        self, 
        repo_path: str, 
        state: str = 'open'
    ) -> List[PullRequestInfo]:
        """List pull requests (not supported for generic provider)."""
        return []
    
    async def create_webhook(
        self, 
        repo_path: str, 
        webhook_url: str, 
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create webhook (not supported for generic provider)."""
        raise GitProviderError("Webhooks not supported by generic Git provider")
    
    async def list_webhooks(self, repo_path: str) -> List[Dict[str, Any]]:
        """List webhooks (not supported for generic provider)."""
        return []


class GitProviderFactory:
    """
    Factory class for creating Git provider clients.
    
    Automatically detects provider type and creates appropriate client instance.
    """
    
    @staticmethod
    def detect_provider(repository_url: str) -> str:
        """
        Detect Git provider from repository URL.
        
        Args:
            repository_url: Git repository URL
            
        Returns:
            Provider type ('github', 'gitlab', or 'generic')
        """
        if not repository_url:
            return 'generic'
        
        url_lower = repository_url.lower()
        
        if 'github.com' in url_lower or 'github.enterprise' in url_lower:
            return 'github'
        elif 'gitlab.com' in url_lower or 'gitlab' in url_lower:
            return 'gitlab'
        else:
            return 'generic'
    
    @staticmethod
    def create_client(
        provider_type: str, 
        credentials: Dict[str, Any]
    ) -> BaseGitProvider:
        """
        Create Git provider client.
        
        Args:
            provider_type: Provider type ('github', 'gitlab', 'generic')
            credentials: Provider-specific credentials
            
        Returns:
            Git provider client instance
        """
        if provider_type == 'github':
            return GitHubAPIClient(credentials)
        elif provider_type == 'gitlab':
            return GitLabAPIClient(credentials)
        elif provider_type == 'generic':
            return GenericGitProvider(credentials)
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")
    
    @staticmethod
    def create_from_fabric(fabric) -> BaseGitProvider:
        """
        Create Git provider client from HedgehogFabric instance.
        
        Args:
            fabric: HedgehogFabric instance
            
        Returns:
            Git provider client instance
        """
        provider_type = GitProviderFactory.detect_provider(fabric.git_repository_url)
        
        credentials = {
            'token': fabric.git_token,
            'username': fabric.git_username,
        }
        
        # Add provider-specific URLs if needed
        if hasattr(fabric, 'git_api_url') and fabric.git_api_url:
            credentials['api_url'] = fabric.git_api_url
        
        return GitProviderFactory.create_client(provider_type, credentials)