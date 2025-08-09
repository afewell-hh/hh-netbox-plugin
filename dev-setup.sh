#!/bin/bash
# NetBox Hedgehog Plugin - Development Setup Script
# ==================================================
# Complementary script to Makefile for complex setup operations
# This handles environment portability and error scenarios

set -e  # Exit on any error

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
DOCKER_COMPOSE_DIR="$SCRIPT_DIR/gitignore/netbox-docker"
NETBOX_URL="http://localhost:8000"
SETUP_TIMEOUT=300  # 5 minutes max setup time

log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if running in supported environment
check_environment() {
    log "Checking environment compatibility..."
    
    # Check for required tools
    local missing_tools=()
    
    command -v docker >/dev/null 2>&1 || missing_tools+=("docker")
    command -v python3 >/dev/null 2>&1 || missing_tools+=("python3")
    command -v git >/dev/null 2>&1 || missing_tools+=("git")
    command -v curl >/dev/null 2>&1 || missing_tools+=("curl")
    
    # Check for Docker Compose (new or old syntax)
    if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
        missing_tools+=("docker-compose")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        error "Missing required tools: ${missing_tools[*]}"
        error "Please install these tools and try again"
        return 1
    fi
    
    # Check Docker daemon
    if ! docker info >/dev/null 2>&1; then
        error "Docker daemon is not running or not accessible"
        error "Please start Docker or check permissions"
        return 1
    fi
    
    success "Environment check passed"
    return 0
}

# Create environment files with proper defaults
create_environment_files() {
    log "Creating environment configuration files..."
    
    local env_dir="$DOCKER_COMPOSE_DIR/env"
    mkdir -p "$env_dir"
    
    # NetBox environment
    if [ ! -f "$env_dir/netbox.env" ]; then
        cat > "$env_dir/netbox.env" << EOF
# NetBox Development Configuration
CORS_ORIGIN_ALLOW_ALL=True
DEBUG=True
DEVELOPER=True
SECRET_KEY=netbox-dev-secret-key-not-for-production
ALLOWED_HOSTS=*
DB_NAME=netbox
DB_USER=netbox
DB_PASSWORD=netbox
DB_HOST=postgres
DB_PORT=5432
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=netbox
REDIS_CACHE_HOST=redis-cache
REDIS_CACHE_PORT=6379
REDIS_CACHE_PASSWORD=netbox
PLUGINS=netbox_hedgehog
EOF
        success "Created NetBox environment file"
    fi
    
    # PostgreSQL environment
    if [ ! -f "$env_dir/postgres.env" ]; then
        cat > "$env_dir/postgres.env" << EOF
POSTGRES_DB=netbox
POSTGRES_USER=netbox
POSTGRES_PASSWORD=netbox
EOF
        success "Created PostgreSQL environment file"
    fi
    
    # Redis environments
    if [ ! -f "$env_dir/redis.env" ]; then
        echo "REDIS_PASSWORD=netbox" > "$env_dir/redis.env"
        success "Created Redis environment file"
    fi
    
    if [ ! -f "$env_dir/redis-cache.env" ]; then
        echo "REDIS_PASSWORD=netbox" > "$env_dir/redis-cache.env"
        success "Created Redis cache environment file"
    fi
}

# Wait for service with proper timeout and health checking
wait_for_service() {
    local service_name="$1"
    local health_check="$2"
    local timeout="${3:-60}"
    local interval="${4:-2}"
    
    log "Waiting for $service_name to be ready..."
    
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if eval "$health_check" >/dev/null 2>&1; then
            success "$service_name is ready"
            return 0
        fi
        
        echo -n "."
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    
    echo  # New line after dots
    error "$service_name failed to become ready within ${timeout}s"
    return 1
}

# Advanced service health checks
check_database_health() {
    cd "$DOCKER_COMPOSE_DIR" && docker compose exec -T postgres pg_isready -q -h localhost -p 5432 -d netbox -U netbox
}

