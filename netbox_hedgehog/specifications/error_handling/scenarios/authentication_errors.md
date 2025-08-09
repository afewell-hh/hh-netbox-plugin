# Authentication Error Scenarios

## Overview

This document covers all authentication and authorization error scenarios in the NetBox Hedgehog Plugin. These scenarios are critical for maintaining secure access to Git repositories, Kubernetes clusters, and API endpoints.

## Authentication Error Categories

### Error Types
1. **Token Management Errors**: Creation, validation, refresh, storage
2. **Credential Errors**: Username/password, SSH keys, certificates  
3. **Authorization Errors**: Insufficient permissions, role restrictions
4. **Session Management Errors**: Login, logout, session expiry

## Token Management Error Scenarios

### Scenario: HH-AUTH-001 - Invalid GitHub Token

**Description**: GitHub authentication token is malformed, corrupted, or invalid format.

**Common Triggers**:
- Manual token entry with typos or extra characters
- Copy/paste issues including whitespace or line breaks
- Token corruption during storage or retrieval
- Wrong token type (personal vs organization token)

**Error Detection Patterns**:
```python
import requests
import re

def validate_github_token_format(token):
    """Validate GitHub token format and structure"""
    
    # GitHub token patterns
    patterns = {
        'personal_access_token': r'^ghp_[A-Za-z0-9]{36}$',
        'oauth_token': r'^gho_[A-Za-z0-9]{36}$', 
        'installation_token': r'^ghs_[A-Za-z0-9]{36}$',
        'refresh_token': r'^ghr_[A-Za-z0-9]{36}$'
    }
    
    for token_type, pattern in patterns.items():
        if re.match(pattern, token):
            return {'valid': True, 'type': token_type}
    
    # Check for common formatting issues
    if not token:
        raise AuthenticationError('HH-AUTH-001', 'Token is empty')
    elif len(token) != 40:
        raise AuthenticationError('HH-AUTH-001', 'Invalid token length')
    elif not token.startswith(('ghp_', 'gho_', 'ghs_', 'ghr_')):
        raise AuthenticationError('HH-AUTH-001', 'Invalid token prefix')
    else:
        raise AuthenticationError('HH-AUTH-001', 'Invalid token format')

def test_github_token(token, repository_url=None):
    """Test GitHub token validity"""
    
    try:
        headers = {'Authorization': f'token {token}'}
        
        # Test basic API access
        response = requests.get('https://api.github.com/user', headers=headers)
        
        if response.status_code == 401:
            error_details = response.json().get('message', 'Authentication failed')
            raise AuthenticationError('HH-AUTH-001', f'Invalid GitHub token: {error_details}')
        elif response.status_code == 403:
            # Token might be valid but has issues
            if 'rate limit' in response.text.lower():
                # Rate limited - token is valid
                return {'valid': True, 'rate_limited': True}
            else:
                raise AuthenticationError('HH-AUTH-001', 'GitHub token lacks required permissions')
        
        return {'valid': True, 'user': response.json()}
        
    except requests.exceptions.RequestException as e:
        raise AuthenticationError('HH-AUTH-001', f'Token validation failed: {str(e)}')
```

**Context Information**:
```json
{
    "error_code": "HH-AUTH-001",
    "token_format": "invalid",
    "token_length": 35,
    "token_prefix": "ghp_", 
    "repository_url": "https://github.com/owner/repo.git",
    "fabric_id": 123,
    "timestamp": "2024-01-15T10:30:00Z"
}
```

