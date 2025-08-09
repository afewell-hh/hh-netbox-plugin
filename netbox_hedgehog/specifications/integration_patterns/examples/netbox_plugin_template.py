#!/usr/bin/env python3
"""
NetBox Plugin Integration Template
Provides a complete template for integrating new NetBox plugins following
Hedgehog patterns and best practices.
"""

# Django and NetBox imports
from django.apps import AppConfig
from django.db import models
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import path, include
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse
from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

# NetBox specific imports
from netbox.plugins import PluginConfig, PluginMenuButton, PluginMenuItem, PluginMenu
from utilities.choices import ButtonColorChoices

# Template Model
class YourPluginModel(models.Model):
    """Template model following Hedgehog patterns"""
    
    # Core fields
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    
    # Sync tracking fields
    sync_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('syncing', 'Syncing'),
            ('synced', 'Synced'),
            ('error', 'Error'),
        ],
        default='pending'
    )
    last_sync_time = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True, default='')
    
    # Timestamps
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['sync_status']),
            models.Index(fields=['last_sync_time']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return f'/plugins/your-plugin/models/{self.pk}/'

# Template View
class YourPluginModelListView(ListView):
    """List view following Hedgehog patterns"""
    
    model = YourPluginModel
    template_name = 'your_plugin/model_list.html'
    context_object_name = 'models'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add filtering
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(sync_status=status_filter)
        
        # Add search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(description__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = YourPluginModel._meta.get_field('sync_status').choices
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        return context

# Template API Serializer
class YourPluginModelSerializer(serializers.ModelSerializer):
    """API serializer following Hedgehog patterns"""
    
    class Meta:
        model = YourPluginModel
        fields = [
            'id', 'name', 'description',
            'sync_status', 'last_sync_time', 'sync_error',
            'created', 'last_updated'
        ]
        read_only_fields = [
            'id', 'sync_status', 'last_sync_time', 'sync_error',
            'created', 'last_updated'
        ]

# Template API ViewSet
class YourPluginModelViewSet(viewsets.ModelViewSet):
    """API viewset following Hedgehog patterns"""
    
    queryset = YourPluginModel.objects.all()
    serializer_class = YourPluginModelSerializer
    filterset_fields = ['sync_status']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created', 'last_updated']
    
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Custom sync action"""
        obj = self.get_object()
        
        # Trigger sync task
        from .tasks import sync_model_task
        task_result = sync_model_task.delay(obj.id)
        
        return Response({
            'message': 'Sync triggered',
            'task_id': task_result.id,
            'object_id': obj.id
        })

# Template Celery Task
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), 
             retry_kwargs={'max_retries': 3, 'countdown': 60})
def sync_model_task(self, model_id):
    """Template sync task following Hedgehog patterns"""
    
    try:
        # Get model instance
        obj = YourPluginModel.objects.get(id=model_id)
        obj.sync_status = 'syncing'
        obj.save(update_fields=['sync_status'])
        
        # Perform sync operations here
        # ... your sync logic ...
        
        # Update success status
        from django.utils import timezone
        obj.sync_status = 'synced'
        obj.last_sync_time = timezone.now()
        obj.sync_error = ''
        obj.save(update_fields=['sync_status', 'last_sync_time', 'sync_error'])
        
        logger.info(f"Successfully synced model {obj.name}")
        
        return {
            'status': 'success',
            'model_id': model_id,
            'model_name': obj.name
        }
        
    except YourPluginModel.DoesNotExist:
        logger.error(f"Model {model_id} not found")
        return {
            'status': 'error',
            'error': 'Model not found'
        }
    except Exception as e:
        logger.error(f"Sync failed for model {model_id}: {e}")
        
        # Update error status
        try:
            obj = YourPluginModel.objects.get(id=model_id)
            obj.sync_status = 'error'
            obj.sync_error = str(e)
            obj.save(update_fields=['sync_status', 'sync_error'])
        except:
            pass
        
        raise self.retry(exc=e)

# Template Plugin Configuration
class YourPluginConfig(PluginConfig):
    """Plugin configuration following Hedgehog patterns"""
    
    name = 'your_plugin'
    verbose_name = 'Your Plugin'
    description = 'Description of your plugin functionality'
    version = '1.0.0'
    author = 'Your Name'
    author_email = 'your.email@example.com'
    base_url = 'your-plugin'
    
    required_settings = []
    default_settings = {
        'sync_interval': 300,  # 5 minutes
        'max_retry_attempts': 3,
        'enable_auto_sync': True,
    }
    
    caching_config = {
        'model_cache_ttl': 300,  # 5 minutes
        'status_cache_ttl': 60,  # 1 minute
    }

# Template URLs
urlpatterns = [
    # Web views
    path('', YourPluginModelListView.as_view(), name='model_list'),
    path('<int:pk>/', DetailView.as_view(
        model=YourPluginModel,
        template_name='your_plugin/model_detail.html'
    ), name='model_detail'),
    
    # API URLs
    path('api/', include('your_plugin.api.urls', namespace='api')),
]

# Template Navigation
menu_buttons = (
    PluginMenuButton(
        link='plugins:your_plugin:model_list',
        title='Add Model',
        icon_class='mdi mdi-plus-thick',
        color=ButtonColorChoices.GREEN
    ),
)

menu_items = (
    PluginMenuItem(
        link='plugins:your_plugin:model_list',
        link_text='Models',
        buttons=menu_buttons,
    ),
)

menu = PluginMenu(
    label='Your Plugin',
    groups=(
        ('Management', menu_items),
    ),
    icon_class='mdi mdi-your-icon'
)

# Template Django App Configuration
class YourPluginAppConfig(AppConfig):
    """Django app configuration following Hedgehog patterns"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'your_plugin'
    label = 'your_plugin'
    verbose_name = 'Your Plugin'
    
    def ready(self):
        """Initialize plugin when Django is ready"""
        try:
            # Import signals
            from . import signals
            
            # Initialize services
            self._initialize_services()
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Your Plugin: Initialization complete")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Your Plugin: Initialization failed: {e}")
    
    def _initialize_services(self):
        """Initialize plugin services"""
        # Register any services here
        pass

