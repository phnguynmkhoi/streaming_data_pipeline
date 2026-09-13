#!/bin/bash
# Downloads Confluent's kafka-connect-avro-converter plugin (the Avro
# Converter itself plus its runtime deps: kafka-avro-serializer,
# kafka-schema-registry-client, etc.) as Confluent Hub's self-contained
# archive, and unpacks it into debezium-plugins/ so it can be bind-mounted
# into the debezium container's plugin path (PLAN.md 3.2). The
# debezium/connect image doesn't ship this converter by default -- only
# Debezium's own connector plugins.
# Safe to re-run: skips if already unpacked.
set -eu
cd "$(dirname "$0")/.."

VERSION="7.4.0"  # matches the confluentinc/cp-*:7.4.0 images already used in docker-compose.yml
PLUGIN_DIR="debezium-plugins/kafka-connect-avro-converter"
ARCHIVE_URL="https://hub-downloads.confluent.io/api/plugins/confluentinc/kafka-connect-avro-converter/versions/${VERSION}/confluentinc-kafka-connect-avro-converter-${VERSION}.zip"

if [ -d "$PLUGIN_DIR/lib" ] && [ -n "$(ls -A "$PLUGIN_DIR/lib" 2>/dev/null)" ]; then
  echo "  kafka-connect-avro-converter already present, skipping"
  exit 0
fi

mkdir -p debezium-plugins
tmpzip="$(mktemp)"
echo "  downloading kafka-connect-avro-converter ${VERSION}"
curl -sS -o "$tmpzip" "$ARCHIVE_URL"

tmpdir="$(mktemp -d)"
python3 -m zipfile -e "$tmpzip" "$tmpdir"

# The archive extracts to a single top-level dir; its lib/ holds most of the
# jars Kafka Connect's plugin scanner needs.
extracted_dir="$(find "$tmpdir" -maxdepth 1 -mindepth 1 -type d | head -n1)"
rm -rf "$PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR"
cp -r "$extracted_dir"/lib "$PLUGIN_DIR/lib"

# Confluent's own archive doesn't bundle Guava, even though
# kafka-schema-registry-client's CachedSchemaRegistryClient needs it at
# runtime (NoClassDefFoundError: com/google/common/base/Ticker) -- their own
# base images apparently provide it on a shared platform classpath, which
# the plain upstream debezium/connect image doesn't have. Version pinned
# from confluentinc/common's pom.xml (guava.version) at the matching 7.4.0 tag.
# failureaccess is a separate, required companion artifact since Guava 27+
# (InternalFutureFailureAccess moved out of the main guava jar) -- without
# it, produce calls fail per-record with ClassNotFoundException instead of
# failing the task outright, so it's easy to miss.
echo "  downloading guava + failureaccess (missing from the Confluent Hub archive)"
curl -sS -o "$PLUGIN_DIR/lib/guava-30.1.1-jre.jar" \
  "https://repo1.maven.org/maven2/com/google/guava/guava/30.1.1-jre/guava-30.1.1-jre.jar"
curl -sS -o "$PLUGIN_DIR/lib/failureaccess-1.0.1.jar" \
  "https://repo1.maven.org/maven2/com/google/guava/failureaccess/1.0.1/failureaccess-1.0.1.jar"

rm -rf "$tmpzip" "$tmpdir"
echo "  done: $PLUGIN_DIR/lib"
