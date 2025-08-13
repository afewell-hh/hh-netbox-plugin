#!/usr/bin/env python3
"""
Simple Decorator Analysis - Static Analysis of View Code

Analyzes decorator usage patterns without requiring Django initialization.
"""

import os
import re
import ast
import json
from datetime import datetime
from typing import Dict, List, Optional

class SimpleDecoratorAnalysis:
    """
    Static analysis of decorator patterns in view files
    """
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'analysis': {},
            'findings': []
        }
    
    def analyze_view_file(self, file_path: str) -> Dict:
        """Analyze a specific view file for decorator patterns"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Parse the AST
            tree = ast.parse(content)
            
            # Find class definitions
            classes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = self.analyze_class_decorators(node, content)
                    classes.append(class_info)
            
            return {
                'file_path': file_path,
                'classes': classes,
                'raw_content_lines': len(content.split('\n'))
            }
            
        except Exception as e:
            return {
                'file_path': file_path,
                'error': str(e)
            }
    
    def analyze_class_decorators(self, class_node: ast.ClassDef, content: str) -> Dict:
        """Analyze decorator patterns in a class"""
        class_info = {
            'class_name': class_node.name,
            'decorators': [],
            'methods': [],
            'has_custom_dispatch': False,
            'dispatch_method': None
        }
        
        # Check class-level decorators
        for decorator in class_node.decorator_list:
            decorator_info = self.extract_decorator_info(decorator)
            class_info['decorators'].append(decorator_info)
        
        # Check methods
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                method_info = self.analyze_method(node, content)
                class_info['methods'].append(method_info)
                
                if node.name == 'dispatch':
                    class_info['has_custom_dispatch'] = True
                    class_info['dispatch_method'] = method_info
        
        return class_info
    
    def analyze_method(self, method_node: ast.FunctionDef, content: str) -> Dict:
        """Analyze a method for authentication patterns"""
        method_info = {
            'method_name': method_node.name,
            'decorators': [],
            'has_auth_check': False,
            'has_ajax_check': False,
            'returns_json_response': False,
            'line_number': method_node.lineno
        }
        
        # Check method decorators
        for decorator in method_node.decorator_list:
            decorator_info = self.extract_decorator_info(decorator)
            method_info['decorators'].append(decorator_info)
        
        # Get method source code
        lines = content.split('\n')
        method_start = method_node.lineno - 1
        method_end = method_start + 20  # Look at first 20 lines of method
        method_source = '\n'.join(lines[method_start:method_end])
        
        # Check for authentication patterns
        method_info['has_auth_check'] = (
            'request.user.is_authenticated' in method_source or
            'user.is_authenticated' in method_source
        )
        
        method_info['has_ajax_check'] = (
            'X-Requested-With' in method_source or
            'XMLHttpRequest' in method_source
        )
        
        method_info['returns_json_response'] = (
            'JsonResponse' in method_source or
            'return JsonResponse' in method_source
        )
        
        return method_info
    
    def extract_decorator_info(self, decorator_node) -> Dict:
        """Extract decorator information from AST node"""
        if isinstance(decorator_node, ast.Name):
            return {
                'type': 'simple',
                'name': decorator_node.id
            }
        elif isinstance(decorator_node, ast.Call):
            if isinstance(decorator_node.func, ast.Name):
                return {
                    'type': 'call',
                    'name': decorator_node.func.id,
                    'args': len(decorator_node.args)
                }
            elif isinstance(decorator_node.func, ast.Attribute):
                return {
                    'type': 'method_call',
                    'name': f"{decorator_node.func.value.id}.{decorator_node.func.attr}" if isinstance(decorator_node.func.value, ast.Name) else str(decorator_node.func.attr),
                    'args': len(decorator_node.args)
                }
        
        return {
            'type': 'unknown',
            'name': str(type(decorator_node).__name__)
        }
    
    def analyze_authentication_patterns(self) -> Dict:
        """Analyze authentication patterns across view files"""
        view_files = [
            '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/sync_views.py',
            '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/fabric_views.py'
        ]
        
        file_analyses = {}
        
        for file_path in view_files:
            if os.path.exists(file_path):
                file_analyses[file_path] = self.analyze_view_file(file_path)
        
        return file_analyses
    
    def identify_decorator_conflicts(self, file_analyses: Dict) -> List[Dict]:
        """Identify potential decorator conflicts"""
        conflicts = []
        
        for file_path, file_analysis in file_analyses.items():
            if 'classes' not in file_analysis:
                continue
                
            for class_info in file_analysis['classes']:
                # Check for @method_decorator(login_required) with custom dispatch
                has_login_decorator = any(
                    'method_decorator' in str(dec.get('name', '')) or 'login_required' in str(dec.get('name', ''))
                    for dec in class_info.get('decorators', [])
                )
                
                has_custom_dispatch = class_info.get('has_custom_dispatch', False)
                dispatch_has_auth_check = False
                
                if has_custom_dispatch and class_info.get('dispatch_method'):
                    dispatch_method = class_info['dispatch_method']
                    dispatch_has_auth_check = dispatch_method.get('has_auth_check', False)
                
                if has_login_decorator and has_custom_dispatch and dispatch_has_auth_check:
                    conflicts.append({
                        'file': file_path,
                        'class': class_info['class_name'],
                        'issue': 'Potential decorator conflict: @login_required may execute before custom dispatch authentication',
                        'severity': 'critical',
                        'details': {
                            'has_login_decorator': has_login_decorator,
                            'has_custom_dispatch': has_custom_dispatch,
                            'dispatch_has_auth_check': dispatch_has_auth_check
                        }
                    })
        
        return conflicts
    
    def run_analysis(self) -> Dict:
        """Run comprehensive decorator analysis"""
        # Analyze authentication patterns
        file_analyses = self.analyze_authentication_patterns()
        self.results['analysis']['files'] = file_analyses
        
        # Identify conflicts
        conflicts = self.identify_decorator_conflicts(file_analyses)
        self.results['analysis']['conflicts'] = conflicts
        
        # Generate findings
        self.generate_findings()
        
        return self.results
    
    def generate_findings(self):
        """Generate analysis findings"""
        findings = []
        
        # Check for conflicts
        conflicts = self.results['analysis'].get('conflicts', [])
        for conflict in conflicts:
            findings.append(f"❌ {conflict['issue']} in {conflict['class']}")
        
        # Analyze file patterns
        files = self.results['analysis'].get('files', {})
        for file_path, file_analysis in files.items():
            if 'classes' not in file_analysis:
                continue
                
            filename = os.path.basename(file_path)
            
            for class_info in file_analysis['classes']:
                class_name = class_info['class_name']
                
                # Check for authentication view classes
                if 'Sync' in class_name or 'Fabric' in class_name:
                    has_decorators = bool(class_info.get('decorators'))
                    has_custom_dispatch = class_info.get('has_custom_dispatch', False)
                    
                    if has_decorators and has_custom_dispatch:
                        findings.append(f"🔍 {class_name} in {filename}: Uses both decorators and custom dispatch")
                    
                    # Check dispatch method details
                    if has_custom_dispatch:
                        dispatch_method = class_info.get('dispatch_method', {})
                        has_auth_check = dispatch_method.get('has_auth_check', False)
                        has_ajax_check = dispatch_method.get('has_ajax_check', False)
                        returns_json = dispatch_method.get('returns_json_response', False)
                        
                        if has_auth_check and has_ajax_check and returns_json:
                            findings.append(f"✅ {class_name}: Custom dispatch properly handles AJAX authentication")
                        elif has_auth_check:
                            findings.append(f"⚠️ {class_name}: Custom dispatch has auth check but may not handle AJAX properly")
        
        # Add recommendations
        if any('decorator conflict' in finding.lower() for finding in findings):
            findings.append("💡 RECOMMENDATION: Remove @method_decorator(login_required) from views with custom dispatch authentication")
        
        if any('ajax authentication' in finding.lower() for finding in findings):
            findings.append("💡 RECOMMENDATION: Ensure AJAX requests include proper X-Requested-With header")
        
        self.results['findings'] = findings
    
    def save_results(self, filename: str = None) -> str:
        """Save analysis results"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"simple_decorator_analysis_{timestamp}.json"
        
        filepath = os.path.join('/tmp', filename)
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        return filepath


def main():
    """Main function"""
    print("🔍 Simple Decorator Analysis")
    print("="*50)
    
    analyzer = SimpleDecoratorAnalysis()
    results = analyzer.run_analysis()
    
    # Save results
    output_file = analyzer.save_results()
    
    # Print findings
    print("\nFINDINGS:")
    for finding in results.get('findings', []):
        print(f"  {finding}")
    
    # Print conflicts
    conflicts = results['analysis'].get('conflicts', [])
    if conflicts:
        print(f"\nCRITICAL CONFLICTS FOUND: {len(conflicts)}")
        for conflict in conflicts:
            print(f"  🚨 {conflict['class']}: {conflict['issue']}")
    
    print(f"\n📊 Full results saved to: {output_file}")
    
    return results


if __name__ == '__main__':
    main()