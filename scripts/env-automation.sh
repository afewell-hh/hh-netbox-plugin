#!/bin/bash
# Environment Configuration Automation
# Handles secrets, environment variables, and configuration management

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_COMPOSE_DIR="$PROJECT_ROOT/gitignore/netbox-docker"
ENV_DIR="$DOCKER_COMPOSE_DIR/env"
CONFIG_DIR="$DOCKER_COMPOSE_DIR/configuration"
CACHE_DIR="$PROJECT_ROOT/.cache"
LOG_FILE="$PROJECT_ROOT/.logs/env-automation.log"

# Ensure directories exist
mkdir -p "$CACHE_DIR" "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $*" >> "$LOG_FILE"
}

success() {
    echo -e "${GREEN}✅ $*${NC}"
    log "SUCCESS: $*"
}

warning() {
    echo -e "${YELLOW}⚠️  $*${NC}"
    log "WARNING: $*"
}

error() {
    echo -e "${RED}❌ $*${NC}"
    log "ERROR: $*"
    exit 1
}

info() {
    echo -e "${BLUE}ℹ️  $*${NC}"
    log "INFO: $*"
}

# Environment file templates
create_env_templates() {
    info "Creating environment file templates..."
    
    mkdir -p "$ENV_DIR"
    
    # NetBox environment
    if [[ ! -f "$ENV_DIR/netbox.env" ]]; then
        cat > "$ENV_DIR/netbox.env" << 'EOF'
# NetBox Configuration
ALLOWED_HOSTS=*
DB_HOST=postgres
DB_NAME=netbox
DB_PASSWORD=netbox
DB_USER=netbox
REDIS_CACHE_HOST=redis-cache
REDIS_CACHE_PASSWORD=redis-cache-password
REDIS_HOST=redis
REDIS_PASSWORD=redis-password
SECRET_KEY=dev-secret-key-change-in-production

# Development Settings
DEBUG=True
DEVELOPMENT_MODE=True
SKIP_SUPERUSER=False

# Hedgehog Plugin Configuration
HEDGEHOG_K8S_NAMESPACE=default
HEDGEHOG_SYNC_ENABLED=True
HEDGEHOG_PERIODIC_SYNC_INTERVAL=300

# Performance Settings
WORKER_TIMEOUT=300
MAX_PAGE_SIZE=1000
PAGINATE_COUNT=50

# Security Settings (Development Only)
LOGIN_REQUIRED=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
EOF
        success "Created NetBox environment template"
    fi
    
    # PostgreSQL environment
    if [[ ! -f "$ENV_DIR/postgres.env" ]]; then
        cat > "$ENV_DIR/postgres.env" << 'EOF'
POSTGRES_DB=netbox
POSTGRES_USER=netbox
POSTGRES_PASSWORD=netbox
POSTGRES_INITDB_ARGS=--encoding=UTF-8 --lc-collate=C --lc-ctype=C
EOF
        success "Created PostgreSQL environment template"
    fi
    
    # Redis environment
    if [[ ! -f "$ENV_DIR/redis.env" ]]; then
        cat > "$ENV_DIR/redis.env" << 'EOF'
REDIS_PASSWORD=redis-password
EOF
        success "Created Redis environment template"
    fi
    
    # Redis cache environment
    if [[ ! -f "$ENV_DIR/redis-cache.env" ]]; then
        cat > "$ENV_DIR/redis-cache.env" << 'EOF'
REDIS_PASSWORD=redis-cache-password
EOF
        success "Created Redis cache environment template"
    fi
}

