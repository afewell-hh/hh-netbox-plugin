# Network & Connectivity Error Scenarios

## Overview

This document covers all network and connectivity error scenarios in the NetBox Hedgehog Plugin, including connection timeouts, DNS resolution failures, TLS issues, and service availability problems.

## Network Error Categories

### Error Types
1. **Connection Errors**: Timeouts, refused connections, unreachable hosts
2. **Protocol Errors**: TLS handshake failures, HTTP errors, WebSocket issues
3. **Service Availability Errors**: Temporary unavailability, load balancer issues
4. **Infrastructure Errors**: DNS resolution, proxy configuration, firewall blocks

## Connection Error Scenarios

### Scenario: HH-NET-001 - Connection Timeout

**Description**: Network requests exceed timeout thresholds without receiving response.

**Common Triggers**:
- High network latency between NetBox and target services
- Service overload causing slow responses
- Network congestion or packet loss
- Intermediate proxies or load balancers causing delays

**Error Detection Patterns**:
```python
import requests
import socket
import time
from requests.exceptions import ConnectTimeout, ReadTimeout, Timeout

def detect_connection_timeout(target_url, timeout=30):
    """Detect and classify connection timeout scenarios"""
    
    start_time = time.time()
    
    try:
        response = requests.get(
            target_url,
            timeout=timeout,
            headers={'User-Agent': 'NetBox-Hedgehog-Plugin/1.0'}
        )
        
        return {
            'success': True,
            'response_time': time.time() - start_time,
            'status_code': response.status_code
        }
        
    except ConnectTimeout as e:
        raise NetworkError('HH-NET-001', 'Connection establishment timeout',
                          context={
                              'target_url': target_url,
                              'timeout': timeout,
                              'error_type': 'connect_timeout',
                              'elapsed_time': time.time() - start_time
                          })
                          
    except ReadTimeout as e:
        raise NetworkError('HH-NET-001', 'Read timeout waiting for response',
                          context={
                              'target_url': target_url,
                              'timeout': timeout,
                              'error_type': 'read_timeout',
                              'elapsed_time': time.time() - start_time
                          })
                          
    except Timeout as e:
        raise NetworkError('HH-NET-001', 'Request timeout',
                          context={
                              'target_url': target_url,
                              'timeout': timeout,
                              'error_type': 'general_timeout',
                              'elapsed_time': time.time() - start_time
                          })

def analyze_timeout_characteristics(target_url, timeout_history):
    """Analyze timeout patterns for adaptive recovery"""
    
    if not timeout_history:
        return {'pattern': 'unknown', 'recommended_timeout': 30}
    
    # Calculate statistics
    response_times = [h['response_time'] for h in timeout_history if h.get('success')]
    timeout_events = [h for h in timeout_history if not h.get('success')]
    
    if response_times:
        avg_response = sum(response_times) / len(response_times)
        max_response = max(response_times)
        
        # Determine if timeouts are consistent or intermittent
        if len(timeout_events) > len(response_times) * 0.5:
            # More than 50% timeouts - consistent slow service
            return {
                'pattern': 'consistently_slow',
                'recommended_timeout': max(60, max_response * 2),
                'avg_response_time': avg_response
            }
        else:
            # Intermittent timeouts - possibly network issues
            return {
                'pattern': 'intermittent_slow',
                'recommended_timeout': max(45, max_response * 1.5),
                'avg_response_time': avg_response
            }
    else:
        # No successful responses
        return {
            'pattern': 'consistently_failing',
            'recommended_timeout': 120,  # Try longer timeout
            'failure_rate': 1.0
        }
```

