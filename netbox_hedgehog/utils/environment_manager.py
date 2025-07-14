"""
Multi-Environment Branch Management for Enterprise GitOps.

This module provides advanced environment management capabilities including:
- Environment branch tracking (staging, production, development)
- Cross-environment drift detection and comparison
- Branch promotion workflows
- Environment synchronization status
- Multi-environment UI data for Frontend Agent

Author: Git Operations Agent
Date: July 10, 2025
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from django.utils import timezone
from django.db import transaction

from ..models.fabric import HedgehogFabric
from ..models.gitops import HedgehogResource

logger = logging.getLogger(__name__)


class EnvironmentType(Enum):
    """Environment types for branch management."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    FEATURE = "feature"
    HOTFIX = "hotfix"


class EnvironmentStatus(Enum):
    """Environment status indicators."""
    HEALTHY = "healthy"
    DRIFT_DETECTED = "drift_detected"
    SYNC_NEEDED = "sync_needed"
    ERROR = "error"
    UNKNOWN = "unknown"


class PromotionStatus(Enum):
    """Branch promotion workflow status."""
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EnvironmentConfig:
    """Configuration for a specific environment."""
    name: str
    env_type: EnvironmentType
    branch: str
    priority: int
    auto_sync: bool = False
    require_approval: bool = True
    max_drift_threshold: int = 5
    sync_schedule: Optional[str] = None  # Cron expression
    promotion_target: Optional[str] = None  # Next environment in pipeline
    
    def __post_init__(self):
        if isinstance(self.env_type, str):
            self.env_type = EnvironmentType(self.env_type)


@dataclass
class BranchComparison:
    """Result of comparing two branches."""
    base_branch: str
    head_branch: str
    ahead_by: int
    behind_by: int
    status: str
    total_commits: int
    files_changed: int
    additions: int
    deletions: int
    has_conflicts: bool = False
    comparison_time: datetime = field(default_factory=timezone.now)
    commits: List[Dict[str, Any]] = field(default_factory=list)
    changed_files: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'base_branch': self.base_branch,
            'head_branch': self.head_branch,
            'ahead_by': self.ahead_by,
            'behind_by': self.behind_by,
            'status': self.status,
            'total_commits': self.total_commits,
            'files_changed': self.files_changed,
            'additions': self.additions,
            'deletions': self.deletions,
            'has_conflicts': self.has_conflicts,
            'comparison_time': self.comparison_time.isoformat(),
            'commits': self.commits[:10],  # Limit to last 10 commits
            'changed_files': self.changed_files[:20]  # Limit to 20 files
        }


@dataclass
class EnvironmentHealth:
    """Health status of an environment."""
    environment: str
    status: EnvironmentStatus
    last_sync: Optional[datetime]
    resource_count: int
    drift_count: int
    error_count: int
    last_commit: str
    branch: str
    sync_duration: Optional[float] = None
    next_sync: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'environment': self.environment,
            'status': self.status.value,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'resource_count': self.resource_count,
            'drift_count': self.drift_count,
            'error_count': self.error_count,
            'last_commit': self.last_commit,
            'branch': self.branch,
            'sync_duration': self.sync_duration,
            'next_sync': self.next_sync.isoformat() if self.next_sync else None,
            'health_score': self._calculate_health_score()
        }
    
    def _calculate_health_score(self) -> float:
        """Calculate health score from 0-100."""
        if self.status == EnvironmentStatus.ERROR:
            return 0.0
        elif self.status == EnvironmentStatus.UNKNOWN:
            return 25.0
        
        # Base score
        score = 100.0
        
        # Reduce score for drift
        if self.drift_count > 0:
            drift_penalty = min(self.drift_count * 10, 50)
            score -= drift_penalty
        
        # Reduce score for errors
        if self.error_count > 0:
            error_penalty = min(self.error_count * 15, 40)
            score -= error_penalty
        
        # Reduce score for old syncs
        if self.last_sync:
            hours_since_sync = (timezone.now() - self.last_sync).total_seconds() / 3600
            if hours_since_sync > 24:
                age_penalty = min((hours_since_sync - 24) / 24 * 10, 20)
                score -= age_penalty
        
        return max(score, 0.0)


