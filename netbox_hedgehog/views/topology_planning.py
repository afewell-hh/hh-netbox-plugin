"""
Topology Planning Views (DIET Module)
CRUD views for BreakoutOption, DeviceTypeExtension, and Topology Plan models.
"""

import re
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html
from django.views import View

from dcim.models import Device, Cable

from netbox.views import generic
from .. import models, tables, forms, choices
from ..services.device_generator import DeviceGenerator
from ..utils.topology_calculations import update_plan_calculations
from ..services.yaml_generator import generate_yaml_for_plan
from ..jobs.device_generation import DeviceGenerationJob


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

        # Calculate expected counts for modal data attributes
        server_classes = instance.server_classes.prefetch_related('connections')
        switch_classes = instance.switch_classes.all()

        server_count = sum(sc.quantity for sc in server_classes)
        switch_count = sum(sc.effective_quantity for sc in switch_classes)
        port_count = sum(
            sc.quantity * connection.ports_per_connection
            for sc in server_classes
            for connection in sc.connections.all()
        )

        expected_device_count = server_count + switch_count
        expected_interface_count = port_count * 2  # Each cable has 2 interfaces
        expected_cable_count = port_count

        # Check if this is first-time generation (no devices exist yet)
        has_existing_devices = (
            hasattr(instance, 'generation_state') and
            instance.generation_state.device_count > 0
        )
        is_first_time = not has_existing_devices
        is_destructive = has_existing_devices

        return {
            'server_classes': instance.server_classes.all(),
            'switch_classes': instance.switch_classes.all(),
            'server_connections': server_connections,
            'can_generate_devices': can_generate_devices,
            'is_first_time_generation': is_first_time,
            'is_destructive_regeneration': is_destructive,
            'expected_device_count': expected_device_count,
            'expected_interface_count': expected_interface_count,
            'expected_cable_count': expected_cable_count,
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

        # Step 1: Check if plan is already locked (QUEUED or IN_PROGRESS)
        if hasattr(plan, 'generation_state'):
            status = plan.generation_state.status
            job = plan.generation_state.job

            # Allow re-enqueue if job was deleted (orphaned state)
            if status in [GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS] and job is not None:
                status_label = "queued" if status == GenerationStatusChoices.QUEUED else "in progress"
                messages.error(
                    request,
                    f"Cannot start generation: a job is already {status_label} for this plan. "
                    "Wait for the current job to complete before starting a new one."
                )
                return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

            # If job is None but status is QUEUED/IN_PROGRESS, reset to FAILED
            # This handles the orphaned job scenario (user deleted job from Jobs page)
            if status in [GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS] and job is None:
                plan.generation_state.status = GenerationStatusChoices.FAILED
                plan.generation_state.save()
                messages.warning(
                    request,
                    "Previous job was deleted. Resetting generation state to allow new generation."
                )

        # Step 2: Auto-recalculate switch quantities (fail-fast on calc errors)
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

        # Step 3: Enqueue background job for device generation
        # Create/update GenerationState with QUEUED status
        state, created = models.GenerationState.objects.update_or_create(
            plan=plan,
            defaults={
                'status': GenerationStatusChoices.QUEUED,
                'device_count': 0,
                'interface_count': 0,
                'cable_count': 0,
                'snapshot': {},
            }
        )

        # Get timeout from plugin config (default: 3600 seconds = 1 hour)
        plugin_config = settings.PLUGINS_CONFIG.get('netbox_hedgehog', {})
        timeout = plugin_config.get('device_generation_timeout', 3600)

        # Enqueue DeviceGenerationJob (passing plan_id as arg, not instance)
        job = DeviceGenerationJob.enqueue(
            name=f"Generate devices for plan: {plan.name}",
            user=request.user,
            plan_id=plan.pk,
            timeout=timeout,
        )

        # Link job to GenerationState
        state.job = job
        state.save()

        # Redirect to NetBox Job detail page
        return redirect(job.get_absolute_url())

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
    Export action for TopologyPlans (DIET-139).

    Generates Hedgehog wiring diagram YAML from a topology plan's NetBox inventory
    (Devices, Interfaces, Cables created by device generation).

    IMPORTANT: Export is inventory-based and read-only.
    - Requires device generation to be completed before export
    - Does NOT mutate the plan (removed update_plan_calculations call)
    - Reads actual NetBox Interface names for port naming (including breakout suffixes)

    Requires change_topologyplan permission for historical reasons (permission model unchanged).
    """
    permission_required = 'netbox_hedgehog.change_topologyplan'
    raise_exception = True

    def get(self, request, pk):
        """Handle export GET request with precondition validation (DIET-139)"""
        _require_topologyplan_change_permission(request)
        plan = get_object_or_404(models.TopologyPlan, pk=pk)

        # ===== PRECONDITION VALIDATION (DIET-139) =====
        # Export requires device generation to be completed

        # Check 1: Generation state must exist
        try:
            generation_state = plan.generation_state
        except AttributeError:
            return HttpResponseBadRequest(
                "Device generation has not been run for this plan. "
                "Click 'Generate Devices' to create NetBox inventory first."
            )

        # Check 2: Generation status must be GENERATED
        if generation_state.status != choices.GenerationStatusChoices.GENERATED:
            return HttpResponseBadRequest(
                f"Device generation status is '{generation_state.status}'. "
                f"Complete device generation before exporting YAML."
            )

        # Check 3: Devices must exist in NetBox
        device_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()
        if device_count == 0:
            return HttpResponseBadRequest(
                "No devices found in NetBox inventory for this plan. "
                "Device generation may have failed or devices were deleted."
            )

        # Check 4: Cables must exist in NetBox
        cable_count = Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()
        if cable_count == 0:
            return HttpResponseBadRequest(
                "No cables found in NetBox inventory for this plan. "
                "Device generation may have failed or is incomplete."
            )

        # ===== GENERATE YAML FROM INVENTORY (DIET-139) =====
        # Do NOT call update_plan_calculations - export is read-only

        # Generate YAML from NetBox inventory (not from plan allocation)
        try:
            yaml_content = generate_yaml_for_plan(plan)
        except Exception as e:
            return HttpResponseBadRequest(
                f"YAML generation failed: {str(e)}"
            )

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

    def dispatch(self, request, *args, **kwargs):
        """Check if plan is locked before allowing edit or create"""
        from netbox_hedgehog.models import TopologyPlan

        plan = None

        # For edit, get plan from existing object
        if kwargs.get('pk'):
            obj = get_object_or_404(self.queryset, pk=kwargs['pk'])
            plan = obj.plan
        # For create, get plan from query param or POST data
        else:
            plan_id = request.GET.get('plan') or request.POST.get('plan')
            if plan_id:
                try:
                    plan = TopologyPlan.objects.get(pk=plan_id)
                except TopologyPlan.DoesNotExist:
                    pass  # Let form validation handle invalid plan

        # Check if plan is locked
        if plan and self._is_plan_locked(plan, request):
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        return super().dispatch(request, *args, **kwargs)

    def _is_plan_locked(self, plan, request):
        """Check if plan is locked during generation"""
        if hasattr(plan, 'generation_state'):
            if plan.generation_state.status in [GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS]:
                messages.error(
                    request,
                    "Cannot modify plan during device generation. Wait for job to complete."
                )
                return True
        return False


class PlanServerClassDeleteView(generic.ObjectDeleteView):
    """Delete view for PlanServerClasses"""
    queryset = models.PlanServerClass.objects.all()

    def dispatch(self, request, *args, **kwargs):
        """Check if plan is locked before allowing delete"""
        obj = get_object_or_404(self.queryset, pk=kwargs['pk'])
        if hasattr(obj.plan, 'generation_state'):
            if obj.plan.generation_state.status in [GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS]:
                messages.error(
                    request,
                    "Cannot modify plan during device generation. Wait for job to complete."
                )
                return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=obj.plan.pk)
        return super().dispatch(request, *args, **kwargs)


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

    def dispatch(self, request, *args, **kwargs):
        """Check if plan is locked before allowing edit or create"""
        from netbox_hedgehog.models import TopologyPlan

        plan = None

        # For edit, get plan from existing object
        if kwargs.get('pk'):
            obj = get_object_or_404(self.queryset, pk=kwargs['pk'])
            plan = obj.plan
        # For create, get plan from query param or POST data
        else:
            plan_id = request.GET.get('plan') or request.POST.get('plan')
            if plan_id:
                try:
                    plan = TopologyPlan.objects.get(pk=plan_id)
                except TopologyPlan.DoesNotExist:
                    pass  # Let form validation handle invalid plan

        # Check if plan is locked
        if plan and hasattr(plan, 'generation_state'):
            if plan.generation_state.status in [GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS]:
                messages.error(
                    request,
                    "Cannot modify plan during device generation. Wait for job to complete."
                )
                return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        return super().dispatch(request, *args, **kwargs)


class PlanSwitchClassDeleteView(generic.ObjectDeleteView):
    """Delete view for PlanSwitchClasses"""
    queryset = models.PlanSwitchClass.objects.all()

    def dispatch(self, request, *args, **kwargs):
        """Check if plan is locked before allowing delete"""
        obj = get_object_or_404(self.queryset, pk=kwargs['pk'])
        if hasattr(obj.plan, 'generation_state'):
            if obj.plan.generation_state.status in [GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS]:
                messages.error(
                    request,
                    "Cannot modify plan during device generation. Wait for job to complete."
                )
                return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=obj.plan.pk)
        return super().dispatch(request, *args, **kwargs)


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

    def dispatch(self, request, *args, **kwargs):
        """Check if plan is locked before allowing edit or create"""
        plan = None

        # For edit, get plan from existing object
        if kwargs.get('pk'):
            obj = get_object_or_404(self.queryset, pk=kwargs['pk'])
            plan = obj.server_class.plan
        # For create, get plan from server_class in POST data
        else:
            server_class_id = request.POST.get('server_class')
            if server_class_id:
                try:
                    server_class = models.PlanServerClass.objects.get(pk=server_class_id)
                    plan = server_class.plan
                except models.PlanServerClass.DoesNotExist:
                    pass  # Let form validation handle invalid server_class

        # Check if plan is locked
        if plan and hasattr(plan, 'generation_state'):
            if plan.generation_state.status in [GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS]:
                messages.error(
                    request,
                    "Cannot modify plan during device generation. Wait for job to complete."
                )
                return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        return super().dispatch(request, *args, **kwargs)


class PlanServerConnectionDeleteView(generic.ObjectDeleteView):
    """Delete view for PlanServerConnections"""
    queryset = models.PlanServerConnection.objects.all()

    def dispatch(self, request, *args, **kwargs):
        """Check if plan is locked before allowing delete"""
        obj = get_object_or_404(self.queryset, pk=kwargs['pk'])
        if hasattr(obj.server_class.plan, 'generation_state'):
            if obj.server_class.plan.generation_state.status in [GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS]:
                messages.error(
                    request,
                    "Cannot modify plan during device generation. Wait for job to complete."
                )
                return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=obj.server_class.plan.pk)
        return super().dispatch(request, *args, **kwargs)


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
