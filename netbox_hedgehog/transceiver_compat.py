"""
Approved asymmetric transceiver compatibility rules for DIET topology plans.

Asymmetric pairs are physically valid optical paths where switch-side and
server-side transceivers intentionally differ in cage_type and/or connector
due to an intermediate passive splitter that is not modeled in NetBox.

Rules are directional: switch-side attributes come first, server-side second.
Reversing the argument order will not produce a match.

Adding a new approved pair:
1. Add a 6-tuple to APPROVED_ASYMMETRIC_PAIRS.
2. Add a test in test_asymmetric_compat.py asserting the new pair passes.
3. Add a negative test asserting the reverse direction still fails.
"""
from __future__ import annotations

# Approved asymmetric compatibility pairs.
# Tuple layout: (switch_cage_type, switch_connector, switch_medium,
#                switch_breakout_topology, server_cage_type, server_connector)
#
# medium is included in the switch-side key because it must also match on
# the server side (enforced independently by V5/V8), but including it here
# prevents accidentally approving cross-medium combinations that happen to
# share the same cage/connector pattern.
#
# switch_breakout_topology is included to restrict the rule to optics that
# explicitly declare sub-link breakout intent, preventing accidental approval
# of straight OSFP optics with the same cage/connector.
APPROVED_ASYMMETRIC_PAIRS: frozenset[tuple[str, str, str, str, str, str]] = frozenset([
    # 800G OSFP (Dual MPO-12, MMF, 2x400g breakout) → Y-splitter → QSFP112 (MPO-12, MMF).
    # Approved for: XOC-64 soc_storage_server_4x200 zone using Celestica R4113-A9220-VR
    # switch optic paired with generic QSFP112-200GBASE-SR2 host optic.
    ('OSFP', 'Dual MPO-12', 'MMF', '2x400g', 'QSFP112', 'MPO-12'),
])


def is_approved_asymmetric_pair(
    switch_cage_type: str | None,
    switch_connector: str | None,
    switch_medium: str | None,
    switch_breakout_topology: str | None,
    server_cage_type: str | None,
    server_connector: str | None,
) -> bool:
    """
    Return True if (switch→server) is an explicitly approved asymmetric pair.

    Convention: pass SwitchPortZone transceiver attribute_data values first,
    PlanServerConnection transceiver attribute_data values second. Reversing
    this order will not produce a match.

    Returns False — strict enforcement — if any argument is None or empty string.
    A missing field on either optic is treated as "unknown", not as "compatible".
    """
    if not all([switch_cage_type, switch_connector, switch_medium,
                switch_breakout_topology, server_cage_type, server_connector]):
        return False
    return (
        switch_cage_type,
        switch_connector,
        switch_medium,
        switch_breakout_topology,
        server_cage_type,
        server_connector,
    ) in APPROVED_ASYMMETRIC_PAIRS