# Template Test
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User

class TestYourPlugin(TestCase):
    """Template test cases following Hedgehog patterns"""
    
    def setUp(self):
        """Set up test environment"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_model_creation(self):
        """Test model creation"""
        obj = YourPluginModel.objects.create(
            name='test-model',
            description='Test model'
        )
        
        self.assertEqual(obj.name, 'test-model')
        self.assertEqual(obj.sync_status, 'pending')
    
    def test_api_list_endpoint(self):
        """Test API list endpoint"""
        response = self.client.get('/plugins/your-plugin/api/models/')
        self.assertEqual(response.status_code, 200)
    
    def test_sync_task(self):
        """Test sync task execution"""
        obj = YourPluginModel.objects.create(
            name='sync-test-model',
            description='Sync test model'
        )
        
        # Execute task synchronously for testing
        result = sync_model_task(obj.id)
        
        self.assertEqual(result['status'], 'success')
        
        # Verify model was updated
        obj.refresh_from_db()
        self.assertEqual(obj.sync_status, 'synced')

# Template JavaScript (frontend)
template_js = """
// Template JavaScript following Hedgehog patterns

class YourPluginAPI {
    constructor() {
        this.baseUrl = '/plugins/your-plugin/api';
        this.csrfToken = this.getCSRFToken();
    }

    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }

    async request(method, endpoint, data = null) {
        const url = `${this.baseUrl}${endpoint}`;
        
        const config = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
            },
            credentials: 'same-origin',
        };

        if (data && ['POST', 'PUT', 'PATCH'].includes(method)) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    async getModels(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = `/models/${queryString ? `?${queryString}` : ''}`;
        return this.request('GET', endpoint);
    }

    async syncModel(id) {
        return this.request('POST', `/models/${id}/sync/`);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.yourPluginAPI = new YourPluginAPI();
    
    // Initialize sync buttons
    document.addEventListener('click', async (e) => {
        if (e.target.matches('[data-sync-model]')) {
            e.preventDefault();
            const modelId = e.target.dataset.syncModel;
            
            try {
                e.target.disabled = true;
                e.target.textContent = 'Syncing...';
                
                await window.yourPluginAPI.syncModel(modelId);
                
                // Show success message
                alert('Sync initiated successfully');
                
                // Reload page to show updated status
                window.location.reload();
                
            } catch (error) {
                alert(`Sync failed: ${error.message}`);
                e.target.disabled = false;
                e.target.textContent = 'Sync';
            }
        }
    });
});
"""

# Template HTML
template_html = """
<!-- Template HTML following Hedgehog patterns -->
<!-- model_list.html -->