# Generate secure secrets
generate_secrets() {
    info "Generating secure secrets..."
    
    # Generate Django secret key
    local secret_key
    secret_key=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" 2>/dev/null || \
                openssl rand -base64 50 | tr -d "=+/" | cut -c1-50)
    
    # Generate Redis passwords
    local redis_password
    local redis_cache_password
    redis_password=$(openssl rand -base64 32 | tr -d "=+/")
    redis_cache_password=$(openssl rand -base64 32 | tr -d "=+/")
    
    # Update environment files
    if [[ -f "$ENV_DIR/netbox.env" ]]; then
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=$secret_key/" "$ENV_DIR/netbox.env"
        sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$redis_password/" "$ENV_DIR/netbox.env"
        sed -i "s/REDIS_CACHE_PASSWORD=.*/REDIS_CACHE_PASSWORD=$redis_cache_password/" "$ENV_DIR/netbox.env"
        success "Updated NetBox secrets"
    fi
    
    if [[ -f "$ENV_DIR/redis.env" ]]; then
        sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$redis_password/" "$ENV_DIR/redis.env"
        success "Updated Redis secrets"
    fi
    
    if [[ -f "$ENV_DIR/redis-cache.env" ]]; then
        sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$redis_cache_password/" "$ENV_DIR/redis-cache.env"
        success "Updated Redis cache secrets"
    fi
    
    # Save secrets to secure backup
    local secrets_file="$CACHE_DIR/secrets_$(date +%Y%m%d_%H%M%S).env"
    cat > "$secrets_file" << EOF
# Generated secrets - $(date)
SECRET_KEY=$secret_key
REDIS_PASSWORD=$redis_password
REDIS_CACHE_PASSWORD=$redis_cache_password
EOF
    chmod 600 "$secrets_file"
    success "Secrets backed up to $secrets_file"
}

# Configure networking
configure_networking() {
    info "Configuring development networking..."
    
    # Update project .env file
    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        cat > "$PROJECT_ROOT/.env" << 'EOF'
# NetBox Hedgehog Development Environment Configuration
NETBOX_URL=http://localhost:8000
NETBOX_TOKEN=

# Superuser Configuration (for testing)
SUPERUSER_NAME=admin
SUPERUSER_PASSWORD=admin

# Development Settings
DEV_MODE=true
DEBUG=true

# Docker Configuration
DOCKER_COMPOSE_DIR=gitignore/netbox-docker

# Setup Performance Tracking
SETUP_TARGET_TIME=300
EOF
        success "Created project .env file"
    fi
    
    # Configure container networking
    if [[ -f "$DOCKER_COMPOSE_DIR/docker-compose.override.yml" ]]; then
        # Ensure NetBox is accessible on port 8000
        if ! grep -q "8000:8080" "$DOCKER_COMPOSE_DIR/docker-compose.override.yml"; then
            warning "Port 8000 mapping not found in override file"
            info "Adding port mapping to docker-compose.override.yml"
            
            # Backup existing override
            cp "$DOCKER_COMPOSE_DIR/docker-compose.override.yml" "$DOCKER_COMPOSE_DIR/docker-compose.override.yml.backup"
            
            # Ensure netbox service has port mapping
            if ! grep -A 10 "^  netbox:" "$DOCKER_COMPOSE_DIR/docker-compose.override.yml" | grep -q "ports:"; then
                sed -i '/^  netbox:/a\    ports:\n      - "8000:8080"' "$DOCKER_COMPOSE_DIR/docker-compose.override.yml"
                success "Added port mapping for NetBox"
            fi
        fi
    fi
}

# Setup development dependencies
setup_dev_dependencies() {
    info "Setting up development dependencies..."
    
    # Create requirements file for container
    if [[ ! -f "$DOCKER_COMPOSE_DIR/requirements-hedgehog.txt" ]]; then
        cat > "$DOCKER_COMPOSE_DIR/requirements-hedgehog.txt" << 'EOF'
# NetBox Hedgehog Plugin Development Dependencies
kubernetes>=24.0.0
pyyaml>=6.0
jsonschema>=4.0.0
GitPython>=3.1.0
requests>=2.28.0
django-rq>=2.5.0
rq-scheduler>=0.13.0

# Development tools
pytest>=7.0.0
pytest-django>=4.5.0
black>=22.0.0
flake8>=5.0.0
coverage>=6.0.0
factory-boy>=3.2.0
EOF
        success "Created Hedgehog requirements file"
    fi
    
    # Create initialization script
    if [[ ! -f "$DOCKER_COMPOSE_DIR/init-hedgehog.sh" ]]; then
        cat > "$DOCKER_COMPOSE_DIR/init-hedgehog.sh" << 'EOF'
#!/bin/bash
# Hedgehog Plugin Initialization Script

set -e

echo "Initializing Hedgehog plugin..."

# Install plugin in development mode
if [ -d "/opt/netbox/netbox/netbox_hedgehog" ]; then
    cd /opt/netbox/netbox/netbox_hedgehog
    pip install -e .
    echo "Hedgehog plugin installed in development mode"
fi

# Run migrations
python /opt/netbox/netbox/manage.py migrate netbox_hedgehog

# Collect static files
python /opt/netbox/netbox/manage.py collectstatic --noinput --clear

echo "Hedgehog plugin initialization complete"
EOF
        chmod +x "$DOCKER_COMPOSE_DIR/init-hedgehog.sh"
        success "Created Hedgehog initialization script"
    fi
}

