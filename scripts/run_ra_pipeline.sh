#!/usr/bin/env bash
# run_ra_pipeline.sh — Run the RA asset pipeline for a single variant
#
# Usage:
#   scripts/run_ra_pipeline.sh \
#     --case <case_id> \
#     --site <site_slug> \
#     --composition-dir <absolute_path> \
#     [--liquid-clone-of <air_variant_dir>] \
#     [--fe-only]
#
# Options:
#   --case               DIET case_id (fixture filename without .yaml)
#   --site               Unique site slug for device generation
#   --composition-dir    Absolute path to the target RA composition directory
#   --liquid-clone-of    (optional) If this is a liquid clone, path to the air variant's
#                        hhfab dir — skips hhfab validate, documents liquid=air equivalence
#   --fe-only            No backend fabric; skip wiring export / hhfab

set -euo pipefail

CASE_ID=""
SITE_SLUG=""
COMPOSITION_DIR=""
LIQUID_CLONE_OF=""
FE_ONLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --case) CASE_ID="$2"; shift 2 ;;
    --site) SITE_SLUG="$2"; shift 2 ;;
    --composition-dir) COMPOSITION_DIR="$2"; shift 2 ;;
    --liquid-clone-of) LIQUID_CLONE_OF="$2"; shift 2 ;;
    --fe-only) FE_ONLY=true; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$CASE_ID" || -z "$SITE_SLUG" || -z "$COMPOSITION_DIR" ]]; then
  echo "Usage: $0 --case <id> --site <slug> --composition-dir <path>" >&2
  exit 1
fi

NETBOX_DIR="/home/ubuntu/afewell-hh/netbox-docker"
PLUGIN_DIR="/home/ubuntu/afewell-hh/hh-netbox-plugin"
PIPELINE_BASE="/tmp/ra_pipeline"
ARTIFACT_DIR="${PIPELINE_BASE}/${CASE_ID}"
CONTAINER_TMP="/tmp/ra_pipeline/${CASE_ID}"

RUN() { cd "$NETBOX_DIR" && docker compose exec -T netbox python manage.py "$@" 2>/dev/null; }
SHELL_QUERY() { cd "$NETBOX_DIR" && docker compose exec -T netbox python manage.py shell -c "$1" 2>/dev/null | tail -1 | tr -d '[:space:]'; }

echo "=== Pipeline: $CASE_ID ==="

# 1. Setup artifact dirs
rm -rf "$ARTIFACT_DIR"
mkdir -p "$ARTIFACT_DIR/inputs" "$ARTIFACT_DIR/netbox" "$ARTIFACT_DIR/wiring" "$ARTIFACT_DIR/hhfab" "$ARTIFACT_DIR/logs"
cp "${PLUGIN_DIR}/netbox_hedgehog/test_cases/${CASE_ID}.yaml" "$ARTIFACT_DIR/inputs/"

# 2. Ingest case
echo "[1/7] Ingesting case $CASE_ID..."
RUN apply_diet_test_case --case "$CASE_ID" --clean > "$ARTIFACT_DIR/logs/ingest.log" 2>&1 || true
PLAN_ID=$(SHELL_QUERY "from netbox_hedgehog.models.topology_planning import TopologyPlan; p = TopologyPlan.objects.order_by('-pk').first(); print(p.pk)")
echo "  Plan ID: $PLAN_ID"
echo "$PLAN_ID" > "$ARTIFACT_DIR/logs/plan_id.txt"

# 3. Generate devices
echo "[2/7] Generating devices (plan $PLAN_ID, site $SITE_SLUG)..."
RUN generate_devices "$PLAN_ID" --site "$SITE_SLUG" > "$ARTIFACT_DIR/logs/generate.log" 2>&1
DEVICE_COUNT=$(SHELL_QUERY "from dcim.models import Device; print(Device.objects.filter(custom_field_data__hedgehog_plan_id=${PLAN_ID}).count())")
echo "  Devices: $DEVICE_COUNT"

# 4. Export inventory JSON and CSV
echo "[3/7] Exporting inventory..."
cd "$NETBOX_DIR" && docker compose exec -T netbox sh -c "mkdir -p /tmp/ra_pipeline/${CASE_ID}/netbox" 2>/dev/null || true
RUN export_plan_inventory_json "$PLAN_ID" --output "${CONTAINER_TMP}/netbox/plan_inventory.json" >> "$ARTIFACT_DIR/logs/generate.log" 2>&1 || echo "  WARN: JSON export failed"
RUN export_interface_connections_csv "$PLAN_ID" --output "${CONTAINER_TMP}/netbox/interface_connections.csv" >> "$ARTIFACT_DIR/logs/generate.log" 2>&1 || echo "  WARN: CSV export failed"
cd "$NETBOX_DIR" && docker compose cp "netbox:${CONTAINER_TMP}/netbox/." "$ARTIFACT_DIR/netbox/" 2>/dev/null || echo "  WARN: cp netbox failed"

