# Git Sync Error Scenarios

## Overview

This document covers all error scenarios related to Git and GitHub synchronization operations in the NetBox Hedgehog Plugin. These scenarios are based on analysis of the `git_sync_tasks.py` and `github_sync_service.py` implementations.

## Common Git Sync Error Patterns

### Error Categories
1. **Repository Access Errors**: Authentication, permissions, URL issues
2. **Git Operation Errors**: Clone, fetch, push, merge operations
3. **GitHub API Errors**: API limits, service issues, resource conflicts
4. **File System Errors**: Local file operations, permissions, disk space

## Repository Access Error Scenarios

### Scenario: HH-GIT-001 - Repository Not Found

**Description**: Git repository URL is invalid, repository has been deleted, or moved to different location.

**Common Triggers**:
- Typo in repository URL during fabric configuration
- Repository deleted from GitHub
- Repository transferred to different owner/organization
- Private repository made public or vice versa

**Error Detection Patterns**:
```python
# In git_sync_tasks.py
try:
    repo_result = git_service.prepare_repository(fabric=fabric, timeout=10)
    if not repo_result.success:
        if 'not found' in repo_result.message.lower():
            raise GitRepositoryError('HH-GIT-001', 'Repository not found')
except subprocess.CalledProcessError as e:
    if e.returncode == 128 and 'not found' in e.stderr:
        raise GitRepositoryError('HH-GIT-001', 'Repository not found')
```

**Typical Error Messages**:
- "remote: Repository not found."
- "fatal: repository 'https://github.com/owner/repo.git' not found"
- "ERROR: Repository not found."

**Context Information**:
```json
{
    "error_code": "HH-GIT-001",
    "repository_url": "https://github.com/invalid/repo.git",
    "fabric_id": 123,
    "operation": "clone",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

**Automatic Recovery**:
```python
def recover_repository_not_found(fabric, error_context):
    """Attempt repository URL correction"""
    
    # Try common URL variations
    variations = [
        fabric.git_repository_url.replace('.git', ''),
        fabric.git_repository_url + '.git',
        fabric.git_repository_url.replace('http://', 'https://'),
        fabric.git_repository_url.replace('https://', 'http://')
    ]
    
    for url in variations:
        if test_repository_access(url):
            fabric.git_repository_url = url
            fabric.save()
            return {'success': True, 'corrected_url': url}
    
    return {'success': False, 'escalate': 'manual'}
```

**Manual Recovery Steps**:
1. Verify repository exists: `git ls-remote https://github.com/owner/repo.git`
2. Check repository permissions
3. Update fabric configuration with correct URL
4. Retry sync operation

### Scenario: HH-GIT-002 - Repository Authentication Failed

**Description**: Git credentials are invalid, expired, or insufficient for repository access.

**Common Triggers**:
- GitHub token expired or revoked
- SSH key not added to repository
- Username/password authentication disabled
- Two-factor authentication required

**Error Detection Patterns**:
```python
# In github_sync_service.py
def sync_cr_to_github(self, cr_instance, operation='update'):
    try:
        response = requests.get(self.api_base, headers=self.headers)
        if response.status_code == 401:
            raise GitAuthenticationError('HH-GIT-002', 'Authentication failed')
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise GitAuthenticationError('HH-GIT-002', str(e))
```

**Typical Error Messages**:
- "remote: Invalid username or password."
- "fatal: Authentication failed for 'https://github.com/owner/repo.git'"
- "Permission denied (publickey)."

**Context Information**:
```json
{
    "error_code": "HH-GIT-002",
    "repository_url": "https://github.com/owner/repo.git",
    "auth_method": "token",
    "fabric_id": 123,
    "operation": "push"
}
```

**Automatic Recovery**:
```python
def recover_authentication_failed(fabric, error_context):
    """Attempt token refresh if refresh token available"""
    
    if fabric.git_refresh_token:
        try:
            new_token = refresh_github_token(fabric.git_refresh_token)
            if new_token and test_github_token(new_token):
                fabric.git_token = new_token
                fabric.save()
                return {'success': True, 'action': 'token_refreshed'}
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
    
    return {'success': False, 'escalate': 'manual', 'reason': 'token_refresh_unavailable'}
```

