"""
Sync Service Protocols

typing.Protocol definitions for synchronization operations:
- Kubernetes synchronization
- Git repository synchronization  
- GitHub integration and webhooks
"""

from typing import Protocol, List, Optional, Dict, Any, Tuple
from datetime import datetime


class KubernetesSyncService(Protocol):
    """Service protocol for Kubernetes synchronization operations"""
    
    def test_connection(self, fabric_id: int) -> Dict[str, Any]:
        """Test Kubernetes cluster connectivity"""
        ...
    
    def sync_resource_to_cluster(self, resource_id: int) -> Dict[str, Any]:
        """Apply single resource to Kubernetes cluster"""
        ...
    
    def sync_resource_from_cluster(self, resource_id: int) -> Dict[str, Any]:
        """Sync single resource state from Kubernetes cluster"""
        ...
    
    def sync_fabric_to_cluster(self, fabric_id: int, 
                              resource_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Apply all fabric resources to Kubernetes cluster"""
        ...
    
    def sync_fabric_from_cluster(self, fabric_id: int,
                               resource_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Sync all fabric resources from Kubernetes cluster"""
        ...
    
    def delete_resource_from_cluster(self, resource_id: int) -> Dict[str, Any]:
        """Delete resource from Kubernetes cluster"""
        ...
    
    def get_resource_status(self, resource_id: int) -> Dict[str, Any]:
        """Get resource status from Kubernetes cluster"""
        ...
    
    def list_cluster_resources(self, fabric_id: int, 
                             namespace: Optional[str] = None,
                             resource_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List resources in Kubernetes cluster"""
        ...
    
    def validate_resource_spec(self, resource_id: int) -> Dict[str, Any]:
        """Validate resource spec against Kubernetes schema"""
        ...
    
    def get_cluster_events(self, fabric_id: int, resource_name: Optional[str] = None,
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get Kubernetes events for fabric resources"""
        ...
    
    def watch_resource_changes(self, fabric_id: int, callback_url: str) -> Dict[str, Any]:
        """Set up watch for resource changes in cluster"""
        ...
    
    def get_sync_metrics(self, fabric_id: int) -> Dict[str, Any]:
        """Get Kubernetes sync performance metrics"""
        ...


class GitSyncService(Protocol):
    """Service protocol for Git repository synchronization operations"""
    
    def test_repository_connection(self, repo_id: int) -> Dict[str, Any]:
        """Test Git repository connectivity"""
        ...
    
    def clone_repository(self, repo_id: int, local_path: str) -> Dict[str, Any]:
        """Clone Git repository to local path"""
        ...
    
    def pull_changes(self, repo_id: int, branch: str = "main") -> Dict[str, Any]:
        """Pull latest changes from repository"""
        ...
    
    def push_changes(self, repo_id: int, commit_message: str,
                    author_name: str, author_email: str) -> Dict[str, Any]:
        """Push local changes to repository"""
        ...
    
    def create_branch(self, repo_id: int, branch_name: str,
                     source_branch: str = "main") -> Dict[str, Any]:
        """Create new branch in repository"""
        ...
    
    def list_branches(self, repo_id: int) -> List[str]:
        """List all branches in repository"""
        ...
    
    def list_commits(self, repo_id: int, branch: str = "main",
                    limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List commits in repository branch"""
        ...
    
    def get_commit_diff(self, repo_id: int, commit_sha: str) -> Dict[str, Any]:
        """Get diff for specific commit"""
        ...
    
    def list_files(self, repo_id: int, path: str = "/", 
                  branch: str = "main") -> List[Dict[str, Any]]:
        """List files in repository path"""
        ...
    
    def get_file_content(self, repo_id: int, file_path: str,
                        branch: str = "main") -> str:
        """Get content of file from repository"""
        ...
    
    def write_file(self, repo_id: int, file_path: str, content: str,
                  commit_message: str, author_name: str, author_email: str) -> Dict[str, Any]:
        """Write file to repository"""
        ...
    
    def delete_file(self, repo_id: int, file_path: str,
                   commit_message: str, author_name: str, author_email: str) -> Dict[str, Any]:
        """Delete file from repository"""
        ...
    
    def sync_resources_to_git(self, fabric_id: int, resource_ids: List[int],
                            commit_message: str, author_name: str, author_email: str) -> Dict[str, Any]:
        """Sync resources to Git repository as YAML files"""
        ...
    
    def sync_resources_from_git(self, fabric_id: int, 
                              file_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """Sync resources from Git repository YAML files"""
        ...
    
    def get_repository_metrics(self, repo_id: int) -> Dict[str, Any]:
        """Get Git repository sync metrics"""
        ...


class GitHubSyncService(Protocol):
    """Service protocol for GitHub integration operations"""
    
    def create_pull_request(self, repo_id: int, title: str, description: str,
                          head_branch: str, base_branch: str = "main") -> Dict[str, Any]:
        """Create pull request on GitHub"""
        ...
    
    def list_pull_requests(self, repo_id: int, state: str = "open") -> List[Dict[str, Any]]:
        """List pull requests in repository"""
        ...
    
    def get_pull_request(self, repo_id: int, pr_number: int) -> Dict[str, Any]:
        """Get specific pull request details"""
        ...
    
    def merge_pull_request(self, repo_id: int, pr_number: int,
                         merge_method: str = "squash") -> Dict[str, Any]:
        """Merge pull request"""
        ...
    
    def close_pull_request(self, repo_id: int, pr_number: int) -> Dict[str, Any]:
        """Close pull request without merging"""
        ...
    
    def add_pull_request_comment(self, repo_id: int, pr_number: int,
                               comment: str) -> Dict[str, Any]:
        """Add comment to pull request"""
        ...
    
    def request_pull_request_review(self, repo_id: int, pr_number: int,
                                  reviewers: List[str]) -> Dict[str, Any]:
        """Request review for pull request"""
        ...
    
    def create_issue(self, repo_id: int, title: str, body: str,
                    labels: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create GitHub issue"""
        ...
    
    def list_issues(self, repo_id: int, state: str = "open") -> List[Dict[str, Any]]:
        """List issues in repository"""
        ...
    
    def create_release(self, repo_id: int, tag_name: str, name: str,
                      body: str, draft: bool = False) -> Dict[str, Any]:
        """Create GitHub release"""
        ...
    
    def list_releases(self, repo_id: int) -> List[Dict[str, Any]]:
        """List releases in repository"""
        ...
    
    def setup_webhook(self, repo_id: int, webhook_url: str,
                     events: List[str]) -> Dict[str, Any]:
        """Set up GitHub webhook for repository"""
        ...
    
    def handle_webhook(self, payload: Dict[str, Any], signature: str) -> Dict[str, Any]:
        """Handle incoming GitHub webhook"""
        ...
    
    def validate_webhook_signature(self, payload: bytes, signature: str,
                                 secret: str) -> bool:
        """Validate GitHub webhook signature"""
        ...
    
    def get_repository_info(self, repo_id: int) -> Dict[str, Any]:
        """Get GitHub repository information"""
        ...
    
    def get_user_permissions(self, repo_id: int, username: str) -> Dict[str, Any]:
        """Get user permissions for repository"""
        ...
    
    def get_github_metrics(self, repo_id: int) -> Dict[str, Any]:
        """Get GitHub integration metrics"""
        ...


class WebhookService(Protocol):
    """Service protocol for webhook management"""
    
    def register_webhook(self, source: str, events: List[str], 
                        callback_url: str, secret: Optional[str] = None) -> str:
        """Register webhook with external service"""
        ...
    
    def unregister_webhook(self, webhook_id: str) -> bool:
        """Unregister webhook"""
        ...
    
    def handle_github_webhook(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GitHub webhook event"""
        ...
    
    def handle_kubernetes_webhook(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Kubernetes webhook event"""
        ...
    
    def get_webhook_history(self, webhook_id: str, 
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get webhook delivery history"""
        ...
    
    def retry_webhook_delivery(self, delivery_id: str) -> Dict[str, Any]:
        """Retry failed webhook delivery"""
        ...
    
    def get_webhook_metrics(self, webhook_id: Optional[str] = None) -> Dict[str, Any]:
        """Get webhook delivery metrics"""
        ...