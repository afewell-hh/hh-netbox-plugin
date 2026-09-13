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
exec docker compose exec -T netbox python -u manage.py test "$@" \
    "--testrunner=$TEST_RUNNER"
