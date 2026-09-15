# spark.cores.max leaves the other worker's cores free for run_iceberg_merge.sh;
# without it a standalone app grabs every core and the merge job never starts.
until docker exec spark-master bin/spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --conf spark.cores.max=2 \
  --py-files spark-apps/credential.py,spark-apps/schema_registry.py,spark-apps/helper.py \
  spark-apps/extract_data.py; do
  exit_code=$?
  echo "Spark job exited with code ${exit_code}. Restarting in 5s..." >&2
  sleep 5
done
