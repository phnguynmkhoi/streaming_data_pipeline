#!/bin/bash
# Entrypoint for the iceberg-merge-scheduler container (PLAN.md 4.4): runs the
# Iceberg merge once a day and reports the outcome to Prometheus via
# Pushgateway, so a silently skipped or failing merge alerts instead of
# quietly leaving a growing gap in the serving views.
#
# A plain sleep loop rather than cron: the Spark image has no cron, and this
# needs no extra binary. Local time has no DST here, so "next 01:00" is exact.
set -u

MERGE_AT="${MERGE_AT:-01:00}"
PUSHGATEWAY="${PUSHGATEWAY:-pushgateway:9091}"
JOB="iceberg_merge"

push_metrics() {
  local exit_code="$1" duration="$2" now="$3"
  local payload="# TYPE ${JOB}_last_exit_code gauge
${JOB}_last_exit_code ${exit_code}
# TYPE ${JOB}_last_run_duration_seconds gauge
${JOB}_last_run_duration_seconds ${duration}
# TYPE ${JOB}_last_run_timestamp_seconds gauge
${JOB}_last_run_timestamp_seconds ${now}
"
  if [ "$exit_code" -eq 0 ]; then
    payload="${payload}# TYPE ${JOB}_last_success_timestamp_seconds gauge
${JOB}_last_success_timestamp_seconds ${now}
"
  fi
  # Pushgateway keeps the last value per job, so a later failure doesn't erase
  # the last success timestamp the staleness alert relies on.
  printf '%s' "$payload" | curl -sS --data-binary @- "http://${PUSHGATEWAY}/metrics/job/${JOB}" \
    || echo "WARNING: could not push metrics to ${PUSHGATEWAY}" >&2
}

seconds_until() {
  local target_today target_tomorrow now
  now=$(date +%s)
  target_today=$(date -d "today ${MERGE_AT}" +%s)
  if [ "$target_today" -gt "$now" ]; then
    echo $((target_today - now))
  else
    target_tomorrow=$(date -d "tomorrow ${MERGE_AT}" +%s)
    echo $((target_tomorrow - now))
  fi
}

run_merge() {
  local started exit_code finished
  started=$(date +%s)
  echo "=== merge starting $(date) ==="
  /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --conf spark.cores.max=2 \
    --py-files /opt/spark/spark-apps/credential.py,/opt/spark/spark-apps/helper.py \
    /opt/spark/spark-apps/merge_to_iceberg.py
  exit_code=$?
  finished=$(date +%s)
  echo "=== merge finished with exit ${exit_code} in $((finished - started))s ==="
  push_metrics "$exit_code" "$((finished - started))" "$finished"
}

echo "iceberg merge scheduler: will run daily at ${MERGE_AT}"

# RUN_ON_START=true runs one merge immediately -- for verifying the scheduler
# without waiting for the next scheduled time.
if [ "${RUN_ON_START:-false}" = "true" ]; then
  echo "RUN_ON_START set: running one merge now"
  run_merge
fi

while true; do
  wait_for=$(seconds_until)
  echo "next merge in ${wait_for}s ($(date -d "+${wait_for} seconds"))"
  sleep "$wait_for"
  run_merge
done
