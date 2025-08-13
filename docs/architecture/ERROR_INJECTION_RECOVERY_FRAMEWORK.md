# Error Injection & Recovery Testing Framework
## Systematic Fault Tolerance Validation for Kubernetes Sync

### Overview

This framework provides **systematic error injection** and **recovery validation** to ensure the Kubernetes sync system handles **ALL possible failure scenarios** gracefully. Every error condition is tested with **automatic recovery verification** and **state consistency validation**.

---

## 1. ERROR INJECTION ARCHITECTURE

### Multi-Layer Error Injection System

```
┌─────────────────────────────────────────────────────────────┐
│                ERROR INJECTION ARCHITECTURE                 │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Network Failure Simulation                       │
│  Layer 2: Authentication/Authorization Errors              │  
│  Layer 3: Kubernetes API Error Responses                   │
│  Layer 4: Database Connectivity Issues                     │
│  Layer 5: Resource Exhaustion (CPU/Memory/Disk)           │
│  Layer 6: System-Level Failures (Process/Service)         │
│  Layer 7: Timing/Race Condition Failures                  │
└─────────────────────────────────────────────────────────────┘
```

### Error Injection Engine

```python
class ErrorInjectionEngine:
    """
    Master error injection system for systematic fault testing
    """
    
    def __init__(self, k8s_cluster: str, fabric_id: int):
        self.k8s_cluster = k8s_cluster
        self.fabric_id = fabric_id
        self.active_injections = []
        
        # Error injection components
        self.network_injector = NetworkErrorInjector()
        self.auth_injector = AuthenticationErrorInjector()
        self.k8s_api_injector = KubernetesAPIErrorInjector()
        self.database_injector = DatabaseErrorInjector()
        self.resource_injector = ResourceExhaustionInjector()
        self.system_injector = SystemFailureInjector()
        self.timing_injector = TimingErrorInjector()
        
    def inject_error_scenario(self, scenario: ErrorScenario) -> ErrorInjectionResult:
        """
        Inject specific error scenario and monitor system response
        """
        # Record pre-injection state
        initial_state = self.capture_system_state()
        
        # Inject error
        injection_result = self.execute_error_injection(scenario)
        
        # Monitor system response
        recovery_result = self.monitor_recovery_process(scenario)
        
        # Validate final consistency
        final_state = self.capture_system_state()
        consistency_result = self.validate_state_consistency(initial_state, final_state)
        
        return ErrorInjectionResult(
            scenario=scenario,
            injection_result=injection_result,
            recovery_result=recovery_result,
            consistency_result=consistency_result,
            system_resilient=recovery_result.recovered and consistency_result.consistent
        )
```

---

## 2. NETWORK FAILURE SIMULATION

### Network Error Types

| Error Type | Description | Recovery Expected | Max Recovery Time |
|------------|-------------|-------------------|-------------------|
| **Connection Timeout** | K8s API unreachable | Exponential backoff retry | 5 minutes |
| **Connection Reset** | TCP connection dropped | Immediate retry | 30 seconds |
| **DNS Resolution Failure** | Cannot resolve K8s hostname | DNS cache refresh | 2 minutes |
| **SSL/TLS Certificate Error** | Certificate expired/invalid | Admin notification | Manual |
| **Intermittent Connectivity** | Sporadic connection loss | Adaptive retry | 10 minutes |
| **Bandwidth Limitation** | Slow/throttled connection | Timeout adjustment | Variable |

### Network Error Injection

