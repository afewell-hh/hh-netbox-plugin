#!/usr/bin/env python3
"""
GUI Test Runner - Comprehensive Test Execution Script

This script provides a user-friendly interface for running the complete GUI test suite
with advanced options for test selection, parallel execution, reporting, and failure analysis.

Features:
- Single-command execution of all GUI tests
- Test selection by type, tags, or specific files
- Multiple browser support (Chromium, Firefox, WebKit)
- Parallel and serial execution modes
- Comprehensive HTML report generation
- Failure analysis and retry mechanisms
- CI/CD integration support
- Interactive test selection mode

Usage:
    python run_gui_tests.py                    # Run all tests
    python run_gui_tests.py --browser firefox  # Use Firefox
    python run_gui_tests.py --parallel 4       # Use 4 workers
    python run_gui_tests.py --tags "slow"      # Run only slow tests
    python run_gui_tests.py --interactive      # Interactive mode
    python run_gui_tests.py --help             # Show full help
"""

import argparse
import os
import sys
import subprocess
import json
import time
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import webbrowser


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class GUITestRunner:
    """Main test runner class with comprehensive execution capabilities"""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent.parent
        self.test_dir = self.script_dir / "tests"
        self.reports_dir = self.script_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Available test files
        self.test_files = {
            'dashboard': 'test_dashboard_pages.py',
            'list_views': 'test_list_views.py', 
            'detail_views': 'test_detail_views.py',
            'create_forms': 'test_create_forms.py',
            'edit_forms': 'test_edit_forms.py',
            'git_sync': 'test_git_sync_ui.py',
            'fabric_workflows': 'test_fabric_workflows.py',
            'dynamic_content': 'test_dynamic_content.py',
            'permission_ui': 'test_permission_ui.py',
            'error_handling': 'test_error_handling.py',
            'visual_regression': 'test_visual_regression.py'
        }
        
        # Test categories and tags
        self.test_categories = {
            'basic': ['dashboard', 'list_views', 'detail_views'],
            'forms': ['create_forms', 'edit_forms'],
            'advanced': ['git_sync', 'fabric_workflows', 'dynamic_content'],
            'validation': ['permission_ui', 'error_handling', 'visual_regression']
        }

    def print_header(self, title: str):
        """Print formatted header"""
        width = 70
        print(f"\n{Colors.HEADER}{'='*width}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{title.center(width)}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*width}{Colors.ENDC}")

    def print_status(self, message: str, status: str = "info"):
        """Print status message with color coding"""
        color_map = {
            'info': Colors.BLUE,
            'success': Colors.GREEN,
            'warning': Colors.WARNING,
            'error': Colors.FAIL
        }
        color = color_map.get(status, Colors.BLUE)
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {color}{message}{Colors.ENDC}")

    def validate_environment(self) -> bool:
        """Validate test environment and dependencies"""
        self.print_status("Validating test environment...", "info")
        
        errors = []
        
        # Check if we're in the correct directory
        if not (self.script_dir / "pytest.ini").exists():
            errors.append("pytest.ini not found - are you in the correct directory?")
        
        # Check for test files
        missing_tests = []
        for name, filename in self.test_files.items():
            if not (self.test_dir / filename).exists():
                missing_tests.append(filename)
        
        if missing_tests:
            errors.append(f"Missing test files: {', '.join(missing_tests)}")
        
        # Check Python dependencies
        try:
            import pytest
            import playwright
            import django
        except ImportError as e:
            errors.append(f"Missing Python dependency: {e}")
        
        # Check Playwright browsers
        try:
            result = subprocess.run(
                ["python3", "-m", "playwright", "install", "--dry-run"],
                capture_output=True, text=True, timeout=10
            )
            if "chromium" not in result.stdout.lower():
                errors.append("Playwright browsers may not be installed")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            errors.append("Playwright CLI not available")
        
        if errors:
            self.print_status("Environment validation failed:", "error")
            for error in errors:
                print(f"  - {Colors.FAIL}{error}{Colors.ENDC}")
            return False
        
        self.print_status("Environment validation passed", "success")
        return True

    def get_test_selection(self, args) -> Tuple[List[str], Dict[str, str]]:
        """Determine which tests to run based on arguments"""
        selected_tests = []
        pytest_args = {}
        
        if args.tests:
            # Specific test files requested
            for test in args.tests:
                if test in self.test_files:
                    selected_tests.append(self.test_files[test])
                elif test.endswith('.py'):
                    selected_tests.append(test)
                else:
                    self.print_status(f"Unknown test: {test}", "warning")
        
        elif args.category:
            # Test category requested
            if args.category in self.test_categories:
                for test_name in self.test_categories[args.category]:
                    selected_tests.append(self.test_files[test_name])
            else:
                self.print_status(f"Unknown category: {args.category}", "error")
                return [], {}
        
        else:
            # Run all tests
            selected_tests = list(self.test_files.values())
        
        # Add marker selection
        if args.tags:
            pytest_args['markers'] = f'-m "{args.tags}"'
        
        return selected_tests, pytest_args

    def build_pytest_command(self, tests: List[str], args, pytest_args: Dict[str, str]) -> List[str]:
        """Build the pytest command with all options"""
        cmd = ["python3", "-m", "pytest"]
        
        # Add test files
        cmd.extend([str(self.test_dir / test) for test in tests])
        
        # Browser selection
        if args.browser != "chromium":
            cmd.extend(["--browser", args.browser])
        
        # Execution mode
        if args.serial:
            cmd.append("--dist=no")
        elif args.parallel and args.parallel > 1:
            cmd.extend(["--numprocesses", str(args.parallel)])
        
        # Verbosity
        if args.verbose >= 2:
            cmd.append("-vvs")
        elif args.verbose == 1:
            cmd.append("-v")
        elif args.quiet:
            cmd.append("-q")
        
        # Output options
        if args.tb_style:
            cmd.extend(["--tb", args.tb_style])
        
        if args.durations:
            cmd.extend(["--durations", str(args.durations)])
        
        # Retry failed tests
        if args.retry_failed:
            cmd.append("--lf")
        
        # Stop on first failure
        if args.fail_fast:
            cmd.append("-x")
        
        # Screenshots and videos
        if args.screenshots:
            cmd.append("--screenshot=on")
        
        if args.record_video:
            cmd.append("--video=on")
        
        # Coverage
        if args.coverage:
            cmd.extend([
                "--cov=netbox_hedgehog",
                "--cov-report=html:reports/coverage_html",
                "--cov-report=term-missing"
            ])
        
        # HTML report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_report = self.reports_dir / f"report_{timestamp}.html"
        cmd.extend(["--html", str(html_report), "--self-contained-html"])
        
        # JUnit XML
        if args.junit_xml:
            cmd.extend(["--junitxml", str(self.reports_dir / "test-results.xml")])
        
        # Add marker selection
        if 'markers' in pytest_args:
            cmd.append(pytest_args['markers'])
        
        # Additional pytest args
        if args.pytest_args:
            cmd.extend(args.pytest_args.split())
        
        return cmd, html_report

    def run_tests(self, cmd: List[str], html_report: Path) -> Tuple[int, Dict[str, any]]:
        """Execute the test command and collect results"""
        self.print_status(f"Executing: {' '.join(cmd)}", "info")
        
        start_time = time.time()
        
        try:
            # Run tests
            result = subprocess.run(
                cmd, 
                cwd=self.script_dir,
                env={**os.environ, "PYTEST_CURRENT_TEST": "1"},
                text=True
            )
            
            execution_time = time.time() - start_time
            
            # Collect results
            results = {
                'exit_code': result.returncode,
                'execution_time': execution_time,
                'html_report': html_report,
                'timestamp': datetime.now().isoformat()
            }
            
            return result.returncode, results
            
        except KeyboardInterrupt:
            self.print_status("Test execution interrupted by user", "warning")
            return 130, {'exit_code': 130, 'interrupted': True}
        
        except Exception as e:
            self.print_status(f"Test execution failed: {e}", "error")
            return 1, {'exit_code': 1, 'error': str(e)}

    def analyze_results(self, results: Dict[str, any]) -> None:
        """Analyze and report test results"""
        self.print_header("Test Results Analysis")
        
        exit_code = results['exit_code']
        
        if exit_code == 0:
            self.print_status("All tests passed successfully!", "success")
        elif exit_code == 130:
            self.print_status("Test execution was interrupted", "warning")
            return
        else:
            self.print_status("Some tests failed or encountered errors", "error")
        
        # Execution time
        if 'execution_time' in results:
            duration = results['execution_time']
            self.print_status(f"Execution time: {duration:.2f} seconds", "info")
        
        # HTML report
        if 'html_report' in results and results['html_report'].exists():
            self.print_status(f"HTML report generated: {results['html_report']}", "success")
            
            # Open report in browser if requested
            if hasattr(self, 'open_report') and self.open_report:
                try:
                    webbrowser.open(f"file://{results['html_report'].absolute()}")
                except Exception:
                    pass  # Fail silently if can't open browser
        
        # Coverage report
        coverage_dir = self.reports_dir / "coverage_html"
        if coverage_dir.exists():
            self.print_status(f"Coverage report: {coverage_dir}/index.html", "info")

    def interactive_mode(self) -> argparse.Namespace:
        """Interactive test selection mode"""
        self.print_header("Interactive Test Selection")
        
        print("Available test categories:")
        for i, (cat, tests) in enumerate(self.test_categories.items(), 1):
            print(f"  {i}. {Colors.CYAN}{cat}{Colors.ENDC} ({len(tests)} tests)")
        
        print(f"  {len(self.test_categories) + 1}. {Colors.CYAN}all{Colors.ENDC} (all tests)")
        print(f"  {len(self.test_categories) + 2}. {Colors.CYAN}custom{Colors.ENDC} (select individual tests)")
        
        while True:
            try:
                choice = input(f"\nSelect category [{Colors.GREEN}1-{len(self.test_categories) + 2}{Colors.ENDC}]: ").strip()
                
                if not choice:
                    continue
                
                choice_num = int(choice)
                
                if 1 <= choice_num <= len(self.test_categories):
                    category = list(self.test_categories.keys())[choice_num - 1]
                    args = argparse.Namespace(category=category, tests=None)
                    break
                elif choice_num == len(self.test_categories) + 1:
                    args = argparse.Namespace(category=None, tests=None)
                    break
                elif choice_num == len(self.test_categories) + 2:
                    args = self._select_individual_tests()
                    break
                else:
                    print(f"{Colors.FAIL}Invalid choice. Please try again.{Colors.ENDC}")
                    
            except (ValueError, KeyboardInterrupt):
                print(f"{Colors.FAIL}Invalid input. Please try again.{Colors.ENDC}")
        
        # Ask for execution options
        args.browser = input(f"Browser [{Colors.GREEN}chromium{Colors.ENDC}/firefox/webkit]: ").strip() or "chromium"
        args.parallel = int(input(f"Parallel workers [{Colors.GREEN}auto{Colors.ENDC}]: ").strip() or "0")
        args.verbose = 1 if input(f"Verbose output? [{Colors.GREEN}y{Colors.ENDC}/n]: ").strip().lower() != 'n' else 0
        
        # Set defaults for other options
        args.serial = False
        args.quiet = False
        args.tb_style = "short"
        args.durations = 10
        args.retry_failed = False
        args.fail_fast = False
        args.screenshots = True
        args.record_video = False
        args.coverage = False
        args.junit_xml = False
        args.pytest_args = ""
        args.tags = ""
        args.open_report = True
        
        return args

    def _select_individual_tests(self) -> argparse.Namespace:
        """Select individual test files"""
        print("\nAvailable test files:")
        for i, (name, filename) in enumerate(self.test_files.items(), 1):
            print(f"  {i:2d}. {Colors.CYAN}{name}{Colors.ENDC} ({filename})")
        
        while True:
            selection = input(f"\nSelect tests [{Colors.GREEN}1-{len(self.test_files)}, comma-separated{Colors.ENDC}]: ").strip()
            
            try:
                indices = [int(x.strip()) for x in selection.split(',') if x.strip()]
                selected_tests = []
                
                for idx in indices:
                    if 1 <= idx <= len(self.test_files):
                        test_name = list(self.test_files.keys())[idx - 1]
                        selected_tests.append(test_name)
                    else:
                        raise ValueError(f"Invalid selection: {idx}")
                
                return argparse.Namespace(category=None, tests=selected_tests)
                
            except ValueError as e:
                print(f"{Colors.FAIL}Invalid selection: {e}. Please try again.{Colors.ENDC}")

    def main(self):
        """Main execution function"""
        parser = argparse.ArgumentParser(
            description="Comprehensive GUI Test Runner for NetBox Hedgehog Plugin",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s                              # Run all tests
  %(prog)s --category basic             # Run basic tests only
  %(prog)s --tests dashboard git_sync   # Run specific test files
  %(prog)s --browser firefox --parallel 4  # Firefox with 4 workers
  %(prog)s --tags "not slow"            # Exclude slow tests
  %(prog)s --interactive                # Interactive mode
  %(prog)s --retry-failed --fail-fast   # Retry failed, stop on first failure
            """
        )
        
        # Test selection
        selection = parser.add_argument_group('Test Selection')
        selection.add_argument('--tests', nargs='*', metavar='TEST', 
                             help='Specific test files to run')
        selection.add_argument('--category', choices=list(self.test_categories.keys()),
                             help='Test category to run')
        selection.add_argument('--tags', metavar='EXPRESSION',
                             help='Pytest marker expression (e.g., "slow", "not slow")')
        selection.add_argument('--interactive', '-i', action='store_true',
                             help='Interactive test selection mode')
        
        # Execution options
        execution = parser.add_argument_group('Execution Options')
        execution.add_argument('--browser', choices=['chromium', 'firefox', 'webkit'],
                             default='chromium', help='Browser to use')
        execution.add_argument('--parallel', type=int, metavar='N',
                             help='Number of parallel workers (0 for auto)')
        execution.add_argument('--serial', action='store_true',
                             help='Run tests serially (no parallelism)')
        execution.add_argument('--retry-failed', action='store_true',
                             help='Only run tests that failed last time')
        execution.add_argument('--fail-fast', '-x', action='store_true',
                             help='Stop on first failure')
        
        # Output and reporting
        output = parser.add_argument_group('Output and Reporting')
        output.add_argument('--verbose', '-v', action='count', default=0,
                          help='Verbose output (-v, -vv for more verbose)')
        output.add_argument('--quiet', '-q', action='store_true',
                          help='Quiet output')
        output.add_argument('--tb-style', choices=['short', 'long', 'auto', 'line', 'native'],
                          default='short', help='Traceback style')
        output.add_argument('--durations', type=int, metavar='N', default=10,
                          help='Show N slowest test durations (0 to disable)')
        output.add_argument('--screenshots', action='store_true',
                          help='Enable screenshot capture on failure')
        output.add_argument('--record-video', action='store_true',
                          help='Record video of test execution')
        output.add_argument('--coverage', action='store_true',
                          help='Generate code coverage report')
        output.add_argument('--junit-xml', action='store_true',
                          help='Generate JUnit XML report')
        output.add_argument('--open-report', action='store_true',
                          help='Open HTML report in browser after completion')
        
        # Advanced options
        advanced = parser.add_argument_group('Advanced Options')
        advanced.add_argument('--pytest-args', metavar='ARGS',
                            help='Additional arguments to pass to pytest')
        advanced.add_argument('--no-validation', action='store_true',
                            help='Skip environment validation')
        
        # Parse arguments
        args = parser.parse_args()
        
        # Handle interactive mode
        if args.interactive:
            args = self.interactive_mode()
        
        # Store open_report flag
        self.open_report = getattr(args, 'open_report', False)
        
        # Print header
        self.print_header("NetBox Hedgehog Plugin - GUI Test Runner")
        
        # Validate environment
        if not args.no_validation and not self.validate_environment():
            return 1
        
        # Get test selection
        tests, pytest_args = self.get_test_selection(args)
        if not tests:
            self.print_status("No tests selected", "error")
            return 1
        
        self.print_status(f"Selected {len(tests)} test files", "info")
        for test in tests:
            print(f"  - {Colors.CYAN}{test}{Colors.ENDC}")
        
        # Build pytest command
        cmd, html_report = self.build_pytest_command(tests, args, pytest_args)
        
        # Run tests
        exit_code, results = self.run_tests(cmd, html_report)
        
        # Analyze results
        self.analyze_results(results)
        
        # Final status
        if exit_code == 0:
            self.print_status("Test execution completed successfully", "success")
        elif exit_code == 130:
            self.print_status("Test execution was interrupted", "warning")
        else:
            self.print_status("Test execution completed with failures", "error")
        
        return exit_code


if __name__ == '__main__':
    runner = GUITestRunner()
    try:
        sys.exit(runner.main())
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Test runner interrupted by user{Colors.ENDC}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.FAIL}Test runner failed: {e}{Colors.ENDC}")
        sys.exit(1)