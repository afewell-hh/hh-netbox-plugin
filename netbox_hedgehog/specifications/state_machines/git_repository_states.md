# GitRepository State Management Documentation

## Overview

GitRepository manages **authentication and connection state** independently from fabric configuration, implementing separation of concerns for git repository access. This enables multiple fabrics to share repositories while maintaining distinct connection health tracking.

## State Dimension

### Connection Status (`connection_status` field)

**Purpose**: Represents the authentication and connection state to the git repository.

**Valid States**:
- `PENDING` - Repository added but not yet validated
- `TESTING` - Connection test in progress
- `CONNECTED` - Successfully authenticated and connected
- `FAILED` - Authentication or connection failed

## State Transition Matrix

| From State | To State | Trigger | Required Conditions | Side Effects |
|-----------|----------|---------|-------------------|--------------|
| `PENDING` | `TESTING` | `test_connection()` called | Valid URL format | Set `connection_status` |
| `TESTING` | `CONNECTED` | Connection test succeeds | Valid credentials, network access | Update `last_validated`, clear errors |
| `TESTING` | `FAILED` | Connection test fails | Invalid credentials or network error | Set `validation_error` |
| `CONNECTED` | `TESTING` | Manual retest initiated | User action or scheduled check | Clear previous validation |
| `CONNECTED` | `FAILED` | Authentication expires | Token expiry, credential revocation | Set `validation_error` |
| `FAILED` | `TESTING` | Retry connection | Fixed credentials or network | Clear previous error |

## Invalid Transitions

| From State | To State | Reason | Agent Action |
|-----------|----------|--------|--------------|
| `PENDING` | `CONNECTED` | Must test first | Reject, require `test_connection()` |
| `PENDING` | `FAILED` | Cannot fail without testing | Reject, invalid state change |
| `TESTING` | `PENDING` | Cannot go backward | Reject, complete test cycle |

## State Triggers

### Automatic Triggers (System Actions)

1. **Repository Creation**:
   - New repository → `PENDING` status
   - Auto-trigger connection test if credentials provided

2. **Credential Updates**:
   - `set_credentials()` called → Status to `TESTING`
   - Test connection automatically with new credentials

3. **Connection Health Monitoring**:
   - Periodic validation (24h) → `CONNECTED` to `TESTING`
   - Failed git operations → `CONNECTED` to `FAILED`

4. **Token Expiration**:
   - OAuth/PAT expiry → `CONNECTED` to `FAILED`
   - Set appropriate error message

### Manual Triggers (User Actions)

1. **Connection Testing**:
   - Manual `test_connection()` → Current state to `TESTING`
   - Credential validation → Update state based on result

2. **Credential Rotation**:
   - `rotate_credentials()` → Force retest connection
   - Backup old credentials before rotation

3. **Repository Management**:
   - URL changes → Reset to `PENDING`, retest required
   - Authentication type changes → Revalidate credentials

## Authentication Types and State Behavior

### Token Authentication (`TOKEN`)

**Credentials Structure**:
```json
{
    "token": "ghp_xxxxxxxxxxxx"
}
```

**State Considerations**:
- Tokens can expire → `CONNECTED` to `FAILED`
- GitHub/GitLab tokens have different scopes
- Token rotation required for security

**Recovery Actions**:
- Generate new token
- Update credentials
- Retest connection

### SSH Key Authentication (`SSH_KEY`)

**Credentials Structure**:
```json
{
    "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----...",
    "passphrase": "optional_passphrase"
}
```

**State Considerations**:
- SSH keys rarely expire
- Passphrase required for encrypted keys
- Key rotation for security compliance

**Recovery Actions**:
- Generate new SSH key pair
- Add public key to git provider
- Update private key credentials

### Basic Authentication (`BASIC`)

**Credentials Structure**:
```json
{
    "username": "user@example.com",
    "password": "password_or_app_token"
}
```

**State Considerations**:
- Often uses app-specific passwords
- Less secure than token/SSH methods
- Password changes → `CONNECTED` to `FAILED`

**Recovery Actions**:
- Update password/app-token
- Consider migration to token auth
- Retest connection

### OAuth Authentication (`OAUTH`)

**Credentials Structure**:
```json
{
    "client_id": "oauth_app_id",
    "client_secret": "oauth_secret",  
    "access_token": "oauth_token",
    "refresh_token": "refresh_token"
}
```

**State Considerations**:
- Tokens expire and need refresh
- Complex credential refresh cycle
- Provider-specific implementations

**Recovery Actions**:
- Attempt token refresh
- Re-authenticate if refresh fails
- Update stored credentials

## Error Conditions and Recovery

### Connection Failures

**Error Types**:
1. **Authentication Failures**
   - Invalid credentials → `FAILED` with specific error
   - Expired tokens → `FAILED` with expiry notice
   - Insufficient permissions → `FAILED` with scope error

2. **Network Failures**
   - DNS resolution → Temporary failure, retry
   - Network timeout → Temporary failure, retry
   - SSL certificate errors → Configuration issue

3. **Repository Access**
   - Repository not found → Check URL/permissions
   - Repository deleted → Update repository status
   - Access denied → Check credential permissions

**Recovery Strategies**:

1. **Automatic Recovery**:
   - Network failures → Retry with exponential backoff
   - Temporary authentication issues → Retry 3 times
   - Rate limiting → Wait and retry

2. **Manual Recovery**:
   - Credential expiry → User updates credentials
   - Permission changes → User fixes repository access
   - Repository URL changes → User updates configuration

### State Inconsistency Detection

**Validation Rules**:
```python
def validate_repository_state(repository):
    """Validate repository state consistency"""
    # Connected state must have recent validation
    if repository.connection_status == 'CONNECTED':
        if not repository.last_validated:
            return False, "Connected state requires validation timestamp"
        
        if repository.last_validated < (timezone.now() - timedelta(hours=25)):
            return False, "Connected state requires recent validation"
    
    # Failed state must have error message
    if repository.connection_status == 'FAILED':
        if not repository.validation_error:
            return False, "Failed state requires error message"
    
    # Testing state should be transient
    if repository.connection_status == 'TESTING':
        # Check if stuck in testing state
        pass
    
    return True, "State is consistent"
```

## State Persistence and Tracking

### Fields Updated During Transitions

1. **Connection State Changes**:
   - `connection_status` - New state value
   - `last_validated` - Timestamp for successful connections
   - `validation_error` - Error message for failures

2. **Credential Updates**:
   - `encrypted_credentials` - New encrypted credential data
   - Trigger state reset to `TESTING`

3. **Repository Metadata** (updated during validation):
   - `default_branch` - Detected default branch
   - `is_private` - Repository visibility
   - Provider-specific metadata

### State History and Monitoring

**Transition Logging**:
```python
def log_repository_state_transition(repository, old_state, new_state, trigger, error=None):
    """Log repository state transitions for monitoring"""
    log_entry = {
        'repository_id': repository.id,
        'repository_name': repository.name,
        'old_state': old_state,
        'new_state': new_state,
        'trigger': trigger,
        'timestamp': timezone.now(),
        'error': error,
        'authentication_type': repository.authentication_type
    }
    
    # Store in monitoring system
    RepositoryStateLog.objects.create(**log_entry)
```

**Health Monitoring**:
- Connection success rate tracking
- Authentication failure patterns
- State transition frequency analysis

## Agent Implementation Guidelines

### Connection Testing

```python
async def test_repository_connection(repository):
    """Test repository connection with proper state management"""
    # Update to testing state
    old_state = repository.connection_status
    repository.connection_status = 'TESTING'
    repository.save(update_fields=['connection_status'])
    
    try:
        # Perform actual connection test
        result = await perform_git_connection_test(repository)
        
        if result.success:
            # Update to connected state
            repository.connection_status = 'CONNECTED'
            repository.last_validated = timezone.now()
            repository.validation_error = ''
            repository.save(update_fields=[
                'connection_status', 'last_validated', 'validation_error'
            ])
            
            # Update repository metadata if available
            if result.metadata:
                update_repository_metadata(repository, result.metadata)
                
        else:
            # Update to failed state
            repository.connection_status = 'FAILED'
            repository.validation_error = result.error
            repository.save(update_fields=['connection_status', 'validation_error'])
            
    except Exception as e:
        # Handle unexpected errors
        repository.connection_status = 'FAILED'
        repository.validation_error = f"Connection test error: {str(e)}"
        repository.save(update_fields=['connection_status', 'validation_error'])
    
    # Log state transition
    log_repository_state_transition(
        repository, old_state, repository.connection_status, 
        'connection_test', repository.validation_error if repository.connection_status == 'FAILED' else None
    )
    
    return repository.connection_status == 'CONNECTED'
```

### Credential Rotation

```python
def rotate_repository_credentials(repository, new_credentials, rotation_reason):
    """Rotate repository credentials with state management"""
    # Backup current credentials
    backup = repository.backup_credentials()
    
    try:
        # Set new credentials
        repository.set_credentials(new_credentials)
        
        # Test new credentials
        test_result = repository.test_connection()
        
        if test_result['success']:
            # Log successful rotation
            log_credential_rotation(repository, rotation_reason, True)
            return {'success': True, 'message': 'Credentials rotated successfully'}
        else:
            # Restore backup if test fails
            repository.restore_credentials(backup)
            log_credential_rotation(repository, rotation_reason, False, test_result['error'])
            return {'success': False, 'error': 'New credentials failed validation'}
            
    except Exception as e:
        # Restore backup on any error
        repository.restore_credentials(backup)
        return {'success': False, 'error': f'Credential rotation failed: {str(e)}'}
```

### State-Aware Operations

```python
def can_perform_git_operation(repository, operation_type):
    """Check if git operation can be performed based on state"""
    if repository.connection_status != 'CONNECTED':
        return False, f"Repository not connected (status: {repository.connection_status})"
    
    # Check if validation is recent enough
    if repository.last_validated:
        staleness = timezone.now() - repository.last_validated
        if staleness > timedelta(hours=24):
            return False, "Connection validation is stale, retest required"
    
    # Check operation-specific requirements
    if operation_type in ['push', 'clone']:
        credentials = repository.get_credentials()
        if not credentials:
            return False, "No credentials available for git operation"
    
    return True, "Repository ready for operation"
```

## Integration Points

### With HedgehogFabric States
- Fabric sync depends on repository connection health
- Repository failures propagate to fabric sync status
- Shared repositories affect multiple fabric states

### With Credential Management
- Credential rotation triggers state transitions
- Authentication failures update connection status
- Security policies enforce credential validation

### With Monitoring Systems
- State transitions generate monitoring events
- Connection health affects fabric alerting
- Performance metrics track state stability

This documentation enables agents to properly handle git repository authentication and connection state management with full error recovery capabilities.