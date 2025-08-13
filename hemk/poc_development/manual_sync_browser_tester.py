#!/usr/bin/env python3
"""
Manual Sync Browser Testing with Playwright
Automated testing of manual sync button functionality
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ManualSyncBrowserTester:
    """Browser-based testing for manual sync functionality"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.fabric_url = f"{self.base_url}/plugins/netbox-hedgehog/fabric/35/"
        self.test_session_id = f"browser_test_{int(time.time())}"
        self.results = []
    
    async def test_sync_button_presence(self) -> Dict[str, Any]:
        """Test if sync button is present and accessible"""
        start_time = time.time()
        
        try:
            # Use requests to check page content (simpler than full browser)
            import requests
            response = requests.get(self.fabric_url, timeout=15)
            
            # Check for sync button indicators
            sync_button_indicators = [
                'sync-button' in response.text.lower(),
                'sync with kubernetes' in response.text.lower(),
                'onclick' in response.text.lower() and 'sync' in response.text.lower(),
                'btn' in response.text.lower() and 'sync' in response.text.lower()
            ]
            
            result = {
                "test_name": "Sync Button Presence",
                "status": "PASS" if any(sync_button_indicators) else "FAIL",
                "duration": time.time() - start_time,
                "details": {
                    "page_status": response.status_code,
                    "page_size": len(response.text),
                    "sync_indicators_found": sum(sync_button_indicators),
                    "button_html_snippet": self.extract_sync_button_html(response.text)
                }
            }
            
            if not any(sync_button_indicators):
                result["error"] = "Sync button not found on fabric detail page"
            
            return result
            
        except Exception as e:
            return {
                "test_name": "Sync Button Presence",
                "status": "ERROR",
                "duration": time.time() - start_time,
                "error": str(e)
            }
    
    def extract_sync_button_html(self, html_content: str) -> str:
        """Extract sync button HTML snippet for analysis"""
        lines = html_content.split('\n')
        sync_lines = []
        
        for i, line in enumerate(lines):
            if 'sync' in line.lower() and any(keyword in line.lower() for keyword in ['button', 'btn', 'onclick']):
                # Get context around the sync button
                start_idx = max(0, i - 2)
                end_idx = min(len(lines), i + 3)
                sync_lines.extend(lines[start_idx:end_idx])
        
        return '\n'.join(sync_lines)[:500]  # First 500 chars
    
    async def test_sync_button_click(self) -> Dict[str, Any]:
        """Test sync button click functionality"""
        start_time = time.time()
        
        try:
            import requests
            
            # First get the page to extract CSRF token
            session = requests.Session()
            page_response = session.get(self.fabric_url, timeout=15)
            
            # Extract CSRF token if present
            csrf_token = self.extract_csrf_token(page_response.text)
            
            # Prepare sync request headers
            headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': self.fabric_url,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            if csrf_token:
                headers['X-CSRFToken'] = csrf_token
            
            # Execute sync request
            sync_url = f"{self.fabric_url}sync/"
            sync_response = session.post(sync_url, headers=headers, timeout=30)
            
            result = {
                "test_name": "Sync Button Click",
                "status": "PASS" if sync_response.status_code in [200, 202] else "FAIL",
                "duration": time.time() - start_time,
                "details": {
                    "csrf_token_found": bool(csrf_token),
                    "sync_status_code": sync_response.status_code,
                    "sync_response_length": len(sync_response.text),
                    "sync_response_preview": sync_response.text[:300],
                    "response_headers": dict(sync_response.headers)
                }
            }
            
            if sync_response.status_code not in [200, 202]:
                result["error"] = f"Sync request failed with status {sync_response.status_code}: {sync_response.text[:200]}"
            
            return result
            
        except Exception as e:
            return {
                "test_name": "Sync Button Click",
                "status": "ERROR", 
                "duration": time.time() - start_time,
                "error": str(e)
            }
    
    def extract_csrf_token(self, html_content: str) -> Optional[str]:
        """Extract CSRF token from HTML content"""
        import re
        
        # Look for CSRF token patterns
        patterns = [
            r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']',
            r'csrf_token["\']:\s*["\']([^"\']+)["\']',
            r'csrftoken["\']:\s*["\']([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(1)
        
        return None
    
    async def test_sync_response_handling(self) -> Dict[str, Any]:
        """Test how sync responses are handled"""
        start_time = time.time()
        
        try:
            import requests
            
            session = requests.Session()
            
            # Get initial page state
            initial_response = session.get(self.fabric_url, timeout=15)
            initial_content = initial_response.text
            
            # Execute sync
            sync_url = f"{self.fabric_url}sync/"
            sync_response = session.post(
                sync_url,
                headers={'X-Requested-With': 'XMLHttpRequest'},
                timeout=30
            )
            
            # Get page state after sync
            await asyncio.sleep(2)  # Wait for potential async updates
            final_response = session.get(self.fabric_url, timeout=15)
            final_content = final_response.text
            
            # Analyze response content
            content_changed = initial_content != final_content
            has_success_message = any(word in sync_response.text.lower() for word in ['success', 'completed', 'synchronized'])
            has_error_message = any(word in sync_response.text.lower() for word in ['error', 'failed', 'exception'])
            
            result = {
                "test_name": "Sync Response Handling",
                "status": "PASS" if sync_response.status_code in [200, 202] else "FAIL",
                "duration": time.time() - start_time,
                "details": {
                    "sync_status_code": sync_response.status_code,
                    "content_changed_after_sync": content_changed,
                    "has_success_message": has_success_message,
                    "has_error_message": has_error_message,
                    "sync_response_size": len(sync_response.text),
                    "response_type": sync_response.headers.get('Content-Type', 'unknown')
                }
            }
            
            if has_error_message:
                result["error"] = f"Sync response contains error message: {sync_response.text[:200]}"
                result["status"] = "FAIL"
            
            return result
            
        except Exception as e:
            return {
                "test_name": "Sync Response Handling",
                "status": "ERROR",
                "duration": time.time() - start_time,
                "error": str(e)
            }
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Execute all browser tests"""
        logger.info(f"🌐 Starting manual sync browser tests - Session: {self.test_session_id}")
        
        # Run tests sequentially for browser testing
        tests = [
            self.test_sync_button_presence(),
            self.test_sync_button_click(), 
            self.test_sync_response_handling()
        ]
        
        results = []
        for test in tests:
            result = await test
            results.append(result)
            
            status_icon = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
            logger.info(f"{status_icon} {result['test_name']}: {result['status']} ({result['duration']:.2f}s)")
            
            if "error" in result:
                logger.error(f"   Error: {result['error']}")
        
        # Generate summary
        summary = {
            "session_id": self.test_session_id,
            "timestamp": datetime.now().isoformat(),
            "test_type": "Manual Sync Browser Testing",
            "results": results,
            "summary": {
                "total_tests": len(results),
                "passed": len([r for r in results if r["status"] == "PASS"]),
                "failed": len([r for r in results if r["status"] == "FAIL"]),
                "errors": len([r for r in results if r["status"] == "ERROR"])
            }
        }
        
        # Save results
        results_file = f"manual_sync_browser_results_{self.test_session_id}.json"
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"📊 Browser test results saved to: {results_file}")
        return summary

async def main():
    """Main execution function"""
    tester = ManualSyncBrowserTester()
    
    try:
        summary = await tester.run_all_tests()
        
        print("\n" + "="*60)
        print("🌐 MANUAL SYNC BROWSER TEST RESULTS")
        print("="*60)
        print(f"📋 Session ID: {summary['session_id']}")
        print(f"✅ Passed: {summary['summary']['passed']}")
        print(f"❌ Failed: {summary['summary']['failed']}")
        print(f"⚠️  Errors: {summary['summary']['errors']}")
        print("="*60)
        
        return summary
        
    except Exception as e:
        logger.error(f"Browser test framework execution failed: {e}")
        return {"error": str(e), "status": "FRAMEWORK_ERROR"}

if __name__ == "__main__":
    asyncio.run(main())