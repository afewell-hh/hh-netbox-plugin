#!/usr/bin/env python3
"""
Static GUI Analysis for Fabric Detail Page
Analyzes templates, CSS, and JavaScript for potential issues
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

class StaticGUIAnalyzer:
    """Static analysis of GUI components for fabric detail page"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues = []
        self.templates_dir = project_root / "netbox_hedgehog" / "templates" / "netbox_hedgehog"
        self.static_dir = project_root / "netbox_hedgehog" / "static" / "netbox_hedgehog"
        
    def log_issue(self, category: str, severity: str, file_path: str, 
                  description: str, evidence: str, impact: str, line_number: int = None):
        """Log a discovered issue"""
        issue = {
            "id": len(self.issues) + 1,
            "category": category,
            "severity": severity,
            "file_path": str(file_path),
            "line_number": line_number,
            "description": description,
            "evidence": evidence,
            "impact": impact,
            "timestamp": datetime.now().isoformat()
        }
        self.issues.append(issue)
        print(f"[{severity}] {category}: {description} ({file_path}:{line_number or 'N/A'})")
        
    def analyze_fabric_detail_templates(self):
        """Analyze all fabric detail template variations"""
        fabric_templates = list(self.templates_dir.glob("fabric_detail*.html"))
        
        for template_path in fabric_templates:
            self._analyze_single_template(template_path)
            
    def _analyze_single_template(self, template_path: Path):
        """Analyze a single template file"""
        try:
            content = template_path.read_text()
            lines = content.split('\n')
            
            # Check for common HTML/Django template issues
            self._check_template_syntax(template_path, content, lines)
            self._check_css_references(template_path, content, lines)
            self._check_javascript_references(template_path, content, lines) 
            self._check_form_issues(template_path, content, lines)
            self._check_accessibility_issues(template_path, content, lines)
            self._check_responsive_design(template_path, content, lines)
            
        except Exception as e:
            self.log_issue(
                category="Template",
                severity="Critical",
                file_path=template_path,
                description=f"Cannot read template file: {str(e)}",
                evidence=f"Exception: {str(e)}",
                impact="Template completely unusable"
            )
            
    def _check_template_syntax(self, template_path: Path, content: str, lines: List[str]):
        """Check Django template syntax issues"""
        # Check for unclosed tags
        open_tags = []
        for i, line in enumerate(lines):
            # Find Django template tags
            tag_matches = re.findall(r'{%\s*(\w+)', line)
            end_matches = re.findall(r'{%\s*end(\w+)', line)
            
            for tag in tag_matches:
                if tag not in ['csrf_token', 'static', 'url', 'load', 'comment', 'if', 'for', 'block']:
                    continue
                if tag in ['if', 'for', 'block']:
                    open_tags.append((tag, i + 1))
                    
            for end_tag in end_matches:
                if open_tags and open_tags[-1][0] == end_tag:
                    open_tags.pop()
                else:
                    self.log_issue(
                        category="Template Syntax",
                        severity="Major",
                        file_path=template_path,
                        line_number=i + 1,
                        description=f"Mismatched end tag: end{end_tag}",
                        evidence=f"Line {i+1}: {line.strip()}",
                        impact="Template rendering will fail"
                    )
        
        # Check for missing extends
        if not re.search(r'{%\s*extends\s+', content):
            self.log_issue(
                category="Template Structure",
                severity="Major",
                file_path=template_path,
                description="Template missing {% extends %} directive",
                evidence="No {% extends %} found in template",
                impact="Template will not inherit base layout"
            )
            
        # Check for missing CSRF tokens in forms
        if '<form' in content and 'method="post"' in content.lower():
            if 'csrfmiddlewaretoken' not in content:
                self.log_issue(
                    category="Security",
                    severity="Critical",
                    file_path=template_path,
                    description="POST form missing CSRF token",
                    evidence="Form with method='post' found but no {% csrf_token %}",
                    impact="Form submissions will fail with CSRF error"
                )
                
    def _check_css_references(self, template_path: Path, content: str, lines: List[str]):
        """Check CSS reference issues"""
        # Find CSS references
        css_refs = re.findall(r'href="{% static \'([^\']+\.css)\' %}"', content)
        css_refs.extend(re.findall(r'href="{% static "([^"]+\.css)" %}"', content))
        
        for css_ref in css_refs:
            css_path = self.static_dir / css_ref.replace('netbox_hedgehog/', '')
            if not css_path.exists():
                self.log_issue(
                    category="CSS",
                    severity="Major",
                    file_path=template_path,
                    description=f"Referenced CSS file does not exist: {css_ref}",
                    evidence=f"CSS reference: {css_ref}, Expected path: {css_path}",
                    impact="Styling will be broken"
                )
                
        # Check for inline styles that should be in CSS
        inline_style_count = len(re.findall(r'style="[^"]*"', content))
        if inline_style_count > 10:
            self.log_issue(
                category="CSS",
                severity="Minor",
                file_path=template_path,
                description=f"Excessive inline styles ({inline_style_count})",
                evidence=f"Found {inline_style_count} inline style attributes",
                impact="Maintainability and consistency issues"
            )
            
    def _check_javascript_references(self, template_path: Path, content: str, lines: List[str]):
        """Check JavaScript reference issues"""
        # Find JS references
        js_refs = re.findall(r'src="{% static \'([^\']+\.js)\' %}"', content)
        js_refs.extend(re.findall(r'src="{% static "([^"]+\.js)" %}"', content))
        
        for js_ref in js_refs:
            js_path = self.static_dir / js_ref.replace('netbox_hedgehog/', '')
            if not js_path.exists():
                self.log_issue(
                    category="JavaScript",
                    severity="Major",
                    file_path=template_path,
                    description=f"Referenced JS file does not exist: {js_ref}",
                    evidence=f"JS reference: {js_ref}, Expected path: {js_path}",
                    impact="JavaScript functionality will fail"
                )
                
        # Check for inline JavaScript
        script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
        for script in script_blocks:
            if 'console.log' in script:
                self.log_issue(
                    category="JavaScript",
                    severity="Minor", 
                    file_path=template_path,
                    description="Debug console.log statements in production code",
                    evidence=f"Script contains console.log: {script[:100]}...",
                    impact="Debug output in production"
                )
                
    def _check_form_issues(self, template_path: Path, content: str, lines: List[str]):
        """Check form-related issues"""
        # Find forms
        form_matches = re.finditer(r'<form[^>]*>', content)
        for match in form_matches:
            form_tag = match.group()
            
            # Check for action attribute
            if 'action=' not in form_tag:
                line_num = content[:match.start()].count('\n') + 1
                self.log_issue(
                    category="Forms",
                    severity="Major",
                    file_path=template_path,
                    line_number=line_num,
                    description="Form missing action attribute",
                    evidence=f"Form tag: {form_tag}",
                    impact="Form may not submit to correct endpoint"
                )
                
            # Check for method attribute on non-GET forms
            if 'method=' not in form_tag and 'button' in content[match.end():match.end()+500]:
                line_num = content[:match.start()].count('\n') + 1
                self.log_issue(
                    category="Forms",
                    severity="Minor",
                    file_path=template_path,
                    line_number=line_num,
                    description="Form missing method attribute",
                    evidence=f"Form tag: {form_tag}",
                    impact="Form will default to GET method"
                )
                
    def _check_accessibility_issues(self, template_path: Path, content: str, lines: List[str]):
        """Check accessibility issues"""
        # Check for images without alt text
        img_matches = re.finditer(r'<img[^>]*>', content)
        for match in img_matches:
            img_tag = match.group()
            if 'alt=' not in img_tag:
                line_num = content[:match.start()].count('\n') + 1
                self.log_issue(
                    category="Accessibility",
                    severity="Minor",
                    file_path=template_path,
                    line_number=line_num,
                    description="Image missing alt attribute",
                    evidence=f"Image tag: {img_tag}",
                    impact="Poor accessibility for screen readers"
                )
                
        # Check for buttons without proper labels
        button_matches = re.finditer(r'<button[^>]*>', content)
        for match in button_matches:
            button_tag = match.group()
            # Look ahead to see if button has text content
            next_content = content[match.end():match.end()+100]
            if not re.search(r'[a-zA-Z]', next_content.split('</button>')[0]):
                if 'aria-label=' not in button_tag and 'title=' not in button_tag:
                    line_num = content[:match.start()].count('\n') + 1
                    self.log_issue(
                        category="Accessibility",
                        severity="Minor", 
                        file_path=template_path,
                        line_number=line_num,
                        description="Button without text or aria-label",
                        evidence=f"Button tag: {button_tag}",
                        impact="Button purpose unclear to screen readers"
                    )
                    
    def _check_responsive_design(self, template_path: Path, content: str, lines: List[str]):
        """Check responsive design issues"""
        # Check for viewport meta tag in head
        if '<head>' in content and 'viewport' not in content:
            self.log_issue(
                category="Responsive Design",
                severity="Major",
                file_path=template_path,
                description="Missing viewport meta tag",
                evidence="No viewport meta tag found in template",
                impact="Poor mobile display"
            )
            
        # Check for hardcoded pixel widths
        px_matches = re.findall(r'width:\s*\d+px', content)
        if len(px_matches) > 5:
            self.log_issue(
                category="Responsive Design", 
                severity="Minor",
                file_path=template_path,
                description=f"Multiple hardcoded pixel widths ({len(px_matches)})",
                evidence=f"Examples: {px_matches[:3]}",
                impact="May not scale well on different screen sizes"
            )
            
    def analyze_css_files(self):
        """Analyze CSS files for issues"""
        css_files = list(self.static_dir.glob("css/*.css"))
        
        for css_path in css_files:
            self._analyze_css_file(css_path)
            
    def _analyze_css_file(self, css_path: Path):
        """Analyze single CSS file"""
        try:
            content = css_path.read_text()
            lines = content.split('\n')
            
            # Check for CSS syntax issues
            brace_count = content.count('{') - content.count('}')
            if brace_count != 0:
                self.log_issue(
                    category="CSS Syntax",
                    severity="Critical",
                    file_path=css_path,
                    description=f"Unmatched braces: {abs(brace_count)} {'opening' if brace_count > 0 else 'closing'}",
                    evidence=f"Opening braces: {content.count('{')}, Closing braces: {content.count('}')}",
                    impact="CSS parsing will fail"
                )
                
            # Check for unused or problematic selectors
            if 'body' in content and css_path.name != 'base.css':
                self.log_issue(
                    category="CSS Structure",
                    severity="Minor",
                    file_path=css_path,
                    description="Component CSS file contains body selector",
                    evidence="Found 'body' selector in component CSS",
                    impact="May cause unintended global styling conflicts"
                )
                
            # Check for CSS Grid/Flexbox browser compatibility
            modern_properties = ['grid-template-columns', 'flex-direction', 'gap']
            for prop in modern_properties:
                if prop in content and 'autoprefixer' not in content:
                    self.log_issue(
                        category="CSS Compatibility",
                        severity="Minor",
                        file_path=css_path,
                        description=f"Modern CSS property '{prop}' without vendor prefixes",
                        evidence=f"Property: {prop}",
                        impact="May not work in older browsers"
                    )
                    
        except Exception as e:
            self.log_issue(
                category="CSS",
                severity="Critical",
                file_path=css_path,
                description=f"Cannot read CSS file: {str(e)}",
                evidence=f"Exception: {str(e)}",
                impact="CSS completely unusable"
            )
            
    def analyze_javascript_files(self):
        """Analyze JavaScript files for issues"""
        js_files = list(self.static_dir.glob("js/*.js"))
        
        for js_path in js_files:
            self._analyze_js_file(js_path)
            
    def _analyze_js_file(self, js_path: Path):
        """Analyze single JavaScript file"""
        try:
            content = js_path.read_text()
            lines = content.split('\n')
            
            # Check for common JavaScript issues
            if 'console.log' in content:
                console_count = content.count('console.log')
                self.log_issue(
                    category="JavaScript",
                    severity="Minor",
                    file_path=js_path,
                    description=f"Debug console.log statements ({console_count})",
                    evidence=f"Found {console_count} console.log calls",
                    impact="Debug output in production"
                )
                
            # Check for jQuery dependency
            if '$(' in content or 'jQuery' in content:
                if 'jquery' not in content.lower():
                    self.log_issue(
                        category="JavaScript Dependencies",
                        severity="Major", 
                        file_path=js_path,
                        description="jQuery usage without explicit dependency",
                        evidence="Found jQuery syntax but no jQuery import/reference",
                        impact="JavaScript will fail if jQuery not loaded"
                    )
                    
            # Check for ES6+ features without transpilation
            es6_features = ['const ', 'let ', '=>', '...', 'async ', 'await ']
            es6_count = sum(content.count(feature) for feature in es6_features)
            if es6_count > 0 and 'babel' not in content.lower():
                self.log_issue(
                    category="JavaScript Compatibility",
                    severity="Minor",
                    file_path=js_path,
                    description=f"ES6+ features without transpilation ({es6_count})",
                    evidence=f"Found modern JavaScript syntax",
                    impact="May not work in older browsers"
                )
                
            # Check for error handling
            if 'try' not in content and ('fetch(' in content or 'XMLHttpRequest' in content):
                self.log_issue(
                    category="JavaScript Error Handling",
                    severity="Major",
                    file_path=js_path,
                    description="AJAX calls without error handling",
                    evidence="Found fetch/XMLHttpRequest without try-catch",
                    impact="Unhandled errors will break functionality"
                )
                
        except Exception as e:
            self.log_issue(
                category="JavaScript",
                severity="Critical",
                file_path=js_path,
                description=f"Cannot read JS file: {str(e)}",
                evidence=f"Exception: {str(e)}",
                impact="JavaScript completely unusable"
            )
            
    def cross_reference_analysis(self):
        """Cross-reference templates with CSS/JS to find mismatches"""
        # Get all template files
        templates = list(self.templates_dir.glob("fabric_detail*.html"))
        
        # Collect CSS classes used in templates
        template_classes = set()
        for template_path in templates:
            try:
                content = template_path.read_text()
                # Find CSS classes
                class_matches = re.findall(r'class="([^"]*)"', content)
                for classes in class_matches:
                    template_classes.update(classes.split())
            except:
                continue
                
        # Check if CSS classes are defined
        css_files = list(self.static_dir.glob("css/*.css"))
        css_classes = set()
        
        for css_path in css_files:
            try:
                content = css_path.read_text()
                # Find CSS class definitions
                css_class_matches = re.findall(r'\.([a-zA-Z0-9_-]+)', content)
                css_classes.update(css_class_matches)
            except:
                continue
                
        # Find classes used in templates but not defined in CSS
        undefined_classes = template_classes - css_classes - {
            'btn', 'card', 'form-control', 'alert', 'badge',  # Bootstrap classes
            'mdi', 'mdi-spin', 'mdi-loading'  # Icon classes
        }
        
        for undefined_class in undefined_classes:
            if undefined_class and len(undefined_class) > 1:  # Skip empty and single chars
                self.log_issue(
                    category="CSS-Template Mismatch",
                    severity="Minor",
                    file_path="templates/",
                    description=f"CSS class '{undefined_class}' used but not defined",
                    evidence=f"Class: {undefined_class}",
                    impact="Styling may not be applied correctly"
                )
                
    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive analysis report"""
        print("\n=== RUNNING COMPREHENSIVE GUI ANALYSIS ===")
        
        # Run all analysis phases
        print("Analyzing fabric detail templates...")
        self.analyze_fabric_detail_templates()
        
        print("Analyzing CSS files...")
        self.analyze_css_files()
        
        print("Analyzing JavaScript files...")
        self.analyze_javascript_files()
        
        print("Cross-referencing templates with CSS/JS...")
        self.cross_reference_analysis()
        
        # Categorize issues
        categories = {}
        severities = {}
        
        for issue in self.issues:
            cat = issue['category']
            sev = issue['severity']
            
            categories[cat] = categories.get(cat, 0) + 1
            severities[sev] = severities.get(sev, 0) + 1
            
        return {
            "executive_summary": {
                "total_issues_found": len(self.issues),
                "critical_issues": severities.get('Critical', 0),
                "major_issues": severities.get('Major', 0),
                "minor_issues": severities.get('Minor', 0),
                "analysis_timestamp": datetime.now().isoformat()
            },
            "issue_breakdown": {
                "by_category": categories,
                "by_severity": severities
            },
            "detailed_issues": self.issues,
            "recommendations": self._generate_recommendations(),
            "architectural_assessment": self._assess_architecture()
        }
        
    def _generate_recommendations(self) -> List[str]:
        """Generate prioritized recommendations"""
        recommendations = []
        
        critical_count = len([i for i in self.issues if i['severity'] == 'Critical'])
        major_count = len([i for i in self.issues if i['severity'] == 'Major'])
        
        if critical_count > 0:
            recommendations.append(f"🚨 URGENT: Fix {critical_count} critical issues that prevent functionality")
            
        if major_count > 0:
            recommendations.append(f"⚠️ HIGH PRIORITY: Address {major_count} major usability issues")
            
        # Category-specific recommendations
        categories = {}
        for issue in self.issues:
            cat = issue['category']
            categories[cat] = categories.get(cat, 0) + 1
            
        if categories.get('Security', 0) > 0:
            recommendations.append("🔒 SECURITY: Address form CSRF and security vulnerabilities")
            
        if categories.get('Template Syntax', 0) > 0:
            recommendations.append("📝 TEMPLATES: Fix template syntax errors that prevent rendering")
            
        if categories.get('JavaScript', 0) > 0:
            recommendations.append("⚡ JAVASCRIPT: Improve error handling and browser compatibility")
            
        if categories.get('CSS', 0) > 0:
            recommendations.append("🎨 STYLING: Fix CSS issues and improve visual consistency")
            
        return recommendations
        
    def _assess_architecture(self) -> Dict[str, str]:
        """Assess overall architectural issues"""
        template_count = len(list(self.templates_dir.glob("fabric_detail*.html")))
        
        assessment = {
            "template_organization": "Good" if template_count <= 3 else "Needs Improvement",
            "css_structure": "Needs Review",  # Based on inline styles found
            "javascript_quality": "Needs Improvement",  # Based on error handling issues
            "overall_maintainability": "Poor" if len(self.issues) > 20 else "Fair"
        }
        
        return assessment


def main():
    """Run static GUI analysis"""
    project_root = Path(__file__).parent.parent
    analyzer = StaticGUIAnalyzer(project_root)
    
    # Generate comprehensive report
    report = analyzer.generate_comprehensive_report()
    
    # Save detailed report
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f"static_gui_analysis_report_{timestamp}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Print executive summary
    print(f"\n=== FABRIC DETAIL PAGE GUI ANALYSIS COMPLETE ===")
    print(f"📊 TOTAL ISSUES FOUND: {report['executive_summary']['total_issues_found']}")
    print(f"🚨 Critical: {report['executive_summary']['critical_issues']}")
    print(f"⚠️  Major: {report['executive_summary']['major_issues']}")  
    print(f"ℹ️  Minor: {report['executive_summary']['minor_issues']}")
    
    print(f"\n📋 ISSUE CATEGORIES:")
    for category, count in report['issue_breakdown']['by_category'].items():
        print(f"   • {category}: {count}")
        
    print(f"\n🏗️ ARCHITECTURAL ASSESSMENT:")
    for aspect, rating in report['architectural_assessment'].items():
        print(f"   • {aspect.replace('_', ' ').title()}: {rating}")
        
    print(f"\n💡 KEY RECOMMENDATIONS:")
    for rec in report['recommendations']:
        print(f"   {rec}")
        
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    return report


if __name__ == "__main__":
    main()