```python
class NetworkErrorInjector:
    """
    Simulates various network failure conditions
    """
    
    def __init__(self):
        self.iptables_rules = []
        self.dns_overrides = {}
        self.ssl_cert_issues = []
        
    def inject_connection_timeout(self, target_host: str, duration_seconds: int) -> NetworkInjectionResult:
        """
        Block all traffic to K8s cluster to simulate connection timeout
        """
        # Use iptables to block traffic (requires root/docker privileges)
        rule = f"OUTPUT -d {target_host} -j DROP"
        
        try:
            # Add iptables rule
            subprocess.run(['iptables', '-A'] + rule.split(), check=True)
            self.iptables_rules.append(rule)
            
            # Wait for specified duration
            time.sleep(duration_seconds)
            
            return NetworkInjectionResult(
                success=True,
                error_type="connection_timeout",
                target=target_host,
                duration=duration_seconds
            )
            
        except subprocess.CalledProcessError as e:
            return NetworkInjectionResult(
                success=False,
                error_type="connection_timeout", 
                error_message=str(e)
            )
        finally:
            # Clean up rule
            self.cleanup_iptables_rule(rule)
    
    def inject_dns_resolution_failure(self, hostname: str, duration_seconds: int) -> NetworkInjectionResult:
        """
        Override DNS resolution to simulate DNS failure
        """
        original_hosts = self.backup_hosts_file()
        
        try:
            # Add invalid DNS entry
            with open('/etc/hosts', 'a') as hosts_file:
                hosts_file.write(f"127.0.0.1 {hostname}\n")
            
            self.dns_overrides[hostname] = "127.0.0.1"
            
            # Wait for specified duration
            time.sleep(duration_seconds)
            
            return NetworkInjectionResult(
                success=True,
                error_type="dns_resolution_failure",
                target=hostname,
                duration=duration_seconds
            )
            
        finally:
            # Restore original hosts file
            self.restore_hosts_file(original_hosts)
            if hostname in self.dns_overrides:
                del self.dns_overrides[hostname]
    
    def inject_ssl_certificate_error(self, target_host: str) -> NetworkInjectionResult:
        """
        Simulate SSL certificate validation failure
        """
        # Mock SSL context to reject certificates
        original_ssl_context = ssl.create_default_context
        
        def mock_ssl_context(*args, **kwargs):
            context = original_ssl_context(*args, **kwargs)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            # Then force verification failure
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True
            context.load_verify_locations()  # Will fail for invalid certs
            return context
        
        try:
            # Patch SSL context
            ssl.create_default_context = mock_ssl_context
            
            return NetworkInjectionResult(
                success=True,
                error_type="ssl_certificate_error",
                target=target_host
            )
            
        finally:
            # Restore original SSL context
            ssl.create_default_context = original_ssl_context
    
    def inject_intermittent_connectivity(self, target_host: str, fail_probability: float, duration_seconds: int) -> NetworkInjectionResult:
        """
        Simulate sporadic connection failures
        """
        # Intermittent blocking with random failures
        import random
        
        start_time = time.time()
        failure_count = 0
        
        while time.time() - start_time < duration_seconds:
            if random.random() < fail_probability:
                # Block connection temporarily
                rule = f"OUTPUT -d {target_host} -j DROP"
                subprocess.run(['iptables', '-A'] + rule.split(), check=True)
                self.iptables_rules.append(rule)
                
                # Block for 5-30 seconds randomly
                block_duration = random.randint(5, 30)
                time.sleep(block_duration)
                
                # Restore connection
                self.cleanup_iptables_rule(rule)
                failure_count += 1
            
            # Wait before next potential failure
            time.sleep(random.randint(1, 10))
        
        return NetworkInjectionResult(
            success=True,
            error_type="intermittent_connectivity",
            target=target_host,
            duration=duration_seconds,
            failure_count=failure_count
        )
```

---

## 3. AUTHENTICATION & AUTHORIZATION ERRORS

### Auth Error Scenarios

| Error Type | Cause | Recovery Action | Expected Result |
|------------|-------|----------------|-----------------|
| **Token Expired** | Service account token expired | Token refresh | Automatic recovery |
| **Invalid Token** | Corrupted/invalid token | Admin notification | Manual fix |
| **Insufficient Permissions** | RBAC restrictions | Permission check | Error state |
| **Token Revoked** | Service account deleted | Admin alert | Manual recreation |
| **Wrong Namespace** | Incorrect namespace config | Config validation | Error state |

### Authentication Error Injection

```python
class AuthenticationErrorInjector:
    """
    Simulates authentication and authorization failures
    """
    
    def inject_expired_token(self, fabric_id: int) -> AuthInjectionResult:
        """
        Simulate expired service account token
        """
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        original_token = fabric.kubernetes_token
        
        # Generate expired token (base64 encoded expired JWT)
        expired_payload = {
            "iss": "kubernetes/serviceaccount",
            "kubernetes.io/serviceaccount/namespace": fabric.kubernetes_namespace,
            "kubernetes.io/serviceaccount/secret.name": "hnp-sync-token",
            "kubernetes.io/serviceaccount/service-account.name": "hnp-sync",
            "sub": "system:serviceaccount:default:hnp-sync",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 7200,  # Issued 2 hours ago
            "nbf": int(time.time()) - 7200   # Not before 2 hours ago
        }
        
        expired_token = self.create_fake_jwt(expired_payload)
        
        try:
            # Replace token with expired one
            fabric.kubernetes_token = expired_token
            fabric.save()
            
            # Trigger sync to test error handling
            sync_result = self.trigger_sync_with_expired_token(fabric_id)
            
            return AuthInjectionResult(
                success=True,
                error_type="expired_token",
                fabric_id=fabric_id,
                sync_result=sync_result,
                expected_error="authentication failed"
            )
            
        finally:
            # Restore original token
            fabric.kubernetes_token = original_token
            fabric.save()
    
    def inject_insufficient_permissions(self, fabric_id: int, restricted_resources: List[str]) -> AuthInjectionResult:
        """
        Simulate RBAC permission restrictions
        """
        # Mock Kubernetes API responses to return 403 Forbidden
        with patch('kubernetes.client.ApiClient.call_api') as mock_api:
            def mock_forbidden_response(*args, **kwargs):
                # Return 403 for restricted resources
                resource_type = self.extract_resource_type_from_api_call(args, kwargs)
                if resource_type in restricted_resources:
                    raise ApiException(
                        status=403,
                        reason="Forbidden",
                        body='{"message": "User cannot list hedgehog.githedgehog.com/v1 fabrics"}'
                    )
                return original_api_call(*args, **kwargs)
            
            original_api_call = mock_api.side_effect
            mock_api.side_effect = mock_forbidden_response
            
            # Trigger sync to test permission handling
            sync_result = self.trigger_sync_with_permission_error(fabric_id)
            
            return AuthInjectionResult(
                success=True,
                error_type="insufficient_permissions",
                fabric_id=fabric_id,
                restricted_resources=restricted_resources,
                sync_result=sync_result,
                expected_error="forbidden"
            )
    
    def inject_token_revocation(self, fabric_id: int) -> AuthInjectionResult:
        """
        Simulate service account deletion/token revocation
        """
        # Mock API to return 401 Unauthorized for all requests
        with patch('kubernetes.client.ApiClient.call_api') as mock_api:
            def mock_unauthorized_response(*args, **kwargs):
                raise ApiException(
                    status=401,
                    reason="Unauthorized", 
                    body='{"message": "Unauthorized"}'
                )
            
            mock_api.side_effect = mock_unauthorized_response
            
            # Trigger sync to test token revocation handling
            sync_result = self.trigger_sync_with_revoked_token(fabric_id)
            
            return AuthInjectionResult(
                success=True,
                error_type="token_revoked",
                fabric_id=fabric_id,
                sync_result=sync_result,
                expected_error="unauthorized"
            )
```

