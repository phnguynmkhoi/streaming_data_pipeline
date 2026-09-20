#!/bin/bash
# Safely shut down the whole streaming pipeline.
#
# What "safe" means here: stop the Spark streaming job first (so it isn't
# killed mid-write to MinIO/Kafka), then bring the stack down without
# touching volumes, so Postgres (postgres_data), MinIO (minio-volume) and
# Kafka (kafka-data, PLAN.md 5.1) data survive. Zookeeper and Pinot still
# have no volumes, so Pinot's cluster state comes back empty next start —
# a known limitation tracked under 5.4, not something this script changes.
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

# The Debezium replication slot is deliberately LEFT IN PLACE. It used to be
# dropped here because the broker had no volume, so Connect's state was wiped
# on every 'down' and the slot was orphaned. Since PLAN.md 5.1 the broker has
# a volume: connector offsets survive, and the slot is what retains the WAL
# they point at. Dropping it now would make Debezium resume from a position
# Postgres no longer has. Unbounded WAL growth isn't a concern while the stack
# is down, because Postgres is down too and generates no WAL.

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
echo "  Preserved (named volumes): Postgres data, MinIO data (parquet/DLQ),"
echo "  Kafka topics + Connect offsets (PLAN.md 5.1), and the Debezium"
echo "  replication slot — so CDC resumes where it left off, no re-snapshot."
echo "  NOT preserved (no volume): Zookeeper and Pinot cluster state, so Pinot"
echo "  schemas/tables are re-created on next start (5.4)."
echo "  — script/start_pipeline.sh handles that for you automatically."
