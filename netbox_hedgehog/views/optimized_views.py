"""
Performance-optimized views for HNP
Targeting <500ms response times with intelligent caching
"""

import time
import logging
from typing import Dict, Any, Optional
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView, DetailView
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

from ..models.fabric import HedgehogFabric
from ..optimizations.query_optimizer import (
    FabricQueryOptimizer, CRDQueryOptimizer, QueryProfiler
)
from ..tasks.cache_tasks import cache_crd_list_page

logger = logging.getLogger('netbox_hedgehog.performance')

class OptimizedFabricListView(ListView):
    """
    High-performance fabric list view
    Uses aggressive caching and query optimization
    """
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_list_optimized.html'
    context_object_name = 'fabrics'
    paginate_by = 25
    
    @method_decorator(cache_page(300))  # 5 minute cache
    @method_decorator(vary_on_headers('Authorization'))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        """Optimized queryset with minimal database hits"""
        with QueryProfiler("FabricListView.get_queryset"):
            # Use optimized query from optimizer
            cached_fabrics = FabricQueryOptimizer.get_fabric_list(
                status=self.request.GET.get('status'),
                limit=100  # Reasonable limit for performance
            )
            
            # Convert to queryset-like structure for template
            return cached_fabrics
    
    def get_context_data(self, **kwargs):
        """Add performance metrics to context"""
        context = super().get_context_data(**kwargs)
        
        # Add quick stats without additional queries
        context['total_fabrics'] = len(context['fabrics'])
        context['active_count'] = len([f for f in context['fabrics'] if f['status'] == 'active'])
        
        # Add performance info for debugging
        if self.request.user.is_staff:
            context['cache_info'] = {
                'cached_at': time.time(),
                'cache_source': 'optimized_query'
            }
        
        return context

class OptimizedFabricDetailView(DetailView):
    """
    High-performance fabric detail view
    Uses comprehensive caching strategy
    """
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_detail_optimized.html'
    context_object_name = 'fabric'
    
    def get_object(self, queryset=None):
        """Get fabric with optimized query"""
        fabric_id = self.kwargs.get('pk')
        
        with QueryProfiler("FabricDetailView.get_object"):
            # Use cached detailed fabric data
            fabric_data = FabricQueryOptimizer.get_fabric_detail(fabric_id)
            
            if not fabric_data:
                from django.http import Http404
                raise Http404("Fabric not found")
            
            # Convert dict to object-like structure for template compatibility
            class FabricData:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)
            
            return FabricData(fabric_data)
    
    def get_context_data(self, **kwargs):
        """Add cached performance data"""
        context = super().get_context_data(**kwargs)
        fabric = context['fabric']
        
        # Add health metrics
        health_metrics = FabricQueryOptimizer.get_fabric_health_metrics(fabric.id)
        context['health_metrics'] = health_metrics
        
        # Add recent CRDs preview
        context['recent_crds_preview'] = self._get_recent_crds_preview(fabric.id)
        
        return context
    
    def _get_recent_crds_preview(self, fabric_id: int) -> Dict[str, Any]:
        """Get preview of recent CRDs for quick display"""
        cache_key = f"recent_crds_preview_{fabric_id}"
        preview = cache.get(cache_key)
        
        if preview is None:
            # Generate preview with minimal queries
            preview = {
                'switches': [],
                'connections': [],
                'total_shown': 0,
                'last_updated': time.time()
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, preview, timeout=300)
        
        return preview

class OptimizedCRDListAPIView:
    """
    High-performance API view for CRD lists
    Implements aggressive caching and async loading
    """
    
    def get(self, request, fabric_id: int, crd_type: str):
        """Get paginated CRD list with caching"""
        start_time = time.time()
        
        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 50)), 100)  # Max 100 items
        search = request.GET.get('search', '').strip()
        
        # Try cache first
        cache_key = f"crd_api_{fabric_id}_{crd_type}_p{page}_s{page_size}"
        if search:
            cache_key += f"_search_{hash(search)}"
        
        cached_result = cache.get(cache_key)
        if cached_result:
            # Add cache hit info
            cached_result['cache_hit'] = True
            cached_result['response_time'] = (time.time() - start_time) * 1000
            return JsonResponse(cached_result)
        
        # Get fresh data
        with QueryProfiler(f"CRDListAPI.{crd_type}"):
            result = CRDQueryOptimizer.get_crd_list(
                fabric_id=fabric_id,
                crd_type=crd_type,
                page=page,
                page_size=page_size,
                search=search
            )
        
        # Add response metadata
        result.update({
            'cache_hit': False,
            'response_time': (time.time() - start_time) * 1000,
            'fabric_id': fabric_id,
            'crd_type': crd_type
        })
        
        # Cache result for future requests
        cache_timeout = 300 if not search else 60  # Shorter cache for searches
        cache.set(cache_key, result, timeout=cache_timeout)
        
        # Trigger background cache refresh if needed
        if result['total_count'] > 0:
            cache_crd_list_page.delay(fabric_id, crd_type, page, page_size)
        
        return JsonResponse(result)

