"""
URL Configuration for Drift Detection Dashboard
Integrates drift detection functionality into NetBox Hedgehog Plugin
"""

from django.urls import path
from ..views.drift_dashboard_view import (
    DriftDetectionDashboardView,
    FabricDriftDetailView,
    ResourceDriftDetailView,
    DriftAnalysisAPIView
)
from ..api.drift_api_endpoints import (
    DriftDashboardAPIView,
    FabricDriftAnalysisAPIView,
    ResourceDriftDetailAPIView,
    DriftSyncAPIView,
    DriftExportAPIView
)

# URL patterns to add to main netbox_hedgehog/urls.py
drift_urlpatterns = [
    # Main drift detection dashboard
    path('drift-detection/', DriftDetectionDashboardView.as_view(), name='drift_dashboard'),
    
    # Fabric-specific drift analysis
    path('drift-detection/fabric/<int:fabric_id>/', FabricDriftDetailView.as_view(), name='fabric_drift_detail'),
    
    # Resource-specific drift details
    path('drift-detection/resource/<int:resource_id>/', ResourceDriftDetailView.as_view(), name='resource_drift_detail'),
    
    # Legacy API endpoint (keep for backwards compatibility)
    path('api/drift-analysis/', DriftAnalysisAPIView.as_view(), name='drift_analysis_api'),
]

# API URL patterns to add to netbox_hedgehog/api/urls.py
drift_api_urlpatterns = [
    # Main dashboard API
    path('drift/dashboard/', DriftDashboardAPIView.as_view(), name='drift_dashboard_api'),
    
    # Fabric drift analysis API
    path('drift/fabric/<int:fabric_id>/', FabricDriftAnalysisAPIView.as_view(), name='fabric_drift_api'),
    
    # Resource drift details API
    path('drift/resource/<int:resource_id>/', ResourceDriftDetailAPIView.as_view(), name='resource_drift_api'),
    
    # Sync operations API
    path('drift/sync/', DriftSyncAPIView.as_view(), name='drift_sync_api'),
    
    # Export API
    path('drift/export/', DriftExportAPIView.as_view(), name='drift_export_api'),
]

# Integration instructions for main URL files:
"""
Add to netbox_hedgehog/urls.py:

# Import the drift URL patterns
from .drift_dashboard.urls.drift_urls import drift_urlpatterns

# Add to urlpatterns list:
urlpatterns = [
    # ... existing patterns ...
] + drift_urlpatterns

Add to netbox_hedgehog/api/urls.py:

# Import the drift API URL patterns  
from ..drift_dashboard.urls.drift_urls import drift_api_urlpatterns

# Add to router or urlpatterns:
urlpatterns = [
    # ... existing patterns ...
] + drift_api_urlpatterns
"""