{% extends 'base/layout.html' %}
{% load helpers %}

{% block title %}Your Plugin - Models{% endblock %}

{% block content %}
    <div class="row">
        <div class="col-md-12">
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Models</h3>
                    <div class="card-actions">
                        <a href="{% url 'plugins:your_plugin:model_add' %}" class="btn btn-primary">
                            <i class="mdi mdi-plus"></i> Add Model
                        </a>
                    </div>
                </div>
                
                <!-- Filters -->
                <div class="card-body">
                    <form method="get" class="form-inline">
                        <input type="text" name="search" class="form-control mr-2" 
                               placeholder="Search..." value="{{ search_query }}">
                        
                        <select name="status" class="form-control mr-2">
                            <option value="">All Statuses</option>
                            {% for value, label in status_choices %}
                                <option value="{{ value }}" 
                                        {% if status_filter == value %}selected{% endif %}>
                                    {{ label }}
                                </option>
                            {% endfor %}
                        </select>
                        
                        <button type="submit" class="btn btn-outline-primary">Filter</button>
                    </form>
                </div>
                
                <!-- Model List -->
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Description</th>
                                <th>Status</th>
                                <th>Last Sync</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for model in models %}
                                <tr>
                                    <td>
                                        <a href="{{ model.get_absolute_url }}">{{ model.name }}</a>
                                    </td>
                                    <td>{{ model.description|truncatechars:50 }}</td>
                                    <td>
                                        <span class="badge badge-{{ model.sync_status|status_color }}">
                                            {{ model.get_sync_status_display }}
                                        </span>
                                    </td>
                                    <td>
                                        {% if model.last_sync_time %}
                                            {{ model.last_sync_time|date:"Y-m-d H:i" }}
                                        {% else %}
                                            Never
                                        {% endif %}
                                    </td>
                                    <td>
                                        <button class="btn btn-sm btn-outline-primary" 
                                                data-sync-model="{{ model.id }}">
                                            Sync
                                        </button>
                                    </td>
                                </tr>
                            {% empty %}
                                <tr>
                                    <td colspan="5" class="text-center">No models found</td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                
                <!-- Pagination -->
                {% if is_paginated %}
                    <div class="card-footer">
                        {% include 'pagination.html' %}
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
{% endblock %}

{% block javascript %}
    {{ block.super }}
    <script>{{ template_js|safe }}</script>
{% endblock %}
"""

if __name__ == '__main__':
    print("NetBox Plugin Integration Template")
    print("==================================")
    print("")
    print("This template provides a complete example of NetBox plugin integration")
    print("following Hedgehog patterns and best practices.")
    print("")
    print("Key components included:")
    print("- Model with sync tracking fields")
    print("- Views with filtering and search")
    print("- API endpoints with custom actions")
    print("- Celery tasks with retry logic")
    print("- Plugin configuration")
    print("- Navigation setup")
    print("- Test cases")
    print("- Frontend JavaScript")
    print("- HTML templates")
    print("")
    print("Customize this template by replacing 'YourPlugin' and 'YourPluginModel'")
    print("with your actual plugin and model names.")