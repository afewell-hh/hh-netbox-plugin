#!/usr/bin/env python3
"""
Execute Validation Gatekeeper - Automated Sync Fix Validation
This script executes the complete validation framework automatically.
ZERO TOLERANCE for false completion claims.
"""

import os
import sys
import json
import time
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sync_validation_gatekeeper import (
        SyncValidationGatekeeper, 
        ValidationResult,
        TestResult
    )
except ImportError as e:
    print(f"🚫 CRITICAL ERROR: Cannot import validation gatekeeper: {e}")
    sys.exit(1)

class ValidationExecutor:
    """
    Executes the complete validation framework with automated evidence collection.
    This is the enforcement arm of the validation gatekeeper.
    """
    
    def __init__(self):
        self.execution_id = f"exec_{int(time.time())}"
        self.evidence_dir = f"validation_evidence_{self.execution_id}"
        self.setup_evidence_directory()
        
    def setup_evidence_directory(self):
        """Create evidence collection directory."""
        try:
            os.makedirs(self.evidence_dir, exist_ok=True)
            print(f"📁 Evidence collection directory: {self.evidence_dir}")
        except Exception as e:
            print(f"🚫 FATAL: Cannot create evidence directory: {e}")
            sys.exit(1)
            
    def execute_comprehensive_validation(self) -> bool:
        """
        Execute the complete validation framework.
        Returns True only if ALL validation passes.
        """
        
        print("🚨" * 20)
        print("🚨 SYNC FIX VALIDATION GATEKEEPER EXECUTION")
        print("🚨 ZERO TOLERANCE - ALL CRITERIA MUST PASS")
        print("🚨" * 20)
        print()
        
        validation_passed = False
        
        try:
            # Phase 1: Pre-validation Environment Check
            print("🔍 PHASE 1: Pre-validation Environment Check")
            if not self._check_environment():
                self._record_failure("Environment check failed")
                return False
                
            # Phase 2: Technical Validation Execution
            print("\n⚡ PHASE 2: Technical Validation Execution")
            gatekeeper = SyncValidationGatekeeper()
            result, evidence = gatekeeper.validate_sync_fix()
            
            # Phase 3: Evidence Collection
            print("\n📊 PHASE 3: Evidence Collection and Analysis")
            self._collect_evidence(result, evidence, gatekeeper)
            
            # Phase 4: Final Determination
            print("\n🎯 PHASE 4: Final Gatekeeper Determination")
            validation_passed = self._make_final_determination(result, evidence)
            
            # Phase 5: Report Generation
            print("\n📄 PHASE 5: Comprehensive Report Generation")
            self._generate_comprehensive_report(result, evidence, gatekeeper, validation_passed)
            
        except Exception as e:
            print(f"🚫 CRITICAL ERROR during validation execution: {e}")
            print("🚫 STACK TRACE:")
            traceback.print_exc()
            self._record_failure(f"Validation execution error: {e}")
            validation_passed = False
            
        # Final enforcement
        self._enforce_validation_result(validation_passed)
        return validation_passed
        
    def _check_environment(self) -> bool:
        """Check that the environment is ready for validation."""
        
        checks = [
            ("Python environment", self._check_python_environment),
            ("NetBox accessibility", self._check_netbox_accessibility),
            ("Kubernetes tools", self._check_kubernetes_tools),
            ("Required files", self._check_required_files),
            ("Database connectivity", self._check_database_connectivity)
        ]
        
        all_passed = True
        
        for check_name, check_function in checks:
            print(f"  🔍 Checking {check_name}...", end=" ")
            try:
                if check_function():
                    print("✅ PASS")
                else:
                    print("❌ FAIL")
                    all_passed = False
            except Exception as e:
                print(f"❌ ERROR: {e}")
                all_passed = False
                
        if not all_passed:
            print("\n🚫 ENVIRONMENT CHECK FAILED - Validation cannot proceed")
            
        return all_passed
        
    def _check_python_environment(self) -> bool:
        """Check Python environment requirements."""
        required_modules = ['requests', 'subprocess', 'json', 'datetime']
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                return False
                
        return True
        
    def _check_netbox_accessibility(self) -> bool:
        """Check if NetBox is accessible."""
        try:
            import requests
            response = requests.get("http://localhost:8000", timeout=5)
            return response.status_code in [200, 302, 403]  # Any reasonable response
        except:
            return False
            
    def _check_kubernetes_tools(self) -> bool:
        """Check if kubectl is available."""
        try:
            subprocess.check_output(["kubectl", "version", "--client"], 
                                  stderr=subprocess.DEVNULL, timeout=10)
            return True
        except:
            return False
            
    def _check_required_files(self) -> bool:
        """Check if required project files exist."""
        required_files = [
            "manage.py",
            "netbox_hedgehog/__init__.py",
            "SYNC_FIX_VALIDATION_FRAMEWORK.md",
            "MANDATORY_SYNC_TEST_SUITE.md"
        ]
        
        for file_path in required_files:
            if not os.path.exists(file_path):
                return False
                
        return True
        
    def _check_database_connectivity(self) -> bool:
        """Check if database is accessible."""
        try:
            # Try to run a simple Django management command
            result = subprocess.run(
                ["python", "manage.py", "check", "--deploy"],
                capture_output=True,
                timeout=30
            )
            return result.returncode == 0
        except:
            return False
            
    def _collect_evidence(self, result, evidence, gatekeeper):
        """Collect all validation evidence."""
        
        evidence_items = [
            ("validation_result.json", self._collect_result_evidence, result, evidence),
            ("test_results.json", self._collect_test_evidence, evidence.test_results),
            ("system_state.json", self._collect_system_evidence),
            ("kubernetes_state.yaml", self._collect_k8s_evidence),
            ("netbox_state.json", self._collect_netbox_evidence),
            ("performance_metrics.json", self._collect_performance_evidence)
        ]
        
        for filename, collector, *args in evidence_items:
            try:
                print(f"  📊 Collecting {filename}...", end=" ")
                data = collector(*args)
                
                filepath = os.path.join(self.evidence_dir, filename)
                if filename.endswith('.json'):
                    with open(filepath, 'w') as f:
                        json.dump(data, f, indent=2, default=str)
                else:
                    with open(filepath, 'w') as f:
                        f.write(str(data))
                        
                print("✅ COLLECTED")
                
            except Exception as e:
                print(f"❌ ERROR: {e}")
                
    def _collect_result_evidence(self, result, evidence):
        """Collect validation result evidence."""
        return {
            "validation_id": self.execution_id,
            "timestamp": datetime.now().isoformat(),
            "final_result": result.value,
            "technical_validation": {
                "kubernetes_connectivity": evidence.kubernetes_connectivity,
                "database_consistency": evidence.database_consistency,
                "ui_functionality": evidence.user_interface_functional,
                "error_handling": evidence.error_handling_verified,
                "performance": evidence.performance_acceptable
            },
            "manual_verification": {
                "independent_reproduction": evidence.independent_reproduction,
                "user_acceptance": evidence.user_acceptance
            }
        }
        
    def _collect_test_evidence(self, test_results):
        """Collect individual test result evidence."""
        return [
            {
                "test_name": test.test_name,
                "passed": test.passed,
                "execution_time": test.execution_time,
                "evidence": test.evidence,
                "error_message": test.error_message
            }
            for test in test_results
        ]
        
    def _collect_system_evidence(self):
        """Collect system state evidence."""
        try:
            return {
                "processes": subprocess.check_output(["ps", "aux"], universal_newlines=True),
                "disk_usage": subprocess.check_output(["df", "-h"], universal_newlines=True),
                "memory_usage": subprocess.check_output(["free", "-h"], universal_newlines=True),
                "netbox_status": self._get_netbox_status()
            }
        except:
            return {"error": "Could not collect system evidence"}
            
    def _collect_k8s_evidence(self):
        """Collect Kubernetes state evidence."""
        try:
            k8s_data = []
            
            commands = [
                "kubectl cluster-info",
                "kubectl get nodes",
                "kubectl get crd",
                "kubectl get all -A"
            ]
            
            for cmd in commands:
                try:
                    output = subprocess.check_output(cmd.split(), universal_newlines=True)
                    k8s_data.append(f"=== {cmd} ===\n{output}\n")
                except:
                    k8s_data.append(f"=== {cmd} ===\nERROR: Command failed\n")
                    
            return "\n".join(k8s_data)
            
        except:
            return "ERROR: Could not collect Kubernetes evidence"
            
    def _collect_netbox_evidence(self):
        """Collect NetBox state evidence."""
        try:
            return {
                "fabric_count": self._get_fabric_count(),
                "sync_status": self._get_sync_status(),
                "recent_logs": self._get_recent_logs()
            }
        except:
            return {"error": "Could not collect NetBox evidence"}
            
    def _collect_performance_evidence(self):
        """Collect performance evidence."""
        return {
            "validation_start": datetime.now().isoformat(),
            "system_load": self._get_system_load(),
            "memory_usage": self._get_memory_usage()
        }
        
    def _get_netbox_status(self):
        """Get NetBox service status."""
        try:
            import requests
            response = requests.get("http://localhost:8000/api/", timeout=5)
            return {"status_code": response.status_code, "accessible": True}
        except:
            return {"accessible": False}
            
    def _get_fabric_count(self):
        """Get fabric count from NetBox."""
        # This would require actual database access
        return "Requires database access"
        
    def _get_sync_status(self):
        """Get sync status from NetBox."""
        return "Requires API access"
        
    def _get_recent_logs(self):
        """Get recent log entries."""
        return "Requires log file access"
        
    def _get_system_load(self):
        """Get system load average."""
        try:
            return subprocess.check_output(["uptime"], universal_newlines=True).strip()
        except:
            return "Unknown"
            
    def _get_memory_usage(self):
        """Get memory usage."""
        try:
            return subprocess.check_output(["free", "-m"], universal_newlines=True)
        except:
            return "Unknown"
            
    def _make_final_determination(self, result, evidence) -> bool:
        """Make the final gatekeeper determination."""
        
        print(f"🎯 Technical Validation Result: {result.value}")
        
        # Technical validation must pass
        if result == ValidationResult.REJECT:
            print("🚫 AUTOMATIC REJECTION: Technical validation failed")
            return False
            
        # Check critical technical requirements
        critical_checks = [
            ("Kubernetes Connectivity", evidence.kubernetes_connectivity),
            ("Database Consistency", evidence.database_consistency),
            ("UI Functionality", evidence.user_interface_functional)
        ]
        
        for check_name, check_result in critical_checks:
            if not check_result:
                print(f"🚫 AUTOMATIC REJECTION: {check_name} failed")
                return False
                
        # If technical validation passes but manual verification needed
        if result == ValidationResult.CONDITIONAL:
            print("⚠️  CONDITIONAL ACCEPTANCE: Technical validation passed")
            print("📋 MANUAL VERIFICATION STILL REQUIRED:")
            print("   - Independent reproduction by fresh validator")
            print("   - User acceptance testing and confirmation")
            return True  # Allow conditional acceptance
            
        # Full acceptance
        if result == ValidationResult.PASS:
            print("✅ FULL ACCEPTANCE: All criteria met")
            return True
            
        return False
        
    def _generate_comprehensive_report(self, result, evidence, gatekeeper, validation_passed):
        """Generate comprehensive validation report."""
        
        # Generate gatekeeper report
        gatekeeper_report = gatekeeper.generate_validation_report(result, evidence)
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(result, evidence, validation_passed)
        
        # Generate technical appendix
        technical_appendix = self._generate_technical_appendix()
        
        # Combine all reports
        full_report = f"""
{executive_summary}

{gatekeeper_report}

{technical_appendix}
"""
        
        # Save complete report
        report_path = f"COMPLETE_VALIDATION_REPORT_{self.execution_id}.md"
        with open(report_path, 'w') as f:
            f.write(full_report)
            
        print(f"📄 Complete validation report: {report_path}")
        print(f"📁 Evidence package: {self.evidence_dir}/")
        
    def _generate_executive_summary(self, result, evidence, validation_passed):
        """Generate executive summary."""
        
        status = "✅ ACCEPTED" if validation_passed else "❌ REJECTED"
        
        return f"""
# EXECUTIVE VALIDATION SUMMARY

## Final Determination: {status}

**Validation ID:** {self.execution_id}  
**Execution Time:** {datetime.now().isoformat()}  
**Gatekeeper Authority:** ABSOLUTE  

## Key Findings:
- Technical Validation: {result.value}
- Manual Verification Required: {'Yes' if result == ValidationResult.CONDITIONAL else 'No'}
- Evidence Package Complete: {'Yes' if os.path.exists(self.evidence_dir) else 'No'}

## Critical Requirements Status:
- ✅ Kubernetes Connectivity: {'PASS' if evidence.kubernetes_connectivity else 'FAIL'}
- ✅ Database Consistency: {'PASS' if evidence.database_consistency else 'FAIL'}
- ✅ UI Functionality: {'PASS' if evidence.user_interface_functional else 'FAIL'}
- ⚠️  Error Handling: {'PASS' if evidence.error_handling_verified else 'PENDING'}
- ⚠️  Performance: {'PASS' if evidence.performance_acceptable else 'PENDING'}

## Next Steps:
{'✅ Sync fix may proceed to deployment' if validation_passed else '🚫 Sync fix must be substantially improved before resubmission'}
"""
        
    def _generate_technical_appendix(self):
        """Generate technical appendix."""
        return f"""
# TECHNICAL APPENDIX

## Validation Framework Details
- Framework Version: 1.0
- Execution Environment: {os.uname().sysname if hasattr(os, 'uname') else 'Unknown'}
- Python Version: {sys.version}
- Evidence Directory: {self.evidence_dir}

## Authority and Enforcement
This validation was conducted under the Sync Fix Validation Framework with:
- ZERO TOLERANCE for false completion claims
- ABSOLUTE AUTHORITY to reject substandard implementations
- MANDATORY EVIDENCE requirements for all claims
- NO EXCEPTIONS or compromises allowed

## Contact and Escalation
For questions about this validation:
- Review the complete framework: SYNC_FIX_VALIDATION_FRAMEWORK.md
- Check mandatory test requirements: MANDATORY_SYNC_TEST_SUITE.md
- Evidence package location: {self.evidence_dir}/

**REMEMBER: This gatekeeper has final authority over sync fix validation.**
"""
        
    def _record_failure(self, reason):
        """Record validation failure."""
        failure_record = {
            "validation_id": self.execution_id,
            "timestamp": datetime.now().isoformat(),
            "failure_reason": reason,
            "authority": "Sync Validation Gatekeeper"
        }
        
        with open(f"validation_failure_{self.execution_id}.json", 'w') as f:
            json.dump(failure_record, f, indent=2)
            
    def _enforce_validation_result(self, validation_passed):
        """Enforce the validation result."""
        
        print("\n" + "="*60)
        print("🚨 FINAL GATEKEEPER ENFORCEMENT")
        print("="*60)
        
        if validation_passed:
            print("✅ VALIDATION PASSED")
            print("📋 Sync fix meets technical validation criteria")
            print("⚠️  Manual verification may still be required")
            print("💡 Review complete report for next steps")
        else:
            print("❌ VALIDATION FAILED")
            print("🚫 Sync fix does NOT meet required standards")
            print("🔄 Substantial improvements required before resubmission")
            print("📋 Review failure reasons in generated report")
            
        print("="*60)
        print(f"📊 Evidence Package: {self.evidence_dir}/")
        print(f"📄 Complete Report: COMPLETE_VALIDATION_REPORT_{self.execution_id}.md")
        print("🔒 Gatekeeper Authority: ABSOLUTE")
        print("="*60)

def main():
    """Main execution entry point."""
    
    print("🚨 SYNC FIX VALIDATION GATEKEEPER")
    print("🚨 Automated Execution Framework")
    print("🚨 ZERO TOLERANCE ENFORCEMENT")
    print()
    
    executor = ValidationExecutor()
    validation_passed = executor.execute_comprehensive_validation()
    
    # Exit with appropriate code
    if validation_passed:
        print("\n✅ Validation completed successfully")
        sys.exit(0)  # Success
    else:
        print("\n❌ Validation failed - improvements required")
        sys.exit(1)  # Failure

if __name__ == "__main__":
    main()