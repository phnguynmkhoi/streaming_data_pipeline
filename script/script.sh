#!/bin/bash
# Registers the Debezium connector. Also (idempotently) pre-creates the CDC
# and clean Kafka topics with explicit retention, instead of letting
# KAFKA_AUTO_CREATE_TOPICS_ENABLE create them on first write with the
# broker's default (~7 day) retention (PLAN.md 2.4). Kafka retention here
# only bounds how far back a consumer can replay from "earliest" — it
# doesn't delete anything from Postgres (the source of truth), so 3 days is
# applied uniformly to every topic; replayability beyond that is preserved
# by the raw Parquet staging archive (see PLAN.md 4.3 step 1).
set -u

RETENTION_MS=259200000  # 3 days

topics=(
  transactions_streaming.public.users
  transactions_streaming.public.products
  transactions_streaming.public.payments
  transactions_streaming.public.shippings
  transactions_streaming.public.transactions
  streaming_users
  streaming_products
  streaming_payments
  streaming_shippings
  streaming_transactions
)

for topic in "${topics[@]}"; do
  docker exec broker kafka-topics --create --if-not-exists \
    --topic "$topic" \
    --bootstrap-server localhost:29092 \
    --partitions 1 \
    --replication-factor 1 \
    --config "retention.ms=$RETENTION_MS"
done

curl -X POST -H "Content-Type: application/json" \
    --data @debezium-connector-postgres.json \
    http://localhost:8093/connectors
