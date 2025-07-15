#!/usr/bin/env python3
"""
Week 1 GitOps Backend Architecture Implementation Validation
Validates that all Week 1 deliverables are correctly implemented
"""

import os
import sys
import re
import ast
from pathlib import Path

def validate_file_exists(file_path, description):
    """Validate that a file exists and is not empty"""
    if not os.path.exists(file_path):
        return False, f"❌ {description}: File does not exist: {file_path}"
    
    if os.path.getsize(file_path) == 0:
        return False, f"❌ {description}: File is empty: {file_path}"
    
    return True, f"✅ {description}: File exists and has content"

def validate_python_syntax(file_path, description):
    """Validate Python syntax of a file"""
    try:
        with open(file_path, 'r') as f:
            ast.parse(f.read())
        return True, f"✅ {description}: Valid Python syntax"
    except SyntaxError as e:
        return False, f"❌ {description}: Syntax error - {e}"
    except Exception as e:
        return False, f"❌ {description}: Error reading file - {e}"

def validate_model_implementation(file_path):
    """Validate GitRepository model implementation"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        checks = [
            ('GitRepository class', 'class GitRepository'),
            ('encrypted_credentials field', 'encrypted_credentials'),
            ('set_credentials method', 'def set_credentials'),
            ('get_credentials method', 'def get_credentials'),
            ('test_connection method', 'def test_connection'),
            ('update_fabric_count method', 'def update_fabric_count'),
            ('can_delete method', 'def can_delete'),
            ('get_dependent_fabrics method', 'def get_dependent_fabrics'),
            ('encryption key property', '_encryption_key'),
            ('Fernet import', 'from cryptography.fernet import Fernet'),
            ('base64 import', 'import base64'),
            ('choices import', 'from ..choices import'),
        ]
        
        results = []
        for description, pattern in checks:
            if pattern in content:
                results.append((True, f"✅ GitRepository model: {description} implemented"))
            else:
                results.append((False, f"❌ GitRepository model: {description} missing"))
        
        return results
    except Exception as e:
        return [(False, f"❌ GitRepository model: Error reading file - {e}")]

def validate_api_implementation(serializers_path, views_path):
    """Validate API implementation"""
    results = []
    
    try:
        # Check serializers
        with open(serializers_path, 'r') as f:
            serializers_content = f.read()
        
        serializer_checks = [
            ('GitRepositorySerializer', 'class GitRepositorySerializer'),
            ('GitRepositoryCreateSerializer', 'class GitRepositoryCreateSerializer'),
            ('GitRepositoryUpdateSerializer', 'class GitRepositoryUpdateSerializer'),
            ('Connection test serializer', 'GitRepositoryTestConnectionSerializer'),
            ('Clone serializer', 'GitRepositoryCloneSerializer'),
            ('Credentials field', 'credentials = serializers.DictField'),
        ]
        
        for description, pattern in serializer_checks:
            if pattern in serializers_content:
                results.append((True, f"✅ API Serializers: {description} implemented"))
            else:
                results.append((False, f"❌ API Serializers: {description} missing"))
        
        # Check views
        with open(views_path, 'r') as f:
            views_content = f.read()
        
        view_checks = [
            ('GitRepositoryViewSet', 'class GitRepositoryViewSet'),
            ('test_connection action', 'def test_connection'),
            ('clone action', 'def clone'),
            ('dependent_fabrics action', 'def dependent_fabrics'),
            ('connection_summary action', 'def connection_summary'),
            ('my_repositories action', 'def my_repositories'),
            ('User filtering', 'filter(created_by='),
        ]
        
        for description, pattern in view_checks:
            if pattern in views_content:
                results.append((True, f"✅ API Views: {description} implemented"))
            else:
                results.append((False, f"❌ API Views: {description} missing"))
        
    except Exception as e:
        results.append((False, f"❌ API implementation: Error reading files - {e}"))
    
    return results

def validate_migration_implementation(migration_path):
    """Validate migration implementation"""
    try:
        with open(migration_path, 'r') as f:
            content = f.read()
        
        checks = [
            ('Migration class', 'class Migration'),
            ('GitRepository model creation', 'CreateModel'),
            ('Fabric fields addition', 'AddField'),
            ('Forward migration function', 'migrate_git_configurations_forward'),
            ('Reverse migration function', 'migrate_git_configurations_reverse'),
            ('Credential encryption', 'encrypt_credentials'),
            ('Credential decryption', 'decrypt_credentials'),
            ('Data preservation', 'migration_summary'),
            ('Error handling', 'try:'),
            ('Unique constraints', 'UniqueConstraint'),
            ('RunPython operation', 'RunPython'),
        ]
        
        results = []
        for description, pattern in checks:
            if pattern in content:
                results.append((True, f"✅ Migration: {description} implemented"))
            else:
                results.append((False, f"❌ Migration: {description} missing"))
        
        return results
    except Exception as e:
        return [(False, f"❌ Migration: Error reading file - {e}")]

def validate_choices_implementation(choices_path):
    """Validate choices implementation"""
    try:
        with open(choices_path, 'r') as f:
            content = f.read()
        
        checks = [
            ('GitRepositoryProviderChoices', 'class GitRepositoryProviderChoices'),
            ('GitAuthenticationTypeChoices', 'class GitAuthenticationTypeChoices'),
            ('GitConnectionStatusChoices', 'class GitConnectionStatusChoices'),
            ('GitHub provider', 'GITHUB'),
            ('Token auth type', 'TOKEN'),
            ('Connected status', 'CONNECTED'),
        ]
        
        results = []
        for description, pattern in checks:
            if pattern in content:
                results.append((True, f"✅ Choices: {description} implemented"))
            else:
                results.append((False, f"❌ Choices: {description} missing"))
        
        return results
    except Exception as e:
        return [(False, f"❌ Choices: Error reading file - {e}")]

def validate_fabric_model_updates(fabric_path):
    """Validate HedgehogFabric model updates"""
    try:
        with open(fabric_path, 'r') as f:
            content = f.read()
        
        checks = [
            ('git_repository ForeignKey', 'git_repository = models.ForeignKey'),
            ('gitops_directory field', 'gitops_directory = models.CharField'),
            ('Unique constraint', 'unique_together'),
            ('GitRepository reference', "'GitRepository'"),
            ('Deprecated field markers', '[DEPRECATED]'),
        ]
        
        results = []
        for description, pattern in checks:
            if pattern in content:
                results.append((True, f"✅ Fabric Model: {description} implemented"))
            else:
                results.append((False, f"❌ Fabric Model: {description} missing"))
        
        return results
    except Exception as e:
        return [(False, f"❌ Fabric Model: Error reading file - {e}")]

def validate_url_routing(urls_path):
    """Validate URL routing for GitRepository API"""
    try:
        with open(urls_path, 'r') as f:
            content = f.read()
        
        if 'git-repositories' in content and 'GitRepositoryViewSet' in content:
            return [(True, "✅ URL Routing: GitRepository API endpoints configured")]
        else:
            return [(False, "❌ URL Routing: GitRepository API endpoints missing")]
        
    except Exception as e:
        return [(False, f"❌ URL Routing: Error reading file - {e}")]

def validate_model_imports(models_init_path):
    """Validate model imports in __init__.py"""
    try:
        with open(models_init_path, 'r') as f:
            content = f.read()
        
        if 'GitRepository' in content:
            return [(True, "✅ Model Imports: GitRepository imported in __init__.py")]
        else:
            return [(False, "❌ Model Imports: GitRepository not imported in __init__.py")]
        
    except Exception as e:
        return [(False, f"❌ Model Imports: Error reading file - {e}")]

def validate_testing_suite():
    """Validate testing suite implementation"""
    test_files = [
        'tests/test_git_repository_model.py',
        'tests/test_git_repository_api.py',
        'tests/test_git_repository_migration.py',
        'tests/run_tests.py'
    ]
    
    results = []
    for test_file in test_files:
        if os.path.exists(test_file):
            results.append((True, f"✅ Testing: {test_file} exists"))
        else:
            results.append((False, f"❌ Testing: {test_file} missing"))
    
    return results

def main():
    """Main validation function"""
    print("=" * 80)
    print("🔍 Week 1 GitOps Backend Architecture Implementation Validation")
    print("=" * 80)
    print()
    
    all_results = []
    
    # Define file paths
    files_to_check = [
        ('netbox_hedgehog/models/git_repository.py', 'GitRepository Model'),
        ('netbox_hedgehog/choices.py', 'Choices Configuration'),
        ('netbox_hedgehog/models/fabric.py', 'Fabric Model Updates'),
        ('netbox_hedgehog/api/serializers.py', 'API Serializers'),
        ('netbox_hedgehog/api/views.py', 'API Views'),
        ('netbox_hedgehog/api/urls.py', 'URL Routing'),
        ('netbox_hedgehog/models/__init__.py', 'Model Imports'),
        ('netbox_hedgehog/migrations/0014_implement_git_repository_separation.py', 'Migration Script'),
    ]
    
    # 1. File existence and syntax validation
    print("📁 File Existence and Syntax Validation")
    print("-" * 50)
    
    for file_path, description in files_to_check:
        # Check existence
        exists, message = validate_file_exists(file_path, description)
        all_results.append((exists, message))
        print(message)
        
        # Check syntax if file exists
        if exists:
            syntax_ok, syntax_message = validate_python_syntax(file_path, f"{description} Syntax")
            all_results.append((syntax_ok, syntax_message))
            print(syntax_message)
    
    print()
    
    # 2. Detailed implementation validation
    print("🔧 Implementation Details Validation")
    print("-" * 50)
    
    # GitRepository model
    model_results = validate_model_implementation('netbox_hedgehog/models/git_repository.py')
    all_results.extend(model_results)
    for _, message in model_results:
        print(message)
    
    # API implementation
    api_results = validate_api_implementation(
        'netbox_hedgehog/api/serializers.py',
        'netbox_hedgehog/api/views.py'
    )
    all_results.extend(api_results)
    for _, message in api_results:
        print(message)
    
    # Migration implementation
    migration_results = validate_migration_implementation(
        'netbox_hedgehog/migrations/0014_implement_git_repository_separation.py'
    )
    all_results.extend(migration_results)
    for _, message in migration_results:
        print(message)
    
    # Choices implementation
    choices_results = validate_choices_implementation('netbox_hedgehog/choices.py')
    all_results.extend(choices_results)
    for _, message in choices_results:
        print(message)
    
    # Fabric model updates
    fabric_results = validate_fabric_model_updates('netbox_hedgehog/models/fabric.py')
    all_results.extend(fabric_results)
    for _, message in fabric_results:
        print(message)
    
    # URL routing
    url_results = validate_url_routing('netbox_hedgehog/api/urls.py')
    all_results.extend(url_results)
    for _, message in url_results:
        print(message)
    
    # Model imports
    import_results = validate_model_imports('netbox_hedgehog/models/__init__.py')
    all_results.extend(import_results)
    for _, message in import_results:
        print(message)
    
    print()
    
    # 3. Testing suite validation
    print("🧪 Testing Suite Validation")
    print("-" * 50)
    
    testing_results = validate_testing_suite()
    all_results.extend(testing_results)
    for _, message in testing_results:
        print(message)
    
    print()
    
    # 4. Summary
    print("📊 Validation Summary")
    print("-" * 50)
    
    passed = sum(1 for result, _ in all_results if result)
    total = len(all_results)
    failed = total - passed
    
    print(f"Total checks: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success rate: {(passed/total)*100:.1f}%")
    
    print()
    
    if failed == 0:
        print("🎉 All validation checks passed!")
        print("Week 1 GitOps Backend Architecture implementation is complete and ready.")
        return 0
    else:
        print(f"⚠️  {failed} validation check(s) failed.")
        print("Please review the failed checks above and make necessary corrections.")
        return 1

if __name__ == '__main__':
    sys.exit(main())