"""Schema validation for YAML DIET test cases."""

from __future__ import annotations

import re
from copy import deepcopy

from .exceptions import TestCaseValidationError

CASE_ID_RE = re.compile(r"^[a-z0-9_]+$")
VALID_PLAN_STATUSES = {"draft", "review", "approved", "exported"}

_V2_API_VERSION = "diet/v2"
_V2_KIND = "TopologyPlan"


def _err(code: str, path: str, message: str, hint: str | None = None) -> dict:
    payload = {
        "severity": "error",
        "code": code,
        "path": path,
        "message": message,
    }
    if hint:
        payload["hint"] = hint
    return payload


def _validate_v2(data: dict) -> tuple[dict, list[dict]]:
    """Validate a v2-format case dict. Returns (normalized_data, errors)."""
    errors: list[dict] = []

    if "reference_data" in data:
        errors.append(_err("v2_forbidden_key", "reference_data",
                           "reference_data is not allowed in v2; use test_fixtures or pre-seeded inventory"))

    kind = data.get("kind")
    if not kind:
        errors.append(_err("missing_required", "kind", "kind is required in v2"))
    elif kind != _V2_KIND:
        errors.append(_err("invalid_value", "kind",
                           f"kind must be '{_V2_KIND}', got '{kind}'"))

    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        errors.append(_err("missing_required", "metadata", "metadata mapping is required in v2"))
        metadata = {}

    case_id = metadata.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        errors.append(_err("missing_required", "metadata.case_id", "case_id is required"))
    elif not CASE_ID_RE.match(case_id):
        errors.append(_err("invalid_format", "metadata.case_id", "case_id must match [a-z0-9_]+"))

    if not isinstance(metadata.get("name"), str) or not metadata.get("name"):
        errors.append(_err("missing_required", "metadata.name", "name is required"))

    if metadata.get("version") != 2:
        errors.append(_err("invalid_value", "metadata.version",
                           f"version must be 2 in a v2 document, got {metadata.get('version')!r}"))

    if metadata.get("managed_by") != "yaml":
        errors.append(_err("invalid_value", "metadata.managed_by",
                           "managed_by must be literal 'yaml'"))

    spec = data.get("spec")
    if not isinstance(spec, dict):
        errors.append(_err("missing_required", "spec", "spec mapping is required in v2"))
        spec = {}

    plan = spec.get("plan")
    if not isinstance(plan, dict):
        errors.append(_err("invalid_type", "spec.plan", "spec.plan must be a mapping"))
        plan = {}

    if not isinstance(plan.get("name"), str) or not plan.get("name"):
        errors.append(_err("missing_required", "spec.plan.name", "spec.plan.name is required"))

    plan_status = plan.get("status")
    if not isinstance(plan_status, str):
        errors.append(_err("missing_required", "spec.plan.status", "spec.plan.status is required"))
    elif plan_status not in VALID_PLAN_STATUSES:
        errors.append(_err("invalid_enum", "spec.plan.status",
                           f"status must be one of {sorted(VALID_PLAN_STATUSES)}"))

    for key in ("switch_classes", "server_classes", "server_connections"):
        if key in spec and not isinstance(spec[key], list):
            errors.append(_err("invalid_type", f"spec.{key}", f"spec.{key} must be a list"))

    # Validate optional status block
    status_block = data.get("status")
    if isinstance(status_block, dict):
        gen = status_block.get("generation")
        if isinstance(gen, dict):
            for field in ("device_count", "interface_count", "cable_count"):
                val = gen.get(field)
                if val is not None and not isinstance(val, int):
                    errors.append(_err("invalid_type", f"status.generation.{field}",
                                       f"{field} must be an integer"))

    # Validate optional contract block
    contract_block = data.get("contract")
    if isinstance(contract_block, dict):
        errors.extend(_validate_contract_block(contract_block))

    return data, errors


