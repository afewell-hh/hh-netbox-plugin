#!/usr/bin/env bash
# Run DIET tests with the test-only DIET-643 runner enabled.
#
# Run from any directory. By default the script uses the sibling netbox-docker
# checkout; isolated lanes can set NETBOX_DOCKER_DIR and normal Compose
# environment variables (for example COMPOSE_PROJECT_NAME/COMPOSE_FILE).
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd -- "$SCRIPT_DIR/../.." && pwd)
NETBOX_DOCKER_DIR=${NETBOX_DOCKER_DIR:-"$REPO_DIR/../netbox-docker"}
TEST_RUNNER=netbox_hedgehog.tests.runner.DietTestRunner
DEFAULT_LABEL=netbox_hedgehog.tests.test_topology_planning

if [[ ! -d "$NETBOX_DOCKER_DIR" ]]; then
    echo "NETBOX_DOCKER_DIR does not exist: $NETBOX_DOCKER_DIR" >&2
    exit 2
fi

for argument in "$@"; do
    if [[ "$argument" == --testrunner || "$argument" == --testrunner=* ]]; then
        echo "run_diet_tests.sh selects the DIET test runner; do not pass --testrunner" >&2
        exit 2
    fi
done

if [[ $# -eq 0 ]]; then
    set -- "$DEFAULT_LABEL"
fi

cd "$NETBOX_DOCKER_DIR"
# Interchange containment needs repository files absent from the usual package
# bind mount. Supply only its inventory and identity inputs, never .git/config,
# host configuration or the rest of the checkout. This is a temporary snapshot,
# not the live CI mount (whose separate environment variable retains statvfs).
for argument in "$@"; do
    if [[ "$argument" == netbox_hedgehog.tests.test_interchange* ]]; then
        evidence_dir=$(mktemp -d /tmp/hnp-reaper-evidence.XXXXXXXX)
        trap 'rmdir "$evidence_dir" 2>/dev/null || true' EXIT
        python3 "$REPO_DIR/scripts/prove_reaper_lane.py" \
            --output "$evidence_dir/reaper-container-evidence.json"
        snapshot_files=(AGENTS.md netbox_hedgehog/__init__.py
            netbox_hedgehog/tests/test_interchange/test_checkout_containment.py)
        for relative in .github scripts netbox_hedgehog/scripts deploy deployment deployments docker dev-setup; do
            [[ ! -e "$REPO_DIR/$relative" ]] || snapshot_files+=("$relative")
        done
        shopt -s nullglob
        for source in "$REPO_DIR"/docker-compose*.yml "$REPO_DIR"/docker-compose*.yaml \
                      "$REPO_DIR"/compose*.yml "$REPO_DIR"/compose*.yaml; do
            snapshot_files+=("${source#"$REPO_DIR/"}")
        done
        tar -C "$REPO_DIR" --exclude=__pycache__ --exclude=.git -cf - "${snapshot_files[@]}" \
            -C "$evidence_dir" reaper-container-evidence.json |
            docker compose exec -T netbox sh -c '
                set -eu
                snapshot=$(mktemp -d /tmp/hnp-checkout.XXXXXXXX)
                cleanup() {
                    case "$snapshot" in /tmp/hnp-checkout.*)
                        chmod -R u+w "$snapshot"
                        rm -rf -- "$snapshot" ;;
                    esac
                }
                trap cleanup EXIT
                tar -xf - -C "$snapshot"
                chmod -R a-w "$snapshot"
                export HNP_TEST_LOCAL_CHECKOUT_ROOT="$snapshot"
                python -u manage.py test "$@"
            ' sh "$@" "--testrunner=$TEST_RUNNER"
        rm -- "$evidence_dir/reaper-container-evidence.json"
        rmdir -- "$evidence_dir"
        trap - EXIT
        exit 0
    fi
done
exec docker compose exec -T netbox python -u manage.py test "$@" \
    "--testrunner=$TEST_RUNNER"
