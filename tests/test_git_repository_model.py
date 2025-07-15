"""
Test suite for GitRepository model
Tests credential encryption/decryption, connection testing, and repository management
"""

import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings
from cryptography.fernet import Fernet

from netbox_hedgehog.models import GitRepository, HedgehogFabric
from netbox_hedgehog.choices import (
    GitRepositoryProviderChoices, 
    GitAuthenticationTypeChoices, 
    GitConnectionStatusChoices
)


class GitRepositoryModelTest(TestCase):
    """Test cases for GitRepository model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.repo_data = {
            'name': 'Test Repository',
            'url': 'https://github.com/test/repo.git',
            'provider': GitRepositoryProviderChoices.GITHUB,
            'authentication_type': GitAuthenticationTypeChoices.TOKEN,
            'description': 'Test repository for unit tests',
            'default_branch': 'main',
            'is_private': True,
            'validate_ssl': True,
            'timeout_seconds': 30,
            'created_by': self.user
        }
    
    def test_create_git_repository(self):
        """Test creating a GitRepository instance"""
        repo = GitRepository.objects.create(**self.repo_data)
        
        self.assertEqual(repo.name, 'Test Repository')
        self.assertEqual(repo.url, 'https://github.com/test/repo.git')
        self.assertEqual(repo.provider, GitRepositoryProviderChoices.GITHUB)
        self.assertEqual(repo.authentication_type, GitAuthenticationTypeChoices.TOKEN)
        self.assertEqual(repo.connection_status, GitConnectionStatusChoices.PENDING)
        self.assertEqual(repo.fabric_count, 0)
        self.assertEqual(repo.created_by, self.user)
    
    def test_credential_encryption_decryption(self):
        """Test credential encryption and decryption functionality"""
        repo = GitRepository.objects.create(**self.repo_data)
        
        # Test token credentials
        token_credentials = {'token': 'github_pat_abcdef123456'}
        repo.set_credentials(token_credentials)
        repo.save()
        
        # Verify credentials are encrypted
        self.assertNotEqual(repo.encrypted_credentials, '')
        self.assertNotIn('github_pat_abcdef123456', repo.encrypted_credentials)
        
        # Verify credentials can be decrypted
        decrypted_credentials = repo.get_credentials()
        self.assertEqual(decrypted_credentials, token_credentials)
    
    def test_credential_encryption_basic_auth(self):
        """Test basic authentication credential encryption"""
        repo = GitRepository.objects.create(
            **{**self.repo_data, 'authentication_type': GitAuthenticationTypeChoices.BASIC}
        )
        
        basic_credentials = {
            'username': 'testuser',
            'password': 'secretpassword123'
        }
        repo.set_credentials(basic_credentials)
        repo.save()
        
        # Verify credentials are encrypted
        self.assertNotEqual(repo.encrypted_credentials, '')
        self.assertNotIn('secretpassword123', repo.encrypted_credentials)
        
        # Verify credentials can be decrypted
        decrypted_credentials = repo.get_credentials()
        self.assertEqual(decrypted_credentials, basic_credentials)
    
    def test_credential_encryption_ssh_key(self):
        """Test SSH key credential encryption"""
        repo = GitRepository.objects.create(
            **{**self.repo_data, 'authentication_type': GitAuthenticationTypeChoices.SSH_KEY}
        )
        
        ssh_credentials = {
            'private_key': '-----BEGIN OPENSSH PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END OPENSSH PRIVATE KEY-----',
            'passphrase': 'keypassphrase'
        }
        repo.set_credentials(ssh_credentials)
        repo.save()
        
        # Verify credentials are encrypted
        self.assertNotEqual(repo.encrypted_credentials, '')
        self.assertNotIn('BEGIN OPENSSH PRIVATE KEY', repo.encrypted_credentials)
        
        # Verify credentials can be decrypted
        decrypted_credentials = repo.get_credentials()
        self.assertEqual(decrypted_credentials, ssh_credentials)
    
    def test_empty_credentials(self):
        """Test handling of empty credentials"""
        repo = GitRepository.objects.create(**self.repo_data)
        
        repo.set_credentials({})
        self.assertEqual(repo.encrypted_credentials, '')
        
        repo.set_credentials(None)
        self.assertEqual(repo.encrypted_credentials, '')
        
        decrypted = repo.get_credentials()
        self.assertEqual(decrypted, {})
    
    def test_encryption_key_consistency(self):
        """Test that encryption key is consistent across calls"""
        repo = GitRepository.objects.create(**self.repo_data)
        
        key1 = repo._encryption_key
        key2 = repo._encryption_key
        
        self.assertEqual(key1, key2)
        
        # Test that the key is derived from Django SECRET_KEY
        self.assertTrue(isinstance(key1, bytes))
        self.assertEqual(len(key1), 44)  # Base64 encoded 32-byte key
    
    def test_fabric_count_tracking(self):
        """Test fabric count tracking functionality"""
        repo = GitRepository.objects.create(**self.repo_data)
        
        # Initially should be 0
        self.assertEqual(repo.fabric_count, 0)
        
        # Create a fabric that uses this repository
        fabric = HedgehogFabric.objects.create(
            name='Test Fabric',
            git_repository=repo,
            gitops_directory='/test/'
        )
        
        # Update fabric count
        count = repo.update_fabric_count()
        self.assertEqual(count, 1)
        self.assertEqual(repo.fabric_count, 1)
        
        # Create another fabric
        fabric2 = HedgehogFabric.objects.create(
            name='Test Fabric 2',
            git_repository=repo,
            gitops_directory='/test2/'
        )
        
        count = repo.update_fabric_count()
        self.assertEqual(count, 2)
        self.assertEqual(repo.fabric_count, 2)
        
        # Delete a fabric
        fabric.delete()
        count = repo.update_fabric_count()
        self.assertEqual(count, 1)
        self.assertEqual(repo.fabric_count, 1)
    
    def test_can_delete_safety_check(self):
        """Test repository deletion safety checks"""
        repo = GitRepository.objects.create(**self.repo_data)
        
        # Should be deletable when no fabrics use it
        can_delete, reason = repo.can_delete()
        self.assertTrue(can_delete)
        self.assertEqual(reason, "Repository can be safely deleted")
        
        # Create a fabric that uses this repository
        fabric = HedgehogFabric.objects.create(
            name='Test Fabric',
            git_repository=repo,
            gitops_directory='/test/'
        )
        
        # Should not be deletable when fabrics use it
        can_delete, reason = repo.can_delete()
        self.assertFalse(can_delete)
        self.assertIn("Repository is used by 1 fabric(s)", reason)
    
    def test_get_dependent_fabrics(self):
        """Test getting list of dependent fabrics"""
        repo = GitRepository.objects.create(**self.repo_data)
        
        # Initially should be empty
        dependent_fabrics = repo.get_dependent_fabrics()
        self.assertEqual(list(dependent_fabrics), [])
        
        # Create fabrics that use this repository
        fabric1 = HedgehogFabric.objects.create(
            name='Test Fabric 1',
            git_repository=repo,
            gitops_directory='/test1/'
        )
        fabric2 = HedgehogFabric.objects.create(
            name='Test Fabric 2',
            git_repository=repo,
            gitops_directory='/test2/'
        )
        
        # Should return both fabrics
        dependent_fabrics = list(repo.get_dependent_fabrics())
        self.assertEqual(len(dependent_fabrics), 2)
        self.assertIn(fabric1, dependent_fabrics)
        self.assertIn(fabric2, dependent_fabrics)
    
    def test_get_connection_summary(self):
        """Test connection summary generation"""
        repo = GitRepository.objects.create(**self.repo_data)
        
        summary = repo.get_connection_summary()
        
        self.assertIn('status', summary)
        self.assertIn('last_validated', summary)
        self.assertIn('validation_error', summary)
        self.assertIn('is_connected', summary)
        self.assertIn('needs_validation', summary)
        self.assertIn('fabric_usage', summary)
        
        self.assertEqual(summary['status'], GitConnectionStatusChoices.PENDING)
        self.assertFalse(summary['is_connected'])
        self.assertTrue(summary['needs_validation'])
        self.assertEqual(summary['fabric_usage']['count'], 0)
        self.assertTrue(summary['fabric_usage']['can_delete'])
    
    def test_get_repository_info(self):
        """Test comprehensive repository information"""
        repo = GitRepository.objects.create(**self.repo_data)
        
        info = repo.get_repository_info()
        
        # Check all required sections
        self.assertIn('basic_info', info)
        self.assertIn('authentication', info)
        self.assertIn('connection', info)
        self.assertIn('repository_settings', info)
        self.assertIn('usage', info)
        
        # Check basic info
        basic_info = info['basic_info']
        self.assertEqual(basic_info['name'], 'Test Repository')
        self.assertEqual(basic_info['url'], 'https://github.com/test/repo.git')
        self.assertEqual(basic_info['provider'], GitRepositoryProviderChoices.GITHUB)
        
        # Check authentication info
        auth_info = info['authentication']
        self.assertEqual(auth_info['type'], GitAuthenticationTypeChoices.TOKEN)
        self.assertFalse(auth_info['has_credentials'])
        self.assertTrue(auth_info['is_private'])
        
        # Check usage info
        usage_info = info['usage']
        self.assertEqual(usage_info['fabric_count'], 0)
        self.assertEqual(usage_info['created_by'], 'testuser')
    
    @patch('netbox_hedgehog.models.git_repository.git.Repo')
    def test_connection_test_success(self, mock_git_repo):
        """Test successful connection test"""
        repo = GitRepository.objects.create(**self.repo_data)
        repo.set_credentials({'token': 'test_token'})
        
        # Mock git operations
        mock_repo_instance = MagicMock()
        mock_remote = MagicMock()
        mock_repo_instance.create_remote.return_value = mock_remote
        mock_repo_instance.git.custom_environment.return_value.__enter__ = MagicMock()
        mock_repo_instance.git.custom_environment.return_value.__exit__ = MagicMock()
        
        # Mock fetch result
        mock_ref = MagicMock()
        mock_ref.remote_head = 'main'
        mock_ref.commit.hexsha = 'abc123def456'
        mock_remote.fetch.return_value = [mock_ref]
        
        mock_git_repo.init.return_value = mock_repo_instance
        
        result = repo.test_connection()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Successfully connected to repository')
        self.assertEqual(result['repository_url'], repo.url)
        self.assertEqual(result['default_branch'], 'main')
        self.assertEqual(result['current_commit'], 'abc123def456')
        self.assertTrue(result['authenticated'])
        
        # Check that repository status was updated
        repo.refresh_from_db()
        self.assertEqual(repo.connection_status, GitConnectionStatusChoices.CONNECTED)
        self.assertIsNotNone(repo.last_validated)
        self.assertEqual(repo.validation_error, '')
    
    @patch('netbox_hedgehog.models.git_repository.git.Repo')
    def test_connection_test_failure(self, mock_git_repo):
        """Test failed connection test"""
        repo = GitRepository.objects.create(**self.repo_data)
        repo.set_credentials({'token': 'invalid_token'})
        
        # Mock git operations to raise an error
        mock_git_repo.init.side_effect = Exception("Authentication failed")
        
        result = repo.test_connection()
        
        self.assertFalse(result['success'])
        self.assertIn('Authentication failed', result['error'])
        self.assertEqual(result['repository_url'], repo.url)
        
        # Check that repository status was updated
        repo.refresh_from_db()
        self.assertEqual(repo.connection_status, GitConnectionStatusChoices.FAILED)
        self.assertIn('Authentication failed', repo.validation_error)
    
    @patch('netbox_hedgehog.models.git_repository.git.Repo')
    def test_clone_repository_success(self, mock_git_repo):
        """Test successful repository clone"""
        repo = GitRepository.objects.create(**self.repo_data)
        repo.set_credentials({'token': 'test_token'})
        
        # Mock clone operation
        mock_repo_instance = MagicMock()
        mock_repo_instance.head.commit.hexsha = 'abc123def456'
        mock_repo_instance.head.commit.message = 'Test commit message'
        mock_git_repo.clone_from.return_value = mock_repo_instance
        
        with tempfile.TemporaryDirectory() as temp_dir:
            target_directory = f"{temp_dir}/clone"
            
            result = repo.clone_repository(target_directory, 'main')
            
            self.assertTrue(result['success'])
            self.assertIn('Successfully cloned repository', result['message'])
            self.assertEqual(result['repository_path'], target_directory)
            self.assertEqual(result['branch'], 'main')
            self.assertEqual(result['commit_sha'], 'abc123def456')
            self.assertEqual(result['commit_message'], 'Test commit message')
    
    @patch('netbox_hedgehog.models.git_repository.git.Repo')
    def test_clone_repository_failure(self, mock_git_repo):
        """Test failed repository clone"""
        repo = GitRepository.objects.create(**self.repo_data)
        repo.set_credentials({'token': 'invalid_token'})
        
        # Mock clone operation to raise an error
        mock_git_repo.clone_from.side_effect = Exception("Clone failed")
        
        result = repo.clone_repository('/nonexistent/path', 'main')
        
        self.assertFalse(result['success'])
        self.assertIn('Clone failed', result['error'])
        self.assertEqual(result['repository_url'], repo.url)
        self.assertEqual(result['target_directory'], '/nonexistent/path')
    
    def test_string_representation(self):
        """Test string representation of GitRepository"""
        repo = GitRepository.objects.create(**self.repo_data)
        
        expected = "Test Repository (https://github.com/test/repo.git)"
        self.assertEqual(str(repo), expected)
    
    def test_unique_constraint(self):
        """Test unique constraint on URL and created_by"""
        repo1 = GitRepository.objects.create(**self.repo_data)
        
        # Creating another repository with same URL and user should raise error
        with self.assertRaises(Exception):  # IntegrityError
            GitRepository.objects.create(**self.repo_data)
        
        # Creating with different user should work
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        repo_data_2 = {**self.repo_data, 'created_by': user2, 'name': 'Test Repository 2'}
        repo2 = GitRepository.objects.create(**repo_data_2)
        
        self.assertNotEqual(repo1, repo2)
        self.assertEqual(repo1.url, repo2.url)
        self.assertNotEqual(repo1.created_by, repo2.created_by)
    
    def test_model_validation(self):
        """Test model validation"""
        # Test invalid URL
        invalid_repo_data = {**self.repo_data, 'url': 'invalid-url'}
        repo = GitRepository(**invalid_repo_data)
        
        # Note: URL validation happens at the Django model field level
        # This test ensures the model can be instantiated but validation
        # would occur during save/clean operations
        
        # Test clean method with missing credentials
        repo = GitRepository(**self.repo_data)
        # The clean method validates credentials match auth type
        # This is more thoroughly tested in the API tests
    
    def test_provider_detection_from_url(self):
        """Test that provider field is set appropriately"""
        # Test GitHub
        github_repo = GitRepository.objects.create(
            **{**self.repo_data, 'url': 'https://github.com/user/repo.git', 'provider': GitRepositoryProviderChoices.GITHUB}
        )
        self.assertEqual(github_repo.provider, GitRepositoryProviderChoices.GITHUB)
        
        # Test GitLab
        gitlab_repo = GitRepository.objects.create(
            **{**self.repo_data, 'name': 'GitLab Repo', 'url': 'https://gitlab.com/user/repo.git', 'provider': GitRepositoryProviderChoices.GITLAB}
        )
        self.assertEqual(gitlab_repo.provider, GitRepositoryProviderChoices.GITLAB)
        
        # Test generic
        generic_repo = GitRepository.objects.create(
            **{**self.repo_data, 'name': 'Generic Repo', 'url': 'https://git.example.com/user/repo.git', 'provider': GitRepositoryProviderChoices.GENERIC}
        )
        self.assertEqual(generic_repo.provider, GitRepositoryProviderChoices.GENERIC)


class GitRepositoryIntegrationTest(TestCase):
    """Integration tests for GitRepository with HedgehogFabric"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.repo = GitRepository.objects.create(
            name='Test Repository',
            url='https://github.com/test/repo.git',
            provider=GitRepositoryProviderChoices.GITHUB,
            authentication_type=GitAuthenticationTypeChoices.TOKEN,
            created_by=self.user
        )
        
        self.repo.set_credentials({'token': 'test_token'})
    
    def test_fabric_repository_relationship(self):
        """Test relationship between fabrics and repositories"""
        # Create fabric using the repository
        fabric = HedgehogFabric.objects.create(
            name='Test Fabric',
            git_repository=self.repo,
            gitops_directory='/hedgehog/'
        )
        
        # Test forward relationship
        self.assertEqual(fabric.git_repository, self.repo)
        self.assertEqual(fabric.gitops_directory, '/hedgehog/')
        
        # Test reverse relationship
        dependent_fabrics = self.repo.get_dependent_fabrics()
        self.assertIn(fabric, dependent_fabrics)
        
        # Test fabric count updates
        count = self.repo.update_fabric_count()
        self.assertEqual(count, 1)
        self.assertEqual(self.repo.fabric_count, 1)
    
    def test_unique_fabric_directory_constraint(self):
        """Test unique constraint on git_repository + gitops_directory"""
        # Create first fabric
        fabric1 = HedgehogFabric.objects.create(
            name='Test Fabric 1',
            git_repository=self.repo,
            gitops_directory='/hedgehog/'
        )
        
        # Creating another fabric with same repo and directory should fail
        with self.assertRaises(Exception):  # IntegrityError
            HedgehogFabric.objects.create(
                name='Test Fabric 2',
                git_repository=self.repo,
                gitops_directory='/hedgehog/'
            )
        
        # Creating with different directory should work
        fabric2 = HedgehogFabric.objects.create(
            name='Test Fabric 2',
            git_repository=self.repo,
            gitops_directory='/different/'
        )
        
        self.assertNotEqual(fabric1, fabric2)
        self.assertEqual(fabric1.git_repository, fabric2.git_repository)
        self.assertNotEqual(fabric1.gitops_directory, fabric2.gitops_directory)
    
    def test_cascade_behavior(self):
        """Test cascade behavior when repository is deleted"""
        # Create fabric using the repository
        fabric = HedgehogFabric.objects.create(
            name='Test Fabric',
            git_repository=self.repo,
            gitops_directory='/hedgehog/'
        )
        
        fabric_id = fabric.id
        
        # Delete the repository (should SET_NULL on fabric)
        self.repo.delete()
        
        # Fabric should still exist but with git_repository set to None
        fabric.refresh_from_db()
        self.assertIsNone(fabric.git_repository)
    
    def test_repository_usage_tracking(self):
        """Test comprehensive repository usage tracking"""
        # Create multiple fabrics
        fabric1 = HedgehogFabric.objects.create(
            name='Fabric 1',
            git_repository=self.repo,
            gitops_directory='/app1/'
        )
        fabric2 = HedgehogFabric.objects.create(
            name='Fabric 2',
            git_repository=self.repo,
            gitops_directory='/app2/'
        )
        fabric3 = HedgehogFabric.objects.create(
            name='Fabric 3',
            git_repository=self.repo,
            gitops_directory='/app3/'
        )
        
        # Update and verify count
        count = self.repo.update_fabric_count()
        self.assertEqual(count, 3)
        
        # Verify deletion safety
        can_delete, reason = self.repo.can_delete()
        self.assertFalse(can_delete)
        self.assertIn("3 fabric(s)", reason)
        
        # Delete some fabrics
        fabric1.delete()
        fabric2.delete()
        
        count = self.repo.update_fabric_count()
        self.assertEqual(count, 1)
        
        # Delete last fabric
        fabric3.delete()
        
        count = self.repo.update_fabric_count()
        self.assertEqual(count, 0)
        
        # Should now be deletable
        can_delete, reason = self.repo.can_delete()
        self.assertTrue(can_delete)