# 5. Export wiring YAMLs
if [[ "$FE_ONLY" == "false" ]]; then
  echo "[4/7] Exporting wiring YAMLs..."
  cd "$NETBOX_DIR" && docker compose exec -T netbox sh -c "mkdir -p ${CONTAINER_TMP}/wiring_tmp" 2>/dev/null || true
  # Export all per-fabric wiring artifacts.  Some fabrics (e.g. frontend with mclag gap) may fail;
  # capture the error to the log and continue — the successful artifacts are preserved.
  RUN export_wiring_yaml "$PLAN_ID" --split-by-fabric --output "${CONTAINER_TMP}/wiring_tmp/wiring" >> "$ARTIFACT_DIR/logs/wiring_export.log" 2>&1 || true
  # Copy all wiring files to the host artifact dir.
  # NOTE: --split-by-fabric writes <base>-<fabric>.yaml inside the base directory, so the
  # container source for docker compose cp is the wiring_tmp/ directory itself.
  cd "$NETBOX_DIR" && docker compose cp "netbox:${CONTAINER_TMP}/wiring_tmp/." "$ARTIFACT_DIR/wiring/" 2>/dev/null || echo "  WARN: cp wiring failed"
  # All per-fabric artifacts are preserved — do NOT delete any wiring-<fabric>.yaml files here.
  # If hhfab cannot validate a particular fabric artifact, that gap is recorded in the hhfab logs
  # (see step 5) and documented in translation-notes; the artifact itself is kept.
  WIRING_FILES=$(find "$ARTIFACT_DIR/wiring/" -name "wiring-*.yaml" 2>/dev/null | sort)
  echo "  Wiring files: $(echo "$WIRING_FILES" | wc -l | tr -d ' ')"
else
  echo "[4/7] Skipping wiring export (FE-only variant — known mclag gap applies)"
  echo "FE-only: no backend wiring to export. FE wiring export blocked by known mclag gap." > "$ARTIFACT_DIR/wiring/WIRING_GAP.txt"
fi

# 6. hhfab validate + diagram
echo "[5/7] Running hhfab validate..."
if [[ "$FE_ONLY" == "true" ]]; then
  echo "Skipped: FE-only variant, no backend wiring available." > "$ARTIFACT_DIR/hhfab/hhfab_validate.log"
