#!/usr/bin/env bash
# Supported host entry point. Keep invocation logic in the mounted package so
# its regression test also runs in CI's inner-package mount shape.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$SCRIPT_DIR/../netbox_hedgehog/scripts/run_diet_tests.sh" "$@"
