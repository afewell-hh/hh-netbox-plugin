"""Helpers for canonical 128GPU YAML-backed test expectations."""

from netbox_hedgehog.test_cases.loader import load_case


CASE_ID_128GPU = "ux_case_128gpu_odd_ports"


def load_case_128gpu() -> dict:
    """Load canonical 128GPU case data from netbox_hedgehog/test_cases."""
    return load_case(CASE_ID_128GPU)


def expected_128gpu_counts() -> dict:
    """Return expected planning object counts from canonical YAML."""
    case = load_case_128gpu()
    return case.get("expected", {}).get("counts", {})
