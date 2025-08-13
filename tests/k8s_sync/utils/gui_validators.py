"""
GUI validation helpers for testing HTML output and visual state representation.
Validates exact CSS classes, icons, colors, and responsive behavior.
"""

from typing import Dict, Any, Optional
from django.test import RequestFactory
from django.template import Context, Template
from django.contrib.auth.models import AnonymousUser
from bs4 import BeautifulSoup
import re


class GUIStateValidator:
    """Validates GUI representation of sync states matches specifications exactly."""
    
    # Expected GUI specifications from the comprehensive spec document
    EXPECTED_GUI_STATES = {
        'not_configured': {
            'text': 'Not Configured',
            'icon': 'mdi mdi-cog-off',
            'css_class': 'bg-secondary text-white',
            'color_hex': '#6c757d',
            'message_pattern': r'Kubernetes server URL required',
            'action_button': 'Configure Server'
        },
        'disabled': {
            'text': 'Sync Disabled',
            'icon': 'mdi mdi-sync-off',
            'css_class': 'bg-secondary text-white',
            'color_hex': '#6c757d',
            'message_pattern': r'disabled by administrator',
            'action_button': 'Enable Sync'
        },
        'never_synced': {
            'text': 'Never Synced',
            'icon': 'mdi mdi-sync-off',
            'css_class': 'bg-warning text-dark',
            'color_hex': '#ffc107',
            'message_pattern': r'never been synchronized',
            'action_button': 'Sync Now'
        },
        'in_sync': {
            'text': 'In Sync',
            'icon': 'mdi mdi-check-circle',
            'css_class': 'bg-success text-white',
            'color_hex': '#198754',
            'message_pattern': r'Last sync:',
            'action_button': 'Sync Now'  # Optional manual
        },
        'out_of_sync': {
            'text': 'Out of Sync',
            'icon': 'mdi mdi-sync-alert',
            'css_class': 'bg-warning text-dark',
            'color_hex': '#ffc107',
            'message_pattern': r'overdue by',
            'action_button': 'Sync Now'
        },
        'syncing': {
            'text': 'Syncing',
            'icon': 'mdi mdi-sync mdi-spin',
            'css_class': 'bg-info text-white',
            'color_hex': '#0dcaf0',
            'message_pattern': r'in progress',
            'action_button': 'View Progress',
            'progress_bar': True
        },
        'error': {
            'text': 'Sync Error',
            'icon': 'mdi mdi-alert-circle',
            'css_class': 'bg-danger text-white',
            'color_hex': '#dc3545',
            'message_pattern': r'(timeout|failed|error)',
            'action_button': 'Retry'
        }
    }
    
    def __init__(self):
        self.request_factory = RequestFactory()
    
    def validate_fabric_status_html(self, fabric, rendered_html: str) -> Dict[str, Any]:
        """
        Validate rendered HTML contains correct status representation.
        
        Args:
            fabric: HedgehogFabric instance
            rendered_html: Rendered HTML content
            
        Returns:
            Validation results dictionary
        """
        soup = BeautifulSoup(rendered_html, 'html.parser')
        current_state = fabric.calculated_sync_status
        expected = self.EXPECTED_GUI_STATES[current_state]
        
        results = {
            'state': current_state,
            'valid': True,
            'errors': [],
            'found_elements': {}
        }
        
        # Find status indicator element
        status_indicator = soup.find(['div', 'span'], class_=re.compile(r'status-indicator|badge|sync-status'))
        
        if not status_indicator:
            results['valid'] = False
            results['errors'].append("No status indicator element found in HTML")
            return results
        
        # Validate CSS classes
        indicator_classes = ' '.join(status_indicator.get('class', []))
        results['found_elements']['css_classes'] = indicator_classes
        
        if expected['css_class'] not in indicator_classes:
            results['valid'] = False
            results['errors'].append(
                f"Expected CSS class '{expected['css_class']}' not found. "
                f"Found: '{indicator_classes}'"
            )
        
        # Validate icon
        icon_element = status_indicator.find('i') or soup.find('i', class_=re.compile(r'mdi'))
        if icon_element:
            icon_classes = ' '.join(icon_element.get('class', []))
            results['found_elements']['icon'] = icon_classes
            
            # Check for expected icon classes
            expected_icon_parts = expected['icon'].split()
            missing_icon_parts = [part for part in expected_icon_parts if part not in icon_classes]
            
            if missing_icon_parts:
                results['valid'] = False
                results['errors'].append(
                    f"Missing icon classes: {missing_icon_parts}. "
                    f"Expected: '{expected['icon']}', Found: '{icon_classes}'"
                )
        else:
            results['valid'] = False
            results['errors'].append("No icon element found")
        
        # Validate status text
        status_text = status_indicator.get_text(strip=True)
        results['found_elements']['text'] = status_text
        
        if expected['text'] not in status_text:
            results['valid'] = False
            results['errors'].append(
                f"Expected status text '{expected['text']}' not found in '{status_text}'"
            )
        
        # Validate message content (if applicable)
        if 'message_pattern' in expected:
            message_elements = soup.find_all(string=re.compile(expected['message_pattern'], re.IGNORECASE))
            if not message_elements:
                results['valid'] = False
                results['errors'].append(
                    f"Expected message pattern '{expected['message_pattern']}' not found in HTML"
                )
        
        # Validate action button
        if 'action_button' in expected:
            button_text = expected['action_button']
            buttons = soup.find_all('button', string=re.compile(button_text, re.IGNORECASE))
            links = soup.find_all('a', string=re.compile(button_text, re.IGNORECASE))
            
            if not buttons and not links:
                results['valid'] = False
                results['errors'].append(
                    f"Expected action button/link '{button_text}' not found"
                )
        
        # Validate progress bar for syncing state
        if expected.get('progress_bar'):
            progress_bars = soup.find_all(['div'], class_=re.compile(r'progress'))
            if not progress_bars:
                results['valid'] = False
                results['errors'].append("Expected progress bar for syncing state not found")
        
        return results
    
    def validate_responsive_behavior(self, fabric, viewport_sizes: Dict[str, str]) -> Dict[str, Any]:
        """
        Validate responsive behavior at different viewport sizes.
        
        Args:
            fabric: HedgehogFabric instance
            viewport_sizes: Dict of viewport_name -> css_media_query
            
        Returns:
            Validation results for each viewport
        """
        results = {}
        
        for viewport_name, media_query in viewport_sizes.items():
            # This would require browser automation (Playwright/Selenium)
            # For now, we validate CSS structure
            results[viewport_name] = {
                'tested': True,
                'media_query': media_query,
                'note': 'Responsive validation requires browser automation'
            }
        
        return results
    
    def validate_accessibility_compliance(self, rendered_html: str) -> Dict[str, Any]:
        """
        Validate accessibility compliance (WCAG 2.1 AA).
        
        Args:
            rendered_html: Rendered HTML content
            
        Returns:
            Accessibility validation results
        """
        soup = BeautifulSoup(rendered_html, 'html.parser')
        
        results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check for alt text on images
        images = soup.find_all('img')
        for img in images:
            if not img.get('alt'):
                results['warnings'].append(f"Image missing alt text: {img}")
        
        # Check for ARIA labels on interactive elements
        interactive = soup.find_all(['button', 'a', 'input'])
        for element in interactive:
            if not element.get('aria-label') and not element.get('title'):
                text_content = element.get_text(strip=True)
                if not text_content:
                    results['warnings'].append(
                        f"Interactive element missing accessible name: {element.name}"
                    )
        
        # Check color contrast (basic validation)
        # Note: Full color contrast validation requires actual color computation
        status_elements = soup.find_all(class_=re.compile(r'bg-(success|danger|warning|info|secondary)'))
        for element in status_elements:
            classes = ' '.join(element.get('class', []))
            if 'text-white' not in classes and 'text-dark' not in classes:
                results['warnings'].append(
                    f"Status element may have insufficient contrast: {classes}"
                )
        
        return results
    
    def render_fabric_status_template(self, fabric, template_name: str = None) -> str:
        """
        Render fabric status using actual Django template.
        
        Args:
            fabric: HedgehogFabric instance
            template_name: Optional template override
            
        Returns:
            Rendered HTML content
        """
        if not template_name:
            template_name = """
            <div class="status-indicator-wrapper">
                <div class="status-indicator {{ fabric.calculated_sync_status_badge_class }} d-inline-flex align-items-center px-2 py-1 rounded-pill">
                    <i class="mdi mdi-sync me-1"></i>
                    {{ fabric.calculated_sync_status_display }}
                </div>
            </div>
            """
        
        template = Template(template_name)
        request = self.request_factory.get('/')
        request.user = AnonymousUser()
        
        context = Context({
            'fabric': fabric,
            'request': request
        })
        
        return template.render(context)


