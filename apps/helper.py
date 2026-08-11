from pyspark.sql.functions import col, from_json, lit, to_date, to_timestamp

KAFKA_BOOTSTRAP_SERVERS = "broker:29092"
LAST_MODIFIED_TS_FORMAT = "yyyy-MM-dd HH:mm:ss.SSSSSS"


# ---------------------------------------------------------------------------
# Pure transformation functions: take/return DataFrames only, no I/O.
# These work identically on streaming and static (batch) DataFrames, which is
# what makes them unit-testable with a local SparkSession — see tests/.
# ---------------------------------------------------------------------------

def parse_cdc_stream(df, streaming_schema, schema, name, pk):
    """Parse Debezium's CDC JSON envelope out of a raw Kafka `value` column.

    Splits rows into (good_df, bad_df):
    - Rows where the envelope's `payload.after` is null (e.g. DELETE
      tombstones) are dropped entirely — never routed to either output.
    - Rows where `after` is unparseable JSON, or parses but is missing the
      primary key (schema drift), go to bad_df as (raw_value, entity).
    - Everything else is flattened to its columns in good_df.
    """
    after_df = df\
        .select(from_json(col("value"), streaming_schema).alias("value"))\
        .select("value.payload.after")\
        .filter(col("after").isNotNull())\
        .select(col("after"), from_json(col("after"), schema).alias("data"))

    # data is null when the JSON itself is unparseable; data.<pk> is null when
    # a column was dropped/renamed upstream (schema drift) but the JSON still parses
    is_bad = col("data").isNull() | col(f"data.{pk}").isNull()

    bad_df = after_df.filter(is_bad)\
        .select(col("after").alias("raw_value"), lit(name).alias("entity"))

    good_df = after_df.filter(~is_bad).selectExpr("data.*")

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

def write_data_to_minio(df, datamart):
    return df.writeStream\
            .queryName(f"minio_{datamart}")\
            .format("parquet")\
            .option("path",f"s3a://transactions/{datamart}")\
            .option("checkpointLocation",f"s3a://checkpoints/{datamart}")\
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


def read_kafka_stream(spark, streaming_schema, schema, name, pk):
    raw_df = spark.readStream\
        .format("kafka")\
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", f"transactions_streaming.public.{name}") \
        .option("startingOffsets", "earliest") \
        .load()\
        .selectExpr("CAST(value AS STRING) as value")

    return parse_cdc_stream(raw_df, streaming_schema, schema, name, pk)
