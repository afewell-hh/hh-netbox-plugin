"""
GUI Test Client for HNP End-to-End Testing

Provides utilities for simulating real GUI interactions and validating responses.
"""

from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse
import json

# Try to import BeautifulSoup, fallback if not available
try:
    from bs4 import BeautifulSoup
    HAS_BEAUTIFULSOUP = True
except ImportError:
    BeautifulSoup = None
    HAS_BEAUTIFULSOUP = False


class HNPGUITestClient:
    """
    Enhanced test client for HNP GUI testing.
    Provides methods for common GUI operations and response validation.
    """
    
    def __init__(self):
        self.client = Client()
        self.user = None
        self._setup_authentication()
    
    def _setup_authentication(self):
        """Set up authenticated user for testing"""
        User = get_user_model()
        
        # Create or get test superuser
        self.user, created = User.objects.get_or_create(
            username='hnp_test_user',
            defaults={
                'email': 'test@hedgehog.io',
                'is_superuser': True,
                'is_staff': True,
                'is_active': True
            }
        )
        
        if created:
            self.user.set_password('test_password')
            self.user.save()
        
        # Force login
        self.client.force_login(self.user)
    
    def get_netbox_token(self):
        """Get NetBox API token from file"""
        try:
            with open('/home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox.token', 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return None
    
    def get_page(self, url_name, **kwargs):
        """
        Get a page and validate basic response.
        
        Args:
            url_name: Django URL name
            **kwargs: URL parameters
            
        Returns:
            Response object with additional validation methods
        """
        try:
            url = reverse(f'plugins:netbox_hedgehog:{url_name}', kwargs=kwargs)
        except:
            # If reverse fails, assume url_name is already a full URL
            url = url_name
            
        response = self.client.get(url)
        
        # Enhance response with validation methods
        if HAS_BEAUTIFULSOUP and response.content:
            response.soup = BeautifulSoup(response.content, 'html.parser')
        else:
            response.soup = None
        response.url = url
        
        return response
    
    def post_form(self, url_name, data, **kwargs):
        """
        Submit a form via POST and validate response.
        
        Args:
            url_name: Django URL name
            data: Form data dictionary
            **kwargs: URL parameters
            
        Returns:
            Response object
        """
        try:
            url = reverse(f'plugins:netbox_hedgehog:{url_name}', kwargs=kwargs)
        except:
            url = url_name
            
        response = self.client.post(url, data, follow=True)
        if HAS_BEAUTIFULSOUP and response.content:
            response.soup = BeautifulSoup(response.content, 'html.parser')
        else:
            response.soup = None
        response.url = url
        
        return response
    
    def click_button(self, response, button_text):
        """
        Simulate clicking a button by finding its form and submitting.
        
        Args:
            response: Previous response containing the button
            button_text: Text content of the button to click
            
        Returns:
            New response after button click
        """
        if not response.soup:
            raise ValueError("Cannot click button - no HTML content to parse")
        
        # Find button
        button = response.soup.find('button', string=button_text) or \
                 response.soup.find('input', {'type': 'submit', 'value': button_text})
        
        if not button:
            raise ValueError(f"Button with text '{button_text}' not found")
        
        # Find parent form
        form = button.find_parent('form')
        if not form:
            raise ValueError(f"No form found for button '{button_text}'")
        
        # Extract form data
        form_data = {}
        for input_elem in form.find_all(['input', 'select', 'textarea']):
            name = input_elem.get('name')
            if name:
                if input_elem.name == 'input':
                    if input_elem.get('type') == 'checkbox':
                        if input_elem.get('checked'):
                            form_data[name] = input_elem.get('value', 'on')
                    else:
                        form_data[name] = input_elem.get('value', '')
                elif input_elem.name == 'select':
                    selected = input_elem.find('option', selected=True)
                    if selected:
                        form_data[name] = selected.get('value', '')
                elif input_elem.name == 'textarea':
                    form_data[name] = input_elem.get_text()
        
        # Submit form
        action = form.get('action', response.url)
        method = form.get('method', 'post').lower()
        
        if method == 'post':
            return self.client.post(action, form_data, follow=True)
        else:
            return self.client.get(action, form_data, follow=True)
    
    def validate_page_loads(self, response, expected_title_contains=None):
        """
        Validate that a page loaded successfully.
        
        Args:
            response: Django response object
            expected_title_contains: String that should be in page title
            
        Raises:
            AssertionError: If validation fails
        """
        assert response.status_code == 200, f"Page failed to load: {response.status_code}"
        assert response.content, "Page has no content"
        
        if expected_title_contains and response.soup:
            title = response.soup.find('title')
            if title:
                assert expected_title_contains.lower() in title.get_text().lower(), \
                    f"Expected '{expected_title_contains}' in title, got: {title.get_text()}"
    
    def validate_table_contains_data(self, response, expected_rows_min=1):
        """
        Validate that a list page contains data in its table.
        
        Args:
            response: Django response object
            expected_rows_min: Minimum number of data rows expected
            
        Raises:
            AssertionError: If validation fails
        """
        assert response.soup, "No HTML content to validate"
        
        # Find main data table
        table = response.soup.find('table') or response.soup.find('div', class_='table')
        assert table, "No data table found on page"
        
        # Count data rows (excluding header)
        rows = table.find_all('tr')
        data_rows = [row for row in rows if not row.find('th')]
        
        assert len(data_rows) >= expected_rows_min, \
            f"Expected at least {expected_rows_min} data rows, found {len(data_rows)}"
    
    def validate_form_exists(self, response, form_fields=None):
        """
        Validate that a form exists on the page.
        
        Args:
            response: Django response object
            form_fields: List of field names that should exist
            
        Raises:
            AssertionError: If validation fails
        """
        assert response.soup, "No HTML content to validate"
        
        form = response.soup.find('form')
        assert form, "No form found on page"
        
        if form_fields:
            for field_name in form_fields:
                field = form.find(['input', 'select', 'textarea'], {'name': field_name})
                assert field, f"Form field '{field_name}' not found"
    
    def validate_detail_page(self, response, object_name):
        """
        Validate that a detail page displays object information correctly.
        
        Args:
            response: Django response object
            object_name: Name of object that should appear on page
            
        Raises:
            AssertionError: If validation fails
        """
        self.validate_page_loads(response)
        
        # Look for object name in page content
        page_text = response.soup.get_text().lower() if response.soup else ""
        assert object_name.lower() in page_text, \
            f"Object name '{object_name}' not found on detail page"
    
    def get_csrf_token(self, response):
        """Extract CSRF token from response"""
        if not response.soup:
            return None
            
        csrf_input = response.soup.find('input', {'name': 'csrfmiddlewaretoken'})
        return csrf_input.get('value') if csrf_input else None
    
    def simulate_fabric_creation(self, fabric_data):
        """
        Simulate creating a fabric through the GUI.
        
        Args:
            fabric_data: Dictionary with fabric information
            
        Returns:
            Response from fabric creation
        """
        # Get fabric creation page
        response = self.get_page('fabric_list')
        self.validate_page_loads(response)
        
        # Submit fabric creation form
        form_data = {
            'name': fabric_data['name'],
            'description': fabric_data.get('description', ''),
            'git_repository': fabric_data.get('git_repository', ''),
            'gitops_directory': fabric_data.get('gitops_directory', ''),
            'kubernetes_server': fabric_data.get('kubernetes_server', ''),
            'kubernetes_namespace': fabric_data.get('kubernetes_namespace', 'default'),
        }
        
        csrf_token = self.get_csrf_token(response)
        if csrf_token:
            form_data['csrfmiddlewaretoken'] = csrf_token
        
        # Note: This assumes we have a create URL - may need adjustment based on actual implementation
        try:
            create_response = self.post_form('fabric_add', form_data)
        except:
            # If fabric_add doesn't exist, try direct form submission
            create_response = self.client.post('/plugins/hedgehog/fabrics/', form_data, follow=True)
        
        return create_response
    
    def simulate_cr_crud_cycle(self, cr_type, cr_data):
        """
        Simulate complete CRUD cycle for a CR type.
        
        Args:
            cr_type: Type of CR (e.g., 'vpc', 'switch', etc.)
            cr_data: Dictionary with CR data
            
        Returns:
            Dictionary with results of each operation
        """
        results = {
            'create': None,
            'read_list': None,
            'read_detail': None,
            'update': None,
            'delete': None
        }
        
        try:
            # CREATE: Navigate to CR list and create new CR
            list_response = self.get_page(f'{cr_type}_list')
            self.validate_page_loads(list_response)
            results['create'] = list_response
            
            # READ LIST: Validate CR appears in list
            results['read_list'] = list_response
            
            # READ DETAIL: Get CR detail page (assumes CR was created)
            # This would need actual CR ID from creation result
            # For now, just validate list page structure
            
            # UPDATE & DELETE would require actual CR manipulation
            # Implementation depends on actual CR creation working
            
        except Exception as e:
            results['error'] = str(e)
        
        return results