### Scenario: HH-GIT-010 - Clone Operation Failed

**Description**: Cannot clone repository to local filesystem due to network, permissions, or disk space issues.

**Common Triggers**:
- Network connectivity issues during clone
- Insufficient disk space for repository
- File system permission issues
- Very large repository size

**Error Detection Patterns**:
```python
# In git operations
try:
    result = subprocess.run(['git', 'clone', repo_url, local_path], 
                           capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        if 'disk' in result.stderr.lower():
            raise GitOperationError('HH-GIT-010', 'Insufficient disk space')
        elif 'permission denied' in result.stderr.lower():
            raise GitOperationError('HH-GIT-010', 'Permission denied')
except subprocess.TimeoutExpired:
    raise GitOperationError('HH-GIT-010', 'Clone operation timed out')
```

**Automatic Recovery**:
```python
def recover_clone_failed(fabric, error_context):
    """Attempt clone recovery strategies"""
    
    strategies = [
        {'action': 'cleanup_partial_clone', 'description': 'Remove partial clone'},
        {'action': 'shallow_clone', 'description': 'Attempt shallow clone'},
        {'action': 'different_location', 'description': 'Try different temp location'}
    ]
    
    for strategy in strategies:
        try:
            if strategy['action'] == 'cleanup_partial_clone':
                shutil.rmtree(fabric.get_local_repo_path(), ignore_errors=True)
            elif strategy['action'] == 'shallow_clone':
                return attempt_shallow_clone(fabric)
            elif strategy['action'] == 'different_location':
                return attempt_clone_alternate_location(fabric)
                
        except Exception as e:
            logger.warning(f"Recovery strategy {strategy['action']} failed: {e}")
            continue
    
    return {'success': False, 'escalate': 'manual'}
```

## GitHub API Error Scenarios

### Scenario: HH-GIT-020 - GitHub API Rate Limited

**Description**: Exceeded GitHub API rate limits for the authenticated user or IP address.

**Common Triggers**:
- High frequency sync operations
- Multiple fabrics using same GitHub token
- Shared IP address with other GitHub API users
- Development/testing with frequent API calls

**Error Detection Patterns**:
```python
# In github_sync_service.py
try:
    response = requests.get(url, headers=self.headers)
    if response.status_code == 429:
        reset_time = response.headers.get('X-RateLimit-Reset')
        raise GitHubApiError('HH-GIT-020', f'Rate limited until {reset_time}')
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 429:
        raise GitHubApiError('HH-GIT-020', 'GitHub API rate limit exceeded')
```

**Context Information**:
```json
{
    "error_code": "HH-GIT-020",
    "rate_limit_remaining": 0,
    "rate_limit_reset": "2024-01-15T11:00:00Z",
    "rate_limit_limit": 5000,
    "operation": "create_file"
}
```

**Automatic Recovery**:
```python
def recover_rate_limit_exceeded(fabric, error_context):
    """Wait for rate limit reset and retry"""
    
    reset_time = error_context.get('rate_limit_reset')
    if reset_time:
        reset_timestamp = datetime.fromisoformat(reset_time.replace('Z', '+00:00'))
        current_time = datetime.now(timezone.utc)
        wait_seconds = (reset_timestamp - current_time).total_seconds()
        
        if wait_seconds > 0 and wait_seconds < 3600:  # Max 1 hour wait
            logger.info(f"Waiting {wait_seconds} seconds for rate limit reset")
            time.sleep(wait_seconds + 60)  # Add 1 minute buffer
            return {'success': True, 'action': 'waited_for_reset', 'wait_time': wait_seconds}
    
    return {'success': False, 'escalate': 'manual', 'reason': 'reset_time_too_long'}
```

### Scenario: HH-GIT-030 - File Not Found in Repository

**Description**: Referenced file doesn't exist in the Git repository, preventing read or update operations.

**Common Triggers**:
- File deleted from repository outside of NetBox
- Incorrect file path configuration
- GitOps directory structure changed
- Branch switching without file migration

