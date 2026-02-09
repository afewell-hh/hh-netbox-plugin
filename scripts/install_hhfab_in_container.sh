#!/usr/bin/env bash
set -euo pipefail

NETBOX_DOCKER_DIR="${NETBOX_DOCKER_DIR:-/home/ubuntu/afewell-hh/netbox-docker}"

if [ ! -d "$NETBOX_DOCKER_DIR" ]; then
  echo "NetBox Docker directory not found: $NETBOX_DOCKER_DIR" >&2
  echo "Set NETBOX_DOCKER_DIR to the correct path and re-run." >&2
  exit 1
fi

cd "$NETBOX_DOCKER_DIR"

docker compose exec netbox bash -c "curl -fsSL https://i.hhdev.io/hhfab | bash"
echo "hhfab installed in NetBox container."
