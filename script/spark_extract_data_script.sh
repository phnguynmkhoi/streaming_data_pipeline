until docker exec spark-master bin/spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.1.3 \
  --py-files spark-apps/credential.py,spark-apps/schema.py,spark-apps/helper.py \
  spark-apps/extract_data.py; do
  exit_code=$?
  echo "Spark job exited with code ${exit_code}. Restarting in 5s..." >&2
  sleep 5
done
