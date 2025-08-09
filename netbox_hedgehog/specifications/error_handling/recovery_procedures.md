# Recovery Procedures for NetBox Hedgehog Plugin

## Overview

This document defines standardized recovery procedures for all error categories in the NetBox Hedgehog Plugin. Each procedure provides step-by-step instructions for both automated recovery systems and manual intervention scenarios.

## Recovery Strategy Framework

### Recovery Hierarchy
1. **Automatic Recovery**: System attempts recovery without user intervention
2. **Assisted Recovery**: System provides guidance for user-initiated recovery
3. **Manual Recovery**: Full manual intervention required
4. **Escalation**: Expert intervention or external dependency resolution needed

### Recovery Principles
- **Safety First**: Never compromise data integrity during recovery
- **Minimal Impact**: Minimize service disruption during recovery
- **Audit Trail**: Log all recovery actions for troubleshooting
- **Validation**: Verify successful recovery before resuming operations
- **Progressive Escalation**: Escalate through recovery levels systematically

## Authentication & Authorization Recovery (HH-AUTH-xxx)

### Token Management Recovery

#### Automatic Recovery Procedures

**HH-AUTH-002: Expired GitHub Token**
```python
def recover_expired_github_token(fabric, error_context):
    """Automatic GitHub token refresh"""
    
    recovery_steps = [
        {
            'step': 1,
            'action': 'check_refresh_token_available',
            'description': 'Check if refresh token is available'
        },
        {
            'step': 2, 
            'action': 'attempt_token_refresh',
            'description': 'Use refresh token to get new access token'
        },
        {
            'step': 3,
            'action': 'validate_new_token',
            'description': 'Test new token with GitHub API'
        },
        {
            'step': 4,
            'action': 'update_stored_credentials',
            'description': 'Update fabric with new token'
        }
    ]
    
    try:
        # Step 1: Check refresh token
        if not fabric.git_refresh_token:
            return escalate_to_manual_recovery('HH-AUTH-002', 'No refresh token available')
        
        # Step 2: Attempt refresh
        new_token = github_refresh_token(fabric.git_refresh_token)
        if not new_token:
            return escalate_to_manual_recovery('HH-AUTH-002', 'Token refresh failed')
        
        # Step 3: Validate new token
        if not validate_github_token(new_token):
            return escalate_to_manual_recovery('HH-AUTH-002', 'New token invalid')
        
        # Step 4: Update credentials
        fabric.git_token = new_token
        fabric.save()
        
        return {
            'success': True,
            'recovery_type': 'automatic',
            'actions_taken': recovery_steps,
            'message': 'GitHub token successfully refreshed'
        }
        
    except Exception as e:
        return escalate_to_manual_recovery('HH-AUTH-002', str(e))
```

#### Manual Recovery Procedures

**HH-AUTH-001: Invalid GitHub Token**

**Prerequisites:**
- Access to GitHub account with repository permissions
- NetBox admin access to update fabric credentials

**Steps:**
1. **Generate New Token**
   ```bash
   # Navigate to GitHub Settings > Developer settings > Personal access tokens
   # Click "Generate new token"
   # Select required scopes: repo, workflow, write:packages
   # Copy the generated token
   ```

2. **Update Fabric Configuration**
   ```python
   # In NetBox admin interface or Django shell
   from netbox_hedgehog.models import HedgehogFabric
   
   fabric = HedgehogFabric.objects.get(name='your-fabric-name')
   fabric.git_token = 'your-new-github-token'
   fabric.save()
   ```

3. **Validate New Token**
   ```bash
   # Test token from command line
   curl -H "Authorization: token your-new-token" \
        https://api.github.com/repos/owner/repo
   ```

4. **Retry Failed Operation**
   ```python
   # Re-attempt the failed operation
   result = fabric.sync_with_github()
   if not result['success']:
       escalate_to_expert_support()
   ```

**HH-AUTH-012: Kubernetes RBAC Denied**

**Prerequisites:**
- Cluster admin access
- kubectl access to target cluster

**Steps:**
1. **Identify Missing Permissions**
   ```bash
   # Check current permissions
   kubectl auth can-i --list --as=system:serviceaccount:hedgehog:hedgehog-service
   
   # Test specific permissions
   kubectl auth can-i create crd --as=system:serviceaccount:hedgehog:hedgehog-service
   ```

2. **Create Required ClusterRole**
   ```yaml
   # hedgehog-cluster-role.yaml
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRole
   metadata:
     name: hedgehog-operator
   rules:
   - apiGroups: ["apiextensions.k8s.io"]
     resources: ["customresourcedefinitions"]
     verbs: ["get", "list", "create", "update", "patch", "delete"]
   - apiGroups: ["wiring.githedgehog.com", "vpc.githedgehog.com"]
     resources: ["*"]
     verbs: ["*"]
   ```

3. **Create ClusterRoleBinding**
   ```yaml
   # hedgehog-cluster-role-binding.yaml
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRoleBinding
   metadata:
     name: hedgehog-operator
   roleRef:
     apiGroup: rbac.authorization.k8s.io
     kind: ClusterRole
     name: hedgehog-operator
   subjects:
   - kind: ServiceAccount
     name: hedgehog-service
     namespace: hedgehog
   ```

4. **Apply RBAC Configuration**
   ```bash
   kubectl apply -f hedgehog-cluster-role.yaml
   kubectl apply -f hedgehog-cluster-role-binding.yaml
   ```

5. **Verify Permissions**
   ```bash
   kubectl auth can-i create crd --as=system:serviceaccount:hedgehog:hedgehog-service
   # Should return "yes"
   ```

## Git & GitHub Integration Recovery (HH-GIT-xxx)

### Repository Access Recovery

#### Automatic Recovery Procedures

**HH-GIT-004: Repository Temporarily Unavailable**
```python
def recover_repository_unavailable(repository_url, error_context):
    """Automatic retry with exponential backoff"""
    
    max_retries = 5
    base_delay = 2  # seconds
    
    for attempt in range(max_retries):
        delay = base_delay * (2 ** attempt)  # exponential backoff
        
        logger.info(f"Attempting repository access, retry {attempt + 1}/{max_retries}")
        
        try:
            # Wait before retry
            time.sleep(delay)
            
            # Test repository accessibility
            result = test_repository_access(repository_url)
            
            if result['success']:
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'attempts': attempt + 1,
                    'total_delay': sum(base_delay * (2 ** i) for i in range(attempt + 1)),
                    'message': f'Repository access restored after {attempt + 1} attempts'
                }
                
        except Exception as e:
            logger.warning(f"Repository access attempt {attempt + 1} failed: {e}")
            continue
    
    # All retries exhausted
    return escalate_to_manual_recovery(
        'HH-GIT-004',
        f'Repository unavailable after {max_retries} attempts'
    )
```

#### Manual Recovery Procedures

**HH-GIT-001: Repository Not Found**

**Prerequisites:**
- Repository owner access or organization admin rights
- Correct repository URL information

**Diagnostic Steps:**
1. **Verify Repository URL**
   ```bash
   # Test repository accessibility
   git ls-remote https://github.com/owner/repo.git
   ```

2. **Check Repository Status**
   ```bash
   # Using GitHub CLI
   gh repo view owner/repo
   
   # Or using API
   curl -H "Authorization: token $GITHUB_TOKEN" \
        https://api.github.com/repos/owner/repo
   ```

**Recovery Options:**

**Option A: Repository Name Changed**
1. Identify correct repository name
2. Update fabric configuration:
   ```python
   fabric = HedgehogFabric.objects.get(name='fabric-name')
   fabric.git_repository_url = 'https://github.com/owner/correct-repo.git'
   fabric.save()
   ```

**Option B: Repository Moved to Different Owner**
1. Get new repository location
2. Update fabric configuration with new owner:
   ```python
   fabric.git_repository_url = 'https://github.com/new-owner/repo.git'
   fabric.save()
   ```

