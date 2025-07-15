"""
Test suite for GitRepository API endpoints
Tests CRUD operations, security, and custom actions
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from netbox_hedgehog.models import GitRepository, HedgehogFabric
from netbox_hedgehog.choices import (
    GitRepositoryProviderChoices, 
    GitAuthenticationTypeChoices, 
    GitConnectionStatusChoices
)


class GitRepositoryAPITest(TestCase):
    """Test cases for GitRepository API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create test repository
        self.repo = GitRepository.objects.create(
            name='Test Repository',
            url='https://github.com/test/repo.git',
            provider=GitRepositoryProviderChoices.GITHUB,
            authentication_type=GitAuthenticationTypeChoices.TOKEN,
            description='Test repository for API tests',
            created_by=self.user1
        )
        self.repo.set_credentials({'token': 'test_token_123'})
        self.repo.save()
        
        # API endpoints
        self.list_url = '/api/plugins/hedgehog/git-repositories/'
        self.detail_url = f'/api/plugins/hedgehog/git-repositories/{self.repo.id}/'
        self.test_connection_url = f'/api/plugins/hedgehog/git-repositories/{self.repo.id}/test_connection/'
        self.clone_url = f'/api/plugins/hedgehog/git-repositories/{self.repo.id}/clone/'
        self.dependent_fabrics_url = f'/api/plugins/hedgehog/git-repositories/{self.repo.id}/dependent_fabrics/'
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated requests are denied"""
        # List repositories
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Get repository detail
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Create repository
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_repositories_user_filtering(self):
        """Test that users only see their own repositories"""
        # Create repository for user2
        repo2 = GitRepository.objects.create(
            name='User 2 Repository',
            url='https://github.com/user2/repo.git',
            provider=GitRepositoryProviderChoices.GITHUB,
            authentication_type=GitAuthenticationTypeChoices.TOKEN,
            created_by=self.user2
        )
        
        # User1 should only see their repository
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['id'], self.repo.id)
        
        # User2 should only see their repository
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['id'], repo2.id)
        
        # Superuser should see all repositories
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(data['count'], 2)
    
    def test_get_repository_detail(self):
        """Test getting repository details"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(data['id'], self.repo.id)
        self.assertEqual(data['name'], 'Test Repository')
        self.assertEqual(data['url'], 'https://github.com/test/repo.git')
        self.assertEqual(data['provider'], GitRepositoryProviderChoices.GITHUB)
        self.assertEqual(data['authentication_type'], GitAuthenticationTypeChoices.TOKEN)
        self.assertTrue(data['has_credentials'])
        self.assertNotIn('credentials', data)  # Credentials should not be exposed
        
        # Check computed fields
        self.assertIn('connection_summary', data)
        self.assertIn('can_delete_info', data)
        self.assertIn('repository_info', data)
        self.assertIn('dependent_fabrics', data)
    
    def test_user_cannot_access_other_user_repository(self):
        """Test that users cannot access repositories they don't own"""
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_create_repository_with_token_auth(self):
        """Test creating repository with token authentication"""
        self.client.force_authenticate(user=self.user1)
        
        create_data = {
            'name': 'New Repository',
            'url': 'https://github.com/test/newrepo.git',
            'provider': GitRepositoryProviderChoices.GITHUB,
            'authentication_type': GitAuthenticationTypeChoices.TOKEN,
            'description': 'New test repository',
            'default_branch': 'main',
            'is_private': True,
            'credentials': {
                'token': 'github_pat_new123456'
            }
        }
        
        response = self.client.post(self.list_url, create_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        data = response.json()
        self.assertEqual(data['name'], 'New Repository')
        self.assertEqual(data['url'], 'https://github.com/test/newrepo.git')
        self.assertTrue(data['has_credentials'])
        
        # Verify repository was created in database
        repo = GitRepository.objects.get(id=data['id'])
        self.assertEqual(repo.created_by, self.user1)
        self.assertEqual(repo.get_credentials()['token'], 'github_pat_new123456')
    
    def test_create_repository_with_basic_auth(self):
        """Test creating repository with basic authentication"""
        self.client.force_authenticate(user=self.user1)
        
        create_data = {
            'name': 'Basic Auth Repository',
            'url': 'https://git.example.com/user/repo.git',
            'provider': GitRepositoryProviderChoices.GENERIC,
            'authentication_type': GitAuthenticationTypeChoices.BASIC,
            'credentials': {
                'username': 'testuser',
                'password': 'testpassword'
            }
        }
        
        response = self.client.post(self.list_url, create_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        data = response.json()
        self.assertEqual(data['authentication_type'], GitAuthenticationTypeChoices.BASIC)
        
        # Verify credentials were stored correctly
        repo = GitRepository.objects.get(id=data['id'])
        credentials = repo.get_credentials()
        self.assertEqual(credentials['username'], 'testuser')
        self.assertEqual(credentials['password'], 'testpassword')
    
    def test_create_repository_missing_credentials(self):
        """Test that creating repository without required credentials fails"""
        self.client.force_authenticate(user=self.user1)
        
        create_data = {
            'name': 'Missing Credentials Repository',
            'url': 'https://github.com/test/missing.git',
            'provider': GitRepositoryProviderChoices.GITHUB,
            'authentication_type': GitAuthenticationTypeChoices.TOKEN,
            # Missing credentials
        }
        
        response = self.client.post(self.list_url, create_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = response.json()
        self.assertIn('credentials', data)
    
    def test_create_repository_invalid_credentials(self):
        """Test creating repository with invalid credentials for auth type"""
        self.client.force_authenticate(user=self.user1)
        
        # Token auth but no token provided
        create_data = {
            'name': 'Invalid Credentials Repository',
            'url': 'https://github.com/test/invalid.git',
            'provider': GitRepositoryProviderChoices.GITHUB,
            'authentication_type': GitAuthenticationTypeChoices.TOKEN,
            'credentials': {
                'username': 'user'  # Wrong credential type
            }
        }
        
        response = self.client.post(self.list_url, create_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = response.json()
        self.assertIn('credentials', data)
    
    def test_update_repository(self):
        """Test updating repository details"""
        self.client.force_authenticate(user=self.user1)
        
        update_data = {
            'name': 'Updated Repository Name',
            'description': 'Updated description',
            'default_branch': 'develop',
            'timeout_seconds': 60
        }
        
        response = self.client.patch(self.detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(data['name'], 'Updated Repository Name')
        self.assertEqual(data['description'], 'Updated description')
        self.assertEqual(data['default_branch'], 'develop')
        self.assertEqual(data['timeout_seconds'], 60)
    
    def test_update_repository_credentials(self):
        """Test updating repository credentials"""
        self.client.force_authenticate(user=self.user1)
        
        update_data = {
            'credentials': {
                'token': 'new_updated_token_789'
            }
        }
        
        response = self.client.patch(self.detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify credentials were updated
        self.repo.refresh_from_db()
        credentials = self.repo.get_credentials()
        self.assertEqual(credentials['token'], 'new_updated_token_789')
    
    def test_delete_repository_success(self):
        """Test deleting repository when no fabrics depend on it"""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify repository was deleted
        self.assertFalse(GitRepository.objects.filter(id=self.repo.id).exists())
    
    def test_delete_repository_with_dependent_fabrics(self):
        """Test that deleting repository with dependent fabrics fails"""
        # Create fabric that uses this repository
        fabric = HedgehogFabric.objects.create(
            name='Test Fabric',
            git_repository=self.repo,
            gitops_directory='/test/'
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(self.detail_url)
        
        # Should fail because fabric depends on repository
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Cannot delete repository', data['error'])
        
        # Verify repository still exists
        self.assertTrue(GitRepository.objects.filter(id=self.repo.id).exists())
    
    @patch('netbox_hedgehog.models.git_repository.git.Repo')
    def test_test_connection_action_success(self, mock_git_repo):
        """Test successful connection test via API"""
        # Mock successful git operations
        mock_repo_instance = MagicMock()
        mock_remote = MagicMock()
        mock_repo_instance.create_remote.return_value = mock_remote
        mock_repo_instance.git.custom_environment.return_value.__enter__ = MagicMock()
        mock_repo_instance.git.custom_environment.return_value.__exit__ = MagicMock()
        
        mock_ref = MagicMock()
        mock_ref.remote_head = 'main'
        mock_ref.commit.hexsha = 'abc123def456'
        mock_remote.fetch.return_value = [mock_ref]
        
        mock_git_repo.init.return_value = mock_repo_instance
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(self.test_connection_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Successfully connected to repository')
        self.assertEqual(data['repository_url'], self.repo.url)
        self.assertEqual(data['current_commit'], 'abc123def456')
    
    @patch('netbox_hedgehog.models.git_repository.git.Repo')
    def test_test_connection_action_failure(self, mock_git_repo):
        """Test failed connection test via API"""
        # Mock failed git operations
        mock_git_repo.init.side_effect = Exception("Authentication failed")
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(self.test_connection_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Authentication failed', data['error'])
    
    @patch('netbox_hedgehog.models.git_repository.git.Repo')
    def test_clone_action_success(self, mock_git_repo):
        """Test successful repository clone via API"""
        # Mock successful clone
        mock_repo_instance = MagicMock()
        mock_repo_instance.head.commit.hexsha = 'abc123def456'
        mock_repo_instance.head.commit.message = 'Test commit'
        mock_git_repo.clone_from.return_value = mock_repo_instance
        
        self.client.force_authenticate(user=self.user1)
        clone_data = {
            'target_directory': '/tmp/test_clone',
            'branch': 'main'
        }
        
        response = self.client.post(self.clone_url, clone_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Successfully cloned repository', data['message'])
        self.assertEqual(data['repository_path'], '/tmp/test_clone')
        self.assertEqual(data['branch'], 'main')
        self.assertEqual(data['commit_sha'], 'abc123def456')
    
    def test_clone_action_missing_directory(self):
        """Test clone action with missing target directory"""
        self.client.force_authenticate(user=self.user1)
        clone_data = {
            'branch': 'main'
            # Missing target_directory
        }
        
        response = self.client.post(self.clone_url, clone_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = response.json()
        self.assertIn('target_directory', data)
    
    def test_dependent_fabrics_action(self):
        """Test getting dependent fabrics via API"""
        # Create fabrics that use this repository
        fabric1 = HedgehogFabric.objects.create(
            name='Test Fabric 1',
            git_repository=self.repo,
            gitops_directory='/app1/'
        )
        fabric2 = HedgehogFabric.objects.create(
            name='Test Fabric 2',
            git_repository=self.repo,
            gitops_directory='/app2/'
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.dependent_fabrics_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(data['repository_id'], self.repo.id)
        self.assertEqual(data['repository_name'], self.repo.name)
        self.assertEqual(data['dependent_fabrics_count'], 2)
        
        fabric_names = [f['name'] for f in data['dependent_fabrics']]
        self.assertIn('Test Fabric 1', fabric_names)
        self.assertIn('Test Fabric 2', fabric_names)
    
    def test_connection_summary_action(self):
        """Test getting connection summary via API"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/plugins/hedgehog/git-repositories/{self.repo.id}/connection_summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('is_connected', data)
        self.assertIn('needs_validation', data)
        self.assertIn('fabric_usage', data)
    
    def test_repository_info_action(self):
        """Test getting repository info via API"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/plugins/hedgehog/git-repositories/{self.repo.id}/repository_info/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('basic_info', data)
        self.assertIn('authentication', data)
        self.assertIn('connection', data)
        self.assertIn('repository_settings', data)
        self.assertIn('usage', data)
    
    def test_my_repositories_action(self):
        """Test getting current user's repositories"""
        # Create another repository for user1
        repo2 = GitRepository.objects.create(
            name='Second Repository',
            url='https://github.com/test/repo2.git',
            provider=GitRepositoryProviderChoices.GITHUB,
            authentication_type=GitAuthenticationTypeChoices.TOKEN,
            created_by=self.user1
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/plugins/hedgehog/git-repositories/my_repositories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(data['count'], 2)
        
        repo_names = [r['name'] for r in data['results']]
        self.assertIn('Test Repository', repo_names)
        self.assertIn('Second Repository', repo_names)
    
    def test_connection_status_summary_action(self):
        """Test getting connection status summary"""
        # Create additional repositories with different statuses
        repo2 = GitRepository.objects.create(
            name='Connected Repository',
            url='https://github.com/test/connected.git',
            provider=GitRepositoryProviderChoices.GITHUB,
            authentication_type=GitAuthenticationTypeChoices.TOKEN,
            connection_status=GitConnectionStatusChoices.CONNECTED,
            created_by=self.user1
        )
        repo3 = GitRepository.objects.create(
            name='Failed Repository',
            url='https://github.com/test/failed.git',
            provider=GitRepositoryProviderChoices.GITHUB,
            authentication_type=GitAuthenticationTypeChoices.TOKEN,
            connection_status=GitConnectionStatusChoices.FAILED,
            created_by=self.user1
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/plugins/hedgehog/git-repositories/connection_status_summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(data['total_repositories'], 3)
        self.assertIn('connection_status_counts', data)
        self.assertIn('connection_health', data)
        
        status_counts = data['connection_status_counts']
        self.assertEqual(status_counts['pending'], 1)  # self.repo
        self.assertEqual(status_counts['connected'], 1)  # repo2
        self.assertEqual(status_counts['failed'], 1)  # repo3
    
    def test_api_filtering(self):
        """Test API filtering capabilities"""
        # Create repositories with different providers and statuses
        repo2 = GitRepository.objects.create(
            name='GitLab Repository',
            url='https://gitlab.com/test/repo.git',
            provider=GitRepositoryProviderChoices.GITLAB,
            authentication_type=GitAuthenticationTypeChoices.BASIC,
            connection_status=GitConnectionStatusChoices.CONNECTED,
            created_by=self.user1
        )
        
        self.client.force_authenticate(user=self.user1)
        
        # Filter by provider
        response = self.client.get(f'{self.list_url}?provider={GitRepositoryProviderChoices.GITHUB}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['provider'], GitRepositoryProviderChoices.GITHUB)
        
        # Filter by authentication type
        response = self.client.get(f'{self.list_url}?authentication_type={GitAuthenticationTypeChoices.BASIC}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['authentication_type'], GitAuthenticationTypeChoices.BASIC)
        
        # Filter by connection status
        response = self.client.get(f'{self.list_url}?connection_status={GitConnectionStatusChoices.CONNECTED}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['connection_status'], GitConnectionStatusChoices.CONNECTED)
    
    def test_api_permissions(self):
        """Test API permission enforcement"""
        # Test that users cannot modify other users' repositories
        self.client.force_authenticate(user=self.user2)
        
        # Try to update repository owned by user1
        update_data = {'name': 'Unauthorized Update'}
        response = self.client.patch(self.detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Try to delete repository owned by user1
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Try to test connection on repository owned by user1
        response = self.client.post(self.test_connection_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_credential_security(self):
        """Test that credentials are never exposed in API responses"""
        self.client.force_authenticate(user=self.user1)
        
        # Check list endpoint
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        for repo_data in data['results']:
            self.assertNotIn('credentials', repo_data)
            self.assertNotIn('encrypted_credentials', repo_data)
            # Should have indicator that credentials exist
            self.assertIn('has_credentials', repo_data)
        
        # Check detail endpoint
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertNotIn('credentials', data)
        self.assertNotIn('encrypted_credentials', data)
        self.assertTrue(data['has_credentials'])
    
    def test_api_error_handling(self):
        """Test API error handling"""
        self.client.force_authenticate(user=self.user1)
        
        # Test invalid repository ID
        invalid_url = '/api/plugins/hedgehog/git-repositories/99999/'
        response = self.client.get(invalid_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Test invalid action
        invalid_action_url = f'/api/plugins/hedgehog/git-repositories/{self.repo.id}/invalid_action/'
        response = self.client.post(invalid_action_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Test invalid JSON in request body
        response = self.client.post(self.list_url, 'invalid json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)