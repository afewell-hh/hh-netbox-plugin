#!/usr/bin/env python3
"""
List available fabrics in the NetBox HNP system
"""

import os
import json
import requests
from urllib.parse import urljoin

# Load environment variables from .env file
def load_env_file(env_path='/home/ubuntu/cc/hedgehog-netbox-plugin/.env'):
    """Load environment variables from .env file"""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    os.environ[key] = value

# Load environment variables
load_env_file()

def list_fabrics():
    """List all available fabrics"""
    netbox_url = os.getenv('NETBOX_URL', 'http://localhost:8000/')
    netbox_token = os.getenv('NETBOX_TOKEN')
    
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Token {netbox_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    try:
        url = urljoin(netbox_url, 'api/plugins/hedgehog/hedgehog-fabrics/')
        response = session.get(url)
        response.raise_for_status()
        
        data = response.json()
        fabrics = data.get('results', [])
        
        print(f"Found {len(fabrics)} fabrics:")
        print("=" * 50)
        
        for fabric in fabrics:
            print(f"ID: {fabric.get('id')}")
            print(f"Name: {fabric.get('name')}")
            print(f"Description: {fabric.get('description', 'N/A')}")
            print(f"Status: {fabric.get('status')}")
            print(f"GitOps Initialized: {fabric.get('gitops_initialized', False)}")
            print(f"Sync Status: {fabric.get('sync_status', 'unknown')}")
            print(f"K8s Server: {fabric.get('kubernetes_server', 'Not configured')}")
            print("-" * 30)
            
        return fabrics
        
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving fabrics: {e}")
        return []

if __name__ == '__main__':
    fabrics = list_fabrics()