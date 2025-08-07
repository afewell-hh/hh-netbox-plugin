#!/usr/bin/env python3
"""
Sync Execution Flow Diagnostic Script

This script traces the complete sync execution flow to identify where file processing stops.
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add Django setup
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

import django
try:
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    sys.exit(1)

from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.services.gitops_onboarding_service import GitOpsOnboardingService
from netbox_hedgehog.services.gitops_ingestion_service import GitOpsIngestionService
from netbox_hedgehog.signals import ensure_gitops_structure, ingest_fabric_raw_files
from netbox_hedgehog.views.sync_views import FabricGitHubSyncView
from netbox_hedgehog.views.fabric_views import FabricSyncView
from django.test import RequestFactory
from django.contrib.auth.models import User

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def diagnose_sync_execution():
    """Trace the complete sync execution flow"""
    
    results = {
        'fabric_analysis': {},
        'sync_mechanisms': {},
        'execution_paths': {},
        'file_processing': {},
        'failure_points': {}
    }
    
    print("=" * 80)
    print("SYNC EXECUTION FLOW DIAGNOSTIC")
    print("=" * 80)
    
    # 1. Find all fabrics
    print("\n1. FABRIC ANALYSIS")
    try:
        fabrics = HedgehogFabric.objects.all()
        print(f"Found {fabrics.count()} fabrics:")
        
        for fabric in fabrics:
            fabric_info = {
                'id': fabric.id,
                'name': fabric.name,
                'sync_status': getattr(fabric, 'sync_status', 'unknown'),
                'git_repository': bool(getattr(fabric, 'git_repository', None)),
                'git_repository_url': getattr(fabric, 'git_repository_url', None),
                'gitops_initialized': getattr(fabric, 'gitops_initialized', False)
            }
            results['fabric_analysis'][fabric.id] = fabric_info
            
            print(f"  - {fabric.name} (ID: {fabric.id})")
            print(f"    Status: {fabric_info['sync_status']}")
            print(f"    Git Repo: {fabric_info['git_repository']}")
            print(f"    Git URL: {fabric_info['git_repository_url']}")
            print(f"    GitOps Init: {fabric_info['gitops_initialized']}")
            
    except Exception as e:
        print(f"Error analyzing fabrics: {e}")
        results['fabric_analysis']['error'] = str(e)
    
    # 2. Test sync mechanisms
    print("\n2. SYNC MECHANISM ANALYSIS")
    
    # Test GitHub sync service
    print("\n2.1 GitHub Sync Service Test")
    try:
        # Get first fabric with git repo
        test_fabric = None
        for fabric in fabrics:
            if hasattr(fabric, 'git_repository') and fabric.git_repository:
                test_fabric = fabric
                break
        
        if test_fabric:
            print(f"Testing GitHub sync for fabric: {test_fabric.name}")
            
            # Test GitOpsOnboardingService
            try:
                onboarding_service = GitOpsOnboardingService(test_fabric)
                print("✓ GitOpsOnboardingService initialized successfully")
                results['sync_mechanisms']['github_onboarding_service'] = 'available'
                
                # Test sync_github_repository method availability
                if hasattr(onboarding_service, 'sync_github_repository'):
                    print("✓ sync_github_repository method available")
                    results['sync_mechanisms']['sync_github_repository'] = 'available'
                else:
                    print("✗ sync_github_repository method NOT available")
                    results['sync_mechanisms']['sync_github_repository'] = 'missing'
            except Exception as e:
                print(f"✗ GitOpsOnboardingService failed: {e}")
                results['sync_mechanisms']['github_onboarding_service'] = f'error: {e}'
                
        else:
            print("No fabric with git repository found for testing")
            results['sync_mechanisms']['github_test'] = 'no_fabric_available'
            
    except Exception as e:
        print(f"Error testing GitHub sync: {e}")
        results['sync_mechanisms']['github_error'] = str(e)
    
    # Test file ingestion service
    print("\n2.2 File Ingestion Service Test")
    try:
        if test_fabric:
            ingestion_service = GitOpsIngestionService(test_fabric)
            print("✓ GitOpsIngestionService initialized successfully")
            results['sync_mechanisms']['ingestion_service'] = 'available'
            
            # Test methods
            if hasattr(ingestion_service, 'process_raw_directory'):
                print("✓ process_raw_directory method available")
                results['sync_mechanisms']['process_raw_directory'] = 'available'
            else:
                print("✗ process_raw_directory method NOT available")
                results['sync_mechanisms']['process_raw_directory'] = 'missing'
        else:
            print("No test fabric available")
            results['sync_mechanisms']['ingestion_test'] = 'no_fabric_available'
            
    except Exception as e:
        print(f"Error testing ingestion service: {e}")
        results['sync_mechanisms']['ingestion_error'] = str(e)
    
    # 3. Test signal functions
    print("\n3. SIGNAL FUNCTION ANALYSIS")
    try:
        print("Testing signal functions availability:")
        
        # Test ensure_gitops_structure
        if callable(ensure_gitops_structure):
            print("✓ ensure_gitops_structure function available")
            results['sync_mechanisms']['ensure_gitops_structure'] = 'available'
        else:
            print("✗ ensure_gitops_structure function NOT available")
            results['sync_mechanisms']['ensure_gitops_structure'] = 'missing'
        
        # Test ingest_fabric_raw_files
        if callable(ingest_fabric_raw_files):
            print("✓ ingest_fabric_raw_files function available")
            results['sync_mechanisms']['ingest_fabric_raw_files'] = 'available'
        else:
            print("✗ ingest_fabric_raw_files function NOT available")
            results['sync_mechanisms']['ingest_fabric_raw_files'] = 'missing'
            
    except Exception as e:
        print(f"Error testing signal functions: {e}")
        results['sync_mechanisms']['signals_error'] = str(e)
    
    # 4. Test view execution paths
    print("\n4. VIEW EXECUTION PATH ANALYSIS")
    try:
        # Create mock request for testing
        factory = RequestFactory()
        
        # Get or create test user
        try:
            user = User.objects.get(username='admin')
        except User.DoesNotExist:
            user = User.objects.create_superuser('admin', 'admin@example.com', 'admin')
        
        if test_fabric:
            print(f"Testing view execution for fabric: {test_fabric.name}")
            
            # Test FabricGitHubSyncView
            print("\n4.1 FabricGitHubSyncView Test")
            try:
                request = factory.post(f'/plugins/hedgehog/fabrics/{test_fabric.id}/github-sync/')
                request.user = user
                
                view = FabricGitHubSyncView()
                view.setup(request)
                
                print("✓ FabricGitHubSyncView can be instantiated")
                results['execution_paths']['github_sync_view'] = 'available'
                
                # Test if view has post method
                if hasattr(view, 'post'):
                    print("✓ FabricGitHubSyncView.post method available")
                    results['execution_paths']['github_sync_post'] = 'available'
                else:
                    print("✗ FabricGitHubSyncView.post method NOT available")
                    results['execution_paths']['github_sync_post'] = 'missing'
                    
            except Exception as e:
                print(f"✗ FabricGitHubSyncView test failed: {e}")
                results['execution_paths']['github_sync_view'] = f'error: {e}'
            
            # Test FabricSyncView
            print("\n4.2 FabricSyncView Test")
            try:
                request = factory.post(f'/plugins/hedgehog/fabrics/{test_fabric.id}/sync/')
                request.user = user
                
                view = FabricSyncView()
                view.setup(request)
                
                print("✓ FabricSyncView can be instantiated")
                results['execution_paths']['fabric_sync_view'] = 'available'
                
                # Test if view has post method
                if hasattr(view, 'post'):
                    print("✓ FabricSyncView.post method available")
                    results['execution_paths']['fabric_sync_post'] = 'available'
                else:
                    print("✗ FabricSyncView.post method NOT available")
                    results['execution_paths']['fabric_sync_post'] = 'missing'
                    
            except Exception as e:
                print(f"✗ FabricSyncView test failed: {e}")
                results['execution_paths']['fabric_sync_view'] = f'error: {e}'
                
        else:
            print("No test fabric available for view testing")
            results['execution_paths']['view_test'] = 'no_fabric_available'
            
    except Exception as e:
        print(f"Error testing view execution: {e}")
        results['execution_paths']['view_error'] = str(e)
    
    # 5. File processing analysis
    print("\n5. FILE PROCESSING ANALYSIS")
    try:
        if test_fabric:
            print(f"Checking file processing for fabric: {test_fabric.name}")
            
            # Check if raw directory exists and has files
            try:
                # Try to determine raw directory path
                onboarding_service = GitOpsOnboardingService(test_fabric)
                
                # Check if we can initialize paths
                if hasattr(onboarding_service, '_determine_base_directory_path'):
                    print("✓ Can determine base directory path")
                    results['file_processing']['path_determination'] = 'available'
                else:
                    print("✗ Cannot determine base directory path")
                    results['file_processing']['path_determination'] = 'missing'
                    
            except Exception as e:
                print(f"Error checking file processing paths: {e}")
                results['file_processing']['path_error'] = str(e)
                
        else:
            print("No test fabric available for file processing analysis")
            results['file_processing']['analysis'] = 'no_fabric_available'
            
    except Exception as e:
        print(f"Error analyzing file processing: {e}")
        results['file_processing']['error'] = str(e)
    
    # 6. Identify potential failure points
    print("\n6. FAILURE POINT IDENTIFICATION")
    
    failure_points = []
    
    # Check for missing services
    if results['sync_mechanisms'].get('github_onboarding_service') != 'available':
        failure_points.append("GitOpsOnboardingService not available")
    
    if results['sync_mechanisms'].get('ingestion_service') != 'available':
        failure_points.append("GitOpsIngestionService not available")
    
    if results['sync_mechanisms'].get('sync_github_repository') != 'available':
        failure_points.append("sync_github_repository method not available")
    
    if results['sync_mechanisms'].get('process_raw_directory') != 'available':
        failure_points.append("process_raw_directory method not available")
    
    # Check for missing signal functions
    if results['sync_mechanisms'].get('ensure_gitops_structure') != 'available':
        failure_points.append("ensure_gitops_structure function not available")
    
    if results['sync_mechanisms'].get('ingest_fabric_raw_files') != 'available':
        failure_points.append("ingest_fabric_raw_files function not available")
    
    # Check for missing view methods
    if results['execution_paths'].get('github_sync_post') != 'available':
        failure_points.append("FabricGitHubSyncView.post method not available")
    
    if results['execution_paths'].get('fabric_sync_post') != 'available':
        failure_points.append("FabricSyncView.post method not available")
    
    results['failure_points']['identified'] = failure_points
    
    print("Potential failure points identified:")
    for i, point in enumerate(failure_points, 1):
        print(f"  {i}. {point}")
    
    if not failure_points:
        print("  No obvious failure points detected - issue may be deeper in execution flow")
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)
    
    return results

if __name__ == "__main__":
    try:
        results = diagnose_sync_execution()
        
        # Save results to file
        output_file = Path("/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/active_projects/qapm_20250804_171500_issue_1_continuation/04_sub_agent_work/backend_investigation/sync_execution_diagnostic_results.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\nResults saved to: {output_file}")
        
    except Exception as e:
        print(f"Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)