**Automatic Recovery**:
```python
def recover_connection_timeout(target_url, error_context):
    """Multi-strategy timeout recovery"""
    
    timeout = error_context.get('timeout', 30)
    error_type = error_context.get('error_type', 'unknown')
    
    # Progressive timeout strategy
    timeout_strategies = [
        {'timeout': timeout * 2, 'description': 'Double timeout'},
        {'timeout': min(timeout * 4, 300), 'description': 'Quadruple timeout (max 5 min)'},
        {'timeout': 600, 'description': 'Extended timeout (10 min)'}
    ]
    
    for strategy in timeout_strategies:
        try:
            logger.info(f"Retry with {strategy['description']}: {strategy['timeout']}s")
            
            response = requests.get(
                target_url,
                timeout=strategy['timeout'],
                headers={'User-Agent': 'NetBox-Hedgehog-Plugin/1.0-Retry'}
            )
            
            # Success with extended timeout
            return {
                'success': True,
                'recovery_type': 'automatic',
                'strategy': strategy['description'],
                'effective_timeout': strategy['timeout'],
                'message': f'Connection successful with {strategy["timeout"]}s timeout'
            }
            
        except (ConnectTimeout, ReadTimeout, Timeout) as e:
            logger.warning(f"Timeout recovery attempt failed with {strategy['timeout']}s: {e}")
            continue
        except Exception as e:
            # Different error type - stop timeout recovery
            logger.error(f"Non-timeout error during recovery: {e}")
            break
    
    # All timeout strategies failed - try alternative approaches
    alternative_result = attempt_alternative_connection_methods(target_url)
    
    if alternative_result.get('success'):
        return alternative_result
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'all_timeout_strategies_failed',
        'attempted_timeouts': [s['timeout'] for s in timeout_strategies],
        'suggestions': [
            'Check network connectivity to target service',
            'Verify service is operational and not overloaded',
            'Consider using alternative endpoint if available',
            'Check for network infrastructure issues'
        ]
    }

def attempt_alternative_connection_methods(target_url):
    """Try alternative connection approaches"""
    
    from urllib.parse import urlparse
    parsed = urlparse(target_url)
    
    alternatives = []
    
    # Try different ports
    if parsed.port:
        if parsed.port == 443:
            alternatives.append(f"{parsed.scheme}://{parsed.hostname}:8443{parsed.path}")
        elif parsed.port == 80:
            alternatives.append(f"{parsed.scheme}://{parsed.hostname}:8080{parsed.path}")
    else:
        # Try standard alternatives
        if parsed.scheme == 'https':
            alternatives.append(f"https://{parsed.netloc}:8443{parsed.path}")
        else:
            alternatives.append(f"http://{parsed.netloc}:8080{parsed.path}")
    
    # Try IP address if hostname provided
    try:
        ip_address = socket.gethostbyname(parsed.hostname)
        alternatives.append(f"{parsed.scheme}://{ip_address}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}{parsed.path}")
    except socket.gaierror:
        pass
    
    for alternative in alternatives:
        try:
            response = requests.get(alternative, timeout=30)
            
            return {
                'success': True,
                'recovery_type': 'automatic',
                'method': 'alternative_endpoint',
                'original_url': target_url,
                'working_url': alternative,
                'message': f'Connection successful using alternative endpoint: {alternative}'
            }
            
        except Exception as e:
            logger.debug(f"Alternative endpoint {alternative} failed: {e}")
            continue
    
    return {'success': False, 'alternatives_tried': alternatives}
```

### Scenario: HH-NET-002 - Connection Refused

**Description**: Target service actively refuses connection attempts.

**Common Triggers**:
- Service not running or stopped
- Port not open or service not listening
- Firewall blocking connections
- Service temporarily overwhelmed

**Error Detection and Recovery**:
```python
def detect_connection_refused(target_url, error):
    """Detect connection refused scenarios"""
    
    error_message = str(error).lower()
    
    if 'connection refused' in error_message:
        return {
            'error_detected': True,
            'error_code': 'HH-NET-002',
            'error_type': 'connection_refused',
            'likely_causes': [
                'Service not running',
                'Port not open',
                'Firewall blocking connection'
            ]
        }
    
    return {'error_detected': False}

def recover_connection_refused(target_url, error_context):
    """Attempt connection refused recovery"""
    
    from urllib.parse import urlparse
    parsed = urlparse(target_url)
    
    recovery_strategies = [
        {
            'name': 'retry_with_delay',
            'action': lambda: retry_with_exponential_backoff(target_url),
            'description': 'Retry with exponential backoff'
        },
        {
            'name': 'try_alternative_ports',
            'action': lambda: try_alternative_ports(parsed),
            'description': 'Try common alternative ports'
        },
        {
            'name': 'check_service_health',
            'action': lambda: check_service_health_endpoints(parsed),
            'description': 'Check service health endpoints'
        }
    ]
    
    for strategy in recovery_strategies:
        try:
            logger.info(f"Attempting recovery: {strategy['description']}")
            result = strategy['action']()
            
            if result.get('success'):
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'strategy': strategy['name'],
                    'details': result,
                    'message': f'Connection restored via {strategy["description"]}'
                }
                
        except Exception as e:
            logger.warning(f"Recovery strategy {strategy['name']} failed: {e}")
            continue
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'service_appears_down',
        'diagnostic_steps': [
            f'Check if service is running on {parsed.hostname}:{parsed.port}',
            'Verify firewall rules allow connections',
            'Check service logs for errors',
            'Confirm service is listening on expected port'
        ]
    }

def retry_with_exponential_backoff(target_url, max_retries=5):
    """Retry connection with exponential backoff"""
    
    import random
    
    for attempt in range(max_retries):
        try:
            # Wait before retry (exponential backoff with jitter)
            if attempt > 0:
                delay = (2 ** attempt) + random.uniform(0, 1)
                logger.info(f"Waiting {delay:.2f}s before retry {attempt + 1}/{max_retries}")
                time.sleep(delay)
            
            response = requests.get(target_url, timeout=30)
            
            return {
                'success': True,
                'attempts': attempt + 1,
                'response_code': response.status_code
            }
            
        except requests.exceptions.ConnectionError as e:
            if 'connection refused' not in str(e).lower():
                # Different error type
                break
            
            if attempt == max_retries - 1:
                # Last attempt failed
                break
                
            logger.debug(f"Retry attempt {attempt + 1} failed: {e}")
    
    return {'success': False, 'attempts': max_retries}

def try_alternative_ports(parsed_url):
    """Try connecting to alternative ports"""
    
    current_port = parsed_url.port
    scheme = parsed_url.scheme
    
    # Common alternative ports by service
    alternatives = []
    
    if scheme == 'https':
        alternatives = [443, 8443, 9443, 6443]  # Common HTTPS ports
    elif scheme == 'http':
        alternatives = [80, 8080, 8000, 3000]   # Common HTTP ports
    
    # Remove current port from alternatives
    if current_port in alternatives:
        alternatives.remove(current_port)
    
    for port in alternatives:
        try:
            alt_url = f"{scheme}://{parsed_url.hostname}:{port}{parsed_url.path}"
            response = requests.get(alt_url, timeout=10)
            
            return {
                'success': True,
                'working_port': port,
                'working_url': alt_url,
                'original_port': current_port
            }
            
        except Exception as e:
            logger.debug(f"Alternative port {port} failed: {e}")
            continue
    
    return {'success': False, 'ports_tried': alternatives}
```

### Scenario: HH-NET-003 - DNS Resolution Failed

**Description**: Cannot resolve hostname to IP address.

**Common Triggers**:
- Hostname doesn't exist
- DNS server unreachable
- DNS configuration issues
- Network connectivity to DNS servers

