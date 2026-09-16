#!/usr/bin/env bash
# Fail closed when a plugin-enabled Django workflow omits #684's host setting.
set -euo pipefail

required='DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024'
workflows=(
  .github/workflows/ci-diet-tests.yml
  .github/workflows/browser-ux-tests.yml
  .github/workflows/e2e-tests.yml
)

for workflow in "${workflows[@]}"; do
  case "$workflow" in
    .github/workflows/ci-diet-tests.yml) expected=4 ;;
    .github/workflows/browser-ux-tests.yml|.github/workflows/e2e-tests.yml) expected=1 ;;
  esac
  plugin_count=$(grep -Fc 'netbox_hedgehog' "$workflow" || true)
  setting_count=$(grep -Fc "$required" "$workflow" || true)
  if (( plugin_count == 0 || setting_count < expected )); then
    echo "$workflow: plugin-enabled NetBox configuration must set $required ($setting_count/$expected found)" >&2
    exit 1
  fi
done
