from pyspark.sql.functions import col, from_json, lit


def write_data_to_minio(df, datamart):
    return df.writeStream\
            .format("parquet")\
            .option("path",f"s3a://transactions/{datamart}")\
            .option("checkpointLocation",f"s3a://checkpoints/{datamart}")\
            .start()


def write_to_kafka(df, name, pk):
    return df\
            .selectExpr(f"CAST({pk} AS STRING) AS key", "to_json(struct(*)) AS value")\
            .writeStream\
            .format("kafka")\
            .option("kafka.bootstrap.servers", "broker:29092") \
            .option("topic", f"streaming_{name}") \
            .option("checkpointLocation", f"s3a://checkpoints/kafka/{name}")\
            .start()


def write_to_dlq(df, name):
    return df.writeStream\
            .format("json")\
            .option("path", f"s3a://dlq/{name}")\
            .option("checkpointLocation", f"s3a://checkpoints/dlq/{name}")\
            .start()


def read_kafka_stream(spark, streaming_schema, schema, name, pk):
    raw_df = spark.readStream\
        .format("kafka")\
        .option("kafka.bootstrap.servers", "broker:29092") \
        .option("subscribe", f"transactions_streaming.public.{name}") \
        .option("startingOffsets", "earliest") \
        .load()\
        .selectExpr("CAST(value AS STRING) as value")\
        .select(from_json(col("value"),streaming_schema).alias("value"))\
        .select("value.payload.after")\
        .filter(col("after").isNotNull())\
        .select(col("after"), from_json(col("after"),schema).alias("data"))

    # data is null when the JSON itself is unparseable; data.<pk> is null when
    # a column was dropped/renamed upstream (schema drift) but the JSON still parses
    is_bad = col("data").isNull() | col(f"data.{pk}").isNull()

    bad_df = raw_df.filter(is_bad)\
        .select(col("after").alias("raw_value"), lit(name).alias("entity"))

    good_df = raw_df.filter(~is_bad).selectExpr("data.*")

    return good_df, bad_df
