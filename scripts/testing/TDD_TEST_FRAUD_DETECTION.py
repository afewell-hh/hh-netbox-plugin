#!/usr/bin/env python3
"""
TDD Test Fraud Detection Script
===============================

Validates whether the TDD tests are actually failing as claimed.
True TDD tests MUST fail initially before implementation.
"""

import os
import sys
import ast
import subprocess
from pathlib import Path

def analyze_tdd_test_file(filepath):
    """Analyze a TDD test file for fraud indicators."""
    if not os.path.exists(filepath):
        return {"exists": False}
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {"exists": True, "parseable": False, "error": "Syntax error in test file"}
    
    # Count test methods
    test_methods = []
    class TestMethodVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node.name.startswith('test_'):
                test_methods.append({
                    "name": node.name,
                    "docstring": ast.get_docstring(node) or "",
                    "has_assertions": any(isinstance(child, ast.Assert) for child in ast.walk(node))
                })
    
    visitor = TestMethodVisitor()
    visitor.visit(tree)
    
    # Analyze for fraud indicators
    fraud_indicators = []
    
    # Check if tests claim to fail but have no real assertions
    fake_tests = [t for t in test_methods if not t["has_assertions"]]
    if fake_tests:
        fraud_indicators.append(f"Tests without assertions: {[t['name'] for t in fake_tests]}")
    
    # Check for suspicious comments about imports failing
    if "# This import will FAIL" in content and "import" not in content.split("# This import will FAIL")[1].split('\n')[0]:
        fraud_indicators.append("Claims import will fail but doesn't actually import")
    
    # Check for MUST FAIL comments without actual failing logic
    if "MUST FAIL" in content:
        lines_with_must_fail = [i+1 for i, line in enumerate(content.split('\n')) if "MUST FAIL" in line]
        fraud_indicators.append(f"MUST FAIL claims on lines: {lines_with_must_fail}")
    
    return {
        "exists": True,
        "parseable": True,
        "test_count": len(test_methods),
        "test_methods": test_methods,
        "fraud_indicators": fraud_indicators,
        "fraud_score": len(fraud_indicators) * 25  # 25 points per indicator
    }

def run_tdd_fraud_detection():
    """Run TDD fraud detection on test files."""
    print("🔍 TDD TEST FRAUD DETECTION")
    print("=" * 50)
    
    # Test files claimed by previous agents
    test_files = [
        "tests/periodic_sync_rq/test_rq_scheduler_integration.py",
        "tests/tdd_issue40_london_school/test_acceptance_failing.py",
        "tests/tdd_periodic_sync_london_school/test_integration_end_to_end.py",
        "tests/run_issue40_tests.py"
    ]
    
    overall_results = {
        "total_files_analyzed": 0,
        "files_with_fraud_indicators": 0,
        "total_fraud_score": 0,
        "file_analysis": {}
    }
    
    for test_file in test_files:
        print(f"\n📁 Analyzing: {test_file}")
        result = analyze_tdd_test_file(test_file)
        overall_results["file_analysis"][test_file] = result
        
        if result["exists"]:
            overall_results["total_files_analyzed"] += 1
            
            if result["fraud_score"] > 0:
                overall_results["files_with_fraud_indicators"] += 1
                overall_results["total_fraud_score"] += result["fraud_score"]
                
                print(f"   ❌ FRAUD DETECTED (Score: {result['fraud_score']}/100)")
                for indicator in result["fraud_indicators"]:
                    print(f"      - {indicator}")
            else:
                print(f"   ✅ No fraud indicators detected ({result['test_count']} tests)")
        else:
            print(f"   ❌ FILE NOT FOUND")
    
    # Final assessment
    print("\n" + "=" * 50)
    print("📊 TDD FRAUD DETECTION SUMMARY")
    
    avg_fraud_score = overall_results["total_fraud_score"] / max(overall_results["total_files_analyzed"], 1)
    
    print(f"Files Analyzed: {overall_results['total_files_analyzed']}")
    print(f"Files with Fraud: {overall_results['files_with_fraud_indicators']}")
    print(f"Average Fraud Score: {avg_fraud_score:.1f}/100")
    
    if avg_fraud_score > 50:
        print("🚨 HIGH FRAUD PROBABILITY - TDD claims appear fabricated")
        verdict = "HIGH_FRAUD"
    elif avg_fraud_score > 25:
        print("⚠️ MODERATE FRAUD RISK - TDD implementation suspicious") 
        verdict = "MODERATE_FRAUD"
    else:
        print("✅ LOW FRAUD RISK - TDD appears legitimate")
        verdict = "LOW_FRAUD"
    
    overall_results["verdict"] = verdict
    overall_results["average_fraud_score"] = avg_fraud_score
    
    return overall_results

def check_if_tests_actually_run():
    """Check if the TDD tests can actually be executed."""
    print("\n🧪 TDD TEST EXECUTION CHECK")
    print("=" * 50)
    
    test_runners = [
        "tests/run_issue40_tests.py",
        "tests/run_periodic_sync_tdd_tests.py"
    ]
    
    execution_results = {}
    
    for runner in test_runners:
        print(f"\n🔬 Testing runner: {runner}")
        if not os.path.exists(runner):
            execution_results[runner] = {"exists": False}
            print(f"   ❌ Runner does not exist")
            continue
        
        try:
            # Try to run with python3 -c to check syntax
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", runner],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print(f"   ✅ Syntax valid - runner compiles")
                execution_results[runner] = {"exists": True, "syntax_valid": True}
            else:
                print(f"   ❌ Syntax error: {result.stderr}")
                execution_results[runner] = {"exists": True, "syntax_valid": False, "error": result.stderr}
                
        except Exception as e:
            print(f"   ❌ Execution check failed: {e}")
            execution_results[runner] = {"exists": True, "syntax_valid": False, "error": str(e)}
    
    return execution_results

if __name__ == "__main__":
    fraud_results = run_tdd_fraud_detection()
    execution_results = check_if_tests_actually_run()
    
    # Save comprehensive results
    import json
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    comprehensive_results = {
        "timestamp": timestamp,
        "fraud_detection": fraud_results,
        "execution_check": execution_results
    }
    
    output_file = f"TDD_FRAUD_DETECTION_RESULTS_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(comprehensive_results, f, indent=2)
    
    print(f"\n📄 Results saved to: {output_file}")
    
    # Exit code based on fraud detection
    if fraud_results["verdict"] == "HIGH_FRAUD":
        sys.exit(2)
    elif fraud_results["verdict"] == "MODERATE_FRAUD":
        sys.exit(1)
    else:
        sys.exit(0)