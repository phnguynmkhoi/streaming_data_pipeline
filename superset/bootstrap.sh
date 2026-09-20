#!/bin/bash
# Superset container entrypoint (PLAN.md 4.2): installs the Trino driver,
# migrates the metadata DB, creates the admin user, and registers the Trino
# connection -- all idempotent, so restarts are cheap.
set -eu

# The image ships no Trino driver; installing at start keeps this repo free of
# a second Dockerfile. Needs network on first boot only (pip caches in the volume).
pip install --quiet --no-warn-script-location "trino[sqlalchemy]==0.333.0"

superset db upgrade

superset fab create-admin \
  --username "${SUPERSET_ADMIN_USER:-admin}" \
  --firstname Admin --lastname User \
  --email "${SUPERSET_ADMIN_EMAIL:-admin@example.com}" \
  --password "${SUPERSET_ADMIN_PASSWORD:-admin}" || true

superset init

# Import the Trino connection, datasets, charts and dashboard as code
# (superset/assets). UUIDs are fixed, so re-importing overwrites in place and
# the dashboard survives a wipe of the superset_home volume.
if [ -d /app/assets ]; then
  bundle=/tmp/superset_assets.zip
  rm -f "$bundle"
  (cd /app && python -c "
import shutil
shutil.make_archive('/tmp/superset_assets', 'zip', root_dir='/app', base_dir='assets')
")
  superset import-dashboards -p "$bundle" -u "${SUPERSET_ADMIN_USER:-admin}" \
    || echo 'WARNING: Superset asset import failed; the UI still works, dashboards just are not provisioned' >&2
fi

exec /usr/bin/run-server.sh
