"""
Unit tests for services/transceiver_rules.py (DIET-450).

Covers the rule evaluation function evaluate_xcvr_pair() in isolation —
no database, no Django models.  Each test class maps to one rule or one
boundary condition.

Test groups
-----------
R1  — R_NULL: both attrs None
R2  — R_INTENT_ASYMMETRY: one side has attrs, other is None
R3  — R_MEDIUM_MISMATCH: medium fields present and different
R4  — R_APPROVED_ASYMMETRIC: approved pair (XOC-64 OSFP→QSFP112)
R5  — R_CAGE_MISMATCH: non-approved cage difference
R6  — R_CONNECTOR_MISMATCH: non-approved connector difference
R7  — R_MATCH: all relevant fields agree
R8  — Null-field null-skip: missing sub-fields do not produce false mismatches
R9  — Reason codes and outcome constants are stable strings
R10 — XcvrRuleResult is hashable (frozen dataclass)
"""

from django.test import SimpleTestCase

from netbox_hedgehog.services.transceiver_rules import (
    OUTCOME_BLOCKED,
    OUTCOME_MATCH,
    OUTCOME_NEEDS_REVIEW,
    R_APPROVED_ASYMMETRIC,
    R_CAGE_MISMATCH,
    R_CONNECTOR_MISMATCH,
    R_INTENT_ASYMMETRY,
    R_MATCH,
    R_MEDIUM_MISMATCH,
    R_NULL,
    XcvrRuleResult,
    evaluate_xcvr_pair,
)


# ---------------------------------------------------------------------------
# Shared attribute dicts
# ---------------------------------------------------------------------------

_OSFP_VR4 = {
    'cage_type': 'OSFP',
    'medium': 'MMF',
    'connector': 'Dual MPO-12',
    'standard': '800GBASE-2xVR4',
    'reach_class': 'VR',
    'breakout_topology': '2x400g',
}
_QSFP112_SR2 = {
    'cage_type': 'QSFP112',
    'medium': 'MMF',
    'connector': 'MPO-12',
    'standard': '200GBASE-SR2',
    'reach_class': 'SR',
    'breakout_topology': '1x',
}
_QSFP112_SMF = {
    'cage_type': 'QSFP112',
    'medium': 'SMF',
    'connector': 'MPO-12',
    'standard': '200GBASE-DR4',
    'reach_class': 'DR',
}
_QSFP28_SR4 = {
    'cage_type': 'QSFP28',
    'medium': 'MMF',
    'connector': 'MPO-12',
    'standard': '100GBASE-SR4',
    'reach_class': 'SR',
}
_QSFP_DD_SR4 = {
    'cage_type': 'QSFP-DD',
    'medium': 'MMF',
    'connector': 'MPO-12',
    'standard': '400GBASE-SR4',
    'reach_class': 'SR',
}
_QSFP28_LC = {
    'cage_type': 'QSFP28',
    'medium': 'MMF',
    'connector': 'LC',
    'standard': '100GBASE-SR',
    'reach_class': 'SR',
}


# ---------------------------------------------------------------------------
# R1: R_NULL — both attrs None
# ---------------------------------------------------------------------------

class TestRuleR1Null(SimpleTestCase):
    """Both endpoints have no transceiver FK → R_NULL match."""

    def test_both_none_returns_match(self):
        result = evaluate_xcvr_pair(None, None)
        self.assertEqual(result.outcome, OUTCOME_MATCH)

    def test_both_none_reason_code_is_r_null(self):
        result = evaluate_xcvr_pair(None, None)
        self.assertEqual(result.reason_code, R_NULL)

    def test_both_none_reason_is_human_readable(self):
        result = evaluate_xcvr_pair(None, None)
        self.assertTrue(len(result.reason) > 0)


# ---------------------------------------------------------------------------
# R2: R_INTENT_ASYMMETRY — one side has attrs, other is None
# ---------------------------------------------------------------------------

