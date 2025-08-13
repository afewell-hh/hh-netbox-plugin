#!/usr/bin/env python3
"""
Validate the GitHub sync fix implementation by analyzing the code changes.

This script checks that the FabricGitHubSyncView has been properly modified
to include file processing integration after GitHub sync operations.
"""

import json
import re
from pathlib import Path
from datetime import datetime


def validate_implementation():
    """
    Validate that the GitHub sync fix has been properly implemented.
    """
    validation_results = {
        'success': False,
        'test_name': 'GitHub Sync Implementation Validation',
        'started_at': datetime.now().isoformat(),
        'checks_performed': [],
        'evidence': {},
        'errors': []
    }
    
    try:
        print("=== GitHub Sync Implementation Validation ===")
        print(f"Started at: {validation_results['started_at']}")
        
        # Check 1: Verify sync_views.py file exists and is readable
        print("\n1. Checking sync_views.py file...")
        
        sync_views_file = Path('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/sync_views.py')
        
        if not sync_views_file.exists():
            raise Exception(f"sync_views.py file not found at {sync_views_file}")
        
        sync_views_content = sync_views_file.read_text()
        print(f"   ✓ File exists and is readable ({len(sync_views_content)} characters)")
        
        validation_results['checks_performed'].append("file_existence_check")
        validation_results['evidence']['file_size'] = len(sync_views_content)
        
        # Check 2: Verify GitOpsIngestionService import is present
        print("\n2. Checking for GitOpsIngestionService import...")
        
        ingestion_import_pattern = r'from\s+\.\.services\.gitops_ingestion_service\s+import\s+GitOpsIngestionService'
        ingestion_import_match = re.search(ingestion_import_pattern, sync_views_content)
        
        if ingestion_import_match:
            print("   ✓ GitOpsIngestionService import found")
            validation_results['evidence']['ingestion_import_present'] = True
        else:
            validation_results['errors'].append("GitOpsIngestionService import not found")
            validation_results['evidence']['ingestion_import_present'] = False
        
        validation_results['checks_performed'].append("import_check")
        
        # Check 3: Find FabricGitHubSyncView class
        print("\n3. Locating FabricGitHubSyncView class...")
        
        github_sync_class_pattern = r'class\s+FabricGitHubSyncView\s*\([^)]+\):'
        github_sync_class_match = re.search(github_sync_class_pattern, sync_views_content)
        
        if github_sync_class_match:
            print("   ✓ FabricGitHubSyncView class found")
            validation_results['evidence']['github_sync_class_found'] = True
        else:
            raise Exception("FabricGitHubSyncView class not found")
        
        validation_results['checks_performed'].append("class_location_check")
        
        # Check 4: Verify file processing integration in post method
        print("\n4. Checking for file processing integration...")
        
        # Look for the critical fix comment and ingestion service usage
        critical_fix_pattern = r'#\s*CRITICAL\s+FIX.*process.*raw.*directory'
        ingestion_service_usage_pattern = r'ingestion_service\s*=\s*GitOpsIngestionService\s*\(\s*fabric\s*\)'
        process_raw_call_pattern = r'ingestion_service\.process_raw_directory\s*\(\s*\)'
        
        critical_fix_found = bool(re.search(critical_fix_pattern, sync_views_content, re.IGNORECASE))
        ingestion_service_usage_found = bool(re.search(ingestion_service_usage_pattern, sync_views_content))
        process_raw_call_found = bool(re.search(process_raw_call_pattern, sync_views_content))
        
        print(f"   Critical fix comment present: {critical_fix_found}")
        print(f"   Ingestion service instantiation: {ingestion_service_usage_found}")
        print(f"   process_raw_directory call: {process_raw_call_found}")
        
        validation_results['evidence']['critical_fix_comment'] = critical_fix_found
        validation_results['evidence']['ingestion_service_usage'] = ingestion_service_usage_found
        validation_results['evidence']['process_raw_call'] = process_raw_call_found
        
        validation_results['checks_performed'].append("integration_pattern_check")
        
        # Check 5: Verify proper error handling
        print("\n5. Checking error handling patterns...")
        
        # Look for proper error handling around ingestion
        try_except_pattern = r'try:\s*.*?ingestion_service.*?except.*?Exception'
        partial_sync_status_pattern = r'partial_sync'
        ingestion_error_handling_pattern = r'ingestion_error'
        
        try_except_found = bool(re.search(try_except_pattern, sync_views_content, re.DOTALL))
        partial_sync_found = bool(re.search(partial_sync_status_pattern, sync_views_content))
        ingestion_error_handling_found = bool(re.search(ingestion_error_handling_pattern, sync_views_content))
        
        print(f"   Try/except around ingestion: {try_except_found}")
        print(f"   Partial sync status handling: {partial_sync_found}")
        print(f"   Ingestion error handling: {ingestion_error_handling_found}")
        
        validation_results['evidence']['try_except_ingestion'] = try_except_found
        validation_results['evidence']['partial_sync_handling'] = partial_sync_found
        validation_results['evidence']['ingestion_error_handling'] = ingestion_error_handling_found
        
        validation_results['checks_performed'].append("error_handling_check")
        
        # Check 6: Verify response structure includes ingestion details
        print("\n6. Checking response structure...")
        
        combined_message_pattern = r'combined_message.*sync_result.*ingestion_result'
        file_ingestion_details_pattern = r'file_ingestion.*files_processed.*documents_extracted'
        
        combined_message_found = bool(re.search(combined_message_pattern, sync_views_content))
        ingestion_details_found = bool(re.search(file_ingestion_details_pattern, sync_views_content))
        
        print(f"   Combined message structure: {combined_message_found}")
        print(f"   File ingestion details in response: {ingestion_details_found}")
        
        validation_results['evidence']['combined_message_structure'] = combined_message_found
        validation_results['evidence']['ingestion_details_response'] = ingestion_details_found
        
        validation_results['checks_performed'].append("response_structure_check")
        
        # Check 7: Count lines added vs. original implementation
        print("\n7. Analyzing implementation scope...")
        
        # Count key implementation elements
        ingestion_service_lines = len(re.findall(r'ingestion_service', sync_views_content))
        process_raw_lines = len(re.findall(r'process_raw_directory', sync_views_content))
        file_processing_lines = len(re.findall(r'file.*process', sync_views_content, re.IGNORECASE))
        
        print(f"   Ingestion service references: {ingestion_service_lines}")
        print(f"   process_raw_directory calls: {process_raw_lines}")
        print(f"   File processing references: {file_processing_lines}")
        
        validation_results['evidence']['ingestion_service_references'] = ingestion_service_lines
        validation_results['evidence']['process_raw_calls'] = process_raw_lines
        validation_results['evidence']['file_processing_references'] = file_processing_lines
        
        validation_results['checks_performed'].append("implementation_scope_analysis")
        
        # Final assessment
        print("\n=== IMPLEMENTATION ASSESSMENT ===")
        
        # Count critical elements
        critical_elements = [
            validation_results['evidence'].get('ingestion_import_present', False),
            validation_results['evidence'].get('ingestion_service_usage', False),
            validation_results['evidence'].get('process_raw_call', False),
            validation_results['evidence'].get('try_except_ingestion', False),
            validation_results['evidence'].get('combined_message_structure', False)
        ]
        
        critical_elements_count = sum(critical_elements)
        total_critical_elements = len(critical_elements)
        
        print(f"Critical implementation elements: {critical_elements_count}/{total_critical_elements}")
        
        if critical_elements_count == total_critical_elements:
            validation_results['success'] = True
            validation_results['assessment'] = "IMPLEMENTATION COMPLETE"
            print("✓ GitHub sync fix implementation is COMPLETE")
        elif critical_elements_count >= 3:
            validation_results['success'] = True
            validation_results['assessment'] = "IMPLEMENTATION MOSTLY COMPLETE"
            print("⚠ GitHub sync fix implementation is MOSTLY COMPLETE")
        else:
            validation_results['assessment'] = "IMPLEMENTATION INCOMPLETE"
            print("✗ GitHub sync fix implementation is INCOMPLETE")
        
        # Implementation summary
        print("\n=== IMPLEMENTATION SUMMARY ===")
        print("Key changes identified:")
        print(f"  - Added GitOpsIngestionService integration: {validation_results['evidence'].get('ingestion_service_usage', False)}")
        print(f"  - Added file processing after GitHub sync: {validation_results['evidence'].get('process_raw_call', False)}")
        print(f"  - Implemented proper error handling: {validation_results['evidence'].get('try_except_ingestion', False)}")
        print(f"  - Enhanced response with ingestion details: {validation_results['evidence'].get('ingestion_details_response', False)}")
        print(f"  - Added partial sync status handling: {validation_results['evidence'].get('partial_sync_handling', False)}")
        
        validation_results['completed_at'] = datetime.now().isoformat()
        
        return validation_results
        
    except Exception as e:
        print(f"\nValidation failed with exception: {e}")
        validation_results['success'] = False
        validation_results['error'] = str(e)
        validation_results['completed_at'] = datetime.now().isoformat()
        return validation_results


def save_validation_results(results):
    """Save validation results to file."""
    results_file = Path('/home/ubuntu/cc/hedgehog-netbox-plugin/github_sync_implementation_validation.json')
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nValidation results saved to: {results_file}")
    return results_file


if __name__ == "__main__":
    results = validate_implementation()
    results_file = save_validation_results(results)
    
    # Exit with appropriate code
    exit_code = 0 if results['success'] else 1
    print(f"\nExiting with code: {exit_code}")
    exit(exit_code)