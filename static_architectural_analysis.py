#!/usr/bin/env python3
"""
STATIC ARCHITECTURAL ANALYSIS
=============================

Analysis of the FGD sync failure based on code inspection and file system evidence.
This provides architectural failure analysis without requiring Django setup.
"""

import os
import json
from pathlib import Path
from datetime import datetime
import re

class StaticArchitecturalAnalyzer:
    """Static analysis of architectural components"""
    
    def __init__(self):
        self.base_path = Path('/home/ubuntu/cc/hedgehog-netbox-plugin')
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'analysis_type': 'static_architectural_failure_investigation',
            'evidence_collected': [],
            'architectural_gaps': [],
            'code_analysis': {},
            'filesystem_evidence': {}
        }
    
    def analyze_service_architecture(self):
        """Analyze service layer architecture"""
        print("=== ANALYZING SERVICE ARCHITECTURE ===")
        
        github_sync_service = self.base_path / 'netbox_hedgehog/services/github_sync_service.py'
        signals_file = self.base_path / 'netbox_hedgehog/signals.py'
        
        analysis = {
            'github_sync_service': {
                'exists': github_sync_service.exists(),
                'size': github_sync_service.stat().st_size if github_sync_service.exists() else 0
            },
            'signals': {
                'exists': signals_file.exists(),
                'size': signals_file.stat().st_size if signals_file.exists() else 0
            }
        }
        
        if github_sync_service.exists():
            with open(github_sync_service, 'r') as f:
                content = f.read()
                
            # Check for critical methods
            has_sync_method = 'def sync_cr_to_github(' in content
            has_github_api = 'requests.put' in content or 'requests.post' in content
            has_error_handling = 'except Exception' in content
            
            analysis['github_sync_service'].update({
                'has_sync_method': has_sync_method,
                'has_github_api_calls': has_github_api,
                'has_error_handling': has_error_handling,
                'line_count': len(content.splitlines())
            })
            
            print(f"✅ GitHubSyncService exists ({analysis['github_sync_service']['line_count']} lines)")
            print(f"   sync_cr_to_github method: {'✅' if has_sync_method else '❌'}")
            print(f"   GitHub API calls: {'✅' if has_github_api else '❌'}")
            print(f"   Error handling: {'✅' if has_error_handling else '❌'}")
        else:
            print("❌ GitHubSyncService does not exist")
            
        if signals_file.exists():
            with open(signals_file, 'r') as f:
                signals_content = f.read()
                
            # Check signal integration
            has_github_import = 'from .services.github_sync_service import GitHubSyncService' in signals_content
            has_sync_call = 'github_service.sync_cr_to_github(' in signals_content
            has_signal_decorators = '@receiver(' in signals_content
            
            analysis['signals'].update({
                'has_github_import': has_github_import,
                'has_sync_call': has_sync_call,
                'has_signal_decorators': has_signal_decorators,
                'line_count': len(signals_content.splitlines())
            })
            
            print(f"✅ Signals file exists ({analysis['signals']['line_count']} lines)")
            print(f"   GitHub service import: {'✅' if has_github_import else '❌'}")
            print(f"   Sync method calls: {'✅' if has_sync_call else '❌'}")
            print(f"   Signal decorators: {'✅' if has_signal_decorators else '❌'}")
        else:
            print("❌ Signals file does not exist")
        
        self.results['code_analysis']['services'] = analysis
        
        # Identify gaps
        if not has_sync_method:
            self.results['architectural_gaps'].append({
                'component': 'GitHubSyncService',
                'gap': 'MISSING_SYNC_METHOD',
                'impact': 'CRITICAL',
                'evidence': 'sync_cr_to_github method not found in service'
            })
            
        if not has_sync_call:
            self.results['architectural_gaps'].append({
                'component': 'Signal Integration',
                'gap': 'NO_SYNC_CALLS',
                'impact': 'CRITICAL', 
                'evidence': 'Signals do not call GitHub sync service'
            })
    
    def analyze_github_repository_evidence(self):
        """Analyze GitHub repository state evidence"""
        print("\n=== ANALYZING GITHUB REPOSITORY EVIDENCE ===")
        
        # Look for GitHub-related configuration files
        github_evidence = {}
        
        # Check for .env files or token files
        env_files = list(self.base_path.glob('**/.env*'))
        token_files = list(self.base_path.glob('**/*.token'))
        
        github_evidence['config_files'] = {
            'env_files': [str(f) for f in env_files],
            'token_files': [str(f) for f in token_files]
        }
        
        print(f"Environment files found: {len(env_files)}")
        print(f"Token files found: {len(token_files)}")
        
        # Check git status for evidence of failed operations
        git_status_file = self.base_path / '.git/index'
        github_evidence['git_repo'] = {
            'has_git_repo': git_status_file.exists(),
            'current_branch': None
        }
        
        if (self.base_path / '.git/HEAD').exists():
            with open(self.base_path / '.git/HEAD', 'r') as f:
                head_content = f.read().strip()
                if head_content.startswith('ref: refs/heads/'):
                    github_evidence['git_repo']['current_branch'] = head_content.replace('ref: refs/heads/', '')
        
        self.results['filesystem_evidence']['github'] = github_evidence
        
        print(f"Git repository present: {'✅' if github_evidence['git_repo']['has_git_repo'] else '❌'}")
        if github_evidence['git_repo']['current_branch']:
            print(f"Current branch: {github_evidence['git_repo']['current_branch']}")
    
    def analyze_raw_directory_evidence(self):
        """Analyze raw directory and file processing evidence"""
        print("\n=== ANALYZING RAW DIRECTORY EVIDENCE ===")
        
        # Look for raw/ directories
        raw_dirs = list(self.base_path.glob('**/raw'))
        managed_dirs = list(self.base_path.glob('**/managed'))
        
        raw_evidence = {
            'raw_directories': [],
            'managed_directories': [],
            'yaml_files_in_raw': 0,
            'yaml_files_in_managed': 0
        }
        
        for raw_dir in raw_dirs:
            if raw_dir.is_dir():
                yaml_files = list(raw_dir.glob('*.yaml')) + list(raw_dir.glob('*.yml'))
                raw_evidence['raw_directories'].append({
                    'path': str(raw_dir),
                    'yaml_file_count': len(yaml_files)
                })
                raw_evidence['yaml_files_in_raw'] += len(yaml_files)
                print(f"Raw directory: {raw_dir} ({len(yaml_files)} YAML files)")
        
        for managed_dir in managed_dirs:
            if managed_dir.is_dir():
                yaml_files = list(managed_dir.glob('**/*.yaml')) + list(managed_dir.glob('**/*.yml'))
                raw_evidence['managed_directories'].append({
                    'path': str(managed_dir),
                    'yaml_file_count': len(yaml_files)
                })
                raw_evidence['yaml_files_in_managed'] += len(yaml_files)
                print(f"Managed directory: {managed_dir} ({len(yaml_files)} YAML files)")
        
        self.results['filesystem_evidence']['directories'] = raw_evidence
        
        # Evidence analysis
        if raw_evidence['yaml_files_in_raw'] > 0 and raw_evidence['yaml_files_in_managed'] == 0:
            self.results['architectural_gaps'].append({
                'component': 'File Processing',
                'gap': 'NO_RAW_TO_MANAGED_CONVERSION',
                'impact': 'CRITICAL',
                'evidence': f"{raw_evidence['yaml_files_in_raw']} files in raw/, 0 in managed/"
            })
            print(f"❌ CRITICAL: {raw_evidence['yaml_files_in_raw']} files stuck in raw/, none processed to managed/")
        
        if len(raw_dirs) == 0:
            self.results['architectural_gaps'].append({
                'component': 'Directory Structure',
                'gap': 'NO_RAW_DIRECTORIES',
                'impact': 'HIGH',
                'evidence': 'No raw/ directories found in repository'
            })
            print("❌ No raw/ directories found")
    
    def analyze_test_contamination(self):
        """Analyze test file contamination evidence"""
        print("\n=== ANALYZING TEST CONTAMINATION EVIDENCE ===")
        
        # Find unauthorized test directories and files
        test_dirs = list(self.base_path.glob('**/tests'))
        test_files = list(self.base_path.glob('**/*test*.py'))
        validation_files = list(self.base_path.glob('**/*validation*.py'))
        
        contamination_evidence = {
            'unauthorized_test_dirs': [str(d) for d in test_dirs if 'project_management' not in str(d)],
            'test_files': [str(f) for f in test_files if f.name != 'architectural_failure_analysis.py'],
            'validation_files': [str(f) for f in validation_files if not f.name.startswith('project_')],
            'total_contamination_files': 0
        }
        
        # Count contamination
        contamination_count = len(contamination_evidence['unauthorized_test_dirs'])
        contamination_count += len(contamination_evidence['test_files']) 
        contamination_count += len(contamination_evidence['validation_files'])
        contamination_evidence['total_contamination_files'] = contamination_count
        
        self.results['filesystem_evidence']['contamination'] = contamination_evidence
        
        if contamination_count > 0:
            print(f"❌ REPOSITORY CONTAMINATION DETECTED: {contamination_count} unauthorized test files/dirs")
            
            for test_dir in contamination_evidence['unauthorized_test_dirs']:
                print(f"   • Unauthorized test directory: {test_dir}")
                
            self.results['architectural_gaps'].append({
                'component': 'Repository Hygiene',
                'gap': 'UNAUTHORIZED_TEST_CONTAMINATION',
                'impact': 'MEDIUM',
                'evidence': f"{contamination_count} unauthorized test files/directories found"
            })
        else:
            print("✅ No unauthorized test contamination detected")
    
    def analyze_model_architecture(self):
        """Analyze CRD model architecture"""
        print("\n=== ANALYZING CRD MODEL ARCHITECTURE ===")
        
        models_dir = self.base_path / 'netbox_hedgehog/models'
        model_files = list(models_dir.glob('*.py')) if models_dir.exists() else []
        
        model_analysis = {
            'models_directory_exists': models_dir.exists(),
            'model_files': [str(f.name) for f in model_files],
            'has_fabric_model': False,
            'has_crd_models': False
        }
        
        # Check for key model files
        fabric_model = models_dir / 'fabric.py'
        if fabric_model.exists():
            model_analysis['has_fabric_model'] = True
            with open(fabric_model, 'r') as f:
                content = f.read()
                
            # Check for GitHub-related fields
            has_git_url = 'git_repository_url' in content
            has_git_token = 'git_token' in content
            has_git_branch = 'git_branch' in content
            
            model_analysis['fabric_model'] = {
                'has_git_url_field': has_git_url,
                'has_git_token_field': has_git_token,
                'has_git_branch_field': has_git_branch
            }
            
            print(f"✅ Fabric model exists")
            print(f"   git_repository_url field: {'✅' if has_git_url else '❌'}")
            print(f"   git_token field: {'✅' if has_git_token else '❌'}")
            print(f"   git_branch field: {'✅' if has_git_branch else '❌'}")
            
            if not all([has_git_url, has_git_token, has_git_branch]):
                self.results['architectural_gaps'].append({
                    'component': 'Fabric Model',
                    'gap': 'MISSING_GITHUB_FIELDS',
                    'impact': 'CRITICAL',
                    'evidence': 'Fabric model missing required GitHub configuration fields'
                })
        else:
            print("❌ Fabric model not found")
            self.results['architectural_gaps'].append({
                'component': 'Fabric Model',
                'gap': 'MODEL_NOT_FOUND',
                'impact': 'CRITICAL',
                'evidence': 'Fabric model file does not exist'
            })
        
        # Check for CRD models
        crd_models = ['vpc.py', 'external.py', 'connection.py', 'server.py', 'switch.py']
        found_crd_models = [model for model in crd_models if (models_dir / model).exists()]
        
        model_analysis['found_crd_models'] = found_crd_models
        model_analysis['has_crd_models'] = len(found_crd_models) > 0
        
        print(f"CRD models found: {len(found_crd_models)}/{len(crd_models)}")
        for model in found_crd_models:
            print(f"   ✅ {model}")
            
        for model in crd_models:
            if model not in found_crd_models:
                print(f"   ❌ {model}")
        
        self.results['code_analysis']['models'] = model_analysis
        
        if len(found_crd_models) == 0:
            self.results['architectural_gaps'].append({
                'component': 'CRD Models',
                'gap': 'NO_CRD_MODELS',
                'impact': 'CRITICAL',
                'evidence': 'No CRD model files found'
            })
    
    def generate_architectural_report(self):
        """Generate comprehensive architectural failure report"""
        print("\n" + "=" * 70)
        print("📊 STATIC ARCHITECTURAL FAILURE ANALYSIS REPORT")
        print("=" * 70)
        
        print(f"\n⏱️  Analysis completed at: {self.results['timestamp']}")
        print(f"🔧 Evidence collected: {len(self.results['evidence_collected'])}")
        print(f"🚨 Architectural gaps: {len(self.results['architectural_gaps'])}")
        
        # Categorize gaps by impact
        critical_gaps = [g for g in self.results['architectural_gaps'] if g['impact'] == 'CRITICAL']
        high_gaps = [g for g in self.results['architectural_gaps'] if g['impact'] == 'HIGH']
        medium_gaps = [g for g in self.results['architectural_gaps'] if g['impact'] == 'MEDIUM']
        
        print(f"\n💥 CRITICAL ARCHITECTURAL GAPS ({len(critical_gaps)}):")
        for gap in critical_gaps:
            print(f"   • {gap['component']}: {gap['gap']}")
            print(f"     Evidence: {gap['evidence']}")
        
        if high_gaps:
            print(f"\n⚠️  HIGH IMPACT GAPS ({len(high_gaps)}):")
            for gap in high_gaps:
                print(f"   • {gap['component']}: {gap['gap']}")
        
        if medium_gaps:
            print(f"\n⚡ MEDIUM IMPACT GAPS ({len(medium_gaps)}):")
            for gap in medium_gaps:
                print(f"   • {gap['component']}: {gap['gap']}")
        
        # Root cause analysis
        if critical_gaps:
            print(f"\n🔍 ROOT CAUSE ANALYSIS:")
            print(f"   The FGD sync failure is caused by {len(critical_gaps)} critical architectural gaps.")
            print(f"   Primary failure points:")
            
            service_gaps = [g for g in critical_gaps if 'Service' in g['component']]
            model_gaps = [g for g in critical_gaps if 'Model' in g['component']]
            integration_gaps = [g for g in critical_gaps if 'Integration' in g['component']]
            
            if service_gaps:
                print(f"   • Service Layer: {len(service_gaps)} critical issues")
            if model_gaps:
                print(f"   • Data Model: {len(model_gaps)} critical issues")  
            if integration_gaps:
                print(f"   • Integration: {len(integration_gaps)} critical issues")
        
        # Implementation recommendations
        print(f"\n🔧 ARCHITECTURAL FIX RECOMMENDATIONS:")
        
        if critical_gaps:
            print("   IMMEDIATE (Critical):")
            for gap in critical_gaps:
                if 'MISSING_SYNC_METHOD' in gap['gap']:
                    print("   • Implement complete sync_cr_to_github() method in GitHubSyncService")
                elif 'NO_SYNC_CALLS' in gap['gap']:
                    print("   • Add GitHub sync service calls to signal handlers")
                elif 'MISSING_GITHUB_FIELDS' in gap['gap']:
                    print("   • Add required GitHub configuration fields to Fabric model")
                elif 'NO_RAW_TO_MANAGED_CONVERSION' in gap['gap']:
                    print("   • Implement raw/ to managed/ file processing workflow")
        
        return self.results
    
    def run_analysis(self):
        """Run complete static architectural analysis"""
        print("🔍 STARTING STATIC ARCHITECTURAL FAILURE ANALYSIS")
        print("=" * 70)
        
        self.analyze_service_architecture()
        self.analyze_github_repository_evidence()
        self.analyze_raw_directory_evidence()
        self.analyze_test_contamination()
        self.analyze_model_architecture()
        
        return self.generate_architectural_report()

def main():
    """Main execution function"""
    analyzer = StaticArchitecturalAnalyzer()
    
    try:
        results = analyzer.run_analysis()
        
        # Save results to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'/home/ubuntu/cc/hedgehog-netbox-plugin/static_architectural_analysis_{timestamp}.json'
        
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Full analysis report saved to: {report_file}")
        
        # Summary
        critical_gaps = len([g for g in results['architectural_gaps'] if g['impact'] == 'CRITICAL'])
        
        if critical_gaps > 0:
            print(f"\n💥 ANALYSIS COMPLETE: {critical_gaps} CRITICAL ARCHITECTURAL GAPS IDENTIFIED")
            print("   FGD sync failure root cause confirmed through static analysis")
            return report_file
        else:
            print(f"\n✅ ANALYSIS COMPLETE: No critical architectural gaps found")
            return report_file
            
    except Exception as e:
        print(f"\n💥 ANALYSIS FAILED: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None

if __name__ == "__main__":
    main()