elif [[ -n "$LIQUID_CLONE_OF" ]] && [[ -d "$LIQUID_CLONE_OF" ]]; then
  echo "Liquid clone of ${LIQUID_CLONE_OF}. Topology identical to air variant." > "$ARTIFACT_DIR/hhfab/hhfab_validate.log"
  # Copy air variant's hhfab output (diagrams + per-fabric validate logs) if available.
  # Per-fabric validate logs are required by publish_ra_assets.sh (hhfab_validate_*.log pattern).
  if ls "${LIQUID_CLONE_OF}"/hhfab/*.drawio 2>/dev/null | head -1 > /dev/null; then
    cp "${LIQUID_CLONE_OF}"/hhfab/*.drawio "$ARTIFACT_DIR/hhfab/" 2>/dev/null || true
    echo "(Diagrams copied from air variant; topology identical.)" >> "$ARTIFACT_DIR/hhfab/hhfab_validate.log"
  fi
  if ls "${LIQUID_CLONE_OF}"/hhfab/hhfab_validate_*.log 2>/dev/null | head -1 > /dev/null; then
    cp "${LIQUID_CLONE_OF}"/hhfab/hhfab_validate_*.log "$ARTIFACT_DIR/hhfab/" 2>/dev/null || true
    echo "(Per-fabric validate logs copied from air variant; topology identical.)" >> "$ARTIFACT_DIR/hhfab/hhfab_validate.log"
  fi
else
  # Iterate over ALL per-fabric wiring artifacts discovered in the wiring/ dir.
  # We do not filter by fabric name — backend, frontend, or any arbitrary managed-fabric name
  # is treated identically here.  If hhfab cannot validate a specific fabric (e.g. frontend
  # with the known mclag gap), the failure is captured in a per-fabric log file and the
  # artifact is still kept.  See issue #326.
  WIRING_FILES_LIST=$(find "$ARTIFACT_DIR/wiring/" -name "wiring-*.yaml" 2>/dev/null | sort)
  if [[ -z "$WIRING_FILES_LIST" ]]; then
    echo "No per-fabric wiring files found; skipping hhfab." > "$ARTIFACT_DIR/hhfab/hhfab_validate.log"
  else
    for WIRING_F in $WIRING_FILES_LIST; do
      FABRIC_NAME=$(basename "$WIRING_F" .yaml | sed 's/^wiring-//')
      HHFAB_WORK="/tmp/hhfab_work_${CASE_ID}_${FABRIC_NAME}"
      rm -rf "$HHFAB_WORK"
      mkdir -p "$HHFAB_WORK"
      cp "$WIRING_F" "${HHFAB_WORK}/wiring.yaml"
      pushd "$HHFAB_WORK" > /dev/null
      VALIDATE_LOG="${ARTIFACT_DIR}/hhfab/hhfab_validate_${FABRIC_NAME}.log"
      hhfab init --dev --force > "${ARTIFACT_DIR}/hhfab/hhfab_init_${FABRIC_NAME}.log" 2>&1 || true
      if hhfab validate > "$VALIDATE_LOG" 2>&1; then
        echo "  [hhfab] ${FABRIC_NAME}: validate OK"
      else
        echo "  [hhfab] ${FABRIC_NAME}: validate FAILED (see ${VALIDATE_LOG}; artifact preserved)"
      fi
      hhfab diagram > "${ARTIFACT_DIR}/hhfab/hhfab_diagram_${FABRIC_NAME}.log" 2>&1 || true
      find . -name "*.drawio" -exec cp {} "${ARTIFACT_DIR}/hhfab/${FABRIC_NAME}.drawio" \; 2>/dev/null || true
      popd > /dev/null
      rm -rf "$HHFAB_WORK"
    done
    # Write a combined validate summary for easy review
    cat "${ARTIFACT_DIR}/hhfab/hhfab_validate_"*.log > "${ARTIFACT_DIR}/hhfab/hhfab_validate.log" 2>/dev/null || true
  fi
fi

# 7. Write translation-notes
echo "[6/7] Writing translation-notes..."
cat > "$ARTIFACT_DIR/inputs/translation-notes.md" << NOTES_EOF
# Translation Notes: ${CASE_ID}

## Pass-1 Status: complete-pass1

## Generation Summary
- Plan ID at generation: ${PLAN_ID}
- Site slug: ${SITE_SLUG}
- Device count: ${DEVICE_COUNT:-unknown}

## Wiring Artifacts
All managed-fabric wiring artifacts produced by --split-by-fabric are preserved in
wiring/. Each wiring-<fabric>.yaml file is independently consumable.
See hhfab/ for per-fabric validation logs (hhfab_validate_<fabric>.log).

If a fabric's wiring export or hhfab validation failed, the artifact is still
preserved and the failure is recorded in the corresponding log file.
Known gap: frontend (DS5000 L3MH variants) export may fail with a mclag gap —
"Switch references group 'fe-mclag' but no PlanMCLAGDomain exists". This is
tracked as a pre-existing DIET gap. The artifact is kept even if export partially
failed; see wiring_export.log for the full error.

$(if [[ "$FE_ONLY" == "true" ]]; then echo "## FE-Only Variant
This variant has no backend fabric by RA design. Only a frontend fabric is defined.
Wiring export and hhfab validation are skipped (FE-only; no backend wiring available).
Frontend wiring export is also blocked by the known mclag gap above."; fi)

$(if [[ -n "$LIQUID_CLONE_OF" ]]; then echo "## Liquid Cooling Variant
This variant is topologically identical to the corresponding air-cooled variant.
Cooling medium and rack density differ only (not modeled in DIET).
Reference air-cooled variant for the same wiring topology."; fi)

## SH Distribution Note (if applicable)
Single-homed scale-out variants use same-switch grouped-per-leaf distribution.
Servers are allocated in contiguous blocks per leaf (first N/2 → leaf A, rest → leaf B).

## XOC Composition Note (if applicable)
XOC variants are modeled as a single scaled DIET plan with the combined server
count. Per-OPG-unit composition semantics are not modeled in DIET pass-1.

NOTES_EOF

# 8. FK verification (before reset)
echo "[fk-check] Verifying transceiver_module_type FKs on PlanServerConnection..."
FK_QUERY="from netbox_hedgehog.models.topology_planning import PlanServerConnection; conns = PlanServerConnection.objects.filter(server_class__plan_id=${PLAN_ID}); total = conns.count(); non_null = conns.exclude(transceiver_module_type=None).count(); print(f'total={total} non_null_transceiver_fk={non_null}')"
FK_RESULT=$(SHELL_QUERY "$FK_QUERY" 2>/dev/null || echo "fk-check-failed")
echo "  FK result: $FK_RESULT"
echo "$FK_RESULT" > "$ARTIFACT_DIR/logs/fk_verification.txt"

# 8b. Publish to RA repo
echo "[7/7] Publishing to $COMPOSITION_DIR ..."
"${PLUGIN_DIR}/scripts/publish_ra_assets.sh" \
  --artifact-root "$ARTIFACT_DIR" \
  --composition-dir "$COMPOSITION_DIR"

# 9. Reset plan data
echo "[cleanup] Resetting plan $PLAN_ID..."
RUN reset_diet_data --plan "$PLAN_ID" --no-input > "$ARTIFACT_DIR/logs/reset.log" 2>&1 || echo "  WARN: reset failed"

echo "=== Done: $CASE_ID ==="
