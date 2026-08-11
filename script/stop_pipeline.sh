#!/bin/bash
# Safely shut down the whole streaming pipeline.
#
# What "safe" means here: stop the Spark streaming job first (so it isn't
# killed mid-write to MinIO/Kafka), then bring the stack down without
# touching volumes, so Postgres (postgres_data) and MinIO (minio-volume)
# data survive. Kafka/Zookeeper/Pinot have no volumes (see PLAN.md 5.1) and
# will always come back empty next start — that's a known, separate,
# already-documented limitation, not something this script changes.
set -u
cd "$(dirname "$0")/.."

echo "== Stopping Spark streaming job (if running) =="
# Kills the host-side restart loop first so it doesn't immediately relaunch
# the job after we kill spark-submit below.
if pkill -f "spark_extract_data_script.sh" 2>/dev/null; then
  echo "  stopped host-side restart loop (script/spark_extract_data_script.sh)"
else
  echo "  no host-side restart loop was running"
fi

if docker ps --format '{{.Names}}' | grep -q '^spark-master$'; then
  if docker exec spark-master pkill -f spark-submit 2>/dev/null; then
    echo "  sent stop signal to spark-submit driver inside spark-master"
    sleep 3
  else
    echo "  no spark-submit process running inside spark-master"
  fi
else
  echo "  spark-master container not running, skipping"
fi

echo "== Dropping Debezium replication slot (if present) =="
# postgres_data is a persisted volume, so any replication slot Debezium
# created survives 'docker compose down' — but broker (Kafka) has no volume,
# so the connector's own state is always wiped on 'down' and re-registered
# fresh on next start_pipeline.sh. Left alone, that mismatch orphans the slot
# every cycle: Postgres keeps retaining WAL for a slot nothing is consuming,
# which grows unbounded while the stack is down. Drop it here, while postgres
# is still up, so start is always working from a clean slate.
slot_name=$(grep -m1 '"slot.name"' debezium-connector-postgres.json 2>/dev/null | sed -E 's/.*"slot.name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
slot_name="${slot_name:-debezium}"
if docker ps --format '{{.Names}}' | grep -q '^postgres$'; then
  if docker exec postgres psql -U postgres -tAc "SELECT 1 FROM pg_replication_slots WHERE slot_name='$slot_name'" 2>/dev/null | grep -q 1; then
    docker exec postgres psql -U postgres -c "SELECT pg_drop_replication_slot('$slot_name');" >/dev/null
    echo "  dropped replication slot '$slot_name'"
  else
    echo "  no '$slot_name' replication slot present, skipping"
  fi
else
  echo "  postgres container not running, skipping"
fi

echo
echo "== Bringing down all containers (volumes preserved) =="
docker compose down
status=$?

if [ $status -ne 0 ]; then
  echo "docker compose down failed with exit code $status" >&2
  exit $status
fi

echo
echo "== Done =="
echo "  Preserved (named volumes): Postgres data, MinIO data (parquet/DLQ)."
echo "  NOT preserved (no volume configured, PLAN.md 5.1): Kafka broker data,"
echo "  Zookeeper state, Pinot cluster state. On next start you'll need to"
echo "  re-register the Debezium connector and re-create Pinot schemas/tables"
echo "  — script/start_pipeline.sh does this for you automatically."
