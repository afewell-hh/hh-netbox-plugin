#!/usr/bin/env bash
# Fail closed if an in-scope interchange-security test root is not selected by
# a PR-triggered Django test command. Roots are discovered from the test layout:
# the core test_interchange package, top-level test_interchange*.py modules,
# and explicit source markers for legacy suites whose name predates the
# interchange namespace. This prevents a new top-level module being forgotten
# in the workflow declaration (#699).
set -euo pipefail

readonly test_root='netbox_hedgehog/tests'
readonly exceptions_file='scripts/interchange_ci_selection_exceptions.tsv'
readonly marker='interchange-security-ci: required'

declare -a discovered_roots=()
declare -A exceptions=()

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

path_to_module() {
  local path=$1
  path=${path%.py}
  printf '%s\n' "${path//\//.}"
}

discover_roots() {
  local path module

  if [[ -d "$test_root/test_interchange" ]] && \
      find "$test_root/test_interchange" -type f -name 'test_*.py' -print -quit | grep -q .; then
    printf '%s\n' 'netbox_hedgehog.tests.test_interchange'
  fi

  while IFS= read -r -d '' path; do
    path_to_module "$path"
  done < <(find "$test_root" -maxdepth 1 -type f -name 'test_interchange*.py' -print0 | sort -z)

  while IFS= read -r -d '' path; do
    module=$(path_to_module "$path")
    printf '%s\n' "$module"
  done < <(grep -rlZ --include='test_*.py' -E "^[[:space:]]*#[[:space:]]*$marker[[:space:]]*$" "$test_root")
}

load_exceptions() {
  local line module owner reason trailing
  [[ -f "$exceptions_file" ]] || fail "Missing $exceptions_file"

  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    IFS=$'\t' read -r module owner reason trailing <<< "$line"
    [[ -z "$trailing" && -n "$module" && "$owner" =~ ^#[0-9]+$ && -n "$reason" ]] ||
      fail "Invalid exception in $exceptions_file: $line"
    [[ -z ${exceptions[$module]+x} ]] || fail "Duplicate exception for $module"
    exceptions[$module]="$owner: $reason"
  done < "$exceptions_file"
}

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

mapfile -t discovered_roots < <(discover_roots | sort -u)
(( ${#discovered_roots[@]} > 0 )) || fail 'No interchange-security test roots were discovered'
load_exceptions

declare -A discovered=()
for root in "${discovered_roots[@]}"; do
  discovered[$root]=1
done
for root in "${!exceptions[@]}"; do
  [[ -n ${discovered[$root]+x} ]] ||
    fail "Exception names no discovered interchange-security root: $root"
done

while IFS= read -r -d '' workflow; do
  grep -Eq '^[[:space:]]*pull_request:' "$workflow" || continue

  selected=0
  excepted=0
  missing=()
  for root in "${discovered_roots[@]}"; do
    if has_django_selection "$workflow" "$root"; then
      ((selected += 1))
    elif [[ -n ${exceptions[$root]+x} ]]; then
      ((excepted += 1))
    else
      missing+=("$root")
    fi
  done

  if (( ${#missing[@]} == 0 )); then
    printf 'interchange CI selection: %s\n' "$workflow"
    printf 'interchange CI coverage: %d discovered root(s); %d selected; %d explicit exception(s)\n' \
      "${#discovered_roots[@]}" "$selected" "$excepted"
    exit 0
  fi
done < <(find .github/workflows -type f \( -name '*.yml' -o -name '*.yaml' \) -print0)

printf '%s\n' 'No PR-triggered Django test command covers every discovered interchange-security root:' >&2
printf '  %s\n' "${discovered_roots[@]}" >&2
printf '%s\n' 'Use one uncommented exact root argument per line after `manage.py test`.' >&2
printf '%s\n' 'A deliberate exclusion requires one tab-separated module, #issue owner, and reason in scripts/interchange_ci_selection_exceptions.tsv.' >&2
exit 1
