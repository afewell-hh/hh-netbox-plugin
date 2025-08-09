"""
Configuration Template Engine API Views

REST API endpoints for the Configuration Template Engine providing
template management, configuration generation, and validation services.
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ..models.fabric import HedgehogFabric
from ..models.gitops import HedgehogResource
from ..services.configuration_template_engine import (
    ConfigurationTemplateEngine, 
    generate_fabric_configurations,
    validate_fabric_templates,
    handle_resource_change
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_fabric_config(request, fabric_id):
    """
    Generate configuration for a specific fabric.
    
    POST /api/plugins/hedgehog/template-engine/fabrics/{fabric_id}/generate/
    
    Parameters:
    - force_regenerate: bool (optional) - Force regeneration even if no changes
    - template_filter: list (optional) - List of template names to process
    """
    try:
        fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
        
        # Get request parameters
        force_regenerate = request.data.get('force_regenerate', False)
        template_filter = request.data.get('template_filter')
        
        logger.info(f"API request to generate configuration for fabric {fabric.name}")
        
        # Generate configurations
        result = generate_fabric_configurations(fabric, force_regenerate=force_regenerate)
        
        # Prepare response
        response_data = {
            'success': result.success,
            'fabric_name': result.fabric_name,
            'generation_id': result.generation_id,
            'files_generated': result.files_generated,
            'files_updated': result.files_updated,
            'files_validated': result.files_validated,
            'execution_time': result.execution_time,
            'error_message': result.error_message,
            'statistics': {
                'total_files': len(result.files_generated + result.files_updated),
                'validation_errors': len(result.validation_errors),
                'template_errors': len(result.template_errors),
                'conflict_resolutions': len(result.conflict_resolutions)
            }
        }
        
        if result.success:
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Configuration generation API error: {str(e)}")
        return Response(
            {'error': str(e), 'success': False},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def regenerate_resource_config(request, resource_id):
    """
    Regenerate configuration for a specific resource.
    
    POST /api/plugins/hedgehog/template-engine/resources/{resource_id}/regenerate/
    """
    try:
        resource = get_object_or_404(HedgehogResource, pk=resource_id)
        
        logger.info(f"API request to regenerate configuration for resource {resource.name}")
        
        # Regenerate configurations
        result = handle_resource_change(resource)
        
        # Prepare response
        response_data = {
            'success': result.success,
            'resource_name': resource.name,
            'resource_kind': resource.kind,
            'fabric_name': result.fabric_name,
            'generation_id': result.generation_id,
            'files_generated': result.files_generated,
            'files_updated': result.files_updated,
            'execution_time': result.execution_time,
            'error_message': result.error_message
        }
        
        if result.success:
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Resource regeneration API error: {str(e)}")
        return Response(
            {'error': str(e), 'success': False},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validate_fabric_templates_api(request, fabric_id):
    """
    Validate templates for a specific fabric.
    
    GET /api/plugins/hedgehog/template-engine/fabrics/{fabric_id}/validate/
    
    Query Parameters:
    - template_names: comma-separated list of template names (optional)
    """
    try:
        fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
        
        # Get template names from query parameters
        template_names_param = request.query_params.get('template_names')
        template_names = None
        if template_names_param:
            template_names = [name.strip() for name in template_names_param.split(',')]
        
        logger.info(f"API request to validate templates for fabric {fabric.name}")
        
        # Validate templates
        results = validate_fabric_templates(fabric, template_names)
        
        # Prepare response
        response_data = {
            'fabric_name': fabric.name,
            'validation_time': results.get('validation_time', 0.0),
            'total_templates': results.get('total_templates', 0),
            'valid_templates': results.get('valid_templates', []),
            'invalid_templates': results.get('invalid_templates', []),
            'warnings': results.get('warnings', []),
            'statistics': {
                'valid_count': len(results.get('valid_templates', [])),
                'invalid_count': len(results.get('invalid_templates', [])),
                'warning_count': len(results.get('warnings', []))
            },
            'error': results.get('error')
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Template validation API error: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_engine_status(request, fabric_id):
    """
    Get template engine status for a fabric.
    
    GET /api/plugins/hedgehog/template-engine/fabrics/{fabric_id}/status/
    """
    try:
        fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
        
        engine = ConfigurationTemplateEngine(fabric)
        status_info = engine.get_engine_status()
        
        # Add additional API-specific information
        status_info.update({
            'fabric_id': fabric.id,
            'fabric_name': fabric.name,
            'timestamp': timezone.now().isoformat(),
            'resource_count': fabric.gitops_resources.count(),
        })
        
        return Response(status_info, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Engine status API error: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_templates(request, fabric_id):
    """
    List available templates for a fabric.
    
    GET /api/plugins/hedgehog/template-engine/fabrics/{fabric_id}/templates/
    
    Query Parameters:
    - category: filter by category (optional)
    - tags: comma-separated list of tags to filter by (optional)
    """
    try:
        fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
        
        engine = ConfigurationTemplateEngine(fabric)
        
        # Get query parameters
        category = request.query_params.get('category')
        tags_param = request.query_params.get('tags')
        tags = None
        if tags_param:
            tags = [tag.strip() for tag in tags_param.split(',')]
        
        # List templates
        templates = engine.template_manager.list_templates(category=category, tags=tags)
        
        response_data = {
            'fabric_name': fabric.name,
            'templates': templates,
            'count': len(templates),
            'filters_applied': {
                'category': category,
                'tags': tags
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"List templates API error: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def optimize_engine_performance(request, fabric_id):
    """
    Optimize template engine performance.
    
    POST /api/plugins/hedgehog/template-engine/fabrics/{fabric_id}/optimize/
    """
    try:
        fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
        
        engine = ConfigurationTemplateEngine(fabric)
        optimization_results = engine.optimize_performance()
        
        response_data = {
            'fabric_name': fabric.name,
            'optimization_results': optimization_results,
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Engine optimization API error: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_engine_caches(request, fabric_id):
    """
    Clear template engine caches.
    
    POST /api/plugins/hedgehog/template-engine/fabrics/{fabric_id}/clear-cache/
    """
    try:
        fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
        
        engine = ConfigurationTemplateEngine(fabric)
        engine.clear_caches()
        
        response_data = {
            'fabric_name': fabric.name,
            'message': 'Caches cleared successfully',
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Clear cache API error: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_schemas(request):
    """
    Get available validation schemas.
    
    GET /api/plugins/hedgehog/template-engine/schemas/
    """
    try:
        # Create a temporary engine instance to access schema validator
        engine = ConfigurationTemplateEngine()
        schemas = engine.schema_validator.get_available_schemas()
        
        schema_list = []
        for schema in schemas:
            schema_list.append({
                'name': schema.name,
                'version': schema.version,
                'resource_type': schema.resource_type,
                'description': schema.description,
                'created_at': schema.created_at.isoformat(),
                'updated_at': schema.updated_at.isoformat()
            })
        
        response_data = {
            'schemas': schema_list,
            'count': len(schema_list),
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Get schemas API error: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Health check endpoint
@api_view(['GET'])
def template_engine_health(request):
    """
    Template engine health check endpoint.
    
    GET /api/plugins/hedgehog/template-engine/health/
    """
    try:
        # Basic health check
        engine = ConfigurationTemplateEngine()
        status_info = {
            'service': 'configuration_template_engine',
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '3.0.0',
            'components': {
                'config_generator': True,
                'template_manager': True,
                'schema_validator': True,
                'file_manager': True
            }
        }
        
        return Response(status_info, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Health check API error: {str(e)}")
        return Response(
            {
                'service': 'configuration_template_engine',
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )