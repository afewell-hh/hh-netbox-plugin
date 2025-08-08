"""
TDD Test Validity Framework - Issue #9 Implementation

Implements the 5-phase validation protocol, triangulation logic, and property-based
testing as mandated by Issue #9 for bulletproof TDD test validity.

This framework ensures every test proves its validity before claiming success.
"""

import json
import time
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ValidationEvidence:
    """Evidence of validation approach used"""
    test_name: str
    validation_phase: str
    approach_used: str
    known_good_data: Any
    expected_outcome: Any
    actual_outcome: Any
    validation_logic: str
    evidence_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TestValidityReport:
    """Complete test validity documentation"""
    test_name: str
    phases_completed: List[str] = field(default_factory=list)
    evidence: List[ValidationEvidence] = field(default_factory=list)
    triangulation_methods: List[str] = field(default_factory=list)
    properties_tested: List[str] = field(default_factory=list)
    gui_validations: List[str] = field(default_factory=list)
    failure_modes_proven: List[str] = field(default_factory=list)
    
    def to_json(self) -> str:
        """Serialize report to JSON for documentation"""
        return json.dumps(self.__dict__, default=str, indent=2)


class TDDValidityFramework:
    """
    Core framework implementing Issue #9 TDD test validity requirements.
    
    Enforces 5-phase validation protocol:
    1. Logic Validation - Test with known-good data you CAN validate
    2. Failure Mode - Prove test fails when it should
    3. Property-Based - Test universal properties (conservation, idempotency)
    4. GUI Observable - Validate through actual GUI elements
    5. Documentation - Document validation approach used
    """
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.report = TestValidityReport(test_name=test_name)
        self._load_env_credentials()
    
    def _load_env_credentials(self):
        """Load credentials from .env file as mandated by Issue #9"""
        env_file = '/home/ubuntu/cc/hedgehog-netbox-plugin/.env'
        self.credentials = {}
        
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        self.credentials[key] = value.strip('"')
        else:
            raise EnvironmentError("ZERO TOLERANCE VIOLATION: .env file not found - credentials not loaded")
    
    # PHASE 1: Logic Validation
    def validate_logic_with_known_good_data(self, 
                                           test_function: Callable,
                                           known_good_input: Any,
                                           expected_output: Any,
                                           validation_logic: str) -> bool:
        """
        Phase 1: Validate test logic using known-good data that can be verified.
        
        This is the cornerstone of valid testing - prove your test logic works
        with data you can independently validate.
        """
        try:
            actual_output = test_function(known_good_input)
            
            # Document the validation evidence
            evidence = ValidationEvidence(
                test_name=self.test_name,
                validation_phase="Logic Validation",
                approach_used="Known-good data verification",
                known_good_data=known_good_input,
                expected_outcome=expected_output,
                actual_outcome=actual_output,
                validation_logic=validation_logic
            )
            
            self.report.evidence.append(evidence)
            self.report.phases_completed.append("Logic Validation")
            
            # The actual validation
            is_valid = (actual_output == expected_output)
            
            if not is_valid:
                raise AssertionError(
                    f"LOGIC VALIDATION FAILED: Expected {expected_output}, got {actual_output}\n"
                    f"Logic: {validation_logic}\n"
                    f"Known-good input: {known_good_input}"
                )
            
            return True
            
        except Exception as e:
            raise AssertionError(f"Phase 1 Logic Validation failed: {e}")
    
    # PHASE 2: Failure Mode Testing
    def prove_test_fails_appropriately(self,
                                     test_function: Callable,
                                     invalid_input: Any,
                                     expected_failure_type: type,
                                     failure_description: str) -> bool:
        """
        Phase 2: Prove the test fails when it should fail.
        
        Critical for test validity - a test that never fails is worthless.
        """
        try:
            # Test should fail with invalid input
            result = test_function(invalid_input)
            
            # If we get here without exception, the test didn't fail as expected
            raise AssertionError(
                f"FAILURE MODE TEST FAILED: Test should have failed with {expected_failure_type.__name__} "
                f"for input {invalid_input}, but returned: {result}"
            )
            
        except expected_failure_type as e:
            # This is expected - test correctly failed
            evidence = ValidationEvidence(
                test_name=self.test_name,
                validation_phase="Failure Mode",
                approach_used="Intentional failure testing",
                known_good_data=invalid_input,
                expected_outcome=f"Failure: {expected_failure_type.__name__}",
                actual_outcome=f"Failed correctly: {str(e)[:100]}",
                validation_logic=failure_description
            )
            
            self.report.evidence.append(evidence)
            self.report.phases_completed.append("Failure Mode")
            self.report.failure_modes_proven.append(failure_description)
            
            return True
            
        except Exception as e:
            raise AssertionError(
                f"Phase 2 Failure Mode failed: Expected {expected_failure_type.__name__}, "
                f"got {type(e).__name__}: {e}"
            )
    
    # PHASE 3: Property-Based Testing
    def test_universal_property(self,
                               operation: Callable,
                               property_name: str,
                               property_test: Callable,
                               test_inputs: List[Any]) -> bool:
        """
        Phase 3: Test universal properties that must always be true.
        
        Examples:
        - Idempotency: f(f(x)) == f(x)
        - Conservation: count_before == count_after for certain operations
        - Ordering: sorted(list) should always be in order
        """
        for input_data in test_inputs:
            try:
                result = operation(input_data)
                property_holds = property_test(input_data, result)
                
                if not property_holds:
                    raise AssertionError(
                        f"Universal property '{property_name}' violated for input: {input_data}\n"
                        f"Operation result: {result}"
                    )
                    
            except Exception as e:
                raise AssertionError(f"Property-based test failed for {property_name}: {e}")
        
        # Document successful property testing
        evidence = ValidationEvidence(
            test_name=self.test_name,
            validation_phase="Property-Based",
            approach_used=f"Universal property: {property_name}",
            known_good_data=test_inputs,
            expected_outcome=f"Property {property_name} holds for all inputs",
            actual_outcome="Property verified for all test inputs",
            validation_logic=f"Property test function validates {property_name}"
        )
        
        self.report.evidence.append(evidence)
        self.report.phases_completed.append("Property-Based")
        self.report.properties_tested.append(property_name)
        
        return True
    
    # PHASE 4: GUI Observable Outcomes
    def validate_gui_outcome(self,
                           gui_test_client,
                           gui_operation: Callable,
                           expected_gui_elements: List[str],
                           gui_validation_description: str) -> bool:
        """
        Phase 4: Validate through actual GUI elements - mandatory per Issue #9.
        
        Every test must have observable GUI outcomes that can be verified.
        """
        try:
            # Execute the GUI operation
            response = gui_operation(gui_test_client)
            
            # Validate expected GUI elements are present
            missing_elements = []
            
            for element in expected_gui_elements:
                # Use BeautifulSoup to search for elements
                if hasattr(response, 'soup') and response.soup:
                    # Search for element by text content, ID, class, or tag
                    found = (response.soup.find(string=element) or 
                           response.soup.find(id=element) or
                           response.soup.find(class_=element) or
                           response.soup.find(element))
                    
                    if not found:
                        missing_elements.append(element)
                else:
                    # Fall back to basic text search
                    if element not in response.content.decode('utf-8', errors='ignore'):
                        missing_elements.append(element)
            
            if missing_elements:
                raise AssertionError(
                    f"GUI validation failed - missing elements: {missing_elements}\n"
                    f"Expected elements: {expected_gui_elements}\n"
                    f"Validation description: {gui_validation_description}"
                )
            
            # Document GUI validation success
            evidence = ValidationEvidence(
                test_name=self.test_name,
                validation_phase="GUI Observable",
                approach_used="GUI element verification",
                known_good_data=expected_gui_elements,
                expected_outcome="All GUI elements present",
                actual_outcome=f"All {len(expected_gui_elements)} elements found",
                validation_logic=gui_validation_description
            )
            
            self.report.evidence.append(evidence)
            self.report.phases_completed.append("GUI Observable")
            self.report.gui_validations.append(gui_validation_description)
            
            return True
            
        except Exception as e:
            raise AssertionError(f"Phase 4 GUI validation failed: {e}")
    
    # PHASE 5: Documentation
    def generate_validation_documentation(self) -> str:
        """
        Phase 5: Generate complete documentation of validation approaches.
        
        Required evidence that the test validity has been proven.
        """
        self.report.phases_completed.append("Documentation")
        
        doc = f"""
# TDD Test Validity Report: {self.test_name}

## Validation Summary
- **Total Phases Completed**: {len(self.report.phases_completed)}/5
- **Phases**: {', '.join(self.report.phases_completed)}
- **Evidence Entries**: {len(self.report.evidence)}
- **Triangulation Methods**: {len(self.report.triangulation_methods)}
- **Properties Tested**: {len(self.report.properties_tested)}
- **GUI Validations**: {len(self.report.gui_validations)}
- **Failure Modes Proven**: {len(self.report.failure_modes_proven)}

## Detailed Evidence
"""
        
        for i, evidence in enumerate(self.report.evidence, 1):
            doc += f"""
### Evidence {i}: {evidence.validation_phase}
- **Approach**: {evidence.approach_used}
- **Known Good Data**: {evidence.known_good_data}
- **Expected**: {evidence.expected_outcome}
- **Actual**: {evidence.actual_outcome}
- **Logic**: {evidence.validation_logic}
- **Timestamp**: {evidence.evidence_timestamp}
"""
        
        # Save documentation
        report_file = f"/tmp/{self.test_name}_validity_report_{int(time.time())}.md"
        with open(report_file, 'w') as f:
            f.write(doc)
        
        print(f"✅ Test validity documentation saved: {report_file}")
        return doc
    
    # Triangulation Helper Methods
    def add_triangulation_method(self, method_name: str, description: str):
        """Add a triangulation method to the report"""
        self.report.triangulation_methods.append(f"{method_name}: {description}")
    
    def triangulate_with_multiple_approaches(self,
                                           approaches: List[Callable],
                                           input_data: Any,
                                           tolerance: float = 0.001) -> bool:
        """
        Triangulation: Use multiple approaches to validate the same logic.
        
        If different approaches give the same result, confidence increases.
        """
        results = []
        
        for i, approach in enumerate(approaches):
            try:
                result = approach(input_data)
                results.append(result)
                
                self.add_triangulation_method(
                    f"Approach_{i+1}",
                    f"Function {approach.__name__ if hasattr(approach, '__name__') else 'anonymous'}"
                )
                
            except Exception as e:
                raise AssertionError(f"Triangulation approach {i+1} failed: {e}")
        
        # Check all results are within tolerance
        if len(results) < 2:
            raise ValueError("Triangulation requires at least 2 approaches")
        
        first_result = results[0]
        for i, result in enumerate(results[1:], 2):
            if isinstance(first_result, (int, float)) and isinstance(result, (int, float)):
                if abs(first_result - result) > tolerance:
                    raise AssertionError(
                        f"Triangulation failed: Approach 1 returned {first_result}, "
                        f"Approach {i} returned {result} (tolerance: {tolerance})"
                    )
            elif first_result != result:
                raise AssertionError(
                    f"Triangulation failed: Approach 1 returned {first_result}, "
                    f"Approach {i} returned {result}"
                )
        
        return True
    
    # Container Testing Enforcement
    def enforce_real_netbox_container(self):
        """
        Enforce zero tolerance policy: tests must run in real NetBox container.
        
        Checks that NetBox is accessible and tests are not using Django TestCase mocks.
        """
        import requests
        
        try:
            # Verify NetBox container is accessible
            response = requests.get("http://localhost:8000/login/", timeout=5)
            
            if response.status_code != 200:
                raise EnvironmentError(
                    f"ZERO TOLERANCE VIOLATION: NetBox container not accessible. "
                    f"Got HTTP {response.status_code}. Tests must run in real NetBox environment."
                )
            
            # Check for Django TestCase usage (basic check)
            import inspect
            frame = inspect.currentframe()
            while frame:
                if 'TestCase' in str(frame.f_locals.get('self', '')):
                    raise EnvironmentError(
                        "ZERO TOLERANCE VIOLATION: Django TestCase detected. "
                        "Tests must use real NetBox container, not mocked environment."
                    )
                frame = frame.f_back
                
        except requests.exceptions.RequestException as e:
            raise EnvironmentError(
                f"ZERO TOLERANCE VIOLATION: Cannot connect to NetBox container: {e}"
            )
    
    def complete_5_phase_validation(self) -> bool:
        """
        Verify all 5 phases have been completed successfully.
        
        Returns True only if all mandatory phases are complete.
        """
        required_phases = [
            "Logic Validation",
            "Failure Mode", 
            "Property-Based",
            "GUI Observable",
            "Documentation"
        ]
        
        completed = set(self.report.phases_completed)
        missing = [phase for phase in required_phases if phase not in completed]
        
        if missing:
            raise AssertionError(
                f"5-Phase validation incomplete. Missing phases: {missing}\n"
                f"Completed phases: {list(completed)}\n"
                f"Issue #9 requires ALL 5 phases for test validity."
            )
        
        return True