**Error Detection and Recovery**:
```python
def detect_dns_resolution_failure(target_url, error):
    """Detect DNS resolution failures"""
    
    error_message = str(error).lower()
    
    dns_error_indicators = [
        'name or service not known',
        'nodename nor servname provided',
        'temporary failure in name resolution',
        'no such host is known'
    ]
    
    if any(indicator in error_message for indicator in dns_error_indicators):
        from urllib.parse import urlparse
        parsed = urlparse(target_url)
        
        return {
            'error_detected': True,
            'error_code': 'HH-NET-003',
            'error_type': 'dns_resolution_failed',
            'hostname': parsed.hostname,
            'error_message': error_message
        }
    
    return {'error_detected': False}

def recover_dns_resolution_failure(target_url, error_context):
    """Attempt DNS resolution recovery"""
    
    hostname = error_context.get('hostname')
    
    if not hostname:
        return {'success': False, 'reason': 'no_hostname_to_resolve'}
    
    recovery_strategies = [
        {
            'name': 'retry_dns_resolution',
            'action': lambda: retry_dns_resolution(hostname),
            'description': 'Retry DNS resolution with different servers'
        },
        {
            'name': 'try_alternative_dns',
            'action': lambda: try_alternative_dns_servers(hostname),
            'description': 'Try alternative DNS servers'
        },
        {
            'name': 'use_ip_if_known',
            'action': lambda: try_known_ip_addresses(hostname),
            'description': 'Use cached IP address if available'
        }
    ]
    
    for strategy in recovery_strategies:
        try:
            logger.info(f"DNS recovery: {strategy['description']}")
            result = strategy['action']()
            
            if result.get('success'):
                # Test connection with resolved IP
                ip_address = result.get('ip_address')
                if test_connection_with_ip(target_url, ip_address):
                    return {
                        'success': True,
                        'recovery_type': 'automatic',
                        'strategy': strategy['name'],
                        'resolved_ip': ip_address,
                        'message': f'DNS resolution recovered: {hostname} -> {ip_address}'
                    }
                    
        except Exception as e:
            logger.warning(f"DNS recovery strategy {strategy['name']} failed: {e}")
            continue
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'dns_resolution_not_recoverable',
        'hostname': hostname,
        'diagnostic_steps': [
            f'Verify hostname exists: nslookup {hostname}',
            'Check DNS server configuration',
            'Try different DNS servers (8.8.8.8, 1.1.1.1)',
            'Check network connectivity to DNS servers'
        ]
    }

def try_alternative_dns_servers(hostname):
    """Try resolving hostname with alternative DNS servers"""
    
    import dns.resolver
    
    # Public DNS servers to try
    dns_servers = [
        '8.8.8.8',      # Google DNS
        '1.1.1.1',      # Cloudflare DNS
        '208.67.222.222', # OpenDNS
        '9.9.9.9'       # Quad9 DNS
    ]
    
    for dns_server in dns_servers:
        try:
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [dns_server]
            
            result = resolver.resolve(hostname, 'A')
            
            if result:
                ip_address = str(result[0])
                return {
                    'success': True,
                    'ip_address': ip_address,
                    'dns_server': dns_server
                }
                
        except Exception as e:
            logger.debug(f"DNS server {dns_server} failed to resolve {hostname}: {e}")
            continue
    
    return {'success': False, 'dns_servers_tried': dns_servers}

def test_connection_with_ip(original_url, ip_address):
    """Test connection using resolved IP address"""
    
    from urllib.parse import urlparse
    parsed = urlparse(original_url)
    
    # Replace hostname with IP address
    ip_url = f"{parsed.scheme}://{ip_address}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}{parsed.path}"
    
    try:
        # Use Host header to maintain virtual host routing
        headers = {
            'Host': parsed.hostname,
            'User-Agent': 'NetBox-Hedgehog-Plugin/1.0'
        }
        
        response = requests.get(ip_url, headers=headers, timeout=30)
        return response.status_code < 400
        
    except Exception as e:
        logger.debug(f"Connection test with IP {ip_address} failed: {e}")
        return False
```

## Protocol Error Scenarios

### Scenario: HH-NET-010 - TLS Handshake Failed

**Description**: SSL/TLS negotiation fails during HTTPS connection establishment.

**Common Triggers**:
- Certificate validation failures
- TLS version mismatches
- Cipher suite incompatibilities
- Certificate chain issues

