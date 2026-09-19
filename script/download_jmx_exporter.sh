#!/bin/bash
# Downloads the Prometheus JMX exporter javaagent, mounted into the Kafka
# broker and Debezium Connect so their JMX metrics become scrapeable
# (PLAN.md 4.1). Neither image bundles one -- Pinot does, so Pinot uses its
# own copy. monitoring/jmx/*.jar is gitignored; the .yml configs next to it
# are tracked. Safe to re-run: skips if already present.
set -eu
cd "$(dirname "$0")/.."

VERSION="1.0.1"
JAR="monitoring/jmx/jmx_prometheus_javaagent.jar"

if [ -f "$JAR" ]; then
  echo "  jmx_prometheus_javaagent already present, skipping"
  exit 0
fi

mkdir -p monitoring/jmx
echo "  downloading jmx_prometheus_javaagent ${VERSION}"
curl -sS -o "$JAR" \
  "https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/${VERSION}/jmx_prometheus_javaagent-${VERSION}.jar"
echo "  done: $JAR"
