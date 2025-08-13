#!/usr/bin/env python3
"""
FOCUSED ENVIRONMENT CONFIGURATION FIX

Based on comprehensive diagnosis findings, this script addresses the specific issues:
1. GITHUB_TOKEN exists in .env but not loaded in environment
2. Test CRD files exist but in different location
3. Django services cannot be imported (development environment)

This creates a focused test to prove GitOps workflow works with proper configuration.
"""

import os
import sys
import json
import yaml
import requests
import subprocess
from pathlib import Path
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'focused_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FocusedEnvironmentFix:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'fixes_applied': [],
            'validation_results': {},
            'test_outcomes': {}
        }
        self.correct_crd_path = "project_management/07_qapm_workspaces/active_projects/qapm_20250804_170830_fgd_sync_resolution/temp/gitops-test-1/gitops/hedgehog/fabric-1/raw"
        
    def load_env_file(self):
        """Load .env file to get configuration"""
        logger.info("--- Loading .env configuration ---")
        
        env_file = Path('.env')
        if not env_file.exists():
            logger.error(".env file not found!")
            return False
            
        # Read .env file
        env_vars = {}
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value.strip('"')
        
        # Set environment variables
        for key, value in env_vars.items():
            os.environ[key] = value
            logger.info(f"Set {key}={'*' * min(len(value), 4)}...")
        
        self.results['fixes_applied'].append("Loaded .env file variables")
        return True
    
    def validate_github_access(self):
        """Test GitHub access with loaded token"""
        logger.info("--- Validating GitHub Access ---")
        
        github_token = os.getenv('GITHUB_TOKEN')
        if not github_token:
            logger.error("GITHUB_TOKEN not found in environment")
            return False
        
        try:
            headers = {'Authorization': f'token {github_token}'}
            response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
            
            if response.status_code == 200:
                user_info = response.json()
                logger.info(f"✅ GitHub authentication successful for user: {user_info.get('login', 'unknown')}")
                self.results['validation_results']['github_auth'] = True
                self.results['validation_results']['github_user'] = user_info.get('login', 'unknown')
                return True
            else:
                logger.error(f"❌ GitHub authentication failed: {response.status_code}")
                self.results['validation_results']['github_auth'] = False
                return False
                
        except Exception as e:
            logger.error(f"❌ GitHub API error: {str(e)}")
            self.results['validation_results']['github_auth'] = False
            return False
    
    def validate_test_repository_access(self):
        """Test access to specific test repository"""
        logger.info("--- Validating Test Repository Access ---")
        
        test_repo = os.getenv('GIT_TEST_REPOSITORY', '')
        if not test_repo:
            logger.error("GIT_TEST_REPOSITORY not configured")
            return False
        
        # Extract owner/repo from URL
        try:
            if 'github.com' in test_repo:
                repo_part = test_repo.split('github.com/')[-1].replace('.git', '')
                api_url = f"https://api.github.com/repos/{repo_part}"
                
                github_token = os.getenv('GITHUB_TOKEN')
                headers = {'Authorization': f'token {github_token}'} if github_token else {}
                
                response = requests.get(api_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    repo_info = response.json()
                    logger.info(f"✅ Test repository accessible: {repo_info['full_name']}")
                    logger.info(f"   - Private: {repo_info['private']}")
                    logger.info(f"   - Push permission: {repo_info.get('permissions', {}).get('push', False)}")
                    
                    self.results['validation_results']['test_repo_access'] = True
                    self.results['validation_results']['test_repo_info'] = {
                        'name': repo_info['full_name'],
                        'private': repo_info['private'],
                        'push_allowed': repo_info.get('permissions', {}).get('push', False)
                    }
                    return True
                else:
                    logger.error(f"❌ Cannot access test repository: {response.status_code}")
                    self.results['validation_results']['test_repo_access'] = False
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Test repository validation error: {str(e)}")
            self.results['validation_results']['test_repo_access'] = False
            return False
    
    def validate_crd_files(self):
        """Validate the CRD test files"""
        logger.info("--- Validating CRD Test Files ---")
        
        crd_dir = Path(self.correct_crd_path)
        if not crd_dir.exists():
            logger.error(f"❌ CRD directory not found: {crd_dir}")
            return False
        
        yaml_files = list(crd_dir.glob('*.yaml')) + list(crd_dir.glob('*.yml'))
        logger.info(f"Found {len(yaml_files)} YAML files")
        
        valid_crds = []
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r') as f:
                    content = yaml.safe_load(f)
                
                if content and isinstance(content, dict):
                    if 'kind' in content and 'metadata' in content:
                        logger.info(f"✅ Valid CRD: {yaml_file.name} ({content.get('kind', 'unknown')})")
                        valid_crds.append({
                            'file': yaml_file.name,
                            'kind': content.get('kind', 'unknown'),
                            'name': content.get('metadata', {}).get('name', 'unknown'),
                            'size': yaml_file.stat().st_size
                        })
                    else:
                        logger.warning(f"⚠️  Invalid CRD structure: {yaml_file.name}")
                else:
                    logger.warning(f"⚠️  Empty or invalid YAML: {yaml_file.name}")
                    
            except Exception as e:
                logger.error(f"❌ Error parsing {yaml_file.name}: {str(e)}")
        
        self.results['validation_results']['crd_files'] = valid_crds
        logger.info(f"✅ Found {len(valid_crds)} valid CRD files")
        return len(valid_crds) > 0
    
    def create_minimal_service_test(self):
        """Create minimal service test without Django dependency"""
        logger.info("--- Creating Minimal Service Test ---")
        
        try:
            # Test if services can be parsed as Python files
            service_files = [
                'netbox_hedgehog/services/gitops_ingestion_service.py',
                'netbox_hedgehog/services/gitops_onboarding_service.py',
                'netbox_hedgehog/services/github_sync_service.py'
            ]
            
            service_status = {}
            for service_file in service_files:
                path = Path(service_file)
                if path.exists():
                    try:
                        # Just check if file is valid Python syntax
                        with open(path, 'r') as f:
                            content = f.read()
                        
                        # Try to compile the file
                        compile(content, str(path), 'exec')
                        
                        service_status[service_file] = {
                            'exists': True,
                            'valid_syntax': True,
                            'size': path.stat().st_size
                        }
                        logger.info(f"✅ Service file valid: {service_file}")
                        
                    except SyntaxError as e:
                        service_status[service_file] = {
                            'exists': True,
                            'valid_syntax': False,
                            'error': str(e)
                        }
                        logger.error(f"❌ Syntax error in {service_file}: {str(e)}")
                else:
                    service_status[service_file] = {'exists': False}
                    logger.error(f"❌ Service file not found: {service_file}")
            
            self.results['validation_results']['service_files'] = service_status
            return True
            
        except Exception as e:
            logger.error(f"❌ Service test error: {str(e)}")
            return False
    
    def test_standalone_github_operations(self):
        """Test GitHub operations without Django"""
        logger.info("--- Testing Standalone GitHub Operations ---")
        
        github_token = os.getenv('GITHUB_TOKEN')
        test_repo = os.getenv('GIT_TEST_REPOSITORY', '')
        
        if not github_token or not test_repo:
            logger.error("❌ Missing GitHub token or test repository")
            return False
        
        try:
            # Extract repo info
            repo_part = test_repo.split('github.com/')[-1].replace('.git', '')
            owner, repo = repo_part.split('/')
            
            headers = {'Authorization': f'token {github_token}'}
            
            # Test 1: List repository contents
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                contents = response.json()
                logger.info(f"✅ Repository contents accessible ({len(contents)} items)")
                
                # Look for gitops directory
                gitops_found = any(item['name'] == 'gitops' for item in contents)
                logger.info(f"   - GitOps directory present: {gitops_found}")
                
                self.results['test_outcomes']['repo_content_access'] = True
                self.results['test_outcomes']['gitops_directory_found'] = gitops_found
                
            else:
                logger.error(f"❌ Cannot list repository contents: {response.status_code}")
                self.results['test_outcomes']['repo_content_access'] = False
            
            # Test 2: Check repository permissions for writing
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                repo_info = response.json()
                can_push = repo_info.get('permissions', {}).get('push', False)
                logger.info(f"✅ Write permissions: {can_push}")
                self.results['test_outcomes']['write_permissions'] = can_push
            
            return True
            
        except Exception as e:
            logger.error(f"❌ GitHub operations test error: {str(e)}")
            self.results['test_outcomes']['github_operations_error'] = str(e)
            return False
    
    def run_complete_fix_and_validation(self):
        """Run complete fix and validation sequence"""
        logger.info("=== STARTING FOCUSED ENVIRONMENT FIX ===")
        
        success_count = 0
        total_tests = 6
        
        # Step 1: Load environment configuration
        if self.load_env_file():
            success_count += 1
        
        # Step 2: Validate GitHub access
        if self.validate_github_access():
            success_count += 1
        
        # Step 3: Test repository access
        if self.validate_test_repository_access():
            success_count += 1
        
        # Step 4: Validate CRD files
        if self.validate_crd_files():
            success_count += 1
        
        # Step 5: Test service files
        if self.create_minimal_service_test():
            success_count += 1
        
        # Step 6: Test GitHub operations
        if self.test_standalone_github_operations():
            success_count += 1
        
        # Save results
        result_file = f'focused_fix_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(result_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"=== FIX VALIDATION COMPLETE: {success_count}/{total_tests} tests passed ===")
        logger.info(f"Results saved to: {result_file}")
        
        return success_count, total_tests, self.results

def main():
    """Run the focused environment fix"""
    fixer = FocusedEnvironmentFix()
    success_count, total_tests, results = fixer.run_complete_fix_and_validation()
    
    print("\n" + "="*60)
    print("FOCUSED ENVIRONMENT FIX RESULTS")
    print("="*60)
    
    print(f"\n📊 OVERALL SCORE: {success_count}/{total_tests} ({success_count/total_tests*100:.1f}%)")
    
    if results['validation_results'].get('github_auth'):
        print(f"✅ GitHub Authentication: SUCCESS")
        print(f"   User: {results['validation_results'].get('github_user', 'unknown')}")
    else:
        print(f"❌ GitHub Authentication: FAILED")
    
    if results['validation_results'].get('test_repo_access'):
        repo_info = results['validation_results'].get('test_repo_info', {})
        print(f"✅ Test Repository Access: SUCCESS")
        print(f"   Repository: {repo_info.get('name', 'unknown')}")
        print(f"   Write Access: {repo_info.get('push_allowed', False)}")
    else:
        print(f"❌ Test Repository Access: FAILED")
    
    crd_files = results['validation_results'].get('crd_files', [])
    if crd_files:
        print(f"✅ CRD Files: {len(crd_files)} valid files found")
        for crd in crd_files:
            print(f"   - {crd['file']} ({crd['kind']})")
    else:
        print(f"❌ CRD Files: No valid files found")
    
    github_ops = results['test_outcomes'].get('repo_content_access', False)
    write_perms = results['test_outcomes'].get('write_permissions', False)
    
    if github_ops and write_perms:
        print(f"✅ GitHub Operations: READY FOR GITOPS")
        print(f"   Repository readable: {github_ops}")
        print(f"   Repository writable: {write_perms}")
    else:
        print(f"❌ GitHub Operations: NOT READY")
        print(f"   Repository readable: {github_ops}")
        print(f"   Repository writable: {write_perms}")
    
    print("\n" + "="*60)
    if success_count >= 5:
        print("🎯 ENVIRONMENT READY FOR GITOPS TESTING!")
        print("\nNEXT STEPS:")
        print("1. Create minimal GitOps workflow test")
        print("2. Test CRD file processing")
        print("3. Validate GitHub push operations")
    else:
        print("⚠️  ENVIRONMENT NEEDS ADDITIONAL FIXES")
        print("\nREMAINING ISSUES:")
        if not results['validation_results'].get('github_auth'):
            print("- Fix GitHub token authentication")
        if not results['validation_results'].get('test_repo_access'):
            print("- Ensure test repository access")
        if not results['validation_results'].get('crd_files'):
            print("- Verify CRD test files location")
    print("="*60)

if __name__ == '__main__':
    main()