---

## 4. KUBERNETES API ERROR RESPONSES

### K8s API Error Scenarios

| Error Code | Error Type | Description | Recovery Strategy |
|------------|------------|-------------|-------------------|
| **400** | Bad Request | Invalid API request format | Request validation |
| **401** | Unauthorized | Authentication failure | Token refresh |
| **403** | Forbidden | Insufficient permissions | Permission check |
| **404** | Not Found | Resource doesn't exist | Resource creation |
| **409** | Conflict | Resource version conflict | Retry with refresh |
| **422** | Unprocessable Entity | Invalid resource spec | Spec validation |
| **429** | Too Many Requests | Rate limiting | Exponential backoff |
| **500** | Internal Server Error | K8s cluster issue | Wait and retry |
| **503** | Service Unavailable | K8s API unavailable | Circuit breaker |

### K8s API Error Injection

```python
class KubernetesAPIErrorInjector:
    """
    Simulates various Kubernetes API error responses
    """
    
    def inject_api_rate_limiting(self, fabric_id: int, rate_limit_duration: int) -> K8sInjectionResult:
        """
        Simulate rate limiting (429 Too Many Requests)
        """
        with patch('kubernetes.client.ApiClient.call_api') as mock_api:
            call_count = 0
            
            def mock_rate_limited_response(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                
                if call_count <= 3:  # First 3 calls are rate limited
                    raise ApiException(
                        status=429,
                        reason="Too Many Requests",
                        body='{"message": "Rate limit exceeded", "details": {"retryAfterSeconds": 60}}',
                        headers={'Retry-After': '60'}
                    )
                
                # After rate limit, allow normal operation
                return original_api_call(*args, **kwargs)
            
            original_api_call = mock_api.side_effect
            mock_api.side_effect = mock_rate_limited_response
            
            # Trigger sync to test rate limiting handling
            sync_start = time.time()
            sync_result = self.trigger_sync_with_rate_limiting(fabric_id)
            sync_duration = time.time() - sync_start
            
            return K8sInjectionResult(
                success=True,
                error_type="rate_limiting",
                fabric_id=fabric_id,
                api_calls_blocked=3,
                sync_result=sync_result,
                sync_duration=sync_duration,
                expected_behavior="exponential_backoff_retry"
            )
    
    def inject_resource_not_found(self, fabric_id: int, missing_resources: List[str]) -> K8sInjectionResult:
        """
        Simulate missing Kubernetes resources (404 Not Found)
        """
        with patch('kubernetes.client.ApiClient.call_api') as mock_api:
            def mock_not_found_response(*args, **kwargs):
                resource_type = self.extract_resource_type_from_api_call(args, kwargs)
                
                if resource_type in missing_resources:
                    raise ApiException(
                        status=404,
                        reason="Not Found",
                        body=f'{{"message": "{resource_type} not found"}}'
                    )
                
                return original_api_call(*args, **kwargs)
            
            original_api_call = mock_api.side_effect
            mock_api.side_effect = mock_not_found_response
            
            # Trigger sync to test missing resource handling
            sync_result = self.trigger_sync_with_missing_resources(fabric_id)
            
            return K8sInjectionResult(
                success=True,
                error_type="resource_not_found",
                fabric_id=fabric_id,
                missing_resources=missing_resources,
                sync_result=sync_result,
                expected_behavior="graceful_error_handling"
            )
    
    def inject_resource_version_conflict(self, fabric_id: int) -> K8sInjectionResult:
        """
        Simulate resource version conflicts (409 Conflict)
        """
        with patch('kubernetes.client.ApiClient.call_api') as mock_api:
            conflict_count = 0
            
            def mock_conflict_response(*args, **kwargs):
                nonlocal conflict_count
                
                # Only simulate conflict for update operations
                if self.is_update_operation(args, kwargs):
                    conflict_count += 1
                    if conflict_count <= 2:  # First 2 updates conflict
                        raise ApiException(
                            status=409,
                            reason="Conflict",
                            body='{"message": "Operation cannot be fulfilled on resource: the object has been modified"}'
                        )
                
                return original_api_call(*args, **kwargs)
            
            original_api_call = mock_api.side_effect
            mock_api.side_effect = mock_conflict_response
            
            # Trigger sync to test conflict resolution
            sync_result = self.trigger_sync_with_conflicts(fabric_id)
            
            return K8sInjectionResult(
                success=True,
                error_type="resource_version_conflict",
                fabric_id=fabric_id,
                conflict_count=conflict_count,
                sync_result=sync_result,
                expected_behavior="retry_with_refresh"
            )
    
    def inject_server_internal_error(self, fabric_id: int, error_probability: float) -> K8sInjectionResult:
        """
        Simulate intermittent K8s server errors (500 Internal Server Error)
        """
        import random
        
        with patch('kubernetes.client.ApiClient.call_api') as mock_api:
            error_count = 0
            
            def mock_server_error_response(*args, **kwargs):
                nonlocal error_count
                
                if random.random() < error_probability:
                    error_count += 1
                    raise ApiException(
                        status=500,
                        reason="Internal Server Error",
                        body='{"message": "Internal error occurred"}'
                    )
                
                return original_api_call(*args, **kwargs)
            
            original_api_call = mock_api.side_effect
            mock_api.side_effect = mock_server_error_response
            
            # Trigger sync to test server error handling
            sync_result = self.trigger_sync_with_server_errors(fabric_id)
            
            return K8sInjectionResult(
                success=True,
                error_type="server_internal_error",
                fabric_id=fabric_id,
                error_count=error_count,
                error_probability=error_probability,
                sync_result=sync_result,
                expected_behavior="retry_with_backoff"
            )
```

