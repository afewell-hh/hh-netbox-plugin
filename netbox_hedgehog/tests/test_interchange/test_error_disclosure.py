"""#688 regression probes for decoder-originated interchange diagnostics."""

from unittest.mock import patch

import yaml
from django.test import SimpleTestCase

from netbox_hedgehog.tests.test_interchange._support import require_interchange


class DecoderDisclosureTestCase(SimpleTestCase):
    """The decoder, not a view, owns safe conversion of parser exceptions."""

    SENTINEL = "SENTINEL_DECODER_VALUE_MUST_NOT_ESCAPE"
    HOSTILE_KEY = "SENTINEL_MAPPING_KEY_MUST_NOT_ESCAPE"

    def assert_safe_error(self, raw, *, code):
        module = require_interchange()
        with self.assertNoLogs("netbox_hedgehog", level="DEBUG"):
            with self.assertRaises(module.InterchangeError) as caught:
                module.decode_document(raw)
        error = caught.exception
        self.assertEqual(error.code, code)
        self.assertNotIn(self.SENTINEL, str(error))
        self.assertNotIn(self.HOSTILE_KEY, str(error))
        self.assertIsNone(error.source_location.path)
        self.assertIsInstance(error.source_location.line, int)
        self.assertIsInstance(error.source_location.column, int)

    def test_yaml_scanner_error_is_fixed_and_source_positioned(self):
        self.assert_safe_error(
            'kubernetes_token: "' + self.SENTINEL + "\n",
            code="invalid-yaml",
        )

    def test_yaml_constructor_error_conversion_cannot_echo_exception_text(self):
        # The event scan succeeds; this targets the later yaml.load() conversion
        # so fixing only the scanner branch cannot satisfy #688.
        with patch.object(yaml, "load", side_effect=yaml.YAMLError(self.SENTINEL)):
            self.assert_safe_error("apiVersion: aid.hedgehog.com/v1\n", code="invalid-yaml")

    def test_duplicate_json_mapping_key_never_becomes_a_source_path(self):
        self.assert_safe_error(
            '{"' + self.HOSTILE_KEY + '": 1, "' + self.HOSTILE_KEY + '": 2}',
            code="duplicate-mapping-key",
        )
