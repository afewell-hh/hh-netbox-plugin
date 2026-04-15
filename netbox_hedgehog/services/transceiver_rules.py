"""
Transceiver compatibility rule engine (DIET-450).

Single authority for evaluating whether two transceiver endpoints
(server-side and switch-side) are compatible.  Produces reason-coded
outcomes consumable by both the connection review UX (#449) and the
generation/reporting layer (DeviceGenerator).

Design principles
-----------------
- Pure functions: no Django ORM, no database access.  Callers resolve
  attribute_data from ModuleType objects; this module only evaluates
  the dict payloads.
- Reason codes are stable string constants (not an Enum) so they can be
  serialised to JSON or compared in template logic without import.
- Outcomes map cleanly to the three review levels used throughout HNP:
  match, needs_review, blocked.

Rule evaluation order
---------------------
1. Both None               → match  / R_NULL
2. One None (asymmetry)    → needs_review / R_INTENT_ASYMMETRY
3. Medium mismatch         → blocked / R_MEDIUM_MISMATCH   (always enforced)
4. Approved asymmetric pair → match / R_APPROVED_ASYMMETRIC
5. Cage type mismatch       → needs_review / R_CAGE_MISMATCH
6. Connector mismatch       → needs_review / R_CONNECTOR_MISMATCH
7. All checks pass          → match / R_MATCH

Rule retention notes
--------------------
Retained as blocked:
  R_MEDIUM_MISMATCH — MMF vs SMF is a physical impossibility; even an
  intermediate splitter cannot bridge optical multimode and singlemode
  fiber.  This rule is never downgraded to needs_review.

Retained as hard ValidationError (save-time, not this module):
  V1: transceiver_module_type must reference a Network Transceiver profile.
  V2/V3: flat cage_type and medium must agree with FK attribute_data when
  both are set.  These are internal contradiction checks (same side), not
  cross-end compat; they remain in model.clean().

Downgraded to needs_review (was hard ValidationError pre-#450):
  R_CAGE_MISMATCH — a non-approved cage type difference triggers human
  review rather than an outright block.  Physically plausible via
  adapter/breakout-splitter; the operator must confirm intent.  Note:
  model.clean() still raises for non-approved cage mismatches; this
  outcome is the rule-engine/UI equivalent consumed at review time and
  in the generation mismatch report.

  R_CONNECTOR_MISMATCH — same rationale as cage mismatch.

Advisory (needs_review):
  R_INTENT_ASYMMETRY — one side specifies a transceiver, the other
  does not.  The plan may be incomplete rather than wrong.

Approved asymmetric pairs:
  R_APPROVED_ASYMMETRIC — pair is in transceiver_compat.APPROVED_ASYMMETRIC_PAIRS
  (e.g. XOC-64 OSFP + Y-splitter + QSFP112).  Outcome is match, not
  needs_review, because the pair has been explicitly reviewed and approved.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Outcome constants
# ---------------------------------------------------------------------------

OUTCOME_MATCH = 'match'
OUTCOME_NEEDS_REVIEW = 'needs_review'
OUTCOME_BLOCKED = 'blocked'

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

R_NULL = 'R_NULL'
R_MATCH = 'R_MATCH'
R_APPROVED_ASYMMETRIC = 'R_APPROVED_ASYMMETRIC'
R_INTENT_ASYMMETRY = 'R_INTENT_ASYMMETRY'
R_MEDIUM_MISMATCH = 'R_MEDIUM_MISMATCH'
R_CAGE_MISMATCH = 'R_CAGE_MISMATCH'
R_CONNECTOR_MISMATCH = 'R_CONNECTOR_MISMATCH'


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class XcvrRuleResult:
    """
    Immutable outcome of a single transceiver-pair compatibility evaluation.

    Fields
    ------
    outcome : str
        One of OUTCOME_MATCH, OUTCOME_NEEDS_REVIEW, OUTCOME_BLOCKED.
    reason_code : str
        Stable machine-readable code (R_* constant).  Safe to persist/compare.
    reason : str
        Short human-readable explanation suitable for UI display.
    """
    outcome: str
    reason_code: str
    reason: str


# ---------------------------------------------------------------------------
# Pre-built results for the null/intent-asymmetry paths (no caller arguments
# needed, so we create them once rather than on every call).
# ---------------------------------------------------------------------------

_RESULT_NULL = XcvrRuleResult(
    OUTCOME_MATCH, R_NULL,
    'No transceiver intent on either end',
)
_RESULT_SERVER_ONLY = XcvrRuleResult(
    OUTCOME_NEEDS_REVIEW, R_INTENT_ASYMMETRY,
    'Connection specifies a transceiver but the switch zone does not',
)
_RESULT_ZONE_ONLY = XcvrRuleResult(
    OUTCOME_NEEDS_REVIEW, R_INTENT_ASYMMETRY,
    'Switch zone specifies a transceiver but the connection does not',
)
_RESULT_MATCH = XcvrRuleResult(
    OUTCOME_MATCH, R_MATCH,
    'Transceiver specifications are compatible',
)
_RESULT_APPROVED = XcvrRuleResult(
    OUTCOME_MATCH, R_APPROVED_ASYMMETRIC,
    'Approved asymmetric pair; physical path uses an external splitter',
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_xcvr_pair(
    server_attrs: dict | None,
    zone_attrs: dict | None,
) -> XcvrRuleResult:
    """
    Evaluate transceiver compatibility between a server endpoint and a
    switch-zone endpoint.

    Parameters
    ----------
    server_attrs:
        ``ModuleType.attribute_data`` dict for the server-side (connection)
        transceiver, or ``None`` if no transceiver FK is set on the
        PlanServerConnection.
    zone_attrs:
        ``ModuleType.attribute_data`` dict for the switch-zone transceiver,
        or ``None`` if no transceiver FK is set on the SwitchPortZone.

    Returns
    -------
    XcvrRuleResult
        Immutable result with ``outcome``, ``reason_code``, and ``reason``.
    """
    # Rule 1: both None → no transceiver intent on either end.
    if server_attrs is None and zone_attrs is None:
        return _RESULT_NULL

    # Rule 2: intent asymmetry — one side has a transceiver, the other does not.
    if server_attrs is None:
        return _RESULT_ZONE_ONLY
    if zone_attrs is None:
        return _RESULT_SERVER_ONLY

    # Both sides have attribute data from here on.

    # Rule 3: medium mismatch — physically impossible; always blocked.
    srv_medium = server_attrs.get('medium')
    zone_medium = zone_attrs.get('medium')
    if srv_medium and zone_medium and srv_medium != zone_medium:
        return XcvrRuleResult(
            OUTCOME_BLOCKED, R_MEDIUM_MISMATCH,
            f'Medium mismatch: server uses {srv_medium}, switch uses {zone_medium}',
        )

    # Rule 4: approved asymmetric pair — skip cage/connector checks for this pair.
    from netbox_hedgehog.transceiver_compat import is_approved_asymmetric_pair
    if is_approved_asymmetric_pair(
        zone_attrs.get('cage_type'),
        zone_attrs.get('connector'),
        zone_attrs.get('medium'),
        zone_attrs.get('breakout_topology'),
        server_attrs.get('cage_type'),
        server_attrs.get('connector'),
    ):
        return _RESULT_APPROVED

    # Rule 5: cage type mismatch (non-approved).
    srv_cage = server_attrs.get('cage_type')
    zone_cage = zone_attrs.get('cage_type')
    if srv_cage and zone_cage and srv_cage != zone_cage:
        return XcvrRuleResult(
            OUTCOME_NEEDS_REVIEW, R_CAGE_MISMATCH,
            f'Cage type mismatch: server uses {srv_cage}, switch uses {zone_cage}',
        )

    # Rule 6: connector mismatch (non-approved).
    srv_connector = server_attrs.get('connector')
    zone_connector = zone_attrs.get('connector')
    if srv_connector and zone_connector and srv_connector != zone_connector:
        return XcvrRuleResult(
            OUTCOME_NEEDS_REVIEW, R_CONNECTOR_MISMATCH,
            f'Connector mismatch: server uses {srv_connector}, switch uses {zone_connector}',
        )

    # Rule 7: all checks passed.
    return _RESULT_MATCH
