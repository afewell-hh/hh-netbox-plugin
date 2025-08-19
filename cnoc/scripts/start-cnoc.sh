#!/bin/bash

# CNOC Startup Script
# Purpose: Consistent startup of CNOC with proper environment configuration
# Created: 2025-08-18
# Requirements: Built cnoc binary, templates, and environment variables

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CNOC_ROOT="$(dirname "$SCRIPT_DIR")"
CNOC_BINARY="$CNOC_ROOT/cnoc"
CNOC_PID_FILE="/tmp/cnoc.pid"

# Default environment configuration
DEFAULT_SERVER_ADDRESS=":8080"
DEFAULT_ENVIRONMENT="development"
DEFAULT_BASE_URL="http://localhost:8080"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to check if CNOC is already running
check_running() {
    if [ -f "$CNOC_PID_FILE" ]; then
        PID=$(cat "$CNOC_PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0  # Running
        else
            rm -f "$CNOC_PID_FILE"  # Clean up stale PID file
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

# Function to stop CNOC
stop_cnoc() {
    if check_running; then
        PID=$(cat "$CNOC_PID_FILE")
        log "Stopping CNOC (PID: $PID)..."
        kill -TERM "$PID" 2>/dev/null || true
        
        # Wait for graceful shutdown (up to 30 seconds)
        for i in {1..30}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p "$PID" > /dev/null 2>&1; then
            warn "Graceful shutdown failed, forcing stop..."
            kill -9 "$PID" 2>/dev/null || true
        fi
        
        rm -f "$CNOC_PID_FILE"
        success "CNOC stopped successfully"
    else
        warn "CNOC is not currently running"
    fi
}

# Function to check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if cnoc binary exists
    if [ ! -f "$CNOC_BINARY" ]; then
        error "CNOC binary not found at: $CNOC_BINARY"
        error "Please run 'go build -o cnoc ./cmd/cnoc/' first"
        exit 1
    fi
    
    # Check if binary is executable
    if [ ! -x "$CNOC_BINARY" ]; then
        error "CNOC binary is not executable: $CNOC_BINARY"
        exit 1
    fi
    
    # Check if templates exist
    if [ ! -d "$CNOC_ROOT/web/templates" ]; then
        error "Templates directory not found: $CNOC_ROOT/web/templates"
        exit 1
    fi
    
    # Check for required template files
    REQUIRED_TEMPLATES=("base.html" "dashboard.html" "simple_dashboard.html")
    for template in "${REQUIRED_TEMPLATES[@]}"; do
        if [ ! -f "$CNOC_ROOT/web/templates/$template" ]; then
            error "Required template not found: $CNOC_ROOT/web/templates/$template"
            exit 1
        fi
    done
    
    success "Prerequisites check passed"
}

# Function to check port availability
check_ports() {
    log "Checking port availability..."
    
    # Extract port from SERVER_ADDRESS
    PORT=$(echo "${SERVER_ADDRESS:-$DEFAULT_SERVER_ADDRESS}" | sed 's/^://')
    
    # Check if web port is available
    if ss -tlnp | grep -q ":$PORT "; then
        error "Port $PORT is already in use"
        log "Current port usage:"
        ss -tlnp | grep -E ":(8080|9090|9091) "
        exit 1
    fi
    
    # Check if metrics port (9090) is available
    if ss -tlnp | grep -q ":9090 " && ! ss -tlnp | grep ":9090 " | grep -q "cnoc"; then
        warn "Port 9090 (metrics) is already in use by another process"
        ss -tlnp | grep ":9090 "
    fi
    
    success "Port $PORT is available"
}

# Function to set up environment
setup_environment() {
    log "Setting up environment..."
    
    # Set default environment variables if not provided
    export SERVER_ADDRESS="${SERVER_ADDRESS:-$DEFAULT_SERVER_ADDRESS}"
    export ENVIRONMENT="${ENVIRONMENT:-$DEFAULT_ENVIRONMENT}"
    export BASE_URL="${BASE_URL:-$DEFAULT_BASE_URL}"
    
    log "Environment configuration:"
    log "  SERVER_ADDRESS: $SERVER_ADDRESS"
    log "  ENVIRONMENT: $ENVIRONMENT"
    log "  BASE_URL: $BASE_URL"
    
    # Change to CNOC root directory for proper template resolution
    cd "$CNOC_ROOT"
    log "Working directory: $(pwd)"
}

# Function to perform health check
health_check() {
    local max_attempts=10
    local attempt=1
    local port=$(echo "$SERVER_ADDRESS" | sed 's/^://')
    
    log "Performing health check..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s --connect-timeout 2 "http://localhost:$port/health" > /dev/null; then
            success "Health check passed"
            return 0
        fi
        
        log "Health check attempt $attempt/$max_attempts failed, retrying..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    error "Health check failed after $max_attempts attempts"
    return 1
}

# Function to verify dashboard response
verify_dashboard() {
    local port=$(echo "$SERVER_ADDRESS" | sed 's/^://')
    local response_size
    
    log "Verifying dashboard response..."
    
    # Check dashboard response size (Issue #72 requirement: >6099 bytes)
    response_size=$(curl -s "http://localhost:$port/dashboard" | wc -c)
    
    if [ "$response_size" -gt 6099 ]; then
        success "Dashboard response size: $response_size bytes (exceeds 6099 byte requirement)"
    else
        error "Dashboard response size: $response_size bytes (below 6099 byte requirement)"
        return 1
    fi
    
    # Check that response is actual HTML
    if curl -s "http://localhost:$port/dashboard" | head -1 | grep -q "<!DOCTYPE html>"; then
        success "Dashboard returns valid HTML"
    else
        error "Dashboard does not return valid HTML"
        return 1
    fi
}

# Function to start CNOC
start_cnoc() {
    log "Starting CNOC..."
    
    # Start CNOC in background
    nohup "$CNOC_BINARY" > /tmp/cnoc.log 2>&1 &
    PID=$!
    
    # Save PID
    echo "$PID" > "$CNOC_PID_FILE"
    
    log "CNOC started with PID: $PID"
    log "Log file: /tmp/cnoc.log"
    
    # Wait a moment for startup
    sleep 3
    
    # Verify it's still running
    if ! ps -p "$PID" > /dev/null 2>&1; then
        error "CNOC failed to start"
        if [ -f "/tmp/cnoc.log" ]; then
            error "Last 10 lines of log:"
            tail -10 /tmp/cnoc.log | sed 's/^/  /'
        fi
        exit 1
    fi
    
    success "CNOC is running (PID: $PID)"
}

# Function to show status
show_status() {
    if check_running; then
        PID=$(cat "$CNOC_PID_FILE")
        success "CNOC is running (PID: $PID)"
        
        # Show port information
        log "Port usage:"
        ss -tlnp | grep "cnoc" | while read line; do
            log "  $line"
        done
        
        # Show recent log entries
        if [ -f "/tmp/cnoc.log" ]; then
            log "Recent log entries:"
            tail -5 /tmp/cnoc.log | sed 's/^/  /'
        fi
    else
        warn "CNOC is not running"
    fi
}

# Function to show usage
usage() {
    echo "CNOC Startup Script"
    echo
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "Commands:"
    echo "  start     Start CNOC (default)"
    echo "  stop      Stop CNOC"
    echo "  restart   Restart CNOC"
    echo "  status    Show CNOC status"
    echo "  health    Check CNOC health"
    echo
    echo "Environment Variables:"
    echo "  SERVER_ADDRESS    Server bind address (default: :8080)"
    echo "  ENVIRONMENT       Environment mode (default: development)"
    echo "  BASE_URL          Base URL for the service (default: http://localhost:8080)"
    echo
    echo "Examples:"
    echo "  $0 start                                    # Start with defaults"
    echo "  SERVER_ADDRESS=:8081 $0 start              # Start on port 8081"
    echo "  ENVIRONMENT=production $0 start            # Start in production mode"
    echo "  $0 stop                                     # Stop CNOC"
    echo "  $0 restart                                  # Restart CNOC"
}

# Main script logic
main() {
    local command="${1:-start}"
    
    case "$command" in
        "start")
            if check_running; then
                warn "CNOC is already running"
                show_status
                exit 0
            fi
            
            check_prerequisites
            setup_environment
            check_ports
            start_cnoc
            health_check
            verify_dashboard
            show_status
            success "CNOC startup completed successfully"
            ;;
        "stop")
            stop_cnoc
            ;;
        "restart")
            stop_cnoc
            sleep 2
            $0 start
            ;;
        "status")
            show_status
            ;;
        "health")
            if check_running; then
                setup_environment
                if health_check && verify_dashboard; then
                    success "CNOC is healthy and dashboard is working"
                else
                    error "CNOC health check failed"
                    exit 1
                fi
            else
                error "CNOC is not running"
                exit 1
            fi
            ;;
        "help"|"-h"|"--help")
            usage
            ;;
        *)
            error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"