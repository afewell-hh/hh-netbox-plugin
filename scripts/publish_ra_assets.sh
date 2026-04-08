#!/usr/bin/env bash
#
# publish_ra_assets.sh — publish RA pipeline artifacts into a training-ra/inference-ra
# composition directory using the current flat asset layout.
#
# Source layout (pipeline artifact root):
#   <artifact_root>/
#     wiring/wiring-*.yaml          (per-fabric wiring; may include WIRING_GAP.txt)
#     hhfab/<fabric>.drawio         (hhfab diagrams)
#     hhfab/hhfab_validate_<f>.log  (per-fabric hhfab validation results)
#     inputs/  netbox/  logs/       (pipeline-local; NOT published)
#
# Destination layout (flat, matches current training-ra structure):
#   <composition_dir>/
#     wiring/wiring-*.yaml
#     diagrams/hhfab/<fabric>.drawio
#     diagrams/hhfab/hhfab_validate_<fabric>.log
#
# Each destination section is replaced atomically at the directory level so
# repeated runs are deterministic and leave no stale files behind.
#
# Usage:
#   scripts/publish_ra_assets.sh \
#     --artifact-root <path> \
#     --composition-dir <path>

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/publish_ra_assets.sh \
    --artifact-root <path> \
    --composition-dir <path>

Example:
  scripts/publish_ra_assets.sh \
    --artifact-root /tmp/ra_pipeline/training_opg128_clos_ro_air_2srv \
    --composition-dir /home/ubuntu/afewell-hh/training-ra/compositions/OPG-128/clos-ro--example
EOF
}

ARTIFACT_ROOT=""
COMPOSITION_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --artifact-root)
      ARTIFACT_ROOT="${2:-}"
      shift 2
      ;;
    --composition-dir)
      COMPOSITION_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$ARTIFACT_ROOT" || -z "$COMPOSITION_DIR" ]]; then
  usage >&2
  exit 1
fi

if [[ ! -d "$ARTIFACT_ROOT" ]]; then
  echo "Artifact root does not exist: $ARTIFACT_ROOT" >&2
  exit 1
fi

if [[ ! -d "$COMPOSITION_DIR" ]]; then
  echo "Composition directory does not exist: $COMPOSITION_DIR" >&2
  exit 1
fi

WIRING_SRC="${ARTIFACT_ROOT}/wiring"
HHFAB_SRC="${ARTIFACT_ROOT}/hhfab"
PUBLISHED=0

# --- wiring/ → <comp>/wiring/ ---
# Atomic directory replace: removes stale files from prior runs.
if [[ -d "$WIRING_SRC" ]]; then
  WIRING_DEST="${COMPOSITION_DIR}/wiring"
  rm -rf "$WIRING_DEST"
  mkdir -p "$WIRING_DEST"
  cp -a "${WIRING_SRC}/." "${WIRING_DEST}/"
  echo "  wiring/         →  ${WIRING_DEST}"
  PUBLISHED=$((PUBLISHED + 1))
fi

# --- hhfab/ → <comp>/diagrams/hhfab/ ---
# Only publishes: *.drawio diagrams and hhfab_validate_*.log files.
# Pipeline-internal logs (hhfab_init_*.log, hhfab_diagram_*.log, hhfab_validate.log)
# are not included in the published composition.
if [[ -d "$HHFAB_SRC" ]]; then
  HHFAB_DEST="${COMPOSITION_DIR}/diagrams/hhfab"
  rm -rf "$HHFAB_DEST"
  mkdir -p "$HHFAB_DEST"
  find "$HHFAB_SRC" -maxdepth 1 \( -name "*.drawio" -o -name "hhfab_validate_*.log" \) \
    -exec cp {} "${HHFAB_DEST}/" \;
  echo "  hhfab/          →  ${HHFAB_DEST}"
  PUBLISHED=$((PUBLISHED + 1))
fi

if [[ "$PUBLISHED" -eq 0 ]]; then
  echo "WARNING: nothing published — wiring/ and hhfab/ both absent from $ARTIFACT_ROOT" >&2
  exit 1
fi

echo "Published RA assets:"
echo "  source:      $ARTIFACT_ROOT"
echo "  destination: $COMPOSITION_DIR"
