#!/bin/bash
# Builds the Scala streaming job (PLAN.md 5.3) in a Maven container, so no
# JVM or Maven is needed on the host. The jar lands in apps/, which every
# Spark container already mounts. The Maven cache is kept in a named volume
# so rebuilds are fast.
# Pass --skip-tests to build without running the ScalaTest suite.
set -eu
cd "$(dirname "$0")/.."

SKIP_TESTS=""
[ "${1:-}" = "--skip-tests" ] && SKIP_TESTS="-DskipTests -Dmaven.test.skip=true"

docker volume create scala-maven-cache >/dev/null

docker run --rm \
  -v "$PWD/scala-app":/app \
  -v scala-maven-cache:/root/.m2 \
  -w /app \
  maven:3.9-eclipse-temurin-11 \
  mvn -q -B $SKIP_TESTS package

jar="scala-app/target/pipeline-streaming-1.0.jar"
[ -f "$jar" ] || { echo "build produced no jar at $jar" >&2; exit 1; }
cp "$jar" apps/pipeline-streaming.jar
echo "  built: apps/pipeline-streaming.jar"
