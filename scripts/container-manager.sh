#!/bin/bash
# Container Management Helper for Agent Development
# Provides streamlined container operations with clear feedback

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
LOG_DIR="$PROJECT_ROOT/.logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Detect docker-compose command
if command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="sudo docker compose"
fi

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $*" >> "$LOG_DIR/container-manager.log"
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

# Service definitions with health check commands
declare -A SERVICES=(
    ["netbox"]="Main NetBox application"
    ["netbox-worker"]="Background task worker"
    ["netbox-rq-worker-hedgehog"]="Hedgehog RQ worker" 
    ["netbox-rq-scheduler"]="Periodic task scheduler"
    ["postgres"]="PostgreSQL database"
    ["redis"]="Redis cache"
    ["redis-cache"]="Redis cache secondary"
)

declare -A HEALTH_CHECKS=(
    ["netbox"]="curl -f http://localhost:8080/login/"
    ["postgres"]="pg_isready -q"
    ["redis"]="redis-cli ping"
)

# Show container status with enhanced information
show_status() {
    info "Container Status Overview"
    echo "========================="
    
    cd "$DOCKER_COMPOSE_DIR"
    
    # Get container information
    local containers
    containers=$($DOCKER_COMPOSE ps --format "table {{.Name}}\t{{.State}}\t{{.Status}}\t{{.Ports}}")
    
    if [[ -z "$containers" ]] || [[ "$containers" == *"NAME"* ]] && [[ $(echo "$containers" | wc -l) -eq 1 ]]; then
        warning "No containers found or not running"
        return 1
    fi
    
    echo "$containers"
    echo ""
    
    # Health summary
    local total=0
    local healthy=0
    local unhealthy=0
    
    for service in "${!SERVICES[@]}"; do
        total=$((total + 1))
        if $DOCKER_COMPOSE ps "$service" | grep -q "Up\|healthy" 2>/dev/null; then
            healthy=$((healthy + 1))
        else
            unhealthy=$((unhealthy + 1))
        fi
    done
    
    echo -e "${BLUE}📊 Health Summary:${NC}"
    echo -e "  Total services: $total"
    echo -e "  ${GREEN}Healthy: $healthy${NC}"
    echo -e "  ${RED}Unhealthy: $unhealthy${NC}"
    
    if [[ $unhealthy -eq 0 ]]; then
        success "All services are healthy!"
    else
        warning "$unhealthy services need attention"
    fi
}

