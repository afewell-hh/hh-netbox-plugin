#!/usr/bin/env python3
"""
Simple validation script to check CRD import success and detail view functionality.
Uses basic HTTP requests and text parsing to avoid dependencies.
"""

import requests
import re
import json
from urllib.parse import urljoin

class SimpleCRDValidator:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NetBox-CRD-Validator/1.0'
        })
        
    def test_basic_connectivity(self):
        """Test basic connectivity to NetBox"""
        print("=== TESTING BASIC CONNECTIVITY ===")
        
        try:
            url = urljoin(self.base_url, '/plugins/hedgehog/')
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                print("✓ NetBox Hedgehog plugin accessible")
                
                # Check if it's the hedgehog plugin
                if 'hedgehog' in response.text.lower():
                    print("✓ Hedgehog plugin loaded correctly")
                    return True
                else:
                    print("⚠️  Response received but doesn't contain hedgehog content")
                    return False
            else:
                print(f"✗ HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ Connection failed: {str(e)}")
            return False
    
    def check_list_pages(self):
        """Check list pages for data presence"""
        print("\n=== CHECKING LIST PAGES FOR DATA ===")
        
        pages = [
            ('Fabrics', '/plugins/hedgehog/fabrics/'),
            ('Servers', '/plugins/hedgehog/servers/'),
            ('Switches', '/plugins/hedgehog/switches/'),
            ('Connections', '/plugins/hedgehog/connections/'),
            ('VPCs', '/plugins/hedgehog/vpcs/'),
            ('Switch Groups', '/plugins/hedgehog/switch-groups/'),
            ('VLAN Namespaces', '/plugins/hedgehog/vlan-namespaces/')
        ]
        
        results = {}
        
        for page_name, path in pages:
            try:
                url = urljoin(self.base_url, path)
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    content = response.text
                    
                    # Simple heuristics to detect data presence
                    has_table = '<table' in content
                    has_tbody = '<tbody' in content
                    
                    # Look for common "no data" indicators
                    no_data_patterns = [
                        'no items found',
                        'no objects found',
                        'no data available',
                        'empty list',
                        'nothing to show'
                    ]
                    
                    has_no_data_message = any(pattern in content.lower() for pattern in no_data_patterns)
                    
                    # Count table rows (rough estimate)
                    row_count = content.count('<tr') - content.count('<th')  # Subtract header rows
                    
                    # Look for pagination
                    has_pagination = 'pagination' in content.lower() or 'page' in content.lower()
                    
                    print(f"{page_name}:")
                    print(f"  Status: Accessible")
                    print(f"  Has table: {has_table}")
                    print(f"  Estimated rows: {max(0, row_count)}")
                    
                    if has_no_data_message:
                        print(f"  ⚠️  Contains 'no data' message")
                    
                    if row_count > 0:
                        print(f"  ✓ Contains data")
                    
                    results[page_name] = {
                        'status': 'accessible',
                        'has_table': has_table,
                        'estimated_rows': max(0, row_count),
                        'has_data': row_count > 0,
                        'has_no_data_message': has_no_data_message
                    }
                    
                else:
                    print(f"{page_name}: HTTP {response.status_code}")
                    results[page_name] = {'status': f'http_{response.status_code}'}
                    
            except Exception as e:
                print(f"{page_name}: Error - {str(e)}")
                results[page_name] = {'status': 'error', 'error': str(e)}
        
        return results
    
    def find_and_test_detail_views(self):
        """Find objects and test their detail views"""
        print("\n=== TESTING DETAIL VIEWS ===")
        
        # Test patterns to find detail view URLs
        list_pages = [
            ('Servers', '/plugins/hedgehog/servers/'),
            ('Switches', '/plugins/hedgehog/switches/'),
            ('Connections', '/plugins/hedgehog/connections/'),
            ('VPCs', '/plugins/hedgehog/vpcs/')
        ]
        
        detail_results = {}
        
        for object_type, list_path in list_pages:
            print(f"\nTesting {object_type}:")
            
            try:
                # Get the list page
                url = urljoin(self.base_url, list_path)
                response = self.session.get(url, timeout=10)
                
                if response.status_code != 200:
                    print(f"  ✗ List page not accessible: HTTP {response.status_code}")
                    detail_results[object_type] = {'status': 'list_page_failed'}
                    continue
                
                content = response.text
                
                # Find detail view links using regex
                # Look for href patterns like /plugins/hedgehog/servers/123/
                pattern = rf'{re.escape(list_path)}\d+/'
                detail_urls = re.findall(pattern, content)
                
                # Remove duplicates and limit to first 3
                unique_urls = list(set(detail_urls))[:3]
                
                if not unique_urls:
                    print(f"  ⚠️  No detail URLs found (no {object_type.lower()} objects)")
                    detail_results[object_type] = {'status': 'no_objects'}
                    continue
                
                print(f"  Found {len(unique_urls)} {object_type.lower()} to test")
                
                success_count = 0
                test_results = []
                
                for detail_url in unique_urls:
                    try:
                        full_url = urljoin(self.base_url, detail_url)
                        detail_response = self.session.get(full_url, timeout=10)
                        
                        if detail_response.status_code == 200:
                            success_count += 1
                            detail_content = detail_response.text
                            
                            # Try to extract object name from title or heading
                            title_match = re.search(r'<title>([^<]*)</title>', detail_content, re.IGNORECASE)
                            object_name = "Unknown"
                            if title_match:
                                title_text = title_match.group(1)
                                # Extract name from title like "server-01 | NetBox"
                                name_match = re.search(r'^([^|]+)', title_text.strip())
                                if name_match:
                                    object_name = name_match.group(1).strip()
                            
                            # Look for state information in the content
                            state_patterns = [
                                r'state[:\s]*(\w+)',
                                r'status[:\s]*(\w+)',
                                r'State:\s*(\w+)',
                                r'Status:\s*(\w+)'
                            ]
                            
                            object_state = "Unknown"
                            for pattern in state_patterns:
                                state_match = re.search(pattern, detail_content, re.IGNORECASE)
                                if state_match:
                                    potential_state = state_match.group(1)
                                    if potential_state.lower() in ['draft', 'committed', 'synced', 'drifted', 'orphaned', 'pending']:
                                        object_state = potential_state
                                        break
                            
                            print(f"    ✓ {object_name[:30]}... (State: {object_state})")
                            
                            test_results.append({
                                'name': object_name,
                                'state': object_state,
                                'url': detail_url,
                                'status': 'success'
                            })
                            
                        else:
                            print(f"    ✗ Detail view failed: HTTP {detail_response.status_code}")
                            test_results.append({
                                'url': detail_url,
                                'status': f'failed_http_{detail_response.status_code}'
                            })
                            
                    except Exception as e:
                        print(f"    ✗ Error testing {detail_url}: {str(e)}")
                        test_results.append({
                            'url': detail_url,
                            'status': 'exception',
                            'error': str(e)
                        })
                
                detail_results[object_type] = {
                    'status': 'tested',
                    'total_found': len(unique_urls),
                    'successful_tests': success_count,
                    'objects': test_results
                }
                
                print(f"  Result: {success_count}/{len(unique_urls)} detail views accessible")
                
            except Exception as e:
                print(f"  ✗ Error testing {object_type}: {str(e)}")
                detail_results[object_type] = {'status': 'error', 'error': str(e)}
        
        return detail_results
    
    def check_workflow_functionality(self):
        """Test basic workflow functionality"""
        print("\n=== CHECKING WORKFLOW FUNCTIONALITY ===")
        
        # Test a specific fabric detail page for sync functionality
        try:
            # First get fabrics list
            fabrics_response = self.session.get(urljoin(self.base_url, '/plugins/hedgehog/fabrics/'))
            
            if fabrics_response.status_code == 200:
                content = fabrics_response.text
                
                # Find a fabric detail URL
                fabric_urls = re.findall(r'/plugins/hedgehog/fabrics/\d+/', content)
                
                if fabric_urls:
                    fabric_url = fabric_urls[0]
                    print(f"Testing fabric workflow: {fabric_url}")
                    
                    # Test fabric detail page
                    detail_response = self.session.get(urljoin(self.base_url, fabric_url))
                    
                    if detail_response.status_code == 200:
                        detail_content = detail_response.text
                        
                        # Check for workflow elements
                        has_sync_button = 'sync' in detail_content.lower()
                        has_test_connection = 'test connection' in detail_content.lower()
                        has_edit_link = 'edit' in detail_content.lower()
                        
                        print(f"  ✓ Fabric detail page accessible")
                        print(f"  Has sync functionality: {has_sync_button}")
                        print(f"  Has test connection: {has_test_connection}")
                        print(f"  Has edit functionality: {has_edit_link}")
                        
                        return {
                            'status': 'tested',
                            'fabric_detail_accessible': True,
                            'has_sync': has_sync_button,
                            'has_test_connection': has_test_connection,
                            'has_edit': has_edit_link
                        }
                    else:
                        print(f"  ✗ Fabric detail page failed: HTTP {detail_response.status_code}")
                        return {'status': 'fabric_detail_failed'}
                else:
                    print(f"  ⚠️  No fabric URLs found")
                    return {'status': 'no_fabrics'}
            else:
                print(f"  ✗ Fabrics list failed: HTTP {fabrics_response.status_code}")
                return {'status': 'fabrics_list_failed'}
                
        except Exception as e:
            print(f"  ✗ Error testing workflow: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    def run_validation(self):
        """Run complete validation"""
        print("NetBox Hedgehog Plugin - CRD Import Validation")
        print("=" * 60)
        
        # Test basic connectivity
        if not self.test_basic_connectivity():
            print("\n✗ CRITICAL: Basic connectivity failed")
            return False
        
        # Check list pages
        list_results = self.check_list_pages()
        
        # Test detail views
        detail_results = self.find_and_test_detail_views()
        
        # Check workflow functionality
        workflow_results = self.check_workflow_functionality()
        
        # Generate summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        
        # List pages summary
        accessible_pages = len([r for r in list_results.values() if r.get('status') == 'accessible'])
        pages_with_data = len([r for r in list_results.values() if r.get('has_data')])
        total_objects = sum(r.get('estimated_rows', 0) for r in list_results.values() if 'estimated_rows' in r)
        
        print(f"\nList Pages:")
        print(f"  Accessible: {accessible_pages}/{len(list_results)}")
        print(f"  With data: {pages_with_data}/{accessible_pages}")
        print(f"  Total objects estimated: {total_objects}")
        
        # Detail views summary
        print(f"\nDetail Views:")
        successful_detail_tests = 0
        total_detail_tests = 0
        
        for object_type, results in detail_results.items():
            if results.get('status') == 'tested':
                successful_detail_tests += results.get('successful_tests', 0)
                total_detail_tests += results.get('total_found', 0)
        
        print(f"  Accessible: {successful_detail_tests}/{total_detail_tests}")
        
        # State analysis
        states_found = set()
        for object_type, results in detail_results.items():
            if results.get('objects'):
                for obj in results['objects']:
                    if obj.get('state') and obj['state'] != 'Unknown':
                        states_found.add(obj['state'])
        
        if states_found:
            print(f"  States found: {', '.join(sorted(states_found))}")
            
            # Check for six-state model
            expected_states = {'draft', 'committed', 'synced', 'drifted', 'orphaned', 'pending'}
            valid_states = states_found.intersection(expected_states)
            
            if 'synced' in valid_states:
                print(f"  ✓ 'synced' state found - indicates successful import")
            else:
                print(f"  ⚠️  'synced' state not detected")
        else:
            print(f"  ⚠️  No state information detected")
        
        # Workflow functionality
        print(f"\nWorkflow Functionality:")
        if workflow_results.get('status') == 'tested':
            print(f"  Fabric workflows: ✓ Accessible")
            if workflow_results.get('has_sync'):
                print(f"  Sync functionality: ✓ Available")
            if workflow_results.get('has_test_connection'):
                print(f"  Test connection: ✓ Available")
        else:
            print(f"  Workflow testing: ✗ Failed")
        
        # Overall assessment
        print(f"\nOverall Assessment:")
        
        success_indicators = 0
        total_indicators = 5
        
        if accessible_pages >= len(list_results) * 0.8:  # 80% pages accessible
            success_indicators += 1
            print(f"  ✓ Page accessibility: Good")
        else:
            print(f"  ✗ Page accessibility: Poor")
        
        if total_objects > 30:  # Reasonable number of objects
            success_indicators += 1
            print(f"  ✓ Data import: Good object count")
        elif total_objects > 0:
            print(f"  ⚠️  Data import: Low object count")
        else:
            print(f"  ✗ Data import: No objects found")
        
        if successful_detail_tests > 0:
            success_indicators += 1
            print(f"  ✓ Detail views: Functional")
        else:
            print(f"  ✗ Detail views: Not working")
        
        if 'synced' in states_found:
            success_indicators += 1
            print(f"  ✓ Six-state model: Working (synced state found)")
        else:
            print(f"  ✗ Six-state model: Issues detected")
        
        if workflow_results.get('has_sync') and workflow_results.get('has_test_connection'):
            success_indicators += 1
            print(f"  ✓ CRUD operations: Available")
        else:
            print(f"  ✗ CRUD operations: Limited")
        
        overall_score = (success_indicators / total_indicators) * 100
        print(f"\nOverall Score: {success_indicators}/{total_indicators} ({overall_score:.0f}%)")
        
        if overall_score >= 80:
            print(f"✓ VALIDATION SUCCESSFUL - Import and workflows are functional")
        elif overall_score >= 60:
            print(f"⚠️  VALIDATION PARTIAL - Some issues detected but core functionality works")
        else:
            print(f"✗ VALIDATION FAILED - Significant issues detected")
        
        return overall_score >= 60

if __name__ == '__main__':
    validator = SimpleCRDValidator()
    success = validator.run_validation()