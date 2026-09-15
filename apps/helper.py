from pyspark.sql.avro.functions import from_avro
from pyspark.sql.functions import base64, col, current_date, expr, lit, to_date, to_timestamp, when

KAFKA_BOOTSTRAP_SERVERS = "broker:29092"
LAST_MODIFIED_TS_FORMAT = "yyyy-MM-dd HH:mm:ss.SSSSSS"

ENTITIES = [
    ("users", "user_id"),
    ("products", "product_id"),
    ("payments", "payment_id"),
    ("transactions", "transaction_id"),
    ("shippings", "shipping_id"),
]

# Kafka's Confluent wire format prefixes every Avro message with a 5-byte
# header (1-byte magic + 4-byte schema ID) before the Avro body. That header
# is stripped before decoding -- see schema_registry.py for why the schema
# itself is fetched once at startup rather than resolved per-record from it.
CONFLUENT_WIRE_HEADER_BYTES = 5


# ---------------------------------------------------------------------------
# Pure transformation functions: take/return DataFrames only, no I/O.
# These work identically on streaming and static (batch) DataFrames, which is
# what makes them unit-testable with a local SparkSession — see tests/.
# ---------------------------------------------------------------------------

def decode_envelope(avro_schema_json):
    """Column expression decoding a raw Kafka `value` into Debezium's Avro
    envelope. Null for Kafka tombstones (null value)."""
    avro_body = expr(f"substring(value, {CONFLUENT_WIRE_HEADER_BYTES + 1}, length(value))")
    return from_avro(avro_body, avro_schema_json)


def cdc_changes(df, avro_schema_json, pk):
    """Flatten Debezium change events for the staging archive that feeds the
    nightly Iceberg MERGE (PLAN.md 4.3).

    Unlike parse_cdc_stream (which feeds Kafka/Pinot and drops deletes), this
    keeps DELETEs: Debezium's `after` is null for a delete, so the row image
    comes from `before`. Each row carries `cdc_op` (c/u/d/r), `cdc_ts_ms`
    (source commit time, used to order changes) and `kafka_offset` (tiebreak
    within the same millisecond). Kafka tombstones and rows with a null
    primary key are dropped -- the latter already go to the DLQ.
    """
    events = df.select(
        decode_envelope(avro_schema_json).alias("e"),
        col("offset").alias("kafka_offset"),
    ).filter(col("e").isNotNull())

    row = when(col("e.op") == "d", col("e.before")).otherwise(col("e.after"))

    return events.select(
        row.alias("row"),
        col("e.op").alias("cdc_op"),
        col("e.source.ts_ms").alias("cdc_ts_ms"),
        col("kafka_offset"),
    ).filter(col(f"row.{pk}").isNotNull())\
        .select("row.*", "cdc_op", "cdc_ts_ms", "kafka_offset")


def parse_cdc_stream(df, avro_schema_json, name, pk):
    """Decode Debezium's Avro CDC envelope out of a raw (binary) Kafka
    `value` column.

    A row that fails to decode entirely (e.g. an incompatible schema change
    since avro_schema_json was fetched at job startup) is NOT routed to
    bad_df here -- from_avro runs in its default FAILFAST mode, so a
    genuinely corrupt/incompatible record raises rather than returning null,
    failing this entity's streaming queries outright. That's deliberate: per
    PLAN.md 3.2, hard schema drift is meant to fail loud (caught and logged
    by extract_data.py's per-entity supervisor) rather than be silently
    absorbed into the DLQ. A compatible/additive schema change (e.g. a new
    field) still decodes fine against the stale schema -- it just won't
    surface the new field until the job restarts and re-fetches.

    Splits successfully-decoded rows into (good_df, bad_df):
    - `after` null (e.g. DELETE tombstones) is dropped entirely — never
      routed to either output.
    - `after.<pk>` null (schema drift landed on the primary key, but the
      record still decoded) goes to bad_df as (raw_value, entity).
    - Everything else is flattened to its columns in good_df.
    """
    after_df = df.select(
        col("value").alias("raw_value"),
        decode_envelope(avro_schema_json)["after"].alias("after"),
    ).filter(col("after").isNotNull())

    is_bad = col(f"after.{pk}").isNull()

    # raw_value is binary (the undecoded Avro body); base64-encode it so the
    # DLQ's JSON sink can actually write it (Spark's JSON writer doesn't
    # accept BinaryType columns as-is).
    bad_df = after_df.filter(is_bad)\
        .select(base64(col("raw_value")).alias("raw_value"), lit(name).alias("entity"))
    good_df = after_df.filter(~is_bad).selectExpr("after.*")

    return good_df, bad_df


def add_date_column(df, ts_col="last_modified_ts", ts_format=LAST_MODIFIED_TS_FORMAT):
    """Derive a `date` column from a string timestamp column."""
    return df.withColumn("date", to_date(to_timestamp(col(ts_col), ts_format)))


def to_kafka_kv(df, pk):
    """Shape a DataFrame into the key/value columns the Kafka sink expects.

    Keying by the primary key is required for Pinot FULL upsert correctness
    once a topic has more than one partition (see PLAN.md 1.7).
    """
    return df.selectExpr(f"CAST({pk} AS STRING) AS key", "to_json(struct(*)) AS value")


# ---------------------------------------------------------------------------
# I/O wrappers: thin glue between the pure functions above and Spark
# Structured Streaming sources/sinks. Not covered by unit tests — they need a
# running Kafka/MinIO, which is an integration-test concern (PLAN.md 6.x).
# ---------------------------------------------------------------------------

def write_to_staging(df, name):
    # Partitioned by processing date, not event date: a change that arrives
    # late (e.g. the job was down over midnight) lands in today's partition
    # and still gets merged tomorrow, instead of into a date already merged.
    return df.withColumn("date", current_date())\
            .writeStream\
            .queryName(f"staging_{name}")\
            .format("parquet")\
            .partitionBy("date")\
            .option("path", f"s3a://staging/{name}")\
            .option("checkpointLocation", f"s3a://checkpoints/staging/{name}")\
            .start()


def write_to_kafka(df, name, pk):
    return to_kafka_kv(df, pk)\
            .writeStream\
            .queryName(f"kafka_{name}")\
            .format("kafka")\
            .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
            .option("topic", f"streaming_{name}") \
            .option("checkpointLocation", f"s3a://checkpoints/kafka/{name}")\
            .start()


def write_to_dlq(df, name):
    return df.writeStream\
            .queryName(f"dlq_{name}")\
            .format("json")\
            .option("path", f"s3a://dlq/{name}")\
            .option("checkpointLocation", f"s3a://checkpoints/dlq/{name}")\
            .start()


def read_kafka_stream(spark, name):
    # value stays binary (Avro-encoded) -- casting it to STRING corrupts the bytes.
    return spark.readStream\
        .format("kafka")\
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", f"transactions_streaming.public.{name}") \
        .option("startingOffsets", "earliest") \
        .load()\
        .select("value", "offset")
