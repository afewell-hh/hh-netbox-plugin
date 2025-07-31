#!/usr/bin/env python3
"""
Check the current state of HCKC fabric and git repositories for architecture research
"""

from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.models.git_repository import GitRepository

def main():
    print("=== HNP Fabric Sync Architecture Research ===\n")
    
    # Show current HCKC fabric
    try:
        fabric = HedgehogFabric.objects.get(pk=19)
        print('=== HCKC Fabric (ID 19) Current State ===')
        print(f'Name: {fabric.name}')
        print(f'Status: {fabric.status}')
        print(f'Connection Status: {fabric.connection_status}')
        print(f'Sync Status: {fabric.sync_status}')
        print(f'Git Repository (FK): {fabric.git_repository}')
        print(f'GitOps Directory: {fabric.gitops_directory}')
        print(f'Git Repository URL (legacy): {fabric.git_repository_url}')
        print(f'Git Path (legacy): {fabric.git_path}')
        print(f'Git Branch (legacy): {fabric.git_branch}')
        print(f'Last Sync: {fabric.last_sync}')
        print(f'Last Git Sync: {fabric.last_git_sync}')
        print(f'Desired State Commit: {fabric.desired_state_commit}')
        print(f'Drift Status: {fabric.drift_status}')
        print(f'GitOps Tool: {fabric.gitops_tool}')
        print(f'GitOps Setup Status: {fabric.gitops_setup_status}')
        print(f'Sync Enabled: {fabric.sync_enabled}')
        print(f'Sync Interval: {fabric.sync_interval}')
        print(f'Sync Error: {fabric.sync_error}')
        print(f'Connection Error: {fabric.connection_error}')
        print()
        
        # Check GitOps configuration
        print('=== GitOps Configuration Analysis ===')
        gitops_summary = fabric.get_gitops_summary()
        print(f'Git Config: {gitops_summary["git_config"]}')
        print(f'Drift Status: {gitops_summary["drift_status"]}')
        print(f'GitOps Tool: {gitops_summary["gitops_tool"]}')
        print(f'Capabilities: {gitops_summary["capabilities"]}')
        print()
        
    except Exception as e:
        print(f'Error accessing fabric: {e}')
        print()

    # Show git repositories
    print('=== Git Repositories ===')
    repos = GitRepository.objects.all()
    if repos:
        for repo in repos:
            print(f'ID: {repo.pk}, Name: {repo.name}')
            print(f'  URL: {repo.url}')
            print(f'  Connection Status: {repo.connection_status}')
            print(f'  Last Validated: {repo.last_validated}')
            print(f'  Fabric Count: {repo.fabric_count}')
            print(f'  Provider: {repo.provider}')
            print(f'  Auth Type: {repo.authentication_type}')
            print(f'  Default Branch: {repo.default_branch}')
            print()
    else:
        print('No GitRepository objects found')
        print()
    
    # Show all fabrics
    print('=== All Fabrics ===')
    all_fabrics = HedgehogFabric.objects.all()
    for fabric in all_fabrics:
        print(f'ID: {fabric.pk}, Name: {fabric.name}')
        print(f'  Status: {fabric.status}')
        print(f'  Connection: {fabric.connection_status}')
        print(f'  Sync: {fabric.sync_status}')
        print(f'  Git Repo (FK): {fabric.git_repository}')
        print(f'  Git URL (legacy): {fabric.git_repository_url}')
        print()

if __name__ == '__main__':
    main()