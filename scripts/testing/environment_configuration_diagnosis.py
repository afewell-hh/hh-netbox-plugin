#!/usr/bin/env python3
"""
URGENT: Environment & Configuration Diagnosis Script

CRITICAL DISCOVERY: Services ARE properly integrated. Issue is environmental/configuration.
EVIDENCE: 48 CRs in raw/, zero GitHub commits, but functional workflow architecture exists.

This script systematically diagnoses configuration and environment issues
preventing the functional GitOps workflow from executing.
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

# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'env_diagnosis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EnvironmentDiagnostic:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'environment': {},
            'configuration': {},
            'permissions': {},
            'github_access': {},
            'test_data': {},
            'service_tracing': {},
            'recommendations': []
        }
        
    def run_full_diagnosis(self):
        """Execute complete diagnostic suite"""
        logger.info("=== STARTING COMPREHENSIVE ENVIRONMENT DIAGNOSIS ===")
        
        self.diagnose_environment()
        self.validate_configuration()
        self.check_permissions()
        self.test_github_access()
        self.verify_test_data()
        self.trace_service_execution()
        self.generate_recommendations()
        
        # Save results
        result_file = f'environment_diagnosis_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(result_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"=== DIAGNOSIS COMPLETE - Results saved to {result_file} ===")
        return self.results

    def diagnose_environment(self):
        """Test environment setup and container configuration"""
        logger.info("--- PHASE 1: Environment Diagnosis ---")
        
        env_data = {}
        
        # Check Python environment
        env_data['python_version'] = sys.version
        env_data['working_directory'] = os.getcwd()
        env_data['user'] = os.getenv('USER', 'unknown')
        
        # Check Django/NetBox environment
        try:
            import django
            env_data['django_version'] = django.VERSION
            env_data['django_settings'] = os.getenv('DJANGO_SETTINGS_MODULE', 'Not set')
        except ImportError:
            env_data['django_status'] = 'Not available'
        
        # Check container environment
        env_data['is_docker'] = os.path.exists('/.dockerenv')
        
        # Check network connectivity
        try:
            response = requests.get('https://api.github.com', timeout=10)
            env_data['github_api_accessible'] = response.status_code == 200
            env_data['internet_connectivity'] = True
        except Exception as e:
            env_data['github_api_accessible'] = False
            env_data['internet_connectivity'] = False
            env_data['connectivity_error'] = str(e)
        
        # Check environment variables
        env_vars = ['DJANGO_SETTINGS_MODULE', 'SECRET_KEY', 'DATABASE_URL']
        env_data['environment_variables'] = {}
        for var in env_vars:
            env_data['environment_variables'][var] = 'SET' if os.getenv(var) else 'NOT SET'
        
        self.results['environment'] = env_data
        logger.info(f"Environment check complete: {json.dumps(env_data, indent=2)}")

    def validate_configuration(self):
        """Examine fabric configuration and GitHub settings"""
        logger.info("--- PHASE 2: Configuration Validation ---")
        
        config_data = {}
        
        # Check .env file
        env_file = Path('.env')
        config_data['env_file_exists'] = env_file.exists()
        if env_file.exists():
            config_data['env_file_size'] = env_file.stat().st_size
            # Don't log contents for security
        
        # Check for token files
        token_files = list(Path('.').glob('*.token'))
        config_data['token_files'] = [str(f) for f in token_files]
        
        # Look for fabric configuration examples
        try:
            # Check if we can import Django models
            sys.path.append('/opt/netbox/netbox')
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
            
            import django
            django.setup()
            
            from netbox_hedgehog.models import Fabric
            
            fabric_count = Fabric.objects.count()
            config_data['fabric_count'] = fabric_count
            
            if fabric_count > 0:
                # Get first fabric for configuration analysis
                fabric = Fabric.objects.first()
                config_data['sample_fabric'] = {
                    'name': fabric.name,
                    'has_github_repo': bool(getattr(fabric, 'github_repo', None)),
                    'has_github_token': bool(getattr(fabric, 'github_token', None)),
                    'github_repo_format': getattr(fabric, 'github_repo', 'Not set')
                }
        except Exception as e:
            config_data['django_model_access'] = f"Failed: {str(e)}"
        
        self.results['configuration'] = config_data
        logger.info(f"Configuration check complete: {json.dumps(config_data, indent=2)}")

    def check_permissions(self):
        """Validate directory permissions and file system access"""
        logger.info("--- PHASE 3: Permissions Validation ---")
        
        perm_data = {}
        
        # Check current directory permissions
        cwd = Path('.')
        perm_data['current_directory'] = {
            'path': str(cwd.absolute()),
            'readable': os.access(cwd, os.R_OK),
            'writable': os.access(cwd, os.W_OK),
            'executable': os.access(cwd, os.X_OK)
        }
        
        # Check key directories
        key_dirs = [
            'netbox_hedgehog',
            'netbox_hedgehog/services',
            'tests',
            'hemk/poc_development/fabric_management_k8s_configs/crds/raw'
        ]
        
        perm_data['key_directories'] = {}
        for dir_path in key_dirs:
            path = Path(dir_path)
            if path.exists():
                perm_data['key_directories'][dir_path] = {
                    'exists': True,
                    'readable': os.access(path, os.R_OK),
                    'writable': os.access(path, os.W_OK),
                    'executable': os.access(path, os.X_OK),
                    'file_count': len(list(path.rglob('*'))) if path.is_dir() else 0
                }
            else:
                perm_data['key_directories'][dir_path] = {'exists': False}
        
        # Check temp directory access
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=True) as tmp:
                perm_data['temp_directory_access'] = True
                perm_data['temp_directory'] = os.path.dirname(tmp.name)
        except Exception as e:
            perm_data['temp_directory_access'] = False
            perm_data['temp_error'] = str(e)
        
        self.results['permissions'] = perm_data
        logger.info(f"Permissions check complete: {json.dumps(perm_data, indent=2)}")

    def test_github_access(self):
        """Test GitHub API authentication and repository access"""
        logger.info("--- PHASE 4: GitHub Access Testing ---")
        
        github_data = {}
        
        # Test basic GitHub API access
        try:
            response = requests.get('https://api.github.com/rate_limit', timeout=10)
            github_data['api_accessible'] = response.status_code == 200
            if response.status_code == 200:
                rate_limit = response.json()
                github_data['rate_limit'] = rate_limit
        except Exception as e:
            github_data['api_accessible'] = False
            github_data['api_error'] = str(e)
        
        # Check for GitHub token in environment
        github_token = os.getenv('GITHUB_TOKEN')
        if github_token:
            github_data['token_configured'] = True
            # Test authenticated access
            try:
                headers = {'Authorization': f'token {github_token}'}
                response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
                github_data['authenticated_access'] = response.status_code == 200
                if response.status_code == 200:
                    user_info = response.json()
                    github_data['authenticated_user'] = user_info.get('login', 'unknown')
            except Exception as e:
                github_data['authenticated_access'] = False
                github_data['auth_error'] = str(e)
        else:
            github_data['token_configured'] = False
        
        # Check for token files
        token_files = list(Path('.').glob('*.token'))
        if token_files:
            github_data['token_files_found'] = [str(f) for f in token_files]
            # Test with first token file
            try:
                with open(token_files[0], 'r') as f:
                    file_token = f.read().strip()
                headers = {'Authorization': f'token {file_token}'}
                response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
                github_data['file_token_valid'] = response.status_code == 200
            except Exception as e:
                github_data['file_token_error'] = str(e)
        
        self.results['github_access'] = github_data
        logger.info(f"GitHub access check complete: {json.dumps(github_data, indent=2)}")

    def verify_test_data(self):
        """Check test data structure and format"""
        logger.info("--- PHASE 5: Test Data Verification ---")
        
        test_data = {}
        
        # Check CRD raw directory
        raw_dir = Path('hemk/poc_development/fabric_management_k8s_configs/crds/raw')
        if raw_dir.exists():
            yaml_files = list(raw_dir.glob('*.yaml')) + list(raw_dir.glob('*.yml'))
            test_data['raw_directory'] = {
                'exists': True,
                'yaml_file_count': len(yaml_files),
                'total_files': len(list(raw_dir.iterdir()))
            }
            
            # Analyze first few YAML files
            sample_files = []
            for yaml_file in yaml_files[:3]:  # Check first 3 files
                file_info = {
                    'filename': yaml_file.name,
                    'size': yaml_file.stat().st_size
                }
                
                try:
                    with open(yaml_file, 'r') as f:
                        content = yaml.safe_load(f)
                    file_info['yaml_valid'] = True
                    file_info['has_kind'] = 'kind' in content if content else False
                    file_info['has_metadata'] = 'metadata' in content if content else False
                    if content:
                        file_info['kind'] = content.get('kind', 'unknown')
                except Exception as e:
                    file_info['yaml_valid'] = False
                    file_info['yaml_error'] = str(e)
                
                sample_files.append(file_info)
            
            test_data['sample_files'] = sample_files
        else:
            test_data['raw_directory'] = {'exists': False}
        
        # Check processed directories
        processed_dirs = ['commit', 'pre_commit']
        for dir_name in processed_dirs:
            dir_path = raw_dir.parent / dir_name
            if dir_path.exists():
                test_data[f'{dir_name}_directory'] = {
                    'exists': True,
                    'file_count': len(list(dir_path.iterdir()))
                }
            else:
                test_data[f'{dir_name}_directory'] = {'exists': False}
        
        self.results['test_data'] = test_data
        logger.info(f"Test data check complete: {json.dumps(test_data, indent=2)}")

    def trace_service_execution(self):
        """Add tracing to service execution"""
        logger.info("--- PHASE 6: Service Execution Tracing ---")
        
        trace_data = {}
        
        # Check if services can be imported
        try:
            sys.path.append('/opt/netbox/netbox')
            from netbox_hedgehog.services.gitops_ingestion_service import GitopsIngestionService
            from netbox_hedgehog.services.gitops_onboarding_service import GitopsOnboardingService
            trace_data['services_importable'] = True
        except Exception as e:
            trace_data['services_importable'] = False
            trace_data['import_error'] = str(e)
        
        # Check service files exist
        service_files = [
            'netbox_hedgehog/services/gitops_ingestion_service.py',
            'netbox_hedgehog/services/gitops_onboarding_service.py',
            'netbox_hedgehog/services/gitops_edit_service.py'
        ]
        
        trace_data['service_files'] = {}
        for service_file in service_files:
            path = Path(service_file)
            trace_data['service_files'][service_file] = {
                'exists': path.exists(),
                'size': path.stat().st_size if path.exists() else 0
            }
        
        # Check if we can create service instances (minimal test)
        try:
            if trace_data['services_importable']:
                # This would require Django setup, so just check file structure
                trace_data['service_structure_check'] = 'Available for testing'
        except Exception as e:
            trace_data['service_instantiation_error'] = str(e)
        
        self.results['service_tracing'] = trace_data
        logger.info(f"Service tracing check complete: {json.dumps(trace_data, indent=2)}")

    def generate_recommendations(self):
        """Generate corrective actions based on findings"""
        logger.info("--- PHASE 7: Generating Recommendations ---")
        
        recommendations = []
        
        # Environment recommendations
        if not self.results['environment'].get('github_api_accessible', False):
            recommendations.append({
                'priority': 'CRITICAL',
                'category': 'Network',
                'issue': 'GitHub API not accessible',
                'action': 'Check container network configuration and firewall settings',
                'test_command': 'curl -I https://api.github.com'
            })
        
        # Configuration recommendations
        if not self.results['configuration'].get('env_file_exists', False):
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Configuration',
                'issue': '.env file missing',
                'action': 'Create .env file with required environment variables',
                'test_command': 'ls -la .env'
            })
        
        # GitHub access recommendations
        github_data = self.results.get('github_access', {})
        if not github_data.get('token_configured', False) and not github_data.get('token_files_found', []):
            recommendations.append({
                'priority': 'CRITICAL',
                'category': 'Authentication',
                'issue': 'No GitHub token found',
                'action': 'Set GITHUB_TOKEN environment variable or create token file',
                'test_command': 'echo $GITHUB_TOKEN or ls *.token'
            })
        
        # Test data recommendations
        test_data = self.results.get('test_data', {})
        if not test_data.get('raw_directory', {}).get('exists', False):
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Test Data',
                'issue': 'CRD raw directory not found',
                'action': 'Verify test data directory structure',
                'test_command': 'ls -la hemk/poc_development/fabric_management_k8s_configs/crds/raw'
            })
        
        # Service recommendations  
        if not self.results.get('service_tracing', {}).get('services_importable', False):
            recommendations.append({
                'priority': 'CRITICAL',
                'category': 'Services',
                'issue': 'Cannot import Django services',
                'action': 'Check Django setup and PYTHONPATH configuration',
                'test_command': 'python -c "import django; django.setup()"'
            })
        
        self.results['recommendations'] = recommendations
        
        # Print summary
        logger.info("=== DIAGNOSIS SUMMARY ===")
        logger.info(f"Total issues found: {len(recommendations)}")
        for rec in recommendations:
            logger.info(f"[{rec['priority']}] {rec['category']}: {rec['issue']}")
        
        return recommendations

def main():
    """Run the complete diagnostic suite"""
    diagnostic = EnvironmentDiagnostic()
    results = diagnostic.run_full_diagnosis()
    
    # Print key findings
    print("\n" + "="*60)
    print("ENVIRONMENT & CONFIGURATION DIAGNOSIS RESULTS")
    print("="*60)
    
    print(f"\n1. ENVIRONMENT STATUS:")
    env = results['environment']
    print(f"   - Internet connectivity: {env.get('internet_connectivity', 'Unknown')}")
    print(f"   - GitHub API accessible: {env.get('github_api_accessible', 'Unknown')}")
    print(f"   - Django available: {'django_version' in env}")
    
    print(f"\n2. CONFIGURATION STATUS:")
    config = results['configuration']
    print(f"   - .env file exists: {config.get('env_file_exists', 'Unknown')}")
    print(f"   - Fabric models accessible: {'fabric_count' in config}")
    print(f"   - Token files found: {len(config.get('token_files', []))}")
    
    print(f"\n3. GITHUB ACCESS STATUS:")
    github = results['github_access']
    print(f"   - Token configured: {github.get('token_configured', 'Unknown')}")
    print(f"   - Authenticated access: {github.get('authenticated_access', 'Unknown')}")
    
    print(f"\n4. TEST DATA STATUS:")
    test_data = results['test_data']
    raw_dir = test_data.get('raw_directory', {})
    print(f"   - Raw directory exists: {raw_dir.get('exists', 'Unknown')}")
    print(f"   - YAML files found: {raw_dir.get('yaml_file_count', 0)}")
    
    print(f"\n5. CRITICAL RECOMMENDATIONS:")
    critical_recs = [r for r in results['recommendations'] if r['priority'] == 'CRITICAL']
    if critical_recs:
        for i, rec in enumerate(critical_recs, 1):
            print(f"   {i}. {rec['issue']}")
            print(f"      Action: {rec['action']}")
            print(f"      Test: {rec['test_command']}")
    else:
        print("   No critical issues found!")
    
    print("\n" + "="*60)
    print(f"Complete results saved to: environment_diagnosis_results_*.json")
    print("="*60)

if __name__ == '__main__':
    main()