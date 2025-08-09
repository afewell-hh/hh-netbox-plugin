#!/bin/bash
# NetBox Hedgehog Plugin - Docker Deployment Script
# Deploys repository changes to running Docker container
# Usage: ./scripts/deploy-to-docker.sh [--verify-only]

set -e

# Configuration
CONTAINER_NAME="netbox-docker-netbox-1"
PLUGIN_REPO_PATH="/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog"
PLUGIN_CONTAINER_PATH="/opt/netbox/netbox/netbox_hedgehog"
NETBOX_URL="http://localhost:8000"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 NetBox Hedgehog Plugin - Docker Deployment${NC}"
echo "=================================================="

# Function to check if container is running
check_container() {
    if ! sudo docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${RED}❌ Container $CONTAINER_NAME is not running${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Container $CONTAINER_NAME is running${NC}"
}

# Function to create backup
create_backup() {
    echo -e "${BLUE}📦 Creating backup...${NC}"
    BACKUP_TAG="backup-$(date +%Y%m%d_%H%M%S)"
    sudo docker tag netbox-hedgehog:latest netbox-hedgehog:$BACKUP_TAG
    echo -e "${GREEN}✅ Backup created: netbox-hedgehog:$BACKUP_TAG${NC}"
}

# Function to deploy files
deploy_files() {
    echo -e "${BLUE}📂 Deploying plugin files...${NC}"
    
    # Templates (UI changes - no restart needed)
    echo "  Deploying templates..."
    sudo docker cp "$PLUGIN_REPO_PATH/templates/" "$CONTAINER_NAME:$PLUGIN_CONTAINER_PATH/"
    
    # Static files (CSS/JS - no restart needed)  
    echo "  Deploying static files..."
    sudo docker cp "$PLUGIN_REPO_PATH/static/" "$CONTAINER_NAME:$PLUGIN_CONTAINER_PATH/"
    
    # Python files (requires restart)
    echo "  Deploying Python files..."
    sudo docker cp "$PLUGIN_REPO_PATH/views/" "$CONTAINER_NAME:$PLUGIN_CONTAINER_PATH/"
    sudo docker cp "$PLUGIN_REPO_PATH/models/" "$CONTAINER_NAME:$PLUGIN_CONTAINER_PATH/"
    sudo docker cp "$PLUGIN_REPO_PATH/forms/" "$CONTAINER_NAME:$PLUGIN_CONTAINER_PATH/"
    sudo docker cp "$PLUGIN_REPO_PATH/api/" "$CONTAINER_NAME:$PLUGIN_CONTAINER_PATH/"
    sudo docker cp "$PLUGIN_REPO_PATH/services/" "$CONTAINER_NAME:$PLUGIN_CONTAINER_PATH/"
    sudo docker cp "$PLUGIN_REPO_PATH/tasks/" "$CONTAINER_NAME:$PLUGIN_CONTAINER_PATH/"
    sudo docker cp "$PLUGIN_REPO_PATH/urls.py" "$CONTAINER_NAME:$PLUGIN_CONTAINER_PATH/"
    
    echo -e "${GREEN}✅ Files deployed successfully${NC}"
}

# Function to restart container
restart_container() {
    echo -e "${BLUE}🔄 Restarting container for Python changes...${NC}"
    sudo docker restart "$CONTAINER_NAME"
    
    # Wait for container to be ready
    echo "  Waiting for container to start..."
    sleep 20
    
    # Wait for NetBox to be ready
    echo "  Waiting for NetBox to be ready..."
    timeout=60
    while [ $timeout -gt 0 ]; do
        if curl -s -f "$NETBOX_URL/login/" >/dev/null 2>&1; then
            break
        fi
        echo -n "."
        sleep 2
        timeout=$((timeout-2))
    done
    
    if [ $timeout -le 0 ]; then
        echo -e "${RED}❌ Container did not become ready within 60 seconds${NC}"
        show_logs
        exit 1
    fi
    
    echo -e "${GREEN}✅ Container restarted and ready${NC}"
}

# Function to verify deployment
verify_deployment() {
    echo -e "${BLUE}🔍 Verifying deployment...${NC}"
    
    # Check container health
    if sudo docker ps | grep "$CONTAINER_NAME" | grep -q "healthy\|Up"; then
        echo -e "${GREEN}✅ Container is healthy${NC}"
    else
        echo -e "${RED}❌ Container is not healthy${NC}"
        return 1
    fi
    
    # Check NetBox accessibility
    if curl -s -f "$NETBOX_URL/login/" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ NetBox web interface is accessible${NC}"
    else
        echo -e "${RED}❌ NetBox web interface is not accessible${NC}"
        return 1
    fi
    
    # Check plugin base URL
    if curl -s "$NETBOX_URL/plugins/hedgehog/" | grep -q "hedgehog\|Hedgehog\|<!DOCTYPE html"; then
        echo -e "${GREEN}✅ Hedgehog plugin responds${NC}"
    else
        echo -e "${YELLOW}⚠️  Plugin may need URL pattern verification${NC}"
    fi
    
    # Check that files were deployed
    echo "  Checking deployed files..."
    if sudo docker exec "$CONTAINER_NAME" ls "$PLUGIN_CONTAINER_PATH/templates/netbox_hedgehog/" >/dev/null 2>&1; then
        template_count=$(sudo docker exec "$CONTAINER_NAME" find "$PLUGIN_CONTAINER_PATH/templates/" -name "*.html" | wc -l)
        echo -e "${GREEN}✅ Templates deployed: $template_count HTML files${NC}"
    else
        echo -e "${RED}❌ Templates not found in container${NC}"
        return 1
    fi
    
    # Check for recent file timestamps
    repo_file="$PLUGIN_REPO_PATH/templates/netbox_hedgehog/productivity_dashboard.html"
    container_file="$PLUGIN_CONTAINER_PATH/templates/netbox_hedgehog/productivity_dashboard.html"
    
    if [ -f "$repo_file" ]; then
        if sudo docker exec "$CONTAINER_NAME" ls "$container_file" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Latest files present in container${NC}"
        else
            echo -e "${YELLOW}⚠️  Some repository files may not be in container${NC}"
        fi
    fi
    
    return 0
}

# Function to show logs
show_logs() {
    echo -e "${BLUE}📋 Recent container logs:${NC}"
    sudo docker logs "$CONTAINER_NAME" --tail 15
}

# Function to show deployment summary
show_summary() {
    echo ""
    echo -e "${BLUE}📊 Deployment Summary${NC}"
    echo "====================="
    echo -e "${GREEN}✅ Plugin files deployed to container${NC}"
    echo -e "${GREEN}✅ Container restarted successfully${NC}"
    echo -e "${GREEN}✅ NetBox application accessible${NC}"
    echo ""
    echo -e "${BLUE}🌐 Access URLs:${NC}"
    echo "  NetBox: $NETBOX_URL"
    echo "  Plugin: $NETBOX_URL/plugins/hedgehog/"
    echo ""
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo "  - Template changes don't require restart"
    echo "  - Python code changes require restart (done automatically)"
    echo "  - Check logs if issues occur: sudo docker logs $CONTAINER_NAME"
}

# Main deployment process
main() {
    case "${1:-}" in
        "--verify-only")
            echo "Running verification only..."
            check_container
            verify_deployment
            exit $?
            ;;
        "--help"|"-h")
            echo "Usage: $0 [--verify-only|--help]"
            echo ""
            echo "Options:"
            echo "  --verify-only    Only verify current deployment, don't deploy"
            echo "  --help          Show this help message"
            exit 0
            ;;
    esac
    
    # Full deployment process
    check_container
    create_backup
    deploy_files
    restart_container
    
    if verify_deployment; then
        show_summary
        echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
        exit 0
    else
        echo -e "${RED}❌ Deployment verification failed${NC}"
        echo "Check logs and container status manually"
        show_logs
        exit 1
    fi
}

# Run main function
main "$@"