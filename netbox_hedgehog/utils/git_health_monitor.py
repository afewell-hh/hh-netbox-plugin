"""
Enhanced Git Repository Health Monitoring
Provides comprehensive health checking, validation, and monitoring capabilities
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import git
from django.utils import timezone
from django.db import transaction
from urllib.parse import urlparse

from ..models import GitRepository
from ..choices import GitConnectionStatusChoices

logger = logging.getLogger('netbox_hedgehog.git_health')


class HealthStatus(str, Enum):
    """Health status levels"""
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'
    CRITICAL = 'critical'


class ValidationResult(str, Enum):
    """Validation result types"""
    PASSED = 'passed'
    WARNING = 'warning'
    FAILED = 'failed'


@dataclass
class HealthCheckResult:
    """Result of a health check operation"""
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    duration_ms: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'status': self.status,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'duration_ms': self.duration_ms
        }


@dataclass
class BranchCheckResult:
    """Result of branch availability check"""
    available_branches: List[str]
    default_branch: str
    missing_branches: List[str]
    current_commit: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class DirectoryValidationResult:
    """Result of directory structure validation"""
    valid_directories: List[str]
    missing_directories: List[str]
    crd_files_found: Dict[str, List[str]]
    validation_errors: List[str]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ChangeDetectionResult:
    """Result of repository change detection"""
    has_changes: bool
    commits_since_last_check: int
    new_commits: List[Dict[str, str]]
    files_changed: List[str]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class HealthReport:
    """Comprehensive health report"""
    repository_id: int
    repository_name: str
    overall_status: HealthStatus
    connection_check: Optional[HealthCheckResult]
    branch_check: Optional[BranchCheckResult]
    directory_check: Optional[DirectoryValidationResult]
    change_detection: Optional[ChangeDetectionResult]
    performance_metrics: Dict[str, Any]
    recommendations: List[str]
    generated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'repository_id': self.repository_id,
            'repository_name': self.repository_name,
            'overall_status': self.overall_status,
            'connection_check': self.connection_check.to_dict() if self.connection_check else None,
            'branch_check': self.branch_check.to_dict() if self.branch_check else None,
            'directory_check': self.directory_check.to_dict() if self.directory_check else None,
            'change_detection': self.change_detection.to_dict() if self.change_detection else None,
            'performance_metrics': self.performance_metrics,
            'recommendations': self.recommendations,
            'generated_at': self.generated_at.isoformat()
        }


class GitHealthMonitor:
    """Enhanced git repository health monitoring and validation"""
    
    def __init__(self, repository: GitRepository):
        self.repository = repository
        self.logger = logging.getLogger(f'git_health.{repository.id}')
        self._performance_history: List[Dict[str, Any]] = []
        self._last_commit_sha: Optional[str] = None
    
    async def periodic_health_check(self) -> HealthCheckResult:
        """
        Perform comprehensive periodic health check.
        Designed to run every 4 hours as specified.
        """
        start_time = timezone.now()
        health_checks = []
        
        try:
            # Run all health checks
            connection_result = await self._check_connection_health()
            health_checks.append(connection_result)
            
            if connection_result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]:
                # Only run additional checks if connection is somewhat working
                auth_result = await self._check_authentication_health()
                health_checks.append(auth_result)
                
                performance_result = await self._check_performance_health()
                health_checks.append(performance_result)
                
                usage_result = await self._check_usage_health()
                health_checks.append(usage_result)
            
            # Determine overall status
            overall_status = self._calculate_overall_status(health_checks)
            
            # Generate summary message
            summary_message = self._generate_health_summary(health_checks)
            
            # Calculate duration
            duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)
            
            # Update repository status if needed
            await self._update_repository_status(overall_status)
            
            return HealthCheckResult(
                status=overall_status,
                message=summary_message,
                details={
                    'checks': [check.to_dict() for check in health_checks],
                    'repository_id': self.repository.id,
                    'repository_url': self.repository.url
                },
                timestamp=timezone.now(),
                duration_ms=duration_ms
            )
            
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)
            
            return HealthCheckResult(
                status=HealthStatus.CRITICAL,
                message=f"Health check failed: {str(e)}",
                details={'error': str(e)},
                timestamp=timezone.now(),
                duration_ms=duration_ms
            )
    
    async def validate_repository_access(self) -> 'ValidationResult':
        """
        Validate comprehensive repository access permissions.
        """
        try:
            # Test basic connectivity
            connection_test = self.repository.test_connection()
            if not connection_test.get('success'):
                return ValidationResult(
                    result=ValidationResult.FAILED,
                    message="Repository connection failed",
                    details=connection_test
                )
            
            # Test read access by listing remote refs
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                repo = git.Repo.init(temp_dir)
                remote = repo.create_remote('test', self._get_authenticated_url())
                
                try:
                    # Test fetch (read) access
                    refs = remote.refs
                    has_refs = len(refs) > 0
                    
                    if not has_refs:
                        return ValidationResult(
                            result=ValidationResult.WARNING,
                            message="Repository appears empty",
                            details={'ref_count': 0}
                        )
                    
                    # Check for write access indicators
                    # Note: Full write test would require actual push
                    can_push = self._check_push_permissions()
                    
                    return ValidationResult(
                        result=ValidationResult.PASSED,
                        message="Repository access validated successfully",
                        details={
                            'read_access': True,
                            'ref_count': len(refs),
                            'write_access_likely': can_push,
                            'default_branch': self.repository.default_branch
                        }
                    )
                    
                except git.exc.GitCommandError as e:
                    error_msg = str(e)
                    if 'authentication' in error_msg.lower():
                        return ValidationResult(
                            result=ValidationResult.FAILED,
                            message="Authentication failed",
                            details={'error': error_msg}
                        )
                    elif 'permission' in error_msg.lower():
                        return ValidationResult(
                            result=ValidationResult.WARNING,
                            message="Limited permissions detected",
                            details={'error': error_msg}
                        )
                    else:
                        return ValidationResult(
                            result=ValidationResult.FAILED,
                            message="Access validation failed",
                            details={'error': error_msg}
                        )
                        
        except Exception as e:
            self.logger.error(f"Access validation error: {str(e)}")
            return ValidationResult(
                result=ValidationResult.FAILED,
                message="Unexpected validation error",
                details={'error': str(e)}
            )
    
    async def check_branch_availability(self, branches: List[str]) -> BranchCheckResult:
        """
        Check availability of specified branches in the repository.
        """
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                repo = git.Repo.init(temp_dir)
                remote = repo.create_remote('test', self._get_authenticated_url())
                
                # Fetch remote refs
                remote.fetch()
                remote_refs = {ref.remote_head: ref.commit.hexsha for ref in remote.refs}
                
                # Check each requested branch
                available_branches = []
                missing_branches = []
                
                for branch in branches:
                    if branch in remote_refs:
                        available_branches.append(branch)
                    else:
                        missing_branches.append(branch)
                
                # Get current commit of default branch
                current_commit = remote_refs.get(
                    self.repository.default_branch,
                    remote_refs.get('main', remote_refs.get('master', 'unknown'))
                )
                
                return BranchCheckResult(
                    available_branches=available_branches,
                    default_branch=self.repository.default_branch,
                    missing_branches=missing_branches,
                    current_commit=current_commit,
                    timestamp=timezone.now()
                )
                
        except Exception as e:
            self.logger.error(f"Branch check error: {str(e)}")
            return BranchCheckResult(
                available_branches=[],
                default_branch=self.repository.default_branch,
                missing_branches=branches,
                current_commit='unknown',
                timestamp=timezone.now()
            )
    
    async def validate_directory_structure(self, directories: List[str]) -> DirectoryValidationResult:
        """
        Validate directory structure and check for Hedgehog CRD files.
        """
        valid_directories = []
        missing_directories = []
        crd_files_found = {}
        validation_errors = []
        
        try:
            # Clone repository to temporary location
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = self.repository.clone_repository(
                    temp_dir,
                    branch=self.repository.default_branch
                )
                
                if not clone_result.get('success'):
                    validation_errors.append(f"Clone failed: {clone_result.get('error')}")
                    return DirectoryValidationResult(
                        valid_directories=[],
                        missing_directories=directories,
                        crd_files_found={},
                        validation_errors=validation_errors,
                        timestamp=timezone.now()
                    )
                
                repo_path = clone_result['repository_path']
                
                # Check each directory
                import os
                for directory in directories:
                    dir_path = os.path.join(repo_path, directory.lstrip('/'))
                    
                    if os.path.exists(dir_path) and os.path.isdir(dir_path):
                        valid_directories.append(directory)
                        
                        # Look for CRD YAML files
                        crd_files = []
                        for root, _, files in os.walk(dir_path):
                            for file in files:
                                if file.endswith(('.yaml', '.yml')):
                                    # Check if it's a Hedgehog CRD
                                    file_path = os.path.join(root, file)
                                    if self._is_hedgehog_crd(file_path):
                                        rel_path = os.path.relpath(file_path, dir_path)
                                        crd_files.append(rel_path)
                        
                        if crd_files:
                            crd_files_found[directory] = crd_files
                    else:
                        missing_directories.append(directory)
                
                return DirectoryValidationResult(
                    valid_directories=valid_directories,
                    missing_directories=missing_directories,
                    crd_files_found=crd_files_found,
                    validation_errors=validation_errors,
                    timestamp=timezone.now()
                )
                
        except Exception as e:
            self.logger.error(f"Directory validation error: {str(e)}")
            validation_errors.append(str(e))
            return DirectoryValidationResult(
                valid_directories=[],
                missing_directories=directories,
                crd_files_found={},
                validation_errors=validation_errors,
                timestamp=timezone.now()
            )
    
    async def monitor_repository_changes(self) -> ChangeDetectionResult:
        """
        Monitor repository for changes since last check.
        """
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                repo = git.Repo.init(temp_dir)
                remote = repo.create_remote('test', self._get_authenticated_url())
                
                # Fetch latest
                remote.fetch()
                
                # Get current HEAD commit
                try:
                    current_head = remote.refs[self.repository.default_branch].commit
                    current_sha = current_head.hexsha
                except (KeyError, IndexError):
                    # Fallback to any available ref
                    current_head = list(remote.refs)[0].commit if remote.refs else None
                    current_sha = current_head.hexsha if current_head else None
                
                # Check for changes
                has_changes = False
                commits_since_last = 0
                new_commits = []
                files_changed = []
                
                if current_sha and self._last_commit_sha:
                    has_changes = current_sha != self._last_commit_sha
                    
                    if has_changes and current_head:
                        # Get commits between last known and current
                        try:
                            # Note: This is a simplified approach
                            # In production, you'd want to properly walk the commit graph
                            commit_count = 0
                            for commit in repo.iter_commits(current_sha):
                                if commit.hexsha == self._last_commit_sha:
                                    break
                                commit_count += 1
                                if commit_count <= 10:  # Limit to recent 10 commits
                                    new_commits.append({
                                        'sha': commit.hexsha[:8],
                                        'author': str(commit.author),
                                        'message': commit.message.strip().split('\n')[0],
                                        'timestamp': datetime.fromtimestamp(commit.committed_date).isoformat()
                                    })
                            
                            commits_since_last = commit_count
                        except Exception as e:
                            self.logger.warning(f"Failed to get commit history: {str(e)}")
                
                # Update last known commit
                if current_sha:
                    self._last_commit_sha = current_sha
                
                return ChangeDetectionResult(
                    has_changes=has_changes,
                    commits_since_last_check=commits_since_last,
                    new_commits=new_commits,
                    files_changed=files_changed,
                    timestamp=timezone.now()
                )
                
        except Exception as e:
            self.logger.error(f"Change detection error: {str(e)}")
            return ChangeDetectionResult(
                has_changes=False,
                commits_since_last_check=0,
                new_commits=[],
                files_changed=[],
                timestamp=timezone.now()
            )
    
    def generate_health_report(self) -> HealthReport:
        """
        Generate comprehensive health report for the repository.
        """
        # Run synchronous health checks
        connection_check = self._run_sync_health_check()
        
        # Get performance metrics
        performance_metrics = self._calculate_performance_metrics()
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            connection_check,
            performance_metrics
        )
        
        # Determine overall status
        overall_status = self._determine_overall_health(
            connection_check,
            performance_metrics
        )
        
        return HealthReport(
            repository_id=self.repository.id,
            repository_name=self.repository.name,
            overall_status=overall_status,
            connection_check=connection_check,
            branch_check=None,  # Would be populated by async checks
            directory_check=None,  # Would be populated by async checks
            change_detection=None,  # Would be populated by async checks
            performance_metrics=performance_metrics,
            recommendations=recommendations,
            generated_at=timezone.now()
        )
    
    # Private helper methods
    
    def _get_authenticated_url(self) -> str:
        """Get repository URL with authentication embedded"""
        credentials = self.repository.get_credentials()
        clone_url = self.repository.url
        
        if self.repository.authentication_type == 'token':
            token = credentials.get('token', '')
            if token:
                parsed_url = urlparse(self.repository.url)
                if parsed_url.scheme in ['https', 'http']:
                    clone_url = f"{parsed_url.scheme}://{token}@{parsed_url.netloc}{parsed_url.path}"
        
        return clone_url
    
    def _is_hedgehog_crd(self, file_path: str) -> bool:
        """Check if a file is a Hedgehog CRD"""
        try:
            import yaml
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                
            if isinstance(data, dict):
                # Check for Hedgehog API groups
                api_version = data.get('apiVersion', '')
                if 'hedgehog.io' in api_version:
                    return True
                    
                # Check for known Hedgehog kinds
                kind = data.get('kind', '')
                hedgehog_kinds = [
                    'VPC', 'Connection', 'Server', 'Switch', 'SwitchGroup',
                    'External', 'ExternalAttachment', 'ExternalPeering',
                    'VPCAttachment', 'VPCPeering', 'IPv4Namespace', 'VLANNamespace'
                ]
                if kind in hedgehog_kinds:
                    return True
                    
        except Exception:
            pass
            
        return False
    
    async def _check_connection_health(self) -> HealthCheckResult:
        """Check basic connection health"""
        start_time = timezone.now()
        
        try:
            result = self.repository.test_connection()
            duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)
            
            if result.get('success'):
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    message="Connection successful",
                    details=result,
                    timestamp=timezone.now(),
                    duration_ms=duration_ms
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Connection failed: {result.get('error')}",
                    details=result,
                    timestamp=timezone.now(),
                    duration_ms=duration_ms
                )
                
        except Exception as e:
            duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)
            return HealthCheckResult(
                status=HealthStatus.CRITICAL,
                message=f"Connection check error: {str(e)}",
                details={'error': str(e)},
                timestamp=timezone.now(),
                duration_ms=duration_ms
            )
    
    async def _check_authentication_health(self) -> HealthCheckResult:
        """Check authentication health"""
        try:
            credentials = self.repository.get_credentials()
            
            if not credentials:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="No credentials configured",
                    details={'has_credentials': False},
                    timestamp=timezone.now(),
                    duration_ms=0
                )
            
            # Check credential age if available
            # In a real implementation, you'd track credential creation date
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Authentication configured",
                details={
                    'has_credentials': True,
                    'auth_type': self.repository.authentication_type
                },
                timestamp=timezone.now(),
                duration_ms=0
            )
            
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.CRITICAL,
                message=f"Authentication check error: {str(e)}",
                details={'error': str(e)},
                timestamp=timezone.now(),
                duration_ms=0
            )
    
    async def _check_performance_health(self) -> HealthCheckResult:
        """Check performance health based on recent metrics"""
        if not self._performance_history:
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="No performance history yet",
                details={'history_size': 0},
                timestamp=timezone.now(),
                duration_ms=0
            )
        
        # Calculate average response time
        avg_duration = sum(p['duration_ms'] for p in self._performance_history[-10:]) / min(len(self._performance_history), 10)
        
        # Determine health based on performance
        if avg_duration < 1000:
            status = HealthStatus.HEALTHY
            message = "Excellent performance"
        elif avg_duration < 3000:
            status = HealthStatus.HEALTHY
            message = "Good performance"
        elif avg_duration < 5000:
            status = HealthStatus.DEGRADED
            message = "Degraded performance"
        else:
            status = HealthStatus.UNHEALTHY
            message = "Poor performance"
        
        return HealthCheckResult(
            status=status,
            message=message,
            details={
                'average_duration_ms': int(avg_duration),
                'sample_size': min(len(self._performance_history), 10)
            },
            timestamp=timezone.now(),
            duration_ms=0
        )
    
    async def _check_usage_health(self) -> HealthCheckResult:
        """Check repository usage health"""
        fabric_count = self.repository.fabric_count
        
        if fabric_count == 0:
            status = HealthStatus.DEGRADED
            message = "Repository not in use"
        elif fabric_count < 5:
            status = HealthStatus.HEALTHY
            message = f"Repository used by {fabric_count} fabric(s)"
        else:
            status = HealthStatus.HEALTHY
            message = f"Repository heavily used ({fabric_count} fabrics)"
        
        return HealthCheckResult(
            status=status,
            message=message,
            details={'fabric_count': fabric_count},
            timestamp=timezone.now(),
            duration_ms=0
        )
    
    def _calculate_overall_status(self, health_checks: List[HealthCheckResult]) -> HealthStatus:
        """Calculate overall health status from individual checks"""
        if not health_checks:
            return HealthStatus.CRITICAL
        
        # Count status levels
        status_counts = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 0,
            HealthStatus.UNHEALTHY: 0,
            HealthStatus.CRITICAL: 0
        }
        
        for check in health_checks:
            status_counts[check.status] += 1
        
        # Determine overall status
        if status_counts[HealthStatus.CRITICAL] > 0:
            return HealthStatus.CRITICAL
        elif status_counts[HealthStatus.UNHEALTHY] > 0:
            return HealthStatus.UNHEALTHY
        elif status_counts[HealthStatus.DEGRADED] > 0:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def _generate_health_summary(self, health_checks: List[HealthCheckResult]) -> str:
        """Generate summary message from health checks"""
        overall_status = self._calculate_overall_status(health_checks)
        
        if overall_status == HealthStatus.HEALTHY:
            return "All health checks passed"
        elif overall_status == HealthStatus.DEGRADED:
            degraded_count = sum(1 for c in health_checks if c.status == HealthStatus.DEGRADED)
            return f"{degraded_count} health check(s) degraded"
        elif overall_status == HealthStatus.UNHEALTHY:
            unhealthy_count = sum(1 for c in health_checks if c.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL])
            return f"{unhealthy_count} health check(s) failed"
        else:
            return "Critical health issues detected"
    
    async def _update_repository_status(self, overall_status: HealthStatus) -> None:
        """Update repository connection status based on health"""
        try:
            if overall_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]:
                self.repository.connection_status = GitConnectionStatusChoices.CONNECTED
            elif overall_status == HealthStatus.UNHEALTHY:
                self.repository.connection_status = GitConnectionStatusChoices.FAILED
            else:
                self.repository.connection_status = GitConnectionStatusChoices.FAILED
            
            self.repository.save(update_fields=['connection_status'])
        except Exception as e:
            self.logger.error(f"Failed to update repository status: {str(e)}")
    
    def _check_push_permissions(self) -> bool:
        """Check if credentials likely have push permissions"""
        # This is a heuristic check - actual push test would require write operation
        if self.repository.authentication_type == 'token':
            # Most tokens with repo access can push
            return True
        elif self.repository.authentication_type == 'ssh_key':
            # SSH keys usually have push access
            return True
        elif self.repository.authentication_type == 'basic':
            # Basic auth may or may not have push
            return False
        else:
            return False
    
    def _run_sync_health_check(self) -> Optional[HealthCheckResult]:
        """Run synchronous health check for report generation"""
        try:
            result = self.repository.test_connection()
            
            if result.get('success'):
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    message="Connection successful",
                    details=result,
                    timestamp=timezone.now(),
                    duration_ms=0
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Connection failed: {result.get('error')}",
                    details=result,
                    timestamp=timezone.now(),
                    duration_ms=0
                )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.CRITICAL,
                message=f"Health check error: {str(e)}",
                details={'error': str(e)},
                timestamp=timezone.now(),
                duration_ms=0
            )
    
    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics from history"""
        if not self._performance_history:
            return {
                'average_response_time_ms': 0,
                'success_rate': 0,
                'sample_size': 0
            }
        
        recent_history = self._performance_history[-50:]  # Last 50 checks
        
        total_duration = sum(p['duration_ms'] for p in recent_history)
        success_count = sum(1 for p in recent_history if p.get('success', False))
        
        return {
            'average_response_time_ms': int(total_duration / len(recent_history)),
            'success_rate': (success_count / len(recent_history)) * 100,
            'sample_size': len(recent_history),
            'last_check': recent_history[-1]['timestamp'] if recent_history else None
        }
    
    def _generate_recommendations(
        self,
        connection_check: Optional[HealthCheckResult],
        performance_metrics: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on health status"""
        recommendations = []
        
        # Connection recommendations
        if connection_check:
            if connection_check.status == HealthStatus.UNHEALTHY:
                recommendations.append("Check repository credentials and network connectivity")
            elif connection_check.status == HealthStatus.CRITICAL:
                recommendations.append("Urgent: Repository connection is failing")
        
        # Performance recommendations
        avg_response = performance_metrics.get('average_response_time_ms', 0)
        if avg_response > 5000:
            recommendations.append("Consider using a repository mirror for better performance")
        elif avg_response > 3000:
            recommendations.append("Repository response times are elevated")
        
        # Success rate recommendations
        success_rate = performance_metrics.get('success_rate', 100)
        if success_rate < 50:
            recommendations.append("Critical: More than half of connection attempts are failing")
        elif success_rate < 90:
            recommendations.append("Connection reliability issues detected")
        
        # Usage recommendations
        if self.repository.fabric_count == 0:
            recommendations.append("Repository is not being used by any fabrics")
        elif self.repository.fabric_count > 10:
            recommendations.append("Consider repository performance optimization for high usage")
        
        # Credential recommendations
        if not self.repository.last_validated:
            recommendations.append("Repository has never been validated")
        elif self.repository.last_validated < timezone.now() - timedelta(days=30):
            recommendations.append("Repository credentials should be re-validated")
        
        return recommendations
    
    def _determine_overall_health(
        self,
        connection_check: Optional[HealthCheckResult],
        performance_metrics: Dict[str, Any]
    ) -> HealthStatus:
        """Determine overall health status"""
        # Start with connection status
        if connection_check:
            if connection_check.status == HealthStatus.CRITICAL:
                return HealthStatus.CRITICAL
            elif connection_check.status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY
        
        # Check success rate
        success_rate = performance_metrics.get('success_rate', 100)
        if success_rate < 50:
            return HealthStatus.CRITICAL
        elif success_rate < 90:
            return HealthStatus.UNHEALTHY
        
        # Check performance
        avg_response = performance_metrics.get('average_response_time_ms', 0)
        if avg_response > 5000:
            return HealthStatus.DEGRADED
        
        # Check usage
        if self.repository.fabric_count == 0:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY