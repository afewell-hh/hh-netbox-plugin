#!/usr/bin/env python3
"""
GUI Integration Validation Script for Hedgehog NetBox Plugin
Tests actual Django template rendering and URL routing
"""

import os
import sys
import django
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
from urllib.parse import urljoin

# Setup Django environment
sys.path.append('/home/ubuntu/cc/hedgehog-netbox-plugin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

try:
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    sys.exit(1)

from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch
from django.contrib.auth.models import User
from django.core.management import call_command
from django.template import Template, Context, TemplateDoesNotExist
from django.template.loader import get_template
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)

class GUIIntegrationValidator:
    """Validates GUI integration with actual Django environment"""
    
    def __init__(self):
        self.client = Client()
        self.user = None
        self.results = []
        
    def setup_test_user(self):
        """Create test user for authenticated requests"""
        try:
            self.user = User.objects.create_user(
                username='gui_tester',
                password='test_password',
                is_staff=True,
                is_superuser=True
            )
            self.client.login(username='gui_tester', password='test_password')
            return True
        except Exception as e:
            logger.error(f"Failed to create test user: {e}")
            return False

    def validate_url_patterns(self) -> List[Dict[str, Any]]:
        """Validate all URL patterns are properly configured"""
        results = []
        
        # Core Hedgehog URLs to test
        test_urls = [
            ('netbox_hedgehog:overview', {}, 'Overview page'),
            ('netbox_hedgehog:fabric_list', {}, 'Fabric list page'),
            ('netbox_hedgehog:gitrepository_list', {}, 'Git repository list'),
            ('netbox_hedgehog:vpc_list', {}, 'VPC list page'),
            ('netbox_hedgehog:connection_list', {}, 'Connection list page'),
            ('netbox_hedgehog:switch_list', {}, 'Switch list page'),
            ('netbox_hedgehog:server_list', {}, 'Server list page'),
            ('netbox_hedgehog:external_list', {}, 'External list page'),
            ('netbox_hedgehog:ipv4namespace_list', {}, 'IPv4 Namespace list'),
            ('netbox_hedgehog:gitops-dashboard', {}, 'GitOps dashboard'),
            ('netbox_hedgehog:drift_dashboard', {}, 'Drift dashboard'),
            ('netbox_hedgehog:productivity-dashboard', {}, 'Productivity dashboard'),
        ]
        
        for url_name, kwargs, description in test_urls:
            try:
                url = reverse(f'plugins:{url_name}', kwargs=kwargs)
                results.append({
                    'test': f'URL_PATTERN_{url_name}',
                    'status': 'PASS',
                    'details': f'URL pattern resolved: {url}',
                    'url': url
                })
            except NoReverseMatch as e:
                results.append({
                    'test': f'URL_PATTERN_{url_name}',
                    'status': 'FAIL', 
                    'details': f'URL pattern not found: {e}',
                    'error': str(e)
                })
            except Exception as e:
                results.append({
                    'test': f'URL_PATTERN_{url_name}',
                    'status': 'ERROR',
                    'details': f'Unexpected error: {e}',
                    'error': str(e)
                })
        
        return results

    def validate_template_rendering(self) -> List[Dict[str, Any]]:
        """Test template rendering with actual context"""
        results = []
        
        # Templates to test
        templates = [
            ('netbox_hedgehog/base.html', 'Base template'),
            ('netbox_hedgehog/overview.html', 'Overview template'),
            ('netbox_hedgehog/fabric_list.html', 'Fabric list template'),
            ('netbox_hedgehog/vpc_list.html', 'VPC list template'),
            ('netbox_hedgehog/gitops_dashboard.html', 'GitOps dashboard'),
            ('netbox_hedgehog/drift_detection_dashboard.html', 'Drift dashboard'),
            ('netbox_hedgehog/productivity_dashboard.html', 'Productivity dashboard'),
        ]
        
        for template_name, description in templates:
            try:
                template = get_template(template_name)
                
                # Test basic rendering with minimal context
                context = Context({
                    'user': self.user,
                    'request': type('obj', (object,), {
                        'user': self.user,
                        'META': {},
                        'GET': {},
                        'method': 'GET'
                    })(),
                    'title': f'Test {description}',
                })
                
                rendered = template.render(context)
                
                results.append({
                    'test': f'TEMPLATE_RENDER_{template_name.replace("/", "_")}',
                    'status': 'PASS',
                    'details': f'Template rendered successfully ({len(rendered)} chars)',
                    'template': template_name
                })
                
            except TemplateDoesNotExist as e:
                results.append({
                    'test': f'TEMPLATE_RENDER_{template_name.replace("/", "_")}',
                    'status': 'FAIL',
                    'details': f'Template not found: {template_name}',
                    'error': str(e)
                })
            except Exception as e:
                results.append({
                    'test': f'TEMPLATE_RENDER_{template_name.replace("/", "_")}',
                    'status': 'ERROR',
                    'details': f'Template rendering failed: {e}',
                    'error': str(e)
                })
        
        return results

    def validate_view_responses(self) -> List[Dict[str, Any]]:
        """Test actual HTTP responses from views"""
        results = []
        
        # URLs to test with HTTP requests
        test_urls = [
            ('/plugins/netbox_hedgehog/', 'Overview page'),
            ('/plugins/netbox_hedgehog/fabrics/', 'Fabric list'),
            ('/plugins/netbox_hedgehog/vpcs/', 'VPC list'),
            ('/plugins/netbox_hedgehog/connections/', 'Connection list'),
            ('/plugins/netbox_hedgehog/switches/', 'Switch list'),
            ('/plugins/netbox_hedgehog/servers/', 'Server list'),
        ]
        
        for url_path, description in test_urls:
            try:
                response = self.client.get(url_path, follow=True)
                
                if response.status_code == 200:
                    results.append({
                        'test': f'VIEW_RESPONSE_{url_path.replace("/", "_")}',
                        'status': 'PASS',
                        'details': f'View returned 200 OK ({len(response.content)} bytes)',
                        'url': url_path,
                        'status_code': response.status_code
                    })
                elif response.status_code in [301, 302]:
                    results.append({
                        'test': f'VIEW_RESPONSE_{url_path.replace("/", "_")}',
                        'status': 'WARNING',
                        'details': f'View returned redirect ({response.status_code})',
                        'url': url_path,
                        'status_code': response.status_code
                    })
                else:
                    results.append({
                        'test': f'VIEW_RESPONSE_{url_path.replace("/", "_")}',
                        'status': 'FAIL',
                        'details': f'View returned {response.status_code}',
                        'url': url_path,
                        'status_code': response.status_code
                    })
                    
            except Exception as e:
                results.append({
                    'test': f'VIEW_RESPONSE_{url_path.replace("/", "_")}',
                    'status': 'ERROR',
                    'details': f'Request failed: {e}',
                    'error': str(e),
                    'url': url_path
                })
        
        return results

    def validate_static_assets(self) -> List[Dict[str, Any]]:
        """Validate static assets are accessible"""
        results = []
        
        static_assets = [
            ('/static/netbox_hedgehog/css/hedgehog.css', 'Main CSS file'),
            ('/static/netbox_hedgehog/css/gitops-dashboard.css', 'GitOps CSS'),
            ('/static/netbox_hedgehog/js/hedgehog.js', 'Main JavaScript'),
            ('/static/netbox_hedgehog/js/gitops-dashboard.js', 'GitOps JavaScript'),
        ]
        
        for asset_path, description in static_assets:
            try:
                response = self.client.get(asset_path)
                
                if response.status_code == 200:
                    results.append({
                        'test': f'STATIC_ASSET_{asset_path.split("/")[-1]}',
                        'status': 'PASS',
                        'details': f'Asset accessible ({len(response.content)} bytes)',
                        'asset_path': asset_path
                    })
                else:
                    results.append({
                        'test': f'STATIC_ASSET_{asset_path.split("/")[-1]}',
                        'status': 'FAIL',
                        'details': f'Asset returned {response.status_code}',
                        'asset_path': asset_path,
                        'status_code': response.status_code
                    })
                    
            except Exception as e:
                results.append({
                    'test': f'STATIC_ASSET_{asset_path.split("/")[-1]}',
                    'status': 'ERROR',
                    'details': f'Asset request failed: {e}',
                    'error': str(e),
                    'asset_path': asset_path
                })
        
        return results

    def validate_model_integration(self) -> List[Dict[str, Any]]:
        """Validate model integration with GUI"""
        results = []
        
        try:
            # Test model imports
            from netbox_hedgehog.models import HedgehogFabric, GitRepository
            from netbox_hedgehog.models.vpc_api import VPC, External, IPv4Namespace
            from netbox_hedgehog.models.wiring_api import Connection, Switch, Server
            
            results.append({
                'test': 'MODEL_IMPORTS',
                'status': 'PASS',
                'details': 'All model imports successful'
            })
            
            # Test model queries
            fabric_count = HedgehogFabric.objects.count()
            results.append({
                'test': 'MODEL_QUERY_FABRIC',
                'status': 'PASS',
                'details': f'Fabric query successful ({fabric_count} fabrics)'
            })
            
            vpc_count = VPC.objects.count()
            results.append({
                'test': 'MODEL_QUERY_VPC',
                'status': 'PASS',
                'details': f'VPC query successful ({vpc_count} VPCs)'
            })
            
        except Exception as e:
            results.append({
                'test': 'MODEL_INTEGRATION',
                'status': 'FAIL',
                'details': f'Model integration failed: {e}',
                'error': str(e)
            })
        
        return results

    def validate_javascript_integration(self) -> List[Dict[str, Any]]:
        """Validate JavaScript integration in templates"""
        results = []
        
        # Check for JavaScript includes in templates
        js_files = [
            '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/static/netbox_hedgehog/js/hedgehog.js',
            '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/static/netbox_hedgehog/js/gitops-dashboard.js',
            '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/static/netbox_hedgehog/js/sync-handler.js',
        ]
        
        for js_file in js_files:
            try:
                if Path(js_file).exists():
                    with open(js_file, 'r') as f:
                        content = f.read()
                    
                    results.append({
                        'test': f'JAVASCRIPT_{Path(js_file).name}',
                        'status': 'PASS',
                        'details': f'JavaScript file exists ({len(content)} chars)',
                        'file_path': js_file
                    })
                else:
                    results.append({
                        'test': f'JAVASCRIPT_{Path(js_file).name}',
                        'status': 'FAIL',
                        'details': 'JavaScript file not found',
                        'file_path': js_file
                    })
                    
            except Exception as e:
                results.append({
                    'test': f'JAVASCRIPT_{Path(js_file).name}',
                    'status': 'ERROR',
                    'details': f'JavaScript validation failed: {e}',
                    'error': str(e)
                })
        
        return results

    def validate_database_schema(self) -> List[Dict[str, Any]]:
        """Validate database schema for GUI models"""
        results = []
        
        try:
            # Check if tables exist
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE 'netbox_hedgehog_%'
                """)
                tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = [
                'netbox_hedgehog_hedgehogfabric',
                'netbox_hedgehog_gitrepository',
                'netbox_hedgehog_vpc',
                'netbox_hedgehog_connection',
                'netbox_hedgehog_switch',
            ]
            
            for table in expected_tables:
                if table in tables:
                    results.append({
                        'test': f'DATABASE_TABLE_{table}',
                        'status': 'PASS',
                        'details': f'Database table exists: {table}'
                    })
                else:
                    results.append({
                        'test': f'DATABASE_TABLE_{table}',
                        'status': 'FAIL',
                        'details': f'Database table missing: {table}'
                    })
            
        except Exception as e:
            results.append({
                'test': 'DATABASE_SCHEMA',
                'status': 'ERROR',
                'details': f'Database schema validation failed: {e}',
                'error': str(e)
            })
        
        return results

    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive GUI integration validation"""
        print("🔍 Starting GUI Integration Validation")
        print("=" * 60)
        
        # Setup test environment
        if not self.setup_test_user():
            return {'error': 'Failed to setup test environment'}
        
        all_results = []
        
        # Run validation tests
        print("📋 Validating URL patterns...")
        all_results.extend(self.validate_url_patterns())
        
        print("🎨 Validating template rendering...")
        all_results.extend(self.validate_template_rendering())
        
        print("🌐 Validating view responses...")
        all_results.extend(self.validate_view_responses())
        
        print("🎯 Validating static assets...")
        all_results.extend(self.validate_static_assets())
        
        print("🗄️ Validating model integration...")
        all_results.extend(self.validate_model_integration())
        
        print("⚡ Validating JavaScript integration...")
        all_results.extend(self.validate_javascript_integration())
        
        print("💾 Validating database schema...")
        all_results.extend(self.validate_database_schema())
        
        # Calculate statistics
        total_tests = len(all_results)
        passed_tests = len([r for r in all_results if r['status'] == 'PASS'])
        failed_tests = len([r for r in all_results if r['status'] == 'FAIL'])
        error_tests = len([r for r in all_results if r['status'] == 'ERROR'])
        warning_tests = len([r for r in all_results if r['status'] == 'WARNING'])
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Generate report
        report = {
            'validation_summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'errors': error_tests,
                'warnings': warning_tests,
                'success_rate': round(success_rate, 2)
            },
            'gui_integration_status': 'PASS' if failed_tests == 0 and error_tests == 0 else 'FAIL',
            'production_ready': failed_tests == 0 and error_tests == 0 and success_rate >= 90,
            'critical_issues': [r for r in all_results if r['status'] in ['FAIL', 'ERROR']],
            'detailed_results': all_results,
            'recommendations': self._generate_recommendations(all_results, success_rate)
        }
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 GUI INTEGRATION VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"🚨 Errors: {error_tests}")
        print(f"⚠️ Warnings: {warning_tests}")
        print(f"📈 Success Rate: {success_rate:.2f}%")
        print(f"🎯 Integration Status: {report['gui_integration_status']}")
        print(f"🚀 Production Ready: {'YES' if report['production_ready'] else 'NO'}")
        
        if report['critical_issues']:
            print(f"\n🚨 Critical Issues ({len(report['critical_issues'])}):")
            for issue in report['critical_issues'][:5]:  # Show first 5
                print(f"   - {issue['test']}: {issue['details']}")
        
        return report

    def _generate_recommendations(self, results: List[Dict], success_rate: float) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        # Count issues by type
        url_issues = len([r for r in results if 'URL_PATTERN' in r['test'] and r['status'] != 'PASS'])
        template_issues = len([r for r in results if 'TEMPLATE' in r['test'] and r['status'] != 'PASS'])
        view_issues = len([r for r in results if 'VIEW_RESPONSE' in r['test'] and r['status'] != 'PASS'])
        static_issues = len([r for r in results if 'STATIC_ASSET' in r['test'] and r['status'] != 'PASS'])
        
        if url_issues > 0:
            recommendations.append(f"Fix {url_issues} URL pattern issues - critical for navigation")
        
        if template_issues > 0:
            recommendations.append(f"Resolve {template_issues} template rendering issues")
        
        if view_issues > 0:
            recommendations.append(f"Address {view_issues} view response issues")
        
        if static_issues > 0:
            recommendations.append(f"Fix {static_issues} static asset issues - affects UI styling")
        
        if success_rate >= 90:
            recommendations.append("GUI integration is solid - ready for comprehensive testing")
        elif success_rate >= 70:
            recommendations.append("GUI integration is mostly functional - address remaining issues")
        else:
            recommendations.append("GUI integration needs significant work before production")
        
        return recommendations

def main():
    """Main validation entry point"""
    validator = GUIIntegrationValidator()
    report = validator.run_comprehensive_validation()
    
    # Save report
    import json
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"/home/ubuntu/cc/hedgehog-netbox-plugin/tests/gui_integration_report_{timestamp}.json"
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    # Exit with appropriate code
    if report['production_ready']:
        print("🎉 GUI integration validation passed - ready for comprehensive testing!")
        sys.exit(0)
    else:
        print("⚠️ GUI integration validation failed - issues need resolution")
        sys.exit(1)

if __name__ == "__main__":
    main()