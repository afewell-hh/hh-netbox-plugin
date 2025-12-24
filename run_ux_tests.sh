#!/bin/bash
#
# Run browser UX tests for NetBox Hedgehog Plugin
#
# These tests run on the HOST and connect to NetBox via HTTP at localhost:8000
# They do NOT require Django to be installed on the host.
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Running Browser UX Tests${NC}"
echo "========================================"
echo "NetBox URL: ${NETBOX_URL:-http://localhost:8000}"
echo "Username: ${NETBOX_USERNAME:-admin}"
echo ""

# Change to the test_ux directory
cd "$(dirname "$0")/netbox_hedgehog/tests/test_ux"

# Run pytest with explicit path to avoid parent conftest.py files
# Use --override-ini to disable pytest-django
python3 -m pytest \
    --override-ini="addopts=-p no:django" \
    --browser chromium \
    --headed=false \
    -v \
    "$@"

echo ""
echo -e "${GREEN}UX Tests Complete${NC}"