check_redis_health() {
    cd "$DOCKER_COMPOSE_DIR" && docker compose exec -T redis redis-cli -a netbox ping | grep -q PONG
}

check_netbox_health() {
    curl -sf "$NETBOX_URL/login/" > /dev/null
}

# Performance monitoring during setup
monitor_setup_performance() {
    local start_time=$(date +%s)
    local setup_log=".dev-setup-performance.log"
    
    echo "Setup started: $(date)" > "$setup_log"
    
    # Run the actual setup
    "$@"
    local setup_result=$?
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo "Setup ended: $(date)" >> "$setup_log"
    echo "Duration: ${duration}s" >> "$setup_log"
    
    if [ $duration -lt 300 ]; then
        success "Setup completed in ${duration}s (target: <300s)"
    else
        warning "Setup took ${duration}s (exceeded 300s target)"
    fi
    
    return $setup_result
}

# Comprehensive setup validation
validate_complete_setup() {
    log "Performing comprehensive setup validation..."
    
    local validation_failed=false
    
    # Check Docker containers
    log "Checking Docker containers..."
    if ! cd "$DOCKER_COMPOSE_DIR" && docker compose ps | grep -E "(postgres|redis|netbox)" | grep -q "Up\|healthy"; then
        error "Docker containers not properly running"
        validation_failed=true
    else
        success "Docker containers running"
    fi
    
    # Check database connectivity
    log "Checking database connectivity..."
    if ! wait_for_service "PostgreSQL" "check_database_health" 30 2; then
        error "Database not accessible"
        validation_failed=true
    fi
    
    # Check Redis connectivity
    log "Checking Redis connectivity..."
    if ! wait_for_service "Redis" "check_redis_health" 30 2; then
        error "Redis not accessible"
        validation_failed=true
    fi
    
    # Check NetBox web interface
    log "Checking NetBox web interface..."
    if ! wait_for_service "NetBox" "check_netbox_health" 60 3; then
        error "NetBox web interface not accessible"
        validation_failed=true
    fi
    
    # Check plugin accessibility
    log "Checking Hedgehog plugin..."
    if curl -s "$NETBOX_URL/plugins/hedgehog/" | grep -iq "hedgehog"; then
        success "Hedgehog plugin accessible"
    else
        warning "Hedgehog plugin may need additional configuration"
    fi
    
    # Run existing validation script
    log "Running comprehensive validation script..."
    if [ -f "$SCRIPT_DIR/quick_validation.py" ]; then
        if python3 "$SCRIPT_DIR/quick_validation.py"; then
            success "Quick validation passed"
        else
            warning "Some validation checks had issues"
        fi
    fi
    
    if [ "$validation_failed" = "true" ]; then
        error "Setup validation failed"
        return 1
    else
        success "All validation checks passed"
        return 0
    fi
}

# Cleanup function for error scenarios
cleanup_on_error() {
    warning "Cleaning up due to setup failure..."
    cd "$DOCKER_COMPOSE_DIR" && docker compose down >/dev/null 2>&1 || true
    error "Setup failed. Environment cleaned up."
}

# Main setup function
main() {
    echo -e "${BLUE}NetBox Hedgehog Development Setup${NC}"
    echo "================================="
    echo ""
    
    # Trap to cleanup on error
    trap cleanup_on_error ERR
    
    # Performance monitoring
    monitor_setup_performance bash -c "
        check_environment
        create_environment_files
        success 'Development environment setup completed successfully!'
    "
    
    echo ""
    echo -e "${GREEN}🎯 Quick Access Information:${NC}"
    echo "  NetBox URL: $NETBOX_URL"
    echo "  Default credentials: admin / admin"
    echo "  Plugin URL: $NETBOX_URL/plugins/hedgehog/"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "  make dev-check    # Check environment health"
    echo "  make dev-test     # Run validation tests"
    echo "  make status       # Show detailed status"
}

# Run main function if script is executed directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi