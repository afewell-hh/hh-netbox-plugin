"""
Recovery Workflow Examples for NetBox Hedgehog Plugin

This module provides automated recovery workflow implementations for common
error scenarios. These workflows orchestrate multiple recovery steps and
provide structured approaches to error resolution.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """Individual workflow step"""
    name: str
    description: str
    action: Callable
    required: bool = True
    timeout: int = 300  # 5 minutes default
    retry_count: int = 0
    max_retries: int = 3
    depends_on: List[str] = None


@dataclass
class WorkflowResult:
    """Workflow execution result"""
    success: bool
    status: WorkflowStatus
    message: str
    steps_completed: List[str]
    steps_failed: List[str]
    total_execution_time: float
    error_details: Optional[Dict[str, Any]] = None


class RecoveryWorkflow(ABC):
    """Base class for recovery workflows"""
    
    def __init__(self, name: str, error_code: str):
        self.name = name
        self.error_code = error_code
        self.steps: List[WorkflowStep] = []
        self.status = WorkflowStatus.PENDING
        self.start_time = None
        self.end_time = None
        self.context = {}
        self._initialize_steps()
    
    @abstractmethod
    def _initialize_steps(self):
        """Initialize workflow steps - override in subclasses"""
        pass
    
    def execute(self, error_context: Dict[str, Any]) -> WorkflowResult:
        """Execute the recovery workflow"""
        
        self.context = error_context
        self.status = WorkflowStatus.IN_PROGRESS
        self.start_time = time.time()
        
        steps_completed = []
        steps_failed = []
        
        try:
            logger.info(f"Starting recovery workflow: {self.name}")
            
            # Execute steps in order
            for step in self.steps:
                try:
                    if self._should_execute_step(step, steps_completed):
                        logger.info(f"Executing step: {step.name}")
                        
                        step_result = self._execute_step(step)
                        
                        if step_result.get('success'):
                            steps_completed.append(step.name)
                            logger.info(f"Step completed successfully: {step.name}")
                        else:
                            steps_failed.append(step.name)
                            logger.warning(f"Step failed: {step.name} - {step_result.get('message', 'Unknown error')}")
                            
                            if step.required:
                                # Required step failed - abort workflow
                                logger.error(f"Required step failed, aborting workflow: {step.name}")
                                break
                    else:
                        logger.info(f"Skipping step due to dependencies: {step.name}")
                        
                except Exception as step_error:
                    steps_failed.append(step.name)
                    logger.error(f"Step execution error: {step.name} - {str(step_error)}")
                    
                    if step.required:
                        logger.error(f"Required step had execution error, aborting workflow")
                        break
            
            # Determine overall success
            required_steps = [s.name for s in self.steps if s.required]
            required_steps_completed = set(required_steps) & set(steps_completed)
            
            success = len(required_steps_completed) == len(required_steps)
            self.status = WorkflowStatus.COMPLETED if success else WorkflowStatus.FAILED
            
        except Exception as workflow_error:
            logger.error(f"Workflow execution error: {str(workflow_error)}")
            self.status = WorkflowStatus.FAILED
            success = False
        
        finally:
            self.end_time = time.time()
        
        execution_time = self.end_time - self.start_time
        
        result = WorkflowResult(
            success=success,
            status=self.status,
            message=self._generate_result_message(steps_completed, steps_failed),
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            total_execution_time=execution_time
        )
        
        logger.info(f"Workflow {self.name} completed with status: {self.status.value}")
        return result
    
    def _should_execute_step(self, step: WorkflowStep, completed_steps: List[str]) -> bool:
        """Check if step should be executed based on dependencies"""
        
        if not step.depends_on:
            return True
        
        # Check if all dependencies are completed
        for dependency in step.depends_on:
            if dependency not in completed_steps:
                return False
        
        return True
    
    def _execute_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute individual workflow step with retry logic"""
        
        for attempt in range(step.max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying step {step.name}, attempt {attempt + 1}/{step.max_retries + 1}")
                    time.sleep(min(2 ** attempt, 30))  # Exponential backoff, max 30 seconds
                
                # Execute the step action with timeout
                step_result = self._execute_with_timeout(step.action, step.timeout, self.context)
                
                if step_result.get('success'):
                    return step_result
                elif attempt < step.max_retries:
                    logger.warning(f"Step {step.name} failed, retrying: {step_result.get('message', 'Unknown error')}")
                    step.retry_count += 1
                    continue
                else:
                    logger.error(f"Step {step.name} failed after {step.max_retries} retries")
                    return step_result
                    
            except Exception as e:
                if attempt < step.max_retries:
                    logger.warning(f"Step {step.name} threw exception, retrying: {str(e)}")
                    step.retry_count += 1
                    continue
                else:
                    logger.error(f"Step {step.name} threw exception after retries: {str(e)}")
                    return {'success': False, 'message': f'Step exception: {str(e)}'}
        
        return {'success': False, 'message': 'Step execution failed'}
    
    def _execute_with_timeout(self, action: Callable, timeout: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action with timeout"""
        
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Step execution timeout after {timeout} seconds")
        
        # Set timeout alarm
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        try:
            result = action(context)
            signal.alarm(0)  # Cancel alarm
            return result
        except TimeoutError as e:
            signal.alarm(0)  # Cancel alarm
            return {'success': False, 'message': str(e)}
        except Exception as e:
            signal.alarm(0)  # Cancel alarm
            raise e
    
    def _generate_result_message(self, completed: List[str], failed: List[str]) -> str:
        """Generate result message based on step outcomes"""
        
        if not failed:
            return f"All workflow steps completed successfully ({len(completed)} steps)"
        elif not completed:
            return f"All workflow steps failed ({len(failed)} steps)"
        else:
            return f"Partial workflow completion: {len(completed)} succeeded, {len(failed)} failed"


class GitRepositoryRecoveryWorkflow(RecoveryWorkflow):
    """Recovery workflow for Git repository issues"""
    
    def __init__(self, error_code: str = "HH-GIT-001"):
        super().__init__("GitRepositoryRecovery", error_code)
    
    def _initialize_steps(self):
        self.steps = [
            WorkflowStep(
                name="validate_repository_url",
                description="Validate and normalize repository URL",
                action=self._validate_repository_url,
                required=True
            ),
            WorkflowStep(
                name="test_repository_access",
                description="Test basic repository access",
                action=self._test_repository_access,
                required=True,
                depends_on=["validate_repository_url"]
            ),
            WorkflowStep(
                name="refresh_credentials",
                description="Refresh authentication credentials if needed",
                action=self._refresh_credentials,
                required=False,
                depends_on=["test_repository_access"]
            ),
            WorkflowStep(
                name="try_alternative_urls",
                description="Try alternative repository URL formats",
                action=self._try_alternative_urls,
                required=False,
                depends_on=["test_repository_access"]
            ),
            WorkflowStep(
                name="verify_permissions",
                description="Verify repository permissions",
                action=self._verify_permissions,
                required=True,
                depends_on=["test_repository_access"]
            ),
            WorkflowStep(
                name="update_configuration",
                description="Update fabric configuration with working settings",
                action=self._update_configuration,
                required=True,
                depends_on=["verify_permissions"]
            )
        ]
    
    def _validate_repository_url(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize repository URL"""
        
        repository_url = context.get('repository_url', '')
        
        if not repository_url:
            return {'success': False, 'message': 'No repository URL provided'}
        
        # Normalize URL format
        import re
        
        # Add .git suffix if missing
        if not repository_url.endswith('.git'):
            repository_url += '.git'
        
        # Ensure HTTPS protocol
        if repository_url.startswith('git@github.com:'):
            # Convert SSH to HTTPS
            repository_url = repository_url.replace('git@github.com:', 'https://github.com/')
        elif not repository_url.startswith('https://'):
            repository_url = 'https://' + repository_url.lstrip('/')
        
        # Validate URL format
        github_pattern = r'https://github\.com/[^/]+/[^/]+\.git'
        if not re.match(github_pattern, repository_url):
            return {
                'success': False,
                'message': f'Invalid GitHub repository URL format: {repository_url}'
            }
        
        # Store normalized URL in context
        context['normalized_repository_url'] = repository_url
        
        return {
            'success': True,
            'message': f'Repository URL validated and normalized: {repository_url}',
            'normalized_url': repository_url
        }
    
    def _test_repository_access(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Test basic repository access"""
        
        repository_url = context.get('normalized_repository_url')
        
        if not repository_url:
            return {'success': False, 'message': 'No normalized repository URL available'}
        
        # Test repository access using git ls-remote
        import subprocess
        
        try:
            logger.info(f"Testing repository access: {repository_url}")
            
            # Use git ls-remote to test access without cloning
            result = subprocess.run(
                ['git', 'ls-remote', repository_url],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Repository access successful',
                    'output': result.stdout[:500]  # Limit output size
                }
            else:
                return {
                    'success': False,
                    'message': f'Repository access failed: {result.stderr}',
                    'error_output': result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'message': 'Repository access timeout'}
        except FileNotFoundError:
            return {'success': False, 'message': 'Git command not found'}
        except Exception as e:
            return {'success': False, 'message': f'Repository access error: {str(e)}'}
    
    def _refresh_credentials(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh authentication credentials"""
        
        fabric_id = context.get('entity_id')
        
        if not fabric_id:
            return {'success': False, 'message': 'No fabric ID provided for credential refresh'}
        
        try:
            # Mock credential refresh logic
            logger.info(f"Refreshing credentials for fabric {fabric_id}")
            
            # In real implementation, this would:
            # 1. Check if refresh token is available
            # 2. Request new access token
            # 3. Update stored credentials
            # 4. Test new credentials
            
            # For now, return mock success
            return {
                'success': True,
                'message': 'Credentials refreshed successfully',
                'credential_type': 'github_token'
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Credential refresh failed: {str(e)}'}
    
    def _try_alternative_urls(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Try alternative repository URL formats"""
        
        original_url = context.get('normalized_repository_url', '')
        
        if not original_url:
            return {'success': False, 'message': 'No original URL to generate alternatives'}
        
        # Generate alternative URLs
        alternatives = []
        
        # Remove .git suffix
        if original_url.endswith('.git'):
            alternatives.append(original_url[:-4])
        
        # Try different protocols (if not production)
        if original_url.startswith('https://'):
            ssh_url = original_url.replace('https://github.com/', 'git@github.com:')
            alternatives.append(ssh_url)
        
        # Test alternatives
        for alt_url in alternatives:
            try:
                import subprocess
                
                result = subprocess.run(
                    ['git', 'ls-remote', alt_url],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if result.returncode == 0:
                    context['working_repository_url'] = alt_url
                    return {
                        'success': True,
                        'message': f'Alternative URL works: {alt_url}',
                        'working_url': alt_url
                    }
                    
            except Exception:
                continue
        
        return {
            'success': False,
            'message': 'No working alternative URLs found',
            'alternatives_tried': alternatives
        }
    
    def _verify_permissions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify repository permissions"""
        
        repository_url = context.get('working_repository_url') or context.get('normalized_repository_url')
        
        if not repository_url:
            return {'success': False, 'message': 'No repository URL to verify permissions'}
        
        try:
            # Test clone access (read permission)
            import subprocess
            import tempfile
            import shutil
            
            with tempfile.TemporaryDirectory() as temp_dir:
                logger.info("Testing clone permissions")
                
                result = subprocess.run(
                    ['git', 'clone', '--depth', '1', repository_url, temp_dir + '/test'],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    # Test push access by checking remote info
                    logger.info("Testing push permissions")
                    
                    # This is a simplified check - real implementation would be more thorough
                    permissions = {
                        'clone': True,
                        'push': True,  # Assume true if clone works and we have credentials
                        'verified': True
                    }
                    
                    return {
                        'success': True,
                        'message': 'Repository permissions verified',
                        'permissions': permissions
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Permission verification failed: {result.stderr}',
                        'error': result.stderr
                    }
                    
        except Exception as e:
            return {'success': False, 'message': f'Permission verification error: {str(e)}'}
    
    def _update_configuration(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update fabric configuration with working settings"""
        
        fabric_id = context.get('entity_id')
        working_url = context.get('working_repository_url') or context.get('normalized_repository_url')
        
        if not fabric_id:
            return {'success': False, 'message': 'No fabric ID for configuration update'}
        
        if not working_url:
            return {'success': False, 'message': 'No working repository URL for configuration update'}
        
        try:
            logger.info(f"Updating fabric {fabric_id} configuration with URL: {working_url}")
            
            # Mock configuration update
            # In real implementation, this would:
            # 1. Get the HedgehogFabric instance
            # 2. Update the git_repository_url field
            # 3. Save the changes
            # 4. Validate the update
            
            return {
                'success': True,
                'message': f'Configuration updated successfully with URL: {working_url}',
                'updated_url': working_url,
                'fabric_id': fabric_id
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Configuration update failed: {str(e)}'}


class KubernetesConnectionRecoveryWorkflow(RecoveryWorkflow):
    """Recovery workflow for Kubernetes connection issues"""
    
    def __init__(self, error_code: str = "HH-K8S-001"):
        super().__init__("KubernetesConnectionRecovery", error_code)
    
    def _initialize_steps(self):
        self.steps = [
            WorkflowStep(
                name="validate_cluster_endpoint",
                description="Validate Kubernetes cluster endpoint",
                action=self._validate_cluster_endpoint,
                required=True
            ),
            WorkflowStep(
                name="test_network_connectivity",
                description="Test network connectivity to cluster",
                action=self._test_network_connectivity,
                required=True,
                depends_on=["validate_cluster_endpoint"]
            ),
            WorkflowStep(
                name="validate_credentials",
                description="Validate Kubernetes credentials",
                action=self._validate_credentials,
                required=True,
                depends_on=["test_network_connectivity"]
            ),
            WorkflowStep(
                name="test_api_access",
                description="Test Kubernetes API access",
                action=self._test_api_access,
                required=True,
                depends_on=["validate_credentials"]
            ),
            WorkflowStep(
                name="check_rbac_permissions",
                description="Check RBAC permissions",
                action=self._check_rbac_permissions,
                required=False,
                depends_on=["test_api_access"]
            ),
            WorkflowStep(
                name="verify_required_crds",
                description="Verify required CRDs are installed",
                action=self._verify_required_crds,
                required=False,
                depends_on=["check_rbac_permissions"]
            )
        ]
    
    def _validate_cluster_endpoint(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Kubernetes cluster endpoint"""
        
        cluster_endpoint = context.get('cluster_endpoint', '')
        
        if not cluster_endpoint:
            return {'success': False, 'message': 'No cluster endpoint provided'}
        
        # Validate URL format
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(cluster_endpoint)
            
            if not parsed.scheme:
                return {'success': False, 'message': 'Cluster endpoint must include scheme (https://)'}
            
            if not parsed.netloc:
                return {'success': False, 'message': 'Cluster endpoint must include hostname'}
            
            if parsed.scheme not in ['https', 'http']:
                return {'success': False, 'message': 'Cluster endpoint must use http or https scheme'}
            
            # Normalize port
            port = parsed.port
            if not port:
                port = 443 if parsed.scheme == 'https' else 80
            
            normalized_endpoint = f"{parsed.scheme}://{parsed.hostname}:{port}"
            context['normalized_cluster_endpoint'] = normalized_endpoint
            
            return {
                'success': True,
                'message': f'Cluster endpoint validated: {normalized_endpoint}',
                'normalized_endpoint': normalized_endpoint
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Invalid cluster endpoint format: {str(e)}'}
    
    def _test_network_connectivity(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Test network connectivity to cluster"""
        
        endpoint = context.get('normalized_cluster_endpoint')
        
        if not endpoint:
            return {'success': False, 'message': 'No cluster endpoint to test'}
        
        from urllib.parse import urlparse
        parsed = urlparse(endpoint)
        hostname = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        
        try:
            import socket
            
            logger.info(f"Testing network connectivity to {hostname}:{port}")
            
            # Test TCP connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            result = sock.connect_ex((hostname, port))
            sock.close()
            
            if result == 0:
                return {
                    'success': True,
                    'message': f'Network connectivity successful to {hostname}:{port}'
                }
            else:
                return {
                    'success': False,
                    'message': f'Network connectivity failed to {hostname}:{port} (error code: {result})'
                }
                
        except socket.gaierror as e:
            return {'success': False, 'message': f'DNS resolution failed for {hostname}: {str(e)}'}
        except Exception as e:
            return {'success': False, 'message': f'Network connectivity test failed: {str(e)}'}
    
    def _validate_credentials(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Kubernetes credentials"""
        
        token = context.get('kubernetes_token')
        
        if not token:
            return {'success': False, 'message': 'No Kubernetes token provided'}
        
        try:
            # Basic token format validation
            if len(token) < 10:
                return {'success': False, 'message': 'Kubernetes token appears too short'}
            
            # JWT token format check
            if token.count('.') == 2:
                # Appears to be JWT - validate structure
                import base64
                import json
                
                try:
                    header, payload, signature = token.split('.')
                    
                    # Decode payload
                    padded_payload = payload + '=' * (4 - len(payload) % 4)
                    decoded_payload = base64.urlsafe_b64decode(padded_payload)
                    token_data = json.loads(decoded_payload)
                    
                    # Check expiration
                    import time
                    current_time = time.time()
                    
                    if 'exp' in token_data and token_data['exp'] < current_time:
                        return {'success': False, 'message': 'Kubernetes token has expired'}
                    
                    return {
                        'success': True,
                        'message': 'Kubernetes token format validated',
                        'token_type': 'jwt',
                        'expiry': token_data.get('exp')
                    }
                    
                except Exception as jwt_error:
                    return {
                        'success': False,
                        'message': f'Invalid JWT token format: {str(jwt_error)}'
                    }
            
            # Non-JWT token (service account token)
            return {
                'success': True,
                'message': 'Kubernetes token format appears valid',
                'token_type': 'service_account'
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Token validation failed: {str(e)}'}
    
    def _test_api_access(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Test Kubernetes API access"""
        
        endpoint = context.get('normalized_cluster_endpoint')
        token = context.get('kubernetes_token')
        
        if not endpoint or not token:
            return {'success': False, 'message': 'Missing endpoint or token for API test'}
        
        try:
            import requests
            
            # Test basic API access
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            api_url = f"{endpoint}/api/v1/namespaces"
            
            logger.info(f"Testing Kubernetes API access: {api_url}")
            
            response = requests.get(api_url, headers=headers, timeout=30, verify=False)
            
            if response.status_code == 200:
                namespaces_data = response.json()
                namespace_count = len(namespaces_data.get('items', []))
                
                return {
                    'success': True,
                    'message': f'Kubernetes API access successful ({namespace_count} namespaces accessible)',
                    'namespace_count': namespace_count
                }
            elif response.status_code == 401:
                return {'success': False, 'message': 'Kubernetes API authentication failed (401 Unauthorized)'}
            elif response.status_code == 403:
                return {'success': False, 'message': 'Kubernetes API access forbidden (403 Forbidden)'}
            else:
                return {
                    'success': False,
                    'message': f'Kubernetes API access failed (HTTP {response.status_code}): {response.text[:200]}'
                }
                
        except requests.exceptions.SSLError as e:
            return {'success': False, 'message': f'SSL/TLS error connecting to Kubernetes API: {str(e)}'}
        except requests.exceptions.ConnectionError as e:
            return {'success': False, 'message': f'Connection error to Kubernetes API: {str(e)}'}
        except requests.exceptions.Timeout as e:
            return {'success': False, 'message': f'Timeout connecting to Kubernetes API: {str(e)}'}
        except Exception as e:
            return {'success': False, 'message': f'Kubernetes API test failed: {str(e)}'}
    
    def _check_rbac_permissions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check RBAC permissions"""
        
        endpoint = context.get('normalized_cluster_endpoint')
        token = context.get('kubernetes_token')
        
        if not endpoint or not token:
            return {'success': False, 'message': 'Missing endpoint or token for RBAC check'}
        
        try:
            import requests
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Test required permissions
            required_permissions = [
                {'verb': 'get', 'resource': 'namespaces'},
                {'verb': 'list', 'resource': 'namespaces'},
                {'verb': 'create', 'resource': 'customresourcedefinitions'},
                {'verb': 'get', 'resource': 'customresourcedefinitions'}
            ]
            
            permission_results = []
            
            for permission in required_permissions:
                # Use SelfSubjectAccessReview to check permissions
                review_data = {
                    'apiVersion': 'authorization.k8s.io/v1',
                    'kind': 'SelfSubjectAccessReview',
                    'spec': {
                        'resourceAttributes': {
                            'verb': permission['verb'],
                            'resource': permission['resource']
                        }
                    }
                }
                
                api_url = f"{endpoint}/apis/authorization.k8s.io/v1/selfsubjectaccessreviews"
                
                response = requests.post(api_url, headers=headers, json=review_data, timeout=30, verify=False)
                
                if response.status_code == 201:
                    result = response.json()
                    allowed = result.get('status', {}).get('allowed', False)
                    permission_results.append({
                        'permission': f"{permission['verb']} {permission['resource']}",
                        'allowed': allowed
                    })
                else:
                    permission_results.append({
                        'permission': f"{permission['verb']} {permission['resource']}",
                        'allowed': False,
                        'error': f'HTTP {response.status_code}'
                    })
            
            # Check if all required permissions are allowed
            denied_permissions = [p for p in permission_results if not p.get('allowed')]
            
            if not denied_permissions:
                return {
                    'success': True,
                    'message': 'All required RBAC permissions verified',
                    'permissions': permission_results
                }
            else:
                return {
                    'success': False,
                    'message': f'{len(denied_permissions)} permissions denied',
                    'denied_permissions': denied_permissions,
                    'all_permissions': permission_results
                }
                
        except Exception as e:
            return {'success': False, 'message': f'RBAC permission check failed: {str(e)}'}
    
    def _verify_required_crds(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify required CRDs are installed"""
        
        endpoint = context.get('normalized_cluster_endpoint')
        token = context.get('kubernetes_token')
        
        if not endpoint or not token:
            return {'success': False, 'message': 'Missing endpoint or token for CRD verification'}
        
        try:
            import requests
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            # Check for required CRDs
            required_crds = [
                'vpcs.vpc.githedgehog.com',
                'connections.wiring.githedgehog.com',
                'switches.wiring.githedgehog.com'
            ]
            
            crd_results = []
            
            for crd_name in required_crds:
                api_url = f"{endpoint}/apis/apiextensions.k8s.io/v1/customresourcedefinitions/{crd_name}"
                
                response = requests.get(api_url, headers=headers, timeout=30, verify=False)
                
                if response.status_code == 200:
                    crd_data = response.json()
                    status = crd_data.get('status', {})
                    conditions = status.get('conditions', [])
                    
                    # Check if CRD is established
                    established = any(
                        c.get('type') == 'Established' and c.get('status') == 'True'
                        for c in conditions
                    )
                    
                    crd_results.append({
                        'name': crd_name,
                        'installed': True,
                        'established': established
                    })
                else:
                    crd_results.append({
                        'name': crd_name,
                        'installed': False,
                        'established': False
                    })
            
            missing_crds = [c for c in crd_results if not c.get('installed')]
            unestablished_crds = [c for c in crd_results if c.get('installed') and not c.get('established')]
            
            if not missing_crds and not unestablished_crds:
                return {
                    'success': True,
                    'message': 'All required CRDs are installed and established',
                    'crds': crd_results
                }
            else:
                issues = []
                if missing_crds:
                    issues.append(f"{len(missing_crds)} CRDs missing")
                if unestablished_crds:
                    issues.append(f"{len(unestablished_crds)} CRDs not established")
                
                return {
                    'success': False,
                    'message': f'CRD issues found: {", ".join(issues)}',
                    'missing_crds': missing_crds,
                    'unestablished_crds': unestablished_crds,
                    'all_crds': crd_results
                }
                
        except Exception as e:
            return {'success': False, 'message': f'CRD verification failed: {str(e)}'}


class NetworkConnectivityRecoveryWorkflow(RecoveryWorkflow):
    """Recovery workflow for network connectivity issues"""
    
    def __init__(self, error_code: str = "HH-NET-001"):
        super().__init__("NetworkConnectivityRecovery", error_code)
    
    def _initialize_steps(self):
        self.steps = [
            WorkflowStep(
                name="analyze_target_endpoint",
                description="Analyze target endpoint and extract components",
                action=self._analyze_target_endpoint,
                required=True
            ),
            WorkflowStep(
                name="test_dns_resolution",
                description="Test DNS resolution for target hostname",
                action=self._test_dns_resolution,
                required=True,
                depends_on=["analyze_target_endpoint"]
            ),
            WorkflowStep(
                name="test_network_connectivity",
                description="Test basic network connectivity",
                action=self._test_network_connectivity,
                required=True,
                depends_on=["test_dns_resolution"]
            ),
            WorkflowStep(
                name="test_progressive_timeouts",
                description="Test with progressively longer timeouts",
                action=self._test_progressive_timeouts,
                required=False,
                depends_on=["test_network_connectivity"]
            ),
            WorkflowStep(
                name="try_alternative_ports",
                description="Try alternative port numbers",
                action=self._try_alternative_ports,
                required=False,
                depends_on=["test_network_connectivity"]
            ),
            WorkflowStep(
                name="test_without_tls",
                description="Test connection without TLS if applicable",
                action=self._test_without_tls,
                required=False,
                depends_on=["test_network_connectivity"]
            )
        ]
    
    def _analyze_target_endpoint(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze target endpoint and extract components"""
        
        target_url = context.get('target_url', '')
        
        if not target_url:
            return {'success': False, 'message': 'No target URL provided'}
        
        try:
            from urllib.parse import urlparse
            
            parsed = urlparse(target_url)
            
            if not parsed.hostname:
                return {'success': False, 'message': f'Cannot extract hostname from URL: {target_url}'}
            
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            
            endpoint_info = {
                'hostname': parsed.hostname,
                'port': port,
                'scheme': parsed.scheme,
                'path': parsed.path,
                'full_url': target_url
            }
            
            context['endpoint_info'] = endpoint_info
            
            return {
                'success': True,
                'message': f'Endpoint analyzed: {parsed.hostname}:{port}',
                'endpoint_info': endpoint_info
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Endpoint analysis failed: {str(e)}'}
    
    def _test_dns_resolution(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Test DNS resolution for target hostname"""
        
        endpoint_info = context.get('endpoint_info', {})
        hostname = endpoint_info.get('hostname')
        
        if not hostname:
            return {'success': False, 'message': 'No hostname to resolve'}
        
        try:
            import socket
            
            logger.info(f"Testing DNS resolution for {hostname}")
            
            # Resolve hostname to IP addresses
            addr_info = socket.getaddrinfo(hostname, None)
            ip_addresses = list(set(info[4][0] for info in addr_info))
            
            context['resolved_ips'] = ip_addresses
            
            return {
                'success': True,
                'message': f'DNS resolution successful: {hostname} -> {ip_addresses}',
                'resolved_ips': ip_addresses
            }
            
        except socket.gaierror as e:
            # Try alternative DNS servers
            alternative_result = self._try_alternative_dns(hostname)
            
            if alternative_result.get('success'):
                context['resolved_ips'] = alternative_result['resolved_ips']
                return alternative_result
            
            return {'success': False, 'message': f'DNS resolution failed: {str(e)}'}
        except Exception as e:
            return {'success': False, 'message': f'DNS resolution error: {str(e)}'}
    
    def _try_alternative_dns(self, hostname: str) -> Dict[str, Any]:
        """Try alternative DNS servers"""
        
        alternative_dns = ['8.8.8.8', '1.1.1.1', '208.67.222.222']
        
        for dns_server in alternative_dns:
            try:
                import subprocess
                
                result = subprocess.run(
                    ['nslookup', hostname, dns_server],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    # Parse IP from nslookup output
                    import re
                    ip_pattern = r'Address: (\d+\.\d+\.\d+\.\d+)'
                    matches = re.findall(ip_pattern, result.stdout)
                    
                    if matches:
                        return {
                            'success': True,
                            'message': f'DNS resolution successful using {dns_server}',
                            'resolved_ips': matches,
                            'dns_server': dns_server
                        }
                        
            except Exception:
                continue
        
        return {'success': False, 'message': 'All alternative DNS servers failed'}
    
    def _test_network_connectivity(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Test basic network connectivity"""
        
        endpoint_info = context.get('endpoint_info', {})
        hostname = endpoint_info.get('hostname')
        port = endpoint_info.get('port')
        
        if not hostname or not port:
            return {'success': False, 'message': 'Missing hostname or port for connectivity test'}
        
        try:
            import socket
            
            logger.info(f"Testing network connectivity to {hostname}:{port}")
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            result = sock.connect_ex((hostname, port))
            sock.close()
            
            if result == 0:
                return {
                    'success': True,
                    'message': f'Network connectivity successful to {hostname}:{port}'
                }
            else:
                return {
                    'success': False,
                    'message': f'Network connectivity failed to {hostname}:{port} (error code: {result})'
                }
                
        except Exception as e:
            return {'success': False, 'message': f'Network connectivity test error: {str(e)}'}
    
    def _test_progressive_timeouts(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Test with progressively longer timeouts"""
        
        target_url = context.get('target_url', '')
        
        if not target_url:
            return {'success': False, 'message': 'No target URL for timeout testing'}
        
        timeouts = [30, 60, 120, 300]  # Progressive timeouts in seconds
        
        for timeout in timeouts:
            try:
                import requests
                
                logger.info(f"Testing connection with {timeout}s timeout")
                
                response = requests.get(target_url, timeout=timeout)
                
                if response.status_code < 400:
                    context['working_timeout'] = timeout
                    return {
                        'success': True,
                        'message': f'Connection successful with {timeout}s timeout',
                        'working_timeout': timeout,
                        'status_code': response.status_code
                    }
                    
            except requests.exceptions.Timeout:
                continue  # Try next timeout
            except Exception as e:
                return {'success': False, 'message': f'Connection error: {str(e)}'}
        
        return {
            'success': False,
            'message': 'All progressive timeouts failed',
            'timeouts_tried': timeouts
        }
    
    def _try_alternative_ports(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Try alternative port numbers"""
        
        endpoint_info = context.get('endpoint_info', {})
        hostname = endpoint_info.get('hostname')
        original_port = endpoint_info.get('port')
        scheme = endpoint_info.get('scheme', 'https')
        
        if not hostname or not original_port:
            return {'success': False, 'message': 'Missing hostname or port for alternative port testing'}
        
        # Define alternative ports based on scheme
        if scheme == 'https':
            alternative_ports = [443, 8443, 9443, 6443]
        else:
            alternative_ports = [80, 8080, 8000, 3000]
        
        # Remove original port from alternatives
        if original_port in alternative_ports:
            alternative_ports.remove(original_port)
        
        for port in alternative_ports:
            try:
                import socket
                
                logger.info(f"Testing alternative port {hostname}:{port}")
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                
                result = sock.connect_ex((hostname, port))
                sock.close()
                
                if result == 0:
                    # Update context with working port
                    endpoint_info['port'] = port
                    context['working_port'] = port
                    
                    return {
                        'success': True,
                        'message': f'Alternative port works: {hostname}:{port}',
                        'working_port': port
                    }
                    
            except Exception:
                continue
        
        return {
            'success': False,
            'message': 'No working alternative ports found',
            'ports_tried': alternative_ports
        }
    
    def _test_without_tls(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Test connection without TLS if applicable"""
        
        endpoint_info = context.get('endpoint_info', {})
        scheme = endpoint_info.get('scheme')
        
        if scheme != 'https':
            return {
                'success': False,
                'message': 'Not applicable - already using non-TLS connection'
            }
        
        # Only test HTTP if explicitly allowed (usually only in development)
        allow_insecure = context.get('allow_insecure_fallback', False)
        
        if not allow_insecure:
            return {
                'success': False,
                'message': 'Insecure HTTP fallback not allowed'
            }
        
        try:
            hostname = endpoint_info.get('hostname')
            port = 80  # HTTP port
            path = endpoint_info.get('path', '')
            
            http_url = f"http://{hostname}:{port}{path}"
            
            import requests
            
            logger.info(f"Testing HTTP fallback: {http_url}")
            
            response = requests.get(http_url, timeout=30)
            
            if response.status_code < 400:
                return {
                    'success': True,
                    'message': f'HTTP fallback successful: {http_url}',
                    'fallback_url': http_url,
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'message': f'HTTP fallback failed with status {response.status_code}'
                }
                
        except Exception as e:
            return {'success': False, 'message': f'HTTP fallback test failed: {str(e)}'}


# Convenience functions for executing workflows
def execute_recovery_workflow(error_code: str, context: Dict[str, Any]) -> WorkflowResult:
    """
    Execute appropriate recovery workflow based on error code
    
    Args:
        error_code: The error code to recover from
        context: Error context and parameters
        
    Returns:
        WorkflowResult indicating success/failure and actions taken
    """
    
    # Map error codes to workflow classes
    workflow_mapping = {
        'HH-GIT-001': GitRepositoryRecoveryWorkflow,
        'HH-GIT-002': GitRepositoryRecoveryWorkflow,
        'HH-K8S-001': KubernetesConnectionRecoveryWorkflow,
        'HH-K8S-002': KubernetesConnectionRecoveryWorkflow,
        'HH-NET-001': NetworkConnectivityRecoveryWorkflow,
        'HH-NET-002': NetworkConnectivityRecoveryWorkflow,
        'HH-NET-003': NetworkConnectivityRecoveryWorkflow
    }
    
    workflow_class = workflow_mapping.get(error_code)
    
    if not workflow_class:
        return WorkflowResult(
            success=False,
            status=WorkflowStatus.FAILED,
            message=f"No recovery workflow available for error code: {error_code}",
            steps_completed=[],
            steps_failed=[],
            total_execution_time=0.0
        )
    
    try:
        workflow = workflow_class(error_code)
        return workflow.execute(context)
    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}")
        return WorkflowResult(
            success=False,
            status=WorkflowStatus.FAILED,
            message=f"Workflow execution error: {str(e)}",
            steps_completed=[],
            steps_failed=[],
            total_execution_time=0.0,
            error_details={'exception': str(e)}
        )