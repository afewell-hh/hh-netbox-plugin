#!/usr/bin/env bash
# Regression harness for #699's source-discovered Interchange Security guard.
set -euo pipefail

readonly source_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT

write_fixture() {
  mkdir -p "$fixture/scripts" "$fixture/.github/workflows" \
    "$fixture/netbox_hedgehog/tests/test_interchange"
  cp "$source_root/scripts/check_interchange_ci_selection.sh" "$fixture/scripts/"
  chmod +x "$fixture/scripts/check_interchange_ci_selection.sh"
  touch "$fixture/netbox_hedgehog/tests/test_interchange/test_core.py"
  touch "$fixture/netbox_hedgehog/tests/test_interchange_ui_red.py"
  touch "$fixture/netbox_hedgehog/tests/test_interchange_inventory_integrity.py"
  touch "$fixture/netbox_hedgehog/tests/test_interchange_audit_retention.py"
  touch "$fixture/netbox_hedgehog/tests/test_interchange_recursion_boundary.py"
  printf '# interchange-security-ci: required\n' > "$fixture/netbox_hedgehog/tests/test_fabric_seam_evidence.py"
  cp "$source_root/scripts/interchange_ci_selection_exceptions.tsv" "$fixture/scripts/"
  cat > "$fixture/.github/workflows/interchange-security-tests.yml" <<'EOF'
on:
  pull_request:
jobs:
  interchange-security:
    steps:
      - name: Run interchange security suites
        run: |
          python manage.py test \
            netbox_hedgehog.tests.test_interchange \
            netbox_hedgehog.tests.test_interchange_ui_red \
            netbox_hedgehog.tests.test_interchange_inventory_integrity \
            netbox_hedgehog.tests.test_interchange_audit_retention \
            netbox_hedgehog.tests.test_interchange_recursion_boundary \
            netbox_hedgehog.tests.test_fabric_seam_evidence \
            --verbosity=2
EOF
}

guard_passes() {
  (cd "$fixture" && bash scripts/check_interchange_ci_selection.sh) >/dev/null 2>&1
}

expect_failure() {
  local label=$1
  if guard_passes; then
    printf 'guard unexpectedly passed: %s\n' "$label" >&2
    exit 1
  fi
  printf 'interchange CI guard mutation: %s => fail closed\n' "$label"
}

write_fixture
guard_passes || { printf '%s\n' 'normal configuration failed' >&2; exit 1; }

printf 'netbox_hedgehog.tests.test_interchange_stale\t#699\tstale fixture exception\n' \
  >> "$fixture/scripts/interchange_ci_selection_exceptions.tsv"
expect_failure 'stale explicit exception'
write_fixture

touch "$fixture/netbox_hedgehog/tests/test_interchange_new_security.py"
expect_failure 'new unselected top-level interchange module'
printf 'netbox_hedgehog.tests.test_interchange_new_security\t#699\tdeliberate fixture exception\n' \
  >> "$fixture/scripts/interchange_ci_selection_exceptions.tsv"
guard_passes || { printf '%s\n' 'valid explicit exception failed' >&2; exit 1; }
rm -f "$fixture/netbox_hedgehog/tests/test_interchange_new_security.py"

write_fixture
touch "$fixture/netbox_hedgehog/tests/test_interchange_new_security.py"
printf 'netbox_hedgehog.tests.test_interchange_new_security\townerless\tinvalid fixture exception\n' \
  >> "$fixture/scripts/interchange_ci_selection_exceptions.tsv"
expect_failure 'exception without a named issue owner'
rm -f "$fixture/netbox_hedgehog/tests/test_interchange_new_security.py"

write_fixture
sed -i '/test_interchange_ui_red/d' "$fixture/.github/workflows/interchange-security-tests.yml"
expect_failure 'selected module removed'

write_fixture
sed -i 's/^            netbox_hedgehog.tests.test_interchange_ui_red/            # netbox_hedgehog.tests.test_interchange_ui_red/' \
  "$fixture/.github/workflows/interchange-security-tests.yml"
expect_failure 'selected module commented out'

write_fixture
sed -i 's/netbox_hedgehog.tests.test_interchange_ui_red/netbox_hedgehog.tests.test_interchange_ui_red_extra/' \
  "$fixture/.github/workflows/interchange-security-tests.yml"
expect_failure 'prefix decoy is not an exact root'

write_fixture
sed -i '/test_interchange_ui_red/d' "$fixture/.github/workflows/interchange-security-tests.yml"
sed -i '/--verbosity=2/a\          echo netbox_hedgehog.tests.test_interchange_ui_red' \
  "$fixture/.github/workflows/interchange-security-tests.yml"
expect_failure 'unrelated shell text is not a test root'

printf '%s\n' 'interchange CI selection guard regression harness: PASS'
