# Superset config (PLAN.md 4.2). Kept minimal: metadata lives in the SQLite
# file on the superset_home volume, which is fine for a single-user dev stack
# (Postgres-backed metadata + Celery workers would be the production setup).
import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"

# Trino queries can outlive the default 30s on cold Iceberg reads.
SUPERSET_WEBSERVER_TIMEOUT = 120
SQLLAB_TIMEOUT = 120
SQLLAB_ASYNC_TIME_LIMIT_SEC = 300

FEATURE_FLAGS = {
    "EMBEDDED_SUPERSET": False,
    "ALERT_REPORTS": False,
}
