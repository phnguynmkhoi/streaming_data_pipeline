#!/bin/bash
# Runs the Scala streaming job (PLAN.md 5.3). Build it first:
#   bash script/build_scala_app.sh
#
# Two modes:
#   client  (default) -- driver runs inside spark-master, same as the PySpark
#                        job, so the two can be compared like for like.
#   cluster           -- driver runs on a worker with --supervise, which is
#                        the whole point of the migration: Spark restarts the
#                        driver itself, no shell retry loop needed.
# Cluster mode needs no retry loop, so it does not use `until`.
set -u
MODE="${1:-client}"
JAR=/opt/spark/spark-apps/pipeline-streaming.jar
CLASS=pipeline.ExtractData

if [ "$MODE" = "cluster" ]; then
  # --supervise restarts the driver if it exits non-zero. Stop it with
  #   docker exec spark-master bin/spark-submit --master spark://spark-master:7077 --kill <driverId>
  # -- killing the process would just make Spark restart it.
  docker exec spark-master bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode cluster \
    --supervise \
    --conf spark.cores.max=2 \
    --conf spark.sql.streaming.metricsEnabled=true \
    --class "$CLASS" \
    "$JAR"
else
  until docker exec spark-master bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --conf spark.cores.max=2 \
    --conf spark.sql.streaming.metricsEnabled=true \
    --conf spark.ui.prometheus.enabled=true \
    --class "$CLASS" \
    "$JAR"; do
    exit_code=$?
    echo "Scala Spark job exited with code ${exit_code}. Restarting in 5s..." >&2
    sleep 5
  done
fi
