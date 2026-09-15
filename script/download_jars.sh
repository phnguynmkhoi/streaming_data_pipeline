#!/bin/bash
# Downloads the JARs Dockerfile.spark bakes into the Spark image (COPY
# ./jars/* /opt/spark/jars): S3A/MinIO support + the Kafka connector for
# Spark Structured Streaming (PLAN.md 2.6), plus spark-avro for decoding
# Debezium's Avro CDC topics (PLAN.md 3.2). jars/ is gitignored (binaries
# don't belong in the repo), so this script is how you (re)populate it.
# Safe to re-run: skips any jar that's already present.
set -eu
cd "$(dirname "$0")/.."
mkdir -p jars

jars=(
  "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.11.375/aws-java-sdk-bundle-1.11.375.jar"
  "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.2.0/hadoop-aws-3.2.0.jar"
  "https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.1.3/spark-sql-kafka-0-10_2.12-3.1.3.jar"
  "https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.1.3/spark-token-provider-kafka-0-10_2.12-3.1.3.jar"
  "https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/2.6.0/kafka-clients-2.6.0.jar"
  "https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.6.2/commons-pool2-2.6.2.jar"
  "https://repo1.maven.org/maven2/org/apache/spark/spark-avro_2.12/3.1.3/spark-avro_2.12-3.1.3.jar"
  "https://repo1.maven.org/maven2/org/apache/avro/avro/1.8.2/avro-1.8.2.jar"  # version pinned by Spark 3.1.3's own pom.xml (avro.version property)
  "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-3.1_2.12/1.3.1/iceberg-spark-runtime-3.1_2.12-1.3.1.jar"  # last Iceberg release supporting Spark 3.1 (PLAN.md 4.3)
)

for url in "${jars[@]}"; do
  out="jars/$(basename "$url")"
  if [ -f "$out" ]; then
    echo "  $(basename "$out") already present, skipping"
  else
    echo "  downloading $(basename "$out")"
    curl -sS -o "$out" "$url"
  fi
done