@dataclass
class PromotionPlan:
    """Plan for promoting changes between environments."""
    source_env: str
    target_env: str
    status: PromotionStatus
    resources_to_promote: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    approvals_required: List[str]
    estimated_duration: timedelta
    risk_assessment: str
    created_at: datetime = field(default_factory=timezone.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'source_env': self.source_env,
            'target_env': self.target_env,
            'status': self.status.value,
            'resources_to_promote': self.resources_to_promote,
            'conflicts': self.conflicts,
            'approvals_required': self.approvals_required,
            'estimated_duration': self.estimated_duration.total_seconds(),
            'risk_assessment': self.risk_assessment,
            'created_at': self.created_at.isoformat(),
            'promotion_ready': len(self.conflicts) == 0 and len(self.approvals_required) == 0
        }


class EnvironmentManager:
    """
    Manages multi-environment GitOps workflows.
    
    Provides functionality for:
    - Environment configuration and tracking
    - Cross-environment comparison and drift detection
    - Branch promotion workflows
    - Environment health monitoring
    - Multi-environment UI data generation
    """
    
    # Default environment configurations
    DEFAULT_ENVIRONMENTS = {
        'development': EnvironmentConfig(
            name='development',
            env_type=EnvironmentType.DEVELOPMENT,
            branch='develop',
            priority=1,
            auto_sync=True,
            require_approval=False,
            max_drift_threshold=10
        ),
        'staging': EnvironmentConfig(
            name='staging',
            env_type=EnvironmentType.STAGING,
            branch='staging',
            priority=2,
            auto_sync=False,
            require_approval=True,
            max_drift_threshold=3,
            promotion_target='production'
        ),
        'production': EnvironmentConfig(
            name='production',
            env_type=EnvironmentType.PRODUCTION,
            branch='main',
            priority=3,
            auto_sync=False,
            require_approval=True,
            max_drift_threshold=0
        )
    }
    
    def __init__(self, fabric: HedgehogFabric):
        """
        Initialize EnvironmentManager for a specific fabric.
        
        Args:
            fabric: HedgehogFabric instance
        """
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
        
        # Load environment configurations
        self.environments = self._load_environment_configs()
        
        # Cache for branch comparisons
        self._comparison_cache = {}
        self._cache_ttl = timedelta(minutes=15)
    
    def _load_environment_configs(self) -> Dict[str, EnvironmentConfig]:
        """
        Load environment configurations for the fabric.
        
        This method loads environment configurations from fabric settings
        or uses defaults if not configured.
        
        Returns:
            Dictionary of environment configurations
        """
        # For now, use default environments
        # In future, this could be loaded from fabric.environment_config field
        environments = {}
        
        for env_name, config in self.DEFAULT_ENVIRONMENTS.items():
            # Customize based on fabric configuration
            if env_name == 'production' and self.fabric.git_branch:
                config.branch = self.fabric.git_branch
            
            environments[env_name] = config
        
        self.logger.debug(f"Loaded {len(environments)} environment configurations")
        return environments
    
    def get_environment_config(self, environment: str) -> Optional[EnvironmentConfig]:
        """
        Get configuration for a specific environment.
        
        Args:
            environment: Environment name
            
        Returns:
            EnvironmentConfig or None if not found
        """
        return self.environments.get(environment)
    
    def list_environments(self) -> List[str]:
        """
        List all configured environments.
        
        Returns:
            List of environment names
        """
        return list(self.environments.keys())
    
    async def get_environment_health(self, environment: str) -> Optional[EnvironmentHealth]:
        """
        Get comprehensive health status for an environment.
        
        Args:
            environment: Environment name
            
        Returns:
            EnvironmentHealth object or None if environment not found
        """
        config = self.get_environment_config(environment)
        if not config:
            self.logger.warning(f"Environment '{environment}' not configured")
            return None
        
        try:
            # Query resources for this environment
            # For now, we'll simulate environment-specific resources
            # In a real implementation, this might filter by labels or annotations
            resources = await asyncio.to_thread(
                list,
                HedgehogResource.objects.filter(fabric=self.fabric)
            )
            
            # Calculate health metrics
            resource_count = len(resources)
            drift_count = sum(1 for r in resources if r.drift_status != 'in_sync')
            error_count = sum(1 for r in resources if r.drift_status == 'error')
            
            # Determine status
            if error_count > 0:
                status = EnvironmentStatus.ERROR
            elif drift_count > config.max_drift_threshold:
                status = EnvironmentStatus.DRIFT_DETECTED
            elif drift_count > 0:
                status = EnvironmentStatus.SYNC_NEEDED
            else:
                status = EnvironmentStatus.HEALTHY
            
            # Get last sync time (use fabric's last_git_sync for now)
            last_sync = self.fabric.last_git_sync
            
            # Get last commit (use fabric's desired_state_commit)
            last_commit = self.fabric.desired_state_commit or ""
            
            return EnvironmentHealth(
                environment=environment,
                status=status,
                last_sync=last_sync,
                resource_count=resource_count,
                drift_count=drift_count,
                error_count=error_count,
                last_commit=last_commit,
                branch=config.branch
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get health for environment '{environment}': {e}")
            return EnvironmentHealth(
                environment=environment,
                status=EnvironmentStatus.ERROR,
                last_sync=None,
                resource_count=0,
                drift_count=0,
                error_count=1,
                last_commit="",
                branch=config.branch
            )
    
    async def get_all_environment_health(self) -> Dict[str, EnvironmentHealth]:
        """
        Get health status for all environments.
        
        Returns:
            Dictionary mapping environment names to EnvironmentHealth objects
        """
        health_data = {}
        
        for env_name in self.environments:
            health = await self.get_environment_health(env_name)
            if health:
                health_data[env_name] = health
        
        return health_data
    
    def _get_cache_key(self, base_branch: str, head_branch: str) -> str:
        """Generate cache key for branch comparison."""
        return f"{self.fabric.pk}:{base_branch}:{head_branch}"
    
    def _is_cache_valid(self, cache_time: datetime) -> bool:
        """Check if cached comparison is still valid."""
        return timezone.now() - cache_time < self._cache_ttl
    
    async def compare_environment_branches(
        self, 
        base_env: str, 
        head_env: str,
        force_refresh: bool = False
    ) -> Optional[BranchComparison]:
        """
        Compare branches between two environments.
        
        Args:
            base_env: Base environment name
            head_env: Head environment name
            force_refresh: Force refresh of cached data
            
        Returns:
            BranchComparison object or None if comparison failed
        """
        base_config = self.get_environment_config(base_env)
        head_config = self.get_environment_config(head_env)
        
        if not base_config or not head_config:
            self.logger.error(f"Invalid environments: {base_env}, {head_env}")
            return None
        
        base_branch = base_config.branch
        head_branch = head_config.branch
        
        # Check cache first
        cache_key = self._get_cache_key(base_branch, head_branch)
        if not force_refresh and cache_key in self._comparison_cache:
            cached_data, cache_time = self._comparison_cache[cache_key]
            if self._is_cache_valid(cache_time):
                self.logger.debug(f"Using cached comparison for {base_branch}..{head_branch}")
                return cached_data
        
        try:
            # For now, create a simulated comparison
            # In the real implementation, this would use Git operations
            comparison = await self._simulate_branch_comparison(base_branch, head_branch)
            
            # Cache the result
            self._comparison_cache[cache_key] = (comparison, timezone.now())
            
            return comparison
            
        except Exception as e:
            self.logger.error(f"Failed to compare {base_branch}..{head_branch}: {e}")
            return None
    
    async def _simulate_branch_comparison(
        self, 
        base_branch: str, 
        head_branch: str
    ) -> BranchComparison:
        """
        Simulate branch comparison for demonstration.
        
        In a real implementation, this would use Git operations
        or provider API to get actual comparison data.
        """
        import random
        
        # Simulate comparison data
        ahead_by = random.randint(0, 10)
        behind_by = random.randint(0, 5)
        files_changed = random.randint(1, 15)
        additions = random.randint(10, 100)
        deletions = random.randint(0, 50)
        
        # Determine status
        if ahead_by == 0 and behind_by == 0:
            status = "identical"
        elif ahead_by > 0 and behind_by == 0:
            status = "ahead"
        elif ahead_by == 0 and behind_by > 0:
            status = "behind"
        else:
            status = "diverged"
        
        # Simulate commits
        commits = []
        for i in range(min(ahead_by, 5)):
            commits.append({
                'sha': f"abc{i:04d}{'x' * 36}",
                'message': f"Update configuration #{i + 1}",
                'author': 'Git Operations Agent',
                'date': (timezone.now() - timedelta(hours=i + 1)).isoformat()
            })
        
        # Simulate changed files
        changed_files = []
        for i in range(min(files_changed, 10)):
            changed_files.append({
                'filename': f"hedgehog/resource-{i + 1}.yaml",
                'status': random.choice(['modified', 'added', 'deleted']),
                'additions': random.randint(1, 20),
                'deletions': random.randint(0, 10)
            })
        
        return BranchComparison(
            base_branch=base_branch,
            head_branch=head_branch,
            ahead_by=ahead_by,
            behind_by=behind_by,
            status=status,
            total_commits=ahead_by,
            files_changed=files_changed,
            additions=additions,
            deletions=deletions,
            has_conflicts=random.choice([True, False]) if status == "diverged" else False,
            commits=commits,
            changed_files=changed_files
        )
    
    async def detect_cross_environment_drift(self) -> Dict[str, Any]:
        """
        Detect drift across all environments.
        
        Returns:
            Dictionary with drift detection results
        """
        drift_results = {
            'environments': {},
            'comparisons': {},
            'summary': {
                'total_environments': len(self.environments),
                'healthy_environments': 0,
                'environments_with_drift': 0,
                'total_drift_count': 0
            },
            'timestamp': timezone.now().isoformat()
        }
        
        # Get health for all environments
        health_data = await self.get_all_environment_health()
        
        for env_name, health in health_data.items():
            drift_results['environments'][env_name] = health.to_dict()
            
            if health.status == EnvironmentStatus.HEALTHY:
                drift_results['summary']['healthy_environments'] += 1
            elif health.drift_count > 0:
                drift_results['summary']['environments_with_drift'] += 1
                drift_results['summary']['total_drift_count'] += health.drift_count
        
        # Compare environments in promotion order
        env_pairs = [
            ('development', 'staging'),
            ('staging', 'production')
        ]
        
        for base_env, head_env in env_pairs:
            if base_env in self.environments and head_env in self.environments:
                comparison = await self.compare_environment_branches(base_env, head_env)
                if comparison:
                    comparison_key = f"{base_env}_to_{head_env}"
                    drift_results['comparisons'][comparison_key] = comparison.to_dict()
        
        return drift_results
    
    async def create_promotion_plan(
        self, 
        source_env: str, 
        target_env: str
    ) -> Optional[PromotionPlan]:
        """
        Create a promotion plan for moving changes between environments.
        
        Args:
            source_env: Source environment name
            target_env: Target environment name
            
        Returns:
            PromotionPlan object or None if creation failed
        """
        source_config = self.get_environment_config(source_env)
        target_config = self.get_environment_config(target_env)
        
        if not source_config or not target_config:
            self.logger.error(f"Invalid environments: {source_env}, {target_env}")
            return None
        
        try:
            # Compare branches to understand what needs to be promoted
            comparison = await self.compare_environment_branches(target_env, source_env)
            if not comparison:
                return None
            
            # Determine resources to promote
            resources_to_promote = []
            conflicts = []
            
            # Simulate resource analysis
            for changed_file in comparison.changed_files:
                resource_info = {
                    'file': changed_file['filename'],
                    'status': changed_file['status'],
                    'changes': {
                        'additions': changed_file['additions'],
                        'deletions': changed_file['deletions']
                    }
                }
                
                # Check for potential conflicts
                if changed_file['status'] == 'modified' and changed_file['deletions'] > 5:
                    conflicts.append({
                        'file': changed_file['filename'],
                        'type': 'significant_deletion',
                        'description': f"File has {changed_file['deletions']} deletions"
                    })
                
                resources_to_promote.append(resource_info)
            
            # Determine approvals required
            approvals_required = []
            if target_config.require_approval:
                approvals_required.append(f"{target_env}_maintainer")
                if target_config.env_type == EnvironmentType.PRODUCTION:
                    approvals_required.append("production_admin")
            
            # Estimate duration
            base_duration = len(resources_to_promote) * 30  # 30 seconds per resource
            if conflicts:
                base_duration += len(conflicts) * 120  # 2 minutes per conflict
            estimated_duration = timedelta(seconds=base_duration)
            
            # Risk assessment
            risk_level = "LOW"
            if comparison.has_conflicts:
                risk_level = "HIGH"
            elif len(conflicts) > 0:
                risk_level = "MEDIUM"
            elif comparison.ahead_by > 10:
                risk_level = "MEDIUM"
            
            risk_assessment = f"{risk_level} - {len(resources_to_promote)} resources, {len(conflicts)} conflicts"
            
            # Determine status
            status = PromotionStatus.READY
            if conflicts:
                status = PromotionStatus.BLOCKED
            elif approvals_required:
                status = PromotionStatus.BLOCKED  # Pending approvals
            
            return PromotionPlan(
                source_env=source_env,
                target_env=target_env,
                status=status,
                resources_to_promote=resources_to_promote,
                conflicts=conflicts,
                approvals_required=approvals_required,
                estimated_duration=estimated_duration,
                risk_assessment=risk_assessment
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create promotion plan {source_env} -> {target_env}: {e}")
            return None
    
    async def get_promotion_pipeline_status(self) -> Dict[str, Any]:
        """
        Get status of the entire promotion pipeline.
        
        Returns:
            Dictionary with pipeline status information
        """
        pipeline_status = {
            'environments': {},
            'promotion_plans': {},
            'pipeline_health': 'UNKNOWN',
            'next_promotions': [],
            'blocked_promotions': [],
            'timestamp': timezone.now().isoformat()
        }
        
        # Get environment health
        health_data = await self.get_all_environment_health()
        for env_name, health in health_data.items():
            pipeline_status['environments'][env_name] = health.to_dict()
        
        # Check promotion readiness
        promotion_pairs = [
            ('development', 'staging'),
            ('staging', 'production')
        ]
        
        healthy_envs = 0
        total_envs = len(self.environments)
        
        for source_env, target_env in promotion_pairs:
            if source_env in self.environments and target_env in self.environments:
                promotion_plan = await self.create_promotion_plan(source_env, target_env)
                if promotion_plan:
                    plan_key = f"{source_env}_to_{target_env}"
                    pipeline_status['promotion_plans'][plan_key] = promotion_plan.to_dict()
                    
                    if promotion_plan.status == PromotionStatus.READY:
                        pipeline_status['next_promotions'].append(plan_key)
                    elif promotion_plan.status == PromotionStatus.BLOCKED:
                        pipeline_status['blocked_promotions'].append(plan_key)
        
        # Calculate overall pipeline health
        for env_name in self.environments:
            if env_name in health_data:
                health = health_data[env_name]
                if health.status in [EnvironmentStatus.HEALTHY, EnvironmentStatus.SYNC_NEEDED]:
                    healthy_envs += 1
        
        if healthy_envs == total_envs:
            pipeline_status['pipeline_health'] = 'HEALTHY'
        elif healthy_envs >= total_envs * 0.7:
            pipeline_status['pipeline_health'] = 'DEGRADED'
        else:
            pipeline_status['pipeline_health'] = 'CRITICAL'
        
        return pipeline_status
    
    async def get_frontend_data(self) -> Dict[str, Any]:
        """
        Get comprehensive data for Frontend Agent UI.
        
        Returns:
            Dictionary with all multi-environment data for UI
        """
        frontend_data = {
            'fabric': {
                'id': self.fabric.pk,
                'name': self.fabric.name,
                'repository_url': self.fabric.git_repository_url,
                'primary_branch': self.fabric.git_branch or 'main'
            },
            'environments': {},
            'comparisons': {},
            'pipeline': {},
            'summary': {
                'total_environments': len(self.environments),
                'healthy_environments': 0,
                'total_resources': 0,
                'total_drift': 0
            },
            'timestamp': timezone.now().isoformat()
        }
        
        # Get environment health data
        health_data = await self.get_all_environment_health()
        for env_name, health in health_data.items():
            frontend_data['environments'][env_name] = health.to_dict()
            
            # Update summary
            if health.status == EnvironmentStatus.HEALTHY:
                frontend_data['summary']['healthy_environments'] += 1
            frontend_data['summary']['total_resources'] += health.resource_count
            frontend_data['summary']['total_drift'] += health.drift_count
        
        # Get branch comparisons
        env_pairs = [
            ('development', 'staging'),
            ('staging', 'production'),
            ('development', 'production')
        ]
        
        for base_env, head_env in env_pairs:
            if base_env in self.environments and head_env in self.environments:
                comparison = await self.compare_environment_branches(base_env, head_env)
                if comparison:
                    comparison_key = f"{base_env}_to_{head_env}"
                    frontend_data['comparisons'][comparison_key] = comparison.to_dict()
        
        # Get pipeline status
        pipeline_status = await self.get_promotion_pipeline_status()
        frontend_data['pipeline'] = pipeline_status
        
        return frontend_data


class EnvironmentManagerError(Exception):
    """Base exception for EnvironmentManager operations."""
    pass


class EnvironmentNotFoundError(EnvironmentManagerError):
    """Environment configuration not found."""
    pass


class PromotionBlockedError(EnvironmentManagerError):
    """Promotion is blocked due to conflicts or missing approvals."""
    pass