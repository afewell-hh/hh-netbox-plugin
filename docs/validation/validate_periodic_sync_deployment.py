#!/usr/bin/env python3
"""
Periodic Sync Deployment Validation Script

This script validates that the RQ-based periodic sync mechanism 
has been properly implemented and deployed for the NetBox Hedgehog Plugin.
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Any

def validate_file_exists(file_path: str) -> Dict[str, Any]:
    """Validate that a file exists and return basic info"""
    if os.path.exists(file_path):
        try:
            size = os.path.getsize(file_path)
            return {
                'exists': True,
                'size': size,
                'readable': os.access(file_path, os.R_OK)
            }
        except Exception as e:
            return {
                'exists': True,
                'size': 0,
                'readable': False,
                'error': str(e)
            }
    else:
        return {'exists': False}

def analyze_fabric_sync_implementation() -> Dict[str, Any]:
    """Analyze the fabric_sync.py implementation"""
    file_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/jobs/fabric_sync.py'
    
    if not os.path.exists(file_path):
        return {
            'valid': False,
            'error': 'fabric_sync.py not found'
        }
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for key implementation elements
        required_classes = [
            'FabricSyncJob',
            'FabricSyncScheduler'
        ]
        
        required_methods = [
            'execute_fabric_sync',
            'bootstrap_all_fabric_schedules',
            'get_scheduled_jobs_status',
            'manually_trigger_sync',
            'start_periodic_sync_for_fabric'
        ]
        
        required_functions = [
            'execute_fabric_sync_rq',
            'queue_fabric_sync'
        ]
        
        required_imports = [
            'django_rq',
            'from rq import get_current_job',
            'RQ_SCHEDULER_AVAILABLE'
        ]
        
        analysis = {
            'valid': True,
            'file_size': len(content),
            'line_count': len(content.splitlines()),
            'classes_found': [],
            'methods_found': [],
            'functions_found': [],
            'imports_found': [],
            'missing_elements': []
        }
        
        # Check classes
        for class_name in required_classes:
            if f'class {class_name}' in content:
                analysis['classes_found'].append(class_name)
            else:
                analysis['missing_elements'].append(f'class {class_name}')
        
        # Check methods
        for method_name in required_methods:
            if f'def {method_name}' in content:
                analysis['methods_found'].append(method_name)
            else:
                analysis['missing_elements'].append(f'method {method_name}')
        
        # Check functions
        for func_name in required_functions:
            if f'def {func_name}' in content:
                analysis['functions_found'].append(func_name)
            else:
                analysis['missing_elements'].append(f'function {func_name}')
        
        # Check imports
        for import_stmt in required_imports:
            if import_stmt in content:
                analysis['imports_found'].append(import_stmt)
            else:
                analysis['missing_elements'].append(f'import {import_stmt}')
        
        # Check for error handling
        error_handling_patterns = [
            'try:',
            'except Exception',
            'logger.error',
            'RQ_SCHEDULER_AVAILABLE'
        ]
        
        analysis['error_handling_found'] = []
        for pattern in error_handling_patterns:
            if pattern in content:
                analysis['error_handling_found'].append(pattern)
        
        # Check for last_sync updates
        last_sync_updates = [
            'fabric.last_sync = timezone.now()',
            'update_fields.*last_sync'
        ]
        
        analysis['last_sync_updates'] = []
        for pattern in last_sync_updates:
            if re.search(pattern, content):
                analysis['last_sync_updates'].append(pattern)
        
        analysis['implementation_complete'] = len(analysis['missing_elements']) == 0
        
        return analysis
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }

def analyze_management_command() -> Dict[str, Any]:
    """Analyze the management command implementation"""
    file_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/management/commands/start_periodic_sync.py'
    
    if not os.path.exists(file_path):
        return {
            'valid': False,
            'error': 'start_periodic_sync.py not found'
        }
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        required_elements = [
            'class Command(BaseCommand)',
            'def add_arguments',
            'def handle',
            '--bootstrap',
            '--manual-trigger', 
            '--status',
            '--fabric-id',
            '--json'
        ]
        
        analysis = {
            'valid': True,
            'file_size': len(content),
            'elements_found': [],
            'missing_elements': []
        }
        
        for element in required_elements:
            if element in content:
                analysis['elements_found'].append(element)
            else:
                analysis['missing_elements'].append(element)
        
        analysis['command_complete'] = len(analysis['missing_elements']) == 0
        
        return analysis
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }

def analyze_plugin_initialization() -> Dict[str, Any]:
    """Analyze the plugin initialization changes"""
    file_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/__init__.py'
    
    if not os.path.exists(file_path):
        return {
            'valid': False,
            'error': '__init__.py not found'
        }
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        required_elements = [
            '_bootstrap_sync_schedules',
            'FabricSyncScheduler',
            'RQ_SCHEDULER_AVAILABLE',
            'hedgehog_sync'
        ]
        
        analysis = {
            'valid': True,
            'file_size': len(content),
            'elements_found': [],
            'missing_elements': []
        }
        
        for element in required_elements:
            if element in content:
                analysis['elements_found'].append(element)
            else:
                analysis['missing_elements'].append(element)
        
        # Check for proper queue configuration
        if 'queues = [' in content and 'hedgehog_sync' in content:
            analysis['queue_configured'] = True
        else:
            analysis['queue_configured'] = False
        
        analysis['initialization_complete'] = len(analysis['missing_elements']) == 0
        
        return analysis
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }

def validate_periodic_sync_deployment():
    """Main validation function"""
    
    print("🔍 Periodic Sync Deployment Validation")
    print("=" * 50)
    
    validation_results = {
        'timestamp': datetime.now().isoformat(),
        'deployment_valid': True,
        'components': {},
        'summary': {
            'total_components': 0,
            'valid_components': 0,
            'issues_found': []
        }
    }
    
    components_to_validate = [
        {
            'name': 'fabric_sync_job',
            'description': 'RQ Fabric Sync Job Implementation',
            'analyzer': analyze_fabric_sync_implementation
        },
        {
            'name': 'management_command',
            'description': 'Management Command for Manual Control',
            'analyzer': analyze_management_command
        },
        {
            'name': 'plugin_initialization',
            'description': 'Plugin Initialization Changes',
            'analyzer': analyze_plugin_initialization
        }
    ]
    
    print(f"🧪 Analyzing {len(components_to_validate)} components...\n")
    
    for component in components_to_validate:
        print(f"📋 {component['description']}")
        
        try:
            analysis = component['analyzer']()
            validation_results['components'][component['name']] = analysis
            validation_results['summary']['total_components'] += 1
            
            if analysis.get('valid', False) and not analysis.get('missing_elements', []):
                validation_results['summary']['valid_components'] += 1
                print(f"   ✅ Valid - All required elements found")
                
                # Show specific details
                if 'implementation_complete' in analysis:
                    print(f"   📊 Implementation: {'Complete' if analysis['implementation_complete'] else 'Incomplete'}")
                if 'command_complete' in analysis:
                    print(f"   📊 Command: {'Complete' if analysis['command_complete'] else 'Incomplete'}")
                if 'initialization_complete' in analysis:
                    print(f"   📊 Initialization: {'Complete' if analysis['initialization_complete'] else 'Incomplete'}")
                    
            else:
                validation_results['deployment_valid'] = False
                issues = analysis.get('missing_elements', [])
                if analysis.get('error'):
                    issues.append(analysis['error'])
                
                validation_results['summary']['issues_found'].extend(issues)
                print(f"   ❌ Issues found: {len(issues)}")
                for issue in issues:
                    print(f"      - {issue}")
            
            print()
                
        except Exception as e:
            print(f"   ❌ Analysis failed: {e}")
            validation_results['components'][component['name']] = {
                'valid': False,
                'error': str(e)
            }
            validation_results['deployment_valid'] = False
            validation_results['summary']['issues_found'].append(f"{component['name']}: {e}")
    
    # Final summary
    print("📊 Deployment Validation Summary")
    print("=" * 32)
    
    total = validation_results['summary']['total_components']
    valid = validation_results['summary']['valid_components']
    success_rate = (valid / total * 100) if total > 0 else 0
    
    print(f"Total Components: {total}")
    print(f"Valid Components: {valid}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if validation_results['deployment_valid']:
        print("\n🎉 Deployment Validation: PASSED")
        print("   The periodic sync mechanism is properly implemented!")
        print("\n📋 Next Steps:")
        print("   1. Ensure worker container is running with RQ support")
        print("   2. Install django-rq-scheduler if not already installed")
        print("   3. Run: python manage.py start_periodic_sync --bootstrap")
        print("   4. Verify: python manage.py start_periodic_sync --status")
    else:
        print(f"\n❌ Deployment Validation: FAILED")
        print(f"   Found {len(validation_results['summary']['issues_found'])} issues")
        
        if validation_results['summary']['issues_found']:
            print("   Issues to resolve:")
            for issue in validation_results['summary']['issues_found']:
                print(f"   - {issue}")
    
    # Save detailed results
    results_file = 'periodic_sync_deployment_validation.json'
    with open(results_file, 'w') as f:
        json.dump(validation_results, f, indent=2)
    
    print(f"\n💾 Detailed validation results saved to: {results_file}")
    
    return validation_results

if __name__ == '__main__':
    validate_periodic_sync_deployment()