**Automatic Recovery**:
```python
def recover_invalid_github_token(fabric, error_context):
    """Attempt automatic token format correction"""
    
    original_token = fabric.git_token
    recovery_attempts = []
    
    # Common token format fixes
    fixes = [
        {
            'name': 'trim_whitespace',
            'action': lambda t: t.strip(),
            'description': 'Remove leading/trailing whitespace'
        },
        {
            'name': 'remove_newlines',
            'action': lambda t: t.replace('\n', '').replace('\r', ''),
            'description': 'Remove line breaks'
        },
        {
            'name': 'extract_from_quotes', 
            'action': lambda t: t.strip('"\''),
            'description': 'Remove surrounding quotes'
        }
    ]
    
    for fix in fixes:
        try:
            fixed_token = fix['action'](original_token)
            
            if fixed_token != original_token:
                # Test the fixed token
                validation_result = test_github_token(fixed_token)
                
                if validation_result.get('valid'):
                    # Update fabric with corrected token
                    fabric.git_token = fixed_token
                    fabric.save()
                    
                    return {
                        'success': True,
                        'recovery_type': 'automatic',
                        'fix_applied': fix['name'],
                        'description': fix['description'],
                        'message': 'GitHub token format automatically corrected'
                    }
                    
        except Exception as e:
            recovery_attempts.append({
                'fix': fix['name'],
                'result': 'failed',
                'error': str(e)
            })
            continue
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'token_format_not_recoverable',
        'attempts': recovery_attempts
    }
```

### Scenario: HH-AUTH-002 - Expired GitHub Token

**Description**: GitHub token has exceeded its validity period and needs renewal.

**Common Triggers**:
- Personal access tokens have configurable expiration dates
- Organization policies enforcing token expiration
- Token revoked manually by user
- Account security incidents triggering token invalidation

**Error Detection Patterns**:
```python
def detect_expired_github_token(response, token):
    """Detect GitHub token expiration from API responses"""
    
    if response.status_code == 401:
        error_body = response.json()
        error_message = error_body.get('message', '').lower()
        
        expiration_indicators = [
            'token expired',
            'bad credentials', 
            'requires authentication',
            'token has expired'
        ]
        
        if any(indicator in error_message for indicator in expiration_indicators):
            # Check token creation date if available
            token_info = get_token_info(token)
            
            return {
                'expired': True,
                'error_code': 'HH-AUTH-002',
                'token_info': token_info,
                'expiration_detected': True
            }
    
    return {'expired': False}

def get_token_info(token):
    """Extract token information for expiration analysis"""
    
    try:
        # Use GitHub API to get token info
        headers = {'Authorization': f'token {token}'}
        response = requests.get('https://api.github.com/applications/grants', 
                              headers=headers)
        
        if response.status_code == 200:
            grants = response.json()
            # Extract token creation and expiration info
            return analyze_token_grants(grants)
    except:
        pass
    
    return {'info_available': False}
```

**Automatic Recovery**:
```python
def recover_expired_github_token(fabric, error_context):
    """Automatic token renewal using refresh token or GitHub Apps"""
    
    # Strategy 1: OAuth refresh token
    if hasattr(fabric, 'git_refresh_token') and fabric.git_refresh_token:
        try:
            new_token = refresh_github_oauth_token(fabric.git_refresh_token)
            
            if new_token and test_github_token(new_token).get('valid'):
                fabric.git_token = new_token['access_token']
                if 'refresh_token' in new_token:
                    fabric.git_refresh_token = new_token['refresh_token']
                fabric.save()
                
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'method': 'oauth_refresh',
                    'message': 'GitHub token automatically renewed'
                }
                
        except Exception as e:
            logger.error(f"OAuth token refresh failed: {e}")
    
    # Strategy 2: GitHub App installation token
    if hasattr(fabric, 'github_app_id') and fabric.github_app_id:
        try:
            app_token = generate_github_app_token(
                fabric.github_app_id,
                fabric.github_app_private_key,
                fabric.github_installation_id
            )
            
            if app_token and test_github_token(app_token).get('valid'):
                fabric.git_token = app_token
                fabric.save()
                
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'method': 'github_app_token',
                    'message': 'GitHub App token automatically generated'
                }
                
        except Exception as e:
            logger.error(f"GitHub App token generation failed: {e}")
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'automatic_renewal_not_available',
        'required_actions': [
            'Generate new personal access token',
            'Update fabric configuration with new token',
            'Consider using GitHub Apps for automatic renewal'
        ]
    }

def refresh_github_oauth_token(refresh_token):
    """Refresh GitHub OAuth token"""
    
    data = {
        'client_id': settings.GITHUB_CLIENT_ID,
        'client_secret': settings.GITHUB_CLIENT_SECRET, 
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    }
    
    response = requests.post('https://github.com/login/oauth/access_token', 
                           data=data,
                           headers={'Accept': 'application/json'})
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Token refresh failed: {response.text}")
```

