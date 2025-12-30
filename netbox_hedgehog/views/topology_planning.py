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


def _require_topologyplan_change_permission(request, plan=None):
    """
    Check change_topologyplan permission.

    Supports both model-level and object-level (ObjectPermission) checks.

    Args:
        request: HTTP request with user
        plan: Optional TopologyPlan instance for object-level permission check

    Raises:
        PermissionDenied: If user lacks permission
    """
    if plan is not None:
        # Object-level permission check (supports ObjectPermission)
        if not request.user.has_perm('netbox_hedgehog.change_topologyplan', plan):
            raise PermissionDenied
    else:
        # Model-level permission check
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
        """Add server classes, switch classes, connections, and permissions to context"""
        # Get all server connections for this plan (via server_class FK)
        server_connections = models.PlanServerConnection.objects.filter(
            server_class__plan=instance
        ).select_related('server_class', 'target_switch_class')

        # Check if user can generate devices (object-level permission + DCIM perms)
        can_generate_devices = self._can_user_generate_devices(request, instance)

        return {
            'server_classes': instance.server_classes.all(),
            'switch_classes': instance.switch_classes.all(),
            'server_connections': server_connections,
            'can_generate_devices': can_generate_devices,
        }

    def _can_user_generate_devices(self, request, instance):
        """
        Check if user has all permissions required to generate devices.

        Requires:
        - Object-level change_topologyplan permission (supports ObjectPermission)
        - All DCIM permissions (add/delete device, add interface, add/delete cable)

        Args:
            request: HTTP request with user
            instance: TopologyPlan instance

        Returns:
            bool: True if user has all required permissions
        """
        # Required DCIM permissions
        required_perms = [
            'dcim.add_device',
            'dcim.delete_device',
            'dcim.add_interface',
            'dcim.add_cable',
            'dcim.delete_cable',
        ]

        # Check object-level change_topologyplan permission
        if not request.user.has_perm('netbox_hedgehog.change_topologyplan', instance):
            return False

        # Check all required DCIM permissions
        for perm in required_perms:
            if not request.user.has_perm(perm):
                return False

        return True


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


class TopologyPlanGenerateUpdateView(View):
    """
    Unified generate/update action for TopologyPlans (DIET #127).

    Single endpoint that:
    1. Auto-recalculates switch quantities before generation
    2. Generates/regenerates NetBox objects via DeviceGenerator
    3. Creates/updates GenerationState with comprehensive snapshot

    Replaces dual "Generate" + "Recalculate" buttons with single unified action.

    POST: Generate or update devices based on current plan state

    Note: Permission checks are done manually inside post() to support
    both model-level and object-level (ObjectPermission) permissions.
    """

    # Required DCIM permissions for device/cable generation
    REQUIRED_DCIM_PERMISSIONS = [
        'dcim.add_device',
        'dcim.delete_device',
        'dcim.add_interface',
        'dcim.add_cable',
        'dcim.delete_cable',
    ]

    def post(self, request, pk):
        """
        Handle unified generate/update POST request.

        Workflow:
        1. Check permissions (change_topologyplan + 6 DCIM perms)
        2. Validate plan has server + switch classes
        3. Auto-recalculate switch quantities
        4. Generate/regenerate devices via DeviceGenerator
        5. Redirect to detail page with success/error message

        Args:
            request: HTTP request
            pk: TopologyPlan primary key

        Returns:
            HttpResponse redirect to detail page
        """
        # Get plan first (needed for object-level permission check)
        plan = get_object_or_404(models.TopologyPlan, pk=pk)

        # Enforce change_topologyplan permission (supports ObjectPermission)
        _require_topologyplan_change_permission(request, plan)

        # Enforce DCIM permissions (required for device/cable generation)
        self._require_dcim_permissions(request)

        # Validate plan has required classes
        if plan.server_classes.count() == 0:
            messages.error(
                request,
                "Cannot generate devices: plan requires at least one server class."
            )
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        if plan.switch_classes.count() == 0:
            messages.error(
                request,
                "Cannot generate devices: plan requires at least one switch class."
            )
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        # Step 1: Auto-recalculate switch quantities (fail-fast on calc errors)
        calc_result = update_plan_calculations(plan)
        if calc_result['errors']:
            # Show first calculation error and abort
            first_error = calc_result['errors'][0]
            switch_class_id = (
                first_error.get('switch_class_id')
                or first_error.get('switch_class')
                or 'unknown'
            )
            message = first_error.get('message') or first_error.get('error') or 'Unknown error'
            messages.error(
                request,
                f"Cannot generate devices due to calculation errors: "
                f"{switch_class_id}: {message}"
            )
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        # Step 2: Generate/regenerate devices
        generator = DeviceGenerator(plan=plan)
        try:
            result = generator.generate_all()
        except ValidationError as exc:
            messages.error(request, f"Generation failed: {' '.join(exc.messages)}")
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)
        except Exception as exc:  # pragma: no cover - safety net for UI feedback
            messages.error(request, f"Generation failed: {exc}")
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        # Success
        messages.success(
            request,
            f"Devices updated successfully: "
            f"{result.device_count} devices, "
            f"{result.interface_count} interfaces, "
            f"{result.cable_count} cables."
        )
        return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

    def _require_dcim_permissions(self, request):
        """
        Enforce DCIM permissions required for device/cable generation.

        Raises:
            PermissionDenied: If user lacks any required DCIM permission
        """
        for perm in self.REQUIRED_DCIM_PERMISSIONS:
            if not request.user.has_perm(perm):
                raise PermissionDenied(
                    f"Device generation requires '{perm}' permission. "
                    f"Contact administrator for device management permissions."
                )


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
