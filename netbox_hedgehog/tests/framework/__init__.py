"""
TDD Test Validity Framework - Issue #9 Implementation

This framework implements the mandatory requirements from GitHub Issue #9:
- 5-phase validation protocol
- Test logic triangulation 
- Property-based testing
- GUI validation requirements
- Zero tolerance enforcement for mocks and environment bypasses

Usage:
    from netbox_hedgehog.tests.framework import TDDValidityFramework, ContainerFirstTestBase
    
    class MyTest(ContainerFirstTestBase):
        def test_something(self):
            framework = TDDValidityFramework("test_name")
            # Implement 5-phase validation...
"""

from .tdd_validity_framework import (
    TDDValidityFramework,
    ContainerFirstTestBase,
    ValidationEvidence,
    TestValidityReport,
    PropertyBasedHelpers,
    TriangulationHelpers
)

__all__ = [
    'TDDValidityFramework',
    'ContainerFirstTestBase', 
    'ValidationEvidence',
    'TestValidityReport',
    'PropertyBasedHelpers',
    'TriangulationHelpers'
]