---

## 5. DATABASE CONNECTIVITY ISSUES

### Database Error Types

| Error Type | Scenario | Impact | Recovery Method |
|------------|----------|--------|----------------|
| **Connection Pool Exhausted** | All DB connections in use | Sync blocked | Connection timeout |
| **Database Unavailable** | Database server down | All operations fail | Connection retry |
| **Lock Timeout** | Long-running transaction | Deadlock/timeout | Transaction retry |
| **Disk Full** | Database storage full | Write operations fail | Admin notification |
| **Replication Lag** | Read replica behind | Stale data reads | Read retry |

### Database Error Injection

```python
class DatabaseErrorInjector:
    """
    Simulates database connectivity and consistency issues
    """
    
    def inject_connection_pool_exhaustion(self, fabric_id: int) -> DatabaseInjectionResult:
        """
        Exhaust database connection pool
        """
        # Create many connections to exhaust pool
        connections = []
        
        try:
            # Exhaust connection pool (default is usually 20-100 connections)
            max_connections = settings.DATABASES['default'].get('OPTIONS', {}).get('MAX_CONNS', 20)
            
            for _ in range(max_connections + 10):
                conn = connections.db.connection
                connections.append(conn)
            
            # Trigger sync operation that needs database access
            sync_start = time.time()
            sync_result = self.trigger_sync_with_db_exhaustion(fabric_id)
            sync_duration = time.time() - sync_start
            
            return DatabaseInjectionResult(
                success=True,
                error_type="connection_pool_exhausted",
                fabric_id=fabric_id,
                connections_created=len(connections),
                sync_result=sync_result,
                sync_duration=sync_duration,
                expected_behavior="connection_timeout_and_retry"
            )
            
        finally:
            # Release all connections
            for conn in connections:
                try:
                    conn.close()
                except:
                    pass
    
    def inject_database_lock_timeout(self, fabric_id: int, lock_duration: int) -> DatabaseInjectionResult:
        """
        Create database lock to simulate lock timeout
        """
        from django.db import transaction
        
        # Start long-running transaction to create lock
        def create_long_lock():
            with transaction.atomic():
                # Lock the fabric row for extended period
                fabric = HedgehogFabric.objects.select_for_update().get(id=fabric_id)
                time.sleep(lock_duration)
        
        # Start lock in background thread
        lock_thread = threading.Thread(target=create_long_lock)
        lock_thread.start()
        
        try:
            # Give lock time to establish
            time.sleep(1)
            
            # Trigger sync operation that will hit the lock
            sync_start = time.time()
            sync_result = self.trigger_sync_with_db_lock(fabric_id)
            sync_duration = time.time() - sync_start
            
            return DatabaseInjectionResult(
                success=True,
                error_type="database_lock_timeout",
                fabric_id=fabric_id,
                lock_duration=lock_duration,
                sync_result=sync_result,
                sync_duration=sync_duration,
                expected_behavior="lock_timeout_and_retry"
            )
            
        finally:
            # Ensure lock thread completes
            lock_thread.join(timeout=lock_duration + 10)
    
    def inject_transaction_deadlock(self, fabric_id: int) -> DatabaseInjectionResult:
        """
        Create transaction deadlock scenario
        """
        results = {'thread1': None, 'thread2': None}
        
        def transaction_1():
            try:
                with transaction.atomic():
                    # Lock fabric first, then try to lock related object
                    fabric = HedgehogFabric.objects.select_for_update().get(id=fabric_id)
                    time.sleep(2)  # Hold lock for 2 seconds
                    # Try to lock related object (this will deadlock)
                    related_obj = RelatedModel.objects.select_for_update().first()
                results['thread1'] = 'success'
            except Exception as e:
                results['thread1'] = f'error: {e}'
        
        def transaction_2():
            try:
                with transaction.atomic():
                    # Lock related object first, then try to lock fabric
                    related_obj = RelatedModel.objects.select_for_update().first()
                    time.sleep(2)  # Hold lock for 2 seconds
                    # Try to lock fabric (this will deadlock)
                    fabric = HedgehogFabric.objects.select_for_update().get(id=fabric_id)
                results['thread2'] = 'success'
            except Exception as e:
                results['thread2'] = f'error: {e}'
        
        # Start both transactions simultaneously
        thread1 = threading.Thread(target=transaction_1)
        thread2 = threading.Thread(target=transaction_2)
        
        thread1.start()
        thread2.start()
        
        thread1.join(timeout=10)
        thread2.join(timeout=10)
        
        # One transaction should succeed, one should fail with deadlock
        deadlock_detected = 'error' in results['thread1'] or 'error' in results['thread2']
        
        return DatabaseInjectionResult(
            success=True,
            error_type="transaction_deadlock",
            fabric_id=fabric_id,
            deadlock_detected=deadlock_detected,
            transaction_results=results,
            expected_behavior="deadlock_detection_and_retry"
        )
```

