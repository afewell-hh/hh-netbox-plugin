"""
Base Page Object Model for NetBox Hedgehog Plugin GUI Testing

This module provides the foundational BasePage class that all page objects inherit from,
containing common functionality for element interaction, waiting, and error handling.
"""

from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
import logging

logger = logging.getLogger(__name__)


class BasePage:
    """
    Base page object containing common functionality for all page interactions
    
    This class provides:
    - Element waiting and interaction utilities
    - AJAX operation handling
    - Screenshot and error capture
    - Navigation helpers
    - Form interaction methods
    """
    
    def __init__(self, page: Page, base_url: str = ""):
        """
        Initialize base page object
        
        Args:
            page: Playwright Page instance
            base_url: Base URL for the application (from live_server fixture)
        """
        self.page = page
        self.base_url = base_url
        self.timeout = 10000  # Default timeout in milliseconds
        
    def goto(self, path: str = "", wait_until: str = "networkidle") -> None:
        """
        Navigate to a specific path
        
        Args:
            path: URL path to navigate to
            wait_until: Wait condition ('networkidle', 'domcontentloaded', 'load')
        """
        url = f"{self.base_url}{path}" if path else self.base_url
        self.page.goto(url, wait_until=wait_until, timeout=self.timeout * 3)
        
    def wait_for_element(self, selector: str, state: str = "visible", timeout: Optional[int] = None) -> Locator:
        """
        Wait for element to be in specified state
        
        Args:
            selector: CSS selector for the element
            state: Element state to wait for ('visible', 'hidden', 'attached', 'detached')
            timeout: Timeout in milliseconds (uses default if None)
            
        Returns:
            Locator for the element
        """
        timeout = timeout or self.timeout
        return self.page.wait_for_selector(selector, state=state, timeout=timeout)
        
    def click_element(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Click an element after waiting for it to be visible and enabled
        
        Args:
            selector: CSS selector for the element
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, "visible", timeout)
        element.click(timeout=timeout)
        
    def fill_field(self, selector: str, value: str, clear_first: bool = True, timeout: Optional[int] = None) -> None:
        """
        Fill a form field with a value
        
        Args:
            selector: CSS selector for the input field
            value: Value to fill
            clear_first: Whether to clear the field first
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, "visible", timeout)
        
        if clear_first:
            element.clear(timeout=timeout)
        element.fill(value, timeout=timeout)
        
    def select_option(self, selector: str, value: Union[str, List[str]], timeout: Optional[int] = None) -> None:
        """
        Select option(s) from a select element
        
        Args:
            selector: CSS selector for the select element
            value: Value(s) to select
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, "visible", timeout)
        element.select_option(value, timeout=timeout)
        
    def get_text(self, selector: str, timeout: Optional[int] = None) -> str:
        """
        Get text content of an element
        
        Args:
            selector: CSS selector for the element
            timeout: Timeout in milliseconds
            
        Returns:
            Text content of the element
        """
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, "visible", timeout)
        return element.text_content() or ""
        
    def get_attribute(self, selector: str, attribute: str, timeout: Optional[int] = None) -> Optional[str]:
        """
        Get attribute value of an element
        
        Args:
            selector: CSS selector for the element  
            attribute: Attribute name to get
            timeout: Timeout in milliseconds
            
        Returns:
            Attribute value or None if not found
        """
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, "visible", timeout)
        return element.get_attribute(attribute)
        
    def is_element_visible(self, selector: str, timeout: Optional[int] = None) -> bool:
        """
        Check if element is visible
        
        Args:
            selector: CSS selector for the element
            timeout: Timeout in milliseconds
            
        Returns:
            True if element is visible, False otherwise
        """
        timeout = timeout or 1000  # Shorter timeout for visibility checks
        try:
            self.wait_for_element(selector, "visible", timeout)
            return True
        except PlaywrightTimeoutError:
            return False
            
    def is_element_present(self, selector: str) -> bool:
        """
        Check if element exists in DOM (regardless of visibility)
        
        Args:
            selector: CSS selector for the element
            
        Returns:
            True if element exists, False otherwise
        """
        return self.page.query_selector(selector) is not None
        
    def wait_for_ajax_complete(self, timeout: Optional[int] = None) -> None:
        """
        Wait for AJAX operations to complete
        
        Args:
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        
        # Wait for network to be idle
        self.page.wait_for_load_state("networkidle", timeout=timeout)
        
        # Wait for jQuery AJAX if present
        try:
            self.page.wait_for_function(
                "typeof jQuery === 'undefined' || jQuery.active === 0",
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            logger.warning("jQuery AJAX wait timed out")
            
        # Wait for custom loading indicators to disappear
        loading_selectors = [".loading", ".spinner", ".loading-overlay", "[data-loading]"]
        for selector in loading_selectors:
            try:
                self.page.wait_for_selector(selector, state="detached", timeout=1000)
            except PlaywrightTimeoutError:
                continue  # Loading indicator not present or already gone
                
    def wait_for_url_change(self, expected_pattern: str, timeout: Optional[int] = None) -> None:
        """
        Wait for URL to change to match a pattern
        
        Args:
            expected_pattern: URL pattern to wait for (can use wildcards with **)
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        self.page.wait_for_url(expected_pattern, timeout=timeout)
        
    def capture_screenshot(self, name: str, full_page: bool = True) -> Path:
        """
        Capture screenshot of current page
        
        Args:
            name: Name for the screenshot file (without extension)
            full_page: Whether to capture full page or just viewport
            
        Returns:
            Path to the captured screenshot
        """
        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        screenshot_path = screenshots_dir / f"{name}.png"
        
        self.page.screenshot(path=str(screenshot_path), full_page=full_page)
        logger.info(f"Screenshot captured: {screenshot_path}")
        return screenshot_path
        
    def get_page_errors(self) -> List[Dict[str, Any]]:
        """
        Get any JavaScript console errors on the page
        
        Returns:
            List of error messages with details
        """
        errors = []
        
        # This would typically be set up in conftest.py with event listeners
        # For now, return empty list as placeholder
        return errors
        
    def scroll_to_element(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Scroll element into view
        
        Args:
            selector: CSS selector for the element
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, "attached", timeout)
        element.scroll_into_view_if_needed(timeout=timeout)
        
    def hover_element(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Hover over an element
        
        Args:
            selector: CSS selector for the element
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, "visible", timeout)
        element.hover(timeout=timeout)
        
    def double_click_element(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Double-click an element
        
        Args:
            selector: CSS selector for the element
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, "visible", timeout)
        element.dblclick(timeout=timeout)
        
    def right_click_element(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Right-click an element
        
        Args:
            selector: CSS selector for the element
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, "visible", timeout)
        element.click(button="right", timeout=timeout)
        
    def press_key(self, key: str, selector: Optional[str] = None, timeout: Optional[int] = None) -> None:
        """
        Press a keyboard key, optionally on a specific element
        
        Args:
            key: Key to press (e.g., 'Enter', 'Tab', 'Escape')
            selector: CSS selector for element to focus (if None, presses on page)
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        
        if selector:
            element = self.wait_for_element(selector, "visible", timeout)
            element.press(key, timeout=timeout)
        else:
            self.page.keyboard.press(key)
            
    def wait_for_alert(self, timeout: Optional[int] = None) -> str:
        """
        Wait for and handle JavaScript alert dialog
        
        Args:
            timeout: Timeout in milliseconds
            
        Returns:
            Alert message text
        """
        timeout = timeout or self.timeout
        
        with self.page.expect_popup(timeout=timeout) as alert_info:
            alert = alert_info.value
            message = alert.message
            alert.accept()
            return message
            
    def check_checkbox(self, selector: str, checked: bool = True, timeout: Optional[int] = None) -> None:
        """
        Check or uncheck a checkbox
        
        Args:
            selector: CSS selector for the checkbox
            checked: True to check, False to uncheck
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, "visible", timeout)
        element.set_checked(checked, timeout=timeout)
        
    def get_element_count(self, selector: str) -> int:
        """
        Get count of elements matching selector
        
        Args:
            selector: CSS selector for elements
            
        Returns:
            Number of matching elements
        """
        return len(self.page.query_selector_all(selector))
        
    def wait_for_element_count(self, selector: str, expected_count: int, timeout: Optional[int] = None) -> None:
        """
        Wait for specific number of elements matching selector
        
        Args:
            selector: CSS selector for elements
            expected_count: Expected number of elements
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        
        def check_count():
            return len(self.page.query_selector_all(selector)) == expected_count
            
        self.page.wait_for_function(check_count, timeout=timeout)


class FormPage(BasePage):
    """
    Specialized page object for form interactions
    
    Provides form-specific functionality including:
    - Form filling with validation
    - Submit handling with success/error detection
    - Field-specific interactions (selects, checkboxes, etc.)
    - Client-side validation testing
    - Form state management
    """
    
    def __init__(self, page: Page, base_url: str = "", form_selector: str = "form"):
        """Initialize form page with specific form selector"""
        super().__init__(page, base_url)
        self.form_selector = form_selector
    
    def fill_form(self, field_values: Dict[str, Any], submit: bool = False) -> None:
        """
        Fill multiple form fields at once
        
        Args:
            field_values: Dictionary mapping field names to values
            submit: Whether to submit form after filling
            
        Example:
            form_page.fill_form({
                'name': 'Test Fabric',
                'git_url': 'https://github.com/example/repo.git',
                'active': True
            }, submit=True)
        """
        for field_name, value in field_values.items():
            field_selector = f"#{field_name}, [name='{field_name}'], [data-field='{field_name}']"
            
            if isinstance(value, bool):
                self.check_checkbox(field_selector, value)
            elif isinstance(value, list):
                self.select_option(field_selector, value)
            else:
                self.fill_field(field_selector, str(value))
        
        if submit:
            self.submit_form()
    
    def submit_form(self, button_selector: str = "button[type='submit'], input[type='submit']") -> None:
        """
        Submit the form and wait for response
        
        Args:
            button_selector: Selector for submit button
        """
        with self.page.expect_response(lambda response: True):
            self.click_element(button_selector)
        self.wait_for_ajax_complete()
    
    def wait_for_validation_error(self, field_name: str, timeout: Optional[int] = None) -> str:
        """
        Wait for client-side validation error and return message
        
        Args:
            field_name: Field name to check for validation error
            timeout: Timeout in milliseconds
            
        Returns:
            Validation error message
        """
        timeout = timeout or self.timeout
        error_selector = f"#id_{field_name} + .invalid-feedback, .field-{field_name} .invalid-feedback"
        error_element = self.wait_for_element(error_selector, "visible", timeout)
        return error_element.text_content() or ""
    
    def is_form_valid(self) -> bool:
        """
        Check if form passes client-side validation
        
        Returns:
            True if form is valid, False otherwise
        """
        invalid_fields = self.page.query_selector_all(".is-invalid, [aria-invalid='true']")
        return len(invalid_fields) == 0
    
    def get_form_data(self) -> Dict[str, Any]:
        """
        Extract current form field values
        
        Returns:
            Dictionary of field names and their current values
        """
        form_data = {}
        
        # Text inputs
        for input_elem in self.page.query_selector_all(f"{self.form_selector} input[type='text'], {self.form_selector} input[type='email'], {self.form_selector} input[type='url'], {self.form_selector} textarea"):
            name = input_elem.get_attribute("name")
            if name:
                form_data[name] = input_elem.input_value()
        
        # Checkboxes
        for checkbox in self.page.query_selector_all(f"{self.form_selector} input[type='checkbox']"):
            name = checkbox.get_attribute("name")
            if name:
                form_data[name] = checkbox.is_checked()
        
        # Select elements
        for select in self.page.query_selector_all(f"{self.form_selector} select"):
            name = select.get_attribute("name")
            if name:
                form_data[name] = select.input_value()
        
        return form_data
    
    def select_dropdown_option(self, selector: str, option_text: str, timeout: Optional[int] = None) -> None:
        """
        Select option from dropdown by visible text
        
        Args:
            selector: Selector for the select element
            option_text: Visible text of option to select
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        select_element = self.wait_for_element(selector, "visible", timeout)
        select_element.select_option(label=option_text, timeout=timeout)
    
    def upload_file(self, file_selector: str, file_path: str, timeout: Optional[int] = None) -> None:
        """
        Upload file to file input
        
        Args:
            file_selector: Selector for file input element
            file_path: Path to file to upload
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        file_input = self.wait_for_element(file_selector, "attached", timeout)
        file_input.set_input_files(file_path, timeout=timeout)


class ListPage(BasePage):
    """
    Specialized page object for list view interactions
    
    Provides list-specific functionality including:
    - Table interactions (sorting, filtering, search)
    - Pagination navigation
    - Bulk operations (select multiple, bulk actions)
    - Column visibility and ordering
    - Export functionality testing
    """
    
    def __init__(self, page: Page, base_url: str = "", table_selector: str = "table"):
        """Initialize list page with specific table selector"""
        super().__init__(page, base_url)
        self.table_selector = table_selector
    
    def sort_by_column(self, column_name: str, timeout: Optional[int] = None) -> None:
        """
        Sort table by clicking column header
        
        Args:
            column_name: Name of column to sort by
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        header_selector = f"{self.table_selector} th:has-text('{column_name}'), {self.table_selector} th[data-column='{column_name}']"
        self.click_element(header_selector, timeout)
        self.wait_for_ajax_complete()
    
    def filter_by_text(self, search_text: str, search_selector: str = "#search, [name='q'], [data-search]", timeout: Optional[int] = None) -> None:
        """
        Filter list by entering search text
        
        Args:
            search_text: Text to search for
            search_selector: Selector for search input
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        self.fill_field(search_selector, search_text, timeout=timeout)
        # Wait for search to process (debounced usually)
        self.page.wait_for_timeout(500)
        self.wait_for_ajax_complete()
    
    def get_table_row_count(self) -> int:
        """
        Get number of rows in table body
        
        Returns:
            Number of table rows
        """
        return len(self.page.query_selector_all(f"{self.table_selector} tbody tr"))
    
    def get_row_data(self, row_index: int) -> List[str]:
        """
        Get text content from all cells in a specific row
        
        Args:
            row_index: Index of row (0-based)
            
        Returns:
            List of cell text content
        """
        row_selector = f"{self.table_selector} tbody tr:nth-child({row_index + 1})"
        cells = self.page.query_selector_all(f"{row_selector} td")
        return [cell.text_content() or "" for cell in cells]
    
    def select_all_items(self, select_all_selector: str = "[data-select-all], #select-all", timeout: Optional[int] = None) -> None:
        """
        Select all items using select-all checkbox
        
        Args:
            select_all_selector: Selector for select-all checkbox
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        self.check_checkbox(select_all_selector, True, timeout)
        self.wait_for_ajax_complete()
    
    def select_items(self, item_indices: List[int], item_selector: str = "[data-bulk-item], [name='selected_items']", timeout: Optional[int] = None) -> None:
        """
        Select specific items by index
        
        Args:
            item_indices: List of item indices to select (0-based)
            item_selector: Selector for item checkboxes
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        checkboxes = self.page.query_selector_all(item_selector)
        
        for index in item_indices:
            if index < len(checkboxes):
                checkboxes[index].set_checked(True, timeout=timeout)
    
    def perform_bulk_action(self, action_value: str, action_selector: str = "[data-bulk-action]", confirm: bool = True, timeout: Optional[int] = None) -> None:
        """
        Perform bulk action on selected items
        
        Args:
            action_value: Value of action to perform
            action_selector: Selector for action dropdown/button
            confirm: Whether to confirm destructive actions
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        
        # Select action
        if self.is_element_present(f"{action_selector} option"):  # Dropdown
            self.select_option(action_selector, action_value, timeout)
        else:  # Button
            self.click_element(f"{action_selector}[value='{action_value}']", timeout)
        
        # Handle confirmation dialog if needed
        if confirm and action_value in ['delete', 'remove', 'archive']:
            try:
                confirm_selector = "[data-confirm], .btn-danger, .confirm-delete"
                if self.is_element_visible(confirm_selector, 1000):
                    self.click_element(confirm_selector, timeout)
            except PlaywrightTimeoutError:
                pass  # No confirmation dialog
        
        self.wait_for_ajax_complete()
    
    def navigate_to_page(self, page_number: int, pagination_selector: str = ".pagination", timeout: Optional[int] = None) -> None:
        """
        Navigate to specific page using pagination
        
        Args:
            page_number: Page number to navigate to
            pagination_selector: Selector for pagination container
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        page_link_selector = f"{pagination_selector} a:has-text('{page_number}')"
        self.click_element(page_link_selector, timeout)
        self.wait_for_ajax_complete()
    
    def get_current_page(self, pagination_selector: str = ".pagination") -> int:
        """
        Get current page number from pagination
        
        Args:
            pagination_selector: Selector for pagination container
            
        Returns:
            Current page number
        """
        active_page = self.page.query_selector(f"{pagination_selector} .page-item.active .page-link, {pagination_selector} .current")
        if active_page:
            return int(active_page.text_content() or "1")
        return 1


class DetailPage(BasePage):
    """
    Specialized page object for detail view interactions
    
    Provides detail-specific functionality including:
    - Detail view navigation
    - Related object interactions
    - Action button testing (edit, delete, sync)
    - Tab navigation for multi-section details
    - Data validation and display
    """
    
    def __init__(self, page: Page, base_url: str = ""):
        """Initialize detail page"""
        super().__init__(page, base_url)
    
    def get_field_value(self, field_name: str) -> str:
        """
        Get value from detail field by name or label
        
        Args:
            field_name: Name or label of field
            
        Returns:
            Field value text
        """
        # Try multiple selectors for field value
        selectors = [
            f"[data-field='{field_name}'] .value",
            f"td:has-text('{field_name}') + td",
            f".field-{field_name} .value",
            f"#{field_name}-value"
        ]
        
        for selector in selectors:
            if self.is_element_present(selector):
                return self.get_text(selector)
        
        return ""
    
    def click_action_button(self, action: str, timeout: Optional[int] = None) -> None:
        """
        Click action button (edit, delete, sync, etc.)
        
        Args:
            action: Action name (edit, delete, sync, test, etc.)
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        
        # Try multiple selector patterns for action buttons
        selectors = [
            f"#{action}-button",
            f"[data-action='{action}']",
            f".btn-{action}",
            f"button:has-text('{action.title()}')",
            f"a:has-text('{action.title()}')"
        ]
        
        for selector in selectors:
            if self.is_element_visible(selector, 1000):
                self.click_element(selector, timeout)
                break
        else:
            raise PlaywrightTimeoutError(f"Action button '{action}' not found")
        
        self.wait_for_ajax_complete()
    
    def switch_to_tab(self, tab_name: str, timeout: Optional[int] = None) -> None:
        """
        Switch to a specific tab in tabbed detail view
        
        Args:
            tab_name: Name of tab to switch to
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        
        tab_selectors = [
            f"a[href='#{tab_name}'], a[data-tab='{tab_name}']",
            f".nav-link:has-text('{tab_name}')",
            f"button[data-bs-target='#{tab_name}']"
        ]
        
        for selector in tab_selectors:
            if self.is_element_visible(selector, 1000):
                self.click_element(selector, timeout)
                self.wait_for_element(f"#{tab_name}", "visible", timeout)
                return
        
        raise PlaywrightTimeoutError(f"Tab '{tab_name}' not found")
    
    def get_status_badge_text(self, status_selector: str = "[data-status], .badge, .status-indicator") -> str:
        """
        Get text from status badge/indicator
        
        Args:
            status_selector: Selector for status element
            
        Returns:
            Status text
        """
        return self.get_text(status_selector)
    
    def get_related_items_count(self, relation_name: str) -> int:
        """
        Get count of related items in a section
        
        Args:
            relation_name: Name of relation (e.g., 'switches', 'connections')
            
        Returns:
            Count of related items
        """
        count_selectors = [
            f"#{relation_name}-count",
            f"[data-count='{relation_name}']",
            f".{relation_name}-count",
            f"#{relation_name}-section .badge"
        ]
        
        for selector in count_selectors:
            if self.is_element_present(selector):
                count_text = self.get_text(selector)
                # Extract number from text like "(5)" or "5 items"
                import re
                match = re.search(r'\d+', count_text)
                return int(match.group()) if match else 0
        
        # Fallback: count table rows or list items
        items_selector = f"#{relation_name}-section tbody tr, #{relation_name}-section .list-group-item"
        return self.get_element_count(items_selector)


class NetBoxPluginPage(BasePage):
    """
    Specialized page object for NetBox plugin-specific UI patterns
    
    Provides NetBox-specific functionality including:
    - NetBox navigation helpers
    - Plugin-specific sync operations
    - Status indicator management
    - NetBox admin interface interactions
    - Custom NetBox UI component handling
    """
    
    def __init__(self, page: Page, base_url: str = ""):
        """Initialize NetBox plugin page"""
        super().__init__(page, base_url)
        self.plugin_prefix = "/plugins/hedgehog"
    
    def navigate_to_plugin_section(self, section: str, timeout: Optional[int] = None) -> None:
        """
        Navigate to specific plugin section
        
        Args:
            section: Section name (fabrics, git-repositories, etc.)
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        url = f"{self.base_url}{self.plugin_prefix}/{section}/"
        self.page.goto(url, wait_until="networkidle", timeout=timeout * 3)
    
    def wait_for_sync_completion(self, fabric_id: Optional[str] = None, timeout: Optional[int] = None) -> bool:
        """
        Wait for fabric sync operation to complete
        
        Args:
            fabric_id: Specific fabric ID to monitor
            timeout: Timeout in milliseconds
            
        Returns:
            True if sync completed successfully
        """
        timeout = timeout or 30000  # Longer timeout for sync operations
        
        try:
            # Wait for sync button to become available again (not disabled/loading)
            sync_button_selector = "#sync-button, .btn-sync-fabric, [data-sync-button]"
            self.page.wait_for_function(
                f"document.querySelector('{sync_button_selector}') && !document.querySelector('{sync_button_selector}').disabled",
                timeout=timeout
            )
            
            # Wait for loading indicators to disappear
            loading_selectors = [".loading-spinner", ".btn-loading", "[data-loading='true']"]
            for selector in loading_selectors:
                try:
                    self.page.wait_for_selector(selector, state="detached", timeout=2000)
                except PlaywrightTimeoutError:
                    continue
            
            return True
            
        except PlaywrightTimeoutError:
            logger.warning(f"Sync operation timeout after {timeout}ms")
            return False
    
    def get_sync_status(self, status_selector: str = "[data-sync-status], .sync-status") -> str:
        """
        Get current sync status from status indicator
        
        Args:
            status_selector: Selector for sync status element
            
        Returns:
            Sync status text
        """
        if self.is_element_visible(status_selector, 2000):
            return self.get_text(status_selector)
        return "unknown"
    
    def get_crd_count(self, crd_selector: str = "[data-crd-count], .crd-count") -> int:
        """
        Get CRD count from counter element
        
        Args:
            crd_selector: Selector for CRD count element
            
        Returns:
            CRD count as integer
        """
        if self.is_element_visible(crd_selector, 2000):
            count_text = self.get_text(crd_selector)
            import re
            match = re.search(r'\d+', count_text)
            return int(match.group()) if match else 0
        return 0
    
    def trigger_fabric_sync(self, fabric_id: Optional[str] = None, wait_completion: bool = True, timeout: Optional[int] = None) -> bool:
        """
        Trigger fabric sync operation
        
        Args:
            fabric_id: Specific fabric ID to sync
            wait_completion: Whether to wait for sync to complete
            timeout: Timeout in milliseconds
            
        Returns:
            True if sync was triggered successfully
            
        Example:
            # Trigger sync and wait for completion
            success = netbox_page.trigger_fabric_sync(fabric_id="123", wait_completion=True)
        """
        timeout = timeout or self.timeout
        
        try:
            sync_selectors = ["#sync-button", ".btn-sync-fabric", "[data-sync-button]"]
            
            for selector in sync_selectors:
                if self.is_element_visible(selector, 1000):
                    self.click_element(selector, timeout)
                    break
            else:
                logger.error("No sync button found")
                return False
            
            if wait_completion:
                return self.wait_for_sync_completion(fabric_id, timeout * 3)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to trigger sync: {e}")
            return False
    
    def test_fabric_connection(self, fabric_id: Optional[str] = None, timeout: Optional[int] = None) -> bool:
        """
        Test fabric connection
        
        Args:
            fabric_id: Specific fabric ID to test
            timeout: Timeout in milliseconds
            
        Returns:
            True if connection test passed
        """
        timeout = timeout or self.timeout
        
        try:
            test_button_selector = "#test-connection-button, .btn-test-connection, [data-test-connection]"
            self.click_element(test_button_selector, timeout)
            
            # Wait for test to complete and check result
            self.wait_for_ajax_complete()
            
            # Check for success indicators
            success_indicators = [".alert-success", ".notification-success", "[data-connection-status='success']"]
            for indicator in success_indicators:
                if self.is_element_visible(indicator, 5000):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def wait_for_notification(self, notification_type: str = "success", timeout: Optional[int] = None) -> str:
        """
        Wait for and capture notification message
        
        Args:
            notification_type: Type of notification (success, error, warning, info)
            timeout: Timeout in milliseconds
            
        Returns:
            Notification message text
        """
        timeout = timeout or self.timeout
        
        notification_selectors = [
            f".alert-{notification_type}",
            f".notification-{notification_type}",
            f"[data-notification='{notification_type}']"
        ]
        
        for selector in notification_selectors:
            try:
                notification_element = self.wait_for_element(selector, "visible", timeout)
                return notification_element.text_content() or ""
            except PlaywrightTimeoutError:
                continue
        
        raise PlaywrightTimeoutError(f"No {notification_type} notification appeared within {timeout}ms")
    
    def dismiss_notification(self, timeout: Optional[int] = None) -> None:
        """
        Dismiss any visible notifications
        
        Args:
            timeout: Timeout in milliseconds
        """
        timeout = timeout or self.timeout
        
        dismiss_selectors = [".alert .btn-close", ".notification .close", "[data-dismiss='alert']"]
        
        for selector in dismiss_selectors:
            if self.is_element_visible(selector, 1000):
                self.click_element(selector, timeout)
                break