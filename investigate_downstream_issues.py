#!/usr/bin/env python3
"""
Downstream Issues Investigation

Investigates the two specific issues identified by researchers:
1. State Service field error: `Invalid field name(s) for model HedgehogResource: 'state'`
2. GitHub API path error: `path cannot start with a slash`
"""

import json
import subprocess
import os
from datetime import datetime

def investigate_state_field_error():
    """Investigate state field error in HedgehogResource model"""
    print("\n" + "="*60)
    print("INVESTIGATING: State Service Field Error")
    print("="*60)
    
    # Check if HedgehogResource model has 'state' field
    try:
        # Look for the model definition
        model_file = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/models/gitops.py"
        if os.path.exists(model_file):
            print(f"✅ Found GitOps model file: {model_file}")
            
            with open(model_file, 'r') as f:
                content = f.read()
                
            # Look for HedgehogResource class and state field
            if 'class HedgehogResource' in content:
                print("✅ Found HedgehogResource class definition")
                
                # Check for state field
                if "state = models." in content:
                    print("✅ Found 'state' field in HedgehogResource model")
                    
                    # Extract state field definition
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'state = models.' in line:
                            state_line = line.strip()
                            print(f"   State field definition: {state_line}")
                            
                            # Show context (few lines around)
                            context_start = max(0, i-2)
                            context_end = min(len(lines), i+3)
                            print("   Context:")
                            for j in range(context_start, context_end):
                                marker = " >>> " if j == i else "     "
                                print(f"{marker}{lines[j]}")
                            break
                else:
                    print("❌ NO 'state' field found in HedgehogResource model")
                    print("   This confirms the state field error!")
                    
                    # Look for any state-related fields
                    state_related = []
                    for line in content.split('\n'):
                        if 'state' in line.lower() and '=' in line:
                            state_related.append(line.strip())
                    
                    if state_related:
                        print("   Found state-related fields:")
                        for field in state_related:
                            print(f"     {field}")
                    else:
                        print("   No state-related fields found")
                        
            else:
                print("❌ HedgehogResource class not found in file")
        else:
            print(f"❌ GitOps model file not found: {model_file}")
    except Exception as e:
        print(f"❌ Error investigating state field: {e}")

def investigate_github_path_error():
    """Investigate GitHub API path error"""
    print("\n" + "="*60)
    print("INVESTIGATING: GitHub API Path Error")
    print("="*60)
    
    try:
        # Check GitHubSyncService path generation
        service_file = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/services/github_sync_service.py"
        if os.path.exists(service_file):
            print(f"✅ Found GitHub sync service file: {service_file}")
            
            with open(service_file, 'r') as f:
                content = f.read()
            
            # Look for path generation methods
            path_methods = [
                '_get_managed_file_path',
                '_get_gitops_base_path',
                '_get_relative_path'
            ]
            
            for method in path_methods:
                if f"def {method}" in content:
                    print(f"✅ Found method: {method}")
                    
                    # Extract method implementation
                    lines = content.split('\n')
                    in_method = False
                    method_lines = []
                    indent_level = None
                    
                    for line in lines:
                        if f"def {method}" in line:
                            in_method = True
                            method_lines.append(line)
                            indent_level = len(line) - len(line.lstrip())
                        elif in_method:
                            current_indent = len(line) - len(line.lstrip()) if line.strip() else indent_level + 4
                            
                            if line.strip() and current_indent <= indent_level:
                                # End of method
                                break
                            else:
                                method_lines.append(line)
                    
                    if method_lines:
                        print(f"   Method implementation:")
                        for line in method_lines[:15]:  # Show first 15 lines
                            print(f"     {line}")
                        if len(method_lines) > 15:
                            print(f"     ... (showing first 15 of {len(method_lines)} lines)")
                        
                        # Check for leading slash issues
                        method_code = '\n'.join(method_lines)
                        if 'return f"/' in method_code or 'return "/' in method_code:
                            print(f"   ⚠️  WARNING: {method} may return paths with leading slash")
                        else:
                            print(f"   ✅ {method} appears to handle paths correctly")
                    
                    print()
                else:
                    print(f"❌ Method {method} not found")
        else:
            print(f"❌ GitHub sync service file not found: {service_file}")
    except Exception as e:
        print(f"❌ Error investigating GitHub path: {e}")

def check_recent_errors():
    """Check for recent errors in logs"""
    print("\n" + "="*60)
    print("CHECKING: Recent Error Logs")
    print("="*60)
    
    # Search for the specific errors in various log locations
    error_patterns = [
        "Invalid field name.*state.*HedgehogResource",
        "path cannot start with a slash",
        "SIGNAL FIRED",
        "GitOps sync",
        "GitHub sync",
    ]
    
    log_locations = [
        '/tmp',
        '/var/log',
        '/opt/netbox/logs',
        '/home/ubuntu/cc/hedgehog-netbox-plugin'
    ]
    
    for location in log_locations:
        if os.path.exists(location):
            print(f"\n📁 Searching in: {location}")
            try:
                for pattern in error_patterns:
                    try:
                        result = subprocess.run(
                            ['grep', '-r', '-l', pattern, location],
                            capture_output=True, text=True, timeout=10
                        )
                        
                        if result.returncode == 0 and result.stdout.strip():
                            files = result.stdout.strip().split('\n')
                            print(f"   📄 Pattern '{pattern}' found in:")
                            for file in files[:5]:  # Show first 5 matches
                                print(f"      {file}")
                            if len(files) > 5:
                                print(f"      ... and {len(files)-5} more files")
                    except subprocess.TimeoutExpired:
                        continue
                    except Exception:
                        continue
            except Exception as e:
                print(f"   ❌ Error searching {location}: {e}")

def analyze_current_workflow_state():
    """Analyze the current state of the workflow based on evidence"""
    print("\n" + "="*60)
    print("ANALYZING: Current Workflow State")
    print("="*60)
    
    evidence = {
        'signals_configured': True,  # We've seen signal code
        'github_service_exists': True,  # We've seen the service
        'partial_sync_evidence': True,  # Post-sync test showed 1 CR in managed/
        'state_tracking_issue': None,  # To be determined
        'github_path_issue': None,  # To be determined
    }
    
    # Check state tracking
    try:
        # Look for state service usage
        result = subprocess.run(['find', '/home/ubuntu/cc/hedgehog-netbox-plugin', '-name', '*.py', '-exec', 'grep', '-l', 'state_service', '{}', ';'], 
                               capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            evidence['state_service_usage'] = len(result.stdout.strip().split('\n'))
            print(f"✅ Found state_service usage in {evidence['state_service_usage']} files")
        else:
            evidence['state_service_usage'] = 0
            print("❌ No state_service usage found")
    except:
        evidence['state_service_usage'] = 0
    
    # Summarize findings
    print(f"\n📊 WORKFLOW STATE ANALYSIS:")
    print(f"   Signals configured: {'✅' if evidence['signals_configured'] else '❌'}")
    print(f"   GitHub service exists: {'✅' if evidence['github_service_exists'] else '❌'}")
    print(f"   Partial sync evidence: {'✅' if evidence['partial_sync_evidence'] else '❌'}")
    print(f"   State service usage: {evidence['state_service_usage']} files")
    
    return evidence

def main():
    """Main investigation function"""
    print("="*80)
    print("DOWNSTREAM ISSUES INVESTIGATION")
    print("Investigating specific issues identified by Layer2 researchers")
    print("="*80)
    
    # Investigate each issue
    investigate_state_field_error()
    investigate_github_path_error()
    check_recent_errors()
    evidence = analyze_current_workflow_state()
    
    # Generate summary report
    print("\n" + "="*80)
    print("INVESTIGATION SUMMARY")
    print("="*80)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Investigation completed at: {timestamp}")
    
    # Save evidence to file
    report_file = f"/tmp/downstream_investigation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'evidence': evidence,
            'investigation_type': 'downstream_issues',
            'target_issues': [
                'State Service field error: Invalid field name(s) for model HedgehogResource: state',
                'GitHub API path error: path cannot start with a slash'
            ]
        }, f, indent=2)
    
    print(f"\nDetailed evidence saved to: {report_file}")
    
    return evidence

if __name__ == '__main__':
    main()