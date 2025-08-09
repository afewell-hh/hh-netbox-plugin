"""
Main OpenAPI Specification Generator

Generates complete OpenAPI 3.0 specification for NetBox Hedgehog Plugin.
"""

from typing import Dict, Any
from ..models import *


def generate_openapi_spec() -> Dict[str, Any]:
    """
    Generate complete OpenAPI 3.0 specification for NetBox Hedgehog Plugin API.
    
    Returns:
        Complete OpenAPI specification dictionary
    """
    
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "NetBox Hedgehog Plugin API",
            "description": (
                "REST API for NetBox Hedgehog Plugin - GitOps-enabled network fabric management.\n\n"
                "This API provides comprehensive access to:\n"
                "- Hedgehog fabric configuration and management\n" 
                "- Git repository integration and synchronization\n"
                "- Kubernetes Custom Resource Definition (CRD) management\n"
                "- GitOps workflow operations and state management\n"
                "- VPC API resources for network isolation\n"
                "- Wiring API resources for physical connectivity\n"
                "- Drift detection and reconciliation\n\n"
                "## Authentication\n"
                "This API uses NetBox's built-in authentication system. "
                "API tokens can be generated in the NetBox admin interface.\n\n"
                "## Rate Limiting\n"
                "API calls are subject to NetBox's configured rate limits.\n\n"
                "## Versioning\n"
                "This API follows semantic versioning. Breaking changes will increment the major version."
            ),
            "version": "1.0.0",
            "contact": {
                "name": "NetBox Hedgehog Plugin",
                "url": "https://github.com/afewell-hh/hh-netbox-plugin"
            },
            "license": {
                "name": "Apache 2.0",
                "url": "https://www.apache.org/licenses/LICENSE-2.0"
            }
        },
        "servers": [
            {
                "url": "/api/plugins/netbox-hedgehog/",
                "description": "NetBox Hedgehog Plugin API"
            }
        ],
        "paths": _get_api_paths(),
        "components": {
            "schemas": _get_component_schemas(),
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Authorization",
                    "description": "NetBox API token. Format: 'Token <your-api-token>'"
                },
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "JWT bearer token for advanced authentication"
                }
            },
            "responses": _get_common_responses(),
            "parameters": _get_common_parameters()
        },
        "security": [
            {"ApiKeyAuth": []},
            {"BearerAuth": []}
        ],
        "tags": [
            {
                "name": "fabrics",
                "description": "Hedgehog fabric management"
            },
            {
                "name": "git-repositories", 
                "description": "Git repository configuration and validation"
            },
            {
                "name": "gitops",
                "description": "GitOps workflow operations"
            },
            {
                "name": "vpc-api",
                "description": "VPC API resources for network isolation"
            },
            {
                "name": "wiring-api", 
                "description": "Wiring API resources for physical connectivity"
            },
            {
                "name": "sync",
                "description": "Synchronization operations"
            },
            {
                "name": "validation",
                "description": "Validation and testing operations"
            }
        ]
    }
    
    return spec


def _get_api_paths() -> Dict[str, Any]:
    """Get all API path definitions"""
    
    paths = {}
    
    # Fabric endpoints
    paths.update(_get_fabric_paths())
    
    # Git repository endpoints
    paths.update(_get_git_repository_paths())
    
    # GitOps endpoints
    paths.update(_get_gitops_paths())
    
    # VPC API endpoints
    paths.update(_get_vpc_api_paths())
    
    # Wiring API endpoints
    paths.update(_get_wiring_api_paths())
    
    # Custom operation endpoints
    paths.update(_get_custom_endpoints())
    
    return paths