### Scenario: HH-AUTH-010 - Insufficient GitHub Permissions

**Description**: GitHub token lacks required repository or organizational permissions.

**Common Triggers**:
- Token created with insufficient scopes
- Repository permissions changed after token creation
- Organization policies restricting token access
- Private repository requires additional permissions

**Error Detection and Recovery**:
```python
def detect_insufficient_github_permissions(response, operation):
    """Detect permission issues from GitHub API responses"""
    
    if response.status_code == 403:
        error_body = response.json()
        error_message = error_body.get('message', '')
        
        permission_indicators = [
            'permission denied',
            'insufficient permissions',
            'requires push access',
            'must have admin rights'
        ]
        
        if any(indicator in error_message.lower() for indicator in permission_indicators):
            return {
                'insufficient_permissions': True,
                'error_code': 'HH-AUTH-010',
                'operation': operation,
                'required_permissions': extract_required_permissions(error_message)
            }
    
    return {'insufficient_permissions': False}

def recover_insufficient_github_permissions(fabric, error_context):
    """Guide user through permission resolution"""
    
    operation = error_context.get('operation', 'unknown')
    required_permissions = error_context.get('required_permissions', [])
    
    # Check current token permissions
    current_permissions = get_github_token_permissions(fabric.git_token)
    
    permission_analysis = {
        'current': current_permissions,
        'required': required_permissions,
        'missing': list(set(required_permissions) - set(current_permissions))
    }
    
    if permission_analysis['missing']:
        return {
            'success': False,
            'escalate': 'manual',
            'reason': 'insufficient_permissions',
            'permission_analysis': permission_analysis,
            'recovery_instructions': generate_permission_fix_instructions(
                fabric, permission_analysis
            )
        }
    else:
        # Permissions seem adequate, might be a different issue
        return {
            'success': False,
            'escalate': 'manual', 
            'reason': 'permission_issue_unclear',
            'permission_analysis': permission_analysis
        }

def generate_permission_fix_instructions(fabric, permission_analysis):
    """Generate step-by-step permission fix instructions"""
    
    instructions = []
    missing_permissions = permission_analysis['missing']
    repository_url = fabric.git_repository_url
    
    # Parse repository owner/name
    owner, repo = parse_github_repository_url(repository_url)
    
    for permission in missing_permissions:
        if permission == 'push':
            instructions.append({
                'step': 'grant_push_access',
                'description': 'Grant push access to repository',
                'actions': [
                    f'Navigate to https://github.com/{owner}/{repo}/settings/access',
                    'Add user as collaborator with push permissions',
                    'Or update existing collaborator permissions'
                ]
            })
        elif permission == 'admin':
            instructions.append({
                'step': 'grant_admin_access',
                'description': 'Grant admin access to repository',
                'actions': [
                    f'Navigate to https://github.com/{owner}/{repo}/settings/access',
                    'Grant admin permissions to user or service account'
                ]
            })
        elif permission == 'write':
            instructions.append({
                'step': 'update_token_scopes',
                'description': 'Update GitHub token scopes',
                'actions': [
                    'Navigate to GitHub Settings > Developer settings > Personal access tokens',
                    'Edit existing token or create new one',
                    'Ensure "repo" scope is selected for full repository access'
                ]
            })
    
    return instructions
```

## Kubernetes Authentication Error Scenarios

### Scenario: HH-AUTH-004 - Invalid Kubernetes Token

**Description**: Kubernetes service account token is invalid, corrupted, or malformed.

**Error Detection**:
```python
def validate_kubernetes_token(token, cluster_endpoint):
    """Validate Kubernetes token format and test authentication"""
    
    import base64
    import json
    
    try:
        # Basic format validation
        if not token:
            raise AuthenticationError('HH-AUTH-004', 'Kubernetes token is empty')
        
        # JWT token format check
        if token.count('.') == 2:
            # Appears to be JWT - validate structure
            header, payload, signature = token.split('.')
            
            try:
                # Decode payload (base64url)
                decoded_payload = base64.urlsafe_b64decode(payload + '==')
                token_data = json.loads(decoded_payload)
                
                # Check expiration
                import time
                current_time = time.time()
                if 'exp' in token_data and token_data['exp'] < current_time:
                    raise AuthenticationError('HH-AUTH-005', 'Kubernetes token expired')
                    
            except Exception as e:
                raise AuthenticationError('HH-AUTH-004', f'Invalid JWT token: {str(e)}')
        
        # Test token with cluster
        config = kubernetes.client.Configuration()
        config.host = cluster_endpoint
        config.api_key['authorization'] = f'Bearer {token}'
        
        api_client = kubernetes.client.ApiClient(config)
        v1 = kubernetes.client.CoreV1Api(api_client)
        
        # Simple test operation
        result = v1.list_namespace(_request_timeout=10)
        return {'valid': True, 'namespaces_accessible': len(result.items)}
        
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 401:
            raise AuthenticationError('HH-AUTH-004', 'Kubernetes token authentication failed')
        else:
            raise AuthenticationError('HH-AUTH-004', f'Token validation error: {str(e)}')
```

**Automatic Recovery**:
```python
def recover_invalid_kubernetes_token(fabric, error_context):
    """Attempt Kubernetes token recovery"""
    
    # Strategy 1: Token refresh using service account
    if fabric.kubernetes_service_account:
        try:
            new_token = refresh_kubernetes_service_account_token(
                fabric.kubernetes_service_account,
                fabric.kubernetes_namespace
            )
            
            if new_token:
                fabric.kubernetes_token = new_token
                fabric.save()
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'method': 'service_account_refresh'
                }
                
        except Exception as e:
            logger.error(f"Service account token refresh failed: {e}")
    
    # Strategy 2: Create new service account
    if fabric.kubernetes_admin_token:
        try:
            result = create_new_service_account(fabric)
            if result.get('success'):
                fabric.kubernetes_token = result['token']
                fabric.kubernetes_service_account = result['service_account_name']
                fabric.save()
                return {
                    'success': True,
                    'recovery_type': 'automatic', 
                    'method': 'new_service_account_created'
                }
                
        except Exception as e:
            logger.error(f"Service account creation failed: {e}")
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'token_recovery_not_available'
    }
```

## Session Management Error Scenarios

### Scenario: HH-AUTH-020 - Token Generation Failed

**Description**: Cannot generate new authentication tokens due to system or configuration issues.

**Common Triggers**:
- Service account creation failures
- OAuth application configuration issues
- Network connectivity to authentication services
- Insufficient permissions to create tokens

**Error Handling**:
```python
def handle_token_generation_failure(service_type, error_context):
    """Handle token generation failures"""
    
    if service_type == 'github':
        return handle_github_token_generation_failure(error_context)
    elif service_type == 'kubernetes':
        return handle_kubernetes_token_generation_failure(error_context)
    else:
        return {
            'success': False,
            'error_code': 'HH-AUTH-020',
            'reason': f'unknown_service_type: {service_type}'
        }

def handle_github_token_generation_failure(error_context):
    """Handle GitHub token generation issues"""
    
    failure_reasons = {
        'oauth_app_not_configured': {
            'recovery': 'configure_oauth_app',
            'instructions': [
                'Create GitHub OAuth App in organization settings',
                'Configure client ID and secret in NetBox settings',
                'Update OAuth callback URLs'
            ]
        },
        'github_app_not_installed': {
            'recovery': 'install_github_app',
            'instructions': [
                'Install GitHub App in target organization',
                'Grant required repository permissions',
                'Update installation ID in fabric configuration'
            ]
        },
        'network_connectivity_issue': {
            'recovery': 'check_connectivity',
            'instructions': [
                'Verify network access to GitHub API',
                'Check proxy configuration if applicable',
                'Verify DNS resolution for github.com'
            ]
        }
    }
    
    detected_reason = detect_github_token_failure_reason(error_context)
    
    if detected_reason in failure_reasons:
        return {
            'success': False,
            'escalate': 'manual',
            'reason': detected_reason,
            'recovery_instructions': failure_reasons[detected_reason]
        }
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'token_generation_failed_unknown'
    }
```

