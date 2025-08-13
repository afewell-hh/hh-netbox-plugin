#!/bin/bash
# NetBox Hedgehog Plugin - Development Performance Optimization
# =============================================================
# Optimizes the development environment for maximum performance

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

DOCKER_COMPOSE_DIR="$(dirname "$0")/../gitignore/netbox-docker"

optimize_docker_performance() {
    log "Optimizing Docker performance..."
    
    # Create optimized docker-compose.override.yml
    cat > "$DOCKER_COMPOSE_DIR/docker-compose.override.yml" << 'EOF'
# Development Performance Optimizations
services:
  netbox:
    environment:
      # Django development optimizations
      - DJANGO_DEBUG=True
      - DJANGO_DEVELOPER=True
      - DEBUG_TOOLBAR=True
      # Cache optimizations
      - CACHE_TIMEOUT=300
      - SESSION_CACHE_ALIAS=default
    volumes:
      # Optimized volume mounts for better performance
      - ./netbox_hedgehog:/opt/netbox/netbox/netbox_hedgehog:rw,cached
      - ./configuration:/etc/netbox/config:z,ro,cached
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2.0'
        reservations:
          memory: 1G
          cpus: '1.0'

  netbox-worker:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'

  netbox-rq-worker-hedgehog:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'

  postgres:
    environment:
      # PostgreSQL performance optimizations
      - POSTGRES_INITDB_ARGS=--data-checksums
    command: >
      postgres
      -c shared_buffers=256MB
      -c effective_cache_size=1GB
      -c maintenance_work_mem=64MB
      -c checkpoint_completion_target=0.7
      -c wal_buffers=16MB
      -c default_statistics_target=100
      -c random_page_cost=1.1
      -c effective_io_concurrency=200
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'

  redis:
    command: >
      sh -c "redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --save 900 1
      --save 300 10
      --save 60 10000
      --requirepass $$REDIS_PASSWORD"
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'

  redis-cache:
    command: >
      sh -c "redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --save ''
      --requirepass $$REDIS_PASSWORD"
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
EOF

    success "Docker performance optimizations applied"
}

optimize_netbox_settings() {
    log "Creating optimized NetBox configuration..."
    
    # Create performance-optimized configuration
    cat > "$DOCKER_COMPOSE_DIR/configuration/performance.py" << 'EOF'
# NetBox Development Performance Configuration
# ===========================================

# Debug settings for development
DEBUG = True
DEVELOPER = True

# Database optimizations
DATABASES['default'].update({
    'OPTIONS': {
        'sslmode': 'disable',
        'connect_timeout': 10,
        'options': '-c default_transaction_isolation=read_committed'
    },
    'CONN_MAX_AGE': 300,
    'ATOMIC_REQUESTS': False,
})

# Cache configuration for development
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            }
        },
        'TIMEOUT': 300,
        'KEY_PREFIX': 'netbox',
    }
}

# Session optimization
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 3600  # 1 hour for development

# Template optimization
TEMPLATES[0]['OPTIONS'].update({
    'context_processors': TEMPLATES[0]['OPTIONS']['context_processors'] + [
        'django.template.context_processors.debug',
    ]
})

# Static files optimization for development
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Disable unnecessary middleware in development
MIDDLEWARE = [mw for mw in MIDDLEWARE if 'SecurityMiddleware' not in mw]

# Logging optimization for development
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'INFO',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'netbox_hedgehog': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# RQ optimization
RQ_QUEUES = {
    'default': {
        'HOST': 'redis',
        'PORT': 6379,
        'DB': 0,
        'PASSWORD': 'netbox',
        'DEFAULT_TIMEOUT': 300,
        'CONNECTION_KWARGS': {
            'socket_timeout': 5,
            'socket_connect_timeout': 5,
            'health_check_interval': 30,
        },
    },
    'hedgehog_sync': {
        'HOST': 'redis',
        'PORT': 6379,
        'DB': 0,
        'PASSWORD': 'netbox',
        'DEFAULT_TIMEOUT': 600,
        'CONNECTION_KWARGS': {
            'socket_timeout': 10,
            'socket_connect_timeout': 10,
            'health_check_interval': 30,
        },
    }
}

# Email backend for development (console output)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Plugin-specific optimizations
PLUGINS_CONFIG = {
    'netbox_hedgehog': {
        'kubernetes_config_file': None,
        'sync_interval': 300,
        'enable_webhooks': True,
        'max_concurrent_syncs': 3,  # Reduced for development
        'enable_gitops': True,
        'gitops_auto_sync': True,
        'git_poll_interval': 60,
        'drift_detection_interval': 300,
        # Performance optimizations
        'cache_timeout': 60,
        'enable_debug': True,
        'log_level': 'DEBUG',
    }
}
EOF

    success "NetBox performance configuration created"
}

create_development_docker_compose() {
    log "Creating development-optimized docker-compose file..."
    
    # Copy base docker-compose and add development optimizations
    cp "$DOCKER_COMPOSE_DIR/docker-compose.yml" "$DOCKER_COMPOSE_DIR/docker-compose.dev.yml"
    
    cat >> "$DOCKER_COMPOSE_DIR/docker-compose.dev.yml" << 'EOF'

# Development environment extensions
  netbox-dev:
    <<: *netbox
    command:
      - /opt/netbox/venv/bin/python
      - /opt/netbox/netbox/manage.py
      - runserver
      - 0.0.0.0:8000
    environment:
      - DJANGO_SETTINGS_MODULE=netbox.settings
      - PYTHONUNBUFFERED=1
      - DJANGO_DEBUG=True
      - DJANGO_DEVELOPMENT=True
    ports:
      - "8001:8000"  # Alternative port for development server
    profiles:
      - dev

  # Development tools container
  dev-tools:
    <<: *netbox
    command: tail -f /dev/null  # Keep container running
    environment:
      - DJANGO_SETTINGS_MODULE=netbox.settings
      - PYTHONUNBUFFERED=1
    profiles:
      - dev
    
  # Performance monitoring
  redis-monitor:
    image: redis:alpine
    command: redis-cli -h redis -a netbox monitor
    depends_on:
      - redis
    profiles:
      - monitor
EOF

    success "Development docker-compose configuration created"
}

optimize_system_settings() {
    log "Checking system-level optimizations..."
    
    # Check Docker daemon settings
    if docker info | grep -q "Storage Driver: overlay2"; then
        success "Docker using overlay2 storage driver (optimal)"
    else
        warning "Consider switching to overlay2 storage driver for better performance"
    fi
    
    # Check available memory
    total_mem=$(free -m | awk 'NR==2{printf "%.1f", $2/1024}')
    if (( $(echo "$total_mem > 8" | bc -l) )); then
        success "System has ${total_mem}GB RAM (good for development)"
    else
        warning "System has ${total_mem}GB RAM (consider 8GB+ for optimal performance)"
    fi
    
    # Check Docker memory limits
    docker_mem=$(docker system info | grep "Total Memory" | awk '{print $3$4}')
    log "Docker memory available: $docker_mem"
}

create_performance_monitoring_script() {
    log "Creating performance monitoring script..."
    
    cat > "$DOCKER_COMPOSE_DIR/../scripts/monitor-dev-performance.sh" << 'EOF'
#!/bin/bash
# Development Performance Monitor
# ==============================

echo "NetBox Development Performance Monitor"
echo "======================================"
echo ""

echo "Container Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" || echo "Docker not running"
echo ""

echo "Response Time Test:"
start_time=$(date +%s.%N)
curl -s http://localhost:8000/login/ > /dev/null 2>&1
end_time=$(date +%s.%N)
response_time=$(echo "$end_time - $start_time" | bc)
echo "NetBox response time: ${response_time}s"
echo ""

echo "Database Connections:"
docker compose exec -T postgres psql -U netbox -d netbox -c "SELECT count(*) as active_connections FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null || echo "Database not available"
echo ""

echo "Redis Memory Usage:"
docker compose exec -T redis redis-cli -a netbox info memory | grep used_memory_human 2>/dev/null || echo "Redis not available"
echo ""

echo "Recent Errors (last 10 lines):"
docker compose logs --tail=10 netbox | grep -i error || echo "No recent errors"
EOF

    chmod +x "$DOCKER_COMPOSE_DIR/../scripts/monitor-dev-performance.sh"
    success "Performance monitoring script created"
}

main() {
    echo ""
    echo -e "${BLUE}NetBox Hedgehog Development Performance Optimization${NC}"
    echo "======================================================"
    echo ""
    
    cd "$DOCKER_COMPOSE_DIR" || exit 1
    
    optimize_docker_performance
    optimize_netbox_settings  
    create_development_docker_compose
    optimize_system_settings
    create_performance_monitoring_script
    
    echo ""
    echo -e "${GREEN}Performance optimization completed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Restart development environment:"
    echo "   docker compose down && docker compose up -d"
    echo ""
    echo "2. Monitor performance:"
    echo "   ../scripts/monitor-dev-performance.sh"
    echo ""
    echo "3. Use development server (optional):"
    echo "   docker compose --profile dev up netbox-dev"
    echo ""
}

main "$@"