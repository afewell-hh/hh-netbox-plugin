#!/usr/bin/env bash
set -euo pipefail

NETBOX_DOCKER_DIR="${NETBOX_DOCKER_DIR:-/home/ubuntu/afewell-hh/netbox-docker}"
FULL_RESET="false"
PURGE_INVENTORY="false"

usage() {
  cat <<'USAGE'
Usage: scripts/reset_local_dev.sh [--full] [--purge-inventory]

Quick reset (default):
  - Clears DIET planning data and generated objects
  - Reseeds DIET reference data + device types

Full reset (--full):
  - Recreates local NetBox containers and volumes
  - Runs migrations
  - Reseeds DIET reference data + device types

Purge inventory (--purge-inventory):
  - Removes ALL Manufacturers, DeviceTypes, ModuleTypes, ModuleTypeProfiles
  - Intended to return NetBox to a near-empty inventory before reseeding

Environment:
  NETBOX_DOCKER_DIR  Path to netbox-docker (default: /home/ubuntu/afewell-hh/netbox-docker)
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full)
      FULL_RESET="true"
      shift
      ;;
    --purge-inventory)
      PURGE_INVENTORY="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "$NETBOX_DOCKER_DIR" ]]; then
  echo "NETBOX_DOCKER_DIR not found: $NETBOX_DOCKER_DIR" >&2
  exit 1
fi

cd "$NETBOX_DOCKER_DIR"

if [[ "$FULL_RESET" == "true" ]]; then
  echo "[FULL] Recreating local NetBox environment..."
  docker compose down -v
  docker compose up -d

  echo "Waiting for NetBox to be ready..."
  for i in {1..60}; do
    if docker compose exec -T netbox python manage.py showmigrations > /dev/null 2>&1; then
      echo "NetBox is ready."
      break
    fi
    echo "Waiting... ($i/60)"
    sleep 5
  done

  docker compose exec -T netbox python manage.py migrate
else
  echo "[QUICK] Resetting DIET data only..."
  docker compose exec -T netbox python manage.py reset_diet_data --no-input
fi

if [[ "$PURGE_INVENTORY" == "true" ]]; then
  echo "[PURGE] Removing all Manufacturers, DeviceTypes, ModuleTypes, ModuleTypeProfiles..."
  docker compose exec -T netbox python manage.py shell -c "from dcim.models import Manufacturer, DeviceType, ModuleType, ModuleTypeProfile; ModuleTypeProfile.objects.all().delete(); ModuleType.objects.all().delete(); DeviceType.objects.all().delete(); Manufacturer.objects.all().delete();"
fi

docker compose exec -T netbox python manage.py load_diet_reference_data
docker compose exec -T netbox python manage.py seed_diet_device_types

echo "Done."
