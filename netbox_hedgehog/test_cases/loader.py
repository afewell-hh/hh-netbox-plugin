"""YAML loader/discovery for DIET test cases."""

from __future__ import annotations

from pathlib import Path

import yaml

from .exceptions import TestCaseNotFoundError, TestCaseValidationError
from .schema import validate_case_dict


def default_cases_root() -> Path:
    return Path(__file__).resolve().parent


def discover_case_files(root: str | Path | None = None) -> list[Path]:
    base = Path(root) if root is not None else default_cases_root()
    return sorted([p for p in base.glob("*.yaml") if p.is_file()])


def list_case_ids(root: str | Path | None = None) -> list[str]:
    return [p.stem for p in discover_case_files(root)]


def load_case(case_id: str, root: str | Path | None = None) -> dict:
    base = Path(root) if root is not None else default_cases_root()
    candidate = base / f"{case_id}.yaml"
    if not candidate.exists():
        raise TestCaseNotFoundError(f"Case '{case_id}' not found in {base}")

    try:
        raw = yaml.safe_load(candidate.read_text())
    except yaml.YAMLError as exc:
        # Include line detail directly in message for test contract.
        raise TestCaseValidationError(
            [
                {
                    "severity": "error",
                    "code": "yaml_parse_error",
                    "path": str(candidate),
                    "message": f"YAML parse error: {exc}",
                    "hint": "Fix YAML syntax and retry.",
                }
            ]
        ) from exc

    if raw is None:
        raw = {}

    try:
        validated = validate_case_dict(raw)
    except TestCaseValidationError:
        raise

    return validated

