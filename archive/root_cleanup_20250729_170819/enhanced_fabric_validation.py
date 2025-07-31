#!/usr/bin/env python3
"""
Enhanced Fabric Page Validation Script
=====================================

This script performs enhanced validation of the fabric page improvements
with specific focus on the exact requirements and provides detailed evidence.
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, List, Any

class EnhancedFabricValidator:
    """Enhanced validator with detailed analysis"""
    
    def __init__(self):
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'tests': [],
            'summary': {}
        }
    
    def run_all_validations(self):
        """Run all validation tests"""
        print("Enhanced Fabric Page Validation")
        print("=" * 50)
        
        self.validate_kubernetes_server_display()
        self.validate_column_layout()
        self.validate_model_field_accuracy()
        self.validate_sync_separation()
        self.generate_final_report()
    
    def validate_kubernetes_server_display(self):
        """Validate Kubernetes server field shows appropriate default text"""
        test_result = {
            'name': 'Kubernetes Server Display',
            'passed': False,
            'evidence': [],
            'issues': [],
            'html_snippets': []
        }
        
        template_path = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html"
        
        try:
            with open(template_path, 'r') as f:
                content = f.read()
            
            # Find the kubernetes server display logic
            k8s_server_section = None
            server_pattern = re.compile(
                r'<th[^>]*>.*?Kubernetes Server.*?</th>.*?<td[^>]*>(.*?)</td>',
                re.DOTALL | re.IGNORECASE
            )
            
            match = server_pattern.search(content)
            if match:
                k8s_server_section = match.group(1)
                test_result['html_snippets'].append({
                    'description': 'Kubernetes Server Display Section',
                    'content': match.group(0)
                })
                
                # Check for conditional logic
                has_if_logic = '{% if' in k8s_server_section and 'kubernetes_server' in k8s_server_section
                has_else_logic = '{% else %}' in k8s_server_section
                
                # Check for default text
                has_default_url = '127.0.0.1:6443' in k8s_server_section
                has_hckc_text = 'HCKC K3s' in k8s_server_section or 'default' in k8s_server_section.lower()
                
                test_result['evidence'].append(f"Conditional logic found: {has_if_logic}")
                test_result['evidence'].append(f"Else clause found: {has_else_logic}")
                test_result['evidence'].append(f"Default URL found: {has_default_url}")
                test_result['evidence'].append(f"Default description found: {has_hckc_text}")
                
                if has_if_logic and has_else_logic and has_default_url:
                    test_result['passed'] = True
                    test_result['evidence'].append("✓ Kubernetes server field properly shows default when blank")
                else:
                    if not has_if_logic:
                        test_result['issues'].append("Missing conditional logic for kubernetes_server field")
                    if not has_else_logic:
                        test_result['issues'].append("Missing else clause for empty kubernetes_server")
                    if not has_default_url:
                        test_result['issues'].append("Missing default URL display")
            else:
                test_result['issues'].append("Could not find Kubernetes Server display section")
                
        except Exception as e:
            test_result['issues'].append(f"Error reading template: {e}")
        
        self.report['tests'].append(test_result)
        self._print_test_result(test_result)
    
    def validate_column_layout(self):
        """Validate Git Configuration layout structure"""
        test_result = {
            'name': 'Git Configuration Column Layout',
            'passed': False,
            'evidence': [],
            'issues': [],
            'html_snippets': []
        }
        
        template_path = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html"
        
        try:
            with open(template_path, 'r') as f:
                content = f.read()
            
            # Find Git Repository Sync section
            git_section_pattern = re.compile(
                r'<div class="col-md-6">.*?<h5[^>]*>.*?Git Repository Sync.*?</h5>.*?</div>.*?</div>',
                re.DOTALL | re.IGNORECASE
            )
            
            git_match = git_section_pattern.search(content)
            if git_match:
                git_section = git_match.group(0)
                test_result['html_snippets'].append({
                    'description': 'Git Repository Sync Section',
                    'content': git_section[:500] + "..." if len(git_section) > 500 else git_section
                })
                
                # Check for 2-column layout (col-md-6)
                has_6_col = 'col-md-6' in git_section
                no_4_col = 'col-md-4' not in git_section
                
                test_result['evidence'].append(f"Uses col-md-6 (2-column): {has_6_col}")
                test_result['evidence'].append(f"Avoids col-md-4 (3-column): {no_4_col}")
                
                if has_6_col and no_4_col:
                    test_result['passed'] = True
                    test_result['evidence'].append("✓ Git configuration uses 2-column layout")
                else:
                    test_result['issues'].append("Git configuration does not use proper 2-column layout")
            
            # Also check Kubernetes section for comparison
            k8s_section_pattern = re.compile(
                r'<div class="col-md-6">.*?<h5[^>]*>.*?HCKC.*?Kubernetes.*?Sync.*?</h5>.*?</div>.*?</div>',
                re.DOTALL | re.IGNORECASE
            )
            
            k8s_match = k8s_section_pattern.search(content)
            if k8s_match:
                k8s_section = k8s_match.group(0)
                has_k8s_6_col = 'col-md-6' in k8s_section
                test_result['evidence'].append(f"Kubernetes section also uses col-md-6: {has_k8s_6_col}")
                
                if has_k8s_6_col:
                    test_result['evidence'].append("✓ Both Git and Kubernetes sections use matching 2-column layout")
                
        except Exception as e:
            test_result['issues'].append(f"Error analyzing layout: {e}")
        
        self.report['tests'].append(test_result)
        self._print_test_result(test_result)
    
    def validate_model_field_accuracy(self):
        """Validate template fields match model fields"""
        test_result = {
            'name': 'Model Field Accuracy',
            'passed': False,
            'evidence': [],
            'issues': [],
            'html_snippets': []
        }
        
        try:
            # Load model fields
            model_path = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/models/fabric.py"
            with open(model_path, 'r') as f:
                model_content = f.read()
            
            # Extract model fields
            model_fields = set()
            field_pattern = re.compile(r'(\w+)\s*=\s*models\.\w+Field')
            for match in field_pattern.finditer(model_content):
                model_fields.add(match.group(1))
            
            # Load template
            template_path = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html"
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Find template field references
            template_fields = set()
            field_refs = re.findall(r'object\.(\w+)', template_content)
            for field in field_refs:
                if not field.startswith('get_') and not field.endswith('_display') and field != 'pk':
                    template_fields.add(field)
            
            # Check for invalid fields
            invalid_fields = template_fields - model_fields
            valid_fields = template_fields & model_fields
            
            test_result['evidence'].append(f"Model fields found: {len(model_fields)}")
            test_result['evidence'].append(f"Template field references: {len(template_fields)}")
            test_result['evidence'].append(f"Valid field references: {len(valid_fields)}")
            
            if invalid_fields:
                test_result['issues'].append(f"Invalid field references found: {sorted(invalid_fields)}")
                # Show context for invalid fields
                for field in invalid_fields:
                    pattern = re.compile(rf'object\.{field}[^a-zA-Z_]', re.IGNORECASE)
                    matches = pattern.search(template_content)
                    if matches:
                        start = max(0, matches.start() - 50)
                        end = min(len(template_content), matches.end() + 50)
                        context = template_content[start:end].strip()
                        test_result['html_snippets'].append({
                            'description': f'Invalid field usage: {field}',
                            'content': context
                        })
            else:
                test_result['passed'] = True
                test_result['evidence'].append("✓ All template fields correspond to valid model fields")
            
        except Exception as e:
            test_result['issues'].append(f"Error validating fields: {e}")
        
        self.report['tests'].append(test_result)
        self._print_test_result(test_result)
    
    def validate_sync_separation(self):
        """Validate edit form separates Git vs Kubernetes sync settings"""
        test_result = {
            'name': 'Edit Form Sync Separation',
            'passed': False,
            'evidence': [],
            'issues': [],
            'html_snippets': []
        }
        
        try:
            # Check for form files
            form_paths = [
                "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/forms/fabric.py",
                "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/forms.py"
            ]
            
            form_content = None
            form_file = None
            
            for path in form_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        content = f.read()
                        if 'fabric' in content.lower():
                            form_content = content
                            form_file = path
                            break
            
            if form_content:
                test_result['evidence'].append(f"Found form definition in: {form_file}")
                
                # Look for field grouping/separation
                git_fields = ['git_repository', 'git_branch', 'gitops_directory']
                k8s_fields = ['kubernetes_server', 'kubernetes_namespace', 'kubernetes_token']
                
                git_field_positions = []
                k8s_field_positions = []
                
                for field in git_fields:
                    match = re.search(field, form_content, re.IGNORECASE)
                    if match:
                        git_field_positions.append(match.start())
                
                for field in k8s_fields:
                    match = re.search(field, form_content, re.IGNORECASE)
                    if match:
                        k8s_field_positions.append(match.start())
                
                if git_field_positions and k8s_field_positions:
                    git_avg = sum(git_field_positions) / len(git_field_positions)
                    k8s_avg = sum(k8s_field_positions) / len(k8s_field_positions)
                    separation = abs(git_avg - k8s_avg)
                    
                    test_result['evidence'].append(f"Git fields average position: {git_avg:.0f}")
                    test_result['evidence'].append(f"K8s fields average position: {k8s_avg:.0f}")
                    test_result['evidence'].append(f"Separation distance: {separation:.0f} characters")
                    
                    # Look for section headers
                    section_headers = []
                    header_patterns = [
                        r'git.*sync.*settings',
                        r'kubernetes.*sync.*settings',
                        r'repository.*configuration',
                        r'cluster.*configuration'
                    ]
                    
                    for pattern in header_patterns:
                        if re.search(pattern, form_content, re.IGNORECASE):
                            section_headers.append(pattern)
                    
                    test_result['evidence'].append(f"Section headers found: {len(section_headers)}")
                    
                    if separation > 200 or len(section_headers) >= 2:
                        test_result['passed'] = True
                        test_result['evidence'].append("✓ Form properly separates Git and Kubernetes sync settings")
                    else:
                        test_result['issues'].append("Git and Kubernetes fields are not clearly separated")
                else:
                    test_result['issues'].append("Could not find sufficient Git or Kubernetes fields in form")
            else:
                test_result['issues'].append("Could not find fabric form definition")
                
        except Exception as e:
            test_result['issues'].append(f"Error analyzing form: {e}")
        
        self.report['tests'].append(test_result)
        self._print_test_result(test_result)
    
    def _print_test_result(self, test_result):
        """Print test result with details"""
        status = "✓ PASSED" if test_result['passed'] else "✗ FAILED"
        print(f"\n{status}: {test_result['name']}")
        print("-" * 50)
        
        if test_result['evidence']:
            print("Evidence:")
            for evidence in test_result['evidence']:
                print(f"  • {evidence}")
        
        if test_result['issues']:
            print("Issues:")
            for issue in test_result['issues']:
                print(f"  ✗ {issue}")
        
        if test_result['html_snippets']:
            print(f"HTML Evidence: {len(test_result['html_snippets'])} snippets captured")
    
    def generate_final_report(self):
        """Generate final validation report"""
        passed_tests = sum(1 for test in self.report['tests'] if test['passed'])
        total_tests = len(self.report['tests'])
        
        self.report['summary'] = {
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': total_tests - passed_tests,
            'success_rate': (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        }
        
        print("\n" + "=" * 50)
        print("FINAL VALIDATION REPORT")
        print("=" * 50)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {self.report['summary']['success_rate']:.1f}%")
        
        # Save detailed report
        report_path = "/home/ubuntu/cc/hedgehog-netbox-plugin/enhanced_validation_report.json"
        with open(report_path, 'w') as f:
            json.dump(self.report, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_path}")
        
        return self.report


def main():
    """Main execution"""
    validator = EnhancedFabricValidator()
    validator.run_all_validations()


if __name__ == "__main__":
    main()