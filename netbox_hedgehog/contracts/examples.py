"""
Contract Examples and Test Data Generator

Provides example data for all models and validation of contract completeness.
This enables automated testing and serves as documentation for agents.
"""

from typing import Dict, Any, List
import json
from datetime import datetime
from .models.core import get_example_data as get_core_examples
from .models.gitops import get_example_data as get_gitops_examples  
from .models.vpc_api import get_example_data as get_vpc_examples
from .models.wiring_api import get_example_data as get_wiring_examples


def get_all_examples() -> Dict[str, Any]:
    """
    Get example data for all models.
    
    Returns:
        Dictionary mapping model names to example instances
    """
    
    examples = {}
    
    # Core model examples
    examples.update(get_core_examples())
    
    # GitOps model examples
    examples.update(get_gitops_examples())
    
    # VPC API model examples
    examples.update(get_vpc_examples())
    
    # Wiring API model examples
    examples.update(get_wiring_examples())
    
    return examples


def get_workflow_examples() -> Dict[str, Any]:
    """
    Get example workflow scenarios that demonstrate model relationships.
    
    Returns:
        Dictionary of workflow scenarios with example data
    """
    
    return {
        "basic_fabric_setup": {
            "description": "Basic fabric setup with Git repository integration",
            "steps": [
                {
                    "step": 1,
                    "action": "Create Git repository",
                    "model": "GitRepository",
                    "data": {
                        "name": "hedgehog-production-config",
                        "url": "https://github.com/example/hedgehog-config.git",
                        "provider": "GITHUB",
                        "authentication_type": "TOKEN",
                        "is_private": True
                    }
                },
                {
                    "step": 2, 
                    "action": "Create Hedgehog fabric",
                    "model": "HedgehogFabric",
                    "data": {
                        "name": "production-fabric",
                        "description": "Production network fabric",
                        "status": "PLANNED",
                        "kubernetes_server": "https://k8s-prod.example.com:6443",
                        "git_repository": 1,
                        "gitops_directory": "/production/",
                        "sync_enabled": True
                    }
                },
                {
                    "step": 3,
                    "action": "Test connections",
                    "description": "Validate Kubernetes and Git connectivity"
                }
            ]
        },
        
        "vpc_configuration": {
            "description": "VPC configuration with networking resources",
            "prerequisites": ["basic_fabric_setup"],
            "steps": [
                {
                    "step": 1,
                    "action": "Create IPv4 namespace",
                    "model": "IPv4Namespace",
                    "data": {
                        "fabric": 1,
                        "name": "production-ipv4",
                        "namespace": "default",
                        "spec": {
                            "subnets": ["10.0.0.0/8", "192.168.0.0/16"]
                        }
                    }
                },
                {
                    "step": 2,
                    "action": "Create VPC",
                    "model": "VPC", 
                    "data": {
                        "fabric": 1,
                        "name": "app-vpc",
                        "namespace": "default",
                        "spec": {
                            "subnets": ["10.1.0.0/16"],
                            "permit": ["any"],
                            "vlanNamespace": "default"
                        }
                    }
                },
                {
                    "step": 3,
                    "action": "Create external system",
                    "model": "External",
                    "data": {
                        "fabric": 1,
                        "name": "internet-gateway",
                        "namespace": "default",
                        "spec": {
                            "inbound": ["0.0.0.0/0"],
                            "outbound": ["10.0.0.0/8"]
                        }
                    }
                },
                {
                    "step": 4,
                    "action": "Create VPC to external peering",
                    "model": "ExternalPeering",
                    "data": {
                        "fabric": 1,
                        "name": "app-internet-peering",
                        "namespace": "default",
                        "spec": {
                            "permit": {
                                "vpc": {"name": "app-vpc"},
                                "external": {"name": "internet-gateway"}
                            }
                        }
                    }
                }
            ]
        },
        
        "wiring_configuration": {
            "description": "Physical wiring and switch configuration",
            "prerequisites": ["basic_fabric_setup"],
            "steps": [
                {
                    "step": 1,
                    "action": "Create VLAN namespace",
                    "model": "VLANNamespace",
                    "data": {
                        "fabric": 1,
                        "name": "production-vlans",
                        "namespace": "default",
                        "spec": {
                            "ranges": ["100-199", "1000-1099"]
                        }
                    }
                },
                {
                    "step": 2,
                    "action": "Create spine switch",
                    "model": "Switch",
                    "data": {
                        "fabric": 1,
                        "name": "spine-01",
                        "namespace": "default",
                        "spec": {
                            "role": "spine",
                            "asn": 65100,
                            "ip": "10.0.1.1/32",
                            "portGroupSpeeds": ["100G"],
                            "portSpeeds": ["25G"]
                        }
                    }
                },
                {
                    "step": 3,
                    "action": "Create server",
                    "model": "Server",
                    "data": {
                        "fabric": 1,
                        "name": "web-server-01",
                        "namespace": "default",
                        "spec": {
                            "description": "Production web server",
                            "interfaces": [
                                {
                                    "name": "Ethernet1",
                                    "ip": "dhcp"
                                }
                            ]
                        }
                    }
                },
                {
                    "step": 4,
                    "action": "Create connection",
                    "model": "Connection",
                    "data": {
                        "fabric": 1,
                        "name": "server-spine-connection",
                        "namespace": "default",
                        "spec": {
                            "unbundled": {
                                "link": {
                                    "server": {"port": "Ethernet1"},
                                    "switch": {"port": "Ethernet1"}
                                }
                            }
                        }
                    }
                }
            ]
        },
        
        "gitops_workflow": {
            "description": "Complete GitOps workflow with drift detection",
            "prerequisites": ["vpc_configuration", "wiring_configuration"],
            "steps": [
                {
                    "step": 1,
                    "action": "Create GitOps resource tracker",
                    "model": "HedgehogResource",
                    "data": {
                        "fabric": 1,
                        "name": "app-vpc",
                        "namespace": "default",
                        "kind": "VPC",
                        "api_version": "vpc.githedgehog.com/v1beta1",
                        "desired_spec": {
                            "subnets": ["10.1.0.0/16"],
                            "permit": ["any"]
                        },
                        "resource_state": "committed"
                    }
                },
                {
                    "step": 2,
                    "action": "Simulate drift",
                    "description": "Simulate actual state differing from desired state",
                    "update": {
                        "actual_spec": {
                            "subnets": ["10.1.0.0/16", "10.1.1.0/24"],
                            "permit": ["any"]
                        },
                        "drift_status": "spec_drift",
                        "drift_score": 0.3
                    }
                },
                {
                    "step": 3,
                    "action": "Create reconciliation alert",
                    "model": "ReconciliationAlert",
                    "data": {
                        "fabric": 1,
                        "resource": 1,
                        "alert_type": "drift_detected",
                        "severity": "medium",
                        "title": "VPC Configuration Drift Detected",
                        "message": "VPC subnets have been modified outside of Git",
                        "suggested_action": "update_git",
                        "drift_details": {
                            "added_subnets": ["10.1.1.0/24"],
                            "drift_type": "subnet_addition"
                        }
                    }
                },
                {
                    "step": 4,
                    "action": "Record state transition",
                    "model": "StateTransitionHistory",
                    "data": {
                        "resource": 1,
                        "from_state": "committed",
                        "to_state": "drifted",
                        "trigger": "drift_detection",
                        "reason": "Actual state differs from desired state",
                        "context": {
                            "drift_score": 0.3,
                            "detection_method": "periodic_scan"
                        }
                    }
                }
            ]
        }
    }


