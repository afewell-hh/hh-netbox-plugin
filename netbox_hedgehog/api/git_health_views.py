"""
Git Repository Health Monitoring API Views
Provides comprehensive health monitoring endpoints for dashboard integration
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, Avg
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import GitRepository
# from ..utils.git_health_monitor import GitHealthMonitor, HealthStatus  # Temporarily disabled
from ..utils.credential_manager import CredentialManager
from ..utils.git_error_handler import GitErrorHandler, handle_git_error
from ..logging.git_operations_logger import (
    git_operations_logger,
    OperationType,
    create_git_log_context
)


class GitHealthSummaryView(APIView):
    """
    GET /api/plugins/hedgehog/git-repositories/health-summary/
    
    Provides overall health summary for all git repositories
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get health summary for all repositories"""
        try:
            context = create_git_log_context(user=request.user)
            
            with git_operations_logger.operation_context(
                OperationType.HEALTH_CHECK,
                context,
                operation='health_summary'
            ):
                # Get all repositories accessible to user
                repositories = GitRepository.objects.filter(
                    created_by=request.user
                )
                
                # Collect health metrics
                summary = {
                    'total_repositories': repositories.count(),
                    'health_distribution': {
                        'healthy': 0,
                        'degraded': 0,
                        'unhealthy': 0,
                        'critical': 0,
                        'unknown': 0
                    },
                    'connection_status': {
                        'connected': repositories.filter(connection_status='connected').count(),
                        'failed': repositories.filter(connection_status='failed').count(),
                        'pending': repositories.filter(connection_status='pending').count(),
                        'testing': repositories.filter(connection_status='testing').count()
                    },
                    'credential_health': {
                        'rotation_due': 0,
                        'rotation_overdue': 0,
                        'healthy': 0
                    },
                    'performance_metrics': {
                        'average_response_time': 0,
                        'success_rate': 0,
                        'error_rate': 0
                    },
                    'last_updated': timezone.now().isoformat()
                }
                
                # Calculate health distribution
                credential_manager = CredentialManager()
                total_response_time = 0
                valid_response_times = 0
                
                for repo in repositories:
                    try:
                        # Get health status
                        monitor = GitHealthMonitor(repo)
                        health_report = monitor.generate_health_report()
                        
                        # Count health distribution
                        health_status = health_report.overall_status
                        if health_status in summary['health_distribution']:
                            summary['health_distribution'][health_status] += 1
                        else:
                            summary['health_distribution']['unknown'] += 1
                        
                        # Check credential health
                        cred_health = credential_manager.get_credential_health(repo)
                        if cred_health.rotation_due:
                            if cred_health.age_days > 180:
                                summary['credential_health']['rotation_overdue'] += 1
                            else:
                                summary['credential_health']['rotation_due'] += 1
                        else:
                            summary['credential_health']['healthy'] += 1
                        
                        # Collect performance metrics
                        if health_report.performance_metrics:
                            avg_time = health_report.performance_metrics.get('average_duration_ms', 0)
                            if avg_time > 0:
                                total_response_time += avg_time
                                valid_response_times += 1
                    
                    except Exception as e:
                        # Log error but continue processing
                        git_operations_logger.log_operation_error(
                            OperationType.HEALTH_CHECK,
                            context,
                            e,
                            None
                        )
                        summary['health_distribution']['unknown'] += 1
                
                # Calculate averages
                if valid_response_times > 0:
                    summary['performance_metrics']['average_response_time'] = int(
                        total_response_time / valid_response_times
                    )
                
                # Calculate success rate from recent operations
                success_rate = self._calculate_success_rate(repositories)
                summary['performance_metrics']['success_rate'] = success_rate
                summary['performance_metrics']['error_rate'] = 100 - success_rate
                
                return Response(summary)
                
        except Exception as e:
            error_response = handle_git_error(
                e,
                'health_summary',
                {'user_id': request.user.id}
            )
            
            return Response(
                {
                    'error': 'Failed to generate health summary',
                    'details': error_response.to_dict()
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_success_rate(self, repositories) -> float:
        """Calculate success rate from repository connection status"""
        if not repositories.exists():
            return 0.0
        
        connected_count = repositories.filter(connection_status='connected').count()
        total_count = repositories.count()
        
        return (connected_count / total_count) * 100 if total_count > 0 else 0.0


class GitRepositoryHealthDetailView(APIView):
    """
    GET /api/plugins/hedgehog/git-repositories/{id}/health-details/
    
    Provides detailed health information for a specific repository
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get detailed health information for repository"""
        try:
            # Get repository
            repository = GitRepository.objects.get(
                pk=pk,
                created_by=request.user
            )
            
            context = create_git_log_context(
                repository_id=repository.id,
                repository_name=repository.name,
                user=request.user
            )
            
            with git_operations_logger.operation_context(
                OperationType.HEALTH_CHECK,
                context,
                operation='health_details',
                repository_id=pk
            ):
                # Generate comprehensive health report
                monitor = GitHealthMonitor(repository)
                health_report = monitor.generate_health_report()
                
                # Get credential health
                credential_manager = CredentialManager()
                credential_health = credential_manager.get_credential_health(repository)
                
                # Get enhanced repository info
                repository_info = repository.get_enhanced_repository_info()
                
                # Compile detailed response
                details = {
                    'repository': {
                        'id': repository.id,
                        'name': repository.name,
                        'url': repository.url,
                        'provider': repository.provider,
                        'authentication_type': repository.authentication_type
                    },
                    'health_report': health_report.to_dict(),
                    'credential_health': credential_health,
                    'repository_info': repository_info,
                    'recommendations': self._generate_actionable_recommendations(
                        health_report,
                        credential_health,
                        repository
                    ),
                    'last_updated': timezone.now().isoformat()
                }
                
                return Response(details)
                
        except GitRepository.DoesNotExist:
            return Response(
                {'error': 'Repository not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            error_response = handle_git_error(
                e,
                'health_details',
                {
                    'user_id': request.user.id,
                    'repository_id': pk
                }
            )
            
            return Response(
                {
                    'error': 'Failed to get health details',
                    'details': error_response.to_dict()
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_actionable_recommendations(
        self,
        health_report,
        credential_health,
        repository
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations for repository health"""
        recommendations = []
        
        # Health-based recommendations
        if health_report.overall_status == HealthStatus.CRITICAL:
            recommendations.append({
                'priority': 'critical',
                'category': 'connectivity',
                'action': 'immediate_attention_required',
                'description': 'Repository health is critical - immediate attention required',
                'steps': [
                    'Check repository connectivity',
                    'Verify credentials are valid',
                    'Contact administrator if issues persist'
                ]
            })
        
        elif health_report.overall_status == HealthStatus.UNHEALTHY:
            recommendations.append({
                'priority': 'high',
                'category': 'connectivity',
                'action': 'investigate_connection_issues',
                'description': 'Repository connection issues detected',
                'steps': [
                    'Test repository connection',
                    'Check network connectivity',
                    'Verify repository URL and credentials'
                ]
            })
        
        # Credential-based recommendations
        if credential_health['rotation_due']:
            priority = 'critical' if credential_health['age_days'] > 365 else 'high'
            recommendations.append({
                'priority': priority,
                'category': 'security',
                'action': 'rotate_credentials',
                'description': f"Credentials are {credential_health['age_days']} days old - rotation recommended",
                'steps': [
                    'Generate new credentials',
                    'Test new credentials',
                    'Update repository configuration',
                    'Verify connectivity'
                ]
            })
        
        # Performance-based recommendations
        if health_report.performance_metrics:
            avg_time = health_report.performance_metrics.get('average_response_time_ms', 0)
            if avg_time > 5000:
                recommendations.append({
                    'priority': 'medium',
                    'category': 'performance',
                    'action': 'optimize_performance',
                    'description': f'Repository response time is slow ({avg_time}ms)',
                    'steps': [
                        'Consider using SSH keys instead of tokens',
                        'Check network connectivity',
                        'Use repository mirrors if available',
                        'Contact git provider support'
                    ]
                })
        
        # Usage-based recommendations
        if repository.fabric_count == 0:
            recommendations.append({
                'priority': 'low',
                'category': 'usage',
                'action': 'repository_unused',
                'description': 'Repository is not being used by any fabrics',
                'steps': [
                    'Assign repository to fabrics',
                    'Consider removing if no longer needed',
                    'Update repository configuration'
                ]
            })
        
        return recommendations


class GitRepositoryHealthHistoryView(APIView):
    """
    GET /api/plugins/hedgehog/git-repositories/{id}/health-history/
    
    Provides health history for a specific repository
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get health history for repository"""
        try:
            # Get repository
            repository = GitRepository.objects.get(
                pk=pk,
                created_by=request.user
            )
            
            # Get query parameters
            days = int(request.GET.get('days', 7))
            granularity = request.GET.get('granularity', 'hour')  # hour, day
            
            context = create_git_log_context(
                repository_id=repository.id,
                repository_name=repository.name,
                user=request.user
            )
            
            # Get operation history from logger
            since = timezone.now() - timedelta(days=days)
            operation_history = git_operations_logger.get_operation_history(
                context=context,
                since=since,
                limit=1000
            )
            
            # Get performance summary
            performance_summary = git_operations_logger.get_performance_summary(
                since=since
            )
            
            # Generate historical data points
            history_data = self._generate_history_data(
                operation_history,
                granularity,
                days
            )
            
            response_data = {
                'repository_id': repository.id,
                'period': {
                    'start': since.isoformat(),
                    'end': timezone.now().isoformat(),
                    'days': days,
                    'granularity': granularity
                },
                'performance_summary': performance_summary,
                'history': history_data,
                'current_status': {
                    'connection_status': repository.connection_status,
                    'last_validated': repository.last_validated.isoformat() if repository.last_validated else None,
                    'validation_error': repository.validation_error
                }
            }
            
            return Response(response_data)
            
        except GitRepository.DoesNotExist:
            return Response(
                {'error': 'Repository not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            error_response = handle_git_error(
                e,
                'health_history',
                {
                    'user_id': request.user.id,
                    'repository_id': pk
                }
            )
            
            return Response(
                {
                    'error': 'Failed to get health history',
                    'details': error_response.to_dict()
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_history_data(
        self,
        operation_history: List[Dict[str, Any]],
        granularity: str,
        days: int
    ) -> List[Dict[str, Any]]:
        """Generate historical data points from operation history"""
        history_data = []
        
        # Group operations by time buckets
        time_buckets = {}
        bucket_size = timedelta(hours=1) if granularity == 'hour' else timedelta(days=1)
        
        for operation in operation_history:
            if 'start_time' in operation:
                start_time = datetime.fromisoformat(operation['start_time'].replace('Z', '+00:00'))
                bucket_key = self._get_time_bucket(start_time, bucket_size)
                
                if bucket_key not in time_buckets:
                    time_buckets[bucket_key] = {
                        'timestamp': bucket_key,
                        'operations': [],
                        'total_duration': 0,
                        'success_count': 0,
                        'error_count': 0
                    }
                
                bucket = time_buckets[bucket_key]
                bucket['operations'].append(operation)
                
                if operation.get('duration_ms'):
                    bucket['total_duration'] += operation['duration_ms']
                
                # Determine success/failure from operation data
                # This is simplified - in real implementation, you'd have success/failure info
                if operation.get('duration_ms', 0) > 0:
                    bucket['success_count'] += 1
                else:
                    bucket['error_count'] += 1
        
        # Convert to ordered list
        for bucket_key in sorted(time_buckets.keys()):
            bucket = time_buckets[bucket_key]
            total_ops = len(bucket['operations'])
            
            if total_ops > 0:
                avg_duration = bucket['total_duration'] / total_ops
                success_rate = (bucket['success_count'] / total_ops) * 100
            else:
                avg_duration = 0
                success_rate = 0
            
            history_data.append({
                'timestamp': bucket_key.isoformat(),
                'average_response_time_ms': int(avg_duration),
                'operation_count': total_ops,
                'success_rate': success_rate,
                'error_count': bucket['error_count'],
                'success_count': bucket['success_count']
            })
        
        return history_data
    
    def _get_time_bucket(self, timestamp: datetime, bucket_size: timedelta) -> datetime:
        """Get the time bucket for a timestamp"""
        if bucket_size == timedelta(hours=1):
            # Round down to hour
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif bucket_size == timedelta(days=1):
            # Round down to day
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return timestamp


class GitConnectionMetricsView(APIView):
    """
    GET /api/plugins/hedgehog/git-repositories/connection-metrics/
    
    Provides connection metrics across all repositories
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get connection metrics for all repositories"""
        try:
            context = create_git_log_context(user=request.user)
            
            # Get query parameters
            days = int(request.GET.get('days', 7))
            include_history = request.GET.get('include_history', 'false').lower() == 'true'
            
            # Get repositories
            repositories = GitRepository.objects.filter(created_by=request.user)
            
            # Calculate metrics
            total_repos = repositories.count()
            connected_repos = repositories.filter(connection_status='connected').count()
            failed_repos = repositories.filter(connection_status='failed').count()
            pending_repos = repositories.filter(connection_status='pending').count()
            
            # Get performance metrics from logger
            since = timezone.now() - timedelta(days=days)
            performance_summary = git_operations_logger.get_performance_summary(since=since)
            
            metrics = {
                'overview': {
                    'total_repositories': total_repos,
                    'connection_distribution': {
                        'connected': connected_repos,
                        'failed': failed_repos,
                        'pending': pending_repos,
                        'testing': repositories.filter(connection_status='testing').count()
                    },
                    'connection_rate': (connected_repos / total_repos * 100) if total_repos > 0 else 0,
                    'failure_rate': (failed_repos / total_repos * 100) if total_repos > 0 else 0
                },
                'performance': performance_summary,
                'period': {
                    'start': since.isoformat(),
                    'end': timezone.now().isoformat(),
                    'days': days
                }
            }
            
            # Add history if requested
            if include_history:
                metrics['history'] = self._get_connection_history(repositories, days)
            
            # Add repository-specific metrics
            metrics['repositories'] = []
            for repo in repositories:
                repo_metrics = {
                    'id': repo.id,
                    'name': repo.name,
                    'connection_status': repo.connection_status,
                    'last_validated': repo.last_validated.isoformat() if repo.last_validated else None,
                    'fabric_count': repo.fabric_count,
                    'provider': repo.provider
                }
                
                # Add health status if available
                try:
                    monitor = GitHealthMonitor(repo)
                    health_report = monitor.generate_health_report()
                    repo_metrics['health_status'] = health_report.overall_status
                    repo_metrics['health_score'] = self._calculate_health_score(health_report)
                except Exception:
                    repo_metrics['health_status'] = 'unknown'
                    repo_metrics['health_score'] = 0
                
                metrics['repositories'].append(repo_metrics)
            
            return Response(metrics)
            
        except Exception as e:
            error_response = handle_git_error(
                e,
                'connection_metrics',
                {'user_id': request.user.id}
            )
            
            return Response(
                {
                    'error': 'Failed to get connection metrics',
                    'details': error_response.to_dict()
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_connection_history(self, repositories, days: int) -> List[Dict[str, Any]]:
        """Get connection history for repositories"""
        # This is a simplified implementation
        # In a real system, you'd track connection status changes over time
        
        history = []
        since = timezone.now() - timedelta(days=days)
        
        # Generate daily snapshots (simplified)
        for i in range(days):
            day = since + timedelta(days=i)
            
            # Simulate historical data
            # In reality, this would come from logged status changes
            history.append({
                'date': day.date().isoformat(),
                'connected_count': repositories.filter(connection_status='connected').count(),
                'failed_count': repositories.filter(connection_status='failed').count(),
                'total_count': repositories.count()
            })
        
        return history
    
    def _calculate_health_score(self, health_report) -> int:
        """Calculate a numeric health score from health report"""
        if health_report.overall_status == HealthStatus.HEALTHY:
            return 100
        elif health_report.overall_status == HealthStatus.DEGRADED:
            return 75
        elif health_report.overall_status == HealthStatus.UNHEALTHY:
            return 50
        elif health_report.overall_status == HealthStatus.CRITICAL:
            return 25
        else:
            return 0


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def force_health_check(request, pk):
    """
    POST /api/plugins/hedgehog/git-repositories/{pk}/force-health-check/
    
    Force an immediate health check for a repository
    """
    try:
        # Get repository
        repository = GitRepository.objects.get(
            pk=pk,
            created_by=request.user
        )
        
        context = create_git_log_context(
            repository_id=repository.id,
            repository_name=repository.name,
            user=request.user
        )
        
        with git_operations_logger.operation_context(
            OperationType.HEALTH_CHECK,
            context,
            operation='force_health_check',
            repository_id=pk
        ) as operation:
            
            # Create health monitor
            monitor = GitHealthMonitor(repository)
            
            # Run comprehensive health check
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run periodic health check
                health_result = loop.run_until_complete(
                    monitor.periodic_health_check()
                )
                
                # Update operation metrics
                git_operations_logger.update_operation_metrics(
                    operation,
                    duration_ms=health_result.duration_ms,
                    network_time_ms=health_result.duration_ms
                )
                
                # Get additional checks
                credential_manager = CredentialManager()
                credential_health = credential_manager.get_credential_health(repository)
                
                # Generate full report
                health_report = monitor.generate_health_report()
                
                response_data = {
                    'repository_id': repository.id,
                    'check_timestamp': timezone.now().isoformat(),
                    'health_check_result': health_result.to_dict(),
                    'credential_health': credential_health,
                    'health_report': health_report.to_dict(),
                    'recommendations': []
                }
                
                # Add recommendations based on results
                if health_result.status != HealthStatus.HEALTHY:
                    response_data['recommendations'].extend([
                        'Investigate connection issues',
                        'Verify repository credentials',
                        'Check network connectivity'
                    ])
                
                if credential_health['rotation_due']:
                    response_data['recommendations'].append('Consider rotating credentials')
                
                return Response(response_data)
                
            finally:
                loop.close()
                
    except GitRepository.DoesNotExist:
        return Response(
            {'error': 'Repository not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        error_response = handle_git_error(
            e,
            'force_health_check',
            {
                'user_id': request.user.id,
                'repository_id': pk
            }
        )
        
        return Response(
            {
                'error': 'Health check failed',
                'details': error_response.to_dict()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )