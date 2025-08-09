"""
OpenAPI Model Schema Definitions

Generates OpenAPI-compatible schemas from Pydantic models.
"""

from typing import Dict, Any
from ..models.core import get_json_schemas as get_core_schemas
from ..models.gitops import get_json_schemas as get_gitops_schemas
from ..models.vpc_api import get_json_schemas as get_vpc_schemas
from ..models.wiring_api import get_json_schemas as get_wiring_schemas


def get_model_schemas() -> Dict[str, Any]:
    """
    Get all model schemas for OpenAPI specification.
    
    Returns:
        Dictionary of schema name to OpenAPI schema definition
    """
    
    schemas = {}
    
    # Core models
    schemas.update(get_core_schemas())
    
    # GitOps models  
    schemas.update(get_gitops_schemas())
    
    # VPC API models
    schemas.update(get_vpc_schemas())
    
    # Wiring API models
    schemas.update(get_wiring_schemas())
    
    return schemas


def convert_pydantic_to_openapi(pydantic_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Pydantic JSON schema to OpenAPI 3.0 compatible schema.
    
    Args:
        pydantic_schema: Pydantic model's JSON schema
        
    Returns:
        OpenAPI compatible schema
    """
    
    # Pydantic schemas are mostly compatible with OpenAPI 3.0
    # but may need some minor adjustments
    
    openapi_schema = pydantic_schema.copy()
    
    # Remove Pydantic-specific fields if present
    openapi_schema.pop('title', None)
    
    # Ensure proper format for date-time fields
    if 'properties' in openapi_schema:
        for prop_name, prop_def in openapi_schema['properties'].items():
            if isinstance(prop_def, dict):
                if prop_def.get('type') == 'string' and 'format' not in prop_def:
                    # Add format for common date fields
                    if any(date_keyword in prop_name.lower() 
                          for date_keyword in ['created', 'updated', 'timestamp', 'date']):
                        prop_def['format'] = 'date-time'
    
    return openapi_schema