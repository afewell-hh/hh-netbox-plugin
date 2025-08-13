#!/usr/bin/env python3
"""
ARCHITECTURAL FAILURE ANALYSIS SCRIPT
=====================================

Purpose: Test every component of the FGD sync workflow to identify where the actual failure occurs.
This script will provide evidence-based analysis of what works vs what fails.

CRITICAL FAILURE EVIDENCE:
- GitHub repository shows NO commits during work period (except one test file)
- Pre-sync test now FAILS 2/5 (contaminated with test artifacts) 
- Post-sync test FAILS 3/4 (no actual sync occurred - 48 CRs still in raw/)
- Repository polluted with unauthorized "tests" directory
"""

import os
import sys
import django
import traceback
import json
import requests
from pathlib import Path
from datetime import datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
sys.path.insert(0, '/opt/netbox')

try:
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    sys.exit(1)

class ArchitecturalFailureAnalyzer:
    """Comprehensive architectural failure analysis"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'analysis_type': 'architectural_failure_investigation',
            'components_tested': [],
            'failures_identified': [],
            'working_components': [],
            'critical_gaps': []
        }
    
    def test_fabric_configuration(self):
        """Test fabric model and configuration completeness"""
        print("\n=== TESTING FABRIC CONFIGURATION ===")
        
        try:
            from netbox_hedgehog.models import HedgehogFabric
            
            fabrics = HedgehogFabric.objects.all()
            print(f"Total fabrics found: {fabrics.count()}")
            
            if fabrics.count() == 0:
                self.failures_identified.append({
                    'component': 'fabric_configuration',
                    'failure': 'NO_FABRICS_FOUND',
                    'evidence': 'HedgehogFabric.objects.all() returned 0 results',
                    'impact': 'CRITICAL - Cannot sync without fabric'
                })
                return False
                
            for fabric in fabrics:
                print(f"\nTesting Fabric: {fabric.name} (ID: {fabric.id})")
                
                # Test required fields for GitHub sync
                required_fields = {
                    'git_repository_url': fabric.git_repository_url,
                    'git_branch': fabric.git_branch,
                    'git_token': fabric.git_token,
                }
                
                missing_fields = []
                for field, value in required_fields.items():
                    if not value:
                        missing_fields.append(field)
                        print(f"  ❌ {field}: NOT SET")
                    else:
                        print(f"  ✅ {field}: SET")
                        if field == 'git_token':
                            print(f"     Token preview: {value[:8]}...")
                        elif field == 'git_repository_url':
                            print(f"     URL: {value}")
                        else:
                            print(f"     Value: {value}")
                
                if missing_fields:
                    self.failures_identified.append({
                        'component': 'fabric_configuration',
                        'failure': 'MISSING_GITHUB_CONFIG',
                        'fabric': fabric.name,
                        'missing_fields': missing_fields,
                        'evidence': f'Required GitHub configuration fields missing: {missing_fields}',
                        'impact': 'CRITICAL - Cannot sync to GitHub without these fields'
                    })
                    return False
                else:
                    self.working_components.append({
                        'component': 'fabric_configuration',
                        'fabric': fabric.name,
                        'status': 'CONFIGURED'
                    })
                    return fabric
                    
        except ImportError as e:
            self.failures_identified.append({
                'component': 'fabric_model',
                'failure': 'IMPORT_ERROR',
                'evidence': str(e),
                'impact': 'CRITICAL - Cannot import HedgehogFabric model'
            })
            return False
        except Exception as e:
            self.failures_identified.append({
                'component': 'fabric_configuration',
                'failure': 'UNEXPECTED_ERROR',
                'evidence': str(e),
                'traceback': traceback.format_exc(),
                'impact': 'CRITICAL'
            })
            return False
    
    def test_github_authentication(self, fabric):
        """Test GitHub API authentication and repository access"""
        print(f"\n=== TESTING GITHUB AUTHENTICATION (Fabric: {fabric.name}) ===")
        
        try:
            from netbox_hedgehog.services.github_sync_service import GitHubSyncService
            
            print("Creating GitHubSyncService...")
            github_service = GitHubSyncService(fabric)
            print("✅ GitHubSyncService created successfully")
            
            print("Testing GitHub API connection...")
            connection_result = github_service.test_connection()
            
            print(f"Connection test result: {connection_result}")
            
            if connection_result['success']:
                print("✅ GitHub API authentication SUCCESSFUL")
                self.working_components.append({
                    'component': 'github_authentication',
                    'status': 'WORKING',
                    'repo': f"{github_service.owner}/{github_service.repo}",
                    'permissions': connection_result.get('permissions', {})
                })
                return github_service
            else:
                print(f"❌ GitHub API authentication FAILED")
                self.failures_identified.append({
                    'component': 'github_authentication',
                    'failure': 'API_CONNECTION_FAILED',
                    'evidence': connection_result,
                    'impact': 'CRITICAL - Cannot sync to GitHub without API access'
                })
                return None
                
        except Exception as e:
            print(f"❌ Exception during GitHub authentication test: {e}")
            self.failures_identified.append({
                'component': 'github_authentication',
                'failure': 'SERVICE_CREATION_FAILED',
                'evidence': str(e),
                'traceback': traceback.format_exc(),
                'impact': 'CRITICAL'
            })
            return None
    
    def test_crd_models_and_signals(self):
        """Test CRD model availability and signal registration"""
        print("\n=== TESTING CRD MODELS AND SIGNAL INTEGRATION ===")
        
        try:
            # Test CRD model imports
            print("Testing CRD model imports...")
            
            crd_models = [
                'VPC', 'External', 'ExternalAttachment', 'ExternalPeering',
                'IPv4Namespace', 'VPCAttachment', 'VPCPeering',
                'Connection', 'Server', 'Switch', 'SwitchGroup', 'VLANNamespace'
            ]
            
            available_models = []
            missing_models = []
            
            for model_name in crd_models:
                try:
                    from django.apps import apps
                    model_class = apps.get_model('netbox_hedgehog', model_name)
                    available_models.append(model_name)
                    print(f"  ✅ {model_name} model available")
                    
                    # Test if model has required methods
                    if hasattr(model_class, 'get_kind') and hasattr(model_class, 'fabric'):
                        print(f"    ✅ {model_name} has required methods (get_kind, fabric)")
                    else:
                        print(f"    ❌ {model_name} missing required methods")
                        self.failures_identified.append({
                            'component': 'crd_models',
                            'failure': 'MISSING_REQUIRED_METHODS',
                            'model': model_name,
                            'missing_methods': [m for m in ['get_kind', 'fabric'] if not hasattr(model_class, m)],
                            'impact': 'HIGH - Sync will fail for this model'
                        })
                        
                except Exception as e:
                    missing_models.append(model_name)
                    print(f"  ❌ {model_name} model NOT available: {e}")
            
            if missing_models:
                self.failures_identified.append({
                    'component': 'crd_models',
                    'failure': 'MODELS_NOT_AVAILABLE',
                    'missing_models': missing_models,
                    'evidence': f'{len(missing_models)} CRD models not available',
                    'impact': 'CRITICAL - Cannot sync these CRD types'
                })
            
            if available_models:
                self.working_components.append({
                    'component': 'crd_models',
                    'available_models': available_models,
                    'count': len(available_models)
                })
            
            # Test signal registration
            print("\nTesting signal registration...")
            
            try:
                from netbox_hedgehog import signals
                print("✅ Signals module imported successfully")
                
                # Check if signal handlers are defined
                signal_handlers = [
                    'on_crd_saved', 'on_crd_deleted', 'on_crd_pre_delete',
                    'on_fabric_saved', 'on_gitops_resource_saved'
                ]
                
                for handler_name in signal_handlers:
                    if hasattr(signals, handler_name):
                        print(f"  ✅ Signal handler {handler_name} defined")
                    else:
                        print(f"  ❌ Signal handler {handler_name} NOT defined")
                        
                self.working_components.append({
                    'component': 'signal_handlers',
                    'status': 'IMPORTED'
                })
                
            except ImportError as e:
                print(f"❌ Failed to import signals module: {e}")
                self.failures_identified.append({
                    'component': 'signal_handlers',
                    'failure': 'IMPORT_FAILED',
                    'evidence': str(e),
                    'impact': 'CRITICAL - No automatic sync without signals'
                })
            
            return len(available_models) > 0
            
        except Exception as e:
            self.failures_identified.append({
                'component': 'crd_models_and_signals',
                'failure': 'UNEXPECTED_ERROR',
                'evidence': str(e),
                'traceback': traceback.format_exc(),
                'impact': 'CRITICAL'
            })
            return False
    
    def test_signal_execution_flow(self, fabric, github_service):
        """Test actual signal execution by creating a CRD"""
        print(f"\n=== TESTING SIGNAL EXECUTION FLOW ===")
        
        try:
            from django.apps import apps
            from django.db import transaction
            
            # Try to get VPC model for testing
            VPC = apps.get_model('netbox_hedgehog', 'VPC')
            
            print("Creating test VPC to trigger signals...")
            
            test_vpc_name = f"test-vpc-analysis-{int(datetime.now().timestamp())}"
            
            with transaction.atomic():
                # Create test VPC
                test_vpc = VPC.objects.create(
                    name=test_vpc_name,
                    fabric=fabric,
                    namespace='default',
                    spec='{"subnets": []}'
                )
                
                print(f"✅ Created test VPC: {test_vpc_name}")
                
                # Wait a moment for signals to process
                import time
                time.sleep(2)
                
                # Check if GitHub sync actually occurred
                print("Checking if GitHub sync occurred...")
                
                # Try to find the file in GitHub
                expected_path = f"fabrics/{fabric.name.lower()}/gitops/managed/vpcs/{test_vpc_name}.yaml"
                
                try:
                    file_info = github_service._get_file_from_github(expected_path)
                    if file_info:
                        print(f"✅ File found in GitHub: {expected_path}")
                        self.working_components.append({
                            'component': 'signal_execution',
                            'status': 'WORKING',
                            'test_file': expected_path,
                            'evidence': 'Signal triggered GitHub sync successfully'
                        })
                        signal_success = True
                    else:
                        print(f"❌ File NOT found in GitHub: {expected_path}")
                        self.failures_identified.append({
                            'component': 'signal_execution',
                            'failure': 'NO_GITHUB_SYNC',
                            'expected_path': expected_path,
                            'evidence': 'Signal did not trigger GitHub sync',
                            'impact': 'CRITICAL - Main workflow broken'
                        })
                        signal_success = False
                        
                except Exception as e:
                    print(f"❌ Error checking GitHub file: {e}")
                    signal_success = False
                
                # Clean up test VPC
                test_vpc.delete()
                print(f"🧹 Cleaned up test VPC: {test_vpc_name}")
                
                return signal_success
                
        except Exception as e:
            print(f"❌ Signal execution test failed: {e}")
            self.failures_identified.append({
                'component': 'signal_execution',
                'failure': 'TEST_EXECUTION_FAILED',
                'evidence': str(e),
                'traceback': traceback.format_exc(),
                'impact': 'CRITICAL'
            })
            return False
    
    def test_github_operations(self, github_service):
        """Test actual GitHub file operations"""
        print(f"\n=== TESTING GITHUB FILE OPERATIONS ===")
        
        try:
            test_content = """# Test file for architectural analysis
