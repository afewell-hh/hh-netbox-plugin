"""
Fabric Service Interface
Abstract interface for fabric management operations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class FabricStats:
    """Fabric statistics summary"""
    total_crds: int
    active_crds: int
    error_crds: int
    sync_status: str
    drift_count: int
    last_sync: Optional[str]


@dataclass
class SyncResult:
    """Fabric sync operation result"""
    success: bool
    stats: FabricStats
    errors: List[str]
    details: Dict[str, Any]


class FabricServiceInterface(ABC):
    """Abstract interface for fabric management operations"""
    
    @abstractmethod
    def get_fabric_statistics(self, fabric) -> FabricStats:
        """
        Get comprehensive fabric statistics.
        
        Args:
            fabric: HedgehogFabric instance
            
        Returns:
            FabricStats with current statistics
        """
        pass
    
    @abstractmethod
    def sync_fabric_from_git(self, fabric) -> SyncResult:
        """
        Synchronize fabric CRDs from Git repository.
        
        Args:
            fabric: HedgehogFabric instance
            
        Returns:
            SyncResult with operation details
            
        Raises:
            FabricError: If sync operation fails
        """
        pass
    
    @abstractmethod
    def validate_fabric_configuration(self, fabric) -> Dict[str, Any]:
        """
        Validate fabric configuration.
        
        Args:
            fabric: HedgehogFabric instance
            
        Returns:
            Validation result with status and details
        """
        pass
    
    @abstractmethod
    def calculate_drift_status(self, fabric) -> Dict[str, Any]:
        """
        Calculate drift status between desired and actual state.
        
        Args:
            fabric: HedgehogFabric instance
            
        Returns:
            Drift analysis result
        """
        pass
    
    @abstractmethod
    def get_gitops_summary(self, fabric) -> Dict[str, Any]:
        """
        Get GitOps configuration summary.
        
        Args:
            fabric: HedgehogFabric instance
            
        Returns:
            GitOps configuration and status summary
        """
        pass