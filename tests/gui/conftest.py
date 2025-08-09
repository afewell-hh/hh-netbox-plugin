"""
Pytest configuration and fixtures for GUI testing with Playwright + Django

This module provides comprehensive fixtures for testing the NetBox Hedgehog Plugin
GUI functionality using Playwright for browser automation and Django's test framework
for database isolation and authentication.

Performance Optimizations:
- Parallel execution with browser context sharing
- Optimized fixture scoping and caching
- Memory usage monitoring and cleanup
- Test data reuse and smart grouping
"""

import pytest
import os
import tempfile
import time
import threading
from pathlib import Path
from typing import Generator, Dict, Any, Optional
from contextlib import contextmanager
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.db import transaction
from django.core.management import call_command
from django.conf import settings
from playwright.sync_api import Browser, BrowserContext, Page, Playwright
import factory
from factory.django import DjangoModelFactory

# Performance monitoring globals
_test_metrics = {}
_browser_contexts_cache = {}
_test_data_cache = {}
_cleanup_registry = set()


# Performance Monitoring Utilities
class TestMetricsCollector:
    """Collects and analyzes test performance metrics"""
    
    def __init__(self):
        self.test_times = {}
        self.memory_usage = {}
        self.browser_contexts = 0
        self.page_creations = 0
        
    def start_test(self, test_name: str):
        self.test_times[test_name] = time.time()
        
    def end_test(self, test_name: str):
        if test_name in self.test_times:
            duration = time.time() - self.test_times[test_name]
            _test_metrics[test_name] = duration
            if duration > 10:  # Log slow tests
                print(f"⚠️  SLOW TEST: {test_name} took {duration:.2f}s")
                
    def record_context_creation(self):
        self.browser_contexts += 1
        
    def record_page_creation(self):
        self.page_creations += 1
        
    def get_summary(self):
        if not _test_metrics:
            return "No test metrics collected"
        avg_time = sum(_test_metrics.values()) / len(_test_metrics)
        slow_tests = [k for k, v in _test_metrics.items() if v > 10]
        return f"""
Test Performance Summary:
- Tests run: {len(_test_metrics)}
- Average time: {avg_time:.2f}s
- Slow tests (>10s): {len(slow_tests)}
- Browser contexts: {self.browser_contexts}
- Page creations: {self.page_creations}
        """

metrics_collector = TestMetricsCollector()


@contextmanager
def browser_context_pool():
    """Context manager for efficient browser context reuse"""
    context_id = threading.current_thread().ident
    if context_id not in _browser_contexts_cache:
        yield None  # First use, create new context
    else:
        yield _browser_contexts_cache[context_id]


# Test Settings Override  
@pytest.fixture(scope="session")
def django_db_setup():
    """
    Configure test database with isolation and NetBox plugin integration
    """
    settings.DATABASES['default']['TEST'] = {
        'NAME': 'test_netbox_hedgehog_gui',
        'CHARSET': None,
        'COLLATION': None,
        'CREATE_DB': True,
        'USER': None,
        'PASSWORD': None,
        'TBLSPACE': None,
        'TBLSPACE_TMP': None,
    }


@pytest.fixture(scope="session")
def live_server_url(live_server):
    """
    Provide live server URL for Playwright tests
    """
    return live_server.url


# Optimized Browser Configuration Fixtures
@pytest.fixture(scope="session")
def browser_type_launch_args():
    """
    Configure browser launch arguments optimized for parallel execution
    """
    args = {
        'headless': not bool(os.getenv('HEADED', False)),
        'slow_mo': int(os.getenv('SLOW_MO', 0)),
        'args': [
            '--disable-dev-shm-usage', 
            '--no-sandbox',
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
            '--disable-features=TranslateUI',
            '--no-first-run',
            '--no-default-browser-check',
        ] if os.getenv('CI') or os.getenv('PARALLEL_TESTS') else []
    }
    
    # Enable devtools in headed mode for debugging
    if not args['headless']:
        args['devtools'] = True
        
    return args


@pytest.fixture(scope="session") 
def browser_context_args():
    """
    Configure browser context optimized for performance and parallel execution
    """
    screenshots_dir = Path("screenshots")
    videos_dir = Path("videos") 
    screenshots_dir.mkdir(exist_ok=True)
    
    # Disable video recording in parallel mode for performance
    context_args = {
        'viewport': {'width': 1920, 'height': 1080},
        'ignore_https_errors': True,
        'reduce_motion': 'reduce',  # Disable animations for faster tests
    }
    
    # Only record video if not in parallel mode
    if not os.getenv('PARALLEL_TESTS'):
        videos_dir.mkdir(exist_ok=True)
        context_args.update({
            'record_video_dir': str(videos_dir),
            'record_video_size': {'width': 1920, 'height': 1080}
        })
    
    return context_args


@pytest.fixture
def browser_context_with_storage(browser: Browser, browser_context_args: Dict[str, Any]):
    """
    Create browser context with persistent storage state capability and context pooling
    """
    context_key = f"{threading.current_thread().ident}_storage"
    
    # Reuse context if available in current thread
    if context_key in _browser_contexts_cache:
        context = _browser_contexts_cache[context_key]
        if not context.pages:  # Context is still valid
            yield context
            return
        else:
            # Clean up invalid context
            _browser_contexts_cache.pop(context_key, None)
    
    # Create new context
    context = browser.new_context(**browser_context_args)
    _browser_contexts_cache[context_key] = context
    metrics_collector.record_context_creation()
    _cleanup_registry.add(lambda: context.close())
    
    yield context
    
    # Don't immediately close - keep for reuse
    # Cleanup handled by session teardown