class TestRuleR2IntentAsymmetry(SimpleTestCase):
    """One endpoint has attrs, other is None → R_INTENT_ASYMMETRY needs_review."""

    def test_server_has_attrs_zone_none(self):
        result = evaluate_xcvr_pair(_QSFP112_SR2, None)
        self.assertEqual(result.outcome, OUTCOME_NEEDS_REVIEW)
        self.assertEqual(result.reason_code, R_INTENT_ASYMMETRY)

    def test_zone_has_attrs_server_none(self):
        result = evaluate_xcvr_pair(None, _OSFP_VR4)
        self.assertEqual(result.outcome, OUTCOME_NEEDS_REVIEW)
        self.assertEqual(result.reason_code, R_INTENT_ASYMMETRY)

    def test_server_reason_mentions_connection(self):
        """Reason for server-only side mentions 'connection' for UI clarity."""
        result = evaluate_xcvr_pair(_QSFP112_SR2, None)
        self.assertIn('connection', result.reason.lower())

    def test_zone_reason_mentions_zone(self):
        """Reason for zone-only side mentions 'zone' for UI clarity."""
        result = evaluate_xcvr_pair(None, _OSFP_VR4)
        self.assertIn('zone', result.reason.lower())


# ---------------------------------------------------------------------------
# R3: R_MEDIUM_MISMATCH — blocked
# ---------------------------------------------------------------------------

class TestRuleR3MediumMismatch(SimpleTestCase):
    """Medium mismatch → R_MEDIUM_MISMATCH blocked (physically impossible)."""

    def test_mmf_vs_smf_is_blocked(self):
        result = evaluate_xcvr_pair(_QSFP112_SR2, _QSFP112_SMF)
        self.assertEqual(result.outcome, OUTCOME_BLOCKED)
        self.assertEqual(result.reason_code, R_MEDIUM_MISMATCH)

    def test_smf_vs_mmf_is_blocked(self):
        result = evaluate_xcvr_pair(_QSFP112_SMF, _QSFP112_SR2)
        self.assertEqual(result.outcome, OUTCOME_BLOCKED)
        self.assertEqual(result.reason_code, R_MEDIUM_MISMATCH)

    def test_reason_mentions_both_mediums(self):
        result = evaluate_xcvr_pair(_QSFP112_SR2, _QSFP112_SMF)
        self.assertIn('MMF', result.reason)
        self.assertIn('SMF', result.reason)

    def test_medium_checked_before_cage(self):
        """Medium check fires even when cage types also differ."""
        mmf_osfp = {'cage_type': 'OSFP', 'medium': 'MMF', 'connector': 'LC'}
        smf_qsfp = {'cage_type': 'QSFP28', 'medium': 'SMF', 'connector': 'LC'}
        result = evaluate_xcvr_pair(mmf_osfp, smf_qsfp)
        self.assertEqual(result.reason_code, R_MEDIUM_MISMATCH)


# ---------------------------------------------------------------------------
# R4: R_APPROVED_ASYMMETRIC — approved pair
# ---------------------------------------------------------------------------

class TestRuleR4ApprovedAsymmetric(SimpleTestCase):
    """Approved asymmetric pair → R_APPROVED_ASYMMETRIC match."""

    def test_xoc64_approved_pair_is_match(self):
        """
        XOC-64 soc-storage path: OSFP-2xVR4 (switch) + Y-splitter + QSFP112-SR2 (server).
        evaluate_xcvr_pair is called with server_attrs first, zone_attrs second.
        """
        result = evaluate_xcvr_pair(_QSFP112_SR2, _OSFP_VR4)
        self.assertEqual(result.outcome, OUTCOME_MATCH)
        self.assertEqual(result.reason_code, R_APPROVED_ASYMMETRIC)

    def test_reversed_pair_is_not_approved(self):
        """Rule is directional: OSFP server vs QSFP112 zone is NOT in the registry."""
        result = evaluate_xcvr_pair(_OSFP_VR4, _QSFP112_SR2)
        self.assertNotEqual(result.reason_code, R_APPROVED_ASYMMETRIC)

    def test_approved_pair_reason_mentions_splitter(self):
        result = evaluate_xcvr_pair(_QSFP112_SR2, _OSFP_VR4)
        self.assertIn('splitter', result.reason.lower())

    def test_medium_mismatch_still_blocked_for_otherwise_approved_shape(self):
        """
        Medium check fires before the approved-pair lookup.
        If someone registered a cross-medium pair in the future, medium would
        still block.  Verify the ordering here with a synthetic case.
        """
        smf_osfp = dict(_OSFP_VR4, medium='SMF')
        result = evaluate_xcvr_pair(_QSFP112_SR2, smf_osfp)
        # MMF (server) vs SMF (switch) → blocked before approved-pair check
        self.assertEqual(result.outcome, OUTCOME_BLOCKED)
        self.assertEqual(result.reason_code, R_MEDIUM_MISMATCH)


# ---------------------------------------------------------------------------
# R5: R_CAGE_MISMATCH — non-approved cage difference
# ---------------------------------------------------------------------------

class TestRuleR5CageMismatch(SimpleTestCase):
    """Non-approved cage type mismatch → R_CAGE_MISMATCH needs_review."""

    def test_qsfp28_vs_qsfp_dd_is_needs_review(self):
        result = evaluate_xcvr_pair(_QSFP28_SR4, _QSFP_DD_SR4)
        self.assertEqual(result.outcome, OUTCOME_NEEDS_REVIEW)
        self.assertEqual(result.reason_code, R_CAGE_MISMATCH)

    def test_reason_names_both_cage_types(self):
        result = evaluate_xcvr_pair(_QSFP28_SR4, _QSFP_DD_SR4)
        self.assertIn('QSFP28', result.reason)
        self.assertIn('QSFP-DD', result.reason)

    def test_missing_cage_field_skipped(self):
        """If one side has no cage_type, the cage check null-skips (no false mismatch)."""
        no_cage = {'medium': 'MMF', 'connector': 'MPO-12'}
        result = evaluate_xcvr_pair(no_cage, _QSFP28_SR4)
        self.assertNotEqual(result.reason_code, R_CAGE_MISMATCH)


# ---------------------------------------------------------------------------
# R6: R_CONNECTOR_MISMATCH — non-approved connector difference
# ---------------------------------------------------------------------------

class TestRuleR6ConnectorMismatch(SimpleTestCase):
    """Non-approved connector mismatch → R_CONNECTOR_MISMATCH needs_review."""

    def test_lc_vs_mpo12_same_cage_is_needs_review(self):
        result = evaluate_xcvr_pair(_QSFP28_LC, _QSFP28_SR4)
        self.assertEqual(result.outcome, OUTCOME_NEEDS_REVIEW)
        self.assertEqual(result.reason_code, R_CONNECTOR_MISMATCH)

    def test_reason_names_both_connectors(self):
        result = evaluate_xcvr_pair(_QSFP28_LC, _QSFP28_SR4)
        self.assertIn('LC', result.reason)
        self.assertIn('MPO-12', result.reason)

    def test_cage_mismatch_checked_before_connector(self):
        """Cage check fires first; connector mismatch on different cages is R_CAGE_MISMATCH."""
        result = evaluate_xcvr_pair(_QSFP28_LC, _QSFP_DD_SR4)
        self.assertEqual(result.reason_code, R_CAGE_MISMATCH)

    def test_missing_connector_field_skipped(self):
        """If one side has no connector, connector check null-skips."""
        no_connector = {'cage_type': 'QSFP28', 'medium': 'MMF'}
        result = evaluate_xcvr_pair(no_connector, _QSFP28_SR4)
        self.assertNotEqual(result.reason_code, R_CONNECTOR_MISMATCH)


# ---------------------------------------------------------------------------
# R7: R_MATCH — all fields agree
# ---------------------------------------------------------------------------

class TestRuleR7Match(SimpleTestCase):
    """Symmetric pair with matching attrs → R_MATCH."""

    def test_identical_attrs_is_match(self):
        result = evaluate_xcvr_pair(_QSFP112_SR2, _QSFP112_SR2)
        self.assertEqual(result.outcome, OUTCOME_MATCH)
        self.assertEqual(result.reason_code, R_MATCH)

    def test_same_cage_medium_different_standard_is_match(self):
        """'standard' is not a blocking dimension; differing standards → match."""
        a = {'cage_type': 'QSFP112', 'medium': 'MMF', 'connector': 'MPO-12', 'standard': 'A'}
        b = {'cage_type': 'QSFP112', 'medium': 'MMF', 'connector': 'MPO-12', 'standard': 'B'}
        result = evaluate_xcvr_pair(a, b)
        self.assertEqual(result.outcome, OUTCOME_MATCH)

    def test_match_reason_is_human_readable(self):
        result = evaluate_xcvr_pair(_QSFP112_SR2, _QSFP112_SR2)
        self.assertTrue(len(result.reason) > 0)


# ---------------------------------------------------------------------------
# R8: Null-field null-skip — missing sub-fields don't false-positive
# ---------------------------------------------------------------------------

class TestRuleR8NullFieldSkip(SimpleTestCase):
    """Fields not present in attribute_data do not trigger false mismatches."""

    def test_empty_dicts_is_match(self):
        result = evaluate_xcvr_pair({}, {})
        self.assertEqual(result.outcome, OUTCOME_MATCH)
        self.assertEqual(result.reason_code, R_MATCH)

    def test_partial_attrs_no_false_mismatch(self):
        """One side has only 'medium'; no cage or connector → no cage/connector mismatch."""
        a = {'medium': 'MMF'}
        b = {'medium': 'MMF', 'cage_type': 'QSFP28', 'connector': 'MPO-12'}
        result = evaluate_xcvr_pair(a, b)
        self.assertEqual(result.outcome, OUTCOME_MATCH)

    def test_none_medium_on_one_side_skips_medium_check(self):
        a = {'cage_type': 'QSFP28', 'connector': 'MPO-12'}          # no medium
        b = {'cage_type': 'QSFP28', 'connector': 'MPO-12', 'medium': 'MMF'}
        result = evaluate_xcvr_pair(a, b)
        self.assertNotEqual(result.reason_code, R_MEDIUM_MISMATCH)


# ---------------------------------------------------------------------------
# R9: Constants are stable strings
# ---------------------------------------------------------------------------

class TestRuleR9Constants(SimpleTestCase):
    """Outcome and reason-code constants must be plain strings."""

    def test_outcome_constants_are_strings(self):
        for val in (OUTCOME_MATCH, OUTCOME_NEEDS_REVIEW, OUTCOME_BLOCKED):
            self.assertIsInstance(val, str)

    def test_reason_code_constants_are_strings(self):
        for val in (R_NULL, R_MATCH, R_APPROVED_ASYMMETRIC, R_INTENT_ASYMMETRY,
                    R_MEDIUM_MISMATCH, R_CAGE_MISMATCH, R_CONNECTOR_MISMATCH):
            self.assertIsInstance(val, str)

    def test_reason_codes_are_prefixed_r(self):
        for val in (R_NULL, R_MATCH, R_APPROVED_ASYMMETRIC, R_INTENT_ASYMMETRY,
                    R_MEDIUM_MISMATCH, R_CAGE_MISMATCH, R_CONNECTOR_MISMATCH):
            self.assertTrue(val.startswith('R_'), f"{val!r} does not start with 'R_'")


# ---------------------------------------------------------------------------
# R10: XcvrRuleResult is a frozen hashable dataclass
# ---------------------------------------------------------------------------

class TestRuleR10ResultType(SimpleTestCase):
    """XcvrRuleResult is frozen and hashable."""

    def test_result_is_frozen(self):
        result = evaluate_xcvr_pair(None, None)
        with self.assertRaises((AttributeError, TypeError)):
            result.outcome = 'mutated'  # type: ignore[misc]

    def test_result_is_hashable(self):
        result = evaluate_xcvr_pair(None, None)
        h = hash(result)
        self.assertIsInstance(h, int)

    def test_equal_results_have_same_hash(self):
        r1 = evaluate_xcvr_pair(None, None)
        r2 = evaluate_xcvr_pair(None, None)
        self.assertEqual(r1, r2)
        self.assertEqual(hash(r1), hash(r2))

    def test_result_has_required_fields(self):
        result = evaluate_xcvr_pair(_QSFP112_SR2, _QSFP112_SR2)
        self.assertTrue(hasattr(result, 'outcome'))
        self.assertTrue(hasattr(result, 'reason_code'))
        self.assertTrue(hasattr(result, 'reason'))
