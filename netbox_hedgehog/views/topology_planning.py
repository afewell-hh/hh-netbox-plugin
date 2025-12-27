"""
Topology Planning Views (DIET Module)
CRUD views for BreakoutOption, DeviceTypeExtension, and Topology Plan models.
"""

import re
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from netbox.views import generic
from .. import models, tables, forms
from ..services.device_generator import DeviceGenerator
from ..utils.topology_calculations import update_plan_calculations
from ..services.yaml_generator import generate_yaml_for_plan


def _require_topologyplan_change_permission(request):
    if not request.user.has_perm('netbox_hedgehog.change_topologyplan'):
        raise PermissionDenied


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
        """Add server classes, switch classes, and connections to context"""
        # Get all server connections for this plan (via server_class FK)
        server_connections = models.PlanServerConnection.objects.filter(
            server_class__plan=instance
        ).select_related('server_class', 'target_switch_class')

        return {
            'server_classes': instance.server_classes.all(),
            'switch_classes': instance.switch_classes.all(),
            'server_connections': server_connections,
        }


class TopologyPlanEditView(generic.ObjectEditView):
    """Create/Edit view for TopologyPlans"""
    queryset = models.TopologyPlan.objects.all()
    form = forms.TopologyPlanForm


class TopologyPlanDeleteView(generic.ObjectDeleteView):
    """Delete view for TopologyPlans"""
    queryset = models.TopologyPlan.objects.all()


class TopologyPlanGenerateView(PermissionRequiredMixin, View):
    """
    Preview and generate NetBox objects for a topology plan.

    GET: show preview counts and warnings
    POST: run generation via DeviceGenerator
    """
    permission_required = 'netbox_hedgehog.change_topologyplan'
    raise_exception = True
    template_name = 'netbox_hedgehog/topology_planning/topologyplan_generate.html'

    def get(self, request, pk):
        _require_topologyplan_change_permission(request)
        plan = get_object_or_404(models.TopologyPlan, pk=pk)
        context = self._build_context(plan)
        return render(request, self.template_name, context)

    def post(self, request, pk):
        _require_topologyplan_change_permission(request)
        plan = get_object_or_404(models.TopologyPlan, pk=pk)
        if plan.server_classes.count() == 0 or plan.switch_classes.count() == 0:
            messages.error(
                request,
                "Generation requires at least one server class and one switch class."
            )
            return redirect('plugins:netbox_hedgehog:topologyplan_generate', pk=plan.pk)

        generator = DeviceGenerator(plan=plan)
        try:
            result = generator.generate_all()
        except ValidationError as exc:
            messages.error(request, f"Generation failed: {' '.join(exc.messages)}")
            return redirect('plugins:netbox_hedgehog:topologyplan_generate', pk=plan.pk)
        except Exception as exc:  # pragma: no cover - safety net for UI feedback
            messages.error(request, f"Generation failed: {exc}")
            return redirect('plugins:netbox_hedgehog:topologyplan_generate', pk=plan.pk)

        messages.success(
            request,
            "Generation complete: "
            f"{result.device_count} devices, "
            f"{result.interface_count} interfaces, "
            f"{result.cable_count} cables."
        )
        return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

    def _build_context(self, plan):
        server_classes = plan.server_classes.prefetch_related('connections')
        switch_classes = plan.switch_classes.all()

        server_count = sum(sc.quantity for sc in server_classes)
        switch_count = sum(sc.effective_quantity for sc in switch_classes)
        port_count = sum(
            sc.quantity * connection.ports_per_connection
            for sc in server_classes
            for connection in sc.connections.all()
        )

        return {
            'object': plan,
            'server_count': server_count,
            'switch_count': switch_count,
            'total_devices': server_count + switch_count,
            'interface_count': port_count * 2,
            'cable_count': port_count,
            'generation_state': getattr(plan, 'generation_state', None),
            'needs_regeneration': plan.needs_regeneration,
            'site_name': DeviceGenerator.DEFAULT_SITE_NAME,
        }


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
        _require_topologyplan_change_permission(request)
        plan = get_object_or_404(models.TopologyPlan, pk=pk)

        # Run calculation engine
        result = update_plan_calculations(plan)

        # Show success message for successfully calculated switches
        if result['summary']:
            messages.success(
                request,
                f"Recalculated {len(result['summary'])} switch classes for plan '{plan.name}'."
            )

        # Show error messages for any validation errors
        if result['errors']:
            for error_info in result['errors']:
                messages.error(
                    request,
                    f"Error calculating '{error_info['switch_class']}': {error_info['error']}"
                )

        # Redirect back to plan detail page
        return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=pk)


class TopologyPlanExportView(PermissionRequiredMixin, View):
    """
    Export action for TopologyPlans (DIET-006).

    Generates Hedgehog wiring diagram YAML from a topology plan
    and returns it as a downloadable file.

    Automatically runs calculation engine before export to ensure
    switch quantities are up-to-date.

    Requires change_topologyplan permission (not just view) because
    the auto-calculation mutates data by saving calculated_quantity.
    """
    permission_required = 'netbox_hedgehog.change_topologyplan'
    raise_exception = True

    def get(self, request, pk):
        """Handle export GET request"""
        _require_topologyplan_change_permission(request)
        plan = get_object_or_404(models.TopologyPlan, pk=pk)

        # Auto-calculate switch quantities before export
        # This ensures effective_quantity is populated even if user hasn't clicked Recalculate
        result = update_plan_calculations(plan)

        # Warn user if there were calculation errors (but continue with export)
        if result['errors']:
            for error_info in result['errors']:
                messages.warning(
                    request,
                    f"Calculation error for '{error_info['switch_class']}': {error_info['error']}. "
                    "Export will use existing quantities."
                )

        # Generate YAML from plan
        yaml_content = generate_yaml_for_plan(plan)

        # Create filename from plan name (sanitize for filesystem)
        filename = re.sub(r'[^a-z0-9-]', '-', plan.name.lower())
        filename = re.sub(r'-+', '-', filename)  # Collapse multiple dashes
        filename = filename.strip('-')  # Remove leading/trailing dashes
        filename = f"{filename}.yaml"

        # Create HTTP response with YAML content
        response = HttpResponse(yaml_content, content_type='text/yaml; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response


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


# =============================================================================
# SwitchPortZone Views (DIET-011)
# =============================================================================

class SwitchPortZoneListView(generic.ObjectListView):
    """List view for SwitchPortZones"""
    queryset = models.SwitchPortZone.objects.select_related(
        'switch_class',
        'switch_class__plan',
        'breakout_option',
    )
    table = tables.SwitchPortZoneTable
    template_name = 'netbox_hedgehog/topology_planning/switchportzone_list.html'


class SwitchPortZoneView(generic.ObjectView):
    """Detail view for a single SwitchPortZone"""
    queryset = models.SwitchPortZone.objects.select_related(
        'switch_class',
        'switch_class__plan',
        'breakout_option',
    )
    template_name = 'netbox_hedgehog/topology_planning/switchportzone.html'


class SwitchPortZoneEditView(generic.ObjectEditView):
    """Create/Edit view for SwitchPortZones"""
    queryset = models.SwitchPortZone.objects.all()
    form = forms.SwitchPortZoneForm
    template_name = 'netbox_hedgehog/topology_planning/switchportzone_edit.html'


class SwitchPortZoneDeleteView(generic.ObjectDeleteView):
    """Delete view for SwitchPortZones"""
    queryset = models.SwitchPortZone.objects.all()
    template_name = 'netbox_hedgehog/topology_planning/switchportzone_delete.html'
