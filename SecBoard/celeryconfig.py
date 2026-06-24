# SecBoard/SecBoard/celeryconfig.py

# SecBoard/SecBoard/celeryconfig.py

# Broker settings
broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'

# Redis Connection Pool Settings
broker_pool_limit = 10
redis_max_connections = 20
broker_connection_max_retries = 0  # Retry forever
broker_connection_retry_on_startup = True

# Serialization
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Time and timezone
timezone = 'Europe/Kiev'
enable_utc = True

# Task execution settings
task_track_started = True
task_time_limit = 30 * 60  # 30 minutes
task_soft_time_limit = 60
task_store_errors_even_if_ignored = True

# Queue settings
task_default_queue = 'default'
task_queues = {
    'default': {
        'exchange': 'default',
        'routing_key': 'default'
    },
    'keycert': {
        'exchange': 'keycert',
        'routing_key': 'keycert'
    }
}

# Task routing
task_routes = {
    'app_keycert.tasks.*': {'queue': 'keycert'},
}

# Worker settings
worker_prefetch_multiplier = 1
worker_max_tasks_per_child = 100
worker_enable_remote_control = True

# Beat settings
beat_scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'
beat_schedule = {
    'check-reminders': {
        'task': 'app_keycert.tasks.check_reminders',
        'schedule': 30 * 60,  # Every 30 minutes
        'options': {'queue': 'keycert'}
    },
    'cleanup-old-reminders': {
        'task': 'app_keycert.tasks.cleanup_old_reminders',
        'schedule': 24 * 60 * 60,  # Daily at midnight
        'options': {'queue': 'keycert'}
    },
    'beat-heartbeat': {
        'task': 'app_access.tasks.beat_heartbeat',
        'schedule': 60.0,  # Every minute
        'options': {'queue': 'default'}
    },
}

# Task result settings
task_ignore_result = False

# Rate limiting
task_annotations = {
    '*': {
        'rate_limit': '10/m'
    }
}

# Additional optimizations
worker_max_memory_per_child = 200000  # 200MB
worker_proc_alive_timeout = 60.0
result_expires = 24 * 60 * 60  # Results expire in 24 hours