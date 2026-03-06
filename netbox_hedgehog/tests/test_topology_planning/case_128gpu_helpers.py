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


def load_contract() -> dict:
    """Return the contract section from canonical YAML."""
    return load_case_128gpu().get("contract", {})


def contract_storage() -> dict:
    """Return the storage invariant block from the canonical YAML contract."""
    c = load_contract().get("storage", {})
    if not c:
        raise KeyError("contract.storage missing from ux_case_128gpu_odd_ports.yaml")
    return c


def contract_zones() -> list:
    """Return the required zones list from the canonical YAML contract."""
    zones = load_contract().get("zones", {}).get("required", [])
    if not zones:
        raise KeyError("contract.zones.required missing from ux_case_128gpu_odd_ports.yaml")
    return zones
