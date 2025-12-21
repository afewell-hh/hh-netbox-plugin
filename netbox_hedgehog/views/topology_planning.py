"""
Topology Planning Views (DIET Module)
CRUD views for BreakoutOption, DeviceTypeExtension, and Topology Plan models.
"""

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from netbox.views import generic
from .. import models, tables, forms
from ..utils.topology_calculations import update_plan_calculations


# BreakoutOption Views
class BreakoutOptionListView(generic.ObjectListView):
    """List view for BreakoutOptions"""
    queryset = models.BreakoutOption.objects.all()
    table = tables.BreakoutOptionTable
    template_name = 'netbox_hedgehog/topology_planning/breakoutoption_list.html'


class BreakoutOptionView(generic.ObjectView):
    """Detail view for a single BreakoutOption"""
    queryset = models.BreakoutOption.objects.all()
    template_name = 'netbox_hedgehog/topology_planning/breakoutoption.html'


class BreakoutOptionEditView(generic.ObjectEditView):
    """Create/Edit view for BreakoutOptions"""
    queryset = models.BreakoutOption.objects.all()
    form = forms.BreakoutOptionForm
    template_name = 'netbox_hedgehog/topology_planning/breakoutoption_edit.html'


class BreakoutOptionDeleteView(generic.ObjectDeleteView):
    """Delete view for BreakoutOptions"""
    queryset = models.BreakoutOption.objects.all()
    template_name = 'netbox_hedgehog/topology_planning/breakoutoption_delete.html'


# DeviceTypeExtension Views
class DeviceTypeExtensionListView(generic.ObjectListView):
    """List view for DeviceTypeExtensions"""
    queryset = models.DeviceTypeExtension.objects.all()
    table = tables.DeviceTypeExtensionTable
    template_name = 'netbox_hedgehog/topology_planning/devicetypeextension_list.html'


class DeviceTypeExtensionView(generic.ObjectView):
    """Detail view for a single DeviceTypeExtension"""
    queryset = models.DeviceTypeExtension.objects.all()
    template_name = 'netbox_hedgehog/topology_planning/devicetypeextension.html'


class DeviceTypeExtensionEditView(generic.ObjectEditView):
    """Create/Edit view for DeviceTypeExtensions"""
    queryset = models.DeviceTypeExtension.objects.all()
    form = forms.DeviceTypeExtensionForm
    template_name = 'netbox_hedgehog/topology_planning/devicetypeextension_edit.html'


class DeviceTypeExtensionDeleteView(generic.ObjectDeleteView):
    """Delete view for DeviceTypeExtensions"""
    queryset = models.DeviceTypeExtension.objects.all()
    template_name = 'netbox_hedgehog/topology_planning/devicetypeextension_delete.html'


# =============================================================================
# TopologyPlan Views (DIET-004)
# =============================================================================

class TopologyPlanListView(generic.ObjectListView):
    """List view for TopologyPlans"""
    queryset = models.TopologyPlan.objects.all()
    table = tables.TopologyPlanTable


class TopologyPlanView(generic.ObjectView):
    """Detail view for a single TopologyPlan"""
    queryset = models.TopologyPlan.objects.all()
    template_name = 'netbox_hedgehog/topologyplan.html'

    def get_extra_context(self, request, instance):
        """Add server and switch classes to context"""
        return {
            'server_classes': instance.server_classes.all(),
            'switch_classes': instance.switch_classes.all(),
        }


class TopologyPlanEditView(generic.ObjectEditView):
    """Create/Edit view for TopologyPlans"""
    queryset = models.TopologyPlan.objects.all()
    form = forms.TopologyPlanForm


class TopologyPlanDeleteView(generic.ObjectDeleteView):
    """Delete view for TopologyPlans"""
    queryset = models.TopologyPlan.objects.all()


class TopologyPlanRecalculateView(PermissionRequiredMixin, View):
    """
    Recalculate action for TopologyPlans.

    Triggers calculation engine to update all switch quantities
    based on current server quantities and connection requirements.
    """
    permission_required = 'netbox_hedgehog.change_topologyplan'
    raise_exception = True

    def post(self, request, pk):
        """Handle recalculate POST request"""
        plan = get_object_or_404(models.TopologyPlan, pk=pk)

        # Run calculation engine
        result = update_plan_calculations(plan)

        # Show success message
        messages.success(
            request,
            f"Recalculated {len(result)} switch classes for plan '{plan.name}'."
        )

        # Redirect back to plan detail page
        return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=pk)


# =============================================================================
# PlanServerClass Views (DIET-004)
# =============================================================================

class PlanServerClassListView(generic.ObjectListView):
    """List view for PlanServerClasses"""
    queryset = models.PlanServerClass.objects.all()
    table = tables.PlanServerClassTable


class PlanServerClassView(generic.ObjectView):
    """Detail view for a single PlanServerClass"""
    queryset = models.PlanServerClass.objects.all()
    template_name = 'netbox_hedgehog/planserverclass.html'


class PlanServerClassEditView(generic.ObjectEditView):
    """Create/Edit view for PlanServerClasses"""
    queryset = models.PlanServerClass.objects.all()
    form = forms.PlanServerClassForm


class PlanServerClassDeleteView(generic.ObjectDeleteView):
    """Delete view for PlanServerClasses"""
    queryset = models.PlanServerClass.objects.all()


# =============================================================================
# PlanSwitchClass Views (DIET-004)
# =============================================================================

class PlanSwitchClassListView(generic.ObjectListView):
    """List view for PlanSwitchClasses"""
    queryset = models.PlanSwitchClass.objects.all()
    table = tables.PlanSwitchClassTable


class PlanSwitchClassView(generic.ObjectView):
    """Detail view for a single PlanSwitchClass"""
    queryset = models.PlanSwitchClass.objects.all()
    template_name = 'netbox_hedgehog/planswitchclass.html'


class PlanSwitchClassEditView(generic.ObjectEditView):
    """Create/Edit view for PlanSwitchClasses"""
    queryset = models.PlanSwitchClass.objects.all()
    form = forms.PlanSwitchClassForm


class PlanSwitchClassDeleteView(generic.ObjectDeleteView):
    """Delete view for PlanSwitchClasses"""
    queryset = models.PlanSwitchClass.objects.all()


# =============================================================================
# PlanServerConnection Views (DIET-005)
# =============================================================================

class PlanServerConnectionListView(generic.ObjectListView):
    """List view for PlanServerConnections"""
    queryset = models.PlanServerConnection.objects.select_related(
        'server_class',
        'server_class__plan',
        'target_switch_class',
        'target_switch_class__plan'
    )
    table = tables.PlanServerConnectionTable


class PlanServerConnectionView(generic.ObjectView):
    """Detail view for a single PlanServerConnection"""
    queryset = models.PlanServerConnection.objects.select_related(
        'server_class',
        'server_class__plan',
        'target_switch_class',
        'target_switch_class__plan',
        'nic_module_type'
    )


class PlanServerConnectionEditView(generic.ObjectEditView):
    """Create/Edit view for PlanServerConnections"""
    queryset = models.PlanServerConnection.objects.all()
    form = forms.PlanServerConnectionForm


class PlanServerConnectionDeleteView(generic.ObjectDeleteView):
    """Delete view for PlanServerConnections"""
    queryset = models.PlanServerConnection.objects.all()
