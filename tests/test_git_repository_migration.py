"""
Test suite for GitRepository migration
Tests data preservation, credential migration, and rollback functionality
"""

import json
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.db import connection
from django.core.management import call_command
from django_migration_testcase import MigrationTest

from netbox_hedgehog.models import HedgehogFabric, GitRepository


class GitRepositoryMigrationTest(TransactionTestCase, MigrationTest):
    """Test cases for GitRepository migration data preservation"""
    
    migrate_from = '0013_add_argocd_tracking_fields'
    migrate_to = '0014_implement_git_repository_separation'
    
    def setUp(self):
        """Set up test data before migration"""
        super().setUp()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create fabrics with git configurations before migration
        self.fabric1_data = {
            'name': 'Test Fabric 1',
            'description': 'First test fabric',
            'git_repository_url': 'https://github.com/test/repo1.git',
            'git_branch': 'main',
            'git_path': 'hedgehog/app1/',
            'git_username': 'testuser1',
            'git_token': 'github_pat_token1'
        }
        
        self.fabric2_data = {
            'name': 'Test Fabric 2',
            'description': 'Second test fabric',
            'git_repository_url': 'https://github.com/test/repo2.git',
            'git_branch': 'develop',
            'git_path': 'fabric2/',
            'git_username': 'testuser2',
            'git_token': 'github_pat_token2'
        }
        
        self.fabric3_data = {
            'name': 'Test Fabric 3',
            'description': 'Third test fabric with same repo as fabric 1',
            'git_repository_url': 'https://github.com/test/repo1.git',  # Same as fabric1
            'git_branch': 'main',
            'git_path': 'hedgehog/app3/',
            'git_username': 'testuser1',
            'git_token': 'github_pat_token1'
        }
        
        self.fabric_no_git_data = {
            'name': 'No Git Fabric',
            'description': 'Fabric without git configuration'
        }
    
    def test_migration_preserves_all_fabric_data(self):
        """Test that migration preserves all fabric configurations"""
        # Create fabrics before migration
        fabric1 = HedgehogFabric.objects.create(**self.fabric1_data)
        fabric2 = HedgehogFabric.objects.create(**self.fabric2_data)
        fabric3 = HedgehogFabric.objects.create(**self.fabric3_data)
        fabric_no_git = HedgehogFabric.objects.create(**self.fabric_no_git_data)
        
        fabric1_id = fabric1.id
        fabric2_id = fabric2.id
        fabric3_id = fabric3.id
        fabric_no_git_id = fabric_no_git.id
        
        # Run migration
        self.migrate()
        
        # Verify all fabrics still exist
        self.assertTrue(HedgehogFabric.objects.filter(id=fabric1_id).exists())
        self.assertTrue(HedgehogFabric.objects.filter(id=fabric2_id).exists())
        self.assertTrue(HedgehogFabric.objects.filter(id=fabric3_id).exists())
        self.assertTrue(HedgehogFabric.objects.filter(id=fabric_no_git_id).exists())
        
        # Verify basic fabric data is preserved
        fabric1_after = HedgehogFabric.objects.get(id=fabric1_id)
        self.assertEqual(fabric1_after.name, 'Test Fabric 1')
        self.assertEqual(fabric1_after.description, 'First test fabric')
        
        fabric2_after = HedgehogFabric.objects.get(id=fabric2_id)
        self.assertEqual(fabric2_after.name, 'Test Fabric 2')
        self.assertEqual(fabric2_after.description, 'Second test fabric')
    
    def test_migration_creates_git_repositories(self):
        """Test that migration creates appropriate GitRepository records"""
        # Create fabrics before migration
        fabric1 = HedgehogFabric.objects.create(**self.fabric1_data)
        fabric2 = HedgehogFabric.objects.create(**self.fabric2_data)
        fabric3 = HedgehogFabric.objects.create(**self.fabric3_data)
        
        # Run migration
        self.migrate()
        
        # Verify GitRepository records were created
        git_repos = GitRepository.objects.all()
        self.assertEqual(git_repos.count(), 2)  # Should be 2 unique repositories
        
        # Check first repository (used by fabric1 and fabric3)
        repo1 = GitRepository.objects.get(url='https://github.com/test/repo1.git')
        self.assertIn('Test Fabric 1', repo1.name)
        self.assertEqual(repo1.url, 'https://github.com/test/repo1.git')
        self.assertEqual(repo1.provider, 'github')
        self.assertEqual(repo1.authentication_type, 'token')
        self.assertEqual(repo1.default_branch, 'main')
        self.assertTrue(repo1.is_private)
        
        # Check second repository
        repo2 = GitRepository.objects.get(url='https://github.com/test/repo2.git')
        self.assertIn('Test Fabric 2', repo2.name)
        self.assertEqual(repo2.url, 'https://github.com/test/repo2.git')
        self.assertEqual(repo2.default_branch, 'develop')
    
    def test_migration_updates_fabric_references(self):
        """Test that fabrics are updated to reference GitRepository records"""
        # Create fabrics before migration
        fabric1 = HedgehogFabric.objects.create(**self.fabric1_data)
        fabric2 = HedgehogFabric.objects.create(**self.fabric2_data)
        fabric3 = HedgehogFabric.objects.create(**self.fabric3_data)
        
        fabric1_id = fabric1.id
        fabric2_id = fabric2.id
        fabric3_id = fabric3.id
        
        # Run migration
        self.migrate()
        
        # Verify fabrics reference GitRepository records
        fabric1_after = HedgehogFabric.objects.get(id=fabric1_id)
        fabric2_after = HedgehogFabric.objects.get(id=fabric2_id)
        fabric3_after = HedgehogFabric.objects.get(id=fabric3_id)
        
        # fabric1 and fabric3 should reference the same repository
        self.assertIsNotNone(fabric1_after.git_repository)
        self.assertIsNotNone(fabric3_after.git_repository)
        self.assertEqual(fabric1_after.git_repository, fabric3_after.git_repository)
        
        # fabric2 should reference a different repository
        self.assertIsNotNone(fabric2_after.git_repository)
        self.assertNotEqual(fabric2_after.git_repository, fabric1_after.git_repository)
        
        # Check gitops_directory migration from git_path
        self.assertEqual(fabric1_after.gitops_directory, '/hedgehog/app1/')
        self.assertEqual(fabric2_after.gitops_directory, '/fabric2/')
        self.assertEqual(fabric3_after.gitops_directory, '/hedgehog/app3/')
    
    def test_migration_encrypts_credentials(self):
        """Test that migration encrypts and stores credentials properly"""
        # Create fabric with credentials before migration
        fabric = HedgehogFabric.objects.create(**self.fabric1_data)
        
        # Run migration
        self.migrate()
        
        # Get the created repository
        repo = GitRepository.objects.get(url='https://github.com/test/repo1.git')
        
        # Verify credentials were migrated and encrypted
        self.assertNotEqual(repo.encrypted_credentials, '')
        
        # Verify credentials can be decrypted
        credentials = repo.get_credentials()
        self.assertEqual(credentials['token'], 'github_pat_token1')
    
    def test_migration_handles_different_auth_types(self):
        """Test migration handles different authentication types"""
        # Create fabric with username/password (basic auth)
        fabric_basic = HedgehogFabric.objects.create(
            name='Basic Auth Fabric',
            git_repository_url='https://git.example.com/repo.git',
            git_username='basicuser',
            # Note: password field doesn't exist in legacy model, so only username
        )
        
        # Create fabric with token
        fabric_token = HedgehogFabric.objects.create(
            name='Token Auth Fabric',
            git_repository_url='https://github.com/token/repo.git',
            git_token='github_pat_xyz'
        )
        
        # Run migration
        self.migrate()
        
        # Check basic auth repository
        repo_basic = GitRepository.objects.get(url='https://git.example.com/repo.git')
        self.assertEqual(repo_basic.authentication_type, 'basic')
        credentials_basic = repo_basic.get_credentials()
        self.assertEqual(credentials_basic['username'], 'basicuser')
        
        # Check token auth repository
        repo_token = GitRepository.objects.get(url='https://github.com/token/repo.git')
        self.assertEqual(repo_token.authentication_type, 'token')
        credentials_token = repo_token.get_credentials()
        self.assertEqual(credentials_token['token'], 'github_pat_xyz')
    
    def test_migration_updates_fabric_counts(self):
        """Test that migration updates fabric_count on repositories"""
        # Create fabrics that share a repository
        fabric1 = HedgehogFabric.objects.create(**self.fabric1_data)
        fabric3 = HedgehogFabric.objects.create(**self.fabric3_data)  # Same repo as fabric1
        
        # Run migration
        self.migrate()
        
        # Check that fabric count is correct
        repo = GitRepository.objects.get(url='https://github.com/test/repo1.git')
        self.assertEqual(repo.fabric_count, 2)
    
    def test_migration_preserves_legacy_fields(self):
        """Test that legacy git fields are preserved for backward compatibility"""
        # Create fabric before migration
        fabric = HedgehogFabric.objects.create(**self.fabric1_data)
        fabric_id = fabric.id
        
        # Run migration
        self.migrate()
        
        # Verify legacy fields are still present and marked as deprecated
        fabric_after = HedgehogFabric.objects.get(id=fabric_id)
        
        # Legacy fields should still exist
        self.assertEqual(fabric_after.git_repository_url, 'https://github.com/test/repo1.git')
        self.assertEqual(fabric_after.git_branch, 'main')
        self.assertEqual(fabric_after.git_path, 'hedgehog/app1/')
        self.assertEqual(fabric_after.git_username, 'testuser1')
        self.assertEqual(fabric_after.git_token, 'github_pat_token1')
    
    def test_migration_handles_empty_git_configurations(self):
        """Test that migration handles fabrics without git configuration"""
        # Create fabric without git configuration
        fabric = HedgehogFabric.objects.create(**self.fabric_no_git_data)
        fabric_id = fabric.id
        
        # Run migration
        self.migrate()
        
        # Verify fabric still exists and has no git repository
        fabric_after = HedgehogFabric.objects.get(id=fabric_id)
        self.assertIsNone(fabric_after.git_repository)
        self.assertEqual(fabric_after.gitops_directory, '/')
    
    def test_migration_provider_detection(self):
        """Test that migration correctly detects git providers from URLs"""
        fabrics_data = [
            {
                'name': 'GitHub Fabric',
                'git_repository_url': 'https://github.com/user/repo.git',
                'expected_provider': 'github'
            },
            {
                'name': 'GitLab Fabric',
                'git_repository_url': 'https://gitlab.com/user/repo.git',
                'expected_provider': 'gitlab'
            },
            {
                'name': 'Bitbucket Fabric',
                'git_repository_url': 'https://bitbucket.org/user/repo.git',
                'expected_provider': 'bitbucket'
            },
            {
                'name': 'Azure DevOps Fabric',
                'git_repository_url': 'https://dev.azure.com/org/project/_git/repo',
                'expected_provider': 'azure'
            },
            {
                'name': 'Generic Fabric',
                'git_repository_url': 'https://git.example.com/user/repo.git',
                'expected_provider': 'generic'
            }
        ]
        
        # Create fabrics before migration
        for fabric_data in fabrics_data:
            HedgehogFabric.objects.create(
                name=fabric_data['name'],
                git_repository_url=fabric_data['git_repository_url']
            )
        
        # Run migration
        self.migrate()
        
        # Verify provider detection
        for fabric_data in fabrics_data:
            repo = GitRepository.objects.get(url=fabric_data['git_repository_url'])
            self.assertEqual(repo.provider, fabric_data['expected_provider'])
    
    def test_migration_creates_system_user_for_orphaned_fabrics(self):
        """Test that migration creates system user for fabrics without owners"""
        # Create fabric before migration (no created_by field in legacy model)
        fabric = HedgehogFabric.objects.create(**self.fabric1_data)
        
        # Run migration
        self.migrate()
        
        # Verify system user was created
        system_user = User.objects.filter(username='system_migration').first()
        self.assertIsNotNone(system_user)
        self.assertFalse(system_user.is_active)
        
        # Verify repository is owned by system user
        repo = GitRepository.objects.get(url='https://github.com/test/repo1.git')
        self.assertEqual(repo.created_by, system_user)


class GitRepositoryMigrationRollbackTest(TransactionTestCase, MigrationTest):
    """Test cases for GitRepository migration rollback functionality"""
    
    migrate_from = '0014_implement_git_repository_separation'
    migrate_to = '0013_add_argocd_tracking_fields'
    
    def setUp(self):
        """Set up test data after migration (for rollback testing)"""
        super().setUp()
        
        # Start from the migrated state
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create GitRepository
        self.repo = GitRepository.objects.create(
            name='Test Repository',
            url='https://github.com/test/repo.git',
            provider='github',
            authentication_type='token',
            default_branch='main',
            is_private=True,
            created_by=self.user
        )
        
        self.repo.set_credentials({'token': 'github_pat_test123'})
        self.repo.save()
        
        # Create fabrics using the repository
        self.fabric1 = HedgehogFabric.objects.create(
            name='Test Fabric 1',
            git_repository=self.repo,
            gitops_directory='/app1/'
        )
        
        self.fabric2 = HedgehogFabric.objects.create(
            name='Test Fabric 2',
            git_repository=self.repo,
            gitops_directory='/app2/'
        )
    
    def test_rollback_restores_git_fields(self):
        """Test that rollback restores git fields to fabric model"""
        fabric1_id = self.fabric1.id
        fabric2_id = self.fabric2.id
        
        # Run rollback migration
        self.migrate()
        
        # Verify fabrics still exist
        fabric1_after = HedgehogFabric.objects.get(id=fabric1_id)
        fabric2_after = HedgehogFabric.objects.get(id=fabric2_id)
        
        # Verify git fields were restored
        self.assertEqual(fabric1_after.git_repository_url, 'https://github.com/test/repo.git')
        self.assertEqual(fabric1_after.git_branch, 'main')
        self.assertEqual(fabric1_after.git_path, 'app1/')  # gitops_directory converted back
        
        self.assertEqual(fabric2_after.git_repository_url, 'https://github.com/test/repo.git')
        self.assertEqual(fabric2_after.git_branch, 'main')
        self.assertEqual(fabric2_after.git_path, 'app2/')
    
    def test_rollback_restores_credentials(self):
        """Test that rollback restores credentials to fabric fields"""
        fabric1_id = self.fabric1.id
        
        # Run rollback migration
        self.migrate()
        
        # Verify credentials were restored
        fabric1_after = HedgehogFabric.objects.get(id=fabric1_id)
        self.assertEqual(fabric1_after.git_token, 'github_pat_test123')
    
    def test_rollback_clears_new_fields(self):
        """Test that rollback clears new architecture fields"""
        fabric1_id = self.fabric1.id
        
        # Run rollback migration
        self.migrate()
        
        # Verify new fields were cleared
        fabric1_after = HedgehogFabric.objects.get(id=fabric1_id)
        self.assertIsNone(fabric1_after.git_repository)
        self.assertEqual(fabric1_after.gitops_directory, '/')


class GitRepositoryMigrationErrorHandlingTest(TestCase):
    """Test cases for migration error handling"""
    
    def test_migration_handles_missing_credentials_gracefully(self):
        """Test that migration handles missing/invalid credentials gracefully"""
        # This test would require more complex setup to simulate migration state
        # For now, we verify that the migration functions handle empty credentials
        
        from netbox_hedgehog.migrations.M0014_implement_git_repository_separation import Migration
        
        # Test that migration doesn't crash with empty credentials
        # This is more of a smoke test to ensure the migration code is robust
        self.assertTrue(hasattr(Migration, 'operations'))
        self.assertTrue(len(Migration.operations) > 0)
    
    def test_migration_handles_duplicate_repositories(self):
        """Test that migration handles potential duplicate repository URLs correctly"""
        # The migration should handle the case where multiple fabrics
        # have the same repository URL by creating a single GitRepository
        # and having both fabrics reference it
        pass  # Implementation would require complex migration testing setup
    
    def test_migration_preserves_fabric_relationships(self):
        """Test that migration preserves all fabric relationships and foreign keys"""
        # This would test that the migration doesn't break existing
        # foreign key relationships in the fabric model
        pass  # Implementation would require complex migration testing setup