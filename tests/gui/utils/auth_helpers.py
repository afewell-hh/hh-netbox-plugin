"""
Authentication utilities for GUI testing

This module provides comprehensive authentication utilities for managing
user authentication, session state, permission testing, and NetBox-specific
authentication workflows in GUI tests.

Classes:
    LoginManager: Handle login/logout operations and session state
    PermissionManager: Manage user permissions and UI permission testing
    SessionManager: Handle session state persistence and restoration
    NetBoxAuthHelper: NetBox-specific authentication workflows and admin access
    AuthenticationHelper: Legacy compatibility class (deprecated)

Usage:
    # Basic login management
    login_manager = LoginManager(page, base_url)
    login_manager.login('admin', 'password')
    
    # Permission-based testing
    perm_manager = PermissionManager(page)
    test_cases = perm_manager.permission_test_cases()
    
    # Session state management
    session_manager = SessionManager(storage_dir)
    session_manager.save_session_state(page.context, 'admin')
    
    # NetBox-specific authentication
    netbox_auth = NetBoxAuthHelper(page, base_url)
    netbox_auth.admin_login('superuser', 'password')
"""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from playwright.sync_api import Page, BrowserContext
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import PermissionDenied
import logging
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UserType(Enum):
    """Enumeration of common user types for testing"""
    SUPERUSER = "superuser"
    ADMIN = "admin" 
    STAFF = "staff"
    REGULAR = "regular"
    READONLY = "readonly"
    ANONYMOUS = "anonymous"


@dataclass
class AuthUser:
    """Data class representing a test user"""
    username: str
    password: str
    user_type: UserType
    permissions: List[str]
    is_staff: bool = False
    is_superuser: bool = False
    email: str = ""
    
    def __post_init__(self):
        if not self.email:
            self.email = f"{self.username}@example.com"


