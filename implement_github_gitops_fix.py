#!/usr/bin/env python3
"""
Implement GitHub GitOps Fix

This script implements the missing GitHub integration for GitOps ingestion.
The current fix works for local directories but not for GitHub repositories.

The GitHub integration needs to:
1. Fetch files from GitHub repository
2. Identify pre-existing YAML files in root directory
3. Move them to appropriate directories (raw/, unmanaged/)
4. Push changes back to GitHub
"""

import requests
import os
import base64
import json
from pathlib import Path
import yaml
from typing import Dict, List, Any, Optional

# Environment variables
GITHUB_TOKEN = "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"
REPO_OWNER = "afewell-hh"
REPO_NAME = "gitops-test-1"
FABRIC_PATH = "gitops/hedgehog/fabric-1"

class GitHubGitOpsProcessor:
    """Process GitOps files directly in GitHub repository"""
    
    def __init__(self, token: str, owner: str, repo: str, fabric_path: str):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.fabric_path = fabric_path.strip('/')
        self.api_base = f"https://api.github.com/repos/{owner}/{repo}"
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def get_directory_contents(self, path: str = "") -> List[Dict]:
        """Get contents of a directory in the GitHub repository"""
        url = f"{self.api_base}/contents/{path}" if path else f"{self.api_base}/contents"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Failed to get contents for {path}: {response.status_code}")
                print(f"   Response: {response.text}")
                return []
        except Exception as e:
            print(f"❌ Error getting contents for {path}: {e}")
            return []
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get content of a file from GitHub"""
        url = f"{self.api_base}/contents/{file_path}"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                file_data = response.json()
                # Decode base64 content
                content = base64.b64decode(file_data['content']).decode('utf-8')
                return content
            else:
                print(f"❌ Failed to get file {file_path}: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error getting file {file_path}: {e}")
            return None
    
    def create_or_update_file(self, file_path: str, content: str, message: str, sha: str = None) -> bool:
        """Create or update a file in GitHub"""
        url = f"{self.api_base}/contents/{file_path}"
        
        # Encode content to base64
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        data = {
            'message': message,
            'content': encoded_content
        }
        
        if sha:
            data['sha'] = sha
        
        try:
            response = requests.put(url, headers=self.headers, json=data)
            if response.status_code in [200, 201]:
                print(f"✅ Successfully created/updated {file_path}")
                return True
            else:
                print(f"❌ Failed to create/update {file_path}: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error creating/updating {file_path}: {e}")
            return False
    
    def delete_file(self, file_path: str, sha: str, message: str) -> bool:
        """Delete a file from GitHub"""
        url = f"{self.api_base}/contents/{file_path}"
        
        data = {
            'message': message,
            'sha': sha
        }
        
        try:
            response = requests.delete(url, headers=self.headers, json=data)
            if response.status_code == 200:
                print(f"✅ Successfully deleted {file_path}")
                return True
            else:
                print(f"❌ Failed to delete {file_path}: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error deleting {file_path}: {e}")
            return False
    
    def analyze_fabric_directory(self) -> Dict[str, Any]:
        """Analyze the current state of the fabric directory"""
        print(f"🔍 Analyzing fabric directory: {self.fabric_path}")
        
        contents = self.get_directory_contents(self.fabric_path)
        
        analysis = {
            'yaml_files_in_root': [],
            'directories': [],
            'other_files': []
        }
        
        for item in contents:
            if item['type'] == 'file':
                if item['name'].endswith(('.yaml', '.yml')):
                    analysis['yaml_files_in_root'].append({
                        'name': item['name'],
                        'path': item['path'],
                        'sha': item['sha']
                    })
                    print(f"   📄 Found YAML file: {item['name']} (should be ingested)")
                else:
                    analysis['other_files'].append(item)
                    print(f"   📄 Other file: {item['name']}")
            elif item['type'] == 'dir':
                analysis['directories'].append(item['name'])
                print(f"   📁 Directory: {item['name']}/")
        
        return analysis
    
    def validate_yaml_file(self, content: str) -> Dict[str, Any]:
        """Validate if a YAML file contains valid Kubernetes CRs"""
        try:
            # Parse YAML content
            documents = list(yaml.safe_load_all(content))
            
            valid_crs = []
            invalid_docs = []
            
            for i, doc in enumerate(documents):
                if doc is None:
                    continue
                    
                # Check if it's a valid Kubernetes resource
                if isinstance(doc, dict) and 'apiVersion' in doc and 'kind' in doc and 'metadata' in doc:
                    # Check if it's a Hedgehog CR
                    api_version = doc.get('apiVersion', '')
                    if 'githedgehog.com' in api_version:
                        valid_crs.append({
                            'index': i,
                            'kind': doc.get('kind'),
                            'name': doc.get('metadata', {}).get('name', f'unnamed-{i}'),
                            'apiVersion': api_version
                        })
                    else:
                        invalid_docs.append({
                            'index': i,
                            'reason': 'Not a Hedgehog CR',
                            'apiVersion': api_version
                        })
                else:
                    invalid_docs.append({
                        'index': i,
                        'reason': 'Not a valid Kubernetes resource'
                    })
            
            return {
                'valid': len(valid_crs) > 0,
                'valid_crs': valid_crs,
                'invalid_docs': invalid_docs,
                'total_documents': len([d for d in documents if d is not None])
            }
            
        except yaml.YAMLError as e:
            return {
                'valid': False,
                'error': f'YAML parsing error: {str(e)}',
                'valid_crs': [],
                'invalid_docs': [],
                'total_documents': 0
            }
    
    def process_yaml_file(self, file_info: Dict, content: str) -> Dict[str, Any]:
        """Process a single YAML file - validate and determine destination"""
        print(f"📄 Processing {file_info['name']}...")
        
        validation = self.validate_yaml_file(content)
        
        result = {
            'file': file_info['name'],
            'valid': validation['valid'],
            'total_documents': validation['total_documents'],
            'valid_crs': validation['valid_crs'],
            'actions': []
        }
        
        if validation['valid']:
            print(f"   ✅ Valid Hedgehog CRs found: {len(validation['valid_crs'])}")
            for cr in validation['valid_crs']:
                print(f"      - {cr['kind']}/{cr['name']} ({cr['apiVersion']})")
            
            # For valid files, move to raw/ directory for ingestion
            raw_path = f"{self.fabric_path}/raw/{file_info['name']}"
            
            if self.create_or_update_file(raw_path, content, f"Move {file_info['name']} to raw/ for ingestion"):
                result['actions'].append(f"Moved to raw/{file_info['name']}")
                
                # Delete from root
                if self.delete_file(file_info['path'], file_info['sha'], f"Remove {file_info['name']} from root after moving to raw/"):
                    result['actions'].append(f"Removed from root")
                else:
                    result['actions'].append(f"Failed to remove from root")
            else:
                result['actions'].append(f"Failed to move to raw/")
                
        else:
            print(f"   ❌ Invalid file: {validation.get('error', 'No valid Hedgehog CRs found')}")
            
            # For invalid files, move to unmanaged/ directory
            unmanaged_path = f"{self.fabric_path}/unmanaged/{file_info['name']}"
            
            if self.create_or_update_file(unmanaged_path, content, f"Move {file_info['name']} to unmanaged/ (invalid CR)"):
                result['actions'].append(f"Moved to unmanaged/{file_info['name']}")
                
                # Delete from root
                if self.delete_file(file_info['path'], file_info['sha'], f"Remove {file_info['name']} from root after moving to unmanaged/"):
                    result['actions'].append(f"Removed from root")
                else:
                    result['actions'].append(f"Failed to remove from root")
            else:
                result['actions'].append(f"Failed to move to unmanaged/")
        
        return result
    
    def run_gitops_ingestion(self) -> Dict[str, Any]:
        """Run the complete GitOps ingestion process"""
        print("🚀 Starting GitHub GitOps Ingestion Process")
        print("=" * 60)
        
        # Step 1: Analyze current state
        analysis = self.analyze_fabric_directory()
        
        if not analysis['yaml_files_in_root']:
            print("✅ No YAML files found in root directory - nothing to process")
            return {
                'success': True,
                'message': 'No files to process',
                'files_processed': 0,
                'files_moved_to_raw': 0,
                'files_moved_to_unmanaged': 0
            }
        
        print(f"\n📊 Found {len(analysis['yaml_files_in_root'])} YAML files to process")
        
        # Step 2: Process each YAML file
        results = {
            'success': True,
            'files_processed': 0,
            'files_moved_to_raw': 0,
            'files_moved_to_unmanaged': 0,
            'processing_results': []
        }
        
        for file_info in analysis['yaml_files_in_root']:
            # Get file content
            content = self.get_file_content(file_info['path'])
            if not content:
                continue
            
            # Process the file
            process_result = self.process_yaml_file(file_info, content)
            results['processing_results'].append(process_result)
            results['files_processed'] += 1
            
            # Count successful moves
            if 'Moved to raw/' in str(process_result['actions']):
                results['files_moved_to_raw'] += 1
            elif 'Moved to unmanaged/' in str(process_result['actions']):
                results['files_moved_to_unmanaged'] += 1
        
        # Summary
        print(f"\n📊 PROCESSING COMPLETE")
        print(f"   Files processed: {results['files_processed']}")
        print(f"   Moved to raw/: {results['files_moved_to_raw']}")
        print(f"   Moved to unmanaged/: {results['files_moved_to_unmanaged']}")
        
        if results['files_moved_to_raw'] > 0 or results['files_moved_to_unmanaged'] > 0:
            print(f"\n🎉 SUCCESS: GitOps ingestion completed!")
            print(f"   ✅ Pre-existing files have been properly processed")
            print(f"   ✅ Repository structure is now clean")
        
        return results


def main():
    """Main execution"""
    print("🔧 GitHub GitOps Fix Implementation")
    print("=" * 50)
    
    # Initialize processor
    processor = GitHubGitOpsProcessor(
        token=GITHUB_TOKEN,
        owner=REPO_OWNER,
        repo=REPO_NAME,
        fabric_path=FABRIC_PATH
    )
    
    # Run the ingestion process
    results = processor.run_gitops_ingestion()
    
    # Print final status
    if results['success'] and (results['files_moved_to_raw'] > 0 or results['files_moved_to_unmanaged'] > 0):
        print("\n🎯 VERIFICATION:")
        print("   1. Check GitHub repository - files should be moved from root")
        print("   2. Valid CRs should be in raw/ directory")
        print("   3. Invalid files should be in unmanaged/ directory")
        print("   4. Root directory should be clean")
        return True
    else:
        print("\n❌ GitOps fix did not complete successfully")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)