# Smart service restart with dependency handling
restart_service() {
    local service="$1"
    local cascade="${2:-false}"
    
    if [[ -z "$service" ]]; then
        error "Service name required"
    fi
    
    if [[ ! ${SERVICES[$service]+_} ]]; then
        error "Unknown service: $service"
    fi
    
    info "Restarting service: $service (${SERVICES[$service]})"
    
    cd "$DOCKER_COMPOSE_DIR"
    
    # Define service dependencies
    local dependents=()
    case "$service" in
        postgres)
            dependents=("netbox" "netbox-worker" "netbox-rq-worker-hedgehog" "netbox-rq-scheduler")
            ;;
        redis)
            dependents=("netbox" "netbox-worker" "netbox-rq-worker-hedgehog")
            ;;
        netbox)
            dependents=("netbox-worker" "netbox-rq-worker-hedgehog" "netbox-rq-scheduler")
            ;;
    esac
    
    # Stop dependents first if cascade restart
    if [[ "$cascade" == "true" ]] && [[ ${#dependents[@]} -gt 0 ]]; then
        warning "Cascade restart enabled - stopping dependent services first"
        for dependent in "${dependents[@]}"; do
            if $DOCKER_COMPOSE ps "$dependent" | grep -q "Up" 2>/dev/null; then
                info "Stopping dependent service: $dependent"
                $DOCKER_COMPOSE stop "$dependent"
            fi
        done
    fi
    
    # Restart the main service
    info "Restarting $service..."
    $DOCKER_COMPOSE restart "$service"
    
    # Wait for service to be ready
    wait_for_service "$service"
    
    # Restart dependents if cascade restart
    if [[ "$cascade" == "true" ]] && [[ ${#dependents[@]} -gt 0 ]]; then
        info "Starting dependent services..."
        for dependent in "${dependents[@]}"; do
            if ! $DOCKER_COMPOSE ps "$dependent" | grep -q "Up" 2>/dev/null; then
                info "Starting dependent service: $dependent"
                $DOCKER_COMPOSE start "$dependent"
                wait_for_service "$dependent"
            fi
        done
    fi
    
    success "Service restart completed: $service"
}

# Wait for service to be ready
wait_for_service() {
    local service="$1"
    local max_attempts=30
    local attempt=0
    
    info "Waiting for $service to be ready..."
    
    while [[ $attempt -lt $max_attempts ]]; do
        if $DOCKER_COMPOSE ps "$service" | grep -q "Up\|healthy" 2>/dev/null; then
            # Additional health check if available
            if [[ ${HEALTH_CHECKS[$service]+_} ]]; then
                if $DOCKER_COMPOSE exec "$service" ${HEALTH_CHECKS[$service]} >/dev/null 2>&1; then
                    success "$service is ready"
                    return 0
                fi
            else
                success "$service is ready"
                return 0
            fi
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo ""
    warning "$service may not be fully ready after $max_attempts attempts"
    return 1
}

# Container logs with intelligent filtering
show_logs() {
    local service="$1"
    local lines="${2:-50}"
    local follow="${3:-false}"
    
    cd "$DOCKER_COMPOSE_DIR"
    
    if [[ -n "$service" ]]; then
        if [[ ! ${SERVICES[$service]+_} ]]; then
            error "Unknown service: $service"
        fi
        
        info "Showing logs for $service (last $lines lines)"
        
        if [[ "$follow" == "true" ]]; then
            info "Following logs (Press Ctrl+C to stop)"
            $DOCKER_COMPOSE logs -f --tail="$lines" "$service"
        else
            $DOCKER_COMPOSE logs --tail="$lines" "$service"
        fi
    else
        info "Showing logs for all services (last $lines lines each)"
        
        if [[ "$follow" == "true" ]]; then
            info "Following logs (Press Ctrl+C to stop)"
            $DOCKER_COMPOSE logs -f --tail="$lines"
        else
            $DOCKER_COMPOSE logs --tail="$lines"
        fi
    fi
}

# Container shell access with service detection
shell_access() {
    local service="${1:-netbox}"
    local shell_cmd="${2:-bash}"
    
    if [[ ! ${SERVICES[$service]+_} ]]; then
        error "Unknown service: $service"
    fi
    
    cd "$DOCKER_COMPOSE_DIR"
    
    if ! $DOCKER_COMPOSE ps "$service" | grep -q "Up" 2>/dev/null; then
        error "Service $service is not running"
    fi
    
    info "Accessing shell for $service using $shell_cmd"
    info "Type 'exit' to return to host shell"
    
    case "$service" in
        postgres)
            $DOCKER_COMPOSE exec "$service" psql -U netbox
            ;;
        redis|redis-cache)
            $DOCKER_COMPOSE exec "$service" redis-cli
            ;;
        *)
            $DOCKER_COMPOSE exec "$service" "$shell_cmd"
            ;;
    esac
}

# Resource monitoring
monitor_resources() {
    local duration="${1:-60}"
    local interval="${2:-5}"
    
    info "Monitoring container resources for ${duration}s (interval: ${interval}s)"
    info "Press Ctrl+C to stop monitoring"
    
    cd "$DOCKER_COMPOSE_DIR"
    
    local start_time
    start_time=$(date +%s)
    local end_time
    end_time=$((start_time + duration))
    
    while [[ $(date +%s) -lt $end_time ]]; do
        clear
        echo -e "${BLUE}📊 Container Resource Monitor - $(date)${NC}"
        echo "================================================"
        
        # Get container IDs
        local container_ids
        container_ids=$($DOCKER_COMPOSE ps -q)
        
        if [[ -n "$container_ids" ]]; then
            docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}" $container_ids 2>/dev/null || warning "Unable to fetch container stats"
        else
            warning "No running containers found"
        fi
        
        echo ""
        echo -e "${YELLOW}⏰ Next update in ${interval}s... (Ctrl+C to stop)${NC}"
        sleep "$interval"
    done
    
    success "Resource monitoring completed"
}

# Backup container volumes
backup_volumes() {
    local backup_name="${1:-containers_${TIMESTAMP}}"
    local backup_dir="$PROJECT_ROOT/.cache/backups"
    
    mkdir -p "$backup_dir"
    
    info "Creating volume backup: $backup_name"
    
    cd "$DOCKER_COMPOSE_DIR"
    
    # Get volume names
    local volumes
    volumes=$($DOCKER_COMPOSE config --volumes 2>/dev/null || echo "")
    
    if [[ -z "$volumes" ]]; then
        warning "No volumes found to backup"
        return 1
    fi
    
    local backup_file="$backup_dir/${backup_name}.tar.gz"
    
    # Create temporary container to backup volumes
    info "Backing up volumes to $backup_file"
    
    for volume in $volumes; do
        info "Backing up volume: $volume"
        docker run --rm \
            -v "${volume}:/backup-source:ro" \
            -v "$backup_dir:/backup-dest" \
            alpine:latest \
            tar -czf "/backup-dest/${volume}_${TIMESTAMP}.tar.gz" -C /backup-source . \
            2>/dev/null || warning "Failed to backup volume: $volume"
    done
    
    success "Volume backup completed in $backup_dir"
}

# Show help
show_help() {
    echo -e "${PURPLE}🐳 Container Manager for Agent Development${NC}"
    echo "==========================================="
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  status                          - Show container status overview"
    echo "  restart <service> [cascade]     - Restart service (cascade=true for dependencies)" 
    echo "  logs <service> [lines] [follow] - Show logs (follow=true to tail)"
    echo "  shell <service> [shell-cmd]     - Access container shell"
    echo "  monitor [duration] [interval]   - Monitor resource usage"
    echo "  backup [name]                   - Backup container volumes"
    echo "  help                           - Show this help"
    echo ""
    echo "Available Services:"
    for service in "${!SERVICES[@]}"; do
        echo "  $service - ${SERVICES[$service]}"
    done
    echo ""
    echo "Examples:"
    echo "  $0 status                      # Show all container status"
    echo "  $0 restart netbox             # Restart just NetBox"
    echo "  $0 restart postgres true      # Restart PostgreSQL and dependents"
    echo "  $0 logs netbox 100 true       # Follow last 100 lines of NetBox logs"
    echo "  $0 shell netbox               # Access NetBox container shell"
    echo "  $0 monitor 300 10             # Monitor resources for 5min, 10s intervals"
    echo "  $0 backup emergency_backup    # Create emergency volume backup"
}

# Main command dispatcher
main() {
    case "${1:-help}" in
        status)
            show_status
            ;;
        restart)
            restart_service "$2" "$3"
            ;;
        logs)
            show_logs "$2" "$3" "$4"
            ;;
        shell)
            shell_access "$2" "$3"
            ;;
        monitor)
            monitor_resources "$2" "$3"
            ;;
        backup)
            backup_volumes "$2"
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

# Trap Ctrl+C gracefully
trap 'echo -e "\n${YELLOW}Operation interrupted by user${NC}"; exit 130' INT

# Run main function
main "$@"