**Option C: Repository Deleted - Restore from Backup**
1. Create new repository:
   ```bash
   gh repo create owner/repo --private
   ```

2. Push backup content:
   ```bash
   git clone /path/to/backup/repo
   cd repo
   git remote add origin https://github.com/owner/repo.git
   git push -u origin main
   ```

**HH-GIT-014: Merge Conflict Detected**

**Prerequisites:**
- Git command line access
- Understanding of GitOps directory structure

**Steps:**
1. **Identify Conflict Details**
   ```bash
   # Get conflict information
   git status
   git diff --name-only --diff-filter=U
   ```

2. **Analyze Conflict Context**
   ```bash
   # View conflicted file
   git show HEAD:path/to/conflicted/file.yaml
   git show origin/main:path/to/conflicted/file.yaml
   ```

3. **Resolution Strategy Selection**

   **Strategy A: Accept Remote Changes (GitOps is authoritative)**
   ```bash
   git checkout --theirs path/to/conflicted/file.yaml
   git add path/to/conflicted/file.yaml
   ```

   **Strategy B: Accept Local Changes (NetBox is authoritative)**
   ```bash
   git checkout --ours path/to/conflicted/file.yaml
   git add path/to/conflicted/file.yaml
   ```

   **Strategy C: Manual Merge**
   ```bash
   # Edit file manually to resolve conflicts
   vim path/to/conflicted/file.yaml
   # Remove conflict markers, choose appropriate content
   git add path/to/conflicted/file.yaml
   ```

4. **Complete Merge Resolution**
   ```bash
   git commit -m "Resolve merge conflict in GitOps configuration"
   git push origin main
   ```

5. **Validate Resolution**
   ```bash
   # Test YAML validity
   yq eval . path/to/conflicted/file.yaml
   
   # Test Kubernetes resource validation
   kubectl apply --dry-run=client -f path/to/conflicted/file.yaml
   ```

## Kubernetes API Recovery (HH-K8S-xxx)

### Cluster Connectivity Recovery

#### Automatic Recovery Procedures

**HH-K8S-004: Cluster Network Timeout**
```python
def recover_cluster_timeout(cluster_config, error_context):
    """Automatic timeout recovery with progressive timeouts"""
    
    timeout_progression = [30, 60, 120, 300]  # seconds
    
    for timeout in timeout_progression:
        try:
            logger.info(f"Attempting cluster connection with {timeout}s timeout")
            
            # Create client with extended timeout
            config = kubernetes.client.Configuration()
            config.host = cluster_config['server']
            config.api_key['authorization'] = cluster_config['token']
            config.timeout = timeout
            
            api_client = kubernetes.client.ApiClient(config)
            v1 = kubernetes.client.CoreV1Api(api_client)
            
            # Test connection with timeout
            namespaces = v1.list_namespace(_request_timeout=timeout)
            
            return {
                'success': True,
                'recovery_type': 'automatic',
                'effective_timeout': timeout,
                'message': f'Cluster connection restored with {timeout}s timeout'
            }
            
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 408 or 'timeout' in str(e).lower():
                continue  # Try next timeout
            else:
                return escalate_to_manual_recovery('HH-K8S-004', str(e))
        except Exception as e:
            logger.error(f"Cluster connection failed with {timeout}s timeout: {e}")
            continue
    
    return escalate_to_manual_recovery(
        'HH-K8S-004',
        'All timeout recovery attempts failed'
    )
```

#### Manual Recovery Procedures

**HH-K8S-001: Cluster Connection Failed**

**Prerequisites:**
- kubectl access to cluster
- Cluster admin permissions
- Network connectivity to cluster

**Diagnostic Steps:**
1. **Test Basic Connectivity**
   ```bash
   # Test API server endpoint
   curl -k https://your-cluster-api:6443/version
   
   # Test with kubectl
   kubectl cluster-info
   ```

2. **Verify Credentials**
   ```bash
   # Check current context
   kubectl config current-context
   
   # Verify token validity
   kubectl auth whoami
   ```

3. **Check Network Connectivity**
   ```bash
   # Test DNS resolution
   nslookup your-cluster-api
   
   # Test port connectivity
   telnet your-cluster-api 6443
   ```

**Recovery Steps:**

**Issue: API Server Unreachable**
1. **Check API Server Status**
   ```bash
   # On master node
   systemctl status kube-apiserver
   kubectl get pods -n kube-system | grep apiserver
   ```

2. **Verify API Server Configuration**
   ```bash
   # Check API server logs
   kubectl logs -n kube-system kube-apiserver-master-node
   ```

3. **Restart API Server if Needed**
   ```bash
   # For systemd
   systemctl restart kube-apiserver
   
   # For kubeadm clusters
   kubectl delete pod -n kube-system kube-apiserver-master-node
   ```

**Issue: Certificate Problems**
1. **Check Certificate Validity**
   ```bash
   # Check certificate expiration
   openssl x509 -in /etc/kubernetes/pki/apiserver.crt -noout -dates
   ```

2. **Regenerate Certificates if Expired**
   ```bash
   # Using kubeadm
   kubeadm certs renew apiserver
   kubeadm certs renew apiserver-kubelet-client
   ```

**HH-K8S-010: CRD Not Found**

**Prerequisites:**
- kubectl access with CRD creation permissions
- Hedgehog CRD manifests

**Steps:**
1. **List Current CRDs**
   ```bash
   kubectl get crd | grep githedgehog.com
   ```

2. **Install Missing CRDs**
   ```bash
   # Install VPC API CRDs
   kubectl apply -f https://raw.githubusercontent.com/githedgehog/vpc-crd/main/config/crd/bases/vpc.githedgehog.com_vpcs.yaml
   
   # Install Wiring API CRDs
   kubectl apply -f https://raw.githubusercontent.com/githedgehog/wiring-crd/main/config/crd/bases/wiring.githedgehog.com_connections.yaml
   ```

3. **Verify CRD Installation**
   ```bash
   kubectl get crd | grep githedgehog.com
   
   # Test CRD functionality
   kubectl explain vpc
   kubectl explain connection
   ```

4. **Update Fabric Configuration**
   ```python
   # Mark CRDs as available in fabric
   fabric = HedgehogFabric.objects.get(name='fabric-name')
   fabric.crd_status = 'installed'
   fabric.save()
   ```

## Data Validation Recovery (HH-VAL-xxx)

### Schema Validation Recovery

#### Automatic Recovery Procedures

**HH-VAL-001: YAML Syntax Error**
```python
def recover_yaml_syntax_error(yaml_content, error_context):
    """Automatic YAML syntax repair"""
    
    common_fixes = [
        # Fix unquoted strings that should be quoted
        (r'(\w+):\s+([^"\'\s][^:\n]*[^"\'\s\n])\s*$', r'\1: "\2"'),
        
        # Fix missing spaces after colons
        (r'(\w+):([^:\s])', r'\1: \2'),
        
        # Fix indentation issues (tabs to spaces)
        (r'\t', '  '),
        
        # Fix trailing commas
        (r',\s*\n\s*(\w+:)', r'\n\1'),
    ]
    
    fixed_content = yaml_content
    
    for pattern, replacement in common_fixes:
        try:
            fixed_content = re.sub(pattern, replacement, fixed_content, flags=re.MULTILINE)
            
            # Test if fix worked
            yaml.safe_load(fixed_content)
            
            return {
                'success': True,
                'recovery_type': 'automatic',
                'fix_applied': pattern,
                'fixed_content': fixed_content,
                'message': 'YAML syntax automatically corrected'
            }
            
        except yaml.YAMLError:
            continue  # Try next fix
    
    # No automatic fix worked
    return escalate_to_manual_recovery(
        'HH-VAL-001',
        'Could not automatically repair YAML syntax'
    )
```

#### Manual Recovery Procedures

**HH-VAL-002: Invalid YAML Structure**

**Prerequisites:**
- Text editor with YAML support
- YAML validation tools

