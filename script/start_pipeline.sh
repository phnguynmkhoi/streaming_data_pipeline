#!/bin/bash
# Safely bring up the whole streaming pipeline.
#
# Safe to re-run any time (idempotent): only registers the Debezium
# connector / creates Pinot schemas & tables if they don't already exist,
# so it won't error out on a stack that's only partially down. Pinot
# instance IDs are pinned to container hostnames (PLAN.md 5.4), so restarts
# no longer create ghost/orphaned Helix instances.
set -u
cd "$(dirname "$0")/.."

wait_healthy() {
  local container="$1" timeout="${2:-90}" waited=0
  echo -n "  waiting for $container to be healthy"
  while [ "$waited" -lt "$timeout" ]; do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null)
    if [ "$status" = "healthy" ]; then
      echo " - healthy"
      return 0
    fi
    echo -n "."
    sleep 3
    waited=$((waited + 3))
  done
  echo " - still '$status' after ${timeout}s, continuing anyway"
  return 1
}

echo "== Starting all containers =="
docker compose up -d
status=$?
if [ $status -ne 0 ]; then
  echo "docker compose up failed with exit code $status" >&2
  exit $status
fi

echo
echo "== Waiting for core services =="
wait_healthy zookeeper 60
wait_healthy broker 60
wait_healthy postgres 60
wait_healthy debezium 90
wait_healthy pinot-controller 60
wait_healthy pinot-broker 60
# pinot-server's healthcheck can stay "unhealthy" if a segment is stuck in
# ERROR state (e.g. lost local-disk segment, PLAN.md 5.4 follow-on issue) —
# that's a real condition, not a false negative, so we don't treat it as fatal.
wait_healthy pinot-server 60

echo
echo "== Registering Debezium connector (idempotent) =="
connector_name=$(grep -m1 '"name"' debezium-connector-postgres.json | sed -E 's/.*"name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
existing=$(curl -s http://localhost:8093/connectors 2>/dev/null)
if echo "$existing" | grep -q "\"$connector_name\""; then
  echo "  connector '$connector_name' already registered, skipping"
else
  bash script/script.sh
  echo
fi

echo
echo "== Creating Pinot schemas (idempotent) =="
declare -A entities=( [transaction]=transactions [product]=products [shipping]=shippings [payment]=payments [user]=users )
for arg in "${!entities[@]}"; do
  name="${entities[$arg]}"
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:9000/schemas/$name")
  if [ "$code" = "200" ]; then
    echo "  schema '$name' already exists, skipping"
  else
    script/create_schema.sh "$arg"
    echo
  fi
done

echo
echo "== Creating Pinot tables (idempotent) =="
for arg in "${!entities[@]}"; do
  name="${entities[$arg]}"
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:9000/tables/$name")
  if [ "$code" = "200" ]; then
    echo "  table '$name' already exists, skipping"
  else
    script/create_table.sh "$arg"
    echo
  fi
done

echo
echo "== Done =="
echo "  Everything is up except the Spark streaming job, which runs in the"
echo "  foreground so you can see its logs. Start it with:"
echo "    bash script/spark_extract_data_script.sh"