def _get_fabric_paths() -> Dict[str, Any]:
    """Get fabric API path definitions"""
    
    return {
        "/fabrics/": {
            "get": {
                "tags": ["fabrics"],
                "summary": "List fabrics",
                "description": "List all Hedgehog fabrics with optional filtering",
                "parameters": [
                    {"$ref": "#/components/parameters/limit"},
                    {"$ref": "#/components/parameters/offset"},
                    {
                        "name": "status",
                        "in": "query",
                        "schema": {"type": "string", "enum": ["PLANNED", "ACTIVE", "DECOMMISSIONED"]},
                        "description": "Filter by fabric status"
                    },
                    {
                        "name": "connection_status", 
                        "in": "query",
                        "schema": {"type": "string", "enum": ["UNKNOWN", "CONNECTED", "FAILED", "TESTING"]},
                        "description": "Filter by connection status"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of fabrics",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "count": {"type": "integer"},
                                        "next": {"type": "string", "nullable": True},
                                        "previous": {"type": "string", "nullable": True},
                                        "results": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/HedgehogFabric"}
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "401": {"$ref": "#/components/responses/Unauthorized"}
                }
            },
            "post": {
                "tags": ["fabrics"],
                "summary": "Create fabric",
                "description": "Create a new Hedgehog fabric",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/HedgehogFabricCreate"}
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Fabric created successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HedgehogFabric"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "401": {"$ref": "#/components/responses/Unauthorized"}
                }
            }
        },
        "/fabrics/{id}/": {
            "get": {
                "tags": ["fabrics"],
                "summary": "Get fabric",
                "description": "Retrieve specific Hedgehog fabric by ID",
                "parameters": [
                    {"$ref": "#/components/parameters/id"}
                ],
                "responses": {
                    "200": {
                        "description": "Fabric details",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HedgehogFabric"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            },
            "put": {
                "tags": ["fabrics"],
                "summary": "Update fabric",
                "description": "Update specific Hedgehog fabric",
                "parameters": [
                    {"$ref": "#/components/parameters/id"}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/HedgehogFabricUpdate"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Fabric updated successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HedgehogFabric"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            },
            "delete": {
                "tags": ["fabrics"],
                "summary": "Delete fabric",
                "description": "Delete specific Hedgehog fabric",
                "parameters": [
                    {"$ref": "#/components/parameters/id"}
                ],
                "responses": {
                    "204": {"description": "Fabric deleted successfully"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "409": {"$ref": "#/components/responses/Conflict"}
                }
            }
        },
        "/fabrics/{id}/test-connection/": {
            "post": {
                "tags": ["fabrics"],
                "summary": "Test fabric connection",
                "description": "Test Kubernetes connectivity for fabric",
                "parameters": [
                    {"$ref": "#/components/parameters/id"}
                ],
                "responses": {
                    "200": {
                        "description": "Connection test results",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ConnectionTestResult"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        },
        "/fabrics/{id}/sync/": {
            "post": {
                "tags": ["fabrics", "sync"],
                "summary": "Trigger fabric sync",
                "description": "Trigger manual synchronization for fabric",
                "parameters": [
                    {"$ref": "#/components/parameters/id"}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "force": {
                                        "type": "boolean",
                                        "default": False,
                                        "description": "Force sync even if fabric appears in sync"
                                    },
                                    "direction": {
                                        "type": "string",
                                        "enum": ["to_kubernetes", "from_kubernetes", "bidirectional"],
                                        "default": "bidirectional",
                                        "description": "Sync direction"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Sync operation started",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SyncOperationResult"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "409": {"$ref": "#/components/responses/Conflict"}
                }
            }
        }
    }


def _get_git_repository_paths() -> Dict[str, Any]:
    """Get Git repository API path definitions"""
    
    return {
        "/git-repos-api/": {
            "get": {
                "tags": ["git-repositories"],
                "summary": "List Git repositories",
                "description": "List all configured Git repositories",
                "parameters": [
                    {"$ref": "#/components/parameters/limit"},
                    {"$ref": "#/components/parameters/offset"}
                ],
                "responses": {
                    "200": {
                        "description": "List of Git repositories",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object", 
                                    "properties": {
                                        "count": {"type": "integer"},
                                        "results": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/GitRepository"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "tags": ["git-repositories"],
                "summary": "Create Git repository",
                "description": "Configure a new Git repository",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/GitRepositoryCreate"}
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Git repository created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/GitRepository"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"}
                }
            }
        }
    }


def _get_gitops_paths() -> Dict[str, Any]:
    """Get GitOps API path definitions"""
    
    return {
        "/gitops/": {
            "get": {
                "tags": ["gitops"],
                "summary": "Get GitOps status",
                "description": "Get global GitOps workflow status",
                "responses": {
                    "200": {
                        "description": "GitOps status",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/GitOpsStatus"}
                            }
                        }
                    }
                }
            }
        },
        "/gitops/drift-analysis/": {
            "post": {
                "tags": ["gitops"],
                "summary": "Analyze drift",
                "description": "Perform drift analysis between Git and Kubernetes",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "fabric_id": {"type": "integer"},
                                    "resource_ids": {
                                        "type": "array",
                                        "items": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Drift analysis results",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/DriftAnalysisResult"}
                            }
                        }
                    }
                }
            }
        }
    }


def _get_vpc_api_paths() -> Dict[str, Any]:
    """Get VPC API path definitions"""
    
    paths = {}
    
    # VPC endpoints
    paths.update({
        "/vpcs/": {
            "get": {
                "tags": ["vpc-api"],
                "summary": "List VPCs",
                "description": "List all VPC resources",
                "responses": {
                    "200": {
                        "description": "List of VPCs",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "results": {
                                            "type": "array", 
                                            "items": {"$ref": "#/components/schemas/VPC"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    })
    
    return paths


def _get_wiring_api_paths() -> Dict[str, Any]:
    """Get Wiring API path definitions"""
    
    return {
        "/connections/": {
            "get": {
                "tags": ["wiring-api"],
                "summary": "List connections",
                "description": "List all connection resources",
                "responses": {
                    "200": {
                        "description": "List of connections",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "results": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/Connection"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }


def _get_custom_endpoints() -> Dict[str, Any]:
    """Get custom operation endpoints"""
    
    return {
        "/sync/": {
            "post": {
                "tags": ["sync"],
                "summary": "Global sync operation",
                "description": "Trigger global synchronization operation",
                "responses": {
                    "200": {"description": "Sync started"}
                }
            }
        },
        "/status/": {
            "get": {
                "tags": ["sync"],
                "summary": "Get system status", 
                "description": "Get overall system health and status",
                "responses": {
                    "200": {
                        "description": "System status",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SystemStatus"}
                            }
                        }
                    }
                }
            }
        }
    }


def _get_component_schemas() -> Dict[str, Any]:
    """Get component schema definitions"""
    
    # Get schemas from Pydantic models
    from ..models.core import get_json_schemas as get_core_schemas
    from ..models.gitops import get_json_schemas as get_gitops_schemas
    from ..models.vpc_api import get_json_schemas as get_vpc_schemas
    from ..models.wiring_api import get_json_schemas as get_wiring_schemas
    
    schemas = {}
    schemas.update(get_core_schemas())
    schemas.update(get_gitops_schemas())
    schemas.update(get_vpc_schemas())
    schemas.update(get_wiring_schemas())
    
    # Add operation result schemas
    schemas.update({
        "ConnectionTestResult": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "details": {"type": "object"},
                "timestamp": {"type": "string", "format": "date-time"}
            }
        },
        "SyncOperationResult": {
            "type": "object", 
            "properties": {
                "operation_id": {"type": "string"},
                "status": {"type": "string", "enum": ["started", "running", "completed", "failed"]},
                "message": {"type": "string"},
                "progress": {"type": "number", "minimum": 0, "maximum": 100}
            }
        },
        "GitOpsStatus": {
            "type": "object",
            "properties": {
                "total_fabrics": {"type": "integer"},
                "active_fabrics": {"type": "integer"},
                "total_resources": {"type": "integer"},
                "synced_resources": {"type": "integer"},
                "drift_detected": {"type": "integer"}
            }
        },
        "DriftAnalysisResult": {
            "type": "object",
            "properties": {
                "total_resources": {"type": "integer"},
                "resources_with_drift": {"type": "integer"},
                "drift_details": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "resource_id": {"type": "integer"},
                            "resource_name": {"type": "string"},
                            "drift_score": {"type": "number"},
                            "drift_summary": {"type": "string"}
                        }
                    }
                }
            }
        },
        "SystemStatus": {
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]},
                "fabrics": {"type": "integer"},
                "repositories": {"type": "integer"},
                "last_sync": {"type": "string", "format": "date-time"}
            }
        }
    })
    
    # Add create/update schemas
    schemas["HedgehogFabricCreate"] = {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string", "maxLength": 100},
            "description": {"type": "string"},
            "kubernetes_server": {"type": "string", "format": "uri"},
            "git_repository": {"type": "integer"}
        }
    }
    
    schemas["HedgehogFabricUpdate"] = {
        "allOf": [{"$ref": "#/components/schemas/HedgehogFabricCreate"}]
    }
    
    schemas["GitRepositoryCreate"] = {
        "type": "object",
        "required": ["name", "url"],
        "properties": {
            "name": {"type": "string", "maxLength": 200},
            "url": {"type": "string", "format": "uri"},
            "provider": {"type": "string", "enum": ["GITHUB", "GITLAB", "BITBUCKET", "GENERIC"]},
            "authentication_type": {"type": "string", "enum": ["TOKEN", "BASIC", "SSH", "OAUTH"]}
        }
    }
    
    return schemas


def _get_common_responses() -> Dict[str, Any]:
    """Get common response definitions"""
    
    return {
        "BadRequest": {
            "description": "Bad request",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error": {"type": "string"},
                            "details": {"type": "object"}
                        }
                    }
                }
            }
        },
        "Unauthorized": {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error": {"type": "string", "example": "Authentication credentials were not provided."}
                        }
                    }
                }
            }
        },
        "NotFound": {
            "description": "Resource not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error": {"type": "string", "example": "Not found."}
                        }
                    }
                }
            }
        },
        "Conflict": {
            "description": "Conflict with current state",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object", 
                        "properties": {
                            "error": {"type": "string"},
                            "conflicts": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            }
        }
    }


def _get_common_parameters() -> Dict[str, Any]:
    """Get common parameter definitions"""
    
    return {
        "id": {
            "name": "id",
            "in": "path",
            "required": True,
            "schema": {"type": "integer"},
            "description": "Object ID"
        },
        "limit": {
            "name": "limit",
            "in": "query", 
            "schema": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 50},
            "description": "Number of results to return per page"
        },
        "offset": {
            "name": "offset",
            "in": "query",
            "schema": {"type": "integer", "minimum": 0, "default": 0},
            "description": "The initial index from which to return the results"
        }
    }