def get_test_scenarios() -> Dict[str, Any]:
    """
    Get test scenarios for validating contract implementations.
    
    Returns:
        Dictionary of test scenarios with expected behaviors
    """
    
    return {
        "model_validation": {
            "description": "Test model schema validation",
            "tests": [
                {
                    "name": "valid_fabric_creation", 
                    "model": "HedgehogFabric",
                    "data": {
                        "name": "test-fabric",
                        "description": "Test fabric",
                        "status": "PLANNED"
                    },
                    "expected": "valid"
                },
                {
                    "name": "invalid_fabric_name",
                    "model": "HedgehogFabric",
                    "data": {
                        "name": "",  # Empty name should fail
                        "status": "PLANNED"
                    },
                    "expected": "validation_error",
                    "expected_errors": ["name: This field is required"]
                },
                {
                    "name": "invalid_fabric_status",
                    "model": "HedgehogFabric",
                    "data": {
                        "name": "test-fabric",
                        "status": "INVALID_STATUS"
                    },
                    "expected": "validation_error",
                    "expected_errors": ["status: Invalid choice"]
                }
            ]
        },
        
        "relationship_validation": {
            "description": "Test model relationship constraints",
            "tests": [
                {
                    "name": "valid_fabric_git_relationship",
                    "setup": [
                        {"model": "GitRepository", "id": 1, "data": {"name": "test-repo", "url": "https://github.com/test/repo.git"}},
                        {"model": "HedgehogFabric", "data": {"name": "test-fabric", "git_repository": 1}}
                    ],
                    "expected": "valid"
                },
                {
                    "name": "invalid_fabric_git_relationship",
                    "setup": [
                        {"model": "HedgehogFabric", "data": {"name": "test-fabric", "git_repository": 999}}
                    ],
                    "expected": "validation_error",
                    "expected_errors": ["git_repository: Invalid pk"]
                }
            ]
        },
        
        "api_operation_validation": {
            "description": "Test API operation behaviors",
            "tests": [
                {
                    "name": "successful_fabric_list",
                    "operation": "GET /fabrics/",
                    "expected_status": 200,
                    "expected_fields": ["count", "results"]
                },
                {
                    "name": "successful_fabric_detail",
                    "operation": "GET /fabrics/1/",
                    "expected_status": 200,
                    "expected_fields": ["id", "name", "status"]
                },
                {
                    "name": "fabric_not_found",
                    "operation": "GET /fabrics/999/",
                    "expected_status": 404,
                    "expected_error": "RESOURCE_NOT_FOUND"
                },
                {
                    "name": "unauthorized_access",
                    "operation": "GET /fabrics/",
                    "headers": {},  # No authentication
                    "expected_status": 401,
                    "expected_error": "AUTHENTICATION_REQUIRED"
                }
            ]
        }
    }