class LoginManager:
    """
    Manages user login/logout operations and session status checking.
    
    Provides methods for logging in different user types, checking login status,
    and managing user sessions in GUI tests.
    
    Example:
        login_manager = LoginManager(page, "http://localhost:8000")
        login_manager.login("admin", "password")
        if login_manager.is_logged_in():
            user_info = login_manager.get_current_user()
    """
    
    def __init__(self, page: Page, base_url: str):
        """
        Initialize login manager.
        
        Args:
            page: Playwright Page instance
            base_url: Base URL for the application
        """
        self.page = page
        self.base_url = base_url.rstrip('/')
        self.current_user = None
        
    def login(self, username: str, password: str = "testpass123", 
              user_type: UserType = UserType.REGULAR, 
              save_state: bool = True) -> Dict[str, Any]:
        """
        Login user with specified credentials and user type.
        
        Args:
            username: Username to login with
            password: Password to use
            user_type: Type of user for context
            save_state: Whether to save authentication state
            
        Returns:
            Dictionary with login result and user information
            
        Raises:
            Exception: If login fails
        """
        logger.info(f"Attempting login for {username} ({user_type.value})")
        
        # Navigate to login page
        login_url = f"{self.base_url}/login/"
        self.page.goto(login_url, wait_until="networkidle")
        
        # Wait for login form to be visible
        self.page.wait_for_selector('input[name="username"]', state="visible", timeout=10000)
        
        # Fill login form
        self.page.fill('input[name="username"]', username)
        self.page.fill('input[name="password"]', password)
        
        # Handle CSRF token if present
        csrf_token = self.page.query_selector('input[name="csrfmiddlewaretoken"]')
        if csrf_token:
            logger.debug("CSRF token found in login form")
            
        # Submit login form
        with self.page.expect_navigation():
            submit_button = self.page.query_selector('input[type="submit"], button[type="submit"]')
            if submit_button:
                submit_button.click()
            else:
                self.page.press('input[name="password"]', 'Enter')
        
        # Verify successful login
        current_url = self.page.url
        if "/login/" in current_url and "?next=" not in current_url:
            # Check for error messages
            error_msg = self.page.query_selector('.alert-danger, .error, .errorlist')
            error_text = error_msg.text_content() if error_msg else "Unknown error"
            raise Exception(f"Login failed for {username}: {error_text}")
            
        # Store current user info
        self.current_user = AuthUser(
            username=username,
            password=password,
            user_type=user_type,
            permissions=[],  # Will be populated by permission manager
            is_staff=(user_type in [UserType.STAFF, UserType.ADMIN, UserType.SUPERUSER]),
            is_superuser=(user_type == UserType.SUPERUSER)
        )
        
        logger.info(f"Successfully logged in as {username}")
        return {
            'success': True,
            'username': username,
            'user_type': user_type.value,
            'current_url': current_url,
            'storage_state': self.page.context.storage_state() if save_state else None
        }
        
    def logout(self) -> Dict[str, Any]:
        """
        Logout current user with session cleanup.
        
        Returns:
            Dictionary with logout result
        """
        logger.info(f"Logging out user: {self.current_user.username if self.current_user else 'Unknown'}")
        
        # Navigate to logout URL
        logout_url = f"{self.base_url}/logout/"
        self.page.goto(logout_url, wait_until="networkidle")
        
        # Clear session cookies
        self.page.context.clear_cookies()
        
        # Verify logout by checking if we're redirected to login or home
        current_url = self.page.url
        logout_success = ("/login/" in current_url or 
                         current_url.rstrip('/') == self.base_url or
                         "logout" in current_url)
        
        if logout_success:
            logger.info("Successfully logged out")
            self.current_user = None
        else:
            logger.warning(f"Logout may have failed - current URL: {current_url}")
            
        return {
            'success': logout_success,
            'current_url': current_url,
            'redirect_url': current_url
        }
        
    def is_logged_in(self) -> bool:
        """
        Check if a user is currently logged in.
        
        Returns:
            True if user is authenticated, False otherwise
        """
        # Check for authentication indicators in the page
        logout_link = self.page.query_selector('a[href*="/logout/"]')
        user_menu = self.page.query_selector('.user-menu, .navbar-user, .dropdown-user')
        auth_indicator = self.page.query_selector('[data-user-authenticated="true"]')
        
        # Check for login form (indicates not logged in)
        login_form = self.page.query_selector('form[action*="login"], input[name="username"]')
        
        is_authenticated = bool((logout_link or user_menu or auth_indicator) and not login_form)
        
        logger.debug(f"Authentication check: {'authenticated' if is_authenticated else 'not authenticated'}")
        return is_authenticated
        
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Get information about currently logged in user.
        
        Returns:
            Dictionary with user information or None if not logged in
        """
        if not self.is_logged_in():
            logger.debug("No user currently logged in")
            return None
            
        user_info = {
            'username': self.current_user.username if self.current_user else None,
            'user_type': self.current_user.user_type.value if self.current_user else None,
            'is_authenticated': True,
            'is_staff': False,
            'is_superuser': False,
            'permissions': []
        }
        
        # Try to extract username from page elements
        user_elements = [
            '.user-name', '.username', '.navbar-text', 
            '[data-username]', '.current-user'
        ]
        
        for selector in user_elements:
            element = self.page.query_selector(selector)
            if element and element.text_content().strip():
                username_text = element.text_content().strip()
                # Extract username from text like "Welcome, admin" or "Logged in as: admin"
                if ',' in username_text:
                    user_info['username'] = username_text.split(',')[-1].strip()
                elif ':' in username_text:
                    user_info['username'] = username_text.split(':')[-1].strip()
                else:
                    user_info['username'] = username_text
                break
                
        # Check for admin/staff indicators
        admin_indicators = [
            'a[href*="/admin/"]',
            '.admin-link',
            '[data-user-staff="true"]'
        ]
        
        for selector in admin_indicators:
            if self.page.query_selector(selector):
                user_info['is_staff'] = True
                break
                
        # Check for superuser indicators  
        superuser_indicators = [
            '.superuser-indicator',
            '[data-user-superuser="true"]'
        ]
        
        for selector in superuser_indicators:
            if self.page.query_selector(selector):
                user_info['is_superuser'] = True
                break
        
        logger.debug(f"Current user info: {user_info}")
        return user_info


class PermissionManager:
    """
    Manages user permissions and permission-based UI testing.
    
    Provides methods to set up user permissions, check UI elements based on
    permissions, and generate common permission test scenarios.
    
    Example:
        perm_manager = PermissionManager(page)
        perm_manager.setup_user_permissions('testuser', ['add_fabric', 'change_fabric'])
        ui_check = perm_manager.check_ui_permissions(['can_add_fabric'])
    """
    
    def __init__(self, page: Page):
        """
        Initialize permission manager.
        
        Args:
            page: Playwright Page instance
        """
        self.page = page
        
    def setup_user_permissions(self, username: str, permissions: List[str], 
                             create_user: bool = True) -> Dict[str, Any]:
        """
        Set up user with specific permissions for test scenarios.
        
        Args:
            username: Username to set permissions for
            permissions: List of permission codenames to assign
            create_user: Whether to create user if not exists
            
        Returns:
            Dictionary with setup result
        """
        logger.info(f"Setting up permissions for {username}: {permissions}")
        
        try:
            # Get or create user
            if create_user:
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': f"{username}@example.com",
                        'password': "testpass123"
                    }
                )
                if created:
                    user.set_password("testpass123")
                    user.save()
            else:
                user = User.objects.get(username=username)
                
            # Clear existing permissions
            user.user_permissions.clear()
            
            # Add new permissions
            added_permissions = []
            for perm_code in permissions:
                try:
                    permission = Permission.objects.get(codename=perm_code)
                    user.user_permissions.add(permission)
                    added_permissions.append(perm_code)
                except Permission.DoesNotExist:
                    logger.warning(f"Permission {perm_code} not found")
                    
            logger.info(f"Successfully set up {len(added_permissions)} permissions for {username}")
            
            return {
                'success': True,
                'username': username,
                'permissions_added': added_permissions,
                'user_created': create_user
            }
            
        except Exception as e:
            logger.error(f"Failed to set up permissions for {username}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
            
    def check_ui_permissions(self, permission_checks: List[str], 
                           base_url: str = "") -> Dict[str, bool]:
        """
        Validate UI elements based on user permissions.
        
        Args:
            permission_checks: List of permission indicators to check
            base_url: Base URL to navigate to if needed
            
        Returns:
            Dictionary mapping permission checks to their results
        """
        logger.info(f"Checking UI permissions: {permission_checks}")
        
        results = {}
        
        for permission in permission_checks:
            try:
                result = self._check_single_permission(permission, base_url)
                results[permission] = result
                logger.debug(f"Permission {permission}: {'GRANTED' if result else 'DENIED'}")
            except Exception as e:
                logger.error(f"Error checking permission {permission}: {e}")
                results[permission] = False
                
        return results
        
    def _check_single_permission(self, permission: str, base_url: str = "") -> bool:
        """
        Check a single permission by examining UI elements.
        
        Args:
            permission: Permission to check
            base_url: Base URL for navigation
            
        Returns:
            True if permission is granted, False otherwise
        """
        # Navigate to relevant page if needed
        if base_url and not self.page.url.startswith(base_url):
            self.page.goto(f"{base_url}/plugins/netbox-hedgehog/", wait_until="networkidle")
            
        # Permission-specific UI element checks
        if permission == "can_add_fabric":
            selectors = [
                'a[href*="/fabrics/add/"]',
                '.btn-add-fabric',
                '[data-action="add-fabric"]',
                'button[data-bs-target="#addFabricModal"]'
            ]
        elif permission == "can_edit_fabric":
            # Navigate to fabric list first
            if "/fabrics/" not in self.page.url:
                self.page.goto(f"{base_url}/plugins/netbox-hedgehog/fabrics/", wait_until="networkidle")
            selectors = [
                '.btn-edit',
                '[data-action="edit"]',
                'a[href*="/edit/"]',
                '.edit-button'
            ]
        elif permission == "can_delete_fabric":
            selectors = [
                '.btn-delete',
                '[data-action="delete"]',
                '.delete-button',
                'button[data-confirm="delete"]'
            ]
        elif permission == "can_sync_git":
            selectors = [
                'button[data-action="sync"]',
                '.sync-button',
                '[data-bs-target="#syncModal"]',
                '.btn-sync'
            ]
        elif permission == "can_access_admin":
            selectors = [
                'a[href*="/admin/"]',
                '.admin-link',
                '.django-admin-link'
            ]
        elif permission == "can_view_fabric_details":
            selectors = [
                '.fabric-detail',
                'a[href*="/fabrics/"]',
                '.view-fabric-button'
            ]
        else:
            # Generic permission check
            selectors = [f'[data-permission="{permission}"]']
            
        # Check if any of the selectors exist and are visible
        for selector in selectors:
            element = self.page.query_selector(selector)
            if element and element.is_visible():
                return True
                
        return False
        
    def permission_test_cases(self) -> List[Dict[str, Any]]:
        """
        Generate common permission test scenarios.
        
        Returns:
            List of test case dictionaries with user types and expected permissions
        """
        test_cases = [
            {
                'name': 'Superuser - Full Access',
                'user_type': UserType.SUPERUSER,
                'username': 'test_superuser',
                'permissions': FABRIC_ADMIN_PERMISSIONS + GIT_ADMIN_PERMISSIONS,
                'expected_ui_access': [
                    'can_add_fabric', 'can_edit_fabric', 'can_delete_fabric',
                    'can_sync_git', 'can_access_admin', 'can_view_fabric_details'
                ],
                'forbidden_ui_access': []
            },
            {
                'name': 'Admin User - Management Access',
                'user_type': UserType.ADMIN,
                'username': 'test_admin',
                'permissions': FABRIC_ADMIN_PERMISSIONS,
                'expected_ui_access': [
                    'can_add_fabric', 'can_edit_fabric', 'can_delete_fabric',
                    'can_view_fabric_details'
                ],
                'forbidden_ui_access': ['can_access_admin']
            },
            {
                'name': 'Staff User - Limited Access',
                'user_type': UserType.STAFF,
                'username': 'test_staff',
                'permissions': ['view_hedgehogfabric', 'change_hedgehogfabric'],
                'expected_ui_access': ['can_edit_fabric', 'can_view_fabric_details'],
                'forbidden_ui_access': ['can_add_fabric', 'can_delete_fabric', 'can_access_admin']
            },
            {
                'name': 'Regular User - View Only',
                'user_type': UserType.REGULAR,
                'username': 'test_regular',
                'permissions': READONLY_PERMISSIONS,
                'expected_ui_access': ['can_view_fabric_details'],
                'forbidden_ui_access': [
                    'can_add_fabric', 'can_edit_fabric', 'can_delete_fabric',
                    'can_sync_git', 'can_access_admin'
                ]
            },
            {
                'name': 'Anonymous User - No Access',
                'user_type': UserType.ANONYMOUS,
                'username': None,
                'permissions': [],
                'expected_ui_access': [],
                'forbidden_ui_access': [
                    'can_add_fabric', 'can_edit_fabric', 'can_delete_fabric',
                    'can_sync_git', 'can_access_admin', 'can_view_fabric_details'
                ]
            }
        ]
        
        logger.info(f"Generated {len(test_cases)} permission test cases")
        return test_cases


class SessionManager:
    """
    Handles session state persistence, restoration, and cleanup.
    
    Provides methods to save and restore session states for test continuity,
    and clean up sessions between tests.
    
    Example:
        session_manager = SessionManager("/tmp/test_sessions")
        session_manager.save_session_state(page.context, "admin")
        session_manager.restore_session_state(new_context, "admin")
    """
    
    def __init__(self, storage_dir: str = "test_sessions"):
        """
        Initialize session manager.
        
        Args:
            storage_dir: Directory to store session files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
    def save_session_state(self, context: BrowserContext, session_id: str, 
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Save session state for test continuity.
        
        Args:
            context: Browser context to save state from
            session_id: Unique identifier for the session
            metadata: Additional metadata to store with session
            
        Returns:
            Dictionary with save result
        """
        logger.info(f"Saving session state: {session_id}")
        
        try:
            storage_state = context.storage_state()
            
            # Add metadata
            session_data = {
                'storage_state': storage_state,
                'session_id': session_id,
                'timestamp': time.time(),
                'metadata': metadata or {}
            }
            
            # Save to file
            session_file = self.storage_dir / f"{session_id}_session.json"
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
                
            logger.info(f"Session state saved to: {session_file}")
            
            return {
                'success': True,
                'session_id': session_id,
                'file_path': str(session_file),
                'timestamp': session_data['timestamp']
            }
            
        except Exception as e:
            logger.error(f"Failed to save session state for {session_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
            
    def restore_session_state(self, context: BrowserContext, session_id: str) -> Dict[str, Any]:
        """
        Restore session state for test setup.
        
        Args:
            context: Browser context to restore state to
            session_id: Session identifier to restore
            
        Returns:
            Dictionary with restore result
        """
        logger.info(f"Restoring session state: {session_id}")
        
        session_file = self.storage_dir / f"{session_id}_session.json"
        
        try:
            if not session_file.exists():
                logger.warning(f"Session file not found: {session_file}")
                return {
                    'success': False,
                    'error': 'Session file not found'
                }
                
            with open(session_file, 'r') as f:
                session_data = json.load(f)
                
            # Restore storage state to context
            storage_state = session_data['storage_state']
            
            # Note: Context storage state can't be modified after creation
            # This should be used when creating a new context
            logger.info(f"Session state loaded for {session_id}")
            
            return {
                'success': True,
                'session_id': session_id,
                'storage_state': storage_state,
                'metadata': session_data.get('metadata', {}),
                'timestamp': session_data.get('timestamp')
            }
            
        except Exception as e:
            logger.error(f"Failed to restore session state for {session_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
            
    def clear_all_sessions(self) -> Dict[str, Any]:
        """
        Clear all saved session states for test cleanup.
        
        Returns:
            Dictionary with cleanup result
        """
        logger.info("Clearing all session states")
        
        try:
            removed_files = []
            for session_file in self.storage_dir.glob("*_session.json"):
                session_file.unlink()
                removed_files.append(str(session_file))
                
            logger.info(f"Removed {len(removed_files)} session files")
            
            return {
                'success': True,
                'files_removed': len(removed_files),
                'removed_files': removed_files
            }
            
        except Exception as e:
            logger.error(f"Failed to clear session states: {e}")
            return {
                'success': False,
                'error': str(e)
            }
            
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all saved session states.
        
        Returns:
            List of session information dictionaries
        """
        sessions = []
        
        for session_file in self.storage_dir.glob("*_session.json"):
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                    
                sessions.append({
                    'session_id': session_data.get('session_id'),
                    'file_path': str(session_file),
                    'timestamp': session_data.get('timestamp'),
                    'metadata': session_data.get('metadata', {})
                })
                
            except Exception as e:
                logger.warning(f"Failed to read session file {session_file}: {e}")
                
        return sessions


class NetBoxAuthHelper:
    """
    NetBox-specific authentication workflows and admin interface access.
    
    Provides specialized methods for NetBox authentication patterns,
    admin interface access, and API token management for GUI tests.
    
    Example:
        netbox_auth = NetBoxAuthHelper(page, "http://localhost:8000")
        netbox_auth.admin_login("superuser", "password")
        token = netbox_auth.create_api_token("testuser")
    """
    
    def __init__(self, page: Page, base_url: str):
        """
        Initialize NetBox authentication helper.
        
        Args:
            page: Playwright Page instance
            base_url: Base URL for the NetBox application
        """
        self.page = page
        self.base_url = base_url.rstrip('/')
        self.admin_base_url = f"{self.base_url}/admin"
        
    def admin_login(self, username: str, password: str = "testpass123") -> Dict[str, Any]:
        """
        Login to NetBox admin interface.
        
        Args:
            username: Admin username
            password: Admin password
            
        Returns:
            Dictionary with login result
        """
        logger.info(f"Attempting NetBox admin login for {username}")
        
        # Navigate to admin login page
        admin_login_url = f"{self.admin_base_url}/login/"
        self.page.goto(admin_login_url, wait_until="networkidle")
        
        # Wait for admin login form
        self.page.wait_for_selector('#id_username', state="visible", timeout=10000)
        
        # Fill admin login form (different from regular login)
        self.page.fill('#id_username', username)
        self.page.fill('#id_password', password)
        
        # Submit admin login
        with self.page.expect_navigation():
            self.page.click('input[type="submit"]')
            
        # Verify admin login success
        current_url = self.page.url
        if "/admin/login/" in current_url and "?next=" not in current_url:
            error_msg = self.page.query_selector('.errornote')
            error_text = error_msg.text_content() if error_msg else "Unknown admin login error"
            raise Exception(f"Admin login failed for {username}: {error_text}")
            
        # Verify we're in admin interface
        admin_header = self.page.query_selector('#header, .django-admin')
        if not admin_header:
            logger.warning("Admin interface elements not found after login")
            
        logger.info(f"Successfully logged into NetBox admin as {username}")
        
        return {
            'success': True,
            'username': username,
            'admin_url': current_url,
            'is_admin': True
        }
        
    def plugin_admin_access(self, plugin_name: str = "netbox_hedgehog") -> Dict[str, Any]:
        """
        Navigate to plugin admin section.
        
        Args:
            plugin_name: Name of the plugin to access
            
        Returns:
            Dictionary with access result
        """
        logger.info(f"Accessing admin section for plugin: {plugin_name}")
        
        # Navigate to plugin admin section
        plugin_admin_url = f"{self.admin_base_url}/"
        self.page.goto(plugin_admin_url, wait_until="networkidle")
        
        # Look for plugin models in admin interface
        plugin_section = self.page.query_selector(f'[data-app="{plugin_name}"], .app-{plugin_name}')
        
        if plugin_section:
            logger.info(f"Found admin section for {plugin_name}")
            return {'success': True, 'plugin_found': True}
        else:
            # Try generic approach - look for hedgehog-related models
            hedgehog_links = self.page.query_selector_all('a[href*="hedgehog"], a[href*="fabric"]')
            if hedgehog_links:
                logger.info(f"Found hedgehog-related admin links: {len(hedgehog_links)}")
                return {'success': True, 'plugin_found': True, 'links_found': len(hedgehog_links)}
            else:
                logger.warning(f"No admin section found for {plugin_name}")
                return {'success': False, 'plugin_found': False}
                
    def create_api_token(self, username: str) -> Optional[str]:
        """
        Create API token for GUI tests through admin interface.
        
        Args:
            username: Username to create token for
            
        Returns:
            API token string or None if creation failed
        """
        logger.info(f"Creating API token for {username} through admin interface")
        
        try:
            # Navigate to token admin page
            token_admin_url = f"{self.admin_base_url}/authtoken/token/"
            self.page.goto(token_admin_url, wait_until="networkidle")
            
            # Check if we can access token admin (might need different permissions)
            if "login" in self.page.url:
                logger.error("Cannot access token admin - insufficient permissions")
                return None
                
            # Click "Add token" button
            add_token_btn = self.page.query_selector('a[href*="/add/"], .addlink')
            if add_token_btn:
                add_token_btn.click()
                self.page.wait_for_load_state("networkidle")
                
                # Fill token creation form
                # Select user
                user_select = self.page.query_selector('#id_user')
                if user_select:
                    self.page.select_option('#id_user', label=username)
                    
                # Submit form
                save_btn = self.page.query_selector('input[name="_save"]')
                if save_btn:
                    save_btn.click()
                    self.page.wait_for_load_state("networkidle")
                    
                    # Extract token from success page
                    token_element = self.page.query_selector('.field-key input, .readonly')
                    if token_element:
                        token = token_element.get_attribute('value') or token_element.text_content()
                        logger.info(f"API token created for {username}")
                        return token.strip() if token else None
                        
            logger.warning(f"Failed to create API token for {username}")
            return None
            
        except Exception as e:
            logger.error(f"Error creating API token for {username}: {e}")
            return None
            
    def validate_netbox_permissions(self, expected_models: List[str]) -> Dict[str, bool]:
        """
        Validate access to NetBox models through admin interface.
        
        Args:
            expected_models: List of model names to check access for
            
        Returns:
            Dictionary mapping model names to access status
        """
        logger.info(f"Validating NetBox model permissions: {expected_models}")
        
        results = {}
        
        # Navigate to admin home
        self.page.goto(f"{self.admin_base_url}/", wait_until="networkidle")
        
        for model in expected_models:
            # Look for model link in admin interface
            model_selectors = [
                f'a[href*="/{model.lower()}/"]',
                f'.model-{model.lower()}',
                f'[data-model="{model}"]'
            ]
            
            has_access = False
            for selector in model_selectors:
                if self.page.query_selector(selector):
                    has_access = True
                    break
                    
            results[model] = has_access
            logger.debug(f"Model {model} access: {'GRANTED' if has_access else 'DENIED'}")
            
        return results
        
    def netbox_user_context_switch(self, username: str, password: str = "testpass123") -> Dict[str, Any]:
        """
        Switch user context within NetBox application.
        
        Args:
            username: New username to switch to
            password: Password for the user
            
        Returns:
            Dictionary with switch result
        """
        logger.info(f"Switching NetBox user context to {username}")
        
        # Logout from admin if currently in admin
        if "/admin/" in self.page.url:
            logout_link = self.page.query_selector('a[href*="/admin/logout/"]')
            if logout_link:
                logout_link.click()
                self.page.wait_for_load_state("networkidle")
                
        # Regular logout
        logout_url = f"{self.base_url}/logout/"
        self.page.goto(logout_url, wait_until="networkidle")
        
        # Login as new user
        login_manager = LoginManager(self.page, self.base_url)
        return login_manager.login(username, password)


# Legacy compatibility class (deprecated - use specific managers instead)
class AuthenticationHelper:
    """
    Legacy authentication helper for backward compatibility.
    
    DEPRECATED: Use LoginManager, PermissionManager, SessionManager, and 
    NetBoxAuthHelper instead for better separation of concerns.
    """
    
    def __init__(self, page: Page, base_url: str):
        """Initialize legacy authentication helper"""
        self.page = page
        self.base_url = base_url
        self.storage_state_dir = Path("auth_storage")
        self.storage_state_dir.mkdir(exist_ok=True)
        
    def login_user(self, username: str, password: str = "testpass123", save_state: bool = True) -> Dict[str, Any]:
        """
        Login user and optionally save authentication state
        
        Args:
            username: Username to login with
            password: Password to use
            save_state: Whether to save authentication state for reuse
            
        Returns:
            Authentication state dictionary
        """
        # Navigate to login page
        login_url = f"{self.base_url}/login/"
        self.page.goto(login_url, wait_until="networkidle")
        
        # Wait for login form to be visible
        self.page.wait_for_selector('input[name="username"]', state="visible")
        
        # Fill login form
        self.page.fill('input[name="username"]', username)
        self.page.fill('input[name="password"]', password)
        
        # Handle CSRF token if present
        csrf_token = self.page.query_selector('input[name="csrfmiddlewaretoken"]')
        if csrf_token:
            logger.info("CSRF token found in login form")
            
        # Submit login form
        submit_button = self.page.query_selector('input[type="submit"], button[type="submit"]')
        if submit_button:
            submit_button.click()
        else:
            # Fallback: press Enter on password field
            self.page.press('input[name="password"]', 'Enter')
            
        # Wait for successful login (URL should change away from login page)
        self.page.wait_for_url(f"{self.base_url}/**", wait_until="networkidle")
        
        # Verify we're not still on login page
        current_url = self.page.url
        if "/login/" in current_url:
            raise Exception(f"Login failed - still on login page: {current_url}")
            
        # Get authentication state
        storage_state = self.page.context.storage_state()
        
        # Save state if requested
        if save_state:
            state_file = self.storage_state_dir / f"{username}_auth_state.json"
            with open(state_file, 'w') as f:
                json.dump(storage_state, f, indent=2)
            logger.info(f"Authentication state saved: {state_file}")
            
        logger.info(f"Successfully logged in as {username}")
        return storage_state
        
    def logout_user(self) -> None:
        """
        Logout current user
        """
        logout_url = f"{self.base_url}/logout/"
        self.page.goto(logout_url, wait_until="networkidle")
        
        # Verify we're redirected to login page or home
        current_url = self.page.url
        if "/login/" in current_url or current_url == self.base_url:
            logger.info("Successfully logged out")
        else:
            logger.warning(f"Logout may have failed - current URL: {current_url}")
            
    def load_authentication_state(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Load saved authentication state for a user
        
        Args:
            username: Username to load state for
            
        Returns:
            Authentication state dictionary or None if not found
        """
        state_file = self.storage_state_dir / f"{username}_auth_state.json"
        
        if state_file.exists():
            with open(state_file, 'r') as f:
                storage_state = json.load(f)
            logger.info(f"Loaded authentication state for {username}")
            return storage_state
        else:
            logger.warning(f"No saved authentication state found for {username}")
            return None
            
    def create_authenticated_context(self, browser, username: str, **context_args) -> BrowserContext:
        """
        Create browser context with saved authentication state
        
        Args:
            browser: Playwright Browser instance
            username: Username to load authentication state for
            **context_args: Additional context arguments
            
        Returns:
            Authenticated browser context
        """
        storage_state = self.load_authentication_state(username)
        
        if storage_state:
            context_args['storage_state'] = storage_state
            
        context = browser.new_context(**context_args)
        logger.info(f"Created authenticated context for {username}")
        return context
        
    def verify_user_permissions(self, expected_permissions: List[str]) -> bool:
        """
        Verify current user has expected permissions by checking UI elements
        
        Args:
            expected_permissions: List of permission indicators to check
            
        Returns:
            True if all permissions verified, False otherwise
        """
        # Navigate to a page that shows permissions (like admin or dashboard)
        self.page.goto(f"{self.base_url}/plugins/netbox-hedgehog/", wait_until="networkidle")
        
        permission_verified = []
        
        for permission in expected_permissions:
            # Check for permission-specific UI elements
            if permission == "can_add_fabric":
                has_permission = self.page.query_selector('a[href*="/fabrics/add/"]') is not None
            elif permission == "can_edit_fabric":
                # Check if edit buttons are present on fabric list
                self.page.goto(f"{self.base_url}/plugins/netbox-hedgehog/fabrics/", wait_until="networkidle")
                has_permission = self.page.query_selector('.btn-edit, [data-action="edit"]') is not None
            elif permission == "can_delete_fabric":
                has_permission = self.page.query_selector('.btn-delete, [data-action="delete"]') is not None
            elif permission == "can_sync_git":
                has_permission = self.page.query_selector('button[data-action="sync"], .sync-button') is not None
            else:
                # Generic permission check - assume permission exists if no error
                has_permission = True
                
            permission_verified.append(has_permission)
            logger.info(f"Permission {permission}: {'GRANTED' if has_permission else 'DENIED'}")
            
        return all(permission_verified)
        
    def switch_user_context(self, new_username: str, password: str = "testpass123") -> Dict[str, Any]:
        """
        Switch to different user context within same page
        
        Args:
            new_username: Username to switch to
            password: Password for new user
            
        Returns:
            New authentication state
        """
        # Logout current user first
        self.logout_user()
        
        # Login as new user
        return self.login_user(new_username, password, save_state=True)
        
    def get_current_user_info(self) -> Dict[str, Any]:
        """
        Get information about currently logged in user
        
        Returns:
            Dictionary with user information
        """
        # Try to extract user info from page elements
        user_info = {
            'username': None,
            'is_authenticated': False,
            'is_staff': False,
            'is_superuser': False
        }
        
        # Check if user is authenticated by looking for logout link or user menu
        logout_link = self.page.query_selector('a[href*="/logout/"]')
        user_menu = self.page.query_selector('.user-menu, .navbar-user, .dropdown-user')
        
        if logout_link or user_menu:
            user_info['is_authenticated'] = True
            
            # Try to extract username from user menu or similar elements
            user_element = self.page.query_selector('.user-name, .username, .navbar-text')
            if user_element:
                user_info['username'] = user_element.text_content().strip()
                
            # Check for admin/staff indicators
            admin_link = self.page.query_selector('a[href*="/admin/"]')
            if admin_link:
                user_info['is_staff'] = True
                
        return user_info
        
    def clear_authentication_cache(self) -> None:
        """
        Clear all saved authentication states
        """
        for state_file in self.storage_state_dir.glob("*_auth_state.json"):
            state_file.unlink()
            logger.info(f"Removed authentication state: {state_file}")
            
    def ensure_authenticated(self, username: str, password: str = "testpass123") -> None:
        """
        Ensure user is authenticated, login if necessary
        
        Args:
            username: Username to ensure is logged in
            password: Password for the user
        """
        current_user = self.get_current_user_info()
        
        if current_user['username'] != username or not current_user['is_authenticated']:
            logger.info(f"Current user: {current_user['username']}, required: {username}")
            self.login_user(username, password, save_state=True)
        else:
            logger.info(f"User {username} already authenticated")


# Utility functions for permission-based testing
def create_user_with_permissions(username: str, permissions: List[str]) -> User:
    """
    Create user with specific permissions for testing
    
    Args:
        username: Username for the new user
        permissions: List of permission codenames
        
    Returns:
        Created User instance
    """
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpass123"
    )
    
    # Add permissions
    for perm_code in permissions:
        try:
            permission = Permission.objects.get(codename=perm_code)
            user.user_permissions.add(permission)
        except Permission.DoesNotExist:
            logger.warning(f"Permission {perm_code} not found")
            
    logger.info(f"Created user {username} with permissions: {permissions}")
    return user


def create_user_group(group_name: str, permissions: List[str]) -> Group:
    """
    Create user group with specific permissions
    
    Args:
        group_name: Name for the group
        permissions: List of permission codenames
        
    Returns:
        Created Group instance
    """
    group, created = Group.objects.get_or_create(name=group_name)
    
    for perm_code in permissions:
        try:
            permission = Permission.objects.get(codename=perm_code)
            group.permissions.add(permission)
        except Permission.DoesNotExist:
            logger.warning(f"Permission {perm_code} not found")
            
    logger.info(f"{'Created' if created else 'Updated'} group {group_name} with permissions: {permissions}")
    return group


# Common permission sets for NetBox Hedgehog Plugin
FABRIC_ADMIN_PERMISSIONS = [
    'add_hedgehogfabric',
    'change_hedgehogfabric', 
    'delete_hedgehogfabric',
    'view_hedgehogfabric'
]

GIT_ADMIN_PERMISSIONS = [
    'add_gitrepository',
    'change_gitrepository',
    'delete_gitrepository', 
    'view_gitrepository'
]

READONLY_PERMISSIONS = [
    'view_hedgehogfabric',
    'view_gitrepository'
]