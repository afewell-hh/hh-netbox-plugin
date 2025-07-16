"""
Git Repository Management Views
Django web views for Git repository management interface
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import View
from netbox.views import generic

from ..models import GitRepository
from ..forms.git_repository import GitRepositoryForm
from ..tables.git_repository import GitRepositoryTable


class GitRepositoryListView(generic.ObjectListView):
    """List view for Git repositories"""
    queryset = GitRepository.objects.all()
    table = GitRepositoryTable
    template_name = 'netbox_hedgehog/git_repository_list.html'


class GitRepositoryView(generic.ObjectView):
    """Detail view for a Git repository"""
    queryset = GitRepository.objects.all()
    template_name = 'netbox_hedgehog/git_repository_detail.html'
    
    def get_extra_context(self, request, instance):
        """Add extra context for the detail view"""
        context = super().get_extra_context(request, instance)
        
        # Get dependent fabrics
        dependent_fabrics = instance.get_dependent_fabrics()
        context['dependent_fabrics'] = dependent_fabrics
        
        # Get connection summary
        context['connection_summary'] = instance.get_connection_summary()
        
        # Check if user can delete
        can_delete, reason = instance.can_delete()
        context['can_delete'] = can_delete
        context['delete_reason'] = reason
        
        return context


class GitRepositoryEditView(generic.ObjectEditView):
    """Create/Edit view for Git repositories"""
    queryset = GitRepository.objects.all()
    form = GitRepositoryForm
    template_name = 'netbox_hedgehog/git_repository_edit.html'
    
    def form_valid(self, form):
        """Handle successful form submission"""
        # Set created_by for new repositories
        if not form.instance.pk:
            form.instance.created_by = self.request.user
        
        # Save the repository
        self.object = form.save()
        
        # Test connection if requested
        if '_test_connection' in self.request.POST:
            result = self.object.test_connection()
            if result['success']:
                messages.success(self.request, f"Connection test successful: {result.get('message', 'Connected')}")
            else:
                messages.error(self.request, f"Connection test failed: {result.get('error', 'Unknown error')}")
            # Return to edit form
            return self.form_invalid(form)
        
        messages.success(self.request, f"Git repository '{self.object.name}' {'created' if not form.instance.pk else 'updated'} successfully")
        
        # Redirect based on button clicked
        if '_addanother' in self.request.POST:
            return redirect(self.get_success_url())
        else:
            return redirect('plugins:netbox_hedgehog:git_repository_detail', pk=self.object.pk)


class GitRepositoryDeleteView(generic.ObjectDeleteView):
    """Delete view for Git repositories"""
    queryset = GitRepository.objects.all()
    template_name = 'netbox_hedgehog/git_repository_confirm_delete.html'
    
    
    def get(self, request, *args, **kwargs):
        """Check if repository can be deleted before showing confirmation"""
        obj = self.get_object()
        can_delete, reason = obj.can_delete()
        
        if not can_delete:
            messages.error(request, f"Cannot delete repository: {reason}")
            return redirect('plugins:netbox_hedgehog:git_repository_detail', pk=obj.pk)
        
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """Handle deletion request"""
        obj = self.get_object()
        can_delete, reason = obj.can_delete()
        
        if not can_delete:
            messages.error(request, f"Cannot delete repository: {reason}")
            return redirect('plugins:netbox_hedgehog:git_repository_detail', pk=obj.pk)
        
        return super().post(request, *args, **kwargs)


class GitRepositoryTestConnectionView(View):
    """Test connection for a Git repository"""
    
    def post(self, request, pk):
        """Test connection to the git repository"""
        repository = get_object_or_404(GitRepository, pk=pk)
        
        # Check permissions
        if not request.user.is_superuser and repository.created_by != request.user:
            messages.error(request, "You don't have permission to test this repository")
            return redirect('plugins:netbox_hedgehog:git_repository_detail', pk=pk)
        
        # Test connection
        result = repository.test_connection()
        
        if result['success']:
            messages.success(request, f"Connection test successful: {result.get('message', 'Connected')}")
        else:
            messages.error(request, f"Connection test failed: {result.get('error', 'Unknown error')}")
        
        return redirect('plugins:netbox_hedgehog:git_repository_detail', pk=pk)