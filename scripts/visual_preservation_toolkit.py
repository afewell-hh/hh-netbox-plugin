#!/usr/bin/env python3
"""
Visual Preservation Toolkit for Fabric Detail Page Enhancement
Ensures zero visual changes during 7-phase enhancement project

Usage:
    python3 visual_preservation_toolkit.py --capture-baseline
    python3 visual_preservation_toolkit.py --validate-preservation
    python3 visual_preservation_toolkit.py --emergency-rollback
"""

import os
import sys
import json
import hashlib
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
import difflib
import shutil

class VisualPreservationToolkit:
    """
    Comprehensive toolkit for preserving visual appearance during enhancement
    """
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.baseline_dir = self.project_root / "visual_baselines"
        self.current_dir = self.project_root / "visual_current" 
        self.results_dir = self.project_root / "visual_results"
        self.css_dir = self.project_root / "netbox_hedgehog" / "static" / "netbox_hedgehog" / "css"
        self.template_dir = self.project_root / "netbox_hedgehog" / "templates" / "netbox_hedgehog"
        
        self.ensure_directories()
        
    def ensure_directories(self):
        """Create necessary directories for testing"""
        for directory in [self.baseline_dir, self.current_dir, self.results_dir]:
            directory.mkdir(exist_ok=True, parents=True)
    
    def capture_baseline(self):
        """Capture comprehensive visual baseline for preservation"""
        print("📸 Capturing Visual Preservation Baseline")
        print("=" * 50)
        
        baseline_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "user": os.getenv("USER", "unknown"),
                "git_commit": self.get_git_commit(),
                "purpose": "Visual preservation baseline for fabric detail page enhancement"
            },
            "css_analysis": self.analyze_css_files(),
            "template_analysis": self.analyze_templates(),
            "critical_classes": self.document_critical_classes(),
            "color_palette": self.extract_color_palette(),
            "layout_structure": self.analyze_layout_structure(),
            "visual_elements": self.catalog_visual_elements()
        }
        
        # Save comprehensive baseline
        baseline_file = self.baseline_dir / "comprehensive_baseline.json"
        with open(baseline_file, "w") as f:
            json.dump(baseline_data, f, indent=2)
        
        # Create human-readable summary
        self.generate_baseline_summary(baseline_data)
        
        print(f"✅ Visual baseline captured successfully")
        print(f"📁 Baseline saved to: {baseline_file}")
        print(f"📋 Summary available at: {self.baseline_dir / 'baseline_summary.md'}")
        
        return baseline_data
    
    def get_git_commit(self):
        """Get current git commit for tracking"""
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, cwd=self.project_root)
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
    
    def analyze_css_files(self):
        """Comprehensive CSS file analysis"""
        css_analysis = {}
        
        css_files = [
            "hedgehog.css",
            "progressive-disclosure.css", 
            "gitops-dashboard.css"
        ]
        
        for css_filename in css_files:
            css_path = self.css_dir / css_filename
            if css_path.exists():
                with open(css_path, 'rb') as f:
                    content = f.read()
                    
                with open(css_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
                
                css_analysis[css_filename] = {
                    "exists": True,
                    "size_bytes": len(content),
                    "line_count": len(text_content.splitlines()),
                    "checksum_md5": hashlib.md5(content).hexdigest(),
                    "checksum_sha256": hashlib.sha256(content).hexdigest(),
                    "critical_selectors": self.extract_critical_selectors(text_content),
                    "color_definitions": self.extract_colors_from_css(text_content),
                    "media_queries": self.extract_media_queries(text_content)
                }
            else:
                css_analysis[css_filename] = {
                    "exists": False,
                    "error": f"CSS file not found at {css_path}"
                }
        
        return css_analysis
    
    def extract_critical_selectors(self, css_content):
        """Extract critical CSS selectors for visual preservation"""
        import re
        
        critical_patterns = [
            r'\.hedgehog-[a-zA-Z0-9-]+',
            r'\.gitops-[a-zA-Z0-9-]+', 
            r'\.fabric-[a-zA-Z0-9-]+',
            r'\.card[a-zA-Z0-9-]*',
            r'\.badge[a-zA-Z0-9-]*',
            r'\.status-[a-zA-Z0-9-]+',
            r'\.section-[a-zA-Z0-9-]+',
            r'\.info-[a-zA-Z0-9-]+'
        ]
        
        selectors = set()
        for pattern in critical_patterns:
            matches = re.findall(pattern, css_content)
            selectors.update(matches)
        
        return sorted(list(selectors))
    
    def extract_colors_from_css(self, css_content):
        """Extract color definitions from CSS"""
        import re
        
        color_patterns = [
            r'#[0-9a-fA-F]{3,8}',  # Hex colors
            r'rgb\([^)]+\)',        # RGB colors
            r'rgba\([^)]+\)',       # RGBA colors
            r'hsl\([^)]+\)',        # HSL colors
            r'var\(--[^)]+\)'       # CSS variables
        ]
        
        colors = set()
        for pattern in color_patterns:
            matches = re.findall(pattern, css_content)
            colors.update(matches)
        
        return sorted(list(colors))
    
    def extract_media_queries(self, css_content):
        """Extract media queries for responsive design analysis"""
        import re
        
        media_pattern = r'@media\s*\([^{]+\)'
        matches = re.findall(media_pattern, css_content)
        return matches
    
    def analyze_templates(self):
        """Analyze template structures for visual preservation"""
        template_analysis = {}
        
        templates = {
            "fabric_detail.html": "fabric_detail.html",
            "fabric_edit.html": "fabric_edit.html", 
            "base.html": "base.html"
        }
        
        for template_name, filename in templates.items():
            template_path = self.template_dir / filename
            if template_path.exists():
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                template_analysis[template_name] = {
                    "exists": True,
                    "size_chars": len(content),
                    "line_count": len(content.splitlines()),
                    "extends_template": self.extract_extends_info(content),
                    "css_includes": self.extract_css_includes(content),
                    "critical_classes": self.extract_template_classes(content),
                    "inline_styles": self.extract_inline_styles(content),
                    "script_includes": self.extract_script_includes(content)
                }
            else:
                template_analysis[template_name] = {
                    "exists": False,
                    "error": f"Template not found at {template_path}"
                }
        
        return template_analysis
    
    def extract_extends_info(self, template_content):
        """Extract template inheritance information"""
        import re
        extends_match = re.search(r'{%\s*extends\s*["\']([^"\']+)["\']', template_content)
        return extends_match.group(1) if extends_match else None
    
    def extract_css_includes(self, template_content):
        """Extract CSS file includes from template"""
        import re
        css_pattern = r'href=["\'][^"\']*\.css[^"\']*["\']'
        matches = re.findall(css_pattern, template_content)
        return [match.strip('href="').strip('href=\'').strip('"').strip("'") for match in matches]
    
    def extract_template_classes(self, template_content):
        """Extract CSS classes used in template"""
        import re
        class_pattern = r'class=["\']([^"\']+)["\']'
        matches = re.findall(class_pattern, template_content)
        
        all_classes = set()
        for match in matches:
            classes = match.split()
            all_classes.update(classes)
        
        # Filter for critical classes
        critical_classes = [cls for cls in all_classes 
                          if any(keyword in cls for keyword in 
                               ['hedgehog', 'gitops', 'fabric', 'card', 'badge', 'section', 'status'])]
        
        return sorted(critical_classes)
    
    def extract_inline_styles(self, template_content):
        """Extract inline styles from template"""
        import re
        style_pattern = r'style=["\']([^"\']+)["\']'
        matches = re.findall(style_pattern, template_content)
        return matches
    
    def extract_script_includes(self, template_content):
        """Extract script includes from template"""
        import re
        script_pattern = r'src=["\'][^"\']*\.js[^"\']*["\']'
        matches = re.findall(script_pattern, template_content)
        return [match.strip('src="').strip('src=\'').strip('"').strip("'") for match in matches]
    
    def document_critical_classes(self):
        """Document all critical CSS classes for preservation"""
        critical_classes = {
            "layout_structure": [
                "hedgehog-wrapper", "hedgehog-header", "hedgehog-content"
            ],
            "card_system": [
                "card", "card-header", "card-body", "card-title"
            ],
            "gitops_components": [
                "gitops-detail-section", "gitops-status-section", "gitops-state-box"
            ],
            "fabric_specific": [
                "fabric-detail", "fabric-edit"
            ],
            "interactive_elements": [
                "status-indicator", "quick-action-btn", "section-toggle", 
                "operation-btn", "drift-spotlight"
            ],
            "information_display": [
                "info-label", "info-value", "info-grid", "info-item"
            ],
            "visual_enhancements": [
                "badge", "timeline-item", "progress-container", "loading-spinner"
            ]
        }
        
        # Validate existence of critical classes in CSS
        css_content = ""
        css_file = self.css_dir / "hedgehog.css"
        if css_file.exists():
            with open(css_file, 'r') as f:
                css_content = f.read()
        
        validated_classes = {}
        for category, classes in critical_classes.items():
            validated_classes[category] = {}
            for class_name in classes:
                class_found = f'.{class_name}' in css_content
                rule_count = css_content.count(f'.{class_name}')
                
                validated_classes[category][class_name] = {
                    "exists_in_css": class_found,
                    "rule_count": rule_count,
                    "critical_for_preservation": True
                }
        
        return validated_classes
    
    def extract_color_palette(self):
        """Extract comprehensive color palette for preservation"""
        return {
            "brand_colors": {
                "primary_gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                "secondary_gradient": "linear-gradient(135deg, #f39c12 0%, #e67e22 100%)"
            },
            "component_colors": {
                "card_shadow": "0 0.125rem 0.25rem rgba(0, 0, 0, 0.075)",
                "card_border": "1px solid rgba(0, 0, 0, 0.125)",
                "header_border": "2px solid var(--bs-primary)"
            },
            "text_colors": {
                "primary_text": "#000",
                "secondary_text": "#212529", 
                "muted_text": "#6c757d",
                "contrast_text": "#f8f9fa"
            },
            "background_colors": {
                "light_background": "#f8f9fa",
                "white_background": "#ffffff",
                "card_header": "var(--bs-light)"
            },
            "border_colors": {
                "light_border": "#e9ecef",
                "medium_border": "#dee2e6", 
                "strong_border": "#adb5bd"
            },
            "status_colors": {
                "success": "#28a745",
                "warning": "#ffc107",
                "danger": "#dc3545",
                "info": "#17a2b8"
            }
        }
    
    def analyze_layout_structure(self):
        """Analyze layout structure for preservation"""
        return {
            "main_container": {
                "class": "hedgehog-wrapper",
                "min_height": "calc(100vh - 200px)",
                "purpose": "Main container for all hedgehog content"
            },
            "header_section": {
                "class": "hedgehog-header",
                "styling": "gradient border-bottom with spacing",
                "purpose": "Branded header section with visual identity"
            },
            "content_cards": {
                "class": "card",
                "features": ["shadow", "border", "rounded corners"],
                "purpose": "Primary content containers"
            },
            "gitops_sections": {
                "class": "gitops-detail-section",
                "styling": "gradient background with left border accent",
                "purpose": "GitOps configuration display areas"
            },
            "responsive_breakpoints": {
                "mobile": "max-width: 768px",
                "tablet": "max-width: 992px", 
                "desktop": "above 992px"
            }
        }
    
    def catalog_visual_elements(self):
        """Catalog all visual elements requiring preservation"""
        return {
            "typography": {
                "headings": "font-weight: 700, enhanced contrast",
                "body_text": "font-weight: 400-500, optimized readability",
                "labels": "font-weight: 700, uppercase with letter-spacing",
                "code_text": "monospace font with enhanced contrast"
            },
            "spacing_system": {
                "card_padding": "2rem for generous content spacing",
                "section_margins": "2rem vertical separation",
                "element_gaps": "1.5rem grid gaps",
                "form_spacing": "1.25rem field separation"
            },
            "shadow_system": {
                "card_shadows": "subtle depth with rgba shadows",
                "hover_effects": "enhanced shadows on interaction",
                "focus_indicators": "outline-based accessibility"
            },
            "animation_system": {
                "transitions": "0.3s ease for smooth interactions",
                "hover_transforms": "translateY(-2px) elevation effects",
                "progress_animations": "linear progress indicators"
            },
            "accessibility_features": {
                "high_contrast": "pure black text on light backgrounds",
                "focus_indicators": "2px solid outline with offset",
                "readable_fonts": "enhanced font weights and sizes"
            }
        }
    
    def generate_baseline_summary(self, baseline_data):
        """Generate human-readable baseline summary"""
        summary_content = f"""# Visual Preservation Baseline Summary

Generated: {baseline_data['metadata']['timestamp']}
Git Commit: {baseline_data['metadata']['git_commit']}

## CSS Files Analysis
"""
        
        for css_file, analysis in baseline_data['css_analysis'].items():
            if analysis.get('exists'):
                summary_content += f"""
### {css_file}
- Size: {analysis['size_bytes']:,} bytes ({analysis['line_count']} lines)
- MD5: {analysis['checksum_md5']}
- Critical Selectors: {len(analysis['critical_selectors'])} found
- Colors: {len(analysis['color_definitions'])} unique colors
- Media Queries: {len(analysis['media_queries'])} responsive breakpoints
"""

        summary_content += "\n## Template Analysis\n"
        for template_name, analysis in baseline_data['template_analysis'].items():
            if analysis.get('exists'):
                summary_content += f"""
### {template_name}
- Size: {analysis['size_chars']:,} characters ({analysis['line_count']} lines) 
- Extends: {analysis['extends_template']}
- CSS Includes: {len(analysis['css_includes'])} files
- Critical Classes: {len(analysis['critical_classes'])} identified
"""

        summary_content += f"""
## Critical Classes Summary
Total Categories: {len(baseline_data['critical_classes'])}
"""
        
        for category, classes in baseline_data['critical_classes'].items():
            validated_count = sum(1 for cls_data in classes.values() if cls_data['exists_in_css'])
            summary_content += f"- {category}: {validated_count}/{len(classes)} classes found in CSS\n"

        summary_content += f"""
## Visual Elements Inventory
- Typography: {len(baseline_data['visual_elements']['typography'])} categories
- Spacing System: {len(baseline_data['visual_elements']['spacing_system'])} definitions
- Color Palette: {len(baseline_data['color_palette'])} categories
- Layout Structure: {len(baseline_data['layout_structure'])} components

## Preservation Requirements
- Zero visual changes tolerance
- Pixel-perfect appearance preservation  
- Comprehensive rollback procedures
- Continuous validation throughout enhancement

## Next Steps
1. Implement changes with visual preservation protocols
2. Run validation after each phase: `python3 visual_preservation_toolkit.py --validate-preservation`
3. Emergency rollback if any visual changes detected
"""

        summary_file = self.baseline_dir / "baseline_summary.md"
        with open(summary_file, "w") as f:
            f.write(summary_content)
    
    def validate_preservation(self):
        """Validate that visual preservation is maintained"""
        print("🔍 Validating Visual Preservation")
        print("=" * 50)
        
        # Check if baseline exists
        baseline_file = self.baseline_dir / "comprehensive_baseline.json"
        if not baseline_file.exists():
            print("❌ No baseline found. Run --capture-baseline first.")
            return False
        
        # Load baseline
        with open(baseline_file, 'r') as f:
            baseline = json.load(f)
        
        # Capture current state
        current_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "git_commit": self.get_git_commit()
            },
            "css_analysis": self.analyze_css_files(),
            "template_analysis": self.analyze_templates(),
            "critical_classes": self.document_critical_classes()
        }
        
        # Perform comprehensive comparison
        validation_results = {
            "css_validation": self.validate_css_preservation(baseline["css_analysis"], current_data["css_analysis"]),
            "template_validation": self.validate_template_preservation(baseline["template_analysis"], current_data["template_analysis"]),
            "class_validation": self.validate_class_preservation(baseline["critical_classes"], current_data["critical_classes"])
        }
        
        # Determine overall validation status
        validation_passed = all([
            validation_results["css_validation"]["passed"],
            validation_results["template_validation"]["passed"],
            validation_results["class_validation"]["passed"]
        ])
        
        # Generate validation report
        report = {
            "validation_passed": validation_passed,
            "timestamp": datetime.now().isoformat(),
            "baseline_commit": baseline["metadata"]["git_commit"],
            "current_commit": current_data["metadata"]["git_commit"],
            "results": validation_results
        }
        
        # Save detailed report
        report_file = self.results_dir / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        # Display results
        print("📋 Validation Results:")
        print(f"CSS Validation: {'✅ PASSED' if validation_results['css_validation']['passed'] else '❌ FAILED'}")
        print(f"Template Validation: {'✅ PASSED' if validation_results['template_validation']['passed'] else '❌ FAILED'}")
        print(f"Class Validation: {'✅ PASSED' if validation_results['class_validation']['passed'] else '❌ FAILED'}")
        print()
        print(f"Overall Result: {'✅ VISUAL PRESERVATION MAINTAINED' if validation_passed else '❌ VISUAL CHANGES DETECTED'}")
        print(f"📁 Detailed report: {report_file}")
        
        if not validation_passed:
            print("\n🚨 VISUAL PRESERVATION FAILURE DETECTED")
            print("📋 Issues found:")
            
            for category, result in validation_results.items():
                if not result["passed"] and result.get("issues"):
                    print(f"\n{category.upper()}:")
                    for issue in result["issues"][:5]:  # Show first 5 issues
                        print(f"  - {issue}")
            
            print("\n💡 Recommended actions:")
            print("  1. Review changes that may have affected visual appearance")
            print("  2. Run emergency rollback: python3 visual_preservation_toolkit.py --emergency-rollback")
            print("  3. Implement changes using visual preservation protocols")
        
        return validation_passed
    
    def validate_css_preservation(self, baseline_css, current_css):
        """Validate CSS file preservation"""
        issues = []
        
        for css_file, baseline_info in baseline_css.items():
            if css_file in current_css:
                current_info = current_css[css_file]
                
                if baseline_info.get("exists") and current_info.get("exists"):
                    # Check for changes
                    if baseline_info["checksum_md5"] != current_info["checksum_md5"]:
                        issues.append(f"CSS file modified: {css_file}")
                    
                    if baseline_info["line_count"] != current_info["line_count"]:
                        issues.append(f"Line count changed in {css_file}: {baseline_info['line_count']} -> {current_info['line_count']}")
                    
                    # Check critical selectors
                    baseline_selectors = set(baseline_info.get("critical_selectors", []))
                    current_selectors = set(current_info.get("critical_selectors", []))
                    
                    missing_selectors = baseline_selectors - current_selectors
                    if missing_selectors:
                        issues.append(f"Missing critical selectors in {css_file}: {list(missing_selectors)[:3]}")
                
                elif baseline_info.get("exists") and not current_info.get("exists"):
                    issues.append(f"CSS file deleted: {css_file}")
            else:
                issues.append(f"CSS file missing from analysis: {css_file}")
        
        return {"passed": len(issues) == 0, "issues": issues}
    
    def validate_template_preservation(self, baseline_templates, current_templates):
        """Validate template structure preservation"""
        issues = []
        
        for template_name, baseline_info in baseline_templates.items():
            if template_name in current_templates:
                current_info = current_templates[template_name]
                
                if baseline_info.get("exists") and current_info.get("exists"):
                    # Check critical structure elements
                    structure_checks = [
                        ("extends_template", "Template inheritance"),
                        ("css_includes", "CSS includes"),
                        ("critical_classes", "Critical CSS classes")
                    ]
                    
                    for key, description in structure_checks:
                        baseline_value = baseline_info.get(key)
                        current_value = current_info.get(key)
                        
                        if baseline_value != current_value:
                            issues.append(f"{description} changed in {template_name}")
                
                elif baseline_info.get("exists") and not current_info.get("exists"):
                    issues.append(f"Template deleted: {template_name}")
            else:
                issues.append(f"Template missing from analysis: {template_name}")
        
        return {"passed": len(issues) == 0, "issues": issues}
    
    def validate_class_preservation(self, baseline_classes, current_classes):
        """Validate critical CSS class preservation"""
        issues = []
        
        for category, baseline_category_classes in baseline_classes.items():
            if category in current_classes:
                current_category_classes = current_classes[category]
                
                for class_name, baseline_class_info in baseline_category_classes.items():
                    if class_name in current_category_classes:
                        current_class_info = current_category_classes[class_name]
                        
                        # Check if class still exists in CSS
                        if baseline_class_info["exists_in_css"] and not current_class_info["exists_in_css"]:
                            issues.append(f"Critical class removed from CSS: {class_name}")
                        
                        # Check rule count changes (may indicate modification)
                        baseline_count = baseline_class_info["rule_count"]
                        current_count = current_class_info["rule_count"]
                        
                        if baseline_count != current_count:
                            issues.append(f"Rule count changed for {class_name}: {baseline_count} -> {current_count}")
                    else:
                        issues.append(f"Critical class missing from analysis: {class_name}")
            else:
                issues.append(f"Critical class category missing: {category}")
        
        return {"passed": len(issues) == 0, "issues": issues}
    
    def emergency_rollback(self):
        """Perform emergency rollback to preserve visual appearance"""
        print("🚨 EMERGENCY VISUAL PRESERVATION ROLLBACK")
        print("=" * 50)
        
        # Confirm rollback
        response = input("⚠️  This will rollback CSS and template changes. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Rollback cancelled")
            return False
        
        try:
            # Create backup of current state
            backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = self.results_dir / f"emergency_backup_{backup_timestamp}"
            backup_dir.mkdir(exist_ok=True)
            
            print(f"💾 Creating backup of current state: {backup_dir}")
            
            # Backup CSS files
            css_backup_dir = backup_dir / "css"
            css_backup_dir.mkdir(exist_ok=True)
            for css_file in self.css_dir.glob("*.css"):
                shutil.copy2(css_file, css_backup_dir / css_file.name)
            
            # Backup templates
            template_backup_dir = backup_dir / "templates"
            template_backup_dir.mkdir(exist_ok=True)
            for template_file in self.template_dir.glob("*.html"):
                shutil.copy2(template_file, template_backup_dir / template_file.name)
            
            # Git stash current changes
            print("📦 Stashing current changes...")
            subprocess.run(['git', 'stash', 'push', '-m', f'Emergency rollback backup {backup_timestamp}'], 
                         cwd=self.project_root, check=True)
            
            # Reset to last known good state
            print("🔄 Resetting to last known good visual state...")
            subprocess.run(['git', 'checkout', 'HEAD~1', '--', 'netbox_hedgehog/static/netbox_hedgehog/css/'], 
                         cwd=self.project_root, check=True)
            subprocess.run(['git', 'checkout', 'HEAD~1', '--', 'netbox_hedgehog/templates/netbox_hedgehog/'], 
                         cwd=self.project_root, check=True)
            
            # Commit rollback
            subprocess.run(['git', 'add', '.'], cwd=self.project_root, check=True)
            subprocess.run(['git', 'commit', '-m', f'Emergency visual preservation rollback - {backup_timestamp}'], 
                         cwd=self.project_root, check=True)
            
            print("✅ Emergency rollback completed successfully")
            print(f"💾 Current state backed up to: {backup_dir}")
            print("🔍 Recommend re-running validation to confirm visual preservation")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Rollback failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error during rollback: {e}")
            return False
    
    def quick_health_check(self):
        """Perform quick visual preservation health check"""
        print("⚡ Quick Visual Preservation Health Check")
        print("=" * 40)
        
        # Check critical files exist
        critical_files = [
            self.css_dir / "hedgehog.css",
            self.template_dir / "fabric_detail.html",
            self.template_dir / "fabric_edit.html"
        ]
        
        files_ok = True
        for file_path in critical_files:
            if file_path.exists():
                print(f"✅ {file_path.name}")
            else:
                print(f"❌ {file_path.name} - FILE MISSING")
                files_ok = False
        
        # Check git status
        try:
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True, cwd=self.project_root)
            modified_files = [line for line in result.stdout.splitlines() 
                            if any(keyword in line for keyword in ['css', 'html', 'templates'])]
            
            if modified_files:
                print(f"⚠️  {len(modified_files)} visual files modified")
                for file_line in modified_files[:3]:
                    print(f"   {file_line}")
            else:
                print("✅ No visual file modifications detected")
        
        except:
            print("⚠️  Could not check git status")
        
        # Quick CSS validation
        css_file = self.css_dir / "hedgehog.css"
        if css_file.exists():
            with open(css_file, 'r') as f:
                content = f.read()
            
            critical_classes = ['hedgehog-wrapper', 'hedgehog-header', 'card', 'gitops-detail-section']
            missing_classes = []
            
            for class_name in critical_classes:
                if f'.{class_name}' not in content:
                    missing_classes.append(class_name)
            
            if missing_classes:
                print(f"⚠️  Missing critical classes: {missing_classes}")
            else:
                print("✅ Critical CSS classes present")
        
        overall_health = files_ok and not missing_classes
        print(f"\n📊 Overall Health: {'✅ GOOD' if overall_health else '⚠️  ISSUES DETECTED'}")
        
        return overall_health

def main():
    parser = argparse.ArgumentParser(description="Visual Preservation Toolkit for Fabric Detail Page Enhancement")
    parser.add_argument('--capture-baseline', action='store_true', 
                       help='Capture comprehensive visual baseline')
    parser.add_argument('--validate-preservation', action='store_true',
                       help='Validate visual preservation against baseline')
    parser.add_argument('--emergency-rollback', action='store_true',
                       help='Emergency rollback to preserve visual appearance')
    parser.add_argument('--health-check', action='store_true',
                       help='Quick visual preservation health check')
    
    args = parser.parse_args()
    
    toolkit = VisualPreservationToolkit()
    
    if args.capture_baseline:
        toolkit.capture_baseline()
    elif args.validate_preservation:
        success = toolkit.validate_preservation()
        sys.exit(0 if success else 1)
    elif args.emergency_rollback:
        success = toolkit.emergency_rollback()
        sys.exit(0 if success else 1)
    elif args.health_check:
        success = toolkit.quick_health_check()
        sys.exit(0 if success else 1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()