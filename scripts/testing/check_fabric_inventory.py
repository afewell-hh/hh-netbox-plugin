#!/usr/bin/env python3
"""
Check what fabrics actually exist in the system for Layer 5 testing
"""

import requests
import json
import re
from datetime import datetime

def check_fabric_inventory():
    session = requests.Session()
    base_url = "http://localhost:8000"
    
    print("=== CHECKING FABRIC INVENTORY ===")
    
    # Load existing cookies if available
    try:
        with open('cookies.txt', 'r') as f:
            cookies = f.read()
            if 'sessionid' in cookies:
                for line in cookies.split('\n'):
                    if 'sessionid' in line:
                        parts = line.split('\t')
                        if len(parts) >= 7:
                            session.cookies.set('sessionid', parts[6])
    except:
        pass
    
    # Get fabric list page
    try:
        response = session.get(f"{base_url}/plugins/hedgehog/fabrics/")
        print(f"Fabric list page status: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            # Look for fabric links/references
            fabric_patterns = [
                r'/plugins/hedgehog/fabrics/(\d+)/',
                r'fabric[_-]?(\d+)',
                r'href=["\'][^"\']*fabrics/(\d+)/',
            ]
            
            fabric_ids = set()
            for pattern in fabric_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    try:
                        fabric_ids.add(int(match))
                    except:
                        pass
            
            print(f"Found fabric IDs: {sorted(fabric_ids)}")
            
            # Test each fabric ID
            working_fabrics = []
            for fabric_id in sorted(fabric_ids):
                try:
                    fabric_response = session.get(f"{base_url}/plugins/hedgehog/fabrics/{fabric_id}/")
                    status = fabric_response.status_code
                    accessible = status == 200
                    
                    fabric_info = {
                        'id': fabric_id,
                        'status_code': status,
                        'accessible': accessible
                    }
                    
                    if accessible:
                        # Extract fabric details
                        page_content = fabric_response.text
                        
                        # Look for fabric name
                        name_patterns = [
                            r'<h1[^>]*>([^<]+)</h1>',
                            r'<title>([^<]*)</title>',
                            r'fabric[_-]?name["\s>:]*([^<"\s]+)'
                        ]
                        
                        for pattern in name_patterns:
                            match = re.search(pattern, page_content, re.IGNORECASE)
                            if match:
                                fabric_info['name'] = match.group(1).strip()
                                break
                        
                        # Look for sync status
                        if 'sync' in page_content.lower():
                            fabric_info['has_sync_capability'] = True
                            
                            if 'never_synced' in page_content.lower():
                                fabric_info['sync_status'] = 'never_synced'
                            elif 'in_sync' in page_content.lower():
                                fabric_info['sync_status'] = 'in_sync'
                            elif 'syncing' in page_content.lower():
                                fabric_info['sync_status'] = 'syncing'
                            else:
                                fabric_info['sync_status'] = 'unknown'
                        
                        working_fabrics.append(fabric_info)
                    
                    print(f"Fabric {fabric_id}: {fabric_info}")
                    
                except Exception as e:
                    print(f"Error checking fabric {fabric_id}: {e}")
            
            # Save detailed inventory
            inventory = {
                'timestamp': datetime.now().isoformat(),
                'total_fabric_ids_found': len(fabric_ids),
                'working_fabrics': working_fabrics,
                'recommended_test_fabric': working_fabrics[0]['id'] if working_fabrics else None
            }
            
            with open('fabric_inventory_for_layer5.json', 'w') as f:
                json.dump(inventory, f, indent=2)
            
            print(f"\n✅ Inventory complete! Found {len(working_fabrics)} working fabrics")
            if working_fabrics:
                print(f"Recommended fabric for testing: {inventory['recommended_test_fabric']}")
            
            return inventory
            
        else:
            print(f"❌ Cannot access fabric list: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Inventory check failed: {e}")
        return None

if __name__ == "__main__":
    check_fabric_inventory()