# Validate configuration
validate_configuration() {
    info "Validating environment configuration..."
    
    local errors=0
    
    # Check required environment files
    for env_file in "netbox.env" "postgres.env" "redis.env" "redis-cache.env"; do
        if [[ ! -f "$ENV_DIR/$env_file" ]]; then
            error "Missing environment file: $env_file"
            errors=$((errors + 1))
        else
            success "Found environment file: $env_file"
        fi
    done
    
    # Check for weak secrets
    if [[ -f "$ENV_DIR/netbox.env" ]]; then
        if grep -q "SECRET_KEY=dev-secret-key" "$ENV_DIR/netbox.env"; then
            warning "Using default secret key - consider regenerating"
        fi
        
        if grep -q "REDIS_PASSWORD=redis-password" "$ENV_DIR/netbox.env"; then
            warning "Using default Redis password - consider regenerating"
        fi
    fi
    
    # Check Docker Compose files
    if [[ ! -f "$DOCKER_COMPOSE_DIR/docker-compose.yml" ]]; then
        error "Missing docker-compose.yml"
        errors=$((errors + 1))
    fi
    
    if [[ ! -f "$DOCKER_COMPOSE_DIR/docker-compose.override.yml" ]]; then
        warning "Missing docker-compose.override.yml"
    fi
    
    # Validate network configuration
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        if ! grep -q "NETBOX_URL=http://localhost:8000" "$PROJECT_ROOT/.env"; then
            warning "NetBox URL may not be correctly configured"
        fi
    fi
    
    if [[ $errors -eq 0 ]]; then
        success "Configuration validation passed"
        return 0
    else
        error "Configuration validation failed with $errors errors"
        return 1
    fi
}

# Backup configuration
backup_configuration() {
    local backup_name="${1:-config_$(date +%Y%m%d_%H%M%S)}"
    local backup_file="$CACHE_DIR/${backup_name}.tar.gz"
    
    info "Creating configuration backup: $backup_name"
    
    # Create backup of all configuration
    tar -czf "$backup_file" \
        -C "$PROJECT_ROOT" \
        --exclude='.git' \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        --exclude='.logs' \
        --exclude='.cache' \
        gitignore/netbox-docker/env/ \
        gitignore/netbox-docker/configuration/ \
        gitignore/netbox-docker/docker-compose.override.yml \
        gitignore/netbox-docker/requirements-hedgehog.txt \
        gitignore/netbox-docker/init-hedgehog.sh \
        .env \
        2>/dev/null || true
    
    if [[ -f "$backup_file" ]]; then
        success "Configuration backup created: $backup_file"
    else
        error "Failed to create configuration backup"
    fi
}

# Restore configuration
restore_configuration() {
    local backup_file="$1"
    
    if [[ -z "$backup_file" ]]; then
        echo -e "${YELLOW}Available backups:${NC}"
        ls -la "$CACHE_DIR"/config_*.tar.gz 2>/dev/null || echo "No backups found"
        echo ""
        read -p "Enter backup filename: " backup_file
    fi
    
    local full_backup_path
    if [[ "$backup_file" =~ ^/ ]]; then
        full_backup_path="$backup_file"
    else
        full_backup_path="$CACHE_DIR/$backup_file"
    fi
    
    if [[ ! -f "$full_backup_path" ]]; then
        error "Backup file not found: $full_backup_path"
    fi
    
    info "Restoring configuration from $full_backup_path"
    
    # Create backup of current config before restore
    backup_configuration "pre_restore_$(date +%Y%m%d_%H%M%S)"
    
    # Extract backup
    tar -xzf "$full_backup_path" -C "$PROJECT_ROOT"
    
    success "Configuration restored from backup"
    
    # Validate restored configuration
    validate_configuration
}

