"""Schema validation for YAML DIET test cases."""

from __future__ import annotations

import re
from copy import deepcopy

from .exceptions import TestCaseValidationError

CASE_ID_RE = re.compile(r"^[a-z0-9_]+$")
VALID_PLAN_STATUSES = {"draft", "review", "approved", "exported"}


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


def validate_case_dict(payload: dict) -> dict:
    """
    Validate and normalize a case payload.

    Returns a normalized copy or raises TestCaseValidationError.
    """
    errors: list[dict] = []
    data = deepcopy(payload)

    if not isinstance(data, dict):
        raise TestCaseValidationError([_err("invalid_type", "<root>", "Case must be a mapping")])

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

