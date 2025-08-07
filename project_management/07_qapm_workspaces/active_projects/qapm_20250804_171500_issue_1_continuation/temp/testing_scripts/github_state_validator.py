#!/usr/bin/env python3
"""
GitHub Repository State Validator
Integration Testing Specialist Tool

Purpose: Document GitHub repository state before and after sync operations
Target: https://github.com/afewell-hh/gitops-test-1/tree/main/gitops/hedgehog/fabric-1/raw
"""

import requests
import json
from datetime import datetime
import os

class GitHubStateValidator:
    def __init__(self):
        self.base_url = "https://api.github.com/repos/afewell-hh/gitops-test-1"
        self.raw_path = "gitops/hedgehog/fabric-1/raw"
        self.managed_path = "gitops/hedgehog/fabric-1/managed"
        
    def get_directory_contents(self, path):
        """Get contents of a directory in the GitHub repository."""
        url = f"{self.base_url}/contents/{path}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return []  # Directory doesn't exist or is empty
            else:
                print(f"Error accessing {path}: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception accessing {path}: {e}")
            return None
    
    def document_current_state(self):
        """Document the current state of both raw/ and managed/ directories."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        state = {
            "timestamp": timestamp,
            "raw_directory": {
                "path": self.raw_path,
                "contents": self.get_directory_contents(self.raw_path)
            },
            "managed_directory": {
                "path": self.managed_path,
                "contents": self.get_directory_contents(self.managed_path)
            }
        }
        
        # Count files
        raw_files = len(state["raw_directory"]["contents"]) if state["raw_directory"]["contents"] else 0
        managed_files = len(state["managed_directory"]["contents"]) if state["managed_directory"]["contents"] else 0
        
        print(f"GitHub Repository State at {timestamp}")
        print(f"Raw directory: {raw_files} files")
        print(f"Managed directory: {managed_files} files")
        
        if state["raw_directory"]["contents"]:
            print("\nRaw directory files:")
            for file in state["raw_directory"]["contents"]:
                print(f"  - {file['name']} ({file['size']} bytes)")
        
        if state["managed_directory"]["contents"]:
            print("\nManaged directory files:")
            for file in state["managed_directory"]["contents"]:
                print(f"  - {file['name']} ({file['size']} bytes)")
        
        return state
    
    def save_state(self, state, filename_prefix="github_state"):
        """Save state to JSON file for comparison."""
        timestamp = state["timestamp"]
        filename = f"{filename_prefix}_{timestamp}.json"
        filepath = f"/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/active_projects/qapm_20250804_171500_issue_1_continuation/04_sub_agent_work/integration_testing/evidence/{filename}"
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        print(f"State saved to: {filepath}")
        return filepath
    
    def compare_states(self, before_state, after_state):
        """Compare two states and document changes."""
        comparison = {
            "before_timestamp": before_state["timestamp"],
            "after_timestamp": after_state["timestamp"],
            "changes": {
                "raw_directory": {},
                "managed_directory": {}
            }
        }
        
        # Compare raw directory
        before_raw = set(f['name'] for f in (before_state["raw_directory"]["contents"] or []))
        after_raw = set(f['name'] for f in (after_state["raw_directory"]["contents"] or []))
        
        comparison["changes"]["raw_directory"] = {
            "files_removed": list(before_raw - after_raw),
            "files_added": list(after_raw - before_raw),
            "files_unchanged": list(before_raw & after_raw)
        }
        
        # Compare managed directory
        before_managed = set(f['name'] for f in (before_state["managed_directory"]["contents"] or []))
        after_managed = set(f['name'] for f in (after_state["managed_directory"]["contents"] or []))
        
        comparison["changes"]["managed_directory"] = {
            "files_removed": list(before_managed - after_managed),
            "files_added": list(after_managed - before_managed),
            "files_unchanged": list(before_managed & after_managed)
        }
        
        return comparison

if __name__ == "__main__":
    validator = GitHubStateValidator()
    state = validator.document_current_state()
    validator.save_state(state, "baseline_state")