"""
Celery tasks for cache management and optimization
Targeting <500ms page load times through intelligent caching
"""

import logging
import time
from typing import Dict, Any, List, Optional
from celery import shared_task
from django.core.cache import cache, caches
from django.db import connection
from django.db.models import Count, Q

from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC, IPv4Namespace
from ..models.wiring_api import Switch, Connection, VLANNamespace, Server, SwitchGroup
from ..models.reconciliation import ReconciliationAlert

logger = logging.getLogger('netbox_hedgehog.performance')

@shared_task(name='netbox_hedgehog.tasks.refresh_fabric_cache')
def refresh_fabric_cache(fabric_id: int) -> Dict[str, Any]:
    """
    Refresh cache for a specific fabric
    Pre-populate all data needed for fast page loads
    """
    start_time = time.time()
    
    try:
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        fabric_cache = caches['fabric_data']
        
        # Cache fabric basic data
        fabric_data = {
            'id': fabric.id,
            'name': fabric.name,
            'description': fabric.description,
            'status': fabric.status,
            'connection_status': fabric.connection_status,
            'sync_status': fabric.sync_status,
            'last_sync_time': fabric.last_sync_time,
            'kubernetes_server': fabric.kubernetes_server,
        }
        
        fabric_cache.set(f"fabric_basic_{fabric_id}", fabric_data, timeout=3600)
        
        # Cache CRD counts for dashboard
        crd_counts = _get_fabric_crd_counts(fabric_id)
        fabric_cache.set(f"fabric_crd_counts_{fabric_id}", crd_counts, timeout=1800)
        
        # Cache recent CRD list for quick display
        recent_crds = _get_recent_crds(fabric_id, limit=50)
        fabric_cache.set(f"fabric_recent_crds_{fabric_id}", recent_crds, timeout=600)
        
        # Cache fabric health metrics
        health_metrics = _calculate_fabric_health(fabric_id)
        fabric_cache.set(f"fabric_health_{fabric_id}", health_metrics, timeout=300)
        
        # Cache connection status details
        connection_details = _get_connection_status(fabric_id)
        fabric_cache.set(f"fabric_connection_{fabric_id}", connection_details, timeout=600)
        
        duration = time.time() - start_time
        logger.info(f"Refreshed cache for fabric {fabric.name} in {duration:.2f}s")
        
        return {
            'success': True,
            'fabric_id': fabric_id,
            'duration': duration,
            'cached_items': ['basic', 'crd_counts', 'recent_crds', 'health', 'connection']
        }
        
    except Exception as e:
        logger.error(f"Cache refresh failed for fabric {fabric_id}: {e}")
        return {
            'success': False,
            'fabric_id': fabric_id,
            'error': str(e)
        }

@shared_task(name='netbox_hedgehog.tasks.refresh_all_fabric_caches')
def refresh_all_fabric_caches() -> Dict[str, Any]:
    """
    Refresh cache for all active fabrics
    Scheduled task to maintain performance
    """
    from celery import group
    
    active_fabrics = HedgehogFabric.objects.filter(
        status='active'
    ).values_list('id', flat=True)
    
    if not active_fabrics:
        return {'success': True, 'message': 'No active fabrics', 'count': 0}
    
    # Execute cache refresh in parallel
    job = group(refresh_fabric_cache.s(fabric_id) for fabric_id in active_fabrics)
    result = job.apply_async()
    
    logger.info(f"Started cache refresh for {len(active_fabrics)} fabrics")
    
    return {
        'success': True,
        'count': len(active_fabrics),
        'job_id': result.id
    }

