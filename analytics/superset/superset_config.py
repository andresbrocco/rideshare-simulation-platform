import os

SECRET_KEY = os.environ.get(
    "SUPERSET_SECRET_KEY", "dev-secret-key-change-in-production"
)

SQLALCHEMY_DATABASE_URI = (
    "postgresql://superset:superset@postgres-superset:5432/superset"
)


class CeleryConfig:
    broker_url = "redis://redis-superset:6379/0"
    imports = ("superset.sql_lab",)
    result_backend = "redis://redis-superset:6379/0"
    worker_prefetch_multiplier = 10
    task_acks_late = True


CELERY_CONFIG = CeleryConfig

RESULTS_BACKEND = {"type": "redis", "uri": "redis://redis-superset:6379/1"}

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_URL": "redis://redis-superset:6379/2",
}

DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_data_",
    "CACHE_REDIS_URL": "redis://redis-superset:6379/3",
}

FILTER_STATE_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_filter_",
    "CACHE_REDIS_URL": "redis://redis-superset:6379/4",
}

EXPLORE_FORM_DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_explore_",
    "CACHE_REDIS_URL": "redis://redis-superset:6379/5",
}

ROW_LIMIT = 5000
SUPERSET_WEBSERVER_PORT = 8088

WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = []
WTF_CSRF_TIME_LIMIT = None

FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
}
