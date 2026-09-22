#!/usr/bin/env bash
# Fail closed if no PR-triggered Django test command selects every interchange
# security root. Discover workflows from source instead of naming a workflow
# file here: workflow renames/splits must preserve the actual selection.
set -euo pipefail

readonly -a required_roots=(
  'netbox_hedgehog.tests.test_interchange'
  'netbox_hedgehog.tests.test_interchange_ui_red'
  'netbox_hedgehog.tests.test_interchange_inventory_integrity'
  'netbox_hedgehog.tests.test_fabric_seam_evidence'
)

has_django_selection() {
  local workflow=$1
  local root=$2

  awk -v root="$root" '
    {
      uncommented = $0
      sub(/^[[:space:]]*/, "", uncommented)
      if (uncommented ~ /^#/) { next }
    }
    /manage\.py test/ { in_test_command = 1 }
    in_test_command {
      candidate = $0
      sub(/#.*/, "", candidate)
      gsub(/^[[:space:]]+|[[:space:]\\]+$/, "", candidate)
      if (candidate == root) { found = 1; exit }
    }
    in_test_command && /^[[:space:]]*-[[:space:]]+name:/ { in_test_command = 0 }
    END { exit !found }
  ' "$workflow"
}

while IFS= read -r -d '' workflow; do
  grep -Eq '^[[:space:]]*pull_request:' "$workflow" || continue

  selected=true
  for root in "${required_roots[@]}"; do
    has_django_selection "$workflow" "$root" || {
      selected=false
      break
    }
  done

  if "$selected"; then
    printf 'interchange CI selection: %s\n' "$workflow"
    exit 0
  fi
done < <(find .github/workflows -type f \( -name '*.yml' -o -name '*.yaml' \) -print0)

printf '%s\n' 'No PR-triggered Django test command selects every interchange security root:' >&2
printf '  %s\n' "${required_roots[@]}" >&2
printf '%s\n' 'Use one uncommented root argument per line after `manage.py test`; quoted or combined roots are intentionally rejected.' >&2
printf '%s\n' 'Keep future ingress/quarantine tests under test_interchange, or extend this declaration and the CI selection in the same change.' >&2
exit 1