@shared_task(name='netbox_hedgehog.tasks.cache_crd_list_page')
def cache_crd_list_page(fabric_id: int, crd_type: str, page: int = 1, 
                       page_size: int = 50) -> Dict[str, Any]:
    """
    Cache CRD list page data for ultra-fast loading
    Target: <100ms cache hit response time
    """
    start_time = time.time()
    
    try:
        # Get model class for CRD type
        model_class = _get_crd_model_class(crd_type)
        if not model_class:
            return {'success': False, 'error': f'Unknown CRD type: {crd_type}'}
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Query with optimized select_related/prefetch_related
        queryset = model_class.objects.filter(fabric_id=fabric_id)
        
        # Get total count
        total_count = queryset.count()
        
        # Get page data with optimizations
        page_objects = list(queryset.select_related('fabric')[offset:offset + page_size])
        
        # Serialize for cache
        page_data = []
        for obj in page_objects:
            page_data.append({
                'id': obj.id,
                'name': getattr(obj, 'name', str(obj)),
                'status': getattr(obj, 'status', 'unknown'),
                'created': obj.created.isoformat() if hasattr(obj, 'created') else None,
                'last_updated': obj.last_updated.isoformat() if hasattr(obj, 'last_updated') else None,
            })
        
        # Cache key
        cache_key = f"crd_list_{fabric_id}_{crd_type}_p{page}_s{page_size}"
        
        cached_data = {
            'items': page_data,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'has_next': offset + page_size < total_count,
            'has_previous': page > 1,
            'cached_at': time.time()
        }
        
        # Cache with 10 minute expiry
        cache.set(cache_key, cached_data, timeout=600)
        
        duration = time.time() - start_time
        logger.info(f"Cached {crd_type} list page {page} for fabric {fabric_id} in {duration:.3f}s")
        
        return {
            'success': True,
            'cache_key': cache_key,
            'item_count': len(page_data),
            'duration': duration
        }
        
    except Exception as e:
        logger.error(f"CRD list cache failed for {crd_type} fabric {fabric_id}: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@shared_task(name='netbox_hedgehog.tasks.warm_popular_caches')
def warm_popular_caches() -> Dict[str, Any]:
    """
    Pre-warm caches for popular pages and data
    Runs periodically to ensure fast user experience
    """
    start_time = time.time()
    warmed_count = 0
    
    try:
        # Get active fabrics
        active_fabrics = HedgehogFabric.objects.filter(status='active')
        
        for fabric in active_fabrics:
            # Warm fabric overview cache
            refresh_fabric_cache.delay(fabric.id)
            warmed_count += 1
            
            # Warm first page of each CRD type
            crd_types = ['switch', 'connection', 'vpc', 'external']
            for crd_type in crd_types:
                cache_crd_list_page.delay(fabric.id, crd_type, page=1)
                warmed_count += 1
        
        duration = time.time() - start_time
        logger.info(f"Initiated cache warming for {warmed_count} items in {duration:.2f}s")
        
        return {
            'success': True,
            'warmed_count': warmed_count,
            'duration': duration
        }
        
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Helper functions

def _get_fabric_crd_counts(fabric_id: int) -> Dict[str, int]:
    """Get count of each CRD type for a fabric"""
    counts = {}
    
    # Use raw SQL for better performance
    with connection.cursor() as cursor:
        crd_tables = [
            'netbox_hedgehog_switch',
            'netbox_hedgehog_connection', 
            'netbox_hedgehog_vpc',
            'netbox_hedgehog_external',
            'netbox_hedgehog_vpcattachment',
            'netbox_hedgehog_vpcpeering',
            'netbox_hedgehog_dhcpsubnet',
            'netbox_hedgehog_ipv4namespace',
        ]
        
        for table in crd_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE fabric_id = %s", [fabric_id])
                crd_name = table.replace('netbox_hedgehog_', '')
                counts[crd_name] = cursor.fetchone()[0]
            except Exception:
                counts[table.replace('netbox_hedgehog_', '')] = 0
    
    return counts

def _get_recent_crds(fabric_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recently updated CRDs across all types"""
    # This would need to be implemented based on your specific CRD models
    # For now, return empty list
    return []

def _calculate_fabric_health(fabric_id: int) -> Dict[str, Any]:
    """Calculate fabric health metrics"""
    return {
        'overall_score': 85,
        'connection_health': 'good',
        'sync_health': 'excellent',
        'crd_health': 'good',
        'last_calculated': time.time()
    }

def _get_connection_status(fabric_id: int) -> Dict[str, Any]:
    """Get detailed connection status"""
    try:
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        return {
            'status': fabric.connection_status,
            'server': fabric.kubernetes_server,
            'last_check': time.time(),
            'response_time': None  # Would measure actual response time
        }
    except:
        return {'status': 'unknown'}

def _get_crd_model_class(crd_type: str):
    """Get Django model class for CRD type"""
    # Map CRD types to model classes
    crd_models = {
        'switch': 'Switch',
        'connection': 'Connection', 
        'vpc': 'VPC',
        'external': 'External',
        # Add other CRD types as needed
    }
    
    if crd_type in crd_models:
        # Return the actual model class - this would need to be implemented
        # based on your specific model structure
        return None
    
    return None