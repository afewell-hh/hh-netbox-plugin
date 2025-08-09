"""
Circuit Breaker Service - External Service Protection

Implements the Circuit Breaker pattern to prevent cascade failures from external services,
providing automatic failure detection, recovery mechanisms, and configurable failure thresholds.

Architecture:
- Circuit Breaker pattern implementation for service protection
- Automatic failure detection and recovery
- Configurable failure thresholds and recovery timeouts
- Health monitoring and metrics collection
- Integration with existing reliability patterns
"""

import logging
import time
import asyncio
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock, RLock
from collections import deque, defaultdict
import statistics

from django.core.cache import cache
from django.conf import settings

from ..application.services.event_service import EventService
from ..domain.interfaces.event_service_interface import EventPriority, EventCategory, RealtimeEvent

logger = logging.getLogger('netbox_hedgehog.circuit_breaker')
performance_logger = logging.getLogger('netbox_hedgehog.performance')

# Circuit Breaker Enums and Data Classes

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"         # Normal operation, requests allowed
    OPEN = "open"             # Failure threshold exceeded, requests blocked
    HALF_OPEN = "half_open"   # Testing recovery, limited requests allowed

class FailureType(Enum):
    """Types of failures that can trigger circuit breaker"""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    SERVICE_ERROR = "service_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""
    failure_threshold: int = 5          # Number of failures to open circuit
    recovery_timeout: int = 60          # Seconds to wait before trying half-open
    success_threshold: int = 3          # Consecutive successes to close circuit
    request_timeout: int = 30           # Default request timeout in seconds
    monitoring_window: int = 300        # Time window for failure rate calculation (seconds)
    max_half_open_requests: int = 3     # Max concurrent requests in half-open state
    failure_rate_threshold: float = 0.5 # Failure rate to trigger circuit opening (0.0-1.0)
    enable_adaptive_timeout: bool = True # Enable adaptive timeout based on response times
    health_check_interval: int = 30     # Seconds between health checks
    metrics_retention: int = 3600       # Seconds to retain metrics

@dataclass
class RequestMetric:
    """Individual request metric for circuit breaker analysis"""
    timestamp: datetime
    duration: float
    success: bool
    failure_type: Optional[FailureType] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'duration': self.duration,
            'success': self.success,
            'failure_type': self.failure_type.value if self.failure_type else None,
            'error_message': self.error_message
        }

@dataclass
class CircuitMetrics:
    """Circuit breaker performance metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    blocked_requests: int = 0
    timeouts: int = 0
    avg_response_time: float = 0.0
    failure_rate: float = 0.0
    state_changes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    uptime_percentage: float = 100.0
    
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

class CircuitBreaker:
    """
    Circuit breaker implementation for protecting external service calls
    """
    
    def __init__(self, service_name: str, config: Optional[CircuitBreakerConfig] = None):
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()
        
        # Circuit state management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.next_attempt_time: Optional[datetime] = None
        self.half_open_requests = 0
        
        # Metrics and monitoring
        self.metrics = CircuitMetrics()
        self.request_history: deque = deque(maxlen=1000)  # Recent request history
        self.response_times: deque = deque(maxlen=100)    # For adaptive timeout
        
        # Thread safety
        self._state_lock = RLock()
        self._metrics_lock = Lock()
        
        # Event publishing
        self.event_service = EventService()
        
        logger.info(f"Circuit breaker initialized for service: {service_name}")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function call through the circuit breaker
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result if successful
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Various exceptions: From the wrapped function
        """
        start_time = time.time()
        
        # Check if request should be blocked
        if not self._can_execute_request():
            self._record_blocked_request()
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open for service: {self.service_name}"
            )
        
        # Track half-open requests
        if self.state == CircuitState.HALF_OPEN:
            with self._state_lock:
                self.half_open_requests += 1
        
        try:
            # Execute the function with timeout
            timeout = self._get_adaptive_timeout()
            
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs), timeout=timeout
                )
            
            # Record successful execution
            duration = time.time() - start_time
            self._record_success(duration)
            
            return result
            
        except asyncio.TimeoutError as e:
            duration = time.time() - start_time
            self._record_failure(duration, FailureType.TIMEOUT, str(e))
            raise CircuitBreakerTimeoutError(
                f"Request timed out after {timeout}s for service: {self.service_name}"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            failure_type = self._classify_failure(e)
            self._record_failure(duration, failure_type, str(e))
            raise
            
        finally:
            # Cleanup half-open request tracking
            if self.state == CircuitState.HALF_OPEN:
                with self._state_lock:
                    self.half_open_requests = max(0, self.half_open_requests - 1)
    
    def get_state(self) -> CircuitState:
        """Get current circuit breaker state"""
        with self._state_lock:
            return self.state
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics"""
        with self._metrics_lock:
            recent_metrics = self._calculate_recent_metrics()
            
            return {
                'service_name': self.service_name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'metrics': {
                    'total_requests': self.metrics.total_requests,
                    'successful_requests': self.metrics.successful_requests,
                    'failed_requests': self.metrics.failed_requests,
                    'blocked_requests': self.metrics.blocked_requests,
                    'success_rate': self.metrics.success_rate(),
                    'failure_rate': self.metrics.failure_rate,
                    'avg_response_time': self.metrics.avg_response_time,
                    'uptime_percentage': self.metrics.uptime_percentage,
                    'state_changes': self.metrics.state_changes
                },
                'recent_metrics': recent_metrics,
                'config': {
                    'failure_threshold': self.config.failure_threshold,
                    'recovery_timeout': self.config.recovery_timeout,
                    'success_threshold': self.config.success_threshold,
                    'failure_rate_threshold': self.config.failure_rate_threshold
                },
                'timestamps': {
                    'last_failure': self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
                    'last_success': self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None,
                    'next_attempt': self.next_attempt_time.isoformat() if self.next_attempt_time else None
                }
            }
    
    def reset(self):
        """Manually reset circuit breaker to closed state"""
        with self._state_lock:
            old_state = self.state
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.next_attempt_time = None
            self.half_open_requests = 0
            
            if old_state != CircuitState.CLOSED:
                self._record_state_change(old_state, CircuitState.CLOSED, "manual_reset")
                
        logger.info(f"Circuit breaker manually reset for service: {self.service_name}")
    
    def force_open(self, reason: str = "manual_override"):
        """Manually force circuit breaker to open state"""
        with self._state_lock:
            old_state = self.state
            self.state = CircuitState.OPEN
            self.next_attempt_time = datetime.now(timezone.utc) + timedelta(seconds=self.config.recovery_timeout)
            
            if old_state != CircuitState.OPEN:
                self._record_state_change(old_state, CircuitState.OPEN, reason)
                
        logger.warning(f"Circuit breaker manually opened for service: {self.service_name}: {reason}")
    
    def is_healthy(self) -> bool:
        """Check if service is considered healthy based on recent metrics"""
        with self._metrics_lock:
            recent_requests = self._get_recent_requests(self.config.monitoring_window)
            
            if len(recent_requests) < 5:  # Not enough data
                return self.state == CircuitState.CLOSED
            
            success_rate = sum(1 for req in recent_requests if req.success) / len(recent_requests)
            return success_rate > (1.0 - self.config.failure_rate_threshold)
    
    # Private helper methods
    
    def _can_execute_request(self) -> bool:
        """Check if request can be executed based on circuit state"""
        with self._state_lock:
            if self.state == CircuitState.CLOSED:
                return True
            elif self.state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if (self.next_attempt_time and 
                    datetime.now(timezone.utc) >= self.next_attempt_time):
                    self._transition_to_half_open()
                    return True
                return False
            elif self.state == CircuitState.HALF_OPEN:
                # Allow limited concurrent requests
                return self.half_open_requests < self.config.max_half_open_requests
            
            return False
    
    def _record_success(self, duration: float):
        """Record successful request execution"""
        current_time = datetime.now(timezone.utc)
        
        # Record request metric
        metric = RequestMetric(
            timestamp=current_time,
            duration=duration,
            success=True
        )
        
        with self._metrics_lock:
            self.request_history.append(metric)
            self.response_times.append(duration)
            
            # Update metrics
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            self.metrics.last_success_time = current_time
            
            # Update average response time
            total_requests = self.metrics.total_requests
            self.metrics.avg_response_time = (
                (self.metrics.avg_response_time * (total_requests - 1) + duration) / total_requests
            )
        
        # Update circuit state
        with self._state_lock:
            self.success_count += 1
            
            if self.state == CircuitState.HALF_OPEN:
                # Check if we should close the circuit
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
    
    def _record_failure(self, duration: float, failure_type: FailureType, error_message: str):
        """Record failed request execution"""
        current_time = datetime.now(timezone.utc)
        
        # Record request metric
        metric = RequestMetric(
            timestamp=current_time,
            duration=duration,
            success=False,
            failure_type=failure_type,
            error_message=error_message
        )
        
        with self._metrics_lock:
            self.request_history.append(metric)
            
            # Update metrics
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.last_failure_time = current_time
            
            if failure_type == FailureType.TIMEOUT:
                self.metrics.timeouts += 1
        
        # Update circuit state
        with self._state_lock:
            self.failure_count += 1
            self.success_count = 0  # Reset success count on failure
            self.last_failure_time = current_time
            
            # Check if we should open the circuit
            should_open = False
            
            if self.state == CircuitState.CLOSED:
                # Check failure threshold
                if self.failure_count >= self.config.failure_threshold:
                    should_open = True
                
                # Check failure rate in monitoring window
                recent_failure_rate = self._calculate_recent_failure_rate()
                if recent_failure_rate > self.config.failure_rate_threshold:
                    should_open = True
                    
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens the circuit
                should_open = True
            
            if should_open:
                self._transition_to_open()
    
    def _record_blocked_request(self):
        """Record request that was blocked by circuit breaker"""
        with self._metrics_lock:
            self.metrics.blocked_requests += 1
            self.metrics.total_requests += 1
    
    def _transition_to_open(self):
        """Transition circuit breaker to open state"""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.next_attempt_time = datetime.now(timezone.utc) + timedelta(seconds=self.config.recovery_timeout)
        
        self._record_state_change(old_state, CircuitState.OPEN, "failure_threshold_exceeded")
        
        logger.warning(f"Circuit breaker opened for service: {self.service_name}")
    
    def _transition_to_half_open(self):
        """Transition circuit breaker to half-open state"""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.failure_count = 0
        self.success_count = 0
        self.half_open_requests = 0
        
        self._record_state_change(old_state, CircuitState.HALF_OPEN, "recovery_timeout_elapsed")
        
        logger.info(f"Circuit breaker transitioned to half-open for service: {self.service_name}")
    
    def _transition_to_closed(self):
        """Transition circuit breaker to closed state"""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.next_attempt_time = None
        
        self._record_state_change(old_state, CircuitState.CLOSED, "recovery_successful")
        
        logger.info(f"Circuit breaker closed for service: {self.service_name}")
    
    def _record_state_change(self, old_state: CircuitState, new_state: CircuitState, reason: str):
        """Record state change for metrics and events"""
        with self._metrics_lock:
            self.metrics.state_changes += 1
        
        # Publish state change event
        asyncio.create_task(self._publish_state_change_event(old_state, new_state, reason))
    
    async def _publish_state_change_event(self, old_state: CircuitState, 
                                        new_state: CircuitState, reason: str):
        """Publish circuit breaker state change event"""
        try:
            event = RealtimeEvent(
                event_id=f"circuit_breaker_{self.service_name}_{int(time.time())}",
                event_type=f"circuit_breaker_state_changed",
                category=EventCategory.SYSTEM,
                priority=EventPriority.HIGH if new_state == CircuitState.OPEN else EventPriority.NORMAL,
                timestamp=datetime.now(timezone.utc),
                fabric_id=None,
                user_id=None,
                data={
                    'service_name': self.service_name,
                    'old_state': old_state.value,
                    'new_state': new_state.value,
                    'reason': reason,
                    'failure_count': self.failure_count,
                    'metrics': {
                        'total_requests': self.metrics.total_requests,
                        'failure_rate': self.metrics.failure_rate,
                        'avg_response_time': self.metrics.avg_response_time
                    }
                },
                metadata={
                    'source': 'circuit_breaker',
                    'service_name': self.service_name
                }
            )
            
            await self.event_service.publish_event(event)
            
        except Exception as e:
            logger.error(f"Failed to publish circuit breaker state change event: {e}")
    
    def _classify_failure(self, exception: Exception) -> FailureType:
        """Classify failure type based on exception"""
        exc_str = str(exception).lower()
        exc_type = type(exception).__name__.lower()
        
        if 'timeout' in exc_str or 'timeout' in exc_type:
            return FailureType.TIMEOUT
        elif 'connection' in exc_str or 'connection' in exc_type:
            return FailureType.CONNECTION_ERROR
        elif 'auth' in exc_str or 'permission' in exc_str:
            return FailureType.AUTHENTICATION_ERROR
        elif 'rate limit' in exc_str or 'rate' in exc_str:
            return FailureType.RATE_LIMIT
        elif any(service_error in exc_str for service_error in ['service', 'server', 'http']):
            return FailureType.SERVICE_ERROR
        else:
            return FailureType.UNKNOWN
    
    def _get_adaptive_timeout(self) -> float:
        """Calculate adaptive timeout based on recent response times"""
        if not self.config.enable_adaptive_timeout or not self.response_times:
            return self.config.request_timeout
        
        # Calculate timeout based on response time percentiles
        response_times_list = list(self.response_times)
        
        try:
            p95 = statistics.quantiles(response_times_list, n=20)[18]  # 95th percentile
            adaptive_timeout = min(p95 * 2, self.config.request_timeout * 2)
            return max(adaptive_timeout, self.config.request_timeout * 0.5)
        except (statistics.StatisticsError, IndexError):
            return self.config.request_timeout
    
    def _calculate_recent_failure_rate(self) -> float:
        """Calculate failure rate in the monitoring window"""
        recent_requests = self._get_recent_requests(self.config.monitoring_window)
        
        if not recent_requests:
            return 0.0
        
        failures = sum(1 for req in recent_requests if not req.success)
        return failures / len(recent_requests)
    
    def _get_recent_requests(self, window_seconds: int) -> List[RequestMetric]:
        """Get requests from the recent time window"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        
        return [
            req for req in self.request_history
            if req.timestamp >= cutoff_time
        ]
    
    def _calculate_recent_metrics(self) -> Dict[str, Any]:
        """Calculate metrics for recent requests"""
        recent_requests = self._get_recent_requests(self.config.monitoring_window)
        
        if not recent_requests:
            return {
                'window_seconds': self.config.monitoring_window,
                'request_count': 0,
                'success_rate': 1.0,
                'failure_rate': 0.0,
                'avg_response_time': 0.0
            }
        
        successes = sum(1 for req in recent_requests if req.success)
        failures = len(recent_requests) - successes
        success_rate = successes / len(recent_requests)
        failure_rate = failures / len(recent_requests)
        
        avg_response_time = statistics.mean(req.duration for req in recent_requests)
        
        return {
            'window_seconds': self.config.monitoring_window,
            'request_count': len(recent_requests),
            'success_rate': success_rate,
            'failure_rate': failure_rate,
            'avg_response_time': avg_response_time,
            'successful_requests': successes,
            'failed_requests': failures
        }

class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers with centralized monitoring
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._breakers_lock = Lock()
        self.event_service = EventService()
        
        logger.info("Circuit Breaker Manager initialized")
    
    def get_circuit_breaker(self, service_name: str, 
                           config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Get or create circuit breaker for a service
        
        Args:
            service_name: Name of the service
            config: Optional configuration for the circuit breaker
            
        Returns:
            CircuitBreaker instance
        """
        with self._breakers_lock:
            if service_name not in self.circuit_breakers:
                self.circuit_breakers[service_name] = CircuitBreaker(service_name, config)
                logger.info(f"Created new circuit breaker for service: {service_name}")
            
            return self.circuit_breakers[service_name]
    
    async def call_with_breaker(self, service_name: str, func: Callable, 
                              *args, config: Optional[CircuitBreakerConfig] = None, 
                              **kwargs) -> Any:
        """
        Execute function call through circuit breaker
        
        Args:
            service_name: Name of the service
            func: Function to execute
            *args: Function arguments
            config: Optional circuit breaker configuration
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        circuit_breaker = self.get_circuit_breaker(service_name, config)
        return await circuit_breaker.call(func, *args, **kwargs)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers"""
        with self._breakers_lock:
            return {
                name: breaker.get_metrics()
                for name, breaker in self.circuit_breakers.items()
            }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary of all services"""
        with self._breakers_lock:
            total_services = len(self.circuit_breakers)
            healthy_services = sum(1 for breaker in self.circuit_breakers.values() if breaker.is_healthy())
            
            states = defaultdict(int)
            for breaker in self.circuit_breakers.values():
                states[breaker.get_state().value] += 1
            
            return {
                'total_services': total_services,
                'healthy_services': healthy_services,
                'unhealthy_services': total_services - healthy_services,
                'health_percentage': (healthy_services / max(1, total_services)) * 100,
                'circuit_states': dict(states),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def reset_all_breakers(self):
        """Reset all circuit breakers"""
        with self._breakers_lock:
            for breaker in self.circuit_breakers.values():
                breaker.reset()
        
        logger.info("All circuit breakers reset")
    
    def reset_breaker(self, service_name: str) -> bool:
        """Reset specific circuit breaker"""
        with self._breakers_lock:
            if service_name in self.circuit_breakers:
                self.circuit_breakers[service_name].reset()
                logger.info(f"Circuit breaker reset for service: {service_name}")
                return True
            return False
    
    async def health_check_all_services(self) -> Dict[str, Dict[str, Any]]:
        """Perform health check on all services with circuit breakers"""
        results = {}
        
        with self._breakers_lock:
            services = list(self.circuit_breakers.keys())
        
        for service_name in services:
            breaker = self.circuit_breakers[service_name]
            
            try:
                # Basic health check - just check if breaker is healthy
                is_healthy = breaker.is_healthy()
                metrics = breaker.get_metrics()
                
                results[service_name] = {
                    'healthy': is_healthy,
                    'state': breaker.get_state().value,
                    'metrics': metrics['metrics'],
                    'recent_metrics': metrics['recent_metrics'],
                    'last_check': datetime.now(timezone.utc).isoformat()
                }
                
            except Exception as e:
                results[service_name] = {
                    'healthy': False,
                    'error': str(e),
                    'last_check': datetime.now(timezone.utc).isoformat()
                }
        
        return results

# Custom exceptions

class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors"""
    pass

class CircuitBreakerOpenError(CircuitBreakerError):
    """Exception raised when circuit breaker is open"""
    pass

class CircuitBreakerTimeoutError(CircuitBreakerError):
    """Exception raised when request times out"""
    pass

# Decorator for easy circuit breaker application

def circuit_breaker(service_name: str, config: Optional[CircuitBreakerConfig] = None):
    """
    Decorator to apply circuit breaker to a function
    
    Args:
        service_name: Name of the service
        config: Optional circuit breaker configuration
        
    Example:
        @circuit_breaker('kubernetes-api')
        async def call_k8s_api():
            # API call implementation
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            manager = get_circuit_breaker_manager()
            return await manager.call_with_breaker(service_name, func, *args, config=config, **kwargs)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator

# Global circuit breaker manager instance
_circuit_breaker_manager = None

def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get global CircuitBreakerManager instance"""
    global _circuit_breaker_manager
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
    return _circuit_breaker_manager

# Utility functions for fabric-specific circuit breakers

def get_kubernetes_circuit_breaker(fabric_id: int) -> CircuitBreaker:
    """Get circuit breaker for Kubernetes service of a specific fabric"""
    service_name = f"kubernetes_fabric_{fabric_id}"
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30,
        success_threshold=2,
        request_timeout=60,
        failure_rate_threshold=0.4
    )
    
    manager = get_circuit_breaker_manager()
    return manager.get_circuit_breaker(service_name, config)

def get_git_circuit_breaker(fabric_id: int) -> CircuitBreaker:
    """Get circuit breaker for Git service of a specific fabric"""
    service_name = f"git_fabric_{fabric_id}"
    config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60,
        success_threshold=3,
        request_timeout=30,
        failure_rate_threshold=0.6
    )
    
    manager = get_circuit_breaker_manager()
    return manager.get_circuit_breaker(service_name, config)

# Integration helper for the integration coordinator
async def protected_kubernetes_call(fabric_id: int, func: Callable, *args, **kwargs) -> Any:
    """
    Execute Kubernetes call with circuit breaker protection
    
    Args:
        fabric_id: ID of the fabric
        func: Kubernetes function to call
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
    """
    circuit_breaker = get_kubernetes_circuit_breaker(fabric_id)
    return await circuit_breaker.call(func, *args, **kwargs)

async def protected_git_call(fabric_id: int, func: Callable, *args, **kwargs) -> Any:
    """
    Execute Git call with circuit breaker protection
    
    Args:
        fabric_id: ID of the fabric
        func: Git function to call
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
    """
    circuit_breaker = get_git_circuit_breaker(fabric_id)
    return await circuit_breaker.call(func, *args, **kwargs)