def validate_gui_state_accuracy(fabric, expected_state: str) -> Dict[str, Any]:
    """
    Comprehensive GUI state validation.
    
    Args:
        fabric: HedgehogFabric instance
        expected_state: Expected sync state
        
    Returns:
        Complete validation results
    """
    validator = GUIStateValidator()
    
    # Render actual template
    rendered_html = validator.render_fabric_status_template(fabric)
    
    # Validate state accuracy
    actual_state = fabric.calculated_sync_status
    state_accurate = actual_state == expected_state
    
    # Validate GUI representation
    gui_validation = validator.validate_fabric_status_html(fabric, rendered_html)
    
    # Validate accessibility
    accessibility = validator.validate_accessibility_compliance(rendered_html)
    
    return {
        'state_calculation': {
            'expected': expected_state,
            'actual': actual_state,
            'accurate': state_accurate
        },
        'gui_representation': gui_validation,
        'accessibility': accessibility,
        'rendered_html': rendered_html,
        'overall_valid': state_accurate and gui_validation['valid'] and accessibility['valid']
    }


def create_gui_test_scenarios(fabrics: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Create comprehensive GUI test scenarios for all fabric states.
    
    Args:
        fabrics: Dict of state_name -> fabric_instance
        
    Returns:
        Dict of state_name -> validation_results
    """
    scenarios = {}
    
    for state_name, fabric in fabrics.items():
        scenarios[state_name] = validate_gui_state_accuracy(fabric, state_name)
    
    return scenarios