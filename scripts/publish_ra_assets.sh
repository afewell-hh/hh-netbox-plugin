#!/usr/bin/env bash
#
# publish_ra_assets.sh
#
# Copy a locally generated RA artifact bundle into the final per-variant
# composition folder inside the training-ra or inference-ra repository.
#
# Expected source layout:
#   <artifact_root>/
#     inputs/
#     netbox/
#     wiring/
#     hhfab/
#     logs/
#
# Destination layout:
#   <composition_dir>/generated/
#     inputs/
#     netbox/
#     wiring/
#     hhfab/
#     logs/
#
# The destination is replaced directory-by-directory for deterministic updates.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/publish_ra_assets.sh \
    --artifact-root <path> \
    --composition-dir <path>

Example:
  scripts/publish_ra_assets.sh \
    --artifact-root /tmp/ra-artifacts/training/OPG-128/clos-ro--example \
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

DEST_ROOT="${COMPOSITION_DIR}/generated"
mkdir -p "$DEST_ROOT"

copy_section() {
  local section="$1"
  local src="${ARTIFACT_ROOT}/${section}"
  local dst="${DEST_ROOT}/${section}"

  if [[ ! -d "$src" ]]; then
    return 0
  fi

  rm -rf "$dst"
  mkdir -p "$dst"
  cp -a "${src}/." "$dst/"
}

copy_section "inputs"
copy_section "netbox"
copy_section "wiring"
copy_section "hhfab"
copy_section "logs"

echo "Published generated assets:"
echo "  source:      $ARTIFACT_ROOT"
echo "  destination: $DEST_ROOT"

