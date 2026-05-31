# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Assistant Rules

- Never read `.env` files.
- Every response must begin with "Khoi".
- `PLAN.md` is the enhancement roadmap and progress tracker. After implementing any item from it, update `PLAN.md` in the same change: flip the item's status marker (🔲 Todo → ✅ Done) in both its section heading and the Summary Table, and note what was done. Keep the phase-level status line accurate (e.g. "Partially complete"). If an implementation diverges from the plan, revise the relevant item to match what was actually built.

## Architecture

Real-time e-commerce data warehouse using CDC (Change Data Capture). Data flows:

```
PostgreSQL → Debezium → Kafka (CDC topics) → Spark Streaming → MinIO (Parquet) + Kafka (clean topics) → Apache Pinot (OLAP)
```

- **`src/main.py`**: Generates synthetic e-commerce data (users, products, payments, transactions) via Faker and inserts into PostgreSQL, which triggers Debezium CDC.
- **`apps/extract_data.py`**: The Spark streaming job. Reads from Debezium CDC Kafka topics, extracts the `after` field from the Debezium JSON envelope, adds a `date` column, then fans out to two sinks: MinIO (`s3a://transactions/{entity}/`) and new clean Kafka topics (`streaming_{entity}`).
- **Pinot** consumes the clean Kafka topics (`streaming_*`) for real-time OLAP queries.

Kafka topic naming convention:
- CDC topics (from Debezium): `transactions_streaming.public.<table_name>`
- Clean topics (from Spark): `streaming_<entity_name>`

## Setup & Startup Sequence

### Prerequisites
- Docker Compose
- JAR files for Spark S3A/MinIO support — must be placed in `jars/` before building:
  - `aws-java-sdk-bundle-1.11.375.jar`
  - `hadoop-aws-3.2.0.jar`

### Full startup (run in order)

```bash
# 1. Start all services
docker compose up -d

# 2. Register Debezium connector with Kafka Connect
bash script/script.sh

# 3. Generate initial data into PostgreSQL (triggers CDC)
python src/main.py

# 4. Create Pinot schemas and realtime tables
bash script/create_all_schema.sh
bash script/create_all_table.sh

# 5. Submit Spark streaming job to cluster
bash script/spark_extract_data_script.sh
```

PostgreSQL initializes automatically with `wal_level=logical` (required for Debezium) and `REPLICA IDENTITY FULL` on all tables (required for UPDATE/DELETE capture).

## Service Endpoints

| Service | URL |
|---------|-----|
| Kafka Control Center | http://localhost:9021 |
| Debezium UI | http://localhost:8080 |
| Debezium REST API | http://localhost:8093 |
| Spark Master UI | http://localhost:9090 |
| MinIO Console | http://localhost:10001 |
| Pinot Controller + Query UI | http://localhost:9000 |

## Key Operational Commands

```bash
# Check Debezium connector status
curl http://localhost:8093/connectors

# List Kafka topics
docker exec broker kafka-topics --list --bootstrap-server localhost:29092

# Verify PostgreSQL WAL level
docker exec postgres psql -U postgres -c "SHOW wal_level;"

# Tail a service's logs
docker compose logs -f <service-name>

# Query Pinot
# Use the SQL editor at http://localhost:9000
```

## Non-Obvious Pitfalls

- **Pinot port conflict**: Pinot Controller runs on port 9000, which is also MinIO's internal API port. MinIO's *external* ports are 10000 (API) and 10001 (console) — see `docker-compose.yml`.
- **MinIO credentials** are hardcoded in `apps/extract_data.py` (development only). The MinIO access key and secret key must match what's configured in the MinIO service in `docker-compose.yml`.
- **Spark S3A checkpoints** are stored in MinIO at `s3a://checkpoints/`. If a Spark job fails and restarts, it resumes from the checkpoint. Delete the checkpoint path in MinIO to restart from the beginning.
- **Pinot upsert mode**: Transaction tables use `FULL` upsert mode (see `pinot/transaction_table.json`) so UPDATE and DELETE CDC events are reflected in query results.
- Pinot schemas and tables are created separately — schemas must exist before tables (`create_all_schema.sh` before `create_all_table.sh`).
