#!/usr/bin/env python3
"""
Independent Validation Script for Issue #40 Periodic Sync Resolution
================================================================================

This script performs independent validation to detect fraudulent completion claims.
It checks actual implementation against claimed functionality.

CRITICAL MISSION: Determine if Issue #40 is actually resolved or if agents 
                  have fabricated evidence packages.
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Add Django path for model imports
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

def generate_timestamp():
    """Generate timestamp for evidence tracking."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def check_file_exists_and_size(filepath, expected_lines=None):
    """Check if file exists and optionally verify line count."""
    path = Path(filepath)
    if not path.exists():
        return {"exists": False, "lines": 0, "status": "FILE_NOT_FOUND"}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f)
    
    result = {
        "exists": True, 
        "lines": line_count,
        "expected_lines": expected_lines,
        "status": "EXISTS"
    }
    
    if expected_lines and abs(line_count - expected_lines) > 50:
        result["status"] = "LINE_COUNT_MISMATCH"
        result["discrepancy"] = line_count - expected_lines
    
    return result

def validate_django_imports():
    """Test if Django imports work (indicates proper environment setup)."""
    try:
        import django
        django.setup()
        
        from netbox_hedgehog.models.fabric import HedgehogFabric
        from netbox_hedgehog.choices import SyncStatusChoices
        
        return {"status": "SUCCESS", "django_ready": True}
    except Exception as e:
        return {"status": "FAILED", "error": str(e), "django_ready": False}

def check_rq_jobs_implementation():
    """Check if RQ jobs are actually implemented and importable."""
    results = {"jobs_module": None, "scheduler_module": None, "errors": []}
    
    try:
        # Check jobs module
        from netbox_hedgehog.jobs import fabric_sync
        results["jobs_module"] = {
            "importable": True,
            "has_FabricSyncJob": hasattr(fabric_sync, 'FabricSyncJob'),
            "has_execute_fabric_sync": hasattr(fabric_sync, 'FabricSyncJob') and 
                                      hasattr(fabric_sync.FabricSyncJob, 'execute_fabric_sync')
        }
    except ImportError as e:
        results["errors"].append(f"jobs.fabric_sync import failed: {e}")
        results["jobs_module"] = {"importable": False}
    
    try:
        # Check tasks module  
        from netbox_hedgehog.tasks import sync_tasks
        results["scheduler_module"] = {
            "importable": True,
            "has_master_sync_scheduler": hasattr(sync_tasks, 'master_sync_scheduler')
        }
    except ImportError as e:
        results["errors"].append(f"tasks.sync_tasks import failed: {e}")
        results["scheduler_module"] = {"importable": False}
    
    return results

def analyze_fabric_model_changes():
    """Analyze fabric model for claimed periodic sync enhancements."""
    try:
        import django
        django.setup()
        
        from netbox_hedgehog.models.fabric import HedgehogFabric
        
        # Check for required fields
        model_fields = [f.name for f in HedgehogFabric._meta.get_fields()]
        
        required_fields = ['sync_enabled', 'sync_interval', 'last_sync', 'scheduler_enabled']
        missing_fields = [f for f in required_fields if f not in model_fields]
        
        # Check for needs_sync method
        has_needs_sync = hasattr(HedgehogFabric, 'needs_sync')
        
        return {
            "status": "SUCCESS",
            "model_fields": model_fields,
            "required_fields_present": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "has_needs_sync_method": has_needs_sync
        }
    except Exception as e:
        return {"status": "FAILED", "error": str(e)}

def check_management_commands():
    """Check if management commands actually exist and are functional."""
    commands_path = Path('netbox_hedgehog/management/commands')
    
    hedgehog_sync_path = commands_path / 'hedgehog_sync.py'
    
    return {
        "hedgehog_sync_exists": hedgehog_sync_path.exists(),
        "hedgehog_sync_lines": hedgehog_sync_path.stat().st_size if hedgehog_sync_path.exists() else 0
    }

def detect_evidence_fraud():
    """Analyze evidence packages for potential fraud indicators."""
    evidence_files = [
        "ISSUE_40_PERIODIC_SYNC_RESOLUTION_COMPLETE.md",
        "PRODUCTION_SYNC_TESTING_EVIDENCE_COMPLETE.json", 
        "PERIODIC_SYNC_TIMER_FINAL_EVIDENCE.json",
        "FINAL_VALIDATION_EVIDENCE_PACKAGE.json"
    ]
    
    fraud_indicators = []
    file_analysis = {}
    
    for evidence_file in evidence_files:
        if os.path.exists(evidence_file):
            with open(evidence_file, 'r') as f:
                content = f.read()
                
            # Check for suspicious patterns
            suspicious_phrases = [
                "COMPLETE", "ACCOMPLISHED", "100%", "FULLY OPERATIONAL",
                "ALL TESTS PASSING", "PRODUCTION READY", "MISSION ACCOMPLISHED"
            ]
            
            matches = sum(1 for phrase in suspicious_phrases if phrase in content)
            
            file_analysis[evidence_file] = {
                "exists": True,
                "size": len(content),
                "suspicious_phrase_count": matches,
                "fraud_score": min(matches * 10, 100)  # Max 100% fraud score
            }
            
            if matches > 5:
                fraud_indicators.append(f"{evidence_file}: Excessive success claims ({matches} phrases)")
        else:
            file_analysis[evidence_file] = {"exists": False}
    
    return {
        "fraud_indicators": fraud_indicators,
        "file_analysis": file_analysis,
        "overall_fraud_risk": "HIGH" if len(fraud_indicators) > 2 else "MEDIUM" if fraud_indicators else "LOW"
    }