---

## 6. RESOURCE EXHAUSTION SIMULATION

### Resource Exhaustion Types

| Resource | Exhaustion Method | Impact | Recovery |
|----------|------------------|--------|----------|
| **CPU** | CPU-intensive loops | Slow processing | Process throttling |
| **Memory** | Large object allocation | Out of memory | Memory cleanup |
| **Disk** | Large file creation | Disk full errors | Disk cleanup |
| **File Descriptors** | Many open files | Cannot open files | FD cleanup |
| **Network Sockets** | Many connections | Connection refused | Socket cleanup |

### Resource Exhaustion Injection

```python
class ResourceExhaustionInjector:
    """
    Simulates system resource exhaustion scenarios
    """
    
    def inject_memory_exhaustion(self, fabric_id: int, memory_mb: int = 1000) -> ResourceInjectionResult:
        """
        Exhaust available memory
        """
        memory_hogs = []
        
        try:
            # Consume specified amount of memory
            for _ in range(memory_mb):
                memory_hog = bytearray(1024 * 1024)  # 1MB chunk
                memory_hogs.append(memory_hog)
            
            # Monitor memory usage
            import psutil
            process = psutil.Process()
            memory_usage_mb = process.memory_info().rss / 1024 / 1024
            
            # Trigger sync under memory pressure
            sync_start = time.time()
            sync_result = self.trigger_sync_with_memory_pressure(fabric_id)
            sync_duration = time.time() - sync_start
            
            return ResourceInjectionResult(
                success=True,
                error_type="memory_exhaustion",
                fabric_id=fabric_id,
                resource_consumed=memory_usage_mb,
                sync_result=sync_result,
                sync_duration=sync_duration,
                expected_behavior="memory_management_or_failure"
            )
            
        finally:
            # Release memory
            memory_hogs.clear()
    
    def inject_cpu_exhaustion(self, fabric_id: int, duration_seconds: int) -> ResourceInjectionResult:
        """
        Exhaust CPU resources with intensive computation
        """
        import multiprocessing
        
        # Create CPU-intensive processes
        cpu_count = multiprocessing.cpu_count()
        processes = []
        
        def cpu_intensive_task():
            """CPU-intensive computation"""
            end_time = time.time() + duration_seconds
            while time.time() < end_time:
                # Perform computationally expensive operation
                for i in range(100000):
                    result = i ** 2 * i ** 0.5
        
        try:
            # Start CPU-intensive processes on all cores
            for _ in range(cpu_count + 2):  # Oversubscribe CPU
                process = multiprocessing.Process(target=cpu_intensive_task)
                process.start()
                processes.append(process)
            
            # Wait a moment for CPU load to build up
            time.sleep(2)
            
            # Trigger sync under CPU pressure
            sync_start = time.time()
            sync_result = self.trigger_sync_with_cpu_pressure(fabric_id)
            sync_duration = time.time() - sync_start
            
            return ResourceInjectionResult(
                success=True,
                error_type="cpu_exhaustion",
                fabric_id=fabric_id,
                resource_consumed=f"{cpu_count + 2} processes",
                sync_result=sync_result,
                sync_duration=sync_duration,
                expected_behavior="cpu_throttling_or_timeout"
            )
            
        finally:
            # Terminate all CPU-intensive processes
            for process in processes:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=5)
    
    def inject_disk_space_exhaustion(self, fabric_id: int) -> ResourceInjectionResult:
        """
        Fill up available disk space
        """
        import tempfile
        import shutil
        
        temp_files = []
        
        try:
            # Get available disk space
            disk_usage = shutil.disk_usage('/')
            available_gb = disk_usage.free / (1024**3)
            
            # Fill up most of available space (leave 100MB free)
            space_to_fill = max(0, available_gb - 0.1)  # Leave 100MB
            
            # Create large files to consume space
            file_size_mb = 100  # 100MB per file
            file_count = int(space_to_fill * 1024 / file_size_mb)
            
            for i in range(min(file_count, 50)):  # Limit to 50 files for safety
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                temp_file.write(b'0' * (file_size_mb * 1024 * 1024))
                temp_file.close()
                temp_files.append(temp_file.name)
            
            # Check remaining disk space
            updated_usage = shutil.disk_usage('/')
            remaining_mb = updated_usage.free / (1024**2)
            
            # Trigger sync with low disk space
            sync_start = time.time()
            sync_result = self.trigger_sync_with_disk_pressure(fabric_id)
            sync_duration = time.time() - sync_start
            
            return ResourceInjectionResult(
                success=True,
                error_type="disk_space_exhaustion",
                fabric_id=fabric_id,
                resource_consumed=f"{len(temp_files)} files, {remaining_mb:.1f}MB remaining",
                sync_result=sync_result,
                sync_duration=sync_duration,
                expected_behavior="disk_space_error_or_cleanup"
            )
            
        finally:
            # Clean up temporary files
            for temp_file_path in temp_files:
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
```

---

## 7. RECOVERY VALIDATION FRAMEWORK

### Recovery Testing Requirements

Each error injection must validate:
1. **Error Detection**: System recognizes the error
2. **Error Categorization**: Proper error classification
3. **Recovery Strategy**: Appropriate recovery action
4. **Recovery Success**: System returns to healthy state
5. **State Consistency**: No data corruption
6. **Performance Impact**: Recovery doesn't degrade performance

### Recovery Validation Engine

```python
class RecoveryValidationEngine:
    """
    Validates system recovery from all injected errors
    """
    
    def validate_complete_recovery_cycle(self, error_scenario: ErrorScenario) -> RecoveryValidationResult:
        """
        Complete recovery validation for any error scenario
        """
        # Phase 1: Capture initial state
        initial_state = self.capture_comprehensive_state(error_scenario.fabric_id)
        
        # Phase 2: Inject error and monitor immediate response
        injection_result = self.error_engine.inject_error_scenario(error_scenario)
        
        # Phase 3: Monitor recovery process
        recovery_monitoring = self.monitor_recovery_process(error_scenario, timeout=300)  # 5 minutes max
        
        # Phase 4: Validate final state consistency
        final_state = self.capture_comprehensive_state(error_scenario.fabric_id)
        consistency_result = self.validate_state_consistency(initial_state, final_state)
        
        # Phase 5: Performance impact assessment
        performance_impact = self.assess_performance_impact(initial_state, final_state)
        
        return RecoveryValidationResult(
            error_scenario=error_scenario,
            injection_result=injection_result,
            recovery_monitoring=recovery_monitoring,
            consistency_result=consistency_result,
            performance_impact=performance_impact,
            overall_success=self.evaluate_recovery_success(
                injection_result, recovery_monitoring, consistency_result, performance_impact
            )
        )
    
    def monitor_recovery_process(self, error_scenario: ErrorScenario, timeout: int) -> RecoveryMonitoringResult:
        """
        Monitor system recovery from error injection
        """
        fabric_id = error_scenario.fabric_id
        monitoring_start = time.time()
        
        recovery_timeline = []
        current_state = None
        
        while time.time() - monitoring_start < timeout:
            # Check current sync state
            new_state = self.get_fabric_sync_state(fabric_id)
            
            if new_state != current_state:
                recovery_timeline.append({
                    'timestamp': time.time(),
                    'elapsed_seconds': time.time() - monitoring_start,
                    'state': new_state,
                    'previous_state': current_state
                })
                current_state = new_state
            
            # Check if recovery is complete
            if self.is_recovery_complete(new_state, error_scenario):
                recovery_complete_time = time.time() - monitoring_start
                
                return RecoveryMonitoringResult(
                    recovery_successful=True,
                    recovery_time_seconds=recovery_complete_time,
                    final_state=new_state,
                    recovery_timeline=recovery_timeline,
                    error_scenario=error_scenario
                )
            
            time.sleep(5)  # Check every 5 seconds
        
        # Recovery didn't complete within timeout
        return RecoveryMonitoringResult(
            recovery_successful=False,
            recovery_time_seconds=timeout,
            final_state=current_state,
            recovery_timeline=recovery_timeline,
            timeout_exceeded=True,
            error_scenario=error_scenario
        )
    
    def validate_state_consistency(self, initial_state: SystemState, final_state: SystemState) -> ConsistencyResult:
        """
        Validate system state consistency after recovery
        """
        consistency_checks = []
        
        # Check database consistency
        db_consistency = self.check_database_consistency(initial_state.fabric_id)
        consistency_checks.append({
            'check': 'database_consistency',
            'passed': db_consistency.consistent,
            'details': db_consistency.details
        })
        
        # Check configuration consistency
        config_consistency = self.check_configuration_consistency(
            initial_state.fabric_config, final_state.fabric_config
        )
        consistency_checks.append({
            'check': 'configuration_consistency',
            'passed': config_consistency.consistent,
            'details': config_consistency.details
        })
        
        # Check K8s state consistency
        k8s_consistency = self.check_k8s_state_consistency(initial_state.fabric_id)
        consistency_checks.append({
            'check': 'k8s_state_consistency',
            'passed': k8s_consistency.consistent,
            'details': k8s_consistency.details
        })
        
        # Overall consistency assessment
        all_consistent = all(check['passed'] for check in consistency_checks)
        
        return ConsistencyResult(
            overall_consistent=all_consistent,
            consistency_checks=consistency_checks,
            inconsistencies=[check for check in consistency_checks if not check['passed']]
        )
```

