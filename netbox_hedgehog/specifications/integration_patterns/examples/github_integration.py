#!/usr/bin/env python3
"""
GitHub Integration Example
Demonstrates GitHub API integration with authentication and error handling.
"""

import requests
import base64
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class GitHubIntegrationExample:
    """Example GitHub API integration"""
    
    def __init__(self, token: str, repository: str):
        """
        Initialize GitHub client
        
        Args:
            token: GitHub API token
            repository: Repository in format "owner/repo"
        """
        self.token = token
        self.repository = repository
        self.base_url = "https://api.github.com"
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        })
    
    def get_repository_info(self) -> Dict[str, Any]:
        """Get repository information"""
        try:
            response = self.session.get(f"{self.base_url}/repos/{self.repository}")
            response.raise_for_status()
            
            repo_info = response.json()
            return {
                'name': repo_info['name'],
                'full_name': repo_info['full_name'],
                'default_branch': repo_info['default_branch'],
                'private': repo_info['private'],
                'clone_url': repo_info['clone_url']
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to get repository info: {e}")
            raise
    
    def create_file(self, path: str, content: str, message: str, 
                   branch: str = 'main') -> Dict[str, Any]:
        """Create or update file in repository"""
        try:
            # Encode content to base64
            encoded_content = base64.b64encode(content.encode()).decode()
            
            # Get current file SHA if it exists
            current_sha = None
            try:
                file_response = self.session.get(
                    f"{self.base_url}/repos/{self.repository}/contents/{path}",
                    params={'ref': branch}
                )
                if file_response.status_code == 200:
                    current_sha = file_response.json()['sha']
            except:
                pass  # File doesn't exist yet
            
            # Prepare request body
            data = {
                'message': message,
                'content': encoded_content,
                'branch': branch
            }
            
            if current_sha:
                data['sha'] = current_sha
            
            # Create/update file
            response = self.session.put(
                f"{self.base_url}/repos/{self.repository}/contents/{path}",
                json=data
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"{'Updated' if current_sha else 'Created'} file: {path}")
            
            return {
                'action': 'updated' if current_sha else 'created',
                'path': path,
                'sha': result['content']['sha'],
                'commit_sha': result['commit']['sha']
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to create/update file {path}: {e}")
            raise

# Example usage
if __name__ == '__main__':
    # Example usage (requires valid token and repository)
    github = GitHubIntegrationExample(
        token='your-github-token',
        repository='owner/repo'
    )
    
    repo_info = github.get_repository_info()
    print(f"Repository: {repo_info['full_name']}")
    
    # Create example file
    result = github.create_file(
        path='example.yaml',
        content='example: configuration',
        message='Add example configuration'
    )
    print(f"File {result['action']}: {result['path']}")