class ContainerFirstTestBase:
    """
    Base class for container-first testing as mandated by Issue #9.
    
    Replaces Django TestCase to enforce real NetBox container usage.
    """
    
    def setUp(self):
        """Set up real container environment"""
        self.framework = TDDValidityFramework(self.__class__.__name__)
        self.framework.enforce_real_netbox_container()
        
        # Load credentials from .env
        self.env_vars = self.framework.credentials
        
        # Set up real API client (not Django test client)
        self.netbox_url = self.env_vars.get('NETBOX_URL', 'http://localhost:8000')
        self.api_token = self.env_vars.get('NETBOX_TOKEN')
        
        if not self.api_token:
            raise EnvironmentError("NETBOX_TOKEN not found in .env file")
    
    def tearDown(self):
        """Clean up after test"""
        # Generate validation documentation
        if hasattr(self, 'framework'):
            self.framework.generate_validation_documentation()


# Example Implementation Classes
class PropertyBasedHelpers:
    """Helper functions for common property-based tests"""
    
    @staticmethod
    def test_idempotency(operation, input_data):
        """Test that f(f(x)) == f(x)"""
        result_once = operation(input_data)
        result_twice = operation(result_once)
        return result_once == result_twice
    
    @staticmethod
    def test_conservation(operation, input_data, count_function):
        """Test that total count is conserved"""
        count_before = count_function(input_data)
        result = operation(input_data)
        count_after = count_function(result)
        return count_before == count_after
    
    @staticmethod
    def test_ordering_preserved(operation, input_data):
        """Test that operation preserves ordering"""
        result = operation(input_data)
        if isinstance(result, list):
            return all(result[i] <= result[i+1] for i in range(len(result)-1))
        return True


class TriangulationHelpers:
    """Helper functions for common triangulation patterns"""
    
    @staticmethod
    def create_triangulation_approaches(base_function, alternative_implementations):
        """Create multiple approaches for triangulation"""
        approaches = [base_function] + alternative_implementations
        return approaches
    
    @staticmethod
    def minimal_implementation(spec):
        """Create minimal implementation for validation"""
        # This would create a simple, obviously-correct implementation
        # for comparison with the main implementation
        pass