def _validate_contract_block(contract: dict) -> list[dict]:
    errors: list[dict] = []

    counts = contract.get("counts")
    if isinstance(counts, dict):
        for k, v in counts.items():
            if not isinstance(v, int):
                errors.append(_err("invalid_type", f"contract.counts.{k}",
                                   f"{k} must be an integer"))

    generation = contract.get("generation")
    if isinstance(generation, dict):
        for k, v in generation.items():
            if not isinstance(v, int):
                errors.append(_err("invalid_type", f"contract.generation.{k}",
                                   f"{k} must be an integer"))

    zones = contract.get("zones")
    if isinstance(zones, dict):
        required = zones.get("required")
        if isinstance(required, list):
            for i, entry in enumerate(required):
                if isinstance(entry, dict) and "switch_class" not in entry:
                    errors.append(_err("missing_required",
                                       f"contract.zones.required[{i}].switch_class",
                                       "switch_class is required in each zones.required entry"))

    return errors


def validate_case_dict(payload: dict) -> dict:
    """
    Validate and normalize a case payload.

    Returns a normalized copy or raises TestCaseValidationError.
    """
    errors: list[dict] = []
    data = deepcopy(payload)

    if not isinstance(data, dict):
        raise TestCaseValidationError([_err("invalid_type", "<root>", "Case must be a mapping")])

    # Dispatch to v2 validator if apiVersion is set
    if data.get("apiVersion") == _V2_API_VERSION:
        data, errors = _validate_v2(data)
        if errors:
            raise TestCaseValidationError(errors)
        return data

    # v1 validation path
    required_top = ["meta", "plan", "switch_classes", "server_classes", "server_connections"]
    for key in required_top:
        if key not in data:
            errors.append(_err("missing_required", key, "Field is required"))

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append(_err("invalid_type", "meta", "meta must be a mapping"))
        meta = {}

    case_id = meta.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        errors.append(_err("missing_required", "meta.case_id", "case_id is required"))
    elif not CASE_ID_RE.match(case_id):
        errors.append(
            _err(
                "invalid_format",
                "meta.case_id",
                "case_id must match [a-z0-9_]+",
            )
        )

    if not isinstance(meta.get("name"), str) or not meta.get("name"):
        errors.append(_err("missing_required", "meta.name", "name is required"))

    if not isinstance(meta.get("version"), int):
        errors.append(_err("invalid_type", "meta.version", "version must be an integer"))

    if meta.get("managed_by") != "yaml":
        errors.append(
            _err(
                "invalid_value",
                "meta.managed_by",
                "managed_by must be literal 'yaml'",
            )
        )

    plan = data.get("plan")
    if not isinstance(plan, dict):
        errors.append(_err("invalid_type", "plan", "plan must be a mapping"))
        plan = {}

    if not isinstance(plan.get("name"), str) or not plan.get("name"):
        errors.append(_err("missing_required", "plan.name", "plan.name is required"))

    status = plan.get("status")
    if not isinstance(status, str):
        errors.append(_err("missing_required", "plan.status", "plan.status is required"))
    elif status not in VALID_PLAN_STATUSES:
        errors.append(
            _err(
                "invalid_enum",
                "plan.status",
                f"status must be one of {sorted(VALID_PLAN_STATUSES)}",
            )
        )

    for key in ("switch_classes", "server_classes", "server_connections"):
        if not isinstance(data.get(key), list):
            errors.append(_err("invalid_type", key, f"{key} must be a list"))

    # Optional aliases normalize for later phases (v1 support)
    for index, item in enumerate(data.get("switch_classes", []) or []):
        if isinstance(item, dict) and "id" in item and "switch_class_id" not in item:
            item["switch_class_id"] = item["id"]
            data["switch_classes"][index] = item
    for index, item in enumerate(data.get("server_classes", []) or []):
        if isinstance(item, dict) and "id" in item and "server_class_id" not in item:
            item["server_class_id"] = item["id"]
            data["server_classes"][index] = item

    if errors:
        raise TestCaseValidationError(errors)
    return data
