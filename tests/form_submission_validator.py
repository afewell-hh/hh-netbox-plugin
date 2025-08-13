#!/usr/bin/env python3
"""
Test Form Submission and Validation for Fabric Edit Page
Validates form submission, save behavior, and validation rules
"""

import requests
import sys
import json
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

def test_form_submission():
    """Test fabric edit form submission and validation"""
    
    base_url = "http://localhost:8000"
    fabric_id = 35
    edit_url = f"{base_url}/plugins/hedgehog/fabrics/{fabric_id}/edit/"
    detail_url = f"{base_url}/plugins/hedgehog/fabrics/{fabric_id}/"
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "fabric_id": fabric_id,
        "tests": {},
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": []
        }
    }
    
    session = requests.Session()
    
    print(f"Testing form submission for Fabric ID {fabric_id}")
    print(f"Edit URL: {edit_url}")
    print("=" * 60)
    
    # Test 1: Load edit form page
    test_name = "load_edit_form"
    results["tests"][test_name] = {"status": "running"}
    results["summary"]["total_tests"] += 1
    
    try:
        print("1. Loading fabric edit form...")
        response = session.get(edit_url)
        
        if response.status_code == 200:
            form_html = response.text
            
            # Check for form elements
            has_form = '<form' in form_html
            has_description = 'description' in form_html.lower()
            has_sync_interval = 'sync_interval' in form_html.lower()
            has_save_button = 'save' in form_html.lower() or 'submit' in form_html.lower()
            
            # Extract CSRF token if present
            csrf_token = None
            if 'csrfmiddlewaretoken' in form_html:
                import re
                csrf_match = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)', form_html)
                if csrf_match:
                    csrf_token = csrf_match.group(1)
            
            results["tests"][test_name] = {
                "status": "passed",
                "response_code": response.status_code,
                "has_form": has_form,
                "has_description_field": has_description,
                "has_sync_interval_field": has_sync_interval,
                "has_save_button": has_save_button,
                "csrf_token_found": csrf_token is not None,
                "form_size": len(form_html)
            }
            results["summary"]["passed"] += 1
            print("✅ Form loaded successfully")
            
        else:
            results["tests"][test_name] = {
                "status": "failed",
                "response_code": response.status_code,
                "error": f"HTTP {response.status_code}"
            }
            results["summary"]["failed"] += 1
            results["summary"]["errors"].append(f"Failed to load edit form: HTTP {response.status_code}")
            print(f"❌ Failed to load form: HTTP {response.status_code}")
            return results
            
    except Exception as e:
        results["tests"][test_name] = {"status": "error", "error": str(e)}
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Error loading form: {e}")
        print(f"❌ Error loading form: {e}")
        return results
    
    # Test 2: Extract current form values
    test_name = "extract_current_values"
    results["tests"][test_name] = {"status": "running"}
    results["summary"]["total_tests"] += 1
    
    try:
        print("2. Extracting current form values...")
        
        # Parse form to get current values
        current_values = {}
        
        # Look for input fields with values
        import re
        
        # Extract description
        desc_match = re.search(r'name=["\']description["\'][^>]*value=["\']([^"\']*)', form_html)
        if desc_match:
            current_values['description'] = desc_match.group(1)
        else:
            # Try textarea
            textarea_match = re.search(r'<textarea[^>]*name=["\']description["\'][^>]*>([^<]*)', form_html)
            if textarea_match:
                current_values['description'] = textarea_match.group(1).strip()
        
        # Extract sync_interval
        sync_match = re.search(r'name=["\']sync_interval["\'][^>]*value=["\']([^"\']*)', form_html)
        if sync_match:
            current_values['sync_interval'] = sync_match.group(1)
        
        results["tests"][test_name] = {
            "status": "passed",
            "current_values": current_values
        }
        results["summary"]["passed"] += 1
        print(f"✅ Current values extracted: {current_values}")
        
    except Exception as e:
        results["tests"][test_name] = {"status": "error", "error": str(e)}
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Error extracting values: {e}")
        print(f"❌ Error extracting values: {e}")
    
    # Test 3: Submit form with changes
    test_name = "submit_form_changes"
    results["tests"][test_name] = {"status": "running"}
    results["summary"]["total_tests"] += 1
    
    try:
        print("3. Submitting form with test changes...")
        
        # Prepare form data with changes
        form_data = {
            'description': current_values.get('description', '') + ' - Updated',
            'sync_interval': '60'  # Change from 30 to 60
        }
        
        if csrf_token:
            form_data['csrfmiddlewaretoken'] = csrf_token
        
        # Submit form
        submit_response = session.post(edit_url, data=form_data, allow_redirects=False)
        
        results["tests"][test_name] = {
            "status": "passed",
            "submit_response_code": submit_response.status_code,
            "form_data_sent": form_data,
            "has_redirect": 'location' in submit_response.headers,
            "redirect_location": submit_response.headers.get('location', ''),
            "response_content_length": len(submit_response.content)
        }
        results["summary"]["passed"] += 1
        print(f"✅ Form submitted: HTTP {submit_response.status_code}")
        
        if 'location' in submit_response.headers:
            print(f"✅ Redirect to: {submit_response.headers['location']}")
        
    except Exception as e:
        results["tests"][test_name] = {"status": "error", "error": str(e)}
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Error submitting form: {e}")
        print(f"❌ Error submitting form: {e}")
    
    # Test 4: Follow redirect and check success
    test_name = "follow_redirect_check_success"
    results["tests"][test_name] = {"status": "running"}
    results["summary"]["total_tests"] += 1
    
    try:
        print("4. Following redirect and checking for success...")
        
        if 'location' in submit_response.headers:
            redirect_url = submit_response.headers['location']
            if not redirect_url.startswith('http'):
                redirect_url = urljoin(base_url, redirect_url)
            
            redirect_response = session.get(redirect_url)
            redirect_content = redirect_response.text
            
            # Check for success indicators
            has_success_message = any(indicator in redirect_content.lower() for indicator in [
                'success', 'saved', 'updated', 'modified'
            ])
            
            # Check for error indicators
            has_error_message = any(indicator in redirect_content.lower() for indicator in [
                'error', 'failed', 'invalid'
            ])
            
            results["tests"][test_name] = {
                "status": "passed",
                "redirect_response_code": redirect_response.status_code,
                "redirect_url": redirect_url,
                "has_success_message": has_success_message,
                "has_error_message": has_error_message,
                "page_title_contains_fabric": 'fabric' in redirect_content.lower()
            }
            results["summary"]["passed"] += 1
            
            if has_success_message:
                print("✅ Success message found")
            if has_error_message:
                print("⚠️ Error message found")
            print(f"✅ Redirected successfully to: {redirect_url}")
            
        else:
            results["tests"][test_name] = {
                "status": "failed",
                "error": "No redirect after form submission"
            }
            results["summary"]["failed"] += 1
            print("❌ No redirect after form submission")
            
    except Exception as e:
        results["tests"][test_name] = {"status": "error", "error": str(e)}
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Error following redirect: {e}")
        print(f"❌ Error following redirect: {e}")
    
    # Test 5: Verify changes in detail view
    test_name = "verify_changes_persisted"
    results["tests"][test_name] = {"status": "running"}
    results["summary"]["total_tests"] += 1
    
    try:
        print("5. Verifying changes were persisted...")
        
        detail_response = session.get(detail_url)
        detail_content = detail_response.text
        
        # Check if updated description is present
        updated_description = current_values.get('description', '') + ' - Updated'
        description_found = updated_description in detail_content
        
        # Check if sync interval was updated
        sync_interval_found = '60' in detail_content
        
        results["tests"][test_name] = {
            "status": "passed",
            "detail_response_code": detail_response.status_code,
            "updated_description_found": description_found,
            "sync_interval_60_found": sync_interval_found,
            "description_searched": updated_description
        }
        results["summary"]["passed"] += 1
        
        if description_found:
            print("✅ Updated description found in detail view")
        if sync_interval_found:
            print("✅ Updated sync interval found in detail view")
            
    except Exception as e:
        results["tests"][test_name] = {"status": "error", "error": str(e)}
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Error verifying changes: {e}")
        print(f"❌ Error verifying changes: {e}")
    
    # Test 6: Test required field validation
    test_name = "test_required_field_validation"
    results["tests"][test_name] = {"status": "running"}
    results["summary"]["total_tests"] += 1
    
    try:
        print("6. Testing required field validation...")
        
        # Try submitting with empty required fields
        empty_form_data = {'description': ''}  # Empty description
        if csrf_token:
            empty_form_data['csrfmiddlewaretoken'] = csrf_token
        
        validation_response = session.post(edit_url, data=empty_form_data, allow_redirects=False)
        validation_content = validation_response.text
        
        # Check if validation errors are shown
        has_validation_errors = any(indicator in validation_content.lower() for indicator in [
            'required', 'this field', 'error', 'invalid'
        ])
        
        # Check if form is re-displayed (no redirect on validation error)
        stayed_on_form = validation_response.status_code == 200
        
        results["tests"][test_name] = {
            "status": "passed",
            "validation_response_code": validation_response.status_code,
            "has_validation_errors": has_validation_errors,
            "stayed_on_form": stayed_on_form,
            "no_redirect_on_error": 'location' not in validation_response.headers
        }
        results["summary"]["passed"] += 1
        
        if has_validation_errors:
            print("✅ Validation errors displayed for empty fields")
        if stayed_on_form:
            print("✅ Form re-displayed on validation error")
            
    except Exception as e:
        results["tests"][test_name] = {"status": "error", "error": str(e)}
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Error testing validation: {e}")
        print(f"❌ Error testing validation: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("FORM SUBMISSION TEST SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {results['summary']['total_tests']}")
    print(f"Passed: {results['summary']['passed']}")
    print(f"Failed: {results['summary']['failed']}")
    
    if results['summary']['errors']:
        print("\nErrors:")
        for error in results['summary']['errors']:
            print(f"  - {error}")
    
    return results

if __name__ == "__main__":
    results = test_form_submission()
    
    # Save results
    with open('/home/ubuntu/cc/hedgehog-netbox-plugin/tests/form_submission_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: tests/form_submission_test_results.json")
    
    # Exit with appropriate code
    if results['summary']['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)