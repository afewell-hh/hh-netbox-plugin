#!/bin/bash
# Agent Workflow Automation Script
# Provides one-command operations for common agent development tasks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_COMPOSE_DIR="$PROJECT_ROOT/gitignore/netbox-docker"
NETBOX_URL="http://localhost:8000"
LOG_FILE="$PROJECT_ROOT/.logs/agent-workflow.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
    log "SUCCESS: $1"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    log "WARNING: $1"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    log "ERROR: $1"
    exit 1
}

info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
    log "INFO: $1"
}

# Check if running in container
is_in_container() {
    [ -f /.dockerenv ] || grep -q docker /proc/1/cgroup 2>/dev/null
}

# Smart restart based on changes
smart_restart() {
    info "Analyzing recent changes for smart restart..."
    
    local changed_files
    changed_files=$(git diff --name-only HEAD~1 2>/dev/null || echo "")
    
    if [[ -z "$changed_files" ]]; then
        warning "No git changes detected, checking for modified files..."
        changed_files=$(find . -name "*.py" -mmin -10 2>/dev/null || echo "")
    fi
    
    local needs_migration=false
    local needs_static=false
    local needs_restart=false
    
    # Analyze changes
    while IFS= read -r file; do
        case "$file" in
            *.py)
                needs_restart=true
                if [[ "$file" == *migration* ]]; then
                    needs_migration=true
                fi
                ;;
            *.css|*.js|*.html)
                needs_static=true
                ;;
        esac
    done <<< "$changed_files"
    
    # Execute appropriate actions
    if [[ "$needs_migration" == true ]]; then
        info "Running migrations..."
        cd "$DOCKER_COMPOSE_DIR" && docker-compose exec netbox python manage.py migrate
    fi
    
    if [[ "$needs_static" == true ]]; then
        info "Collecting static files..."
        cd "$DOCKER_COMPOSE_DIR" && docker-compose exec netbox python manage.py collectstatic --noinput --clear
    fi
    
    if [[ "$needs_restart" == true ]]; then
        info "Restarting application services..."
        cd "$DOCKER_COMPOSE_DIR" && docker-compose restart netbox netbox-worker netbox-rq-worker-hedgehog
    fi
    
    success "Smart restart completed"
}

# Quick health check
health_check() {
    info "Running quick health check..."
    
    # Check NetBox response
    if curl -s -f "$NETBOX_URL/login/" >/dev/null 2>&1; then
        success "NetBox is responding"
    else
        error "NetBox is not responding at $NETBOX_URL"
    fi
    
    # Check plugin
    if curl -s "$NETBOX_URL/plugins/hedgehog/" | grep -q "hedgehog\|Hedgehog" 2>/dev/null; then
        success "Hedgehog plugin is accessible"
    else
        warning "Hedgehog plugin may need attention"
    fi
    
    # Check containers
    local running_containers
    running_containers=$(cd "$DOCKER_COMPOSE_DIR" && docker-compose ps --filter "status=running" --format "{{.Names}}" | wc -l)
    
    if [[ "$running_containers" -ge 3 ]]; then
        success "Containers are healthy ($running_containers running)"
    else
        warning "Some containers may be down ($running_containers running)"
    fi
}

# Performance check
performance_check() {
    info "Checking performance metrics..."
    
    # Response time check
    local start_time
    local end_time
    local response_time
    
    start_time=$(date +%s%N)
    if curl -s -f "$NETBOX_URL/login/" >/dev/null 2>&1; then
        end_time=$(date +%s%N)
        response_time=$(( (end_time - start_time) / 1000000 ))
        
        if [[ $response_time -lt 1000 ]]; then
            success "Response time: ${response_time}ms (excellent)"
        elif [[ $response_time -lt 3000 ]]; then
            success "Response time: ${response_time}ms (good)"
        else
            warning "Response time: ${response_time}ms (slow)"
        fi
    else
        error "Service not responding for performance check"
    fi
    
    # Container resource usage (if available)
    if command -v docker >/dev/null 2>&1; then
        info "Container resource usage:"
        cd "$DOCKER_COMPOSE_DIR" && docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $(docker-compose ps -q) 2>/dev/null || warning "Docker stats not available"
    fi
}

# Error recovery
error_recovery() {
    info "Starting error recovery procedures..."
    
    # Check and restart stopped containers
    local stopped_containers
    stopped_containers=$(cd "$DOCKER_COMPOSE_DIR" && docker-compose ps --filter "status=exited" --format "{{.Names}}")
    
    if [[ -n "$stopped_containers" ]]; then
        warning "Found stopped containers, restarting..."
        cd "$DOCKER_COMPOSE_DIR" && docker-compose up -d
        sleep 15
    fi
    
    # Check if NetBox is responding
    if ! curl -s -f "$NETBOX_URL/login/" >/dev/null 2>&1; then
        warning "NetBox not responding, attempting restart..."
        cd "$DOCKER_COMPOSE_DIR" && docker-compose restart netbox
        sleep 10
        
        # Wait for recovery
        local attempts=0
        while [[ $attempts -lt 30 ]]; do
            if curl -s -f "$NETBOX_URL/login/" >/dev/null 2>&1; then
                success "NetBox recovered after restart"
                break
            fi
            sleep 2
            ((attempts++))
        done
        
        if [[ $attempts -eq 30 ]]; then
            error "NetBox failed to recover after restart"
        fi
    fi
    
    # Final validation
    health_check
    success "Error recovery completed"
}

# Environment setup validation
validate_environment() {
    info "Validating development environment..."
    
    # Check required commands
    local missing_commands=()
    for cmd in docker curl git make; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing_commands+=("$cmd")
        fi
    done
    
    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        error "Missing required commands: ${missing_commands[*]}"
    fi
    
    # Check Docker access
    if ! docker info >/dev/null 2>&1; then
        if ! sudo docker info >/dev/null 2>&1; then
            error "Docker daemon not accessible"
        fi
    fi
    
    # Check project structure
    if [[ ! -f "$PROJECT_ROOT/Makefile" ]]; then
        error "Makefile not found in project root"
    fi
    
    if [[ ! -d "$DOCKER_COMPOSE_DIR" ]]; then
        error "Docker compose directory not found: $DOCKER_COMPOSE_DIR"
    fi
    
    success "Environment validation passed"
}

# Agent readiness check
agent_readiness() {
    info "Checking agent readiness..."
    
    validate_environment
    health_check
    performance_check
    
    success "🤖 Environment is ready for agent development work!"
}

# Show help
show_help() {
    echo -e "${BLUE}Agent Workflow Automation${NC}"
    echo "========================"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  smart-restart    - Analyze changes and restart only what's needed"
    echo "  health-check     - Quick health validation"
    echo "  performance      - Check performance metrics" 
    echo "  error-recovery   - Automatic error recovery"
    echo "  validate-env     - Validate development environment"
    echo "  agent-ready      - Complete agent readiness check"
    echo "  help            - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 smart-restart    # After making code changes"
    echo "  $0 health-check     # Quick status check"
    echo "  $0 agent-ready      # Comprehensive readiness check"
}

# Main command dispatcher
main() {
    case "${1:-help}" in
        smart-restart)
            smart_restart
            ;;
        health-check)
            health_check
            ;;
        performance)
            performance_check
            ;;
        error-recovery)
            error_recovery
            ;;
        validate-env)
            validate_environment
            ;;
        agent-ready)
            agent_readiness
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