**Error Detection and Recovery**:
```python
def detect_tls_handshake_failure(target_url, error):
    """Detect TLS handshake failures"""
    
    error_message = str(error).lower()
    
    tls_error_indicators = [
        'ssl handshake failed',
        'certificate verify failed',
        'ssl: certificate_verify_failed',
        'bad handshake',
        'wrong version number'
    ]
    
    if any(indicator in error_message for indicator in tls_error_indicators):
        return {
            'error_detected': True,
            'error_code': 'HH-NET-010',
            'error_type': 'tls_handshake_failed',
            'error_message': error_message,
            'possible_causes': analyze_tls_error_causes(error_message)
        }
    
    return {'error_detected': False}

def recover_tls_handshake_failure(target_url, error_context):
    """Attempt TLS handshake recovery"""
    
    error_message = error_context.get('error_message', '')
    
    recovery_strategies = [
        {
            'name': 'disable_ssl_verification',
            'action': lambda: try_without_ssl_verification(target_url),
            'description': 'Try without SSL certificate verification'
        },
        {
            'name': 'try_different_tls_versions',
            'action': lambda: try_different_tls_versions(target_url),
            'description': 'Try different TLS protocol versions'
        },
        {
            'name': 'use_system_ca_bundle',
            'action': lambda: try_with_system_ca_bundle(target_url),
            'description': 'Use system CA certificate bundle'
        }
    ]
    
    # Only try insecure options in development or if explicitly allowed
    if not should_allow_insecure_connections():
        recovery_strategies = [s for s in recovery_strategies if s['name'] != 'disable_ssl_verification']
    
    for strategy in recovery_strategies:
        try:
            logger.info(f"TLS recovery: {strategy['description']}")
            result = strategy['action']()
            
            if result.get('success'):
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'strategy': strategy['name'],
                    'details': result,
                    'message': f'TLS connection recovered via {strategy["description"]}'
                }
                
        except Exception as e:
            logger.warning(f"TLS recovery strategy {strategy['name']} failed: {e}")
            continue
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'tls_handshake_not_recoverable',
        'diagnostic_steps': generate_tls_diagnostic_steps(target_url, error_message)
    }

def try_different_tls_versions(target_url):
    """Try connecting with different TLS versions"""
    
    import ssl
    import urllib3
    
    # TLS versions to try
    tls_versions = [
        (ssl.PROTOCOL_TLS_CLIENT, 'TLS_CLIENT'),
        (ssl.PROTOCOL_TLSv1_2, 'TLSv1.2'),
        (ssl.PROTOCOL_TLSv1_3, 'TLSv1.3') if hasattr(ssl, 'PROTOCOL_TLSv1_3') else None
    ]
    
    tls_versions = [tv for tv in tls_versions if tv is not None]
    
    for protocol, version_name in tls_versions:
        try:
            session = requests.Session()
            
            # Create custom SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.protocol = protocol
            
            # Create adapter with custom SSL context
            adapter = requests.adapters.HTTPAdapter()
            adapter.init_poolmanager(ssl_context=ssl_context)
            
            session.mount('https://', adapter)
            
            response = session.get(target_url, timeout=30)
            
            return {
                'success': True,
                'tls_version': version_name,
                'response_code': response.status_code
            }
            
        except Exception as e:
            logger.debug(f"TLS version {version_name} failed: {e}")
            continue
    
    return {'success': False, 'tls_versions_tried': [tv[1] for tv in tls_versions]}

def generate_tls_diagnostic_steps(target_url, error_message):
    """Generate TLS diagnostic steps based on error"""
    
    from urllib.parse import urlparse
    parsed = urlparse(target_url)
    hostname = parsed.hostname
    port = parsed.port or 443
    
    base_steps = [
        f'Test TLS connection: openssl s_client -connect {hostname}:{port}',
        f'Check certificate validity: openssl s_client -showcerts -connect {hostname}:{port}',
        'Verify certificate chain and expiration dates'
    ]
    
    if 'certificate verify failed' in error_message.lower():
        base_steps.extend([
            'Check if certificate is self-signed',
            'Verify certificate is issued by trusted CA',
            'Check if intermediate certificates are missing'
        ])
    elif 'wrong version number' in error_message.lower():
        base_steps.extend([
            'Service might not support HTTPS on this port',
            'Try HTTP instead of HTTPS if appropriate',
            'Check if service uses non-standard TLS configuration'
        ])
    
    return base_steps
```

## Service Availability Error Scenarios

### Scenario: HH-NET-020 - Service Unavailable

**Description**: Target service returns 503 Service Unavailable or similar error codes.

**Common Triggers**:
- Service temporarily down for maintenance
- Service overloaded with requests
- Database or dependency failures
- Configuration issues

