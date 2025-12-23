"""
Tests for PortSpecification helper.

This helper parses port range specifications (e.g., "1-48", "1-32:2", "1,3,5,7")
into lists of port numbers for switch port zone allocation.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError

from netbox_hedgehog.services.port_specification import PortSpecification


class PortSpecificationTestCase(TestCase):
    """Test suite for PortSpecification helper"""

    # =========================================================================
    # Basic Parsing Tests
    # =========================================================================

    def test_parse_single_port(self):
        """Test parsing single port number"""
        spec = PortSpecification("5")
        ports = spec.parse()

        self.assertEqual(ports, [5])

    def test_parse_simple_range(self):
        """Test parsing simple range (1-48)"""
        spec = PortSpecification("1-48")
        ports = spec.parse()

        self.assertEqual(ports, list(range(1, 49)))
        self.assertEqual(len(ports), 48)

    def test_parse_comma_separated_list(self):
        """Test parsing comma-separated list"""
        spec = PortSpecification("1,3,5,7,9")
        ports = spec.parse()

        self.assertEqual(ports, [1, 3, 5, 7, 9])

    def test_parse_mixed_format(self):
        """Test parsing mixed format (ranges + lists)"""
        spec = PortSpecification("1-4,6,8-10")
        ports = spec.parse()

        self.assertEqual(ports, [1, 2, 3, 4, 6, 8, 9, 10])

    def test_parse_interleaved_format(self):
        """Test parsing interleaved format (1-32:2 = every 2nd port)"""
        spec = PortSpecification("1-32:2")
        ports = spec.parse()

        # Should be [1, 3, 5, 7, ..., 31]
        self.assertEqual(ports, list(range(1, 33, 2)))
        self.assertEqual(len(ports), 16)

    def test_parse_interleaved_step_3(self):
        """Test parsing interleaved with step=3"""
        spec = PortSpecification("1-16:3")
        ports = spec.parse()

        # Should be [1, 4, 7, 10, 13, 16]
        self.assertEqual(ports, [1, 4, 7, 10, 13, 16])

    # =========================================================================
    # Whitespace Handling
    # =========================================================================

    def test_parse_with_whitespace_around_commas(self):
        """Test port_spec handles whitespace around commas"""
        spec = PortSpecification("1-4, 6, 8-10")
        ports = spec.parse()

        # Should strip whitespace and parse correctly
        self.assertEqual(ports, [1, 2, 3, 4, 6, 8, 9, 10])

    def test_parse_with_leading_trailing_whitespace(self):
        """Test port_spec handles leading/trailing whitespace"""
        spec = PortSpecification("  1-16  ")
        ports = spec.parse()

        self.assertEqual(ports, list(range(1, 17)))

    def test_parse_with_whitespace_in_range(self):
        """Test port_spec handles whitespace in range"""
        spec = PortSpecification("1 - 8")
        ports = spec.parse()

        self.assertEqual(ports, list(range(1, 9)))

    # =========================================================================
    # Deduplication
    # =========================================================================

    def test_parse_deduplicates_overlapping_ranges(self):
        """Test port_spec deduplicates when ranges overlap"""
        spec = PortSpecification("1-4,3-6")
        ports = spec.parse()

        # Should deduplicate to [1,2,3,4,5,6]
        self.assertEqual(ports, [1, 2, 3, 4, 5, 6])

    def test_parse_deduplicates_explicit_duplicates(self):
        """Test port_spec deduplicates explicit duplicate values"""
        spec = PortSpecification("1,2,3,2,1")
        ports = spec.parse()

        # Should deduplicate to [1,2,3]
        self.assertEqual(ports, [1, 2, 3])

    def test_parse_complex_with_overlaps(self):
        """Test port_spec with complex overlapping patterns"""
        spec = PortSpecification("1-10,5-15,20,20,25-30")
        ports = spec.parse()

        # Should deduplicate to [1-15, 20, 25-30]
        expected = list(range(1, 16)) + [20] + list(range(25, 31))
        self.assertEqual(ports, sorted(set(expected)))

    # =========================================================================
    # Sorting
    # =========================================================================

    def test_parse_returns_sorted_list(self):
        """Test parse() returns ports in sorted order"""
        spec = PortSpecification("10,5,20,15,1")
        ports = spec.parse()

        self.assertEqual(ports, [1, 5, 10, 15, 20])

    def test_parse_mixed_format_returns_sorted(self):
        """Test mixed format returns sorted list"""
        spec = PortSpecification("20-25,1-5,10")
        ports = spec.parse()

        expected = list(range(1, 6)) + [10] + list(range(20, 26))
        self.assertEqual(ports, expected)

    # =========================================================================
    # Invalid Range Validation
    # =========================================================================

    def test_parse_rejects_reversed_range(self):
        """Test port_spec rejects range where start > end"""
        spec = PortSpecification("10-5")

        with self.assertRaises(ValidationError) as cm:
            spec.parse()

        error_message = str(cm.exception).lower()
        self.assertIn('invalid range', error_message)

    def test_parse_rejects_equal_range_endpoints(self):
        """Test port_spec rejects range where start == end (should use single number)"""
        # This is technically valid (produces one port) but let's allow it
        spec = PortSpecification("5-5")
        ports = spec.parse()

        # Should produce [5]
        self.assertEqual(ports, [5])

    # =========================================================================
    # Zero and Negative Port Numbers
    # =========================================================================

    def test_parse_rejects_zero_port(self):
        """Test port_spec rejects port number 0"""
        spec = PortSpecification("0-5")

        with self.assertRaises(ValidationError) as cm:
            spec.parse()

        error_message = str(cm.exception).lower()
        self.assertIn('must be positive', error_message)

    def test_parse_rejects_zero_in_list(self):
        """Test port_spec rejects zero in comma-separated list"""
        spec = PortSpecification("1,0,3")

        with self.assertRaises(ValidationError) as cm:
            spec.parse()

        error_message = str(cm.exception).lower()
        self.assertIn('must be positive', error_message)

    def test_parse_rejects_negative_port(self):
        """Test port_spec rejects negative port numbers"""
        spec = PortSpecification("-1-3")

        with self.assertRaises(ValidationError) as cm:
            spec.parse()

        error_message = str(cm.exception).lower()
        self.assertTrue(
            'must be positive' in error_message or 'invalid' in error_message
        )

    def test_parse_rejects_negative_in_range(self):
        """Test port_spec rejects negative in range end"""
        spec = PortSpecification("1--3")  # Malformed

        with self.assertRaises(ValidationError):
            spec.parse()

    # =========================================================================
    # Maximum Port Number Validation
    # =========================================================================

    def test_parse_rejects_port_above_1024(self):
        """Test port_spec rejects port numbers > 1024"""
        spec = PortSpecification("1-9999")

        with self.assertRaises(ValidationError) as cm:
            spec.parse()

        error_message = str(cm.exception).lower()
        self.assertIn('maximum port number', error_message)

    def test_parse_rejects_single_port_above_1024(self):
        """Test port_spec rejects single port > 1024"""
        spec = PortSpecification("2000")

        with self.assertRaises(ValidationError) as cm:
            spec.parse()

        error_message = str(cm.exception).lower()
        self.assertIn('maximum port number', error_message)

    def test_parse_accepts_port_1024(self):
        """Test port_spec accepts port 1024 (boundary test)"""
        spec = PortSpecification("1024")
        ports = spec.parse()

        self.assertEqual(ports, [1024])

    def test_parse_accepts_range_up_to_1024(self):
        """Test port_spec accepts range up to 1024"""
        spec = PortSpecification("1020-1024")
        ports = spec.parse()

        self.assertEqual(ports, [1020, 1021, 1022, 1023, 1024])

    # =========================================================================
    # Interleaved Step Validation
    # =========================================================================

    def test_parse_rejects_zero_step_interleaved(self):
        """Test port_spec rejects interleaved with step=0"""
        spec = PortSpecification("1-16:0")

        with self.assertRaises(ValidationError) as cm:
            spec.parse()

        error_message = str(cm.exception).lower()
        self.assertIn('step must be positive', error_message)

    def test_parse_rejects_negative_step_interleaved(self):
        """Test port_spec rejects interleaved with negative step"""
        spec = PortSpecification("1-16:-2")

        with self.assertRaises(ValidationError) as cm:
            spec.parse()

        error_message = str(cm.exception).lower()
        self.assertIn('step must be positive', error_message)

    def test_parse_interleaved_step_larger_than_range(self):
        """Test interleaved with step larger than range"""
        spec = PortSpecification("1-10:20")
        ports = spec.parse()

        # Step 20 on range 1-10 should produce only [1]
        self.assertEqual(ports, [1])

    # =========================================================================
    # Empty and Invalid Formats
    # =========================================================================

    def test_parse_rejects_empty_string(self):
        """Test port_spec rejects empty string"""
        spec = PortSpecification("")

        with self.assertRaises(ValidationError) as cm:
            spec.parse()

        error_message = str(cm.exception).lower()
        self.assertIn('port specification', error_message)

    def test_parse_rejects_whitespace_only(self):
        """Test port_spec rejects whitespace-only string"""
        spec = PortSpecification("   ")

        with self.assertRaises(ValidationError) as cm:
            spec.parse()

        error_message = str(cm.exception).lower()
        self.assertIn('port specification', error_message)

    def test_parse_rejects_invalid_characters(self):
        """Test port_spec rejects invalid characters"""
        spec = PortSpecification("1-16abc")

        with self.assertRaises(ValidationError):
            spec.parse()

    def test_parse_rejects_multiple_colons(self):
        """Test port_spec rejects multiple colons"""
        spec = PortSpecification("1-16:2:3")

        with self.assertRaises(ValidationError):
            spec.parse()

    def test_parse_rejects_colon_without_range(self):
        """Test port_spec rejects colon without range"""
        spec = PortSpecification("5:2")

        with self.assertRaises(ValidationError):
            spec.parse()

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_parse_large_range(self):
        """Test parsing large range (realistic max: 1024 ports)"""
        spec = PortSpecification("1-1024")
        ports = spec.parse()

        self.assertEqual(len(ports), 1024)
        self.assertEqual(ports[0], 1)
        self.assertEqual(ports[-1], 1024)

    def test_parse_interleaved_with_single_port(self):
        """Test interleaved format with single port"""
        spec = PortSpecification("5-5:1")
        ports = spec.parse()

        self.assertEqual(ports, [5])

    def test_parse_preserves_port_uniqueness(self):
        """Test complex specification maintains port uniqueness"""
        spec = PortSpecification("1-10,5-15,10,15,20-25,23")
        ports = spec.parse()

        # Should have no duplicates
        self.assertEqual(len(ports), len(set(ports)))

    # =========================================================================
    # Realistic Use Cases
    # =========================================================================

    def test_parse_server_downlinks(self):
        """Test realistic server downlink port specification"""
        spec = PortSpecification("1-48")
        ports = spec.parse()

        self.assertEqual(len(ports), 48)
        self.assertEqual(ports, list(range(1, 49)))

    def test_parse_spine_uplinks(self):
        """Test realistic spine uplink port specification"""
        spec = PortSpecification("49-64")
        ports = spec.parse()

        self.assertEqual(len(ports), 16)
        self.assertEqual(ports, list(range(49, 65)))

    def test_parse_rail_optimized_interleaved(self):
        """Test rail-optimized interleaved port allocation"""
        # Rail 0 gets odd ports: 1, 3, 5, ..., 63
        spec = PortSpecification("1-64:2")
        ports = spec.parse()

        self.assertEqual(len(ports), 32)
        self.assertEqual(ports[0], 1)
        self.assertEqual(ports[-1], 63)
        # All odd numbers
        self.assertTrue(all(p % 2 == 1 for p in ports))

    def test_parse_mclag_peer_ports(self):
        """Test MCLAG peer port specification"""
        spec = PortSpecification("65,66")
        ports = spec.parse()

        self.assertEqual(ports, [65, 66])

    # =========================================================================
    # String Representation
    # =========================================================================

    def test_str_representation(self):
        """Test __str__ returns original specification"""
        spec = PortSpecification("1-48,50,52-64")

        # Should preserve original spec
        self.assertEqual(str(spec), "1-48,50,52-64")

    # =========================================================================
    # Initialization
    # =========================================================================

    def test_init_stores_specification(self):
        """Test initialization stores specification"""
        spec = PortSpecification("1-16")

        self.assertEqual(spec.spec, "1-16")

    def test_init_strips_whitespace(self):
        """Test initialization strips leading/trailing whitespace"""
        spec = PortSpecification("  1-16  ")

        self.assertEqual(spec.spec, "1-16")
