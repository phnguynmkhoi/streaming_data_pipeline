#!/bin/bash
# Merges every completed, not-yet-merged day of staging CDC data into the
# Iceberg lakehouse (PLAN.md 4.3). Manual for now -- scheduling is PLAN.md 4.4.
# Safe to re-run: already-merged days are skipped.
# Pass --include-today to also merge today's still-open partition (e.g. to
# check results without waiting for midnight UTC); it isn't marked as merged.
set -eu
cd "$(dirname "$0")/.."

docker exec spark-master bin/spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --conf spark.cores.max=2 \
  --py-files spark-apps/credential.py,spark-apps/helper.py \
  spark-apps/merge_to_iceberg.py "$@"
