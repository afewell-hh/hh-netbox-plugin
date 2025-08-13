#!/bin/bash
# NetBox Hedgehog Plugin - Development Commands
# =============================================
# Simple commands for common development scenarios

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOCKER_COMPOSE_DIR="$(dirname "$0")/../gitignore/netbox-docker"
NETBOX_URL="http://localhost:8000"

log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Change to docker compose directory
cd_docker() {
    cd "$DOCKER_COMPOSE_DIR" || {
        error "Could not find docker-compose directory at $DOCKER_COMPOSE_DIR"
        exit 1
    }
}

# Quick development commands
dev_status() {
    log "Checking development environment status..."
    cd_docker
    echo ""
    echo "=== Container Status ==="
    docker compose ps
    echo ""
    echo "=== Service Health ==="
    docker compose exec -T netbox curl -s "$NETBOX_URL/admin/" > /dev/null && echo "✅ NetBox web interface: OK" || echo "❌ NetBox web interface: DOWN"
    docker compose exec -T postgres pg_isready -q -h localhost -p 5432 -d netbox -U netbox && echo "✅ PostgreSQL: OK" || echo "❌ PostgreSQL: DOWN"
    docker compose exec -T redis redis-cli -a netbox ping | grep -q PONG && echo "✅ Redis: OK" || echo "❌ Redis: DOWN"
    echo ""
    echo "=== Quick Access ==="
    echo "NetBox URL: $NETBOX_URL"
    echo "Plugin URL: $NETBOX_URL/plugins/hedgehog/"
}

dev_logs() {
    log "Showing development logs..."
    cd_docker
    if [ "$1" = "follow" ] || [ "$1" = "-f" ]; then
        docker compose logs -f netbox netbox-worker netbox-rq-worker-hedgehog
    else
        docker compose logs --tail=50 netbox netbox-worker netbox-rq-worker-hedgehog
    fi
}

dev_restart_fast() {
    log "Fast restart for model/code changes..."
    cd_docker
    docker compose restart netbox netbox-worker netbox-rq-worker-hedgehog
    success "Fast restart completed. Services restarting..."
    sleep 3
    dev_status
}

dev_restart_full() {
    log "Full restart for settings/config changes..."
    cd_docker
    docker compose restart
    success "Full restart completed. All services restarting..."
    sleep 5
    dev_status
}

dev_migrate() {
    log "Creating and applying database migrations..."
    cd_docker
    
    # Create migrations
    log "Creating migrations..."
    docker compose exec netbox python manage.py makemigrations netbox_hedgehog
    
    # Apply migrations
    log "Applying migrations..."
    docker compose exec netbox python manage.py migrate
    
    # Restart services to reload model changes
    log "Restarting services..."
    docker compose restart netbox netbox-worker netbox-rq-worker-hedgehog
    
    success "Migration completed successfully"
}

dev_shell() {
    log "Opening Django shell..."
    cd_docker
    docker compose exec netbox python manage.py shell
}

dev_test() {
    local test_pattern="$1"
    log "Running tests..."
    cd_docker
    
    if [ -n "$test_pattern" ]; then
        log "Running specific tests: $test_pattern"
        docker compose exec netbox python manage.py test netbox_hedgehog."$test_pattern"
    else
        log "Running all plugin tests..."
        docker compose exec netbox python manage.py test netbox_hedgehog
    fi
}

dev_static() {
    log "Collecting static files..."
    cd_docker
    docker compose exec netbox python manage.py collectstatic --noinput
    success "Static files collected"
}

dev_reset_db() {
    warning "This will RESET ALL DATABASE DATA!"
    read -p "Are you sure? (type 'yes' to confirm): " confirm
    if [ "$confirm" = "yes" ]; then
        log "Resetting database..."
        cd_docker
        docker compose exec netbox python manage.py flush --noinput
        docker compose exec netbox python manage.py migrate
        log "Creating superuser..."
        docker compose exec netbox python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created: admin/admin')
else:
    print('Superuser already exists')
"
        success "Database reset completed. Login: admin/admin"
    else
        log "Database reset cancelled"
    fi
}

dev_debug() {
    log "Starting debug session..."
    cd_docker
    echo ""
    echo "=== Debug Information ==="
    echo "Container stats:"
    docker stats --no-stream netbox netbox-worker netbox-rq-worker-hedgehog
    echo ""
    echo "Recent errors:"
    docker compose logs --tail=20 netbox | grep -i error || echo "No recent errors found"
    echo ""
    echo "Django debug commands available:"
    echo "  docker compose exec netbox python manage.py shell"
    echo "  docker compose exec netbox python manage.py dbshell"
    echo "  docker compose exec netbox python manage.py check"
}

dev_performance() {
    log "Running performance checks..."
    cd_docker
    echo ""
    echo "=== Performance Metrics ==="
    echo "Container resource usage:"
    docker stats --no-stream netbox
    echo ""
    echo "Database connections:"
    docker compose exec postgres psql -U netbox -d netbox -c "SELECT count(*) as active_connections FROM pg_stat_activity WHERE state = 'active';"
    echo ""
    echo "Django checks:"
    docker compose exec netbox python manage.py check --deploy
}

# Help function
show_help() {
    echo ""
    echo -e "${BLUE}NetBox Hedgehog Plugin - Development Commands${NC}"
    echo "=============================================="
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  status          - Show development environment status"
    echo "  logs [follow]   - Show logs (add 'follow' to tail logs)"
    echo "  restart-fast    - Fast restart for code/model changes (10-15s)"
    echo "  restart-full    - Full restart for settings/config changes (30s)"
    echo "  migrate         - Create and apply database migrations"
    echo "  shell           - Open Django shell"
    echo "  test [pattern]  - Run tests (optionally specify test pattern)"
    echo "  static          - Collect static files"
    echo "  reset-db        - Reset database (WARNING: destroys all data)"
    echo "  debug           - Show debug information"
    echo "  performance     - Show performance metrics"
    echo "  help            - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 status                    # Check environment status"
    echo "  $0 logs follow              # Follow logs in real-time"
    echo "  $0 restart-fast             # Quick restart after code changes"
    echo "  $0 migrate                  # Apply database migrations"
    echo "  $0 test models              # Run model tests only"
    echo ""
    echo "Quick Development Loop:"
    echo "  1. Make code changes"
    echo "  2. $0 status               # Check if auto-reload worked"
    echo "  3. $0 migrate              # If models changed"
    echo "  4. $0 test                 # Run tests"
    echo ""
}

# Main command router
main() {
    case "${1:-help}" in
        "status")
            dev_status
            ;;
        "logs")
            dev_logs "$2"
            ;;
        "restart-fast"|"restart")
            dev_restart_fast
            ;;
        "restart-full")
            dev_restart_full
            ;;
        "migrate")
            dev_migrate
            ;;
        "shell")
            dev_shell
            ;;
        "test")
            dev_test "$2"
            ;;
        "static")
            dev_static
            ;;
        "reset-db")
            dev_reset_db
            ;;
        "debug")
            dev_debug
            ;;
        "performance"|"perf")
            dev_performance
            ;;
        "help"|"-h"|"--help"|"")
            show_help
            ;;
        *)
            error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"