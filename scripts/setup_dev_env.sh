#!/usr/bin/env bash
# setup_dev_env.sh — ensure netbox-docker is configured to load the netbox_hedgehog plugin.
#
# The netbox-docker/configuration/plugins.py file must declare PLUGINS = ["netbox_hedgehog"].
# Without this, all tests fail with:
#   RuntimeError: Model class netbox_hedgehog.models.* doesn't declare an explicit app_label
#   and isn't in an application in INSTALLED_APPS.
#
# Run this once after cloning or after any full reset of the netbox-docker environment.
# It is idempotent — safe to run multiple times.

set -euo pipefail

NETBOX_DOCKER_DIR="${NETBOX_DOCKER_DIR:-/home/ubuntu/afewell-hh/netbox-docker}"
PLUGINS_FILE="${NETBOX_DOCKER_DIR}/configuration/plugins.py"

if [[ ! -d "$NETBOX_DOCKER_DIR" ]]; then
  echo "ERROR: netbox-docker directory not found: $NETBOX_DOCKER_DIR" >&2
  echo "Set NETBOX_DOCKER_DIR to the correct path." >&2
  exit 1
fi

if [[ ! -f "$PLUGINS_FILE" ]]; then
  echo "ERROR: plugins.py not found: $PLUGINS_FILE" >&2
  exit 1
fi

# Check if already configured
if grep -q '^PLUGINS *= *\["netbox_hedgehog"\]' "$PLUGINS_FILE" 2>/dev/null; then
  echo "plugins.py already configured: PLUGINS = [\"netbox_hedgehog\"] found."
else
  # Insert after the first comment block (before first commented-out PLUGINS line)
  # Use a temp file for safety
  TMP=$(mktemp)
  awk '
    /^# PLUGINS = \["netbox_bgp"\]/ && !inserted {
      print "PLUGINS = [\"netbox_hedgehog\"]"
      inserted = 1
    }
    { print }
  ' "$PLUGINS_FILE" > "$TMP"
  mv "$TMP" "$PLUGINS_FILE"
  echo "Added PLUGINS = [\"netbox_hedgehog\"] to $PLUGINS_FILE"
fi

# Restart container to pick up the change
cd "$NETBOX_DOCKER_DIR"
echo "Restarting netbox container to pick up plugin registration..."
docker compose restart netbox
echo "Done. netbox_hedgehog plugin is now registered."
