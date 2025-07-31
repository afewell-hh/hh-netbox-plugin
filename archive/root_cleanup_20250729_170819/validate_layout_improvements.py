#!/usr/bin/env python3
"""
Validate Fabric Detail Page Layout Improvements
==============================================

This script validates the layout improvements based on user feedback:
1. Colored sync status boxes removed from top
2. Left column reorganized into logical groupings (Git, HCKC, Drift)
3. Right column Git Configuration uses vertical layout
"""

import requests
import re
from datetime import datetime

def validate_colored_boxes_removed():
    """Test that brightly colored sync status boxes are removed"""
    print("=== Testing Colored Boxes Removal ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    
    if response.status_code != 200:
        print(f"❌ Page not accessible: {response.status_code}")
        return False
    
    html = response.text
    
    # Check for colored card elements that should be removed
    colored_card_patterns = [
        r'card border-info',
        r'card border-primary',
        r'col-md-6.*Git.*Sync',
        r'col-md-6.*HCKC.*Sync'
    ]
    
    found_colored = []
    for pattern in colored_card_patterns:
        if re.search(pattern, html):
            found_colored.append(pattern)
    
    if found_colored:
        print(f"❌ Colored sync boxes still found: {found_colored}")
        return False
    else:
        print("✅ Brightly colored sync status boxes successfully removed")
        return True

def validate_left_column_reorganization():
    """Test that left column is reorganized into logical groupings"""
    print("\n=== Testing Left Column Reorganization ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    html = response.text
    
    # Look for section headings
    expected_sections = [
        r'Git Repository Sync',
        r'HCKC.*Sync|Kubernetes.*Sync', 
        r'Drift Detection'
    ]
    
    found_sections = []
    for section in expected_sections:
        if re.search(section, html):
            found_sections.append(section)
    
    # Look for separated sync fields
    sync_field_patterns = [
        r'Git Sync Status',
        r'HCKC Sync Status',
        r'Git Last Sync',
        r'HCKC Last Sync'
    ]
    
    found_fields = []
    for field in sync_field_patterns:
        if re.search(field, html):
            found_fields.append(field)
    
    sections_found = len(found_sections)
    fields_found = len(found_fields)
    
    if sections_found >= 2 and fields_found >= 2:  # At least Git and HCKC sections with some fields
        print(f"✅ Left column reorganized successfully")
        print(f"   Sections found: {sections_found}/3")
        print(f"   Separated sync fields: {fields_found}/4")
        return True
    else:
        print(f"❌ Left column reorganization incomplete")
        print(f"   Sections: {found_sections}")
        print(f"   Fields: {found_fields}")
        return False

def validate_drift_detection_added():
    """Test that drift detection information is added to left column"""
    print("\n=== Testing Drift Detection Addition ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    html = response.text
    
    # Look for drift-related elements
    drift_patterns = [
        r'Drift Detection',
        r'Drift Status',
        r'Drift Count',
        r'mdi-compare'  # Icon for drift detection
    ]
    
    found_drift = []
    for pattern in drift_patterns:
        if re.search(pattern, html):
            found_drift.append(pattern)
    
    if len(found_drift) >= 2:  # Should have heading and at least one field
        print(f"✅ Drift detection information added")
        print(f"   Found drift elements: {len(found_drift)}/4")
        return True
    else:
        print(f"❌ Drift detection not properly added: {found_drift}")
        return False

def validate_right_column_vertical_layout():
    """Test that right column Git Configuration uses vertical layout"""
    print("\n=== Testing Right Column Vertical Layout ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    html = response.text
    
    # Look for vertical layout indicators in Git Configuration section
    vertical_layout_patterns = [
        r'<strong>Repository:</strong><br>',
        r'<strong>GitOps Directory:</strong><br>',
        r'<strong>URL:</strong><br>',
        r'<strong>Branch:</strong><br>'
    ]
    
    found_vertical = []
    for pattern in vertical_layout_patterns:
        if re.search(pattern, html):
            found_vertical.append(pattern)
    
    if len(found_vertical) >= 2:  # Should have multiple fields with <br> tags
        print(f"✅ Right column uses vertical layout")
        print(f"   Vertical fields found: {len(found_vertical)}/4")
        return True
    else:
        print(f"❌ Right column not using vertical layout: {found_vertical}")
        return False

def validate_table_style_maintained():
    """Test that the table-style display in left column is maintained"""
    print("\n=== Testing Table Style Maintenance ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    html = response.text
    
    # Look for table structure elements
    table_patterns = [
        r'table table-borderless',
        r'<th width="200">',
        r'<tr>.*<th>.*</th>.*<td>',
        r'badge.*bg-'  # Badge styling
    ]
    
    found_table = []
    for pattern in table_patterns:
        if re.search(pattern, html):
            found_table.append(pattern)
    
    if len(found_table) >= 3:  # Should have table structure
        print(f"✅ Table-style display maintained")
        print(f"   Table elements found: {len(found_table)}/4")
        return True
    else:
        print(f"❌ Table-style display not maintained: {found_table}")
        return False

def main():
    """Run complete validation of layout improvements"""
    print("FABRIC DETAIL PAGE LAYOUT IMPROVEMENTS VALIDATION")
    print("=" * 60)
    print(f"Testing improved layout at: {datetime.now()}")
    print("=" * 60)
    
    tests = [
        validate_colored_boxes_removed,
        validate_left_column_reorganization,
        validate_drift_detection_added,
        validate_right_column_vertical_layout,
        validate_table_style_maintained
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("=== LAYOUT IMPROVEMENTS VALIDATION SUMMARY ===")
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 ALL LAYOUT IMPROVEMENTS VALIDATED!")
        print("✅ Brightly colored sync boxes removed")
        print("✅ Left column reorganized into logical groupings")
        print("✅ Drift detection information added")
        print("✅ Right column uses vertical layout")
        print("✅ Table-style display maintained")
    else:
        print("❌ Some improvements need attention:")
        test_names = [
            "Colored boxes removal",
            "Left column reorganization", 
            "Drift detection addition",
            "Right column vertical layout",
            "Table style maintenance"
        ]
        for i, (name, result) in enumerate(zip(test_names, results)):
            status = "✅" if result else "❌"
            print(f"   {status} {name}")
    
    print("=" * 60)
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)