"""
OpenAPI Error Schema Definitions

Defines structured error response schemas for consistent API error handling.
"""

from typing import Dict, Any


def get_error_schemas() -> Dict[str, Any]:
    """
    Get error response schemas for OpenAPI specification.
    
    Returns:
        Dictionary of error response definitions
    """
    
    return {
        "BadRequest": {
            "description": "Bad Request - Invalid input parameters or malformed request",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["error"],
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "Human-readable error message",
                                "example": "Invalid input parameters"
                            },
                            "error_code": {
                                "type": "string",
                                "description": "Machine-readable error code",
                                "example": "VALIDATION_ERROR"
                            },
                            "details": {
                                "type": "object",
                                "description": "Additional error details",
                                "properties": {
                                    "field_errors": {
                                        "type": "object",
                                        "additionalProperties": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        },
                                        "description": "Field-specific validation errors"
                                    },
                                    "non_field_errors": {
                                        "type": "array", 
                                        "items": {"type": "string"},
                                        "description": "General validation errors"
                                    }
                                }
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time",
                                "description": "Error timestamp"
                            },
                            "request_id": {
                                "type": "string",
                                "description": "Unique request identifier for debugging"
                            }
                        }
                    },
                    "examples": {
                        "validationError": {
                            "summary": "Validation error example",
                            "value": {
                                "error": "Validation failed",
                                "error_code": "VALIDATION_ERROR",
                                "details": {
                                    "field_errors": {
                                        "name": ["This field is required."],
                                        "kubernetes_server": ["Enter a valid URL."]
                                    }
                                },
                                "timestamp": "2024-01-15T12:00:00Z",
                                "request_id": "req_123456"
                            }
                        }
                    }
                }
            }
        },
        
        "Unauthorized": {
            "description": "Unauthorized - Authentication credentials missing or invalid",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["error"],
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "Authentication error message",
                                "example": "Authentication credentials were not provided."
                            },
                            "error_code": {
                                "type": "string",
                                "description": "Authentication error code",
                                "example": "AUTHENTICATION_REQUIRED"
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time"
                            }
                        }
                    },
                    "examples": {
                        "missingCredentials": {
                            "summary": "Missing authentication",
                            "value": {
                                "error": "Authentication credentials were not provided.",
                                "error_code": "AUTHENTICATION_REQUIRED",
                                "timestamp": "2024-01-15T12:00:00Z"
                            }
                        },
                        "invalidToken": {
                            "summary": "Invalid API token",
                            "value": {
                                "error": "Invalid token.",
                                "error_code": "INVALID_TOKEN", 
                                "timestamp": "2024-01-15T12:00:00Z"
                            }
                        }
                    }
                }
            }
        },
        
        "Forbidden": {
            "description": "Forbidden - Insufficient permissions for this operation",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["error"],
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "Permission error message",
                                "example": "You do not have permission to perform this action."
                            },
                            "error_code": {
                                "type": "string",
                                "description": "Permission error code",
                                "example": "INSUFFICIENT_PERMISSIONS"
                            },
                            "required_permissions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Permissions required for this operation"
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time"
                            }
                        }
                    },
                    "example": {
                        "error": "You do not have permission to perform this action.",
                        "error_code": "INSUFFICIENT_PERMISSIONS",
                        "required_permissions": ["netbox_hedgehog.change_hedgehogfabric"],
                        "timestamp": "2024-01-15T12:00:00Z"
                    }
                }
            }
        },
        
        "NotFound": {
            "description": "Not Found - The requested resource does not exist",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["error"],
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "Not found error message",
                                "example": "Not found."
                            },
                            "error_code": {
                                "type": "string",
                                "description": "Not found error code",
                                "example": "RESOURCE_NOT_FOUND"
                            },
                            "resource_type": {
                                "type": "string",
                                "description": "Type of resource that was not found",
                                "example": "HedgehogFabric"
                            },
                            "resource_id": {
                                "type": "integer",
                                "description": "ID of resource that was not found",
                                "example": 123
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time"
                            }
                        }
                    },
                    "example": {
                        "error": "Fabric not found.",
                        "error_code": "RESOURCE_NOT_FOUND",
                        "resource_type": "HedgehogFabric",
                        "resource_id": 123,
                        "timestamp": "2024-01-15T12:00:00Z"
                    }
                }
            }
        },
        
        "Conflict": {
            "description": "Conflict - Request conflicts with current resource state",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["error"],
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "Conflict error message",
                                "example": "Operation conflicts with current resource state."
                            },
                            "error_code": {
                                "type": "string",
                                "description": "Conflict error code",
                                "example": "RESOURCE_CONFLICT"
                            },
                            "conflicts": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "description": {"type": "string"},
                                        "resource_id": {"type": "integer"}
                                    }
                                },
                                "description": "Detailed conflict information"
                            },
                            "suggested_actions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Suggested actions to resolve conflict"
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time"
                            }
                        }
                    },
                    "example": {
                        "error": "Fabric name already exists.",
                        "error_code": "RESOURCE_CONFLICT",
                        "conflicts": [
                            {
                                "type": "name_conflict",
                                "description": "A fabric with this name already exists",
                                "resource_id": 456
                            }
                        ],
                        "suggested_actions": [
                            "Choose a different fabric name",
                            "Update the existing fabric instead"
                        ],
                        "timestamp": "2024-01-15T12:00:00Z"
                    }
                }
            }
        },
        
        "UnprocessableEntity": {
            "description": "Unprocessable Entity - Valid request format but semantic errors",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["error"],
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "Semantic error message",
                                "example": "Request cannot be processed due to semantic errors."
                            },
                            "error_code": {
                                "type": "string",
                                "description": "Semantic error code",
                                "example": "SEMANTIC_ERROR"
                            },
                            "validation_errors": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "field": {"type": "string"},
                                        "value": {"type": "string"},
                                        "error": {"type": "string"},
                                        "error_code": {"type": "string"}
                                    }
                                },
                                "description": "Detailed semantic validation errors"
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time"
                            }
                        }
                    },
                    "example": {
                        "error": "Invalid Kubernetes configuration.",
                        "error_code": "SEMANTIC_ERROR",
                        "validation_errors": [
                            {
                                "field": "kubernetes_server",
                                "value": "https://invalid-cluster:6443",
                                "error": "Cannot connect to Kubernetes cluster",
                                "error_code": "CONNECTION_FAILED"
                            }
                        ],
                        "timestamp": "2024-01-15T12:00:00Z"
                    }
                }
            }
        },
        
        "InternalServerError": {
            "description": "Internal Server Error - An unexpected error occurred",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["error"],
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "Internal error message",
                                "example": "An unexpected error occurred."
                            },
                            "error_code": {
                                "type": "string",
                                "description": "Internal error code",
                                "example": "INTERNAL_ERROR"
                            },
                            "trace_id": {
                                "type": "string",
                                "description": "Trace ID for debugging",
                                "example": "trace_789abc"
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time"
                            }
                        }
                    },
                    "example": {
                        "error": "An unexpected error occurred while processing the request.",
                        "error_code": "INTERNAL_ERROR",
                        "trace_id": "trace_789abc",
                        "timestamp": "2024-01-15T12:00:00Z"
                    }
                }
            }
        },
        
        "ServiceUnavailable": {
            "description": "Service Unavailable - Temporary service disruption",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["error"],
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "Service unavailable message",
                                "example": "Service temporarily unavailable."
                            },
                            "error_code": {
                                "type": "string", 
                                "description": "Service error code",
                                "example": "SERVICE_UNAVAILABLE"
                            },
                            "retry_after": {
                                "type": "integer",
                                "description": "Suggested retry delay in seconds",
                                "example": 300
                            },
                            "maintenance_mode": {
                                "type": "boolean",
                                "description": "Whether service is in maintenance mode",
                                "example": False
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time"
                            }
                        }
                    },
                    "example": {
                        "error": "Kubernetes cluster temporarily unavailable.",
                        "error_code": "SERVICE_UNAVAILABLE", 
                        "retry_after": 300,
                        "maintenance_mode": False,
                        "timestamp": "2024-01-15T12:00:00Z"
                    }
                }
            }
        }
    }