**Error Detection Patterns**:
```python
# In github_sync_service.py
def _get_file_from_github(self, file_path):
    try:
        url = f"{self.api_base}/contents/{file_path}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 404:
            raise GitHubFileError('HH-GIT-030', f'File not found: {file_path}')
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise GitHubFileError('HH-GIT-030', f'File not found: {file_path}')
```

**Automatic Recovery**:
```python
def recover_file_not_found(fabric, cr_instance, error_context):
    """Create missing file or find alternative location"""
    
    file_path = error_context.get('file_path')
    
    # Strategy 1: Create file if this is a create operation
    if error_context.get('operation') == 'create':
        return create_missing_file(fabric, cr_instance, file_path)
    
    # Strategy 2: Search for file in alternative locations
    alternative_paths = [
        file_path.replace('/managed/', '/'),  # Root level
        file_path.replace('/managed/', '/generated/'),  # Generated directory
        file_path.replace('.yaml', '.yml')  # Alternative extension
    ]
    
    for alt_path in alternative_paths:
        if check_file_exists_github(fabric, alt_path):
            return {'success': True, 'action': 'found_alternative', 'new_path': alt_path}
    
    return {'success': False, 'escalate': 'manual', 'reason': 'file_not_recoverable'}
```

## Git Operation Error Scenarios

### Scenario: HH-GIT-014 - Merge Conflict Detected

**Description**: Automatic merge failed due to conflicting changes in Git repository.

**Common Triggers**:
- Simultaneous changes to same file from NetBox and external source
- Multiple NetBox instances updating same repository
- Manual changes to GitOps files in repository
- Incomplete previous merge operations

**Error Detection Patterns**:
```python
try:
    result = subprocess.run(['git', 'merge', 'origin/main'], 
                           capture_output=True, text=True)
    if result.returncode != 0 and 'conflict' in result.stderr.lower():
        conflicts = parse_git_conflicts(result.stderr)
        raise GitMergeError('HH-GIT-014', 'Merge conflicts detected', 
                           context={'conflicts': conflicts})
except subprocess.CalledProcessError as e:
    if 'conflict' in e.stderr:
        raise GitMergeError('HH-GIT-014', 'Merge conflicts detected')
```

**Conflict Resolution Strategies**:
```python
def recover_merge_conflict(fabric, error_context):
    """Automatic merge conflict resolution"""
    
    conflicts = error_context.get('conflicts', [])
    resolution_strategy = determine_resolution_strategy(fabric, conflicts)
    
    if resolution_strategy == 'accept_ours':
        # NetBox changes take precedence
        return resolve_conflicts_accept_ours(conflicts)
    elif resolution_strategy == 'accept_theirs':  
        # Repository changes take precedence
        return resolve_conflicts_accept_theirs(conflicts)
    elif resolution_strategy == 'smart_merge':
        # Attempt intelligent merge
        return attempt_smart_merge(conflicts)
    else:
        # Escalate to manual resolution
        return {'success': False, 'escalate': 'manual', 'conflicts': conflicts}

def determine_resolution_strategy(fabric, conflicts):
    """Determine appropriate conflict resolution strategy"""
    
    # If fabric configured as authoritative source
    if fabric.gitops_authority == 'netbox':
        return 'accept_ours'
    
    # If repository configured as authoritative source
    if fabric.gitops_authority == 'git':
        return 'accept_theirs'
    
    # Check conflict types for smart resolution
    conflict_types = analyze_conflict_types(conflicts)
    if all(ct in ['metadata_only', 'timestamp_only'] for ct in conflict_types):
        return 'smart_merge'
    
    return 'manual'
```

### Scenario: HH-GIT-015 - Branch Not Found

**Description**: Specified Git branch does not exist in the repository.

**Common Triggers**:
- Branch name typo in fabric configuration
- Branch deleted from repository
- Default branch changed in repository
- Branch name case sensitivity issues

