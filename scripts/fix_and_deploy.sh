#!/bin/bash
# Fix and deploy authentication changes

set -e

echo "🔧 Fixing and deploying authentication changes..."

# Stop containers first
echo "⏹️  Stopping containers..."
sudo docker compose -f gitignore/netbox-docker/docker-compose.yml stop netbox netbox-worker netbox-rq-worker-hedgehog

# Copy all updated files
echo "📦 Copying updated files..."
sudo docker cp netbox_hedgehog/ netbox-docker-netbox-1:/opt/netbox/netbox/

# Start containers
echo "▶️  Starting containers..."
sudo docker compose -f gitignore/netbox-docker/docker-compose.yml start netbox netbox-worker netbox-rq-worker-hedgehog

# Wait for healthy status
echo "⏳ Waiting for containers to be healthy..."
sleep 15

# Check status
echo "📊 Container status:"
sudo docker compose -f gitignore/netbox-docker/docker-compose.yml ps

echo "✅ Deployment complete!"