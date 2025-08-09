"""
OpenAPI Endpoint Definitions

Defines OpenAPI path specifications for all API endpoints.
"""

from typing import Dict, Any


def get_endpoint_specifications() -> Dict[str, Any]:
    """
    Get OpenAPI path specifications for all endpoints.
    
    Returns:
        Dictionary of endpoint path to OpenAPI path specification
    """
    
    endpoints = {}
    
    # Add all endpoint categories
    endpoints.update(get_fabric_endpoints())
    endpoints.update(get_git_repository_endpoints())
    endpoints.update(get_gitops_endpoints())
    endpoints.update(get_vpc_api_endpoints())
    endpoints.update(get_wiring_api_endpoints())
    endpoints.update(get_custom_endpoints())
    
    return endpoints


def get_fabric_endpoints() -> Dict[str, Any]:
    """Get Hedgehog Fabric API endpoint specifications"""
    
    return {
        "/fabrics/": {
            "get": {
                "tags": ["fabrics"],
                "summary": "List Hedgehog fabrics",
                "description": "Retrieve a list of all Hedgehog fabrics with optional filtering",
                "operationId": "listFabrics",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "Number of results to return per page",
                        "schema": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 50}
                    },
                    {
                        "name": "offset", 
                        "in": "query",
                        "description": "The initial index from which to return results",
                        "schema": {"type": "integer", "minimum": 0, "default": 0}
                    },
                    {
                        "name": "status",
                        "in": "query",
                        "description": "Filter by fabric configuration status",
                        "schema": {
                            "type": "string",
                            "enum": ["PLANNED", "ACTIVE", "DECOMMISSIONED"]
                        }
                    },
                    {
                        "name": "connection_status",
                        "in": "query", 
                        "description": "Filter by connection status",
                        "schema": {
                            "type": "string",
                            "enum": ["UNKNOWN", "CONNECTED", "FAILED", "TESTING"]
                        }
                    },
                    {
                        "name": "sync_status",
                        "in": "query",
                        "description": "Filter by synchronization status",
                        "schema": {
                            "type": "string", 
                            "enum": ["NEVER_SYNCED", "IN_SYNC", "OUT_OF_SYNC", "SYNCING", "ERROR"]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "count": {
                                            "type": "integer",
                                            "description": "Total number of fabrics"
                                        },
                                        "next": {
                                            "type": "string",
                                            "nullable": True,
                                            "description": "URL for next page of results"
                                        },
                                        "previous": {
                                            "type": "string", 
                                            "nullable": True,
                                            "description": "URL for previous page of results"
                                        },
                                        "results": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/HedgehogFabric"}
                                        }
                                    }
                                },
                                "examples": {
                                    "fabricList": {
                                        "summary": "Example fabric list",
                                        "value": {
                                            "count": 2,
                                            "next": None,
                                            "previous": None,
                                            "results": [
                                                {
                                                    "id": 1,
                                                    "name": "production-fabric",
                                                    "description": "Production fabric",
                                                    "status": "ACTIVE",
                                                    "connection_status": "CONNECTED"
                                                }
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "500": {"$ref": "#/components/responses/InternalServerError"}
                }
            },
            "post": {
                "tags": ["fabrics"],
                "summary": "Create Hedgehog fabric",
                "description": "Create a new Hedgehog fabric configuration",
                "operationId": "createFabric",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "maxLength": 100,
                                        "description": "Unique name for the fabric"
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "Optional description"
                                    },
                                    "kubernetes_server": {
                                        "type": "string",
                                        "format": "uri",
                                        "description": "Kubernetes API server URL"
                                    },
                                    "kubernetes_namespace": {
                                        "type": "string",
                                        "maxLength": 253,
                                        "default": "default",
                                        "description": "Default Kubernetes namespace"
                                    },
                                    "git_repository": {
                                        "type": "integer",
                                        "description": "Git repository ID"
                                    },
                                    "gitops_directory": {
                                        "type": "string",
                                        "maxLength": 500,
                                        "default": "/",
                                        "description": "Directory path for GitOps files"
                                    },
                                    "sync_enabled": {
                                        "type": "boolean", 
                                        "default": True,
                                        "description": "Enable automatic synchronization"
                                    },
                                    "sync_interval": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "default": 300,
                                        "description": "Sync interval in seconds"
                                    }
                                }
                            },
                            "examples": {
                                "newFabric": {
                                    "summary": "New production fabric",
                                    "value": {
                                        "name": "production-fabric",
                                        "description": "Production Hedgehog fabric",
                                        "kubernetes_server": "https://k8s.example.com:6443",
                                        "git_repository": 1,
                                        "sync_enabled": True
                                    }
                                }
                            }
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
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "409": {"$ref": "#/components/responses/Conflict"}
                }
            }
        },
        "/fabrics/{id}/": {
            "get": {
                "tags": ["fabrics"],
                "summary": "Get Hedgehog fabric",
                "description": "Retrieve a specific Hedgehog fabric by ID",
                "operationId": "getFabric",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "description": "Fabric ID",
                        "schema": {"type": "integer"}
                    }
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
                "summary": "Update Hedgehog fabric", 
                "description": "Update an existing Hedgehog fabric",
                "operationId": "updateFabric",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"}
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/HedgehogFabric"}
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
                "summary": "Delete Hedgehog fabric",
                "description": "Delete a Hedgehog fabric and all associated resources",
                "operationId": "deleteFabric",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path", 
                        "required": True,
                        "schema": {"type": "integer"}
                    }
                ],
                "responses": {
                    "204": {"description": "Fabric deleted successfully"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "409": {"$ref": "#/components/responses/Conflict"}
                }
            }
        }
    }