**Error Detection and Recovery**:
```python
def detect_service_unavailable(response):
    """Detect service unavailability conditions"""
    
    unavailable_indicators = {
        503: 'Service Temporarily Unavailable',
        502: 'Bad Gateway', 
        504: 'Gateway Timeout',
        429: 'Too Many Requests'
    }
    
    if response.status_code in unavailable_indicators:
        retry_after = response.headers.get('Retry-After')
        
        return {
            'error_detected': True,
            'error_code': 'HH-NET-020',
            'status_code': response.status_code,
            'error_type': unavailable_indicators[response.status_code].lower().replace(' ', '_'),
            'retry_after': parse_retry_after_header(retry_after),
            'response_headers': dict(response.headers)
        }
    
    return {'error_detected': False}

def recover_service_unavailable(target_url, error_context):
    """Attempt service unavailability recovery"""
    
    status_code = error_context.get('status_code')
    retry_after = error_context.get('retry_after')
    error_type = error_context.get('error_type')
    
    if error_type == 'too_many_requests':
        # Rate limiting - respect Retry-After header
        return handle_rate_limiting(target_url, retry_after)
    elif status_code in [502, 503, 504]:
        # Service/gateway issues - retry with backoff
        return handle_service_downtime(target_url, retry_after)
    else:
        return {'success': False, 'reason': f'unhandled_status_code: {status_code}'}

def handle_rate_limiting(target_url, retry_after):
    """Handle rate limiting with appropriate delays"""
    
    if retry_after and retry_after <= 300:  # Max 5 minutes wait
        logger.info(f"Rate limited, waiting {retry_after} seconds as requested")
        time.sleep(retry_after + 1)  # Add 1 second buffer
        
        try:
            response = requests.get(target_url, timeout=30)
            
            if response.status_code < 400:
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'method': 'rate_limit_wait',
                    'wait_time': retry_after,
                    'message': f'Request successful after {retry_after}s rate limit wait'
                }
                
        except Exception as e:
            logger.error(f"Request failed after rate limit wait: {e}")
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'rate_limit_exceeded',
        'retry_after': retry_after,
        'suggestions': [
            'Reduce request frequency',
            'Implement request queuing',
            'Contact service provider about rate limits'
        ]
    }

def handle_service_downtime(target_url, retry_after):
    """Handle service downtime with exponential backoff"""
    
    max_retries = 5
    base_delay = retry_after if retry_after and retry_after <= 60 else 10
    
    for attempt in range(max_retries):
        if attempt > 0:
            # Exponential backoff with jitter
            delay = min(base_delay * (2 ** (attempt - 1)), 300)  # Max 5 minutes
            jitter = random.uniform(0, delay * 0.1)  # 10% jitter
            total_delay = delay + jitter
            
            logger.info(f"Service downtime retry {attempt}/{max_retries} after {total_delay:.1f}s")
            time.sleep(total_delay)
        
        try:
            response = requests.get(target_url, timeout=30)
            
            if response.status_code < 400:
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'method': 'service_recovery_wait',
                    'attempts': attempt + 1,
                    'message': f'Service recovered after {attempt + 1} attempts'
                }
            elif response.status_code not in [502, 503, 504]:
                # Different error - stop retrying
                break
                
        except Exception as e:
            logger.debug(f"Service recovery attempt {attempt + 1} failed: {e}")
            continue
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'service_remains_unavailable',
        'attempts': max_retries,
        'suggestions': [
            'Check service status page or announcements',
            'Contact service provider support',
            'Consider using alternative service endpoint if available'
        ]
    }

def parse_retry_after_header(retry_after):
    """Parse Retry-After header value"""
    
    if not retry_after:
        return None
    
    try:
        # Try parsing as seconds
        return int(retry_after)
    except ValueError:
        # Try parsing as HTTP date
        from email.utils import parsedate_to_datetime
        try:
            retry_date = parsedate_to_datetime(retry_after)
            current_time = datetime.now(retry_date.tzinfo)
            delta = retry_date - current_time
            return max(0, int(delta.total_seconds()))
        except:
            return None
```

## Testing Network Error Scenarios

```python
class NetworkErrorTests:
    
    def test_connection_timeout_recovery(self):
        """Test HH-NET-001 timeout recovery"""
        
        with mock.patch('requests.get') as mock_get:
            # First call times out
            mock_get.side_effect = [
                requests.exceptions.ConnectTimeout(),
                # Second call succeeds 
                Mock(status_code=200)
            ]
            
            result = recover_connection_timeout('https://test.example.com', {
                'timeout': 30,
                'error_type': 'connect_timeout'
            })
            
            self.assertTrue(result['success'])
            self.assertEqual(result['strategy'], 'Double timeout')
    
    def test_dns_resolution_recovery(self):
        """Test HH-NET-003 DNS resolution recovery"""
        
        with mock.patch('dns.resolver.Resolver') as mock_resolver:
            mock_result = Mock()
            mock_result.__iter__ = Mock(return_value=iter(['1.2.3.4']))
            mock_resolver.return_value.resolve.return_value = mock_result
            
            result = recover_dns_resolution_failure('https://test.example.com', {
                'hostname': 'test.example.com'
            })
            
            self.assertTrue(result['success'])
            self.assertEqual(result['resolved_ip'], '1.2.3.4')
    
    def test_service_unavailable_recovery(self):
        """Test HH-NET-020 service recovery"""
        
        with mock.patch('requests.get') as mock_get:
            # First response: 503 Service Unavailable
            mock_503 = Mock()
            mock_503.status_code = 503
            mock_503.headers = {'Retry-After': '10'}
            
            # Second response: 200 OK
            mock_200 = Mock()
            mock_200.status_code = 200
            
            mock_get.side_effect = [mock_503, mock_200]
            
            with mock.patch('time.sleep'):  # Speed up test
                result = recover_service_unavailable('https://test.example.com', {
                    'status_code': 503,
                    'retry_after': 10,
                    'error_type': 'service_temporarily_unavailable'
                })
                
                self.assertTrue(result['success'])
                self.assertEqual(result['method'], 'service_recovery_wait')
```

This comprehensive network error scenario documentation provides agents with detailed knowledge for handling all connectivity and protocol-related failures in the NetBox Hedgehog Plugin.