**Steps:**
1. **Identify Structural Issues**
   ```bash
   # Validate YAML structure
   yq eval . your-file.yaml
   
   # Or using Python
   python -c "import yaml; print(yaml.safe_load(open('your-file.yaml')))"
   ```

2. **Common Structure Fixes**

   **Issue: Incorrect Indentation**
   ```yaml
   # Incorrect
   apiVersion: v1
   kind: Pod
   metadata:
   name: test-pod
     namespace: default
   
   # Correct
   apiVersion: v1
   kind: Pod
   metadata:
     name: test-pod
     namespace: default
   ```

   **Issue: Missing Required Fields**
   ```yaml
   # Incomplete - missing required fields
   apiVersion: vpc.githedgehog.com/v1alpha2
   kind: VPC
   metadata:
     name: test-vpc
   
   # Complete - with required spec
   apiVersion: vpc.githedgehog.com/v1alpha2
   kind: VPC
   metadata:
     name: test-vpc
   spec:
     subnets:
       - 10.1.0.0/24
   ```

3. **Validate Structure Against Schema**
   ```bash
   # Validate against Kubernetes schema
   kubectl apply --dry-run=client -f your-file.yaml
   
   # Validate against custom schema if available
   jsonschema -i your-file.yaml schema.json
   ```

## Network & Connectivity Recovery (HH-NET-xxx)

### Connection Recovery

#### Automatic Recovery Procedures

**HH-NET-001: Connection Timeout**
```python
def recover_connection_timeout(target_url, error_context):
    """Automatic timeout recovery with adaptive timeouts"""
    
    # Progressive timeout strategy
    timeout_strategy = [
        {'timeout': 30, 'retries': 3},
        {'timeout': 60, 'retries': 2}, 
        {'timeout': 120, 'retries': 1}
    ]
    
    for strategy in timeout_strategy:
        for attempt in range(strategy['retries']):
            try:
                logger.info(f"Connection attempt with {strategy['timeout']}s timeout, retry {attempt + 1}")
                
                response = requests.get(
                    target_url,
                    timeout=strategy['timeout'],
                    headers={'User-Agent': 'NetBox-Hedgehog-Plugin/1.0'}
                )
                
                if response.status_code == 200:
                    return {
                        'success': True,
                        'recovery_type': 'automatic',
                        'effective_timeout': strategy['timeout'],
                        'attempts': attempt + 1,
                        'message': f'Connection restored with {strategy["timeout"]}s timeout'
                    }
                    
            except requests.exceptions.Timeout:
                continue  # Try next timeout/retry
            except Exception as e:
                return escalate_to_manual_recovery('HH-NET-001', str(e))
    
    return escalate_to_manual_recovery(
        'HH-NET-001', 
        'All timeout recovery attempts failed'
    )
```

### Manual Recovery Procedures

**HH-NET-002: Connection Refused**

**Prerequisites:**
- Network diagnostic tools (ping, telnet, curl)
- Access to target service configuration

**Steps:**
1. **Basic Connectivity Test**
   ```bash
   # Test DNS resolution
   nslookup target-service.example.com
   
   # Test network connectivity
   ping target-service.example.com
   
   # Test port connectivity  
   telnet target-service.example.com 443
   ```

2. **Service Status Check**
   ```bash
   # Check if service is running
   curl -I https://target-service.example.com/health
   
   # Check service logs if accessible
   kubectl logs -f deployment/target-service
   ```

3. **Firewall and Security Groups**
   ```bash
   # Check local firewall rules
   sudo iptables -L | grep target-port
   
   # For cloud environments, check security groups
   aws ec2 describe-security-groups --group-ids sg-12345678
   ```

4. **Proxy Configuration**
   ```bash
   # Test direct connection vs proxy
   curl --noproxy "*" https://target-service.example.com
   
   # Check proxy settings
   echo $HTTP_PROXY
   echo $HTTPS_PROXY
   ```

## State Transition Recovery (HH-STATE-xxx)

### State Consistency Recovery

