"""
Git Repository Management Views
Django web views for Git repository management interface
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import View, TemplateView
from netbox.views import generic

from ..models import GitRepository
from ..forms.git_repository import GitRepositoryForm
from ..tables.git_repository import GitRepositoryTable


class GitRepositoryTestView(TemplateView):
    """Test view to bypass NetBox generic view issues"""
    template_name = 'netbox_hedgehog/overview.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Git Repository Test - This page works!'
        return context

class GitRepositoryListView(TemplateView):
    """List view for Git repositories - Using same pattern as working fabric views"""
    template_name = 'netbox_hedgehog/git_repository_list.html'
    
    def get_context_data(self, **kwargs):
        print("DEBUG: GitRepositoryListView.get_context_data() called from git_repository_views.py")
        context = super().get_context_data(**kwargs)
        repos = GitRepository.objects.all()
        print(f"DEBUG: Found {repos.count()} repositories in git_repository_views.py")
        for repo in repos:
            print(f"DEBUG: - {repo.name}: {repo.url}")
        context['object_list'] = repos
        context['repositories'] = repos
        context['title'] = 'Git Repositories'
        print(f"DEBUG: Template being used: {self.template_name}")
        return context
    


class GitRepositoryView(TemplateView):
    """Detail view for a Git repository - Using same pattern as working fabric views"""
    template_name = 'netbox_hedgehog/git_repository_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the git repository
        pk = kwargs.get('pk') or self.kwargs.get('pk')
        try:
            repository = GitRepository.objects.get(pk=pk)
            context['object'] = repository
            context['repository'] = repository
            
            # Get dependent fabrics if method exists
            if hasattr(repository, 'get_dependent_fabrics'):
                context['dependent_fabrics'] = repository.get_dependent_fabrics()
            
            # Get connection summary if method exists
            if hasattr(repository, 'get_connection_summary'):
                context['connection_summary'] = repository.get_connection_summary()
            
            # Check if user can delete if method exists
            if hasattr(repository, 'can_delete'):
                can_delete, reason = repository.can_delete()
                context['can_delete'] = can_delete
                context['delete_reason'] = reason
            
        except GitRepository.DoesNotExist:
            context['object'] = None
            context['repository'] = None
        
        return context


class GitRepositoryEditView(generic.ObjectEditView):
    """Create/Edit view for Git repositories"""
    queryset = GitRepository.objects.all()
    form = GitRepositoryForm
    template_name = 'netbox_hedgehog/git_repository_edit.html'
    
    def form_valid(self, form):
        """Handle successful form submission"""
        # Set created_by for new repositories (temporarily disabled)
        # if not form.instance.pk:
        #     form.instance.created_by = self.request.user
        
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
            return redirect('plugins:netbox_hedgehog:gitrepository_detail', pk=self.object.pk)


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
            return redirect('plugins:netbox_hedgehog:gitrepository_detail', pk=obj.pk)
        
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """Handle deletion request"""
        obj = self.get_object()
        can_delete, reason = obj.can_delete()
        
        if not can_delete:
            messages.error(request, f"Cannot delete repository: {reason}")
            return redirect('plugins:netbox_hedgehog:gitrepository_detail', pk=obj.pk)
        
        return super().post(request, *args, **kwargs)


class GitRepositoryTestConnectionView(View):
    """Test connection for a Git repository"""
    
    def post(self, request, pk):
        """Test connection to the git repository"""
        repository = get_object_or_404(GitRepository, pk=pk)
        
        # Check permissions (temporarily simplified)
        # if not request.user.is_superuser and repository.created_by != request.user:
        #     messages.error(request, "You don't have permission to test this repository")
        #     return redirect('plugins:netbox_hedgehog:gitrepository_detail', pk=pk)
        
        # Test connection
        result = repository.test_connection()
        
        if result['success']:
            messages.success(request, f"Connection test successful: {result.get('message', 'Connected')}")
        else:
            messages.error(request, f"Connection test failed: {result.get('error', 'Unknown error')}")
        
        return redirect('plugins:netbox_hedgehog:gitrepository_detail', pk=pk)