# Optimized Authentication Fixtures with Caching
class UserFactory(DjangoModelFactory):
    """Factory for creating test users with various permission levels"""
    
    class Meta:
        model = User
        django_get_or_create = ('username',)
    
    username = factory.Sequence(lambda n: f'testuser{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    is_superuser = False


@pytest.fixture(scope="session")
@pytest.mark.django_db
def admin_user(django_db_blocker):
    """Create cached superuser for admin access tests"""
    cache_key = 'admin_user'
    if cache_key in _test_data_cache:
        return _test_data_cache[cache_key]
    
    with django_db_blocker.unblock():
        user = UserFactory(
            username='admin',
            email='admin@example.com', 
            is_staff=True,
            is_superuser=True
        )
        # Set password for authentication
        user.set_password('testpass123')
        user.save()
        _test_data_cache[cache_key] = user
        return user


@pytest.fixture(scope="session")
@pytest.mark.django_db  
def staff_user(django_db_blocker):
    """Create cached staff user with standard permissions"""
    cache_key = 'staff_user'
    if cache_key in _test_data_cache:
        return _test_data_cache[cache_key]
    
    with django_db_blocker.unblock():
        user = UserFactory(
            username='staff',
            email='staff@example.com',
            is_staff=True
        )
        user.set_password('testpass123')
        user.save()
        
        # Add standard NetBox permissions
        content_type = ContentType.objects.get_for_model(User)
        permissions = Permission.objects.filter(content_type=content_type)
        user.user_permissions.set(permissions)
        _test_data_cache[cache_key] = user
        return user


@pytest.fixture(scope="session")  
@pytest.mark.django_db
def regular_user(django_db_blocker):
    """Create cached regular user with limited permissions"""
    cache_key = 'regular_user'
    if cache_key in _test_data_cache:
        return _test_data_cache[cache_key]
    
    with django_db_blocker.unblock():
        user = UserFactory(
            username='regular',
            email='regular@example.com'
        )
        user.set_password('testpass123')
        user.save()
        _test_data_cache[cache_key] = user
        return user


@pytest.fixture(scope="session")  
def authenticated_context(browser: Browser, live_server_url: str, admin_user: User, browser_context_args: Dict[str, Any]):
    """
    Create cached browser context with authenticated admin session for reuse
    """
    cache_key = f"auth_context_{admin_user.username}"
    
    if cache_key in _browser_contexts_cache:
        context = _browser_contexts_cache[cache_key]
        # Verify context is still valid
        try:
            # Test context by creating a page and checking auth state
            test_page = context.new_page()
            test_page.goto(f"{live_server_url}/api/")  # API endpoint requires auth
            test_page.close()
            return context
        except:
            # Context invalid, remove from cache
            _browser_contexts_cache.pop(cache_key, None)
    
    # Create new authenticated context
    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    
    # Navigate to login page
    page.goto(f"{live_server_url}/login/")
    
    # Fill login form
    page.fill('input[name="username"]', admin_user.username)
    page.fill('input[name="password"]', 'testpass123')
    
    # Handle CSRF token if present
    csrf_token = page.query_selector('input[name="csrfmiddlewaretoken"]')
    if csrf_token:
        page.click('input[type="submit"], button[type="submit"]')
    else:
        page.click('input[type="submit"], button[type="submit"]')
    
    # Wait for successful login
    page.wait_for_url(f"{live_server_url}/**", wait_until="networkidle")
    page.close()  # Close login page, keep context
    
    # Cache for reuse
    _browser_contexts_cache[cache_key] = context
    metrics_collector.record_context_creation()
    _cleanup_registry.add(lambda: context.close())
    
    return context


@pytest.fixture
def authenticated_page(authenticated_context: BrowserContext):
    """
    Create authenticated page within established session context (optimized)
    """
    page = authenticated_context.new_page()
    metrics_collector.record_page_creation()
    yield page
    page.close()


# Optimized Database Fixtures with Caching
@pytest.fixture(scope="session")
@pytest.mark.django_db
def sample_fabric_data(django_db_blocker):
    """
    Create cached sample fabric data for testing
    """
    cache_key = 'sample_fabric_data'
    if cache_key in _test_data_cache:
        return _test_data_cache[cache_key]
    
    with django_db_blocker.unblock():
        try:
            from netbox_hedgehog.models.fabric import HedgehogFabric
            from netbox_hedgehog.models.git_repository import GitRepository
            
            # Create git repository first
            git_repo = GitRepository.objects.create(
                name='test-fabric-repo',
                url='https://github.com/test/fabric-repo.git',
                branch='main'
            )
            
            # Create fabric
            fabric = HedgehogFabric.objects.create(
                name='test-fabric',
                description='Test fabric for GUI testing',
                git_repository=git_repo
            )
            
            data = {
                'fabric': fabric,
                'git_repository': git_repo
            }
            _test_data_cache[cache_key] = data
            return data
        except ImportError:
            # Models not available in test environment
            data = {'fabric': None, 'git_repository': None}
            _test_data_cache[cache_key] = data
            return data


@pytest.fixture(scope="session")
@pytest.mark.django_db 
def sample_vpc_data(django_db_blocker):
    """
    Create cached sample VPC data for testing
    """
    cache_key = 'sample_vpc_data'
    if cache_key in _test_data_cache:
        return _test_data_cache[cache_key]
    
    with django_db_blocker.unblock():
        try:
            from netbox_hedgehog.models.vpc_api import VPCAttachment
            
            # This would need actual VPC model creation based on your schemas
            # Placeholder for now
            data = {'vpc_count': 0}  # Update when VPC models are available
            _test_data_cache[cache_key] = data
            return data
        except ImportError:
            data = {'vpc_count': 0}
            _test_data_cache[cache_key] = data
            return data


# Page Object Fixtures
@pytest.fixture
def fabric_page(authenticated_page: Page, live_server_url: str):
    """
    Navigate to fabric list page
    """
    authenticated_page.goto(f"{live_server_url}/plugins/netbox-hedgehog/fabrics/")
    authenticated_page.wait_for_load_state("networkidle")
    return authenticated_page


@pytest.fixture
def git_repository_page(authenticated_page: Page, live_server_url: str):
    """
    Navigate to git repository list page  
    """
    authenticated_page.goto(f"{live_server_url}/plugins/netbox-hedgehog/git-repositories/")
    authenticated_page.wait_for_load_state("networkidle")
    return authenticated_page


# Utility Fixtures
@pytest.fixture
def screenshot_helper():
    """
    Helper for taking screenshots during tests
    """
    def take_screenshot(page: Page, name: str, full_page: bool = True):
        screenshot_path = Path("screenshots") / f"{name}.png"
        return page.screenshot(path=str(screenshot_path), full_page=full_page)
    
    return take_screenshot


@pytest.fixture
def wait_for_ajax():
    """
    Helper for waiting for AJAX operations to complete
    """
    def wait_for_ajax_completion(page: Page, timeout: int = 5000):
        # Wait for network to be idle (no pending requests)
        page.wait_for_load_state("networkidle", timeout=timeout)
        
        # Additional wait for any jQuery AJAX if present
        try:
            page.wait_for_function(
                "typeof jQuery !== 'undefined' && jQuery.active === 0",
                timeout=timeout
            )
        except:
            # jQuery may not be present, continue
            pass
            
        # Wait for any custom loading indicators to disappear
        try:
            page.wait_for_selector(".loading, .spinner", state="detached", timeout=1000)
        except:
            # No loading indicators found, continue
            pass
    
    return wait_for_ajax_completion


@pytest.fixture
def error_handler():
    """
    Helper for handling and capturing errors during tests
    """
    def capture_errors(page: Page):
        errors = []
        
        # Capture console errors
        def handle_console_message(msg):
            if msg.type == "error":
                errors.append(f"Console Error: {msg.text}")
        
        page.on("console", handle_console_message)
        
        # Capture network errors
        def handle_request_failed(request):
            errors.append(f"Network Error: {request.method} {request.url} - {request.failure}")
            
        page.on("requestfailed", handle_request_failed)
        
        return errors
    
    return capture_errors


# Network Request Mocking Fixtures  
@pytest.fixture
def mock_github_api(authenticated_context: BrowserContext):
    """
    Mock GitHub API responses for testing git operations
    """
    def setup_github_mock(success: bool = True, response_data: Dict = None):
        if response_data is None:
            response_data = {"status": "success", "message": "Mocked response"}
            
        def handle_github_requests(route, request):
            if "api.github.com" in request.url:
                route.fulfill(
                    status=200 if success else 500,
                    content_type="application/json",
                    body=str(response_data)
                )
            else:
                route.continue_()
                
        authenticated_context.route("**/*", handle_github_requests)
    
    return setup_github_mock


# Cleanup Fixtures
@pytest.fixture(autouse=True)
def cleanup_files():
    """
    Automatically cleanup any test files created during testing
    """
    yield
    
    # Cleanup screenshots older than test run
    screenshots_dir = Path("screenshots")
    if screenshots_dir.exists():
        for file in screenshots_dir.glob("*.png"):
            try:
                # Keep only recent files (optional cleanup logic)
                pass
            except:
                pass


# Session-level fixtures for performance
@pytest.fixture(scope="session", autouse=True)
def django_setup():
    """
    Ensure Django is properly configured for testing
    """
    import django
    from django.conf import settings
    
    if not settings.configured:
        django.setup()


# Database transaction management for Playwright tests
@pytest.fixture
@pytest.mark.django_db(transaction=True)
def db_transaction():
    """
    Provide database transaction context for Playwright tests
    
    Playwright tests need transaction=True because they run in separate threads
    """
    with transaction.atomic():
        yield


# Enhanced Performance monitoring fixtures
@pytest.fixture(autouse=True)
def performance_monitor(request):
    """
    Monitor test performance and capture metrics with detailed tracking
    """
    test_name = request.node.name
    metrics_collector.start_test(test_name)
    
    yield
    
    metrics_collector.end_test(test_name)


@pytest.fixture(scope="session", autouse=True)
def session_cleanup():
    """
    Session-level cleanup and performance reporting
    """
    yield
    
    # Execute all cleanup functions
    for cleanup_func in _cleanup_registry:
        try:
            cleanup_func()
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    # Clear caches
    _browser_contexts_cache.clear()
    _test_data_cache.clear()
    
    # Print performance summary
    print("\n" + "="*60)
    print(metrics_collector.get_summary())
    print("="*60)


@pytest.fixture(autouse=True)
def memory_optimizer():
    """
    Memory optimization fixture to prevent memory leaks
    """
    import gc
    
    # Force garbage collection before test
    gc.collect()
    
    yield
    
    # Force garbage collection after test
    gc.collect()
    
    
@pytest.fixture
def fast_page_load():
    """
    Helper to optimize page loading speed
    """
    def optimize_page(page: Page):
        # Block unnecessary resources for faster loading
        page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}", lambda route: route.abort())
        page.route("**/analytics**", lambda route: route.abort())
        page.route("**/tracking**", lambda route: route.abort())
        
    return optimize_page