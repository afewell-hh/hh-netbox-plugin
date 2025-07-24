"""
GitOps Test Helpers for HNP End-to-End Testing

Utilities for GitOps directory manipulation and Git operations during testing.
"""

import os
import shutil
import tempfile
import subprocess
import yaml
import json
from pathlib import Path
from datetime import datetime, timezone


class GitOpsTestHelper:
    """Helper for GitOps operations during testing."""
    
    def __init__(self, test_repo_url="https://github.com/afewell-hh/gitops-test-1"):
        self.test_repo_url = test_repo_url
        self.temp_dir = None
        self.repo_path = None
    
    def setup_test_repository(self):
        """
        Set up a temporary GitOps repository for testing.
        
        Returns:
            Path to cloned repository
        """
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp(prefix="hnp_gitops_test_")
        self.repo_path = os.path.join(self.temp_dir, "gitops-test")
        
        try:
            # Clone test repository
            result = subprocess.run([
                'git', 'clone', self.test_repo_url, self.repo_path
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                raise Exception(f"Failed to clone repository: {result.stderr}")
            
            return self.repo_path
            
        except subprocess.TimeoutExpired:
            raise Exception("Git clone timed out")
        except Exception as e:
            self.cleanup()
            raise e
    
    def create_test_gitops_structure(self, fabric_namespace="fabric-1"):
        """
        Create GitOps directory structure for testing.
        
        Args:
            fabric_namespace: Kubernetes namespace for fabric
            
        Returns:
            Path to GitOps directory
        """
        if not self.repo_path:
            self.setup_test_repository()
        
        gitops_path = os.path.join(self.repo_path, "gitops", "hedgehog", fabric_namespace)
        
        # Create directory structure
        os.makedirs(os.path.join(gitops_path, "raw"), exist_ok=True)
        os.makedirs(os.path.join(gitops_path, "managed"), exist_ok=True)
        os.makedirs(os.path.join(gitops_path, ".hnp"), exist_ok=True)
        
        return gitops_path
    
    def create_test_crs_in_gitops(self, gitops_path, test_data):
        """
        Create test CR files in GitOps directory structure.
        
        Args:
            gitops_path: Path to GitOps directory
            test_data: Test data from HNPTestDataFactory
        """
        from .test_data_factory import HNPTestDataFactory
        
        # Create raw files (multi-document YAML)
        raw_path = os.path.join(gitops_path, "raw")
        
        # VPC raw file
        if test_data.get('vpcs'):
            vpc_docs = []
            for vpc in test_data['vpcs']:
                yaml_content = HNPTestDataFactory.cr_data_to_yaml(
                    vpc, 'vpc.githedgehog.com/v1beta1', 'VPC'
                )
                vpc_docs.append(yaml_content)
            
            with open(os.path.join(raw_path, "vpcs.yaml"), 'w') as f:
                f.write("---\n".join(vpc_docs))
        
        # Switch raw file
        if test_data.get('switches'):
            switch_docs = []
            for switch in test_data['switches']:
                yaml_content = HNPTestDataFactory.cr_data_to_yaml(
                    switch, 'wiring.githedgehog.com/v1beta1', 'Switch'
                )
                switch_docs.append(yaml_content)
            
            with open(os.path.join(raw_path, "switches.yaml"), 'w') as f:
                f.write("---\n".join(switch_docs))
        
        # Connection raw file
        if test_data.get('connections'):
            connection_docs = []
            for connection in test_data['connections']:
                yaml_content = HNPTestDataFactory.cr_data_to_yaml(
                    connection, 'wiring.githedgehog.com/v1beta1', 'Connection'
                )
                connection_docs.append(yaml_content)
            
            with open(os.path.join(raw_path, "connections.yaml"), 'w') as f:
                f.write("---\n".join(connection_docs))
        
        # Create managed files (individual files)
        managed_path = os.path.join(gitops_path, "managed")
        
        # Individual VPC files
        for i, vpc in enumerate(test_data.get('vpcs', []), 1):
            yaml_content = HNPTestDataFactory.cr_data_to_yaml(
                vpc, 'vpc.githedgehog.com/v1beta1', 'VPC'
            )
            filename = f"vpc-{str(i).zfill(3)}.yaml"
            with open(os.path.join(managed_path, filename), 'w') as f:
                f.write(yaml_content)
        
        # Individual Switch files
        for i, switch in enumerate(test_data.get('switches', []), 1):
            yaml_content = HNPTestDataFactory.cr_data_to_yaml(
                switch, 'wiring.githedgehog.com/v1beta1', 'Switch'
            )
            filename = f"switch-{str(i).zfill(3)}.yaml"
            with open(os.path.join(managed_path, filename), 'w') as f:
                f.write(yaml_content)
        
        # Create HNP metadata
        hnp_path = os.path.join(gitops_path, ".hnp")
        
        sync_status = {
            'last_sync': datetime.now(timezone.utc).isoformat(),
            'total_resources': sum(len(test_data.get(key, [])) for key in test_data.keys()),
            'sync_status': 'success',
            'resource_counts': {
                cr_type: len(crs) for cr_type, crs in test_data.items() if isinstance(crs, list)
            }
        }
        
        with open(os.path.join(hnp_path, "sync_status.json"), 'w') as f:
            json.dump(sync_status, f, indent=2)
        
        # Create last sync timestamp
        with open(os.path.join(hnp_path, "last_sync.timestamp"), 'w') as f:
            f.write(datetime.now(timezone.utc).isoformat())
    
    def commit_changes(self, message="Test changes from HNP testing framework"):
        """
        Commit changes to the test repository.
        
        Args:
            message: Commit message
            
        Returns:
            Commit SHA if successful, None otherwise
        """
        if not self.repo_path:
            return None
        
        try:
            # Configure git user for testing
            subprocess.run([
                'git', 'config', 'user.name', 'HNP Test Framework'
            ], cwd=self.repo_path, check=True)
            
            subprocess.run([
                'git', 'config', 'user.email', 'test@hedgehog.io'
            ], cwd=self.repo_path, check=True)
            
            # Add all changes
            subprocess.run([
                'git', 'add', '.'
            ], cwd=self.repo_path, check=True)
            
            # Commit changes
            result = subprocess.run([
                'git', 'commit', '-m', message
            ], cwd=self.repo_path, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Get commit SHA
                sha_result = subprocess.run([
                    'git', 'rev-parse', 'HEAD'
                ], cwd=self.repo_path, capture_output=True, text=True)
                
                return sha_result.stdout.strip() if sha_result.returncode == 0 else None
            
            return None
            
        except subprocess.CalledProcessError:
            return None
    
    def verify_file_exists(self, relative_path):
        """
        Verify that a file exists in the GitOps repository.
        
        Args:
            relative_path: Path relative to repository root
            
        Returns:
            True if file exists, False otherwise
        """
        if not self.repo_path:
            return False
        
        full_path = os.path.join(self.repo_path, relative_path)
        return os.path.exists(full_path)
    
    def read_yaml_file(self, relative_path):
        """
        Read and parse a YAML file from the repository.
        
        Args:
            relative_path: Path relative to repository root
            
        Returns:
            Parsed YAML content or None if error
        """
        if not self.repo_path:
            return None
        
        full_path = os.path.join(self.repo_path, relative_path)
        
        try:
            with open(full_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception:
            return None
    
    def write_yaml_file(self, relative_path, data):
        """
        Write data to a YAML file in the repository.
        
        Args:
            relative_path: Path relative to repository root
            data: Data to write as YAML
            
        Returns:
            True if successful, False otherwise
        """
        if not self.repo_path:
            return False
        
        full_path = os.path.join(self.repo_path, relative_path)
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
            
            return True
        except Exception:
            return False
    
    def delete_file(self, relative_path):
        """
        Delete a file from the repository.
        
        Args:
            relative_path: Path relative to repository root
            
        Returns:
            True if successful, False otherwise
        """
        if not self.repo_path:
            return False
        
        full_path = os.path.join(self.repo_path, relative_path)
        
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
            return True
        except Exception:
            return False
    
    def get_file_count(self, directory_path=""):
        """
        Get count of files in a directory.
        
        Args:
            directory_path: Directory path relative to repository root
            
        Returns:
            Number of files in directory
        """
        if not self.repo_path:
            return 0
        
        full_path = os.path.join(self.repo_path, directory_path)
        
        if not os.path.exists(full_path):
            return 0
        
        try:
            return len([f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))])
        except Exception:
            return 0
    
    def list_yaml_files(self, directory_path=""):
        """
        List all YAML files in a directory.
        
        Args:
            directory_path: Directory path relative to repository root
            
        Returns:
            List of YAML file names
        """
        if not self.repo_path:
            return []
        
        full_path = os.path.join(self.repo_path, directory_path)
        
        if not os.path.exists(full_path):
            return []
        
        try:
            return [f for f in os.listdir(full_path) 
                   if f.endswith(('.yaml', '.yml')) and os.path.isfile(os.path.join(full_path, f))]
        except Exception:
            return []
    
    def cleanup(self):
        """Clean up temporary test repository."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass  # Best effort cleanup
            finally:
                self.temp_dir = None
                self.repo_path = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()


class GitOpsTestValidator:
    """Validator for GitOps operations during testing."""
    
    @staticmethod
    def validate_gitops_structure(gitops_path):
        """
        Validate that GitOps directory has expected structure.
        
        Args:
            gitops_path: Path to GitOps directory
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'errors': [],
            'structure': {
                'raw_dir': False,
                'managed_dir': False,
                'hnp_dir': False,
                'sync_status': False
            }
        }
        
        # Check directory structure
        raw_path = os.path.join(gitops_path, "raw")
        managed_path = os.path.join(gitops_path, "managed")
        hnp_path = os.path.join(gitops_path, ".hnp")
        sync_status_path = os.path.join(hnp_path, "sync_status.json")
        
        results['structure']['raw_dir'] = os.path.exists(raw_path)
        results['structure']['managed_dir'] = os.path.exists(managed_path)
        results['structure']['hnp_dir'] = os.path.exists(hnp_path)
        results['structure']['sync_status'] = os.path.exists(sync_status_path)
        
        # Check for errors
        if not results['structure']['raw_dir']:
            results['errors'].append("Missing raw/ directory")
            results['valid'] = False
        
        if not results['structure']['managed_dir']:
            results['errors'].append("Missing managed/ directory")
            results['valid'] = False
        
        if not results['structure']['hnp_dir']:
            results['errors'].append("Missing .hnp/ directory")
            results['valid'] = False
        
        if not results['structure']['sync_status']:
            results['errors'].append("Missing sync_status.json file")
            results['valid'] = False
        
        return results
    
    @staticmethod
    def validate_cr_yaml(yaml_content, expected_kind=None):
        """
        Validate CR YAML content.
        
        Args:
            yaml_content: YAML content string
            expected_kind: Expected Kubernetes kind
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'errors': [],
            'parsed': None
        }
        
        try:
            # Parse YAML
            parsed = yaml.safe_load(yaml_content)
            results['parsed'] = parsed
            
            # Validate structure
            if not isinstance(parsed, dict):
                results['errors'].append("YAML must be a dictionary")
                results['valid'] = False
                return results
            
            # Check required fields
            required_fields = ['apiVersion', 'kind', 'metadata', 'spec']
            for field in required_fields:
                if field not in parsed:
                    results['errors'].append(f"Missing required field: {field}")
                    results['valid'] = False
            
            # Check metadata structure
            if 'metadata' in parsed:
                metadata = parsed['metadata']
                if not isinstance(metadata, dict):
                    results['errors'].append("metadata must be a dictionary")
                    results['valid'] = False
                elif 'name' not in metadata:
                    results['errors'].append("metadata.name is required")
                    results['valid'] = False
            
            # Check expected kind
            if expected_kind and parsed.get('kind') != expected_kind:
                results['errors'].append(f"Expected kind '{expected_kind}', got '{parsed.get('kind')}'")
                results['valid'] = False
            
        except yaml.YAMLError as e:
            results['errors'].append(f"Invalid YAML: {e}")
            results['valid'] = False
        except Exception as e:
            results['errors'].append(f"Validation error: {e}")
            results['valid'] = False
        
        return results