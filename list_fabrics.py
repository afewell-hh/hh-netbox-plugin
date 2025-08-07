#!/usr/bin/env python3
"""
Simple script to list fabrics in the NetBox HNP plugin
"""

import requests

def list_fabrics():
    """List all fabrics using various API approaches."""
    
    headers = {
        'Authorization': 'Token ced6a3e0a978db0ad4de39cd66af4868372d7dd0',
        'Accept': 'application/json'
    }
    
    # Try different API endpoints
    endpoints = [
        'http://localhost:8000/api/plugins/hedgehog/fabrics/',
        'http://localhost:8000/api/plugins/netbox-hedgehog/fabrics/',
        'http://localhost:8000/api/plugins/netbox_hedgehog/fabrics/',
    ]
    
    for endpoint in endpoints:
        print(f"Trying: {endpoint}")
        try:
            response = requests.get(endpoint, headers=headers)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'results' in data:
                        print(f"Found {len(data['results'])} fabrics:")
                        for fabric in data['results']:
                            print(f"  ID: {fabric.get('id')}, Name: {fabric.get('name')}")
                            if 'git_repository' in fabric:
                                print(f"     Git: {fabric['git_repository']}")
                        return data['results']
                    else:
                        print(f"Data: {data}")
                except:
                    print(f"Response text: {response.text[:200]}")
            else:
                print(f"Error: {response.text[:100]}")
        except Exception as e:
            print(f"Exception: {e}")
        print()
    
    return None

if __name__ == "__main__":
    fabrics = list_fabrics()
    if not fabrics:
        print("No fabrics found through API. The fabric data might only be accessible through the web interface.")