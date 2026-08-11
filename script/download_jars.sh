#!/bin/bash
# Downloads the JARs Dockerfile.spark bakes into the Spark image (COPY
# ./jars/* /opt/spark/jars): S3A/MinIO support + the Kafka connector for
# Spark Structured Streaming (PLAN.md 2.6). jars/ is gitignored (binaries
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
