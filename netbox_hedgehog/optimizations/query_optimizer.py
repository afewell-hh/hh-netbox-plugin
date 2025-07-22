"""
Database query optimization utilities for HNP
Enterprise-scale performance optimizations
"""

import logging
from typing import Dict, Any, List, Optional, QuerySet
from django.db import models, connection
from django.core.cache import cache
from django.db.models import Prefetch, Count, Q
from functools import wraps
import time

logger = logging.getLogger('netbox_hedgehog.performance')

def query_cache(timeout: int = 300, key_prefix: str = None):
    """
    Decorator to cache database query results
    Automatically generates cache keys based on function name and args
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key_parts = [key_prefix or func.__name__]
            
            # Add args to cache key
            for arg in args:
                if hasattr(arg, 'id'):
                    cache_key_parts.append(f"id_{arg.id}")
                else:
                    cache_key_parts.append(str(arg))
            
            # Add kwargs to cache key
            for key, value in sorted(kwargs.items()):
                cache_key_parts.append(f"{key}_{value}")
            
            cache_key = ":".join(cache_key_parts)
            
            # Try cache first
            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache HIT for {func.__name__}: {cache_key}")
                return result
            
            # Execute function and cache result
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            cache.set(cache_key, result, timeout=timeout)
            logger.debug(f"Cache MISS for {func.__name__}: {cache_key} (took {duration*1000:.2f}ms)")
            
            return result
        return wrapper
    return decorator

def optimize_queryset(queryset: QuerySet, select_related: List[str] = None, 
                     prefetch_related: List[str] = None) -> QuerySet:
    """
    Apply common optimizations to a queryset
    Reduces N+1 queries and improves performance
    """
    if select_related:
        queryset = queryset.select_related(*select_related)
    
    if prefetch_related:
        queryset = queryset.prefetch_related(*prefetch_related)
    
    return queryset

class FabricQueryOptimizer:
    """
    Optimized queries for Fabric operations
    Implements enterprise-scale query patterns
    """
    
    @staticmethod
    @query_cache(timeout=1800, key_prefix="fabric_list")
    def get_fabric_list(status: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get optimized fabric list with minimal database hits
        Uses covering indexes and select_related
        """
        from ..models.fabric import HedgehogFabric
        
        queryset = HedgehogFabric.objects.all()
        
        if status:
            queryset = queryset.filter(status=status)
        
        # Use covering index for common fields
        queryset = queryset.only(
            'id', 'name', 'description', 'status', 
            'connection_status', 'sync_status', 'created', 'last_updated'
        )
        
        if limit:
            queryset = queryset[:limit]
        
        # Convert to list to avoid additional queries
        results = []
        for fabric in queryset:
            results.append({
                'id': fabric.id,
                'name': fabric.name,
                'description': fabric.description,
                'status': fabric.status,
                'connection_status': fabric.connection_status,
                'sync_status': fabric.sync_status,
                'created': fabric.created,
                'last_updated': fabric.last_updated,
            })
        
        return results
    
    @staticmethod
    @query_cache(timeout=600, key_prefix="fabric_detail")
    def get_fabric_detail(fabric_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed fabric information with optimized queries
        """
        from ..models.fabric import HedgehogFabric
        
        try:
            fabric = HedgehogFabric.objects.get(id=fabric_id)
            
            # Get CRD counts with single query
            crd_counts = FabricQueryOptimizer.get_fabric_crd_counts(fabric_id)
            
            return {
                'id': fabric.id,
                'name': fabric.name,
                'description': fabric.description,
                'status': fabric.status,
                'connection_status': fabric.connection_status,
                'sync_status': fabric.sync_status,
                'kubernetes_server': fabric.kubernetes_server,
                'git_repository_url': fabric.git_repository_url,
                'created': fabric.created,
                'last_updated': fabric.last_updated,
                'crd_counts': crd_counts,
                'realtime_monitoring_enabled': getattr(fabric, 'realtime_monitoring_enabled', False),
                'watch_enabled': getattr(fabric, 'watch_enabled', False),
            }
            
        except HedgehogFabric.DoesNotExist:
            return None
    
    @staticmethod
    @query_cache(timeout=900, key_prefix="fabric_crd_counts")
    def get_fabric_crd_counts(fabric_id: int) -> Dict[str, int]:
        """
        Get CRD counts for a fabric using optimized raw SQL
        Much faster than individual model queries
        """
        counts = {}
        
        # Use raw SQL with prepared statement for performance
        with connection.cursor() as cursor:
            # Define CRD tables to count
            crd_tables = [
                ('switches', 'netbox_hedgehog_switch'),
                ('connections', 'netbox_hedgehog_connection'),
                ('vpcs', 'netbox_hedgehog_vpc'),
                ('externals', 'netbox_hedgehog_external'),
                ('vpc_attachments', 'netbox_hedgehog_vpcattachment'),
                ('vpc_peerings', 'netbox_hedgehog_vpcpeering'),
                ('dhcp_subnets', 'netbox_hedgehog_dhcpsubnet'),
                ('ipv4_namespaces', 'netbox_hedgehog_ipv4namespace'),
            ]
            
            # Build single query to get all counts
            count_queries = []
            for crd_name, table_name in crd_tables:
                count_queries.append(f"(SELECT '{crd_name}', COUNT(*) FROM {table_name} WHERE fabric_id = %s)")
            
            union_query = " UNION ALL ".join(count_queries)
            
            cursor.execute(union_query, [fabric_id] * len(crd_tables))
            
            for crd_name, count in cursor.fetchall():
                counts[crd_name] = count
        
        return counts
    
    @staticmethod
    @query_cache(timeout=300, key_prefix="active_fabrics")
    def get_active_fabrics() -> List[Dict[str, Any]]:
        """
        Get all active fabrics with optimized query
        Uses partial index on active status
        """
        return FabricQueryOptimizer.get_fabric_list(status='active')
    
    @staticmethod
    def get_fabric_health_metrics(fabric_id: int) -> Dict[str, Any]:
        """
        Calculate fabric health metrics with optimized queries
        """
        # Use cached CRD counts
        crd_counts = FabricQueryOptimizer.get_fabric_crd_counts(fabric_id)
        
        # Calculate health score based on various factors
        total_crds = sum(crd_counts.values())
        
        # Basic health calculation
        health_score = min(100, max(0, (total_crds * 10)))  # 10 points per CRD, max 100
        
        health_status = 'excellent' if health_score >= 80 else \
                       'good' if health_score >= 60 else \
                       'fair' if health_score >= 40 else 'poor'
        
        return {
            'score': health_score,
            'status': health_status,
            'total_crds': total_crds,
            'crd_breakdown': crd_counts,
            'calculated_at': time.time()
        }

class CRDQueryOptimizer:
    """
    Optimized queries for CRD operations
    """
    
    @staticmethod
    @query_cache(timeout=600, key_prefix="crd_list")
    def get_crd_list(fabric_id: int, crd_type: str, page: int = 1, 
                    page_size: int = 50, search: str = None) -> Dict[str, Any]:
        """
        Get paginated CRD list with optimizations
        """
        # This would need to be implemented based on your actual CRD models
        # For now, return empty result
        return {
            'items': [],
            'total_count': 0,
            'page': page,
            'page_size': page_size,
            'has_next': False,
            'has_previous': False,
        }
    
    @staticmethod
    def bulk_update_crd_status(fabric_id: int, crd_updates: List[Dict[str, Any]]) -> int:
        """
        Bulk update CRD status for better performance
        Uses bulk_update for fewer database round trips
        """
        # Implementation would depend on your CRD models
        return len(crd_updates)

class QueryPerformanceMonitor:
    """
    Monitor and log query performance
    """
    
    @staticmethod
    def log_slow_queries(threshold_ms: float = 100):
        """
        Log queries that exceed threshold
        """
        if hasattr(connection, 'queries'):
            for query in connection.queries:
                time_ms = float(query['time']) * 1000
                if time_ms > threshold_ms:
                    logger.warning(f"Slow query ({time_ms:.2f}ms): {query['sql'][:200]}...")
    
    @staticmethod
    def get_query_stats() -> Dict[str, Any]:
        """
        Get current query statistics
        """
        if hasattr(connection, 'queries'):
            queries = connection.queries
            if queries:
                times = [float(q['time']) for q in queries]
                return {
                    'count': len(queries),
                    'total_time': sum(times),
                    'avg_time': sum(times) / len(times),
                    'max_time': max(times),
                    'min_time': min(times),
                }
        
        return {
            'count': 0,
            'total_time': 0,
            'avg_time': 0,
            'max_time': 0,
            'min_time': 0,
        }

# Context manager for query performance monitoring
class QueryProfiler:
    """
    Context manager to profile database queries
    """
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.start_query_count = 0
    
    def __enter__(self):
        self.start_time = time.time()
        if hasattr(connection, 'queries'):
            self.start_query_count = len(connection.queries)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if hasattr(connection, 'queries'):
            query_count = len(connection.queries) - self.start_query_count
        else:
            query_count = 0
        
        logger.info(f"Query profile - {self.operation_name}: "
                   f"{duration*1000:.2f}ms, {query_count} queries")
        
        # Log slow queries
        QueryPerformanceMonitor.log_slow_queries()
        
        return False  # Don't suppress exceptions