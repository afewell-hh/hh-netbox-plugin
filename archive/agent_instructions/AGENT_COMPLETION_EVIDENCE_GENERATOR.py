#!/usr/bin/env python3
"""
Agent Completion Evidence Generator

This script generates comprehensive evidence that agents must provide to prove
their implementation of HNP fabric sync functionality actually works.

Agents MUST run this script and provide ALL output as evidence of completion.
Any missing evidence or failed tests will result in completion claim rejection.

Usage: python3 AGENT_COMPLETION_EVIDENCE_GENERATOR.py
"""

import os
import sys
import json
import subprocess
import requests
from datetime import datetime
from pathlib import Path
import tempfile
import yaml

class EvidenceGenerator:
    """Generates comprehensive evidence for fabric sync functionality"""
    
    def __init__(self):
        self.evidence = {
            'timestamp': datetime.now().isoformat(),
            'agent_id': os.environ.get('AGENT_ID', 'unknown'),
            'test_results': {},
            'validation_errors': [],
            'completion_status': 'INCOMPLETE'
        }
    
    def run_django_command(self, command, test_name):
        """Execute Django command and capture output"""
        cmd = [
            'sudo', 'docker', 'exec', 'netbox-docker-netbox-1',
            'python3', 'manage.py', 'shell', '-c', command
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                self.evidence['validation_errors'].append(
                    f"{test_name}: Django command failed: {result.stderr}"
                )
                return None
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            self.evidence['validation_errors'].append(f"{test_name}: Command timed out")
            return None
        except Exception as e:
            self.evidence['validation_errors'].append(f"{test_name}: Command failed: {str(e)}")
            return None
    
    def generate_configuration_evidence(self):
        """Generate evidence that configuration is fixed"""
        print("Generating Configuration Evidence...")
        
        command = """
from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.models.git_repository import GitRepository

fabric = HedgehogFabric.objects.get(id=19)
print('=== CONFIGURATION VALIDATION ===')
print(f'Fabric ID: {fabric.id}')
print(f'Fabric Name: {fabric.name}')
print(f'Git Repository FK: {fabric.git_repository}')
print(f'GitOps Directory: {fabric.gitops_directory}')

if fabric.git_repository:
    print(f'Linked Repository URL: {fabric.git_repository.url}')
    print(f'Repository Connection Status: {fabric.git_repository.connection_status}')
    print(f'Repository ID: {fabric.git_repository.id}')
    
    # Validate the expected values
    if fabric.git_repository.id == 6:
        print('VALIDATION: Git Repository FK CORRECT')
    else:
        print(f'VALIDATION: Git Repository FK WRONG (expected 6, got {fabric.git_repository.id})')
else:
    print('ERROR: No GitRepository linked')
    print('VALIDATION: Git Repository FK MISSING')

if fabric.gitops_directory == 'gitops/hedgehog/fabric-1/':
    print('VALIDATION: GitOps Directory CORRECT')
elif fabric.gitops_directory == '/':
    print('VALIDATION: GitOps Directory WRONG (still root /)')
else:
    print(f'VALIDATION: GitOps Directory WRONG (expected gitops/hedgehog/fabric-1/, got {fabric.gitops_directory})')
"""
        
        output = self.run_django_command(command, "Configuration Test")
        self.evidence['test_results']['configuration'] = {
            'command': command,
            'output': output,
            'passed': output and 'Git Repository FK CORRECT' in output and 'GitOps Directory CORRECT' in output
        }
        
        print("Configuration Evidence Generated")
        return output
    
    def generate_authentication_evidence(self):
        """Generate evidence that authentication works"""
        print("Generating Authentication Evidence...")
        
        command = """
from netbox_hedgehog.models.git_repository import GitRepository

repo = GitRepository.objects.get(id=6)
print('=== AUTHENTICATION VALIDATION ===')
print(f'Repository: {repo.name}')
print(f'URL: {repo.url}')
print(f'Has Credentials: {bool(repo.encrypted_credentials)}')

if repo.encrypted_credentials:
    print('Testing connection...')
    result = repo.test_connection()
    print(f'Connection Success: {result["success"]}')
    
    if result['success']:
        print(f'Authenticated: {result["authenticated"]}')
        print(f'Default Branch: {result["default_branch"]}')
        print(f'Current Commit: {result["current_commit"][:8]}')
        print('VALIDATION: Authentication PASSED')
    else:
        print(f'Error: {result["error"]}')
        print('VALIDATION: Authentication FAILED')
else:
    print('VALIDATION: No credentials configured')
"""
        
        output = self.run_django_command(command, "Authentication Test")
        self.evidence['test_results']['authentication'] = {
            'command': command,
            'output': output,
            'passed': output and 'VALIDATION: Authentication PASSED' in output
        }
        
        print("Authentication Evidence Generated")
        return output
    
    def generate_repository_content_evidence(self):
        """Generate evidence that repository content is accessible"""
        print("Generating Repository Content Evidence...")
        
        command = """
from netbox_hedgehog.models.git_repository import GitRepository
import tempfile
import yaml
from pathlib import Path

repo = GitRepository.objects.get(id=6)
print('=== REPOSITORY CONTENT VALIDATION ===')

with tempfile.TemporaryDirectory() as temp_dir:
    result = repo.clone_repository(temp_dir)
    
    if result['success']:
        print('Repository cloned successfully')
        print(f'Commit SHA: {result["commit_sha"][:8]}')
        
        gitops_path = Path(temp_dir) / 'gitops' / 'hedgehog' / 'fabric-1'
        
        if gitops_path.exists():
            print(f'GitOps directory found: gitops/hedgehog/fabric-1/')
            
            yaml_files = list(gitops_path.glob('*.yaml'))
            print(f'YAML files found: {len(yaml_files)}')
            
            crd_count = 0
            for yaml_file in yaml_files:
                file_size = yaml_file.stat().st_size
                print(f'  - {yaml_file.name} ({file_size} bytes)')
                
                try:
                    with open(yaml_file, 'r') as f:
                        docs = list(yaml.safe_load_all(f))
                        
                    for doc in docs:
                        if doc and isinstance(doc, dict) and 'kind' in doc and 'metadata' in doc:
                            kind = doc['kind']
                            name = doc['metadata']['name']
                            print(f'    {kind}: {name}')
                            
                            if kind in ['VPC', 'Connection', 'Switch', 'Server', 'External', 
                                       'ExternalAttachment', 'ExternalPeering', 'IPv4Namespace',
                                       'VPCAttachment', 'VPCPeering', 'SwitchGroup', 'VLANNamespace']:
                                crd_count += 1
                                
                except Exception as e:
                    print(f'    ERROR parsing: {e}')
            
            print(f'Total valid CRDs found: {crd_count}')
            
            if crd_count > 0:
                print('VALIDATION: Repository Content PASSED')
            else:
                print('VALIDATION: Repository Content FAILED (no valid CRDs)')
        else:
            print(f'ERROR: GitOps directory not found at gitops/hedgehog/fabric-1/')
            print('VALIDATION: Repository Content FAILED')
    else:
        print(f'ERROR: Clone failed: {result["error"]}')
        print('VALIDATION: Repository Content FAILED')
"""
        
        output = self.run_django_command(command, "Repository Content Test")
        self.evidence['test_results']['repository_content'] = {
            'command': command,
            'output': output,
            'passed': output and 'VALIDATION: Repository Content PASSED' in output
        }
        
        print("Repository Content Evidence Generated")
        return output
    
    def generate_sync_functionality_evidence(self):
        """Generate evidence that sync actually works"""
        print("Generating Sync Functionality Evidence...")
        
        command = """
from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.models.vpc_api import VPC
from netbox_hedgehog.models.wiring_api import Connection, Switch
from django.apps import apps

fabric = HedgehogFabric.objects.get(id=19)
print('=== SYNC FUNCTIONALITY VALIDATION ===')

# Record pre-sync state
vpc_before = VPC.objects.filter(fabric=fabric).count()
conn_before = Connection.objects.filter(fabric=fabric).count()
switch_before = Switch.objects.filter(fabric=fabric).count()
cached_before = fabric.cached_crd_count

print(f'PRE-SYNC STATE:')
print(f'  VPCs: {vpc_before}')
print(f'  Connections: {conn_before}')
print(f'  Switches: {switch_before}')
print(f'  Cached Count: {cached_before}')
print(f'  Last Sync: {fabric.last_git_sync}')

# Trigger sync
print('\\nTriggering sync...')
try:
    result = fabric.trigger_gitops_sync()
    print(f'Sync Success: {result["success"]}')
    
    if result['success']:
        print(f'Sync Message: {result["message"]}')
        print(f'Resources Created: {result.get("resources_created", 0)}')
        print(f'Resources Updated: {result.get("resources_updated", 0)}')
        
        if result.get('errors'):
            print(f'Sync Errors: {result["errors"]}')
        
        # Record post-sync state
        fabric.refresh_from_db()
        vpc_after = VPC.objects.filter(fabric=fabric).count()
        conn_after = Connection.objects.filter(fabric=fabric).count()
        switch_after = Switch.objects.filter(fabric=fabric).count()
        cached_after = fabric.cached_crd_count
        
        print(f'\\nPOST-SYNC STATE:')
        print(f'  VPCs: {vpc_after}')
        print(f'  Connections: {conn_after}')
        print(f'  Switches: {switch_after}')
        print(f'  Cached Count: {cached_after}')
        print(f'  Last Sync: {fabric.last_git_sync}')
        
        total_crds = vpc_after + conn_after + switch_after
        print(f'  Total CRDs: {total_crds}')
        
        # Validation checks
        if total_crds > 0:
            print('\\nVALIDATION: CRD Creation PASSED')
        else:
            print('\\nVALIDATION: CRD Creation FAILED (no CRDs created)')
        
        if cached_after > 0:
            print('VALIDATION: Cached Count Update PASSED')
        else:
            print('VALIDATION: Cached Count Update FAILED')
        
        if fabric.last_git_sync:
            print('VALIDATION: Last Sync Update PASSED')
        else:
            print('VALIDATION: Last Sync Update FAILED')
        
        # List some actual CRD names
        if vpc_after > 0:
            print('\\nCreated VPCs:')
            for vpc in VPC.objects.filter(fabric=fabric)[:5]:
                print(f'  - {vpc.name}')
        
        if conn_after > 0:
            print('Created Connections:')
            for conn in Connection.objects.filter(fabric=fabric)[:5]:
                print(f'  - {conn.name}')
        
        if switch_after > 0:
            print('Created Switches:')
            for switch in Switch.objects.filter(fabric=fabric)[:3]:
                print(f'  - {switch.name}')
        
        # Overall validation
        if total_crds > 0 and cached_after > 0 and fabric.last_git_sync:
            print('\\nVALIDATION: Sync Functionality PASSED')
        else:
            print('\\nVALIDATION: Sync Functionality FAILED')
    else:
        print(f'Sync Error: {result["error"]}')
        print('VALIDATION: Sync Functionality FAILED')
        
except Exception as e:
    print(f'Sync Exception: {str(e)}')
    print('VALIDATION: Sync Functionality FAILED')
"""
        
        output = self.run_django_command(command, "Sync Functionality Test")
        self.evidence['test_results']['sync_functionality'] = {
            'command': command,
            'output': output,
            'passed': output and 'VALIDATION: Sync Functionality PASSED' in output
        }
        
        print("Sync Functionality Evidence Generated")
        return output
    
    def generate_gui_evidence(self):
        """Generate evidence that GUI functionality works"""
        print("Generating GUI Evidence...")
        
        gui_results = {
            'fabric_page_accessible': False,
            'sync_button_exists': False,
            'fabric_name_displayed': False,
            'crd_counts_displayed': False,
            'last_sync_displayed': False
        }
        
        try:
            # Test fabric detail page access
            response = requests.get('http://localhost:8000/plugins/hedgehog/fabrics/19/', timeout=10)
            
            if response.status_code == 200:
                gui_results['fabric_page_accessible'] = True
                page_text = response.text
                
                # Check for fabric name
                if 'HCKC' in page_text:
                    gui_results['fabric_name_displayed'] = True
                
                # Check for sync button
                if 'Sync Now' in page_text or 'sync' in page_text.lower():
                    gui_results['sync_button_exists'] = True
                
                # Check for CRD counts (any non-zero numbers)
                if any(f'Total CRDs: {i}' in page_text for i in range(1, 100)):
                    gui_results['crd_counts_displayed'] = True
                elif 'VPCs:' in page_text or 'Connections:' in page_text:
                    gui_results['crd_counts_displayed'] = True
                
                # Check for last sync timestamp
                if 'Last Sync' in page_text or 'last_git_sync' in page_text:
                    gui_results['last_sync_displayed'] = True
            else:
                self.evidence['validation_errors'].append(
                    f"GUI Test: Fabric page returned HTTP {response.status_code}"
                )
        
        except requests.exceptions.ConnectionError:
            self.evidence['validation_errors'].append(
                "GUI Test: Cannot connect to NetBox at localhost:8000"
            )
        except Exception as e:
            self.evidence['validation_errors'].append(f"GUI Test: {str(e)}")
        
        gui_passed = all(gui_results.values())
        
        self.evidence['test_results']['gui_functionality'] = {
            'results': gui_results,
            'passed': gui_passed
        }
        
        print(f"GUI Evidence Generated - Passed: {gui_passed}")
        return gui_results
    
    def generate_comprehensive_evidence(self):
        """Generate all evidence required for completion validation"""
        print("=" * 70)
        print("HNP FABRIC SYNC COMPLETION EVIDENCE GENERATOR")
        print("=" * 70)
        print(f"Timestamp: {self.evidence['timestamp']}")
        print(f"Agent ID: {self.evidence['agent_id']}")
        print()
        
        # Generate all evidence
        config_output = self.generate_configuration_evidence()
        print()
        
        auth_output = self.generate_authentication_evidence()
        print()
        
        content_output = self.generate_repository_content_evidence()
        print()
        
        sync_output = self.generate_sync_functionality_evidence()
        print()
        
        gui_results = self.generate_gui_evidence()
        print()
        
        # Determine overall completion status
        all_tests_passed = all([
            self.evidence['test_results']['configuration']['passed'],
            self.evidence['test_results']['authentication']['passed'],
            self.evidence['test_results']['repository_content']['passed'],
            self.evidence['test_results']['sync_functionality']['passed'],
            self.evidence['test_results']['gui_functionality']['passed']
        ])
        
        if all_tests_passed and len(self.evidence['validation_errors']) == 0:
            self.evidence['completion_status'] = 'COMPLETE'
        else:
            self.evidence['completion_status'] = 'INCOMPLETE'
        
        # Generate summary report
        print("=" * 70)
        print("EVIDENCE SUMMARY")
        print("=" * 70)
        
        for test_name, test_data in self.evidence['test_results'].items():
            status = "✓ PASSED" if test_data['passed'] else "✗ FAILED"
            print(f"{test_name.upper()}: {status}")
        
        if self.evidence['validation_errors']:
            print("\\nVALIDATION ERRORS:")
            for error in self.evidence['validation_errors']:
                print(f"  - {error}")
        
        print(f"\\nOVERALL STATUS: {self.evidence['completion_status']}")
        
        if self.evidence['completion_status'] == 'COMPLETE':
            print("\\n🎉 ALL EVIDENCE GENERATED SUCCESSFULLY")
            print("   Agent may submit this evidence for completion validation")
        else:
            print("\\n⚠️  EVIDENCE GENERATION FAILED")
            print("   Agent MUST fix failing tests before claiming completion")
        
        # Save evidence to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        evidence_file = f"agent_completion_evidence_{timestamp}.json"
        
        with open(evidence_file, 'w') as f:
            json.dump(self.evidence, f, indent=2, default=str)
        
        print(f"\\nEvidence saved to: {evidence_file}")
        print("Submit this file as proof of completion")
        
        return self.evidence['completion_status'] == 'COMPLETE'

def main():
    """Main evidence generator"""
    generator = EvidenceGenerator()
    success = generator.generate_comprehensive_evidence()
    
    if success:
        print("\\n" + "=" * 70)
        print("COMPLETION EVIDENCE SUCCESSFULLY GENERATED")
        print("=" * 70)
        print("NEXT STEPS:")
        print("1. Submit the generated evidence file to QAPM")
        print("2. Provide screenshots of working GUI functionality")
        print("3. Demonstrate live sync workflow if requested")
        print("4. Answer any validation questions from QAPM")
        sys.exit(0)
    else:
        print("\\n" + "=" * 70)
        print("EVIDENCE GENERATION FAILED")
        print("=" * 70)
        print("REQUIRED ACTIONS:")
        print("1. Fix all failing tests identified above")
        print("2. Re-run this evidence generator")
        print("3. Do NOT claim completion until all tests pass")
        print("4. See AGENT_VALIDATION_PROTOCOL.md for requirements")
        sys.exit(1)

if __name__ == "__main__":
    main()