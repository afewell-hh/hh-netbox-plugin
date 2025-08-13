#!/bin/bash
# Hot-reload deployment script for NetBox Hedgehog Plugin
# Based on Issue #43 methodology for development workflow

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

CONTAINER_NAME="netbox-docker-netbox-1"
PLUGIN_PATH="/opt/netbox/netbox/netbox_hedgehog"

echo -e "${GREEN}🚀 NetBox Hedgehog Plugin Hot-Reload Deployment${NC}"
echo "================================================"

# Function to deploy files
deploy_files() {
    local file_type=$1
    local source_path=$2
    local dest_path=$3
    
    echo -e "${YELLOW}📦 Deploying $file_type...${NC}"
    
    # Check if container is running
    if ! sudo docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${RED}❌ Container $CONTAINER_NAME is not running${NC}"
        exit 1
    fi
    
    # Deploy files
    sudo docker cp "$source_path" "$CONTAINER_NAME:$dest_path"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $file_type deployed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to deploy $file_type${NC}"
        exit 1
    fi
}

# Function to restart services
restart_services() {
    echo -e "${YELLOW}🔄 Restarting services...${NC}"
    sudo docker compose -f gitignore/netbox-docker/docker-compose.yml restart netbox netbox-worker netbox-rq-worker-hedgehog
    echo -e "${GREEN}✅ Services restarted${NC}"
}

# Main deployment logic
case "${1:-all}" in
    templates)
        echo "Deploying templates only (no restart needed)..."
        deploy_files "Templates" \
            "netbox_hedgehog/templates/" \
            "$PLUGIN_PATH/"
        echo -e "${GREEN}✅ Templates deployed - changes should be visible immediately${NC}"
        ;;
    
    static)
        echo "Deploying static files..."
        deploy_files "Static files" \
            "netbox_hedgehog/static/" \
            "$PLUGIN_PATH/"
        
        # Collect static files
        echo -e "${YELLOW}📦 Collecting static files...${NC}"
        sudo docker exec "$CONTAINER_NAME" python manage.py collectstatic --noinput
        echo -e "${GREEN}✅ Static files collected${NC}"
        ;;
    
    python)
        echo "Deploying Python code..."
        deploy_files "Python files" \
            "netbox_hedgehog/" \
            "$PLUGIN_PATH/"
        
        # Python changes need restart
        restart_services
        ;;
    
    models)
        echo "Deploying model changes..."
        deploy_files "Model files" \
            "netbox_hedgehog/models/" \
            "$PLUGIN_PATH/models/"
        
        # Check for migrations
        echo -e "${YELLOW}🔍 Checking for migrations...${NC}"
        sudo docker exec "$CONTAINER_NAME" python manage.py makemigrations --dry-run netbox_hedgehog
        
        read -p "Do you need to create migrations? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo docker exec "$CONTAINER_NAME" python manage.py makemigrations netbox_hedgehog
            sudo docker exec "$CONTAINER_NAME" python manage.py migrate
        fi
        
        restart_services
        ;;
    
    all)
        echo "Deploying all files..."
        deploy_files "All plugin files" \
            "netbox_hedgehog/" \
            "$PLUGIN_PATH/"
        
        # Collect static files
        echo -e "${YELLOW}📦 Collecting static files...${NC}"
        sudo docker exec "$CONTAINER_NAME" python manage.py collectstatic --noinput
        
        # Check for migrations
        echo -e "${YELLOW}🔍 Checking for migrations...${NC}"
        sudo docker exec "$CONTAINER_NAME" python manage.py showmigrations netbox_hedgehog | tail -5
        
        restart_services
        ;;
    
    quick)
        echo "Quick deployment (templates + python, no migrations)..."
        deploy_files "Quick update" \
            "netbox_hedgehog/" \
            "$PLUGIN_PATH/"
        echo -e "${GREEN}✅ Quick deployment complete - template changes are immediate${NC}"
        ;;
    
    *)
        echo "Usage: $0 [templates|static|python|models|all|quick]"
        echo ""
        echo "  templates - Deploy only template files (instant, no restart)"
        echo "  static    - Deploy static files and run collectstatic"
        echo "  python    - Deploy Python code and restart services"
        echo "  models    - Deploy models with migration check"
        echo "  all       - Deploy everything with full restart"
        echo "  quick     - Deploy templates and python without restart"
        exit 1
        ;;
esac

# Verify deployment
echo ""
echo -e "${YELLOW}🔍 Verifying deployment...${NC}"

# Check container health
HEALTH=$(sudo docker inspect "$CONTAINER_NAME" --format='{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
echo "Container health: $HEALTH"

# Check service status
echo "Service status:"
sudo docker compose -f gitignore/netbox-docker/docker-compose.yml ps | grep netbox

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:8000 in your browser"
echo "2. Login with admin/admin"
echo "3. Navigate to Plugins > Hedgehog to test changes"
echo ""
echo "To monitor logs:"
echo "  sudo docker compose -f gitignore/netbox-docker/docker-compose.yml logs -f netbox"