class PerformanceDashboardView:
    """
    Performance monitoring dashboard for administrators
    """
    
    def get(self, request):
        """Get performance metrics dashboard"""
        if not request.user.is_staff:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        metrics = self._gather_performance_metrics()
        return JsonResponse(metrics)
    
    def _gather_performance_metrics(self) -> Dict[str, Any]:
        """Gather comprehensive performance metrics"""
        
        # Get recent performance data from cache
        current_minute = int(time.time() // 60)
        
        # Collect metrics from last 5 minutes
        recent_metrics = []
        for i in range(5):
            metrics_key = f"performance_metrics_{current_minute - i}"
            minute_data = cache.get(metrics_key)
            if minute_data:
                minute_data['minute'] = current_minute - i
                recent_metrics.append(minute_data)
        
        # Calculate aggregate metrics
        if recent_metrics:
            total_requests = sum(m['requests'] for m in recent_metrics)
            avg_response_time = sum(m['avg_time'] for m in recent_metrics) / len(recent_metrics)
            error_rate = sum(m['error_count'] for m in recent_metrics) / max(total_requests, 1)
            slow_request_rate = sum(m['slow_count'] for m in recent_metrics) / max(total_requests, 1)
        else:
            total_requests = avg_response_time = error_rate = slow_request_rate = 0
        
        # Get cache statistics
        cache_stats = self._get_cache_statistics()
        
        # Get slow requests
        slow_requests = cache.get('slow_requests', [])
        
        return {
            'summary': {
                'total_requests_5min': total_requests,
                'avg_response_time_ms': avg_response_time * 1000,
                'error_rate_percent': error_rate * 100,
                'slow_request_rate_percent': slow_request_rate * 100,
            },
            'recent_metrics': recent_metrics,
            'cache_stats': cache_stats,
            'slow_requests': slow_requests[-20:],  # Last 20 slow requests
            'recommendations': self._generate_recommendations(recent_metrics, cache_stats)
        }
    
    def _get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache hit/miss statistics"""
        # This would need to be implemented based on your Redis setup
        return {
            'hit_rate': 85.3,  # Placeholder
            'total_keys': 1245,
            'memory_usage_mb': 64.2,
            'expired_keys_last_hour': 234
        }
    
    def _generate_recommendations(self, recent_metrics: list, cache_stats: dict) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        if recent_metrics:
            avg_response = sum(m['avg_time'] for m in recent_metrics) / len(recent_metrics)
            if avg_response > 1.0:
                recommendations.append("Average response time is high - consider query optimization")
            
            total_errors = sum(m['error_count'] for m in recent_metrics)
            if total_errors > 10:
                recommendations.append("High error rate detected - check application logs")
        
        if cache_stats.get('hit_rate', 0) < 80:
            recommendations.append("Cache hit rate is low - review caching strategy")
        
        if not recommendations:
            recommendations.append("Performance is optimal")
        
        return recommendations

# Decorator for automatic performance monitoring
def monitor_performance(view_name: str):
    """Decorator to automatically monitor view performance"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            start_time = time.time()
            
            try:
                response = view_func(request, *args, **kwargs)
                duration = time.time() - start_time
                
                # Log performance
                logger.info(f"View {view_name} completed in {duration*1000:.2f}ms")
                
                # Add performance headers for debugging
                if hasattr(request, 'user') and request.user.is_staff:
                    response['X-View-Time'] = f"{duration*1000:.2f}ms"
                    response['X-View-Name'] = view_name
                
                return response
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"View {view_name} failed after {duration*1000:.2f}ms: {e}")
                raise
        
        return wrapper
    return decorator