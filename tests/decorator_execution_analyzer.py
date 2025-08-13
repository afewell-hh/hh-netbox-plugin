#!/usr/bin/env python3
"""
Decorator Execution Order Analyzer

This script analyzes the exact execution order of Django decorators and view methods
to validate Phase 1 findings about @login_required executing before custom dispatch() methods.
"""

import os
import sys
import django
import logging
from typing import Dict, List
import inspect
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.test import RequestFactory, TestCase
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.generic import View

logger = logging.getLogger(__name__)

class DecoratorExecutionAnalyzer:
    """
    Analyzes decorator execution order in Django views to identify authentication issues
    """
    
    def __init__(self):
        self.factory = RequestFactory()
        self.test_results = {
            'timestamp': datetime.now().isoformat(),
            'analysis': {},
            'execution_traces': {},
            'findings': []
        }
        
        # Create test user
        self.authenticated_user = User.objects.filter(username='testuser').first()
        if not self.authenticated_user:
            self.authenticated_user = User.objects.create_user(
                username='testuser', 
                password='testpass',
                is_staff=True
            )
    
    def trace_method_execution(self, view_class, method_name: str = 'dispatch') -> Dict:
        """
        Trace method execution order by monkey patching methods
        """
        execution_trace = []
        original_methods = {}
        
        # Store original methods
        if hasattr(view_class, method_name):
            original_methods[method_name] = getattr(view_class, method_name)
        
        # Create tracing wrapper
        def create_tracer(method_name, original_method):
            def tracer(*args, **kwargs):
                execution_trace.append(f"{method_name}_start")
                try:
                    result = original_method(*args, **kwargs)
                    execution_trace.append(f"{method_name}_success")
                    return result
                except Exception as e:
                    execution_trace.append(f"{method_name}_exception: {str(e)}")
                    raise
            return tracer
        
        # Monkey patch methods
        for method_name, original_method in original_methods.items():
            setattr(view_class, method_name, create_tracer(method_name, original_method))
        
        return execution_trace, original_methods
    
    def analyze_sync_view_decorators(self) -> Dict:
        """
        Analyze the FabricSyncView decorator execution order
        """
        logger.info("🔍 Analyzing FabricSyncView decorator execution...")
        
        try:
            from netbox_hedgehog.views.sync_views import FabricSyncView
            
            # Create test requests
            ajax_request = self.factory.post('/test-sync/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            ajax_request.user = AnonymousUser()
            
            auth_ajax_request = self.factory.post('/test-sync/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            auth_ajax_request.user = self.authenticated_user
            
            # Test 1: Unauthenticated AJAX request
            logger.info("Testing unauthenticated AJAX request...")
            
            try:
                view_instance = FabricSyncView()
                response = view_instance.dispatch(ajax_request, pk=1)
                
                unauthenticated_result = {
                    'status_code': response.status_code,
                    'content_type': response.get('Content-Type', ''),
                    'is_json': response.get('Content-Type', '').startswith('application/json'),
                    'custom_dispatch_executed': True,  # If we get here, dispatch ran
                    'response_content': response.content.decode('utf-8')[:500] if hasattr(response, 'content') else str(response)
                }
                
                # Check if it's our custom authentication response
                try:
                    import json
                    if hasattr(response, 'content'):
                        content = json.loads(response.content)
                        unauthenticated_result['custom_auth_response'] = (
                            'error' in content and 
                            'Authentication required' in content.get('error', '')
                        )
                except:
                    unauthenticated_result['custom_auth_response'] = False
                    
            except Exception as e:
                unauthenticated_result = {
                    'error': str(e),
                    'custom_dispatch_executed': False,
                    'exception_type': type(e).__name__
                }
            
            # Test 2: Authenticated AJAX request
            logger.info("Testing authenticated AJAX request...")
            
            try:
                view_instance = FabricSyncView()
                auth_response = view_instance.dispatch(auth_ajax_request, pk=1)
                
                authenticated_result = {
                    'status_code': auth_response.status_code,
                    'content_type': auth_response.get('Content-Type', ''),
                    'custom_dispatch_executed': True,
                    'response_content': str(auth_response)[:500]
                }
                
            except Exception as e:
                authenticated_result = {
                    'error': str(e),
                    'custom_dispatch_executed': False,
                    'exception_type': type(e).__name__
                }
            
            # Analyze view class structure
            view_analysis = {
                'has_dispatch_method': hasattr(FabricSyncView, 'dispatch'),
                'dispatch_method_source': None,
                'decorators_applied': [],
                'method_resolution_order': [cls.__name__ for cls in FabricSyncView.__mro__]
            }
            
            # Get dispatch method source if available
            if hasattr(FabricSyncView, 'dispatch'):
                try:
                    view_analysis['dispatch_method_source'] = inspect.getsource(FabricSyncView.dispatch)
                except:
                    view_analysis['dispatch_method_source'] = "Source not available"
            
            # Check for decorators
            if hasattr(FabricSyncView, '__dict__'):
                for attr_name, attr_value in FabricSyncView.__dict__.items():
                    if hasattr(attr_value, '__name__') and 'decorator' in str(attr_value):
                        view_analysis['decorators_applied'].append(attr_name)
            
            return {
                'success': True,
                'view_class': 'FabricSyncView',
                'unauthenticated_test': unauthenticated_result,
                'authenticated_test': authenticated_result,
                'view_analysis': view_analysis
            }
            
        except ImportError as e:
            return {
                'success': False,
                'error': f'Could not import FabricSyncView: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Analysis failed: {str(e)}'
            }
    
    def test_decorator_bypass_hypothesis(self) -> Dict:
        """
        Test if removing @method_decorator(login_required) allows custom dispatch to work
        """
        logger.info("🧪 Testing decorator bypass hypothesis...")
        
        try:
            # Create a test view without login_required decorator
            class TestSyncViewWithoutDecorator(View):
                """Test sync view without @login_required decorator"""
                
                def dispatch(self, request, *args, **kwargs):
                    """Custom dispatch with authentication check"""
                    if not request.user.is_authenticated:
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'error': 'Authentication required. Please login to perform sync operations.',
                                'action': 'redirect_to_login',
                                'login_url': '/login/'
                            }, status=401)
                    return super().dispatch(request, *args, **kwargs)
                
                def post(self, request, pk):
                    """Dummy post method"""
                    return JsonResponse({'success': True, 'message': 'Test successful'})
            
            # Create a test view with login_required decorator
            @method_decorator(login_required, name='dispatch')
            class TestSyncViewWithDecorator(View):
                """Test sync view with @login_required decorator"""
                
                def dispatch(self, request, *args, **kwargs):
                    """Custom dispatch with authentication check"""
                    if not request.user.is_authenticated:
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'error': 'Authentication required. Please login to perform sync operations.',
                                'action': 'redirect_to_login',
                                'login_url': '/login/'
                            }, status=401)
                    return super().dispatch(request, *args, **kwargs)
                
                def post(self, request, pk):
                    """Dummy post method"""
                    return JsonResponse({'success': True, 'message': 'Test successful'})
            
            # Test both views with unauthenticated AJAX request
            ajax_request = self.factory.post('/test/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            ajax_request.user = AnonymousUser()
            
            # Test view without decorator
            try:
                view_without = TestSyncViewWithoutDecorator()
                response_without = view_without.dispatch(ajax_request, pk=1)
                
                without_decorator_result = {
                    'custom_dispatch_executed': True,
                    'status_code': response_without.status_code,
                    'is_custom_auth_response': response_without.status_code == 401,
                    'response_type': type(response_without).__name__
                }
                
                # Check response content
                if hasattr(response_without, 'content'):
                    import json
                    try:
                        content = json.loads(response_without.content)
                        without_decorator_result['custom_auth_message'] = content.get('error', '')
                    except:
                        without_decorator_result['response_content'] = response_without.content.decode('utf-8')[:200]
                
            except Exception as e:
                without_decorator_result = {
                    'custom_dispatch_executed': False,
                    'error': str(e),
                    'exception_type': type(e).__name__
                }
            
            # Test view with decorator
            try:
                view_with = TestSyncViewWithDecorator()
                response_with = view_with.dispatch(ajax_request, pk=1)
                
                with_decorator_result = {
                    'custom_dispatch_executed': True,
                    'status_code': response_with.status_code,
                    'response_type': type(response_with).__name__
                }
                
                # Check if it's a redirect (expected from @login_required)
                if hasattr(response_with, 'status_code'):
                    with_decorator_result['is_redirect'] = response_with.status_code == 302
                    if hasattr(response_with, 'url'):
                        with_decorator_result['redirect_url'] = response_with.url
                
            except Exception as e:
                with_decorator_result = {
                    'custom_dispatch_executed': False,
                    'error': str(e),
                    'exception_type': type(e).__name__
                }
            
            return {
                'success': True,
                'without_decorator': without_decorator_result,
                'with_decorator': with_decorator_result,
                'hypothesis_confirmed': (
                    without_decorator_result.get('custom_dispatch_executed', False) and
                    not with_decorator_result.get('custom_dispatch_executed', False)
                )
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Decorator bypass test failed: {str(e)}'
            }
    
    def analyze_mixin_inheritance(self) -> Dict:
        """
        Analyze if AjaxAuthenticationMixin affects decorator execution
        """
        logger.info("🔍 Analyzing mixin inheritance patterns...")
        
        try:
            from netbox_hedgehog.views.fabric_views import FabricSyncView as FabricViewsSyncView
            from netbox_hedgehog.mixins.auth import AjaxAuthenticationMixin
            
            # Analyze FabricSyncView from fabric_views.py (uses AjaxAuthenticationMixin)
            fabric_sync_analysis = {
                'class_name': 'FabricSyncView (fabric_views)',
                'uses_mixin': issubclass(FabricViewsSyncView, AjaxAuthenticationMixin),
                'has_custom_dispatch': hasattr(FabricViewsSyncView, 'dispatch'),
                'mro': [cls.__name__ for cls in FabricViewsSyncView.__mro__]
            }
            
            # Check mixin implementation
            mixin_analysis = {
                'mixin_has_dispatch': hasattr(AjaxAuthenticationMixin, 'dispatch'),
                'mixin_methods': [method for method in dir(AjaxAuthenticationMixin) if not method.startswith('_')]
            }
            
            # Test mixin behavior
            ajax_request = self.factory.post('/test/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            ajax_request.user = AnonymousUser()
            
            try:
                view_instance = FabricViewsSyncView()
                response = view_instance.dispatch(ajax_request, pk=1)
                
                mixin_test_result = {
                    'dispatch_executed': True,
                    'status_code': response.status_code,
                    'response_type': type(response).__name__,
                    'is_json_response': hasattr(response, 'content') and response.get('Content-Type', '').startswith('application/json')
                }
                
            except Exception as e:
                mixin_test_result = {
                    'dispatch_executed': False,
                    'error': str(e),
                    'exception_type': type(e).__name__
                }
            
            return {
                'success': True,
                'fabric_sync_analysis': fabric_sync_analysis,
                'mixin_analysis': mixin_analysis,
                'mixin_test_result': mixin_test_result
            }
            
        except ImportError as e:
            return {
                'success': False,
                'error': f'Could not import required classes: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Mixin analysis failed: {str(e)}'
            }
    
    def run_comprehensive_analysis(self) -> Dict:
        """
        Run comprehensive decorator execution analysis
        """
        logger.info("🚀 Starting comprehensive decorator execution analysis...")
        
        # Test 1: Analyze sync view decorators
        self.test_results['analysis']['sync_view_decorators'] = self.analyze_sync_view_decorators()
        
        # Test 2: Test decorator bypass hypothesis
        self.test_results['analysis']['decorator_bypass'] = self.test_decorator_bypass_hypothesis()
        
        # Test 3: Analyze mixin inheritance
        self.test_results['analysis']['mixin_inheritance'] = self.analyze_mixin_inheritance()
        
        # Generate findings
        self.generate_findings()
        
        return self.test_results
    
    def generate_findings(self):
        """Generate analysis findings and recommendations"""
        findings = []
        
        # Check sync view decorator analysis
        sync_analysis = self.test_results['analysis'].get('sync_view_decorators', {})
        if sync_analysis.get('success'):
            unauth_test = sync_analysis.get('unauthenticated_test', {})
            if unauth_test.get('custom_dispatch_executed'):
                findings.append("✅ Custom dispatch method executes for unauthenticated AJAX requests")
            else:
                findings.append("❌ Custom dispatch method blocked by decorators")
        
        # Check decorator bypass hypothesis
        bypass_analysis = self.test_results['analysis'].get('decorator_bypass', {})
        if bypass_analysis.get('success'):
            if bypass_analysis.get('hypothesis_confirmed'):
                findings.append("❌ CRITICAL: @login_required decorator prevents custom dispatch execution")
                findings.append("💡 RECOMMENDATION: Remove @method_decorator(login_required) and rely on custom authentication in dispatch()")
            else:
                findings.append("✅ Custom dispatch works regardless of decorator presence")
        
        # Check mixin analysis
        mixin_analysis = self.test_results['analysis'].get('mixin_inheritance', {})
        if mixin_analysis.get('success'):
            mixin_test = mixin_analysis.get('mixin_test_result', {})
            if mixin_test.get('dispatch_executed'):
                findings.append("✅ AjaxAuthenticationMixin allows custom dispatch execution")
            else:
                findings.append("❌ AjaxAuthenticationMixin may be interfering with dispatch execution")
        
        self.test_results['findings'] = findings
    
    def save_results(self, filename: str = None) -> str:
        """Save analysis results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"decorator_execution_analysis_{timestamp}.json"
        
        filepath = os.path.join('/tmp', filename)
        
        import json
        with open(filepath, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        logger.info(f"💾 Analysis results saved to: {filepath}")
        return filepath


def main():
    """Main function to run decorator execution analysis"""
    import json
    
    print("🔍 Decorator Execution Order Analysis")
    print("="*50)
    
    analyzer = DecoratorExecutionAnalyzer()
    results = analyzer.run_comprehensive_analysis()
    
    # Save results
    output_file = analyzer.save_results()
    
    # Print findings
    print("\nFINDINGS:")
    for finding in results.get('findings', []):
        print(f"  {finding}")
    
    print(f"\n📊 Full results saved to: {output_file}")
    
    # Print critical analysis
    print("\n" + "="*50)
    print("CRITICAL ANALYSIS SUMMARY")
    print("="*50)
    
    sync_analysis = results['analysis'].get('sync_view_decorators', {})
    if sync_analysis.get('success'):
        unauth = sync_analysis.get('unauthenticated_test', {})
        print(f"Custom dispatch execution: {unauth.get('custom_dispatch_executed', False)}")
        print(f"Custom auth response: {unauth.get('custom_auth_response', False)}")
    
    bypass_analysis = results['analysis'].get('decorator_bypass', {})
    if bypass_analysis.get('success'):
        print(f"Decorator bypass hypothesis confirmed: {bypass_analysis.get('hypothesis_confirmed', False)}")
    
    return results


if __name__ == '__main__':
    main()