"""Runtime helpers for YAML case application."""

from __future__ import annotations

from pathlib import Path

from .ingest import apply_case
from .loader import discover_case_files, list_case_ids as _list_case_ids, load_case


def list_case_ids(root: str | Path | None = None) -> list[str]:
    return _list_case_ids(root=root)


def apply_case_id(
    case_id: str,
    *,
    root: str | Path | None = None,
    clean: bool = False,
    prune: bool = False,
    reference_mode: str = "ensure",
):
    case = load_case(case_id, root=root)
    return apply_case(
        case,
        clean=clean,
        prune=prune,
        reference_mode=reference_mode,
    )


def apply_all_cases(
    *,
    root: str | Path | None = None,
    clean: bool = False,
    prune: bool = False,
    reference_mode: str = "ensure",
):
    applied = []
    for case_file in discover_case_files(root=root):
        case_id = case_file.stem
        plan = apply_case_id(
            case_id,
            root=root,
            clean=clean,
            prune=prune,
            reference_mode=reference_mode,
        )
        applied.append((case_id, plan))
    return applied

