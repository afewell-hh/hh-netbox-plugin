"""Test-only restricted I-JSON profile, RFC 8785 canonicalization, and
content-integrity binding for the T4 interchange contract (#672 / #673).

This module is EVIDENCE INFRASTRUCTURE. It is not the production interchange
implementation, not a schema, and must never be imported by production code.
The production canonicalizer implements RFC 8785 against the published
specification and its own test vectors; nothing here establishes its authority
(#672 N3).

Why the profile is restricted
-----------------------------
RFC 8785 renders numbers with the ECMAScript ``Number::toString`` algorithm,
i.e. IEEE 754 doubles. Two consequences bite an interchange format:

* integers beyond 2**53 do not round-trip exactly, and
* YAML's ``1`` versus ``1.0`` typing can canonicalize differently from the same
  value written in JSON.

Either produces a content-integrity digest that differs between YAML and JSON
encodings of the *same* catalog -- surfacing as a spurious mismatch rather than
an obvious bug. The profile therefore REJECTS floats and out-of-range integers
instead of rendering them, which is what "unsafe non-representable values
reject" means in #673.

Under those restrictions, and with astral characters barred from keys, JCS
reduces exactly to ``json.dumps(sort_keys=True, separators=(",", ":"),
ensure_ascii=False)``:

* JCS sorts keys by UTF-16 code unit; Python sorts by code point. These agree
  for every character in the BMP, so barring astral key characters makes the
  orders identical rather than merely usually-identical.
* JCS number rendering reduces to plain decimal for safe integers.
* JCS string escaping matches ``json.dumps`` (short forms for \\b \\f \\n \\r
  \\t, ``\\u00xx`` for other control characters).

Widening the profile is not a code change here -- it requires the full
ECMAScript number algorithm plus the RFC 8785 numeric test vectors.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: Versioned identifier from the accepted product decision (#672).
BINDING_ALGORITHM = "aid-jcs-rfc8785-sha256-v1"

#: IEEE 754 double exact-integer bound.
MAX_SAFE_INTEGER = 2 ** 53 - 1


class RestrictedProfileError(ValueError):
    """A value cannot be represented in the restricted I-JSON profile."""


def _check(value: Any, path: str) -> None:
    if value is None or isinstance(value, str):
        if isinstance(value, str):
            return
        return
    if isinstance(value, bool):
        # Must precede int: bool is a subclass of int.
        return
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise RestrictedProfileError(
                f"{path}: integer {value} exceeds the exact-integer range of the "
                f"canonical number rendering; represent it as a string")
        return
    if isinstance(value, float):
        raise RestrictedProfileError(
            f"{path}: floating-point values are not representable in this profile "
            f"(YAML/JSON typing and IEEE 754 rendering would make the digest "
            f"encoding-dependent); use an integer or string")
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise RestrictedProfileError(f"{path}: mapping key {key!r} is not a string")
            if any(ord(ch) > 0xFFFF for ch in key):
                raise RestrictedProfileError(
                    f"{path}.{key}: key contains a non-BMP character, whose UTF-16 "
                    f"sort order differs from code-point order")
            _check(item, f"{path}.{key}")
        return
    raise RestrictedProfileError(f"{path}: unsupported type {type(value).__name__}")


def canonicalize(value: Any) -> bytes:
    """Return the RFC 8785 canonical UTF-8 form, or raise for unsafe values."""
    _check(value, "$")
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_integrity_digest(value: Any) -> str:
    """SHA-256 hex digest over the canonical form."""
    return hashlib.sha256(canonicalize(value)).hexdigest()


def content_integrity_binding(value: Any) -> dict:
    """The portable binding: versioned algorithm identifier plus digest."""
    return {"algorithm": BINDING_ALGORITHM, "digest": content_integrity_digest(value)}