apiVersion: vpc.githedgehog.com/v1alpha2
kind: VPC
metadata:
  name: test-analysis-vpc
  namespace: default
spec:
  subnets: []
"""
            test_path = f"test-analysis-{int(datetime.now().timestamp())}.yaml"
            
            print(f"Testing file creation in GitHub: {test_path}")
            
            # Test file creation
            create_result = github_service._create_file_in_github(
                test_path,
                test_content,
                "Test file creation for architectural analysis"
            )
            
            print(f"Create result: {create_result}")
            
            if create_result['success']:
                print("✅ File creation SUCCESSFUL")
                
                # Test file retrieval
                print("Testing file retrieval...")
                file_info = github_service._get_file_from_github(test_path)
                
                if file_info:
                    print("✅ File retrieval SUCCESSFUL")
                    
                    # Test file deletion (cleanup)
                    print("Testing file deletion...")
                    delete_result = github_service._delete_file_from_github(
                        test_path,
                        file_info['sha'],
                        "Clean up test file"
                    )
                    
                    if delete_result['success']:
                        print("✅ File deletion SUCCESSFUL")
                        self.working_components.append({
                            'component': 'github_operations',
                            'operations_tested': ['create', 'retrieve', 'delete'],
                            'status': 'ALL_WORKING'
                        })
                        return True
                    else:
                        print(f"❌ File deletion FAILED: {delete_result}")
                        self.failures_identified.append({
                            'component': 'github_operations',
                            'failure': 'DELETE_OPERATION_FAILED',
                            'evidence': delete_result,
                            'impact': 'MEDIUM - Creates orphaned files'
                        })
                        return False
                else:
                    print("❌ File retrieval FAILED")
                    self.failures_identified.append({
                        'component': 'github_operations',
                        'failure': 'RETRIEVE_OPERATION_FAILED',
                        'evidence': 'Created file could not be retrieved',
                        'impact': 'HIGH - Cannot verify sync results'
                    })
                    return False
            else:
                print(f"❌ File creation FAILED: {create_result}")
                self.failures_identified.append({
                    'component': 'github_operations',
                    'failure': 'CREATE_OPERATION_FAILED',
                    'evidence': create_result,
                    'impact': 'CRITICAL - Cannot sync to GitHub'
                })
                return False
                
        except Exception as e:
            print(f"❌ GitHub operations test failed: {e}")
            self.failures_identified.append({
                'component': 'github_operations',
                'failure': 'OPERATIONS_TEST_FAILED',
                'evidence': str(e),
                'traceback': traceback.format_exc(),
                'impact': 'CRITICAL'
            })
            return False
    
    def test_raw_directory_operations(self, fabric):
        """Test raw directory file processing"""
        print(f"\n=== TESTING RAW DIRECTORY OPERATIONS ===")
        
        try:
            # Check if raw directory path is configured
            if hasattr(fabric, 'raw_directory_path') and fabric.raw_directory_path:
                raw_path = Path(fabric.raw_directory_path)
                print(f"Raw directory configured: {raw_path}")
                
                if raw_path.exists():
                    print("✅ Raw directory exists")
                    
                    # Count files
                    yaml_files = list(raw_path.glob('*.yaml')) + list(raw_path.glob('*.yml'))
                    print(f"YAML files in raw directory: {len(yaml_files)}")
                    
                    if yaml_files:
                        self.working_components.append({
                            'component': 'raw_directory',
                            'path': str(raw_path),
                            'file_count': len(yaml_files),
                            'status': 'FILES_PRESENT'
                        })
                        
                        # Test ingestion service
                        try:
                            from netbox_hedgehog.services.gitops_ingestion_service import GitOpsIngestionService
                            
                            ingestion_service = GitOpsIngestionService(fabric)
                            print("✅ GitOpsIngestionService created")
                            
                            # This is where we would test actual ingestion
                            # but we don't want to modify state during analysis
                            self.working_components.append({
                                'component': 'ingestion_service',
                                'status': 'SERVICE_AVAILABLE'
                            })
                            
                        except ImportError as e:
                            print(f"❌ GitOpsIngestionService not available: {e}")
                            self.failures_identified.append({
                                'component': 'ingestion_service',
                                'failure': 'SERVICE_NOT_AVAILABLE',
                                'evidence': str(e),
                                'impact': 'HIGH - Cannot process raw files'
                            })
                    else:
                        print("⚠️ Raw directory is empty")
                        self.failures_identified.append({
                            'component': 'raw_directory',
                            'failure': 'DIRECTORY_EMPTY',
                            'evidence': 'No YAML files found in raw directory',
                            'impact': 'MEDIUM - Nothing to sync'
                        })
                else:
                    print("❌ Raw directory does not exist")
                    self.failures_identified.append({
                        'component': 'raw_directory',
                        'failure': 'DIRECTORY_NOT_FOUND',
                        'path': str(raw_path),
                        'evidence': 'Configured raw directory path does not exist',
                        'impact': 'HIGH - Cannot access files to sync'
                    })
            else:
                print("⚠️ Raw directory path not configured")
                self.failures_identified.append({
                    'component': 'raw_directory',
                    'failure': 'PATH_NOT_CONFIGURED',
                    'evidence': 'Fabric.raw_directory_path is not set',
                    'impact': 'HIGH - Cannot locate files to sync'
                })
                
        except Exception as e:
            print(f"❌ Raw directory test failed: {e}")
            self.failures_identified.append({
                'component': 'raw_directory',
                'failure': 'TEST_FAILED',
                'evidence': str(e),
                'traceback': traceback.format_exc(),
                'impact': 'HIGH'
            })
    
    def run_analysis(self):
        """Run complete architectural failure analysis"""
        print("🔍 STARTING COMPREHENSIVE ARCHITECTURAL FAILURE ANALYSIS")
        print("=" * 70)
        
        self.components_tested.append('fabric_configuration')
        fabric = self.test_fabric_configuration()
        
        if not fabric:
            print("❌ CRITICAL: Cannot proceed without fabric configuration")
            return self.generate_report()
        
        self.components_tested.append('github_authentication')
        github_service = self.test_github_authentication(fabric)
        
        if not github_service:
            print("❌ CRITICAL: Cannot proceed without GitHub authentication")
            return self.generate_report()
        
        self.components_tested.append('crd_models_and_signals')
        models_ok = self.test_crd_models_and_signals()
        
        self.components_tested.append('github_operations')
        github_ops_ok = self.test_github_operations(github_service)
        
        self.components_tested.append('signal_execution')
        if models_ok and github_ops_ok:
            signals_ok = self.test_signal_execution_flow(fabric, github_service)
        else:
            print("⚠️ Skipping signal execution test due to prerequisite failures")
            signals_ok = False
        
        self.components_tested.append('raw_directory')
        self.test_raw_directory_operations(fabric)
        
        return self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive architectural failure analysis report"""
        self.results['components_tested'] = self.components_tested
        
        print("\n" + "=" * 70)
        print("📊 ARCHITECTURAL FAILURE ANALYSIS REPORT")
        print("=" * 70)
        
        print(f"\n⏱️  Analysis completed at: {self.results['timestamp']}")
        print(f"🔧 Components tested: {len(self.components_tested)}")
        print(f"✅ Working components: {len(self.working_components)}")
        print(f"❌ Failures identified: {len(self.failures_identified)}")
        
        if self.working_components:
            print(f"\n✅ WORKING COMPONENTS ({len(self.working_components)}):")
            for component in self.working_components:
                print(f"   • {component['component']}: {component.get('status', 'OK')}")
        
        if self.failures_identified:
            print(f"\n❌ CRITICAL FAILURES ({len(self.failures_identified)}):")
            for failure in self.failures_identified:
                print(f"   • {failure['component']}: {failure['failure']}")
                print(f"     Impact: {failure['impact']}")
                if 'evidence' in failure:
                    print(f"     Evidence: {failure['evidence']}")
        
        # Identify root cause
        critical_failures = [f for f in self.failures_identified if f['impact'] == 'CRITICAL']
        
        if critical_failures:
            print(f"\n🚨 ROOT CAUSE ANALYSIS:")
            print(f"   Found {len(critical_failures)} critical failures that prevent sync:")
            for failure in critical_failures:
                print(f"   • {failure['component']}: {failure['failure']}")
        
        # Generate architectural gaps summary
        self.critical_gaps = [
            {
                'gap': failure['failure'],
                'component': failure['component'], 
                'impact': failure['impact'],
                'evidence': failure.get('evidence', 'No evidence provided')
            }
            for failure in self.failures_identified
            if failure['impact'] == 'CRITICAL'
        ]
        
        self.results['critical_gaps'] = self.critical_gaps
        
        return self.results

def main():
    """Main execution function"""
    analyzer = ArchitecturalFailureAnalyzer()
    
    try:
        results = analyzer.run_analysis()
        
        # Save results to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'/home/ubuntu/cc/hedgehog-netbox-plugin/architectural_failure_analysis_{timestamp}.json'
        
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Full analysis report saved to: {report_file}")
        
        # Return exit code based on critical failures
        critical_failures = len([f for f in results['failures_identified'] if f['impact'] == 'CRITICAL'])
        
        if critical_failures > 0:
            print(f"\n💥 ANALYSIS COMPLETE: {critical_failures} CRITICAL FAILURES IDENTIFIED")
            sys.exit(1)
        else:
            print(f"\n✅ ANALYSIS COMPLETE: No critical failures found")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n💥 ANALYSIS FAILED WITH EXCEPTION: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(2)

if __name__ == "__main__":
    main()