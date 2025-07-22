"""
Performance monitoring middleware for HNP
Real-time performance tracking and optimization
"""

import time
import logging
from typing import Dict, Any
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('netbox_hedgehog.performance')

class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to monitor and optimize request performance
    Tracks response times, database queries, and cache hits
    """
    
    def process_request(self, request: HttpRequest) -> None:
        """Start performance tracking for request"""
        request._performance_start = time.time()
        request._performance_data = {
            'start_time': request._performance_start,
            'path': request.path,
            'method': request.method,
            'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
        }
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Complete performance tracking and log metrics"""
        if not hasattr(request, '_performance_start'):
            return response
        
        # Calculate total response time
        end_time = time.time()
        duration = end_time - request._performance_start
        
        # Gather performance metrics
        metrics = self._gather_metrics(request, response, duration)
        
        # Log performance data
        self._log_performance(metrics)
        
        # Check for slow requests
        if duration > 1.0:  # Requests over 1 second
            self._handle_slow_request(metrics)
        
        # Add performance headers for debugging
        if hasattr(request, 'user') and request.user.is_staff:
            response['X-Response-Time'] = f"{duration*1000:.2f}ms"
            response['X-DB-Queries'] = str(metrics.get('db_queries', 0))
            response['X-Cache-Hits'] = str(metrics.get('cache_hits', 0))
        
        return response
    
    def _gather_metrics(self, request: HttpRequest, response: HttpResponse, duration: float) -> Dict[str, Any]:
        """Gather comprehensive performance metrics"""
        from django.db import connection
        
        metrics = {
            'duration': duration,
            'path': request.path,
            'method': request.method,
            'status_code': response.status_code,
            'user_id': request._performance_data.get('user_id'),
            'timestamp': time.time(),
        }
        
        # Database query metrics
        if hasattr(connection, 'queries'):
            metrics['db_queries'] = len(connection.queries)
            metrics['db_time'] = sum(float(q['time']) for q in connection.queries)
        
        # Cache metrics (would need custom cache backend to track hits/misses)
        metrics['cache_hits'] = getattr(request, '_cache_hits', 0)
        metrics['cache_misses'] = getattr(request, '_cache_misses', 0)
        
        # Memory usage (if available)
        try:
            import psutil
            process = psutil.Process()
            metrics['memory_mb'] = process.memory_info().rss / 1024 / 1024
        except ImportError:
            pass
        
        # Response size
        if hasattr(response, 'content'):
            metrics['response_size'] = len(response.content)
        
        return metrics
    
    def _log_performance(self, metrics: Dict[str, Any]) -> None:
        """Log performance metrics"""
        duration_ms = metrics['duration'] * 1000
        
        # Log based on performance thresholds
        if duration_ms > 5000:  # > 5 seconds
            log_level = logging.ERROR
            threshold = "CRITICAL"
        elif duration_ms > 2000:  # > 2 seconds  
            log_level = logging.WARNING
            threshold = "SLOW"
        elif duration_ms > 500:  # > 500ms
            log_level = logging.INFO
            threshold = "MODERATE"
        else:
            log_level = logging.DEBUG
            threshold = "FAST"
        
        logger.log(
            log_level,
            f"{threshold} {metrics['method']} {metrics['path']} - "
            f"{duration_ms:.2f}ms "
            f"[DB: {metrics.get('db_queries', 0)} queries, "
            f"{metrics.get('db_time', 0)*1000:.1f}ms] "
            f"[Cache: {metrics.get('cache_hits', 0)} hits] "
            f"[Status: {metrics['status_code']}]"
        )
        
        # Store metrics for dashboard
        self._store_metrics(metrics)
    
    def _handle_slow_request(self, metrics: Dict[str, Any]) -> None:
        """Handle slow requests with optimization suggestions"""
        duration_ms = metrics['duration'] * 1000
        path = metrics['path']
        
        logger.warning(f"Slow request detected: {path} took {duration_ms:.2f}ms")
        
        # Cache slow request for analysis
        slow_requests_key = "slow_requests"
        slow_requests = cache.get(slow_requests_key, [])
        slow_requests.append({
            'path': path,
            'duration': duration_ms,
            'timestamp': metrics['timestamp'],
            'db_queries': metrics.get('db_queries', 0),
            'method': metrics['method']
        })
        
        # Keep only last 100 slow requests
        if len(slow_requests) > 100:
            slow_requests = slow_requests[-100:]
        
        cache.set(slow_requests_key, slow_requests, timeout=3600)
        
        # Check for optimization opportunities
        self._suggest_optimizations(metrics)
    
    def _suggest_optimizations(self, metrics: Dict[str, Any]) -> None:
        """Suggest optimizations based on metrics"""
        suggestions = []
        
        # Too many database queries
        if metrics.get('db_queries', 0) > 20:
            suggestions.append("Consider using select_related/prefetch_related to reduce DB queries")
        
        # High database time
        if metrics.get('db_time', 0) > 1.0:
            suggestions.append("Database queries are slow - check indexes and query optimization")
        
        # Low cache hit rate
        cache_total = metrics.get('cache_hits', 0) + metrics.get('cache_misses', 0)
        if cache_total > 0 and metrics.get('cache_hits', 0) / cache_total < 0.5:
            suggestions.append("Low cache hit rate - consider caching strategy improvements")
        
        # Large response size
        if metrics.get('response_size', 0) > 1024 * 1024:  # > 1MB
            suggestions.append("Large response size - consider pagination or data optimization")
        
        if suggestions:
            logger.info(f"Optimization suggestions for {metrics['path']}: {'; '.join(suggestions)}")
    
    def _store_metrics(self, metrics: Dict[str, Any]) -> None:
        """Store metrics for performance dashboard"""
        # Store in Redis for real-time monitoring
        metrics_key = f"performance_metrics_{int(time.time() // 60)}"  # Per minute
        
        try:
            # Get existing metrics for this minute
            minute_metrics = cache.get(metrics_key, {
                'requests': 0,
                'total_time': 0,
                'avg_time': 0,
                'max_time': 0,
                'min_time': float('inf'),
                'error_count': 0,
                'slow_count': 0,
                'db_queries': 0,
                'cache_hits': 0,
                'cache_misses': 0,
            })
            
            # Update metrics
            minute_metrics['requests'] += 1
            minute_metrics['total_time'] += metrics['duration']
            minute_metrics['avg_time'] = minute_metrics['total_time'] / minute_metrics['requests']
            minute_metrics['max_time'] = max(minute_metrics['max_time'], metrics['duration'])
            minute_metrics['min_time'] = min(minute_metrics['min_time'], metrics['duration'])
            
            if metrics['status_code'] >= 400:
                minute_metrics['error_count'] += 1
            
            if metrics['duration'] > 2.0:  # > 2 seconds
                minute_metrics['slow_count'] += 1
            
            minute_metrics['db_queries'] += metrics.get('db_queries', 0)
            minute_metrics['cache_hits'] += metrics.get('cache_hits', 0)
            minute_metrics['cache_misses'] += metrics.get('cache_misses', 0)
            
            # Store with 1 hour expiry
            cache.set(metrics_key, minute_metrics, timeout=3600)
            
        except Exception as e:
            logger.error(f"Failed to store performance metrics: {e}")


class CacheOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware to optimize caching for specific HNP views
    Implements intelligent caching strategies
    """
    
    # Views that benefit from aggressive caching
    CACHEABLE_VIEWS = {
        '/hedgehog/fabrics/': 3600,  # 1 hour
        '/hedgehog/fabric/': 1800,   # 30 minutes  
        '/hedgehog/crds/': 600,      # 10 minutes
    }
    
    def process_request(self, request: HttpRequest) -> HttpResponse:
        """Check for cached responses"""
        if request.method != 'GET':
            return None
        
        # Check if this view should be cached
        cache_timeout = self._get_cache_timeout(request.path)
        if not cache_timeout:
            return None
        
        # Generate cache key
        cache_key = self._generate_cache_key(request)
        
        # Try to get cached response
        cached_response = cache.get(cache_key)
        if cached_response:
            # Track cache hit
            request._cache_hits = getattr(request, '_cache_hits', 0) + 1
            logger.debug(f"Cache HIT for {request.path}")
            return cached_response
        
        # Track cache miss
        request._cache_misses = getattr(request, '_cache_misses', 0) + 1
        request._cache_key = cache_key
        request._cache_timeout = cache_timeout
        
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Cache successful responses"""
        if (hasattr(request, '_cache_key') and 
            response.status_code == 200 and 
            request.method == 'GET'):
            
            # Cache the response
            cache.set(
                request._cache_key, 
                response, 
                timeout=request._cache_timeout
            )
            logger.debug(f"Cached response for {request.path}")
        
        return response
    
    def _get_cache_timeout(self, path: str) -> int:
        """Get cache timeout for a path"""
        for pattern, timeout in self.CACHEABLE_VIEWS.items():
            if path.startswith(pattern):
                return timeout
        return 0
    
    def _generate_cache_key(self, request: HttpRequest) -> str:
        """Generate cache key for request"""
        key_parts = [
            'view_cache',
            request.path,
            request.GET.urlencode(),
        ]
        
        # Include user ID for personalized content
        if hasattr(request, 'user') and request.user.is_authenticated:
            key_parts.append(f"user_{request.user.id}")
        
        return ":".join(key_parts)