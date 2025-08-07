#!/usr/bin/env python3
"""
FGD CR Counter - Unified Fuzzy Logic

This module provides a single, simple function to count valid CR records
in any FGD directory tree. This logic is used by both pre-sync and post-sync
validation tests to ensure consistency.

The logic is "fuzzy" - it doesn't care about file names, directory structure,
or specific content. It just counts valid YAML CR objects.
"""

import requests
import base64
import yaml
import time
from typing import List, Dict, Any

class FGDCRCounter:
    """Counts CR records in FGD directory trees via GitHub API"""
    
    def __init__(self, repo_owner: str, repo_name: str, github_token: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.api_base = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        self.headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def get_directory_contents(self, path: str) -> List[Dict]:
        """Get contents of a directory via GitHub API"""
        url = f"{self.api_base}/contents/{path}"
        time.sleep(0.1)  # Rate limiting
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to get {path}: {response.status_code}")
            
        return response.json()
    
    def get_file_content(self, path: str) -> str:
        """Get content of a file via GitHub API"""
        url = f"{self.api_base}/contents/{path}"
        time.sleep(0.1)  # Rate limiting
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to get {path}: {response.status_code}")
            
        file_data = response.json()
        return base64.b64decode(file_data['content']).decode('utf-8')
    
    def is_valid_cr(self, obj: Dict) -> bool:
        """Check if a YAML object is a valid CR"""
        if not isinstance(obj, dict):
            return False
        
        # Must have 'kind' field
        if 'kind' not in obj:
            return False
        
        # Must have metadata with name
        if 'metadata' not in obj:
            return False
            
        if not isinstance(obj['metadata'], dict):
            return False
            
        if 'name' not in obj['metadata']:
            return False
        
        return True
    
    def count_crs_in_file(self, file_path: str) -> int:
        """Count valid CR records in a single YAML file"""
        try:
            content = self.get_file_content(file_path)
            
            # Parse all YAML documents in the file
            documents = list(yaml.safe_load_all(content))
            
            # Count valid CRs
            cr_count = 0
            for doc in documents:
                if self.is_valid_cr(doc):
                    cr_count += 1
            
            return cr_count
            
        except Exception as e:
            print(f"Warning: Could not parse {file_path}: {e}")
            return 0
    
    def count_crs_in_directory_tree(self, base_path: str) -> int:
        """
        Count all valid CR records in a directory tree.
        
        This is the core "fuzzy logic" that both tests use.
        It recursively scans all directories and counts valid CRs in all .yaml files.
        """
        total_crs = 0
        
        try:
            # Get contents of this directory
            contents = self.get_directory_contents(base_path)
            
            for item in contents:
                item_name = item['name']
                item_type = item['type']
                item_path = f"{base_path}/{item_name}"
                
                if item_type == 'file':
                    # Count CRs in YAML files (skip .gitkeep and non-YAML files)
                    if item_name.endswith('.yaml') and item_name != '.gitkeep':
                        file_cr_count = self.count_crs_in_file(item_path)
                        total_crs += file_cr_count
                        if file_cr_count > 0:
                            print(f"    {item_path}: {file_cr_count} CRs")
                
                elif item_type == 'dir':
                    # Recursively count CRs in subdirectories
                    subdir_crs = self.count_crs_in_directory_tree(item_path)
                    total_crs += subdir_crs
                    if subdir_crs > 0:
                        print(f"    {item_path}/: {subdir_crs} CRs")
            
            return total_crs
            
        except Exception as e:
            print(f"Warning: Could not scan directory {base_path}: {e}")
            return 0


def count_fgd_crs(repo_owner: str, repo_name: str, fgd_path: str, 
                  github_token: str, target_dir: str = None) -> int:
    """
    Convenience function to count CRs in an FGD directory.
    
    Args:
        repo_owner: GitHub repo owner
        repo_name: GitHub repo name  
        fgd_path: Path to FGD root (e.g., "gitops/hedgehog/fabric-1")
        github_token: GitHub API token
        target_dir: Subdirectory to scan (e.g., "raw" or "managed"), or None for entire FGD
        
    Returns:
        Total number of valid CR records found
    """
    counter = FGDCRCounter(repo_owner, repo_name, github_token)
    
    if target_dir:
        scan_path = f"{fgd_path}/{target_dir}"
    else:
        scan_path = fgd_path
    
    print(f"Scanning {scan_path} for CR records...")
    return counter.count_crs_in_directory_tree(scan_path)


if __name__ == '__main__':
    # Test the counter logic
    import os
    
    # Load GitHub token
    github_token = None
    try:
        with open('/home/ubuntu/cc/hedgehog-netbox-plugin/.env', 'r') as f:
            for line in f:
                if line.startswith('GITHUB_TOKEN='):
                    github_token = line.split('=', 1)[1].strip().strip('"')
    except:
        print("Could not load GitHub token from .env file")
        exit(1)
    
    if not github_token:
        print("GitHub token not found in .env file")
        exit(1)
    
    # Test counting CRs in raw directory
    print("=== TESTING FUZZY CR COUNTER ===")
    raw_crs = count_fgd_crs(
        repo_owner="afewell-hh",
        repo_name="gitops-test-1", 
        fgd_path="gitops/hedgehog/fabric-1",
        github_token=github_token,
        target_dir="raw"
    )
    
    print(f"\nTotal CRs in raw/: {raw_crs}")
    
    # Test counting CRs in managed directory  
    managed_crs = count_fgd_crs(
        repo_owner="afewell-hh",
        repo_name="gitops-test-1",
        fgd_path="gitops/hedgehog/fabric-1", 
        github_token=github_token,
        target_dir="managed"
    )
    
    print(f"Total CRs in managed/: {managed_crs}")
    print(f"\n=== SUMMARY ===")
    print(f"Raw CRs: {raw_crs}")
    print(f"Managed CRs: {managed_crs}")
    print(f"Total CRs: {raw_crs + managed_crs}")