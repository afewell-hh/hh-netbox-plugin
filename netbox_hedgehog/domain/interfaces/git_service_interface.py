"""
Git Service Interface
Abstract interface for Git operations to enable dependency injection
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class GitReference:
    """Git reference information"""
    commit_sha: str
    branch: str
    local_path: str
    repository_url: str


@dataclass
class GitSyncResult:
    """Git synchronization result"""
    success: bool
    commit_sha: str
    files_found: int
    manifests_parsed: int
    crds_created: int
    crds_updated: int
    errors: List[str]
    
    @property
    def total_processed(self) -> int:
        return self.crds_created + self.crds_updated


class GitServiceInterface(ABC):
    """Abstract interface for Git operations"""
    
    @abstractmethod
    def clone_repository(self, url: str, branch: str, local_path: str, 
                        username: Optional[str] = None, token: Optional[str] = None) -> GitReference:
        """
        Clone Git repository to local path.
        
        Args:
            url: Git repository URL
            branch: Branch to clone
            local_path: Local directory path
            username: Git username (optional)
            token: Git access token (optional)
            
        Returns:
            GitReference with commit and path information
            
        Raises:
            GitError: If clone operation fails
        """
        pass
    
    @abstractmethod
    def list_yaml_files(self, repo_path: str, directory: str = "") -> List[str]:
        """
        List YAML files in repository directory.
        
        Args:
            repo_path: Path to local repository
            directory: Subdirectory to search (empty for root)
            
        Returns:
            List of YAML file paths relative to repo_path
        """
        pass
    
    @abstractmethod
    def get_latest_commit(self, repo_path: str) -> str:
        """
        Get latest commit SHA.
        
        Args:
            repo_path: Path to local repository
            
        Returns:
            Latest commit SHA
        """
        pass
    
    @abstractmethod
    def validate_repository(self, url: str, branch: str,
                          username: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate Git repository access without cloning.
        
        Args:
            url: Git repository URL
            branch: Branch to validate
            username: Git username (optional)
            token: Git access token (optional)
            
        Returns:
            Validation result with status and details
        """
        pass
    
    @abstractmethod
    def cleanup_repository(self, local_path: str) -> None:
        """
        Clean up local repository directory.
        
        Args:
            local_path: Path to local repository to remove
        """
        pass