def validate_contract_completeness() -> Dict[str, Any]:
    """
    Validate that contracts are complete and consistent.
    
    Returns:
        Validation report with any issues found
    """
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "status": "passed",
        "issues": [],
        "statistics": {}
    }
    
    try:
        # Check all models have examples
        examples = get_all_examples()
        expected_models = [
            "HedgehogFabric", "GitRepository", "BaseCRD",
            "HedgehogResource", "StateTransitionHistory", "ReconciliationAlert",
            "VPC", "External", "ExternalAttachment", "ExternalPeering", 
            "IPv4Namespace", "VPCAttachment", "VPCPeering",
            "Connection", "Server", "Switch", "SwitchGroup", "VLANNamespace"
        ]
        
        missing_examples = []
        for model in expected_models:
            if model not in examples:
                missing_examples.append(model)
        
        if missing_examples:
            report["issues"].append({
                "type": "missing_examples",
                "severity": "warning",
                "message": f"Missing examples for models: {missing_examples}"
            })
        
        # Check workflow completeness
        workflows = get_workflow_examples()
        if len(workflows) < 4:
            report["issues"].append({
                "type": "insufficient_workflows",
                "severity": "info", 
                "message": "Consider adding more workflow examples"
            })
        
        # Statistics
        report["statistics"] = {
            "total_models": len(expected_models),
            "models_with_examples": len(examples),
            "total_workflows": len(workflows),
            "test_scenarios": len(get_test_scenarios())
        }
        
        # Set overall status
        if any(issue["severity"] == "error" for issue in report["issues"]):
            report["status"] = "failed"
        elif any(issue["severity"] == "warning" for issue in report["issues"]):
            report["status"] = "warning"
            
    except Exception as e:
        report["status"] = "error"
        report["issues"].append({
            "type": "validation_exception",
            "severity": "error",
            "message": f"Exception during validation: {str(e)}"
        })
    
    return report


def export_examples_json(file_path: str = None) -> str:
    """
    Export all examples to JSON file.
    
    Args:
        file_path: Optional file path, defaults to examples.json
        
    Returns:
        JSON string of all examples
    """
    
    export_data = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "version": "1.0.0",
            "description": "NetBox Hedgehog Plugin contract examples"
        },
        "model_examples": get_all_examples(),
        "workflow_examples": get_workflow_examples(),
        "test_scenarios": get_test_scenarios(),
        "validation_report": validate_contract_completeness()
    }
    
    json_data = json.dumps(export_data, indent=2, default=str)
    
    if file_path:
        with open(file_path, 'w') as f:
            f.write(json_data)
    
    return json_data