def get_git_repository_endpoints() -> Dict[str, Any]:
    """Get Git Repository API endpoint specifications"""
    
    return {
        "/git-repos-api/": {
            "get": {
                "tags": ["git-repositories"],
                "summary": "List Git repositories",
                "description": "Retrieve list of configured Git repositories",
                "operationId": "listGitRepositories",
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
            }
        }
    }


def get_gitops_endpoints() -> Dict[str, Any]:
    """Get GitOps API endpoint specifications"""
    
    return {
        "/gitops/": {
            "get": {
                "tags": ["gitops"],
                "summary": "Get GitOps status",
                "description": "Get global GitOps workflow status and metrics",
                "operationId": "getGitOpsStatus",
                "responses": {
                    "200": {
                        "description": "GitOps status information",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "total_fabrics": {"type": "integer"},
                                        "active_fabrics": {"type": "integer"},
                                        "total_resources": {"type": "integer"},
                                        "synced_resources": {"type": "integer"},
                                        "drift_detected": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }


def get_vpc_api_endpoints() -> Dict[str, Any]:
    """Get VPC API endpoint specifications"""
    
    return {
        "/vpcs/": {
            "get": {
                "tags": ["vpc-api"],
                "summary": "List VPC resources",
                "description": "Retrieve list of VPC Custom Resource Definitions",
                "operationId": "listVPCs",
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
    }


def get_wiring_api_endpoints() -> Dict[str, Any]:
    """Get Wiring API endpoint specifications"""
    
    return {
        "/connections/": {
            "get": {
                "tags": ["wiring-api"],
                "summary": "List connection resources",
                "description": "Retrieve list of Connection Custom Resource Definitions",
                "operationId": "listConnections",
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


def get_custom_endpoints() -> Dict[str, Any]:
    """Get custom operation endpoint specifications"""
    
    return {
        "/sync/": {
            "post": {
                "tags": ["sync"],
                "summary": "Global sync operation",
                "description": "Trigger global synchronization across all fabrics",
                "operationId": "globalSync",
                "responses": {
                    "200": {"description": "Sync operation started"},
                    "409": {"description": "Sync already in progress"}
                }
            }
        },
        "/status/": {
            "get": {
                "tags": ["system"],
                "summary": "Get system status",
                "description": "Get overall system health and status information", 
                "operationId": "getSystemStatus",
                "responses": {
                    "200": {
                        "description": "System status",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "version": {"type": "string"},
                                        "status": {
                                            "type": "string",
                                            "enum": ["healthy", "degraded", "unhealthy"]
                                        },
                                        "fabrics": {"type": "integer"},
                                        "repositories": {"type": "integer"},
                                        "last_sync": {
                                            "type": "string",
                                            "format": "date-time"
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