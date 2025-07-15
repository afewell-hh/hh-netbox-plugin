"""
Health Metrics Collector
Aggregates and processes health metrics for dashboard display
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from threading import Lock

from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
from django.core.cache import cache

from ..models import GitRepository
from ..utils.git_health_monitor import GitHealthMonitor, HealthStatus
from ..utils.credential_manager import CredentialManager
from ..logging.git_operations_logger import git_operations_logger

logger = logging.getLogger('netbox_hedgehog.health_metrics_collector')


@dataclass
class HealthMetric:
    """Individual health metric data point"""
    timestamp: datetime
    repository_id: int
    metric_type: str
    metric_name: str
    value: float
    unit: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'repository_id': self.repository_id,
            'metric_type': self.metric_type,
            'metric_name': self.metric_name,
            'value': self.value,
            'unit': self.unit,
            'metadata': self.metadata
        }


@dataclass
class AggregatedMetrics:
    """Aggregated metrics over a time period"""
    period_start: datetime
    period_end: datetime
    repository_count: int
    metrics: Dict[str, Any]
    health_distribution: Dict[str, int]
    performance_summary: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'repository_count': self.repository_count,
            'metrics': self.metrics,
            'health_distribution': self.health_distribution,
            'performance_summary': self.performance_summary
        }


@dataclass
class TrendData:
    """Trend analysis data"""
    metric_name: str
    trend_direction: str  # 'up', 'down', 'stable'
    trend_percentage: float
    confidence: float
    period_days: int
    data_points: List[Tuple[datetime, float]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'metric_name': self.metric_name,
            'trend_direction': self.trend_direction,
            'trend_percentage': self.trend_percentage,
            'confidence': self.confidence,
            'period_days': self.period_days,
            'data_points': [(dt.isoformat(), value) for dt, value in self.data_points]
        }


class HealthMetricsCollector:
    """Collects and aggregates health metrics for dashboard display"""
    
    # Cache keys
    CACHE_KEY_METRICS = 'hedgehog:health_metrics'
    CACHE_KEY_AGGREGATED = 'hedgehog:aggregated_metrics'
    CACHE_KEY_TRENDS = 'hedgehog:trend_data'
    
    # Metric collection intervals
    COLLECTION_INTERVAL = 300  # 5 minutes
    AGGREGATION_INTERVAL = 3600  # 1 hour
    CLEANUP_INTERVAL = 86400  # 24 hours
    
    # Data retention periods
    RAW_METRICS_RETENTION_HOURS = 48
    AGGREGATED_METRICS_RETENTION_DAYS = 30
    TREND_DATA_RETENTION_DAYS = 90
    
    def __init__(self):
        self.logger = logger
        self._metrics_buffer: Dict[int, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._buffer_lock = Lock()
        self._last_collection = None
        self._last_aggregation = None
    
    def collect_repository_metrics(
        self,
        repository: GitRepository,
        include_health_check: bool = True,
        include_credential_check: bool = True,
        include_performance: bool = True
    ) -> List[HealthMetric]:
        """
        Collect comprehensive metrics for a single repository.
        
        Args:
            repository: GitRepository instance
            include_health_check: Whether to run health check
            include_credential_check: Whether to check credential health
            include_performance: Whether to collect performance metrics
            
        Returns:
            List of HealthMetric instances
        """
        metrics = []
        timestamp = timezone.now()
        
        try:
            # Basic repository metrics
            metrics.extend(self._collect_basic_metrics(repository, timestamp))
            
            # Health check metrics
            if include_health_check:
                metrics.extend(self._collect_health_metrics(repository, timestamp))
            
            # Credential health metrics
            if include_credential_check:
                metrics.extend(self._collect_credential_metrics(repository, timestamp))
            
            # Performance metrics
            if include_performance:
                metrics.extend(self._collect_performance_metrics(repository, timestamp))
            
            # Store metrics in buffer
            with self._buffer_lock:
                self._metrics_buffer[repository.id].extend(metrics)
            
            # Cache recent metrics
            self._cache_repository_metrics(repository.id, metrics)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect metrics for repository {repository.id}: {str(e)}")
            return []
    
    def collect_all_repositories_metrics(
        self,
        user_id: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict[int, List[HealthMetric]]:
        """
        Collect metrics for all repositories.
        
        Args:
            user_id: Optional user ID to filter repositories
            force_refresh: Force refresh even if recently collected
            
        Returns:
            Dictionary mapping repository ID to metrics list
        """
        # Check if we need to collect (avoid too frequent collection)
        if not force_refresh and self._last_collection:
            if timezone.now() - self._last_collection < timedelta(seconds=self.COLLECTION_INTERVAL):
                return self._get_cached_metrics()
        
        all_metrics = {}
        
        try:
            # Get repositories to collect from
            repositories = GitRepository.objects.all()
            if user_id:
                repositories = repositories.filter(created_by_id=user_id)
            
            # Collect metrics for each repository
            for repository in repositories:
                try:
                    metrics = self.collect_repository_metrics(
                        repository,
                        include_health_check=True,
                        include_credential_check=True,
                        include_performance=True
                    )
                    all_metrics[repository.id] = metrics
                    
                except Exception as e:
                    self.logger.warning(
                        f"Failed to collect metrics for repository {repository.id}: {str(e)}"
                    )
                    all_metrics[repository.id] = []
            
            self._last_collection = timezone.now()
            
            # Cache the results
            cache.set(
                f"{self.CACHE_KEY_METRICS}:all",
                all_metrics,
                timeout=self.COLLECTION_INTERVAL
            )
            
            return all_metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect metrics for all repositories: {str(e)}")
            return {}
    
    def aggregate_metrics(
        self,
        period_hours: int = 24,
        granularity: str = 'hour'  # 'hour', 'day'
    ) -> AggregatedMetrics:
        """
        Aggregate metrics over a time period.
        
        Args:
            period_hours: Number of hours to aggregate over
            granularity: Aggregation granularity
            
        Returns:
            AggregatedMetrics instance
        """
        cache_key = f"{self.CACHE_KEY_AGGREGATED}:{period_hours}:{granularity}"
        cached_result = cache.get(cache_key)
        
        if cached_result and not self._should_refresh_aggregation():
            return AggregatedMetrics(**cached_result)
        
        try:
            period_start = timezone.now() - timedelta(hours=period_hours)
            period_end = timezone.now()
            
            # Get all metrics in the period
            all_repository_metrics = self._get_metrics_in_period(period_start, period_end)
            
            # Count repositories
            repository_count = len(all_repository_metrics)
            
            # Aggregate metrics by type
            aggregated_metrics = self._aggregate_metrics_by_type(all_repository_metrics)
            
            # Calculate health distribution
            health_distribution = self._calculate_health_distribution(all_repository_metrics)
            
            # Calculate performance summary
            performance_summary = self._calculate_performance_summary(all_repository_metrics)
            
            result = AggregatedMetrics(
                period_start=period_start,
                period_end=period_end,
                repository_count=repository_count,
                metrics=aggregated_metrics,
                health_distribution=health_distribution,
                performance_summary=performance_summary
            )
            
            # Cache the result
            cache.set(cache_key, result.to_dict(), timeout=self.AGGREGATION_INTERVAL)
            
            self._last_aggregation = timezone.now()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to aggregate metrics: {str(e)}")
            # Return empty aggregation
            return AggregatedMetrics(
                period_start=period_start,
                period_end=timezone.now(),
                repository_count=0,
                metrics={},
                health_distribution={},
                performance_summary={}
            )
    
    def calculate_trends(
        self,
        metric_names: List[str],
        period_days: int = 7
    ) -> List[TrendData]:
        """
        Calculate trends for specified metrics.
        
        Args:
            metric_names: List of metric names to analyze
            period_days: Number of days to analyze
            
        Returns:
            List of TrendData instances
        """
        cache_key = f"{self.CACHE_KEY_TRENDS}:{hash(tuple(metric_names))}:{period_days}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return [TrendData(**trend) for trend in cached_result]
        
        trends = []
        
        try:
            period_start = timezone.now() - timedelta(days=period_days)
            
            for metric_name in metric_names:
                trend_data = self._calculate_metric_trend(metric_name, period_start, period_days)
                if trend_data:
                    trends.append(trend_data)
            
            # Cache the results
            cache.set(
                cache_key,
                [trend.to_dict() for trend in trends],
                timeout=3600  # 1 hour
            )
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Failed to calculate trends: {str(e)}")
            return []
    
    def get_real_time_metrics(
        self,
        repository_id: Optional[int] = None,
        metric_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get real-time metrics for dashboard display.
        
        Args:
            repository_id: Optional repository ID to filter
            metric_types: Optional metric types to include
            
        Returns:
            Dictionary with real-time metrics
        """
        try:
            current_time = timezone.now()
            
            # Get recent metrics (last 5 minutes)
            recent_metrics = self._get_recent_metrics(
                repository_id=repository_id,
                minutes=5
            )
            
            # Filter by metric types if specified
            if metric_types:
                recent_metrics = [
                    m for m in recent_metrics
                    if m.metric_type in metric_types
                ]
            
            # Calculate real-time summaries
            real_time_data = {
                'timestamp': current_time.isoformat(),
                'total_repositories': self._count_active_repositories(),
                'metrics_summary': self._summarize_recent_metrics(recent_metrics),
                'alert_conditions': self._check_alert_conditions(recent_metrics),
                'health_status': self._get_overall_health_status(),
                'performance_indicators': self._get_performance_indicators(recent_metrics)
            }
            
            return real_time_data
            
        except Exception as e:
            self.logger.error(f"Failed to get real-time metrics: {str(e)}")
            return {
                'timestamp': timezone.now().isoformat(),
                'error': 'Failed to collect real-time metrics'
            }
    
    def cleanup_old_metrics(self) -> Dict[str, int]:
        """
        Clean up old metrics data.
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            cleanup_stats = {
                'raw_metrics_cleaned': 0,
                'aggregated_metrics_cleaned': 0,
                'cache_entries_cleared': 0
            }
            
            # Clean up raw metrics buffer
            cutoff_time = timezone.now() - timedelta(hours=self.RAW_METRICS_RETENTION_HOURS)
            
            with self._buffer_lock:
                for repo_id, metrics_deque in self._metrics_buffer.items():
                    original_length = len(metrics_deque)
                    
                    # Remove old metrics
                    while metrics_deque and metrics_deque[0].timestamp < cutoff_time:
                        metrics_deque.popleft()
                        cleanup_stats['raw_metrics_cleaned'] += 1
            
            # Clean up cache entries
            cache_patterns = [
                f"{self.CACHE_KEY_METRICS}:*",
                f"{self.CACHE_KEY_AGGREGATED}:*",
                f"{self.CACHE_KEY_TRENDS}:*"
            ]
            
            # Note: Django cache doesn't support pattern deletion
            # In production, you'd use Redis pattern deletion or implement custom cleanup
            
            return cleanup_stats
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old metrics: {str(e)}")
            return {'error': str(e)}
    
    # Private helper methods
    
    def _collect_basic_metrics(
        self,
        repository: GitRepository,
        timestamp: datetime
    ) -> List[HealthMetric]:
        """Collect basic repository metrics"""
        metrics = []
        
        # Connection status metric
        status_values = {
            'connected': 1.0,
            'failed': 0.0,
            'pending': 0.5,
            'testing': 0.75
        }
        
        metrics.append(HealthMetric(
            timestamp=timestamp,
            repository_id=repository.id,
            metric_type='connection',
            metric_name='connection_status',
            value=status_values.get(repository.connection_status, 0.0),
            unit='boolean',
            metadata={'status': repository.connection_status}
        ))
        
        # Fabric count metric
        metrics.append(HealthMetric(
            timestamp=timestamp,
            repository_id=repository.id,
            metric_type='usage',
            metric_name='fabric_count',
            value=float(repository.fabric_count),
            unit='count',
            metadata={'fabrics': repository.fabric_count}
        ))
        
        # Last validation age
        if repository.last_validated:
            age_hours = (timestamp - repository.last_validated).total_seconds() / 3600
            metrics.append(HealthMetric(
                timestamp=timestamp,
                repository_id=repository.id,
                metric_type='validation',
                metric_name='last_validation_age',
                value=age_hours,
                unit='hours',
                metadata={'last_validated': repository.last_validated.isoformat()}
            ))
        
        return metrics
    
    def _collect_health_metrics(
        self,
        repository: GitRepository,
        timestamp: datetime
    ) -> List[HealthMetric]:
        """Collect health-related metrics"""
        metrics = []
        
        try:
            monitor = GitHealthMonitor(repository)
            health_report = monitor.generate_health_report()
            
            # Overall health score
            health_scores = {
                HealthStatus.HEALTHY: 100.0,
                HealthStatus.DEGRADED: 75.0,
                HealthStatus.UNHEALTHY: 50.0,
                HealthStatus.CRITICAL: 25.0
            }
            
            health_score = health_scores.get(health_report.overall_status, 0.0)
            
            metrics.append(HealthMetric(
                timestamp=timestamp,
                repository_id=repository.id,
                metric_type='health',
                metric_name='health_score',
                value=health_score,
                unit='score',
                metadata={'status': health_report.overall_status}
            ))
            
            # Performance metrics from health report
            if health_report.performance_metrics:
                perf_metrics = health_report.performance_metrics
                
                if 'average_response_time_ms' in perf_metrics:
                    metrics.append(HealthMetric(
                        timestamp=timestamp,
                        repository_id=repository.id,
                        metric_type='performance',
                        metric_name='response_time',
                        value=float(perf_metrics['average_response_time_ms']),
                        unit='milliseconds',
                        metadata=perf_metrics
                    ))
                
                if 'success_rate' in perf_metrics:
                    metrics.append(HealthMetric(
                        timestamp=timestamp,
                        repository_id=repository.id,
                        metric_type='reliability',
                        metric_name='success_rate',
                        value=float(perf_metrics['success_rate']),
                        unit='percentage',
                        metadata=perf_metrics
                    ))
        
        except Exception as e:
            self.logger.warning(f"Failed to collect health metrics for repo {repository.id}: {str(e)}")
        
        return metrics
    
    def _collect_credential_metrics(
        self,
        repository: GitRepository,
        timestamp: datetime
    ) -> List[HealthMetric]:
        """Collect credential-related metrics"""
        metrics = []
        
        try:
            credential_manager = CredentialManager()
            cred_health = credential_manager.get_credential_health(repository)
            
            # Credential age
            metrics.append(HealthMetric(
                timestamp=timestamp,
                repository_id=repository.id,
                metric_type='security',
                metric_name='credential_age',
                value=float(cred_health.age_days),
                unit='days',
                metadata={'rotation_due': cred_health.rotation_due}
            ))
            
            # Credential health score
            metrics.append(HealthMetric(
                timestamp=timestamp,
                repository_id=repository.id,
                metric_type='security',
                metric_name='credential_health_score',
                value=float(cred_health.health_score),
                unit='score',
                metadata={'recommendations': cred_health.recommendations}
            ))
            
        except Exception as e:
            self.logger.warning(f"Failed to collect credential metrics for repo {repository.id}: {str(e)}")
        
        return metrics
    
    def _collect_performance_metrics(
        self,
        repository: GitRepository,
        timestamp: datetime
    ) -> List[HealthMetric]:
        """Collect performance-related metrics"""
        metrics = []
        
        try:
            # Get performance summary from logger
            performance_summary = git_operations_logger.get_performance_summary(
                since=timestamp - timedelta(hours=1)
            )
            
            if performance_summary['total_operations'] > 0:
                # Average response time
                metrics.append(HealthMetric(
                    timestamp=timestamp,
                    repository_id=repository.id,
                    metric_type='performance',
                    metric_name='avg_response_time',
                    value=float(performance_summary['average_response_time_ms']),
                    unit='milliseconds',
                    metadata=performance_summary
                ))
                
                # Operation count
                metrics.append(HealthMetric(
                    timestamp=timestamp,
                    repository_id=repository.id,
                    metric_type='usage',
                    metric_name='operation_count',
                    value=float(performance_summary['total_operations']),
                    unit='count',
                    metadata=performance_summary
                ))
        
        except Exception as e:
            self.logger.warning(f"Failed to collect performance metrics for repo {repository.id}: {str(e)}")
        
        return metrics
    
    def _cache_repository_metrics(
        self,
        repository_id: int,
        metrics: List[HealthMetric]
    ) -> None:
        """Cache metrics for a repository"""
        cache_key = f"{self.CACHE_KEY_METRICS}:repo:{repository_id}"
        cache.set(
            cache_key,
            [metric.to_dict() for metric in metrics],
            timeout=self.COLLECTION_INTERVAL
        )
    
    def _get_cached_metrics(self) -> Dict[int, List[HealthMetric]]:
        """Get cached metrics for all repositories"""
        cached = cache.get(f"{self.CACHE_KEY_METRICS}:all")
        if cached:
            return cached
        return {}
    
    def _should_refresh_aggregation(self) -> bool:
        """Check if aggregation should be refreshed"""
        if not self._last_aggregation:
            return True
        
        return timezone.now() - self._last_aggregation > timedelta(seconds=self.AGGREGATION_INTERVAL)
    
    def _get_metrics_in_period(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[int, List[HealthMetric]]:
        """Get metrics for all repositories in time period"""
        all_metrics = {}
        
        with self._buffer_lock:
            for repo_id, metrics_deque in self._metrics_buffer.items():
                period_metrics = [
                    metric for metric in metrics_deque
                    if start_time <= metric.timestamp <= end_time
                ]
                if period_metrics:
                    all_metrics[repo_id] = period_metrics
        
        return all_metrics
    
    def _aggregate_metrics_by_type(
        self,
        all_repository_metrics: Dict[int, List[HealthMetric]]
    ) -> Dict[str, Any]:
        """Aggregate metrics by type across all repositories"""
        aggregated = defaultdict(lambda: {'sum': 0, 'count': 0, 'avg': 0, 'min': float('inf'), 'max': float('-inf')})
        
        for repo_metrics in all_repository_metrics.values():
            for metric in repo_metrics:
                key = f"{metric.metric_type}.{metric.metric_name}"
                agg = aggregated[key]
                
                agg['sum'] += metric.value
                agg['count'] += 1
                agg['min'] = min(agg['min'], metric.value)
                agg['max'] = max(agg['max'], metric.value)
        
        # Calculate averages
        for key, agg in aggregated.items():
            if agg['count'] > 0:
                agg['avg'] = agg['sum'] / agg['count']
            else:
                agg['min'] = 0
                agg['max'] = 0
        
        return dict(aggregated)
    
    def _calculate_health_distribution(
        self,
        all_repository_metrics: Dict[int, List[HealthMetric]]
    ) -> Dict[str, int]:
        """Calculate health status distribution"""
        distribution = defaultdict(int)
        
        for repo_metrics in all_repository_metrics.values():
            # Get latest health score for each repository
            health_metrics = [
                m for m in repo_metrics
                if m.metric_name == 'health_score'
            ]
            
            if health_metrics:
                latest_health = max(health_metrics, key=lambda x: x.timestamp)
                
                if latest_health.value >= 90:
                    distribution['healthy'] += 1
                elif latest_health.value >= 75:
                    distribution['degraded'] += 1
                elif latest_health.value >= 50:
                    distribution['unhealthy'] += 1
                else:
                    distribution['critical'] += 1
            else:
                distribution['unknown'] += 1
        
        return dict(distribution)
    
    def _calculate_performance_summary(
        self,
        all_repository_metrics: Dict[int, List[HealthMetric]]
    ) -> Dict[str, float]:
        """Calculate performance summary across all repositories"""
        response_times = []
        success_rates = []
        
        for repo_metrics in all_repository_metrics.values():
            for metric in repo_metrics:
                if metric.metric_name == 'response_time':
                    response_times.append(metric.value)
                elif metric.metric_name == 'success_rate':
                    success_rates.append(metric.value)
        
        summary = {}
        
        if response_times:
            summary['avg_response_time'] = sum(response_times) / len(response_times)
            summary['min_response_time'] = min(response_times)
            summary['max_response_time'] = max(response_times)
        
        if success_rates:
            summary['avg_success_rate'] = sum(success_rates) / len(success_rates)
            summary['min_success_rate'] = min(success_rates)
            summary['max_success_rate'] = max(success_rates)
        
        return summary
    
    def _calculate_metric_trend(
        self,
        metric_name: str,
        start_time: datetime,
        period_days: int
    ) -> Optional[TrendData]:
        """Calculate trend for a specific metric"""
        try:
            # Collect data points for the metric
            data_points = []
            
            with self._buffer_lock:
                for repo_metrics in self._metrics_buffer.values():
                    for metric in repo_metrics:
                        if (metric.metric_name == metric_name and 
                            metric.timestamp >= start_time):
                            data_points.append((metric.timestamp, metric.value))
            
            if len(data_points) < 2:
                return None
            
            # Sort by timestamp
            data_points.sort(key=lambda x: x[0])
            
            # Calculate trend
            values = [point[1] for point in data_points]
            if len(values) < 2:
                return None
            
            # Simple linear trend calculation
            first_half = values[:len(values)//2]
            second_half = values[len(values)//2:]
            
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)
            
            if first_avg == 0:
                trend_percentage = 0
            else:
                trend_percentage = ((second_avg - first_avg) / first_avg) * 100
            
            # Determine trend direction
            if abs(trend_percentage) < 5:
                trend_direction = 'stable'
            elif trend_percentage > 0:
                trend_direction = 'up'
            else:
                trend_direction = 'down'
            
            # Calculate confidence (simplified)
            confidence = min(len(data_points) / 10.0, 1.0)
            
            return TrendData(
                metric_name=metric_name,
                trend_direction=trend_direction,
                trend_percentage=abs(trend_percentage),
                confidence=confidence,
                period_days=period_days,
                data_points=data_points[-10:]  # Last 10 points
            )
            
        except Exception as e:
            self.logger.error(f"Failed to calculate trend for {metric_name}: {str(e)}")
            return None
    
    def _get_recent_metrics(
        self,
        repository_id: Optional[int] = None,
        minutes: int = 5
    ) -> List[HealthMetric]:
        """Get metrics from the last N minutes"""
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        recent_metrics = []
        
        with self._buffer_lock:
            if repository_id:
                # Get metrics for specific repository
                if repository_id in self._metrics_buffer:
                    recent_metrics = [
                        metric for metric in self._metrics_buffer[repository_id]
                        if metric.timestamp >= cutoff_time
                    ]
            else:
                # Get metrics for all repositories
                for metrics_deque in self._metrics_buffer.values():
                    recent_metrics.extend([
                        metric for metric in metrics_deque
                        if metric.timestamp >= cutoff_time
                    ])
        
        return recent_metrics
    
    def _count_active_repositories(self) -> int:
        """Count repositories with recent activity"""
        return len(self._metrics_buffer)
    
    def _summarize_recent_metrics(
        self,
        recent_metrics: List[HealthMetric]
    ) -> Dict[str, Any]:
        """Summarize recent metrics"""
        if not recent_metrics:
            return {}
        
        summary = defaultdict(list)
        
        for metric in recent_metrics:
            summary[metric.metric_name].append(metric.value)
        
        # Calculate summaries
        result = {}
        for metric_name, values in summary.items():
            result[metric_name] = {
                'count': len(values),
                'avg': sum(values) / len(values),
                'min': min(values),
                'max': max(values)
            }
        
        return result
    
    def _check_alert_conditions(
        self,
        recent_metrics: List[HealthMetric]
    ) -> List[Dict[str, Any]]:
        """Check for alert conditions in recent metrics"""
        alerts = []
        
        # Group metrics by repository
        repo_metrics = defaultdict(list)
        for metric in recent_metrics:
            repo_metrics[metric.repository_id].append(metric)
        
        for repo_id, metrics in repo_metrics.items():
            # Check for health score alerts
            health_scores = [
                m.value for m in metrics
                if m.metric_name == 'health_score'
            ]
            
            if health_scores and min(health_scores) < 50:
                alerts.append({
                    'repository_id': repo_id,
                    'alert_type': 'health_critical',
                    'severity': 'high',
                    'message': f'Repository health score below 50: {min(health_scores)}'
                })
            
            # Check for response time alerts
            response_times = [
                m.value for m in metrics
                if m.metric_name == 'response_time'
            ]
            
            if response_times and max(response_times) > 10000:  # 10 seconds
                alerts.append({
                    'repository_id': repo_id,
                    'alert_type': 'performance_degraded',
                    'severity': 'medium',
                    'message': f'High response time detected: {max(response_times)}ms'
                })
        
        return alerts
    
    def _get_overall_health_status(self) -> Dict[str, Any]:
        """Get overall health status across all repositories"""
        all_repos = GitRepository.objects.all()
        total_count = all_repos.count()
        
        if total_count == 0:
            return {'status': 'unknown', 'message': 'No repositories configured'}
        
        connected_count = all_repos.filter(connection_status='connected').count()
        failed_count = all_repos.filter(connection_status='failed').count()
        
        connection_rate = (connected_count / total_count) * 100
        
        if connection_rate >= 90:
            status = 'healthy'
            message = f'{connected_count}/{total_count} repositories connected'
        elif connection_rate >= 70:
            status = 'degraded'
            message = f'Some connection issues: {connected_count}/{total_count} connected'
        else:
            status = 'unhealthy'
            message = f'Many connection issues: {connected_count}/{total_count} connected'
        
        return {
            'status': status,
            'message': message,
            'connection_rate': connection_rate,
            'total_repositories': total_count,
            'connected_repositories': connected_count,
            'failed_repositories': failed_count
        }
    
    def _get_performance_indicators(
        self,
        recent_metrics: List[HealthMetric]
    ) -> Dict[str, Any]:
        """Get performance indicators from recent metrics"""
        indicators = {
            'avg_response_time': 0,
            'success_rate': 0,
            'operation_count': 0,
            'status': 'unknown'
        }
        
        # Calculate from recent metrics
        response_times = [
            m.value for m in recent_metrics
            if m.metric_name == 'response_time'
        ]
        
        success_rates = [
            m.value for m in recent_metrics
            if m.metric_name == 'success_rate'
        ]
        
        operation_counts = [
            m.value for m in recent_metrics
            if m.metric_name == 'operation_count'
        ]
        
        if response_times:
            indicators['avg_response_time'] = sum(response_times) / len(response_times)
        
        if success_rates:
            indicators['success_rate'] = sum(success_rates) / len(success_rates)
        
        if operation_counts:
            indicators['operation_count'] = sum(operation_counts)
        
        # Determine status
        if indicators['avg_response_time'] < 2000 and indicators['success_rate'] > 95:
            indicators['status'] = 'excellent'
        elif indicators['avg_response_time'] < 5000 and indicators['success_rate'] > 90:
            indicators['status'] = 'good'
        elif indicators['avg_response_time'] < 10000 and indicators['success_rate'] > 80:
            indicators['status'] = 'fair'
        else:
            indicators['status'] = 'poor'
        
        return indicators


# Global collector instance
health_metrics_collector = HealthMetricsCollector()