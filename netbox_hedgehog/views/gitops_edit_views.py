from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from netbox.views import generic
from django.urls import reverse

from ..services import GitOpsEditService
from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering
from ..models.wiring_api import Connection, Server, Switch, SwitchGroup, VLANNamespace
from .. import forms
from ..forms import gitops_forms


class GitOpsEditMixin:
    """Mixin to add GitOps workflow to edit views"""
    
    def form_valid(self, form):
        """Override to integrate GitOps workflow"""
        # Get commit message from form if available
        commit_message = form.cleaned_data.get('commit_message', None)
        
        # Save the instance first (standard Django behavior)
        response = super().form_valid(form)
        
        # Apply GitOps workflow
        try:
            gitops_service = GitOpsEditService()
            result = gitops_service.update_and_commit_cr(
                cr_instance=self.object,
                form_data=form.cleaned_data,
                user=self.request.user,
                commit_message=commit_message
            )
            
            if result.get('success'):
                messages.success(
                    self.request,
                    f'Successfully updated {self.object.__class__.__name__} {self.object.name} '
                    f'and committed changes to Git. {result.get("commit_sha", "")}',
                    extra_tags='gitops-success'
                )
            else:
                messages.warning(
                    self.request,
                    f'Updated {self.object.__class__.__name__} {self.object.name} in database, '
                    f'but Git operations had issues: {result.get("error", "Unknown error")}',
                    extra_tags='gitops-warning'
                )
                
        except Exception as e:
            messages.error(
                self.request,
                f'Updated {self.object.__class__.__name__} {self.object.name} in database, '
                f'but GitOps workflow failed: {str(e)}',
                extra_tags='gitops-error'
            )
        
        return response


# VPC API Edit Views with GitOps Integration
class GitOpsVPCEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = VPC.objects.all()
    form = gitops_forms.GitOpsVPCForm
    template_name = 'netbox_hedgehog/gitops/vpc_edit.html'


class GitOpsExternalEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = External.objects.all()
    form = gitops_forms.GitOpsExternalForm
    template_name = 'netbox_hedgehog/gitops/external_edit.html'


class GitOpsExternalAttachmentEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = ExternalAttachment.objects.all()
    form = gitops_forms.GitOpsExternalAttachmentForm
    template_name = 'netbox_hedgehog/gitops/externalattachment_edit.html'


class GitOpsExternalPeeringEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = ExternalPeering.objects.all()
    form = gitops_forms.GitOpsExternalPeeringForm
    template_name = 'netbox_hedgehog/gitops/externalpeering_edit.html'


class GitOpsIPv4NamespaceEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = IPv4Namespace.objects.all()
    form = gitops_forms.GitOpsIPv4NamespaceForm
    template_name = 'netbox_hedgehog/gitops/ipv4namespace_edit.html'


class GitOpsVPCAttachmentEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = VPCAttachment.objects.all()
    form = gitops_forms.GitOpsVPCAttachmentForm
    template_name = 'netbox_hedgehog/gitops/vpcattachment_edit.html'


class GitOpsVPCPeeringEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = VPCPeering.objects.all()
    form = gitops_forms.GitOpsVPCPeeringForm
    template_name = 'netbox_hedgehog/gitops/vpcpeering_edit.html'


# Wiring API Edit Views with GitOps Integration
class GitOpsConnectionEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = Connection.objects.all()
    form = gitops_forms.GitOpsConnectionForm
    template_name = 'netbox_hedgehog/gitops/connection_edit.html'


class GitOpsServerEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = Server.objects.all()
    form = gitops_forms.GitOpsServerForm
    template_name = 'netbox_hedgehog/gitops/server_edit.html'


class GitOpsSwitchEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = Switch.objects.all()
    form = gitops_forms.GitOpsSwitchForm
    template_name = 'netbox_hedgehog/gitops/switch_edit.html'


class GitOpsSwitchGroupEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = SwitchGroup.objects.all()
    form = gitops_forms.GitOpsSwitchGroupForm
    template_name = 'netbox_hedgehog/gitops/switchgroup_edit.html'


class GitOpsVLANNamespaceEditView(GitOpsEditMixin, generic.ObjectEditView):
    queryset = VLANNamespace.objects.all()
    form = gitops_forms.GitOpsVLANNamespaceForm
    template_name = 'netbox_hedgehog/gitops/vlannamespace_edit.html'


# YAML Preview and Validation Views
class YAMLPreviewView(LoginRequiredMixin, View):
    """View for previewing YAML changes before saving"""
    
    def post(self, request):
        try:
            model_name = request.POST.get('model_name')
            object_id = request.POST.get('object_id')
            form_data = request.POST.dict()
            
            # Get the model class and instance
            model_class = self._get_model_class(model_name)
            if not model_class:
                return JsonResponse({'error': f'Unknown model: {model_name}'}, status=400)
            
            cr_instance = get_object_or_404(model_class, pk=object_id)
            
            # Generate YAML preview
            gitops_service = GitOpsEditService()
            preview_result = gitops_service.preview_yaml_changes(cr_instance, form_data)
            
            return JsonResponse({
                'success': True,
                'preview': preview_result,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=500)
    
    def _get_model_class(self, model_name: str):
        """Get model class from name"""
        model_map = {
            'VPC': VPC,
            'External': External,
            'ExternalAttachment': ExternalAttachment,
            'ExternalPeering': ExternalPeering,
            'IPv4Namespace': IPv4Namespace,
            'VPCAttachment': VPCAttachment,
            'VPCPeering': VPCPeering,
            'Connection': Connection,
            'Server': Server,
            'Switch': Switch,
            'SwitchGroup': SwitchGroup,
            'VLANNamespace': VLANNamespace,
        }
        return model_map.get(model_name)


class YAMLValidationView(LoginRequiredMixin, View):
    """View for validating YAML content"""
    
    def post(self, request):
        try:
            yaml_content = request.POST.get('yaml_content', '')
            cr_type = request.POST.get('cr_type', '')
            
            gitops_service = GitOpsEditService()
            validation_result = gitops_service.validate_yaml_schema(yaml_content, cr_type)
            
            return JsonResponse({
                'success': True,
                'validation': validation_result,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=500)


class GitOpsWorkflowStatusView(LoginRequiredMixin, View):
    """View for checking GitOps workflow status"""
    
    def get(self, request, model_name, object_id):
        try:
            # Get the model class and instance
            model_class = self._get_model_class(model_name)
            if not model_class:
                return JsonResponse({'error': f'Unknown model: {model_name}'}, status=400)
            
            cr_instance = get_object_or_404(model_class, pk=object_id)
            
            # Get GitOps status
            gitops_status = {
                'cr_name': cr_instance.name,
                'cr_type': model_name,
                'fabric_name': cr_instance.fabric.name,
                'has_git_file': bool(cr_instance.git_file_path),
                'git_file_path': cr_instance.git_file_path,
                'last_synced': cr_instance.last_synced.isoformat() if cr_instance.last_synced else None,
                'last_gui_edit': getattr(cr_instance, 'last_gui_edit', None),
                'edited_in_gui': getattr(cr_instance, 'edited_in_gui', False),
                'kubernetes_status': cr_instance.kubernetes_status,
                'sync_status': self._determine_sync_status(cr_instance)
            }
            
            return JsonResponse({
                'success': True,
                'gitops_status': gitops_status,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=500)
    
    def _get_model_class(self, model_name: str):
        """Get model class from name"""
        model_map = {
            'VPC': VPC,
            'External': External,
            'ExternalAttachment': ExternalAttachment,
            'ExternalPeering': ExternalPeering,
            'IPv4Namespace': IPv4Namespace,
            'VPCAttachment': VPCAttachment,
            'VPCPeering': VPCPeering,
            'Connection': Connection,
            'Server': Server,
            'Switch': Switch,
            'SwitchGroup': SwitchGroup,
            'VLANNamespace': VLANNamespace,
        }
        return model_map.get(model_name)
    
    def _determine_sync_status(self, cr_instance):
        """Determine the sync status of a CR"""
        if cr_instance.git_file_path and cr_instance.kubernetes_status == 'live':
            return 'in_sync'
        elif cr_instance.git_file_path and cr_instance.kubernetes_status != 'live':
            return 'pending_deployment'
        elif not cr_instance.git_file_path and cr_instance.kubernetes_status == 'live':
            return 'missing_from_git'
        else:
            return 'not_synced'