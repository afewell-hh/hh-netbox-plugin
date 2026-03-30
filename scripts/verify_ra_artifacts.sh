#!/usr/bin/env bash
# verify_ra_artifacts.sh — Artifact-collection regression checker for the RA pipeline
#
# Verifies that a completed RA pipeline artifact root:
#   1. Contains at least one wiring-<fabric>.yaml file
#   2. Does NOT contain backend-only files with legacy names (wiring-backend only)
#      while also containing other per-fabric export output (i.e. no deletion of
#      non-backend artifacts happened)
#   3. Has a corresponding hhfab_validate_<fabric>.log for every wiring file
#      (hhfab was attempted for every fabric, not just backend-named ones)
#
# This is a post-run contract check, not a substitute for a full pipeline run.
# See also: issue #326 (RA pipeline drops per-fabric wiring artifacts)
#
# Usage:
#   scripts/verify_ra_artifacts.sh --artifact-root <path>
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed

set -uo pipefail

ARTIFACT_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --artifact-root) ARTIFACT_ROOT="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$ARTIFACT_ROOT" ]]; then
  echo "Usage: $0 --artifact-root <path>" >&2
  exit 1
fi

if [[ ! -d "$ARTIFACT_ROOT" ]]; then
  echo "Artifact root does not exist: $ARTIFACT_ROOT" >&2
  exit 1
fi

WIRING_DIR="${ARTIFACT_ROOT}/wiring"
HHFAB_DIR="${ARTIFACT_ROOT}/hhfab"
PASS=true

echo "=== Verifying RA artifact root: $ARTIFACT_ROOT ==="

# --- Check 1: wiring/ exists and is non-empty ---
if [[ ! -d "$WIRING_DIR" ]]; then
  echo "FAIL: wiring/ directory missing"
  PASS=false
else
  WIRING_FILES=$(find "$WIRING_DIR" -name "wiring-*.yaml" 2>/dev/null | sort)
  WIRING_COUNT=$(echo "$WIRING_FILES" | grep -c . || true)
  if [[ "$WIRING_COUNT" -eq 0 ]]; then
    echo "FAIL: no wiring-*.yaml files found under wiring/"
    PASS=false
  else
    echo "OK:   wiring/ contains $WIRING_COUNT file(s):"
    echo "$WIRING_FILES" | sed 's/^/        /'
  fi
fi

# --- Check 2: no frontend artifact was silently deleted ---
# If the export log mentions a frontend fabric and the wiring file is absent,
# that is evidence of the old deletion behavior.
if [[ -f "${ARTIFACT_ROOT}/logs/wiring_export.log" ]]; then
  EXPORTED_FABRICS=$(grep -oE "wiring-[a-z0-9_-]+\.yaml" "${ARTIFACT_ROOT}/logs/wiring_export.log" \
    | sed 's/wiring-//; s/\.yaml//' | sort -u)
  for FAB in $EXPORTED_FABRICS; do
    EXPECTED="${WIRING_DIR}/wiring-${FAB}.yaml"
    if [[ ! -f "$EXPECTED" ]]; then
      echo "FAIL: wiring-${FAB}.yaml was mentioned in export log but is absent from wiring/"
      echo "      This suggests the artifact was deleted post-export (issue #326 regression)"
      PASS=false
    else
      echo "OK:   wiring-${FAB}.yaml present (exported and preserved)"
    fi
  done
fi

# --- Check 3: hhfab validate log exists for every wiring file ---
if [[ -d "$HHFAB_DIR" && "$WIRING_COUNT" -gt 0 ]]; then
  for WIRING_F in $WIRING_FILES; do
    FABRIC=$(basename "$WIRING_F" .yaml | sed 's/^wiring-//')
    VALIDATE_LOG="${HHFAB_DIR}/hhfab_validate_${FABRIC}.log"
    if [[ ! -f "$VALIDATE_LOG" ]]; then
      echo "FAIL: no hhfab_validate_${FABRIC}.log — hhfab was not attempted for fabric '${FABRIC}'"
      echo "      This suggests hhfab iteration still uses backend-only filename patterns (issue #326)"
      PASS=false
    else
      echo "OK:   hhfab_validate_${FABRIC}.log present"
    fi
  done
fi

# --- Check 4: backend-only filter not in play ---
# Heuristic: if >1 fabric appears in the wiring/ dir, hhfab logs for ALL fabrics must exist.
# A pipeline that only ran hhfab for backend-named files would be missing non-backend logs.
if [[ "$WIRING_COUNT" -gt 1 ]] && [[ -d "$HHFAB_DIR" ]]; then
  HHFAB_LOG_COUNT=$(find "$HHFAB_DIR" -name "hhfab_validate_*.log" 2>/dev/null | grep -v hhfab_validate\.log | wc -l | tr -d ' ')
  if [[ "$HHFAB_LOG_COUNT" -lt "$WIRING_COUNT" ]]; then
    echo "FAIL: $WIRING_COUNT wiring files but only $HHFAB_LOG_COUNT hhfab validate logs"
    echo "      hhfab was not attempted for all fabrics (backend-only filter may still be active)"
    PASS=false
  else
    echo "OK:   hhfab validate attempted for all $WIRING_COUNT fabric(s)"
  fi
fi

echo ""
if [[ "$PASS" == "true" ]]; then
  echo "=== All checks PASSED ==="
  exit 0
else
  echo "=== One or more checks FAILED ==="
  exit 1
fi
