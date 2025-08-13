#!/usr/bin/env python3
"""
GitHub API Execution Tracer
===========================

MISSION: Determine if GitHub API calls are happening and succeeding/failing.

This script traces the complete GitHub API execution workflow:
1. Direct API call testing from service layer
2. Signal handler tracing when CRD is saved/updated
3. Authentication verification
4. Repository state checking

Agent #15 proved authentication works - this traces actual API execution.
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from pathlib import Path

# Setup Django environment
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

import django
django.setup()

# Setup comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('github_api_trace.log', mode='w')
    ]
)

logger = logging.getLogger('github_api_tracer')

# Enable API trace logging
api_trace_logger = logging.getLogger('netbox_hedgehog.services.github_sync_service.api_trace')
api_trace_logger.setLevel(logging.DEBUG)
api_trace_handler = logging.StreamHandler()
api_trace_handler.setFormatter(logging.Formatter('API_TRACE: %(message)s'))
api_trace_logger.addHandler(api_trace_handler)

# Enable signals logging
signals_logger = logging.getLogger('netbox_hedgehog.signals')
signals_logger.setLevel(logging.DEBUG)


def test_direct_api_execution():
    """Test 1: Direct GitHub API execution via service."""
    
    logger.info("=" * 60)
    logger.info("TEST 1: DIRECT GITHUB API SERVICE EXECUTION")
    logger.info("=" * 60)
    
    try:
        from netbox_hedgehog.models import HedgehogFabric, VPC
        from netbox_hedgehog.services.github_sync_service import GitHubSyncService
        
        # Get a fabric with GitHub configuration
        fabric = HedgehogFabric.objects.filter(
            git_repository_url__isnull=False
        ).first()
        
        if not fabric:
            logger.error("No fabric found with GitHub configuration!")
            return False
        
        logger.info(f"Testing with fabric: {fabric.name}")
        logger.info(f"GitHub URL: {fabric.git_repository_url}")
        
        # Test service initialization
        logger.info("Initializing GitHubSyncService...")
        github_service = GitHubSyncService(fabric)
        
        # Test connection first
        logger.info("Testing GitHub API connection...")
        connection_result = github_service.test_connection()
        logger.info(f"Connection test result: {connection_result}")
        
        if not connection_result.get('success'):
            logger.error(f"GitHub connection failed: {connection_result.get('error')}")
            return False
        
        # Get or create a test VPC
        test_vpc, created = VPC.objects.get_or_create(
            name='api-test-vpc',
            fabric=fabric,
            defaults={
                'subnet': '10.1.0.0/16',
                'namespace': 'default'
            }
        )
        
        logger.info(f"Test VPC: {test_vpc.name} (created: {created})")
        
        # Direct API sync test
        logger.info("Testing direct sync_cr_to_github call...")
        operation = 'create' if created else 'update'
        
        result = github_service.sync_cr_to_github(
            test_vpc,
            operation=operation,
            user='api_tracer',
            commit_message=f"API Test: {operation} VPC via direct service call at {datetime.now()}"
        )
        
        logger.info(f"Direct sync result: {result}")
        
        if result['success']:
            logger.info("✅ DIRECT API CALL SUCCESSFUL!")
            logger.info(f"Commit SHA: {result.get('commit_sha')}")
            logger.info(f"File path: {result.get('file_path')}")
            return True
        else:
            logger.error(f"❌ DIRECT API CALL FAILED: {result.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Exception in direct API test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_signal_triggered_execution():
    """Test 2: GitHub API execution via Django signals."""
    
    logger.info("=" * 60)
    logger.info("TEST 2: SIGNAL-TRIGGERED GITHUB API EXECUTION")
    logger.info("=" * 60)
    
    try:
        from netbox_hedgehog.models import HedgehogFabric, VPC
        
        # Get a fabric with GitHub configuration
        fabric = HedgehogFabric.objects.filter(
            git_repository_url__isnull=False
        ).first()
        
        if not fabric:
            logger.error("No fabric found with GitHub configuration!")
            return False
        
        logger.info(f"Testing with fabric: {fabric.name}")
        
        # Create a new VPC to trigger signals
        test_vpc_name = f'signal-test-vpc-{int(time.time())}'
        logger.info(f"Creating VPC '{test_vpc_name}' to trigger post_save signal...")
        
        # This should trigger the on_crd_saved signal which calls GitHub sync
        test_vpc = VPC.objects.create(
            name=test_vpc_name,
            fabric=fabric,
            subnet='10.2.0.0/16',
            namespace='default'
        )
        
        logger.info(f"VPC created: {test_vpc.name}")
        logger.info("Signal should have triggered GitHub sync automatically")
        
        # Check if the VPC has git metadata set (indicates successful sync)
        test_vpc.refresh_from_db()
        
        if hasattr(test_vpc, 'git_file_path') and test_vpc.git_file_path:
            logger.info(f"✅ SIGNAL-TRIGGERED SYNC SUCCESSFUL!")
            logger.info(f"Git file path: {test_vpc.git_file_path}")
            logger.info(f"Last synced: {test_vpc.last_synced}")
            return True
        else:
            logger.warning("⚠️ Signal triggered but no git metadata found")
            # Check if sync failed or if signal didn't fire
            logger.info("Checking for sync errors in logs...")
            return False
            
    except Exception as e:
        logger.error(f"Exception in signal test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_github_repository_state():
    """Test 3: Check if changes are actually appearing in GitHub repository."""
    
    logger.info("=" * 60)
    logger.info("TEST 3: GITHUB REPOSITORY STATE VERIFICATION")
    logger.info("=" * 60)
    
    try:
        import requests
        from netbox_hedgehog.models import HedgehogFabric
        from netbox_hedgehog.services.github_sync_service import GitHubSyncService
        
        # Get a fabric with GitHub configuration
        fabric = HedgehogFabric.objects.filter(
            git_repository_url__isnull=False
        ).first()
        
        if not fabric:
            logger.error("No fabric found with GitHub configuration!")
            return False
        
        github_service = GitHubSyncService(fabric)
        
        # Check repository recent commits
        commits_url = f"{github_service.api_base}/commits"
        params = {
            'per_page': 10,
            'branch': fabric.git_branch or 'main'
        }
        
        logger.info(f"Checking recent commits in {github_service.owner}/{github_service.repo}")
        response = requests.get(commits_url, headers=github_service.headers, params=params)
        
        if response.status_code == 200:
            commits = response.json()
            logger.info(f"Found {len(commits)} recent commits")
            
            # Check for HNP-related commits
            hnp_commits = []
            for commit in commits:
                message = commit.get('commit', {}).get('message', '')
                if 'HNP' in message or 'hedgehog' in message.lower() or 'netbox' in message.lower():
                    hnp_commits.append({
                        'sha': commit['sha'][:8],
                        'message': message[:100],
                        'date': commit.get('commit', {}).get('author', {}).get('date')
                    })
            
            if hnp_commits:
                logger.info(f"✅ Found {len(hnp_commits)} HNP-related commits:")
                for commit in hnp_commits:
                    logger.info(f"  {commit['sha']}: {commit['message']} ({commit['date']})")
                return True
            else:
                logger.warning("⚠️ No HNP-related commits found in recent history")
                logger.info("Recent commit messages:")
                for commit in commits[:5]:
                    message = commit.get('commit', {}).get('message', '')
                    logger.info(f"  {commit['sha'][:8]}: {message[:100]}")
                return False
        else:
            logger.error(f"Failed to fetch commits: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Exception in repository state test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_authentication_and_permissions():
    """Test 4: Verify GitHub authentication and repository permissions."""
    
    logger.info("=" * 60)
    logger.info("TEST 4: GITHUB AUTHENTICATION & PERMISSIONS")
    logger.info("=" * 60)
    
    try:
        from netbox_hedgehog.models import HedgehogFabric
        from netbox_hedgehog.services.github_sync_service import GitHubSyncService
        
        # Get a fabric with GitHub configuration
        fabric = HedgehogFabric.objects.filter(
            git_repository_url__isnull=False
        ).first()
        
        if not fabric:
            logger.error("No fabric found with GitHub configuration!")
            return False
        
        github_service = GitHubSyncService(fabric)
        
        # Test connection and permissions
        connection_result = github_service.test_connection()
        
        if connection_result['success']:
            logger.info("✅ AUTHENTICATION SUCCESSFUL!")
            logger.info(f"Repository: {connection_result.get('repo_name')}")
            logger.info(f"Default branch: {connection_result.get('default_branch')}")
            logger.info(f"Permissions: {connection_result.get('permissions')}")
            return True
        else:
            logger.error(f"❌ AUTHENTICATION FAILED: {connection_result.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Exception in authentication test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Run comprehensive GitHub API execution analysis."""
    
    logger.info("GitHub API Execution Tracer Starting...")
    logger.info("Agent #15 Investigation: Are GitHub API calls actually executing?")
    logger.info(f"Timestamp: {datetime.now()}")
    
    results = {}
    
    # Test 1: Authentication and permissions
    logger.info("\n🔐 Testing GitHub authentication and permissions...")
    results['authentication'] = test_authentication_and_permissions()
    
    # Test 2: Direct API execution
    logger.info("\n🚀 Testing direct GitHub API service execution...")
    results['direct_api'] = test_direct_api_execution()
    
    # Test 3: Signal-triggered execution
    logger.info("\n📡 Testing signal-triggered GitHub API execution...")
    results['signal_triggered'] = test_signal_triggered_execution()
    
    # Test 4: Repository state verification
    logger.info("\n📊 Testing GitHub repository state...")
    results['repository_state'] = test_github_repository_state()
    
    # Final analysis
    logger.info("\n" + "=" * 60)
    logger.info("GITHUB API EXECUTION ANALYSIS COMPLETE")
    logger.info("=" * 60)
    
    success_count = sum(1 for result in results.values() if result)
    total_tests = len(results)
    
    logger.info(f"Tests passed: {success_count}/{total_tests}")
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")
    
    if success_count == total_tests:
        logger.info("\n🎉 ALL TESTS PASSED - GitHub API is executing correctly!")
        conclusion = "GitHub API calls are executing successfully"
    elif success_count == 0:
        logger.error("\n💥 ALL TESTS FAILED - GitHub API calls are NOT executing!")
        conclusion = "GitHub API calls are failing completely"
    else:
        logger.warning(f"\n⚠️ PARTIAL SUCCESS - {success_count}/{total_tests} tests passed")
        conclusion = "GitHub API calls are partially working"
    
    # Save results
    report = {
        'timestamp': datetime.now().isoformat(),
        'conclusion': conclusion,
        'test_results': results,
        'success_rate': f"{success_count}/{total_tests}"
    }
    
    with open('github_api_execution_analysis.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"\nDetailed report saved to github_api_execution_analysis.json")
    logger.info(f"API trace log saved to github_api_trace.log")
    
    return results


if __name__ == '__main__':
    main()