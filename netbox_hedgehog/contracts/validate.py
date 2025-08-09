#!/usr/bin/env python3
"""
Contract Validation Script

Validates that all contracts are complete, consistent, and machine-readable.
Can be used in CI/CD pipelines for automated validation.

Usage:
    python validate.py [--export-examples] [--export-openapi] [--strict]
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

try:
    from .examples import validate_contract_completeness, export_examples_json
    from .openapi.main import generate_openapi_spec
    from .models.core import get_json_schemas as get_core_schemas
    from .models.gitops import get_json_schemas as get_gitops_schemas
    from .models.vpc_api import get_json_schemas as get_vpc_schemas
    from .models.wiring_api import get_json_schemas as get_wiring_schemas
except ImportError:
    # Handle case where script is run standalone
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from examples import validate_contract_completeness, export_examples_json
        from openapi.main import generate_openapi_spec
        from models.core import get_json_schemas as get_core_schemas
        from models.gitops import get_json_schemas as get_gitops_schemas
        from models.vpc_api import get_json_schemas as get_vpc_schemas
        from models.wiring_api import get_json_schemas as get_wiring_schemas
    except ImportError as e:
        print(f"Error importing modules: {e}")
        sys.exit(1)


def validate_pydantic_schemas() -> Dict[str, Any]:
    """
    Validate all Pydantic model schemas are well-formed.
    
    Returns:
        Validation report for schema validation
    """
    
    report = {
        "status": "passed",
        "issues": [],
        "schemas_validated": 0
    }
    
    try:
        schema_groups = [
            ("core", get_core_schemas),
            ("gitops", get_gitops_schemas),
            ("vpc_api", get_vpc_schemas),
            ("wiring_api", get_wiring_schemas)
        ]
        
        for group_name, get_schemas_func in schema_groups:
            try:
                schemas = get_schemas_func()
                report["schemas_validated"] += len(schemas)
                
                for schema_name, schema_def in schemas.items():
                    # Basic schema validation
                    if not isinstance(schema_def, dict):
                        report["issues"].append({
                            "type": "invalid_schema_type",
                            "severity": "error",
                            "message": f"{group_name}.{schema_name}: Schema must be a dictionary"
                        })
                        continue
                    
                    # Check required fields
                    if "type" not in schema_def:
                        report["issues"].append({
                            "type": "missing_schema_type",
                            "severity": "error", 
                            "message": f"{group_name}.{schema_name}: Schema missing 'type' field"
                        })
                    
                    # Check properties exist for object types
                    if schema_def.get("type") == "object" and "properties" not in schema_def:
                        report["issues"].append({
                            "type": "missing_properties",
                            "severity": "warning",
                            "message": f"{group_name}.{schema_name}: Object schema missing 'properties'"
                        })
            
            except Exception as e:
                report["issues"].append({
                    "type": "schema_generation_error",
                    "severity": "error",
                    "message": f"Error generating {group_name} schemas: {str(e)}"
                })
    
    except Exception as e:
        report["issues"].append({
            "type": "validation_exception",
            "severity": "error",
            "message": f"Exception during schema validation: {str(e)}"
        })
    
    # Set overall status
    if any(issue["severity"] == "error" for issue in report["issues"]):
        report["status"] = "failed"
    elif any(issue["severity"] == "warning" for issue in report["issues"]):
        report["status"] = "warning"
    
    return report


def validate_openapi_spec() -> Dict[str, Any]:
    """
    Validate OpenAPI specification is well-formed.
    
    Returns:
        Validation report for OpenAPI specification
    """
    
    report = {
        "status": "passed",
        "issues": [],
        "endpoints_validated": 0
    }
    
    try:
        spec = generate_openapi_spec()
        
        # Validate basic structure
        required_fields = ["openapi", "info", "paths", "components"]
        for field in required_fields:
            if field not in spec:
                report["issues"].append({
                    "type": "missing_openapi_field",
                    "severity": "error",
                    "message": f"OpenAPI spec missing required field: {field}"
                })
        
        # Validate OpenAPI version
        if spec.get("openapi") != "3.0.3":
            report["issues"].append({
                "type": "invalid_openapi_version",
                "severity": "warning",
                "message": f"Expected OpenAPI 3.0.3, got: {spec.get('openapi')}"
            })
        
        # Validate paths
        if "paths" in spec:
            report["endpoints_validated"] = len(spec["paths"])
            
            for path, path_def in spec["paths"].items():
                if not isinstance(path_def, dict):
                    report["issues"].append({
                        "type": "invalid_path_definition",
                        "severity": "error",
                        "message": f"Path {path} definition must be a dictionary"
                    })
                    continue
                
                # Check that at least one HTTP method is defined
                http_methods = ["get", "post", "put", "patch", "delete", "head", "options"]
                if not any(method in path_def for method in http_methods):
                    report["issues"].append({
                        "type": "no_http_methods",
                        "severity": "warning",
                        "message": f"Path {path} has no HTTP methods defined"
                    })
        
        # Validate components
        if "components" in spec and "schemas" in spec["components"]:
            for schema_name, schema_def in spec["components"]["schemas"].items():
                if not isinstance(schema_def, dict):
                    report["issues"].append({
                        "type": "invalid_component_schema",
                        "severity": "error",
                        "message": f"Component schema {schema_name} must be a dictionary"
                    })
    
    except Exception as e:
        report["issues"].append({
            "type": "openapi_generation_error", 
            "severity": "error",
            "message": f"Error generating OpenAPI spec: {str(e)}"
        })
    
    # Set overall status
    if any(issue["severity"] == "error" for issue in report["issues"]):
        report["status"] = "failed"
    elif any(issue["severity"] == "warning" for issue in report["issues"]):
        report["status"] = "warning"
    
    return report


def run_full_validation(strict: bool = False) -> Dict[str, Any]:
    """
    Run complete validation of all contracts.
    
    Args:
        strict: If True, warnings are treated as errors
        
    Returns:
        Complete validation report
    """
    
    print("🔍 Running NetBox Hedgehog Plugin contract validation...")
    
    full_report = {
        "timestamp": datetime.now().isoformat(),
        "status": "passed",
        "reports": {},
        "summary": {}
    }
    
    # Run all validation checks
    validations = [
        ("contract_completeness", validate_contract_completeness),
        ("pydantic_schemas", validate_pydantic_schemas),
        ("openapi_specification", validate_openapi_spec)
    ]
    
    total_issues = 0
    error_count = 0
    warning_count = 0
    
    for validation_name, validation_func in validations:
        print(f"  ✓ Running {validation_name} validation...")
        
        try:
            report = validation_func()
            full_report["reports"][validation_name] = report
            
            issues = report.get("issues", [])
            total_issues += len(issues)
            
            for issue in issues:
                if issue["severity"] == "error":
                    error_count += 1
                elif issue["severity"] == "warning":
                    warning_count += 1
                    
        except Exception as e:
            error_count += 1
            full_report["reports"][validation_name] = {
                "status": "error",
                "issues": [{
                    "type": "validation_failure",
                    "severity": "error",
                    "message": f"Validation failed with exception: {str(e)}"
                }]
            }
    
    # Generate summary
    full_report["summary"] = {
        "total_validations": len(validations),
        "total_issues": total_issues,
        "error_count": error_count,
        "warning_count": warning_count
    }
    
    # Determine overall status
    if error_count > 0:
        full_report["status"] = "failed"
    elif warning_count > 0 and strict:
        full_report["status"] = "failed"
    elif warning_count > 0:
        full_report["status"] = "warning"
    else:
        full_report["status"] = "passed"
    
    return full_report


def print_validation_report(report: Dict[str, Any]) -> None:
    """Print validation report in human-readable format."""
    
    print(f"\n📋 Validation Report - {report['timestamp']}")
    print(f"Status: {'✅ PASSED' if report['status'] == 'passed' else '❌ FAILED' if report['status'] == 'failed' else '⚠️ WARNING'}")
    
    if "summary" in report:
        summary = report["summary"]
        print(f"\nSummary:")
        print(f"  Total validations: {summary['total_validations']}")
        print(f"  Total issues: {summary['total_issues']}")
        print(f"  Errors: {summary['error_count']}")
        print(f"  Warnings: {summary['warning_count']}")
    
    # Print details for each validation
    for validation_name, validation_report in report.get("reports", {}).items():
        status_icon = "✅" if validation_report["status"] == "passed" else "❌" if validation_report["status"] == "failed" else "⚠️"
        print(f"\n{status_icon} {validation_name.replace('_', ' ').title()}:")
        
        issues = validation_report.get("issues", [])
        if not issues:
            print("  No issues found")
        else:
            for issue in issues:
                severity_icon = "❌" if issue["severity"] == "error" else "⚠️" if issue["severity"] == "warning" else "ℹ️"
                print(f"  {severity_icon} {issue['message']}")


def main():
    """Main entry point for validation script."""
    
    parser = argparse.ArgumentParser(description="Validate NetBox Hedgehog Plugin contracts")
    parser.add_argument("--export-examples", action="store_true", 
                       help="Export examples to JSON file")
    parser.add_argument("--export-openapi", action="store_true",
                       help="Export OpenAPI specification to JSON file")
    parser.add_argument("--strict", action="store_true",
                       help="Treat warnings as errors")
    parser.add_argument("--output-dir", type=str, default=".",
                       help="Output directory for exported files")
    
    args = parser.parse_args()
    
    # Run validation
    report = run_full_validation(strict=args.strict)
    print_validation_report(report)
    
    # Export files if requested
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    if args.export_examples:
        try:
            examples_file = output_dir / "contract_examples.json"
            export_examples_json(str(examples_file))
            print(f"\n📁 Examples exported to: {examples_file}")
        except Exception as e:
            print(f"\n❌ Error exporting examples: {e}")
    
    if args.export_openapi:
        try:
            openapi_file = output_dir / "openapi_spec.json"
            spec = generate_openapi_spec()
            with open(openapi_file, 'w') as f:
                json.dump(spec, f, indent=2)
            print(f"📁 OpenAPI spec exported to: {openapi_file}")
        except Exception as e:
            print(f"\n❌ Error exporting OpenAPI spec: {e}")
    
    # Exit with appropriate code
    if report["status"] == "failed":
        print(f"\n❌ Validation failed!")
        sys.exit(1)
    elif report["status"] == "warning":
        print(f"\n⚠️ Validation completed with warnings")
        sys.exit(0)
    else:
        print(f"\n✅ All validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()