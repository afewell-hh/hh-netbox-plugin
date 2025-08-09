"""
OpenAPI Specifications

OpenAPI 3.0 specifications for NetBox Hedgehog Plugin REST APIs.
Provides:
- Complete API endpoint documentation
- Request/response schema definitions
- Authentication requirements
- Error response specifications
"""

from .models import get_model_schemas
from .endpoints import get_endpoint_specifications
from .errors import get_error_schemas
from .main import generate_openapi_spec

__all__ = [
    "get_model_schemas",
    "get_endpoint_specifications", 
    "get_error_schemas",
    "generate_openapi_spec",
]