import json
import logging
import threading
import time

from pyspark.sql import SparkSession

from credential import MINIO_ACCESS_KEY, MINIO_SECRET_KEY
from schema_registry import fetch_latest_schema
from helper import (
    ENTITIES,
    add_date_column,
    cdc_changes,
    parse_cdc_stream,
    read_kafka_stream,
    write_to_dlq,
    write_to_kafka,
    write_to_staging,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("streaming_pipeline")

POLL_INTERVAL_SECONDS = 5


def log_query_started(query):
    logger.info(json.dumps({"event": "started", "query": query.name, "id": query.id}))


def supervise_entity(name, queries):
    """Poll one entity's streaming queries (kafka/staging/dlq) for progress and
    failures, isolated from the other 4 entities -- so a decode failure on
    this entity's topic (e.g. an Avro schema-drift mismatch, PLAN.md 3.2)
    doesn't take down the other 4. Before this, all 15 queries shared one
    spark.streams.awaitAnyTermination() (PLAN.md 1.1), so any one query
    dying killed the whole job.

    Polling `.lastProgress`/`.exception()` (both plain Python-native
    StreamingQuery APIs, unrelated to the listener) rather than
    StreamingQueryListener: pyspark.sql.streaming.StreamingQueryListener
    (the native Python listener API) only exists from Spark 3.4 onward --
    this project pins Spark 3.1.3. A Py4J Java-interface bridge (the usual
    pre-3.4 workaround) was tried and doesn't work either:
    org.apache.spark.sql.streaming.StreamingQueryListener is a Scala
    *abstract class*, not an interface/trait, and Py4J's Python Proxy
    mechanism can only implement Java interfaces -- confirmed via
    `py4j.Py4JException: ... is not an interface and cannot be used as a
    Python Proxy` when actually run (PLAN.md 2.5).

    If any of this entity's queries dies with an exception, the other
    queries for the same entity are stopped too (so the entity fails as a
    consistent unit) and the failure is logged. Queries for every other
    entity keep running untouched.
    """
    last_batch_id = {q.name: None for q in queries}

    while any(q.isActive for q in queries):
        for q in queries:
            if not q.isActive:
                continue

            exception = q.exception()
            if exception is not None:
                logger.error(json.dumps({
                    "event": "entity_failed",
                    "entity": name,
                    "query": q.name,
                    "exception": str(exception),
                }))
                for other in queries:
                    if other.isActive:
                        other.stop()
                return

            progress = q.lastProgress
            if progress and progress.get("batchId") != last_batch_id[q.name]:
                last_batch_id[q.name] = progress.get("batchId")
                logger.info(json.dumps({
                    "event": "progress",
                    "query": progress.get("name"),
                    "batch_id": progress.get("batchId"),
                    "input_rows": progress.get("numInputRows"),
                    "rows_per_sec": progress.get("processedRowsPerSecond"),
                    "batch_duration_ms": (progress.get("durationMs") or {}).get("triggerExecution"),
                    "watermark": (progress.get("eventTime") or {}).get("watermark"),
                }))

        time.sleep(POLL_INTERVAL_SECONDS)


spark = SparkSession\
        .builder\
        .appName("transactions_streaming")\
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")\
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .getOrCreate()

entity_threads = []
for name, pk in ENTITIES:
    avro_schema_json = fetch_latest_schema(f"transactions_streaming.public.{name}")
    raw_df = read_kafka_stream(spark, name)
    good_df, bad_df = parse_cdc_stream(raw_df, avro_schema_json, name, pk)

    queries = [
        write_to_kafka(add_date_column(good_df), name, pk),
        write_to_staging(cdc_changes(raw_df, avro_schema_json, pk), name),
        write_to_dlq(bad_df, name),
    ]
    for q in queries:
        log_query_started(q)

    t = threading.Thread(target=supervise_entity, args=(name, queries))
    t.start()
    entity_threads.append(t)

for t in entity_threads:
    t.join()