def get_error_codes() -> Dict[str, str]:
    """
    Get mapping of error codes to descriptions.
    Integrated with comprehensive error handling catalog from Issue #21.
    
    Returns:
        Dictionary mapping error codes to human-readable descriptions
    """
    
    return {
        # Legacy error codes (maintained for backward compatibility)
        "AUTHENTICATION_REQUIRED": "Authentication credentials are required",
        "INVALID_TOKEN": "The provided API token is invalid or expired", 
        "INSUFFICIENT_PERMISSIONS": "User lacks required permissions for this operation",
        "VALIDATION_ERROR": "Input validation failed",
        "SEMANTIC_ERROR": "Request is syntactically valid but semantically incorrect",
        "SCHEMA_VALIDATION_ERROR": "Data does not conform to expected schema",
        "RESOURCE_NOT_FOUND": "The requested resource does not exist",
        "RESOURCE_CONFLICT": "Operation conflicts with existing resource state",
        "RESOURCE_LOCKED": "Resource is currently locked for modification",
        "RESOURCE_DEPENDENCY_ERROR": "Operation violates resource dependencies",
        "KUBERNETES_CONNECTION_ERROR": "Cannot connect to Kubernetes cluster",
        "GIT_CONNECTION_ERROR": "Cannot connect to Git repository",
        "INVALID_CONFIGURATION": "Configuration is invalid or incomplete",
        "DRIFT_DETECTED": "Resource drift detected between desired and actual state",
        "OPERATION_IN_PROGRESS": "Another operation is already in progress",
        "OPERATION_FAILED": "The requested operation failed to complete",
        "SYNC_ERROR": "Synchronization operation failed",
        "ROLLBACK_REQUIRED": "Operation requires rollback due to errors",
        "INTERNAL_ERROR": "An unexpected internal error occurred",
        "SERVICE_UNAVAILABLE": "Service is temporarily unavailable",
        "RATE_LIMITED": "Request rate limit exceeded",
        "TIMEOUT_ERROR": "Operation timed out",
        
        # Comprehensive Error Catalog (Issue #21) - Authentication & Authorization
        "HH-AUTH-001": "GitHub token is invalid or malformed",
        "HH-AUTH-002": "GitHub token has expired",
        "HH-AUTH-003": "GitHub token is missing where required",
        "HH-AUTH-004": "Kubernetes service account token is invalid",
        "HH-AUTH-005": "Kubernetes token has expired",
        "HH-AUTH-006": "Kubernetes credentials not configured",
        "HH-AUTH-007": "SSH key for Git access is invalid or corrupted",
        "HH-AUTH-008": "SSH key lacks permission for repository",
        "HH-AUTH-010": "GitHub token lacks required repository permissions",
        "HH-AUTH-011": "User cannot access Git repository",
        "HH-AUTH-012": "Service account lacks required Kubernetes permissions",
        "HH-AUTH-013": "Cannot access specified Kubernetes namespace",
        "HH-AUTH-014": "Cannot access specific Kubernetes resource",
        "HH-AUTH-015": "Operation requires administrative privileges",
        "HH-AUTH-020": "Cannot generate new authentication token",
        "HH-AUTH-021": "Token format validation failed",
        "HH-AUTH-022": "Cannot securely store authentication token",
        "HH-AUTH-023": "Cannot update expired token",
        "HH-AUTH-024": "Cannot encrypt token for storage",
        
        # Git & GitHub Integration Errors
        "HH-GIT-001": "Git repository URL is invalid or inaccessible",
        "HH-GIT-002": "Git repository authentication failed",
        "HH-GIT-003": "User lacks required repository permissions",
        "HH-GIT-004": "Git repository service temporarily unavailable",
        "HH-GIT-005": "Git repository is locked for maintenance",
        "HH-GIT-006": "Git repository URL format is invalid",
        "HH-GIT-010": "Cannot clone repository to local filesystem",
        "HH-GIT-011": "Cannot fetch latest changes from remote",
        "HH-GIT-012": "Cannot push local changes to remote",
        "HH-GIT-013": "Cannot pull remote changes",
        "HH-GIT-014": "Automatic merge failed due to conflicts",
        "HH-GIT-015": "Specified Git branch does not exist",
        "HH-GIT-016": "Cannot create Git commit",
        "HH-GIT-017": "Cannot create or retrieve Git tag",
        "HH-GIT-020": "Exceeded GitHub API rate limit",
        "HH-GIT-021": "GitHub API token invalid or expired",
        "HH-GIT-022": "Requested GitHub resource doesn't exist",
        "HH-GIT-023": "Using unsupported GitHub API version",
        "HH-GIT-024": "Cannot create or update GitHub webhook",
        "HH-GIT-025": "GitHub API returned server error",
        "HH-GIT-030": "Referenced file doesn't exist in Git repository",
        "HH-GIT-031": "Cannot write to file in repository",
        "HH-GIT-032": "File content doesn't match expected format",
        "HH-GIT-033": "Required directory structure missing",
        "HH-GIT-034": "File size exceeds repository limits",
        "HH-GIT-035": "Unexpected binary file in YAML directory",
        
        # Kubernetes API Errors
        "HH-K8S-001": "Cannot connect to Kubernetes API server",
        "HH-K8S-002": "Kubernetes authentication failed",
        "HH-K8S-003": "TLS certificate validation failed",
        "HH-K8S-004": "Request to Kubernetes API timed out",
        "HH-K8S-005": "Kubernetes version not supported",
        "HH-K8S-006": "Kubernetes API server not responding",
        "HH-K8S-010": "Custom Resource Definition doesn't exist",
        "HH-K8S-011": "Resource spec doesn't match CRD schema",
        "HH-K8S-012": "CRD version incompatible with resource",
        "HH-K8S-013": "Cannot install Custom Resource Definition",
        "HH-K8S-014": "Cannot update existing CRD",
        "HH-K8S-020": "Cannot create Kubernetes resource",
        "HH-K8S-021": "Cannot update existing Kubernetes resource",
        "HH-K8S-022": "Cannot delete Kubernetes resource",
        "HH-K8S-023": "Requested Kubernetes resource doesn't exist",
        "HH-K8S-024": "Resource name conflicts with existing",
        "HH-K8S-025": "Request exceeds namespace resource quotas",
        "HH-K8S-026": "Finalizers prevent resource deletion",
        "HH-K8S-030": "Target namespace doesn't exist",
        "HH-K8S-031": "Cannot create new namespace",
        "HH-K8S-032": "Required service account doesn't exist",
        "HH-K8S-033": "Service account lacks required permissions",
        "HH-K8S-034": "Required cluster role not found",
        "HH-K8S-035": "Cannot bind role to service account",
        
        # Data Validation Errors
        "HH-VAL-001": "YAML file contains syntax errors",
        "HH-VAL-002": "YAML structure doesn't match expected format",
        "HH-VAL-003": "Data doesn't match required JSON schema",
        "HH-VAL-004": "Field value type doesn't match expected",
        "HH-VAL-005": "Mandatory field not provided",
        "HH-VAL-006": "Field contains invalid value",
        "HH-VAL-010": "Attempted state transition not allowed",
        "HH-VAL-011": "Required dependency not met",
        "HH-VAL-012": "Data violates business rule constraints",
        "HH-VAL-013": "Foreign key constraint violation",
        "HH-VAL-014": "Value must be unique but already exists",
        "HH-VAL-020": "Data format doesn't match expected pattern",
        "HH-VAL-021": "Value outside acceptable range",
        "HH-VAL-022": "String length outside acceptable range",
        "HH-VAL-023": "Value doesn't match required regex pattern",
        "HH-VAL-024": "Email address format invalid",
        "HH-VAL-025": "URL format invalid",
        "HH-VAL-030": "Referenced resource doesn't exist",
        "HH-VAL-031": "Resources create circular reference",
        "HH-VAL-032": "Resource versions incompatible",
        "HH-VAL-033": "Resources in incompatible namespaces",
        "HH-VAL-034": "Resource reference points to wrong type",
        
        # Network & Connectivity Errors
        "HH-NET-001": "Request timed out waiting for response",
        "HH-NET-002": "Target service refused connection",
        "HH-NET-003": "Cannot resolve hostname to IP address",
        "HH-NET-004": "Network routing prevents connection",
        "HH-NET-005": "Target port blocked by firewall",
        "HH-NET-006": "HTTP proxy misconfigured",
        "HH-NET-010": "SSL/TLS negotiation failed",
        "HH-NET-011": "TLS certificate validation failed",
        "HH-NET-012": "HTTP request returned error status",
        "HH-NET-013": "Cannot establish WebSocket connection",
        "HH-NET-014": "Unsupported protocol version",
        "HH-NET-015": "Response content type unexpected",
        "HH-NET-020": "Target service temporarily unavailable",
        "HH-NET-021": "Load balancer cannot route request",
        "HH-NET-022": "Circuit breaker preventing requests",
        "HH-NET-023": "Service health check indicates problem",
        "HH-NET-024": "Request rate limit exceeded",
        "HH-NET-025": "Network bandwidth limit reached",
        
        # State Transition Errors
        "HH-STATE-001": "Current state cannot transition to target",
        "HH-STATE-002": "Required condition for transition not satisfied",
        "HH-STATE-003": "Another process holds state transition lock",
        "HH-STATE-004": "State changed since last read (optimistic locking)",
        "HH-STATE-005": "State transition exceeded time limit",
        "HH-STATE-010": "Entity in inconsistent internal state",
        "HH-STATE-011": "Cannot sync state across components",
        "HH-STATE-012": "Cannot save state changes to database",
        "HH-STATE-013": "Cannot recover from corrupted state",
        "HH-STATE-014": "State machine definition invalid",
        "HH-STATE-020": "Individual workflow step failed",
        "HH-STATE-021": "Workflow exceeded maximum execution time",
        "HH-STATE-022": "Cannot rollback partial workflow",
        "HH-STATE-023": "Dependent workflow step failed",
        "HH-STATE-024": "Workflow suspended awaiting external input"
    }