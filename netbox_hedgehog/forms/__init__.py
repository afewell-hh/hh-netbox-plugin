# Legacy forms (for compatibility)
from .fabric import FabricForm as LegacyFabricForm
from .vpc_api import VPCForm as LegacyVPCForm, ExternalForm, IPv4NamespaceForm as LegacyIPv4NamespaceForm
from .wiring_api import ConnectionForm as LegacyConnectionForm, SwitchForm as LegacySwitchForm, ServerForm as LegacyServerForm

# Enhanced forms (Phase 4)
from .fabric_forms import (
    HedgehogFabricForm,
    FabricOnboardingForm,
    ConnectionTestForm,
    KubeconfigUploadForm,
    ReconciliationSettingsForm,
    BulkFabricOperationsForm,
)

from .vpc_forms import (
    VPCForm,
    VPCCreateForm,
    VPCCustomForm,
    VPCApplyForm,
    VPCBulkActionsForm,
    SubnetConfigForm,
    SubnetConfigFormSet,
    IPv4NamespaceForm,
    VLANNamespaceForm,
)

from .wiring_forms import (
    SwitchForm,
    ConnectionForm,
    ConnectionLinkForm,
    ConnectionLinkFormSet,
    ServerForm,
    SwitchGroupForm,
    TopologyFilterForm,
    BulkSwitchOperationsForm,
    ConnectionTestForm,
)

__all__ = [
    # Enhanced fabric forms (Phase 4)
    'HedgehogFabricForm',
    'FabricOnboardingForm',
    'ConnectionTestForm',
    'KubeconfigUploadForm',
    'ReconciliationSettingsForm',
    'BulkFabricOperationsForm',
    
    # Enhanced VPC forms (Phase 4)
    'VPCForm',
    'VPCCreateForm',
    'VPCCustomForm',
    'VPCApplyForm',
    'VPCBulkActionsForm',
    'SubnetConfigForm',
    'SubnetConfigFormSet',
    'IPv4NamespaceForm',
    'VLANNamespaceForm',
    
    # Enhanced wiring forms (Phase 4)
    'SwitchForm',
    'ConnectionForm',
    'ConnectionLinkForm',
    'ConnectionLinkFormSet',
    'ServerForm',
    'SwitchGroupForm',
    'TopologyFilterForm',
    'BulkSwitchOperationsForm',
    'ConnectionTestForm',
    
    # Legacy forms (for compatibility)
    'LegacyFabricForm',
    'LegacyVPCForm',
    'ExternalForm',
    'LegacyIPv4NamespaceForm',
    'LegacyConnectionForm',
    'LegacySwitchForm',
    'LegacyServerForm',
]