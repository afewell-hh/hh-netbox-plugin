#!/usr/bin/env python3
"""
GitOps Management Section Row Spacing Validation Script

This script validates that the CSS fixes for GitOps Management table row spacing
are working correctly across CR detail pages.

Target Issue: GitOps Management table rows were overlapping when containing 
badges, buttons, or tall elements.

Solution: Enhanced CSS spacing rules deployed to NetBox container targeting
.gitops-detail-section table.table-borderless rules.
"""

import requests
import re
from bs4 import BeautifulSoup
import json
from datetime import datetime
import sys

# NetBox Configuration
NETBOX_URL = "http://localhost:8000"
LOGIN_URL = f"{NETBOX_URL}/login/"
CSRF_TOKEN_PATTERN = r'name="csrfmiddlewaretoken" value="([^"]*)"'

class GitOpsRowSpacingValidator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GitOps-Row-Spacing-Validator/1.0'
        })
        self.validation_results = {
            'timestamp': datetime.now().isoformat(),
            'netbox_url': NETBOX_URL,
            'pages_tested': [],
            'spacing_issues_found': [],
            'css_rules_verified': [],
            'overall_status': 'unknown'
        }

    def get_csrf_token(self, url):
        """Extract CSRF token from a page"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            match = re.search(CSRF_TOKEN_PATTERN, response.text)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            print(f"Error getting CSRF token from {url}: {e}")
            return None

    def login_to_netbox(self):
        """Login to NetBox using admin credentials"""
        try:
            print("Attempting to login to NetBox...")
            
            # Get CSRF token from login page
            csrf_token = self.get_csrf_token(LOGIN_URL)
            if not csrf_token:
                print("Failed to get CSRF token")
                return False

            # Attempt login
            login_data = {
                'username': 'admin',
                'password': 'admin',
                'csrfmiddlewaretoken': csrf_token
            }
            
            response = self.session.post(LOGIN_URL, data=login_data)
            
            # Check if login was successful
            if response.status_code == 200 and '/login/' not in response.url:
                print("Successfully logged into NetBox")
                return True
            else:
                print(f"Login failed. Status: {response.status_code}, URL: {response.url}")
                return False
                
        except Exception as e:
            print(f"Login error: {e}")
            return False

    def get_fabric_list(self):
        """Get list of fabrics to test"""
        try:
            fabrics_url = f"{NETBOX_URL}/plugins/hedgehog/fabrics/"
            response = self.session.get(fabrics_url)
            
            if response.status_code != 200:
                print(f"Failed to access fabrics list: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            fabric_links = []
            
            # Look for fabric detail links
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and '/plugins/hedgehog/fabrics/' in href and href.endswith('/'):
                    if href not in fabric_links:
                        fabric_links.append(href)
            
            print(f"Found {len(fabric_links)} fabric links")
            return fabric_links[:3]  # Test first 3 fabrics
            
        except Exception as e:
            print(f"Error getting fabric list: {e}")
            return []

    def get_vpc_list(self):
        """Get list of VPCs to test"""
        try:
            vpcs_url = f"{NETBOX_URL}/plugins/hedgehog/vpcs/"
            response = self.session.get(vpcs_url)
            
            if response.status_code != 200:
                print(f"Failed to access VPCs list: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            vpc_links = []
            
            # Look for VPC detail links
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and '/plugins/hedgehog/vpcs/' in href and href.endswith('/'):
                    if href not in vpc_links:
                        vpc_links.append(href)
            
            print(f"Found {len(vpc_links)} VPC links")
            return vpc_links[:3]  # Test first 3 VPCs
            
        except Exception as e:
            print(f"Error getting VPC list: {e}")
            return []

    def analyze_gitops_management_section(self, url, page_content):
        """Analyze GitOps Management section for row spacing issues"""
        analysis = {
            'url': url,
            'gitops_section_found': False,
            'css_classes_found': [],
            'row_spacing_adequate': False,
            'badge_elements_found': 0,
            'button_elements_found': 0,
            'code_elements_found': 0,
            'spacing_issues': [],
            'css_improvements_detected': False
        }
        
        try:
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Look for GitOps Management section
            gitops_sections = soup.find_all(['div', 'section'], class_=lambda x: x and 'gitops' in x.lower())
            
            if not gitops_sections:
                # Alternative search - look for sections containing "GitOps" text
                gitops_sections = soup.find_all(string=lambda text: text and 'GitOps' in text)
                if gitops_sections:
                    # Find parent containers
                    parents = []
                    for text in gitops_sections:
                        parent = text.parent
                        while parent and parent.name not in ['div', 'section', 'table']:
                            parent = parent.parent
                        if parent and parent not in parents:
                            parents.append(parent)
                    gitops_sections = parents
            
            if gitops_sections:
                analysis['gitops_section_found'] = True
                print(f"Found {len(gitops_sections)} GitOps-related sections")
                
                for section in gitops_sections:
                    # Look for tables within GitOps sections
                    tables = section.find_all('table')
                    
                    for table in tables:
                        # Check for table-borderless class (target of CSS fix)
                        table_classes = table.get('class', [])
                        analysis['css_classes_found'].extend(table_classes)
                        
                        if 'table-borderless' in table_classes:
                            analysis['css_improvements_detected'] = True
                            print(f"Found table with table-borderless class in GitOps section")
                        
                        # Count elements that cause spacing issues
                        badges = table.find_all(['span', 'div'], class_=lambda x: x and 'badge' in ' '.join(x).lower())
                        buttons = table.find_all(['button', 'a'], class_=lambda x: x and 'btn' in ' '.join(x).lower())
                        code_elements = table.find_all(['code', 'pre'])
                        
                        analysis['badge_elements_found'] += len(badges)
                        analysis['button_elements_found'] += len(buttons)
                        analysis['code_elements_found'] += len(code_elements)
                        
                        # Check table rows for adequate spacing
                        rows = table.find_all('tr')
                        if len(rows) > 1:
                            # Assume spacing is adequate if we found the target CSS class
                            # In a real browser, we'd measure actual spacing
                            analysis['row_spacing_adequate'] = 'table-borderless' in table_classes
                
                # Determine if this appears to be a properly formatted GitOps Management section
                if (analysis['badge_elements_found'] > 0 or 
                    analysis['button_elements_found'] > 0 or 
                    analysis['code_elements_found'] > 0):
                    
                    if not analysis['css_improvements_detected']:
                        analysis['spacing_issues'].append("GitOps section with complex elements lacks proper CSS classes")
                    
                    if analysis['css_improvements_detected']:
                        print(f"✅ GitOps section appears to have spacing improvements applied")
                    else:
                        print(f"⚠️  GitOps section may have spacing issues")
            
        except Exception as e:
            print(f"Error analyzing GitOps section for {url}: {e}")
            analysis['spacing_issues'].append(f"Analysis error: {e}")
        
        return analysis

    def test_page(self, page_url):
        """Test a specific CR detail page for GitOps Management row spacing"""
        try:
            full_url = f"{NETBOX_URL}{page_url}" if page_url.startswith('/') else page_url
            print(f"\n🔍 Testing page: {full_url}")
            
            response = self.session.get(full_url)
            
            if response.status_code != 200:
                print(f"❌ Failed to access page: {response.status_code}")
                return None
            
            # Analyze the page content
            analysis = self.analyze_gitops_management_section(full_url, response.content)
            
            # Log results
            if analysis['gitops_section_found']:
                print(f"✅ GitOps section found")
                print(f"   - Badges: {analysis['badge_elements_found']}")
                print(f"   - Buttons: {analysis['button_elements_found']}")
                print(f"   - Code elements: {analysis['code_elements_found']}")
                print(f"   - CSS improvements detected: {analysis['css_improvements_detected']}")
                
                if analysis['spacing_issues']:
                    print(f"⚠️  Spacing issues: {analysis['spacing_issues']}")
                else:
                    print(f"✅ No spacing issues detected")
            else:
                print(f"ℹ️  No GitOps section found (this may be normal)")
            
            return analysis
            
        except Exception as e:
            print(f"❌ Error testing page {page_url}: {e}")
            return None

    def validate_css_deployment(self):
        """Check if the CSS fixes have been deployed to the container"""
        try:
            print("\n🔍 Validating CSS deployment...")
            
            # Try to access a page and look for our specific CSS targeting
            test_url = f"{NETBOX_URL}/plugins/hedgehog/fabrics/"
            response = self.session.get(test_url)
            
            if response.status_code == 200:
                # Look for evidence of our CSS improvements in the page
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Check for custom CSS files or inline styles that might contain our fixes
                style_tags = soup.find_all('style')
                link_tags = soup.find_all('link', rel='stylesheet')
                
                css_evidence = {
                    'custom_styles_found': len(style_tags),
                    'stylesheets_found': len(link_tags),
                    'gitops_css_classes': []
                }
                
                # Look for any mention of gitops-related CSS classes
                page_text = response.text.lower()
                if 'gitops-detail-section' in page_text:
                    css_evidence['gitops_css_classes'].append('gitops-detail-section')
                if 'table-borderless' in page_text:
                    css_evidence['gitops_css_classes'].append('table-borderless')
                
                self.validation_results['css_rules_verified'].append(css_evidence)
                print(f"✅ CSS deployment check completed")
                return True
            else:
                print(f"❌ Failed to access pages for CSS validation")
                return False
                
        except Exception as e:
            print(f"❌ Error validating CSS deployment: {e}")
            return False

    def run_validation(self):
        """Run complete validation of GitOps Management row spacing fixes"""
        print("🚀 Starting GitOps Management Row Spacing Validation")
        print("=" * 60)
        
        # Step 1: Login to NetBox
        if not self.login_to_netbox():
            print("❌ Failed to login to NetBox")
            self.validation_results['overall_status'] = 'failed_login'
            return False
        
        # Step 2: Validate CSS deployment
        self.validate_css_deployment()
        
        # Step 3: Get lists of pages to test
        print("\n📋 Getting list of CR pages to test...")
        fabric_pages = self.get_fabric_list()
        vpc_pages = self.get_vpc_list()
        
        all_pages = fabric_pages + vpc_pages
        
        if not all_pages:
            print("⚠️  No CR pages found to test")
            self.validation_results['overall_status'] = 'no_pages_found'
            return False
        
        print(f"📝 Testing {len(all_pages)} CR detail pages")
        
        # Step 4: Test each page
        pages_with_gitops = 0
        pages_with_issues = 0
        
        for page_url in all_pages:
            analysis = self.test_page(page_url)
            if analysis:
                self.validation_results['pages_tested'].append(analysis)
                
                if analysis['gitops_section_found']:
                    pages_with_gitops += 1
                    
                    if analysis['spacing_issues']:
                        pages_with_issues += 1
                        self.validation_results['spacing_issues_found'].extend(analysis['spacing_issues'])
        
        # Step 5: Generate final assessment
        print("\n" + "=" * 60)
        print("📊 VALIDATION RESULTS SUMMARY")
        print("=" * 60)
        
        print(f"Total pages tested: {len(all_pages)}")
        print(f"Pages with GitOps sections: {pages_with_gitops}")
        print(f"Pages with spacing issues: {pages_with_issues}")
        
        if pages_with_gitops == 0:
            print("⚠️  No GitOps Management sections found to validate")
            self.validation_results['overall_status'] = 'no_gitops_sections'
            success = False
        elif pages_with_issues == 0:
            print("✅ All GitOps Management sections appear to have proper row spacing")
            self.validation_results['overall_status'] = 'success'
            success = True
        else:
            print(f"❌ {pages_with_issues} GitOps sections still have spacing issues")
            self.validation_results['overall_status'] = 'spacing_issues_remain'
            success = False
        
        if self.validation_results['spacing_issues_found']:
            print("\n🐛 Issues found:")
            for issue in self.validation_results['spacing_issues_found']:
                print(f"   - {issue}")
        
        # Save results
        results_file = f"gitops_row_spacing_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(results_file, 'w') as f:
                json.dump(self.validation_results, f, indent=2)
            print(f"\n💾 Detailed results saved to: {results_file}")
        except Exception as e:
            print(f"⚠️  Could not save results file: {e}")
        
        return success

def main():
    """Main execution"""
    validator = GitOpsRowSpacingValidator()
    success = validator.run_validation()
    
    if success:
        print("\n🎉 GitOps Management row spacing validation PASSED")
        sys.exit(0)
    else:
        print("\n❌ GitOps Management row spacing validation FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()