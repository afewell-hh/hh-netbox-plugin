"""
Performance-optimized Django settings for HNP
Redis caching, channel layers, and database optimization
"""

import os

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB_CACHE = int(os.getenv('REDIS_DB_CACHE', 1))
REDIS_DB_CHANNELS = int(os.getenv('REDIS_DB_CHANNELS', 2))
REDIS_DB_CELERY = int(os.getenv('REDIS_DB_CELERY', 3))

# Channel Layers Configuration (WebSocket performance)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
            "prefix": "hnp:",
            "symmetric_encryption_keys": [os.getenv('CHANNELS_SECRET_KEY', 'change-me')],
            "capacity": 10000,  # High capacity for enterprise load
            "expiry": 300,  # 5 minutes message expiry
            "group_expiry": 86400,  # 24 hours group expiry
            # Performance optimizations
            "redis": {
                "db": REDIS_DB_CHANNELS,
                "connection_pool_kwargs": {
                    "max_connections": 50,
                    "retry_on_timeout": True,
                },
            },
        },
    },
}

# Cache Configuration (Database query optimization)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CACHE}',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,  # Graceful degradation
        },
        'KEY_PREFIX': 'hnp:cache',
        'TIMEOUT': 300,  # 5 minutes default
    },
    # Separate cache for long-term data
    'fabric_data': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CACHE}',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 20,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'hnp:fabric',
        'TIMEOUT': 3600,  # 1 hour for fabric data
    },
    # Fast cache for real-time events
    'events': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CACHE}',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 30,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'hnp:events',
        'TIMEOUT': 60,  # 1 minute for events
    },
}

# Celery Configuration (Background processing)
CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CELERY}'
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CELERY}'

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# Performance optimization
CELERY_TASK_ROUTES = {
    'netbox_hedgehog.tasks.git_sync_*': {'queue': 'git_sync'},
    'netbox_hedgehog.tasks.kubernetes_*': {'queue': 'kubernetes'},
    'netbox_hedgehog.tasks.cache_*': {'queue': 'cache_refresh'},
}

CELERY_WORKER_CONCURRENCY = int(os.getenv('CELERY_CONCURRENCY', 4))
CELERY_WORKER_PREFETCH_MULTIPLIER = 2
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_DISABLE_RATE_LIMITS = True

# Task time limits
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes
CELERY_TASK_TIME_LIMIT = 600      # 10 minutes hard limit

# Result backend settings
CELERY_RESULT_EXPIRES = 3600  # Results expire in 1 hour
CELERY_TASK_IGNORE_RESULT = False

# Database optimization
DATABASES_PERFORMANCE_SETTINGS = {
    'OPTIONS': {
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        'charset': 'utf8mb4',
        # Connection pooling
        'CONN_MAX_AGE': 60,  # 1 minute connection reuse
    },
    'TEST': {
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        }
    }
}

# Session configuration with Redis
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 hours

# Logging configuration for performance monitoring
PERFORMANCE_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'performance': {
            'format': '[{asctime}] {levelname} {name} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'performance_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/tmp/hnp_performance.log',
            'formatter': 'performance',
        },
    },
    'loggers': {
        'netbox_hedgehog.performance': {
            'handlers': ['performance_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['performance_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Performance monitoring middleware
MIDDLEWARE_PERFORMANCE = [
    'netbox_hedgehog.middleware.PerformanceMonitoringMiddleware',
]

# Template caching
TEMPLATE_CACHE_SETTINGS = {
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'OPTIONS': {
        'loaders': [
            ('django.template.loaders.cached.Loader', [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ]),
        ],
    },
}

# Static files optimization
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.CachedStaticFilesStorage'