## Multi-Service Authentication Error Scenarios

### Scenario: Authentication Cascade Failure

**Description**: Authentication failure in one service cascades to other dependent services.

**Error Chain Example**:
1. `HH-AUTH-002`: GitHub token expires
2. `HH-GIT-002`: Git sync fails due to authentication
3. `HH-STATE-012`: Cannot update fabric sync status
4. `HH-K8S-020`: Resource updates fail due to missing Git data

**Recovery Strategy**:
```python
def recover_authentication_cascade_failure(fabric, error_chain):
    """Handle cascading authentication failures"""
    
    # Identify root authentication cause
    auth_errors = [e for e in error_chain if e['code'].startswith('HH-AUTH')]
    
    if not auth_errors:
        return {'success': False, 'reason': 'no_auth_errors_in_chain'}
    
    root_auth_error = auth_errors[0]  # First authentication error
    
    # Attempt recovery of root cause
    recovery_result = attempt_auth_error_recovery(fabric, root_auth_error)
    
    if recovery_result.get('success'):
        # Root cause resolved, attempt to recover dependent failures
        dependent_recovery = recover_dependent_failures(fabric, error_chain)
        
        return {
            'success': True,
            'recovery_type': 'automatic',
            'root_cause_resolved': root_auth_error['code'],
            'dependent_recovery': dependent_recovery
        }
    else:
        return {
            'success': False,
            'escalate': 'manual',
            'root_cause': root_auth_error,
            'recovery_blocked_by': recovery_result.get('reason')
        }
```

## Testing Authentication Error Scenarios

```python
class AuthenticationErrorTests:
    
    def test_invalid_github_token_format(self):
        """Test HH-AUTH-001 detection and recovery"""
        fabric = self.create_test_fabric(git_token='invalid_token_format')
        
        with self.assertRaises(AuthenticationError) as context:
            test_github_token(fabric.git_token)
        
        self.assertEqual(context.exception.code, 'HH-AUTH-001')
        
        # Test automatic recovery
        recovery_result = recover_invalid_github_token(fabric, {
            'token_format': 'invalid'
        })
        
        # Should attempt format fixes
        self.assertIn('fix_applied', recovery_result)
    
    def test_expired_token_recovery(self):
        """Test HH-AUTH-002 automatic renewal"""
        fabric = self.create_test_fabric()
        fabric.git_refresh_token = 'ghr_valid_refresh_token'
        
        with mock.patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                'access_token': 'new_access_token',
                'refresh_token': 'new_refresh_token'
            }
            
            result = recover_expired_github_token(fabric, {})
            
            self.assertTrue(result['success'])
            self.assertEqual(result['method'], 'oauth_refresh')
    
    def test_insufficient_permissions_guidance(self):
        """Test HH-AUTH-010 user guidance"""
        fabric = self.create_test_fabric(
            git_repository_url='https://github.com/owner/repo.git'
        )
        
        result = recover_insufficient_github_permissions(fabric, {
            'operation': 'push',
            'required_permissions': ['push', 'write']
        })
        
        self.assertFalse(result['success'])
        self.assertEqual(result['escalate'], 'manual')
        self.assertIn('recovery_instructions', result)
```

This comprehensive authentication error scenario documentation provides agents with detailed knowledge for handling all authentication and authorization failures in the NetBox Hedgehog Plugin.