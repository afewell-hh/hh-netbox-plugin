#!/usr/bin/env python3
"""
Comprehensive Fabric Detail Page GUI Analysis
Systematic investigation of functional and visual issues
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
from typing import Dict, List, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class FabricDetailAnalyzer:
    """Comprehensive GUI analyzer for fabric detail page"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.fabric_detail_url = f"{self.base_url}/plugins/hedgehog/fabrics/1/"
        self.issues = []
        self.evidence = {}
        self.page = None
        self.browser = None
        self.context = None
        
    def log_issue(self, category: str, severity: str, location: str, 
                  description: str, evidence: str, impact: str):
        """Log a discovered issue with all required details"""
        issue = {
            "id": len(self.issues) + 1,
            "category": category,
            "severity": severity,
            "location": location,
            "description": description,
            "evidence": evidence,
            "impact": impact,
            "timestamp": datetime.now().isoformat()
        }
        self.issues.append(issue)
        print(f"[{severity}] {category}: {description}")
        
    async def setup_browser(self):
        """Initialize browser for testing"""
        playwright = sync_playwright().start()
        self.browser = playwright.chromium.launch(headless=False)
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        )
        self.page = self.context.new_page()
        
        # Enable console logging
        self.page.on("console", self._handle_console)
        self.page.on("pageerror", self._handle_page_error)
        
    def _handle_console(self, msg):
        """Capture console messages"""
        if msg.type == "error":
            self.log_issue(
                category="JavaScript",
                severity="Major",
                location="Browser Console",
                description=f"Console Error: {msg.text}",
                evidence=f"Console: {msg.text}",
                impact="JavaScript functionality may be broken"
            )
            
    def _handle_page_error(self, error):
        """Capture page errors"""
        self.log_issue(
            category="JavaScript",
            severity="Critical",
            location="Page Error",
            description=f"Page Error: {error.message}",
            evidence=f"Error: {error.message}\nStack: {error.stack}",
            impact="Page functionality severely impacted"
        )
        
    async def test_page_accessibility(self):
        """Test if fabric detail page is accessible"""
        try:
            response = await self.page.goto(self.fabric_detail_url)
            
            if response.status != 200:
                self.log_issue(
                    category="Navigation",
                    severity="Critical", 
                    location=self.fabric_detail_url,
                    description=f"Fabric detail page returns HTTP {response.status}",
                    evidence=f"HTTP Status: {response.status}, URL: {self.fabric_detail_url}",
                    impact="Page cannot be accessed by users"
                )
                return False
                
            # Wait for page to load
            await self.page.wait_for_load_state('networkidle')
            return True
            
        except Exception as e:
            self.log_issue(
                category="Navigation",
                severity="Critical",
                location=self.fabric_detail_url,
                description=f"Failed to load fabric detail page: {str(e)}",
                evidence=f"Exception: {str(e)}",
                impact="Page completely inaccessible"
            )
            return False
            
    async def analyze_visual_elements(self):
        """Analyze visual layout and styling issues"""
        # Check for missing CSS
        css_links = await self.page.query_selector_all('link[rel="stylesheet"]')
        for link in css_links:
            href = await link.get_attribute('href')
            if 'hedgehog' in href:
                # Test CSS loading
                response = await self.page.goto(f"{self.base_url}{href}")
                if response.status != 200:
                    self.log_issue(
                        category="Visual",
                        severity="Major",
                        location=f"CSS: {href}",
                        description="Hedgehog CSS file not loading",
                        evidence=f"CSS URL: {href}, Status: {response.status}",
                        impact="Styling and visual presentation broken"
                    )
        
        # Return to main page
        await self.page.goto(self.fabric_detail_url)
        await self.page.wait_for_load_state('networkidle')
        
        # Check for layout issues
        page_content = await self.page.content()
        if 'class="dashboard-section"' not in page_content:
            self.log_issue(
                category="Visual",
                severity="Major",
                location="Main Layout",
                description="Dashboard sections not properly rendered",
                evidence="Missing 'dashboard-section' CSS classes in HTML",
                impact="Progressive disclosure UI not working"
            )
            
        # Check responsive design
        await self.page.set_viewport_size({"width": 375, "height": 667})  # Mobile
        await asyncio.sleep(1)
        
        # Check if mobile layout exists
        mobile_content = await self.page.content()
        if 'grid-template-columns' in mobile_content:
            # Look for responsive breakpoints
            computed_styles = await self.page.evaluate('''() => {
                const section = document.querySelector('.status-cards');
                if (section) {
                    return window.getComputedStyle(section).gridTemplateColumns;
                }
                return null;
            }''')
            
            if computed_styles and computed_styles.count('1fr') > 2:
                self.log_issue(
                    category="Visual",
                    severity="Minor",
                    location="Mobile Layout",
                    description="Grid layout not optimized for mobile",
                    evidence=f"Mobile grid-template-columns: {computed_styles}",
                    impact="Poor mobile user experience"
                )
        
        # Reset to desktop
        await self.page.set_viewport_size({"width": 1920, "height": 1080})
        
    async def test_interactive_elements(self):
        """Test all buttons, forms, and interactive components"""
        # Find all buttons
        buttons = await self.page.query_selector_all('button, .btn, [role="button"]')
        
        for i, button in enumerate(buttons):
            try:
                button_text = await button.text_content()
                button_class = await button.get_attribute('class')
                is_disabled = await button.get_attribute('disabled')
                
                if is_disabled:
                    continue
                    
                # Test button click
                await button.click()
                await asyncio.sleep(0.5)
                
                # Check for any JavaScript errors after click
                # (Errors are automatically captured by console handler)
                
            except Exception as e:
                self.log_issue(
                    category="Interactive",
                    severity="Major",
                    location=f"Button {i}: {button_text}",
                    description=f"Button click failed: {str(e)}",
                    evidence=f"Button text: {button_text}, Class: {button_class}, Error: {str(e)}",
                    impact="User cannot interact with button functionality"
                )
        
        # Test form submissions if any
        forms = await self.page.query_selector_all('form')
        for i, form in enumerate(forms):
            action = await form.get_attribute('action')
            method = await form.get_attribute('method')
            
            # Check for CSRF token
            csrf_token = await form.query_selector('[name="csrfmiddlewaretoken"]')
            if not csrf_token and method and method.upper() == 'POST':
                self.log_issue(
                    category="Security",
                    severity="Critical",
                    location=f"Form {i}",
                    description="Form missing CSRF token",
                    evidence=f"Form action: {action}, method: {method}, no CSRF token found",
                    impact="Form submissions will fail with CSRF error"
                )
                
    async def test_data_integrity(self):
        """Test data display and field validation"""
        # Check for empty or malformed data displays
        data_elements = await self.page.query_selector_all('.info-value, .status-card-value')
        
        for element in data_elements:
            text_content = await element.text_content()
            if not text_content or text_content.strip() == '':
                parent_element = await element.query_selector('xpath=..')
                parent_html = await parent_element.inner_html() if parent_element else 'Unknown'
                
                self.log_issue(
                    category="Data",
                    severity="Minor",
                    location="Data Display",
                    description="Empty data field displayed",
                    evidence=f"Empty element HTML: {parent_html[:200]}...",
                    impact="Information not properly displayed to user"
                )
                
        # Check for broken links
        links = await self.page.query_selector_all('a[href]')
        for link in links:
            href = await link.get_attribute('href')
            if href and href.startswith('/'):
                # Test internal links
                full_url = f"{self.base_url}{href}"
                try:
                    response = await self.page.goto(full_url)
                    if response.status >= 400:
                        link_text = await link.text_content()
                        self.log_issue(
                            category="Navigation",
                            severity="Major",
                            location=f"Link: {href}",
                            description=f"Broken internal link returns {response.status}",
                            evidence=f"Link text: {link_text}, URL: {full_url}, Status: {response.status}",
                            impact="Navigation functionality broken"
                        )
                except Exception as e:
                    link_text = await link.text_content()
                    self.log_issue(
                        category="Navigation",
                        severity="Major", 
                        location=f"Link: {href}",
                        description=f"Link navigation failed: {str(e)}",
                        evidence=f"Link text: {link_text}, URL: {full_url}, Error: {str(e)}",
                        impact="Navigation functionality broken"
                    )
                    
                # Return to fabric detail page
                await self.page.goto(self.fabric_detail_url)
                await self.page.wait_for_load_state('networkidle')
                
    async def test_progressive_disclosure(self):
        """Test progressive disclosure UI functionality"""
        # Find collapsible sections
        toggle_buttons = await self.page.query_selector_all('.section-toggle')
        
        for i, toggle in enumerate(toggle_buttons):
            try:
                section_title = await toggle.text_content()
                
                # Test toggle functionality
                await toggle.click()
                await asyncio.sleep(0.3)
                
                # Check if content is properly hidden/shown
                is_collapsed = await toggle.evaluate('el => el.classList.contains("collapsed")')
                content_section = await toggle.evaluate('''toggle => {
                    return toggle.nextElementSibling;
                }''')
                
                if content_section:
                    content_collapsed = await content_section.evaluate('el => el.classList.contains("collapsed")')
                    
                    if is_collapsed != content_collapsed:
                        self.log_issue(
                            category="Interactive",
                            severity="Minor",
                            location=f"Progressive Disclosure Section: {section_title}",
                            description="Toggle state and content visibility mismatch",
                            evidence=f"Toggle collapsed: {is_collapsed}, Content collapsed: {content_collapsed}",
                            impact="Progressive disclosure UI inconsistent"
                        )
                
            except Exception as e:
                self.log_issue(
                    category="Interactive",
                    severity="Major",
                    location=f"Progressive Disclosure {i}",
                    description=f"Progressive disclosure failed: {str(e)}",
                    evidence=f"Section: {section_title}, Error: {str(e)}",
                    impact="Collapsible sections not working"
                )
                
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive analysis report"""
        # Categorize issues
        categories = {}
        severities = {}
        
        for issue in self.issues:
            cat = issue['category']
            sev = issue['severity']
            
            categories[cat] = categories.get(cat, 0) + 1
            severities[sev] = severities.get(sev, 0) + 1
            
        return {
            "analysis_summary": {
                "total_issues": len(self.issues),
                "categories": categories,
                "severities": severities,
                "timestamp": datetime.now().isoformat()
            },
            "issues": self.issues,
            "recommendations": self._generate_recommendations()
        }
        
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on found issues"""
        recommendations = []
        
        critical_count = len([i for i in self.issues if i['severity'] == 'Critical'])
        major_count = len([i for i in self.issues if i['severity'] == 'Major'])
        
        if critical_count > 0:
            recommendations.append(f"URGENT: Address {critical_count} critical issues immediately")
            
        if major_count > 0:
            recommendations.append(f"HIGH PRIORITY: Fix {major_count} major issues affecting usability")
            
        # Category-specific recommendations
        js_issues = [i for i in self.issues if i['category'] == 'JavaScript']
        if js_issues:
            recommendations.append("Review JavaScript implementation and error handling")
            
        nav_issues = [i for i in self.issues if i['category'] == 'Navigation']
        if nav_issues:
            recommendations.append("Fix navigation and URL routing issues")
            
        return recommendations
        
    async def cleanup(self):
        """Cleanup browser resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()


async def main():
    """Run comprehensive fabric detail page analysis"""
    analyzer = FabricDetailAnalyzer()
    
    try:
        print("=== FABRIC DETAIL PAGE COMPREHENSIVE ANALYSIS ===")
        print(f"Target URL: {analyzer.fabric_detail_url}")
        print("Starting systematic investigation...\n")
        
        await analyzer.setup_browser()
        
        # Execute analysis phases
        print("Phase 1: Testing page accessibility...")
        if await analyzer.test_page_accessibility():
            print("✓ Page accessible, proceeding with analysis\n")
            
            print("Phase 2: Analyzing visual elements...")
            await analyzer.analyze_visual_elements()
            print("✓ Visual analysis complete\n")
            
            print("Phase 3: Testing interactive elements...")
            await analyzer.test_interactive_elements()
            print("✓ Interactive elements tested\n")
            
            print("Phase 4: Testing data integrity...")
            await analyzer.test_data_integrity()
            print("✓ Data integrity analysis complete\n")
            
            print("Phase 5: Testing progressive disclosure...")
            await analyzer.test_progressive_disclosure()
            print("✓ Progressive disclosure tested\n")
        else:
            print("✗ Page not accessible, analysis limited\n")
            
        # Generate report
        report = analyzer.generate_report()
        
        # Save report
        report_file = f"fabric_detail_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        # Print summary
        print("=== ANALYSIS COMPLETE ===")
        print(f"Total Issues Found: {report['analysis_summary']['total_issues']}")
        print(f"By Severity: {report['analysis_summary']['severities']}")
        print(f"By Category: {report['analysis_summary']['categories']}")
        print(f"\nDetailed report saved to: {report_file}")
        
        if report['recommendations']:
            print("\nRECOMMENDATIONS:")
            for rec in report['recommendations']:
                print(f"• {rec}")
                
    except Exception as e:
        print(f"Analysis failed: {str(e)}")
        
    finally:
        await analyzer.cleanup()


if __name__ == "__main__":
    asyncio.run(main())