---

## 8. COMPREHENSIVE ERROR SCENARIO TESTS

### Master Error Testing Suite

```python
class ComprehensiveErrorTestSuite(TestCase):
    """
    Master test suite covering all error scenarios and recovery validation
    """
    
    def setUp(self):
        """Setup error testing environment"""
        self.error_engine = ErrorInjectionEngine(
            k8s_cluster="https://vlab-art.l.hhdev.io:6443",
            fabric_id=None  # Will be set per test
        )
        self.recovery_validator = RecoveryValidationEngine()
        
    def test_all_network_error_scenarios(self):
        """
        CRITICAL: Test all network failure scenarios and recovery
        """
        fabric = self.create_test_fabric()
        
        network_scenarios = [
            ErrorScenario(
                name="connection_timeout",
                error_type="network",
                fabric_id=fabric.id,
                parameters={"duration": 60, "target_host": "vlab-art.l.hhdev.io"}
            ),
            ErrorScenario(
                name="dns_resolution_failure",
                error_type="network",
                fabric_id=fabric.id,
                parameters={"duration": 120, "hostname": "vlab-art.l.hhdev.io"}
            ),
            ErrorScenario(
                name="ssl_certificate_error",
                error_type="network",
                fabric_id=fabric.id,
                parameters={"target_host": "vlab-art.l.hhdev.io"}
            ),
            ErrorScenario(
                name="intermittent_connectivity",
                error_type="network", 
                fabric_id=fabric.id,
                parameters={"duration": 180, "fail_probability": 0.3}
            )
        ]
        
        for scenario in network_scenarios:
            with self.subTest(scenario=scenario.name):
                # Execute error injection and recovery validation
                result = self.recovery_validator.validate_complete_recovery_cycle(scenario)
                
                # Assert recovery was successful
                self.assertTrue(result.overall_success,
                              f"Recovery failed for {scenario.name}: {result.get_failure_summary()}")
                
                # Assert specific network error recovery requirements
                self.assertLessEqual(result.recovery_monitoring.recovery_time_seconds, 300,
                                   f"Network recovery took too long: {result.recovery_monitoring.recovery_time_seconds}s")
                
                self.assertTrue(result.consistency_result.overall_consistent,
                              f"State inconsistency after {scenario.name} recovery")
    
    def test_all_authentication_error_scenarios(self):
        """
        CRITICAL: Test all authentication/authorization error scenarios
        """
        fabric = self.create_test_fabric()
        
        auth_scenarios = [
            ErrorScenario(
                name="expired_token",
                error_type="authentication",
                fabric_id=fabric.id,
                parameters={}
            ),
            ErrorScenario(
                name="insufficient_permissions",
                error_type="authentication",
                fabric_id=fabric.id,
                parameters={"restricted_resources": ["fabrics", "switches"]}
            ),
            ErrorScenario(
                name="token_revocation",
                error_type="authentication",
                fabric_id=fabric.id,
                parameters={}
            )
        ]
        
        for scenario in auth_scenarios:
            with self.subTest(scenario=scenario.name):
                result = self.recovery_validator.validate_complete_recovery_cycle(scenario)
                
                # Authentication errors may require manual intervention
                if scenario.name in ["token_revocation", "insufficient_permissions"]:
                    # Should transition to error state and stay there
                    self.assertEqual(result.recovery_monitoring.final_state, SyncState.ERROR)
                    self.assertTrue(result.consistency_result.overall_consistent)
                else:
                    # Should recover automatically
                    self.assertTrue(result.overall_success)
    
    def test_all_kubernetes_api_error_scenarios(self):
        """
        CRITICAL: Test all Kubernetes API error scenarios
        """
        fabric = self.create_test_fabric()
        
        k8s_api_scenarios = [
            ErrorScenario(
                name="rate_limiting",
                error_type="k8s_api",
                fabric_id=fabric.id,
                parameters={"rate_limit_duration": 60}
            ),
            ErrorScenario(
                name="resource_not_found",
                error_type="k8s_api", 
                fabric_id=fabric.id,
                parameters={"missing_resources": ["fabrics"]}
            ),
            ErrorScenario(
                name="resource_version_conflict",
                error_type="k8s_api",
                fabric_id=fabric.id,
                parameters={}
            ),
            ErrorScenario(
                name="server_internal_error",
                error_type="k8s_api",
                fabric_id=fabric.id,
                parameters={"error_probability": 0.5}
            )
        ]
        
        for scenario in k8s_api_scenarios:
            with self.subTest(scenario=scenario.name):
                result = self.recovery_validator.validate_complete_recovery_cycle(scenario)
                
                # K8s API errors should recover with retry logic
                self.assertTrue(result.overall_success,
                              f"K8s API recovery failed for {scenario.name}")
                
                # Should implement proper backoff strategies
                if scenario.name == "rate_limiting":
                    self.assertGreaterEqual(result.recovery_monitoring.recovery_time_seconds, 30,
                                          "Rate limiting should enforce backoff delay")
    
    def test_all_database_error_scenarios(self):
        """
        CRITICAL: Test all database error scenarios
        """
        fabric = self.create_test_fabric()
        
        db_scenarios = [
            ErrorScenario(
                name="connection_pool_exhausted",
                error_type="database",
                fabric_id=fabric.id,
                parameters={}
            ),
            ErrorScenario(
                name="database_lock_timeout",
                error_type="database",
                fabric_id=fabric.id,
                parameters={"lock_duration": 30}
            ),
            ErrorScenario(
                name="transaction_deadlock",
                error_type="database",
                fabric_id=fabric.id,
                parameters={}
            )
        ]
        
        for scenario in db_scenarios:
            with self.subTest(scenario=scenario.name):
                result = self.recovery_validator.validate_complete_recovery_cycle(scenario)
                
                # Database errors should recover with connection retry
                self.assertTrue(result.overall_success,
                              f"Database recovery failed for {scenario.name}")
                
                # Database consistency is critical
                self.assertTrue(result.consistency_result.overall_consistent,
                              f"Database inconsistency after {scenario.name}")
    
    def test_all_resource_exhaustion_scenarios(self):
        """
        CRITICAL: Test all resource exhaustion scenarios
        """
        fabric = self.create_test_fabric()
        
        resource_scenarios = [
            ErrorScenario(
                name="memory_exhaustion",
                error_type="resource",
                fabric_id=fabric.id,
                parameters={"memory_mb": 500}
            ),
            ErrorScenario(
                name="cpu_exhaustion", 
                error_type="resource",
                fabric_id=fabric.id,
                parameters={"duration_seconds": 30}
            ),
            ErrorScenario(
                name="disk_space_exhaustion",
                error_type="resource",
                fabric_id=fabric.id,
                parameters={}
            )
        ]
        
        for scenario in resource_scenarios:
            with self.subTest(scenario=scenario.name):
                result = self.recovery_validator.validate_complete_recovery_cycle(scenario)
                
                # Resource exhaustion may cause graceful degradation
                if result.recovery_monitoring.final_state == SyncState.ERROR:
                    # Error state is acceptable for severe resource exhaustion
                    self.assertTrue(result.consistency_result.overall_consistent)
                else:
                    # Should recover once resources are available
                    self.assertTrue(result.overall_success)
```

---

## 9. ERROR RECOVERY METRICS & REQUIREMENTS

### Recovery Performance Targets

| Error Type | Max Recovery Time | Success Rate | Consistency Required |
|------------|------------------|-------------|---------------------|
| **Network Timeout** | 5 minutes | 99% | Yes |
| **DNS Failure** | 2 minutes | 95% | Yes |
| **Auth Token Expired** | 30 seconds | 98% | Yes |
| **Rate Limiting** | 2 minutes | 100% | Yes |
| **Resource Conflicts** | 1 minute | 95% | Critical |
| **Memory Exhaustion** | Variable | 80% | Critical |
| **Database Lock** | 30 seconds | 90% | Critical |

### Recovery Evidence Requirements

Each error test must provide:
1. **Error Injection Evidence**: Proof error was actually injected
2. **System Response Evidence**: Logs showing error detection
3. **Recovery Process Evidence**: Timeline of recovery steps
4. **Final State Evidence**: Proof system returned to healthy state
5. **Consistency Evidence**: Independent verification of data consistency

---

## 10. CONTINUOUS ERROR TESTING PIPELINE

### Automated Error Testing Integration

```yaml
# error-resilience-pipeline.yml
name: Error Resilience Validation

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  push:
    paths:
      - 'netbox_hedgehog/tasks/**'
      - 'netbox_hedgehog/application/services/**'

jobs:
  error-resilience-testing:
    runs-on: ubuntu-latest
    
    steps:
    - name: Setup Error Testing Environment
      run: |
        # Setup isolated test environment with fault injection capabilities
        
    - name: Run Network Error Tests
      run: pytest netbox_hedgehog/tests/error_injection/test_network_errors.py -v --tb=short
      
    - name: Run Authentication Error Tests
      run: pytest netbox_hedgehog/tests/error_injection/test_auth_errors.py -v --tb=short
      
    - name: Run Kubernetes API Error Tests
      run: pytest netbox_hedgehog/tests/error_injection/test_k8s_api_errors.py -v --tb=short
      
    - name: Run Database Error Tests
      run: pytest netbox_hedgehog/tests/error_injection/test_database_errors.py -v --tb=short
      
    - name: Run Resource Exhaustion Tests
      run: pytest netbox_hedgehog/tests/error_injection/test_resource_exhaustion.py -v --tb=short
      
    - name: Generate Recovery Report
      run: python scripts/generate_recovery_report.py
      
    - name: Upload Error Testing Evidence
      uses: actions/upload-artifact@v3
      with:
        name: error-recovery-evidence
        path: error_test_evidence/
```

This error injection and recovery framework ensures **bulletproof fault tolerance** by systematically testing **every possible failure scenario** with **automatic recovery validation** and **state consistency verification**.