def run_independent_validation():
    """Run complete independent validation suite."""
    timestamp = generate_timestamp()
    results = {
        "validation_timestamp": timestamp,
        "validator": "Independent Validation Agent",
        "mission": "Detect fraud in Issue #40 completion claims",
        "methodology": "Evidence-based validation with fraud detection"
    }
    
    print("🔍 INDEPENDENT VALIDATION - Issue #40 Periodic Sync Resolution")
    print("=" * 70)
    
    # 1. File Existence Validation
    print("\n1️⃣ FILE EXISTENCE VALIDATION")
    file_checks = {
        "netbox_hedgehog/jobs/fabric_sync.py": 334,  # Claimed lines
        "netbox_hedgehog/tasks/sync_tasks.py": 655,  # Claimed lines  
        "netbox_hedgehog/migrations/0023_add_scheduler_enabled_field.py": None,
        "netbox_hedgehog/management/commands/hedgehog_sync.py": 250
    }
    
    results["file_validation"] = {}
    for filepath, expected_lines in file_checks.items():
        check_result = check_file_exists_and_size(filepath, expected_lines)
        results["file_validation"][filepath] = check_result
        print(f"   {filepath}: {check_result['status']} ({check_result['lines']} lines)")
    
    # 2. Django Environment Test
    print("\n2️⃣ DJANGO ENVIRONMENT VALIDATION")
    django_result = validate_django_imports()
    results["django_validation"] = django_result
    print(f"   Django Setup: {django_result['status']}")
    
    # 3. RQ Jobs Implementation
    print("\n3️⃣ RQ JOBS IMPLEMENTATION CHECK")
    rq_result = check_rq_jobs_implementation()
    results["rq_validation"] = rq_result
    print(f"   Jobs Module: {rq_result.get('jobs_module', {}).get('importable', False)}")
    print(f"   Scheduler Module: {rq_result.get('scheduler_module', {}).get('importable', False)}")
    
    # 4. Fabric Model Analysis
    print("\n4️⃣ FABRIC MODEL ENHANCEMENT VALIDATION")
    model_result = analyze_fabric_model_changes()
    results["model_validation"] = model_result
    if model_result["status"] == "SUCCESS":
        print(f"   Required Fields: {model_result['required_fields_present']}")
        print(f"   needs_sync() Method: {model_result['has_needs_sync_method']}")
    else:
        print(f"   Model Analysis Failed: {model_result.get('error', 'Unknown error')}")
    
    # 5. Management Commands
    print("\n5️⃣ MANAGEMENT COMMANDS VALIDATION")
    cmd_result = check_management_commands()
    results["commands_validation"] = cmd_result
    print(f"   hedgehog_sync command: {cmd_result['hedgehog_sync_exists']}")
    
    # 6. Fraud Detection Analysis
    print("\n6️⃣ EVIDENCE FRAUD DETECTION")
    fraud_result = detect_evidence_fraud()
    results["fraud_analysis"] = fraud_result
    print(f"   Fraud Risk Level: {fraud_result['overall_fraud_risk']}")
    print(f"   Fraud Indicators: {len(fraud_result['fraud_indicators'])}")
    
    # Final Assessment
    print("\n" + "=" * 70)
    print("📊 FINAL ASSESSMENT")
    
    # Calculate overall validity score
    validity_checks = [
        results["file_validation"]["netbox_hedgehog/jobs/fabric_sync.py"]["exists"],
        results["file_validation"]["netbox_hedgehog/tasks/sync_tasks.py"]["exists"], 
        results["django_validation"]["status"] == "SUCCESS",
        results["rq_validation"]["jobs_module"]["importable"] if results["rq_validation"]["jobs_module"] else False,
        results["model_validation"]["status"] == "SUCCESS"
    ]
    
    validity_score = sum(validity_checks) / len(validity_checks) * 100
    results["overall_validity_score"] = validity_score
    
    if validity_score >= 80 and fraud_result['overall_fraud_risk'] == "LOW":
        results["final_determination"] = "ISSUE_LIKELY_RESOLVED"
        print("✅ VERDICT: Issue #40 appears to be genuinely resolved")
    elif validity_score >= 60:
        results["final_determination"] = "PARTIAL_IMPLEMENTATION" 
        print("⚠️ VERDICT: Partial implementation detected - requires further investigation")
    else:
        results["final_determination"] = "FRAUDULENT_CLAIMS"
        print("❌ VERDICT: Evidence suggests fraudulent completion claims")
    
    print(f"   Overall Validity Score: {validity_score:.1f}%")
    print(f"   Fraud Risk: {fraud_result['overall_fraud_risk']}")
    
    # Save results
    output_file = f"INDEPENDENT_VALIDATION_RESULTS_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Full results saved to: {output_file}")
    return results

if __name__ == "__main__":
    try:
        validation_results = run_independent_validation()
        sys.exit(0 if validation_results["final_determination"] == "ISSUE_LIKELY_RESOLVED" else 1)
    except Exception as e:
        print(f"❌ VALIDATION SCRIPT FAILED: {e}")
        sys.exit(2)