#### Automatic Recovery Procedures

**HH-STATE-010: Inconsistent State**
```python
def recover_inconsistent_state(entity, error_context):
    """Automatic state consistency repair"""
    
    # State consistency rules
    consistency_rules = [
        {
            'condition': lambda e: e.status == 'ACTIVE' and e.connection_status == 'DISCONNECTED',
            'action': lambda e: setattr(e, 'status', 'INACTIVE'),
            'description': 'Active entity cannot be disconnected'
        },
        {
            'condition': lambda e: e.sync_status == 'SYNCED' and not e.last_sync,
            'action': lambda e: setattr(e, 'sync_status', 'NEVER_SYNCED'),
            'description': 'Synced entity must have last_sync timestamp'
        }
    ]
    
    fixes_applied = []
    
    for rule in consistency_rules:
        if rule['condition'](entity):
            try:
                rule['action'](entity)
                fixes_applied.append(rule['description'])
            except Exception as e:
                logger.error(f"State consistency fix failed: {e}")
                continue
    
    if fixes_applied:
        try:
            entity.save()
            return {
                'success': True,
                'recovery_type': 'automatic',
                'fixes_applied': fixes_applied,
                'message': 'State consistency automatically restored'
            }
        except Exception as e:
            return escalate_to_manual_recovery('HH-STATE-010', str(e))
    
    return escalate_to_manual_recovery(
        'HH-STATE-010',
        'No automatic consistency fixes available'
    )
```

#### Manual Recovery Procedures

**HH-STATE-001: Transition Not Allowed**

**Prerequisites:**
- Understanding of entity state machines
- Database access for state inspection

**Steps:**
1. **Identify Current State**
   ```python
   # Check entity current state
   entity = HedgehogFabric.objects.get(id=entity_id)
   print(f"Status: {entity.status}")
   print(f"Connection Status: {entity.connection_status}")  
   print(f"Sync Status: {entity.sync_status}")
   ```

2. **Review State Transition Rules**
   ```python
   # Check valid transitions from current state
   from netbox_hedgehog.specifications.state_machines import get_valid_transitions
   
   valid_transitions = get_valid_transitions(
       entity.__class__, 
       entity.get_current_state()
   )
   print(f"Valid transitions: {valid_transitions}")
   ```

3. **Identify Transition Path**
   ```python
   # Find path from current to desired state
   path = find_transition_path(
       entity.get_current_state(),
       desired_state
   )
   print(f"Required transition path: {' -> '.join(path)}")
   ```

4. **Execute Valid Transition Sequence**
   ```python
   # Execute transitions in sequence
   for target_state in path[1:]:  # Skip current state
       try:
           entity.transition_to(target_state, 'manual_recovery')
           logger.info(f"Transitioned to {target_state}")
       except Exception as e:
           logger.error(f"Transition to {target_state} failed: {e}")
           break
   ```

## Recovery Escalation Procedures

### Escalation Levels

#### Level 1: Automatic Retry
- System automatically retries with backoff
- No human intervention required
- Success/failure logged for monitoring

#### Level 2: Guided Recovery  
- System provides recovery instructions
- User follows automated guidance
- System validates recovery success

#### Level 3: Manual Resolution
- Expert intervention required
- Custom recovery procedures needed
- May require external dependencies

#### Level 4: Emergency Response
- System-wide impact
- Immediate attention required
- May require vendor support

### Escalation Implementation

```python
def escalate_recovery(error_code, context, escalation_level):
    """Escalate recovery based on error severity and attempts"""
    
    escalation_actions = {
        1: create_monitoring_alert,
        2: create_user_notification_with_guidance,
        3: create_admin_alert_with_procedures,
        4: create_emergency_incident
    }
    
    action = escalation_actions.get(escalation_level)
    if action:
        return action(error_code, context)
    else:
        logger.error(f"Invalid escalation level: {escalation_level}")
```

This comprehensive recovery procedure framework ensures consistent, documented recovery approaches for all error scenarios in the NetBox Hedgehog Plugin.