**Error Detection and Recovery**:
```python
def recover_branch_not_found(fabric, error_context):
    """Handle missing branch scenarios"""
    
    configured_branch = fabric.git_branch or 'main'
    
    # Get list of available branches
    try:
        result = subprocess.run(['git', 'ls-remote', '--heads', fabric.git_repository_url],
                               capture_output=True, text=True)
        available_branches = parse_remote_branches(result.stdout)
        
        # Try common branch name alternatives
        alternatives = ['main', 'master', 'develop', 'dev']
        for alt_branch in alternatives:
            if alt_branch in available_branches and alt_branch != configured_branch:
                fabric.git_branch = alt_branch
                fabric.save()
                return {'success': True, 'action': 'switched_branch', 'new_branch': alt_branch}
        
        # If no alternatives, suggest creating branch
        if available_branches:
            return {'success': False, 'escalate': 'manual', 
                   'suggestion': 'create_branch', 'available_branches': available_branches}
        
    except Exception as e:
        logger.error(f"Could not list remote branches: {e}")
    
    return {'success': False, 'escalate': 'manual'}
```

## Integration Error Scenarios

### Scenario: Multi-Component Sync Failure

**Description**: Sync operation fails across multiple components (Git + Kubernetes + Database).

**Error Chain Example**:
1. `HH-GIT-002`: Authentication fails for GitHub API
2. `HH-STATE-003`: Cannot transition fabric sync status  
3. `HH-K8S-020`: Cannot update Kubernetes resources
4. `HH-VAL-010`: State validation fails due to inconsistency

**Recovery Strategy**:
```python
def recover_multi_component_failure(fabric, error_chain):
    """Handle cascading failure scenarios"""
    
    recovery_plan = {
        'rollback_actions': [],
        'retry_actions': [],
        'manual_actions': []
    }
    
    # Analyze error chain for recovery strategy
    for error in error_chain:
        if error['code'].startswith('HH-GIT'):
            recovery_plan['retry_actions'].append('retry_git_sync')
        elif error['code'].startswith('HH-STATE'):
            recovery_plan['rollback_actions'].append('rollback_state_changes')
        elif error['code'].startswith('HH-K8S'):
            recovery_plan['manual_actions'].append('validate_k8s_connectivity')
    
    # Execute recovery plan
    return execute_recovery_plan(fabric, recovery_plan)
```

## Testing Error Scenarios

### Git Sync Error Test Cases
```python
class GitSyncErrorTests:
    
    def test_repository_not_found(self):
        """Test HH-GIT-001 scenario"""
        fabric = self.create_test_fabric(
            git_repository_url='https://github.com/invalid/repo.git'
        )
        
        with self.assertRaises(GitRepositoryError) as context:
            git_sync_fabric(fabric.id)
        
        self.assertEqual(context.exception.code, 'HH-GIT-001')
        self.assertIn('not found', context.exception.message.lower())
    
    def test_authentication_failed(self):
        """Test HH-GIT-002 scenario"""
        fabric = self.create_test_fabric(git_token='invalid_token')
        
        with self.assertRaises(GitAuthenticationError) as context:
            sync_service = GitHubSyncService(fabric)
            sync_service.sync_cr_to_github(test_cr_instance)
        
        self.assertEqual(context.exception.code, 'HH-GIT-002')
    
    def test_rate_limit_recovery(self):
        """Test HH-GIT-020 automatic recovery"""
        fabric = self.create_test_fabric()
        
        with mock.patch('requests.get') as mock_get:
            # Simulate rate limit response
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.headers = {'X-RateLimit-Reset': '1642248000'}
            mock_get.return_value = mock_response
            
            # Should trigger automatic recovery
            result = recover_rate_limit_exceeded(fabric, {
                'rate_limit_reset': '2024-01-15T11:00:00Z'
            })
            
            self.assertTrue(result['success'])
            self.assertEqual(result['action'], 'waited_for_reset')
```

## Monitoring and Alerting

### Error Metrics
- Git sync failure rate by error code
- Average recovery time by error type  
- Manual intervention frequency
- Repository availability metrics

### Alert Conditions
- Multiple consecutive sync failures
- Authentication failures (immediate)
- Repository unavailability > 15 minutes
- Merge conflicts requiring manual resolution

This comprehensive coverage of Git sync error scenarios provides agents with the knowledge needed to handle all major failure modes in Git and GitHub integration operations.