# Show configuration status
show_status() {
    echo -e "${PURPLE}🔧 Environment Configuration Status${NC}"
    echo "==================================="
    echo ""
    
    # Environment files status
    echo -e "${BLUE}📁 Environment Files:${NC}"
    for env_file in "netbox.env" "postgres.env" "redis.env" "redis-cache.env"; do
        if [[ -f "$ENV_DIR/$env_file" ]]; then
            local size
            size=$(stat -f%z "$ENV_DIR/$env_file" 2>/dev/null || stat -c%s "$ENV_DIR/$env_file" 2>/dev/null || echo "unknown")
            echo -e "  ${GREEN}✅${NC} $env_file ($size bytes)"
        else
            echo -e "  ${RED}❌${NC} $env_file (missing)"
        fi
    done
    echo ""
    
    # Configuration files status
    echo -e "${BLUE}⚙️  Configuration Files:${NC}"
    local config_files=("docker-compose.yml" "docker-compose.override.yml" "requirements-hedgehog.txt" "init-hedgehog.sh")
    for config_file in "${config_files[@]}"; do
        if [[ -f "$DOCKER_COMPOSE_DIR/$config_file" ]]; then
            echo -e "  ${GREEN}✅${NC} $config_file"
        else
            echo -e "  ${YELLOW}⚠️${NC} $config_file (missing)"
        fi
    done
    echo ""
    
    # Project configuration
    echo -e "${BLUE}🏗️  Project Configuration:${NC}"
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        echo -e "  ${GREEN}✅${NC} .env file"
        local netbox_url
        netbox_url=$(grep "NETBOX_URL=" "$PROJECT_ROOT/.env" | cut -d'=' -f2)
        echo -e "     NetBox URL: $netbox_url"
    else
        echo -e "  ${RED}❌${NC} .env file (missing)"
    fi
    
    # Security status
    echo -e "${BLUE}🔐 Security Status:${NC}"
    if [[ -f "$ENV_DIR/netbox.env" ]]; then
        if grep -q "SECRET_KEY=dev-secret-key" "$ENV_DIR/netbox.env"; then
            echo -e "  ${YELLOW}⚠️${NC} Using default secret key"
        else
            echo -e "  ${GREEN}✅${NC} Custom secret key configured"
        fi
        
        if grep -q "REDIS_PASSWORD=redis-password" "$ENV_DIR/netbox.env"; then
            echo -e "  ${YELLOW}⚠️${NC} Using default Redis password"
        else
            echo -e "  ${GREEN}✅${NC} Custom Redis password configured"
        fi
    fi
    
    # Backup status
    echo ""
    echo -e "${BLUE}💾 Available Backups:${NC}"
    local backup_count
    backup_count=$(ls -1 "$CACHE_DIR"/config_*.tar.gz 2>/dev/null | wc -l || echo "0")
    if [[ $backup_count -gt 0 ]]; then
        echo -e "  ${GREEN}✅${NC} $backup_count configuration backups available"
        ls -la "$CACHE_DIR"/config_*.tar.gz 2>/dev/null | tail -3
    else
        echo -e "  ${YELLOW}⚠️${NC} No configuration backups found"
    fi
}

# Show help
show_help() {
    echo -e "${PURPLE}🔧 Environment Configuration Automation${NC}"
    echo "========================================"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  setup             - Complete environment setup"
    echo "  templates         - Create environment file templates"
    echo "  secrets           - Generate secure secrets" 
    echo "  networking        - Configure development networking"
    echo "  dependencies      - Setup development dependencies"
    echo "  validate          - Validate configuration"
    echo "  backup [name]     - Backup configuration"
    echo "  restore [file]    - Restore configuration from backup"
    echo "  status           - Show configuration status"
    echo "  help             - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 setup                    # Complete initial setup"
    echo "  $0 secrets                  # Generate new secure secrets"
    echo "  $0 backup production_ready  # Backup current config"
    echo "  $0 restore config_backup.tar.gz  # Restore from backup"
    echo "  $0 status                   # Check current status"
}

# Main command dispatcher
main() {
    case "${1:-help}" in
        setup)
            create_env_templates
            generate_secrets
            configure_networking
            setup_dev_dependencies
            validate_configuration
            success "Environment configuration setup complete!"
            ;;
        templates)
            create_env_templates
            ;;
        secrets)
            generate_secrets
            ;;
        networking)
            configure_networking
            ;;
        dependencies)
            setup_dev_dependencies
            ;;
        validate)
            validate_configuration
            ;;
        backup)
            backup_configuration "$2"
            ;;
        restore)
            restore_configuration "$2"
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"