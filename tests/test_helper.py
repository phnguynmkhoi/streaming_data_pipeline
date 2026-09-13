import base64
import json

import pytest
from pyspark.sql import Row
from pyspark.sql.avro.functions import to_avro
from pyspark.sql.functions import col, struct
from pyspark.sql.types import StringType, StructField, StructType

from helper import add_date_column, parse_cdc_stream, to_kafka_kv

# Minimal stand-in for a Debezium Avro CDC envelope: a record with a single
# `after` field, nullable (null for DELETE tombstones), itself a nullable
# record of the entity's columns. Real envelopes carry more fields
# (before/source/op/ts_ms/...), but parse_cdc_stream only reads `after`.
VALUE_AVRO_SCHEMA = {
    "type": "record",
    "name": "Value",
    "namespace": "test",
    "fields": [
        {"name": "user_id", "type": ["null", "string"], "default": None},
        {"name": "full_name", "type": ["null", "string"], "default": None},
    ],
}

ENVELOPE_AVRO_SCHEMA = json.dumps({
    "type": "record",
    "name": "Envelope",
    "namespace": "test",
    "fields": [
        {"name": "after", "type": ["null", VALUE_AVRO_SCHEMA], "default": None},
    ],
})

VALUE_STRUCT_TYPE = StructType([
    StructField("user_id", StringType(), True),
    StructField("full_name", StringType(), True),
])

CONFLUENT_HEADER = b"\x00\x00\x00\x00\x01"  # magic byte + dummy 4-byte schema id -- parse_cdc_stream strips these blindly, it never validates the id


def encode_envelope(spark, after_value):
    """Build Confluent-wire-format Avro bytes for a Debezium-style envelope
    matching ENVELOPE_AVRO_SCHEMA. `after_value` is a dict of field values,
    or None for a DELETE tombstone.
    """
    after_row = Row(**after_value) if after_value is not None else None
    df = spark.createDataFrame(
        [Row(after=after_row)],
        StructType([StructField("after", VALUE_STRUCT_TYPE, True)]),
    )
    body = df.select(to_avro(struct(col("after")), ENVELOPE_AVRO_SCHEMA).alias("bytes"))\
        .collect()[0]["bytes"]
    return CONFLUENT_HEADER + body


def test_parse_cdc_stream_good_row_goes_to_good_df(spark):
    value = encode_envelope(spark, {"user_id": "u1", "full_name": "Alice"})
    df = spark.createDataFrame([(value,)], ["value"])

    good_df, bad_df = parse_cdc_stream(df, ENVELOPE_AVRO_SCHEMA, "users", "user_id")

    assert bad_df.count() == 0
    rows = good_df.collect()
    assert len(rows) == 1
    assert rows[0]["user_id"] == "u1"
    assert rows[0]["full_name"] == "Alice"


def test_parse_cdc_stream_schema_drift_missing_pk_goes_to_bad_df(spark):
    # user_id is null on this row even though the record decoded fine --
    # the case a plain "decode succeeded" check would miss.
    value = encode_envelope(spark, {"user_id": None, "full_name": "Bob"})
    df = spark.createDataFrame([(value,)], ["value"])

    good_df, bad_df = parse_cdc_stream(df, ENVELOPE_AVRO_SCHEMA, "users", "user_id")

    assert good_df.count() == 0
    rows = bad_df.collect()
    assert len(rows) == 1
    assert rows[0]["entity"] == "users"
    # raw_value is base64-encoded in bad_df (see parse_cdc_stream) since the
    # DLQ's JSON sink can't write raw binary columns.
    assert rows[0]["raw_value"] == base64.b64encode(value).decode()


def test_parse_cdc_stream_decode_failure_raises(spark):
    # Not valid Avro against ENVELOPE_AVRO_SCHEMA at all -- simulates an
    # incompatible schema change decoded with a stale cached schema.
    # from_avro's default FAILFAST mode raises rather than returning null;
    # in production this is caught by extract_data.py's per-entity
    # supervisor, not routed to the DLQ (see PLAN.md 3.2).
    garbage = b"\xff\xff\xff\xff\xff\xff\xff\xff"
    df = spark.createDataFrame([(garbage,)], ["value"])

    good_df, bad_df = parse_cdc_stream(df, ENVELOPE_AVRO_SCHEMA, "users", "user_id")

    with pytest.raises(Exception):
        bad_df.collect()


def test_parse_cdc_stream_drops_delete_tombstones(spark):
    # after is Avro-null for DELETE events -- these must be dropped
    # entirely, not routed to either output (see PLAN.md 1.4).
    value = encode_envelope(spark, None)
    df = spark.createDataFrame([(value,)], ["value"])

    good_df, bad_df = parse_cdc_stream(df, ENVELOPE_AVRO_SCHEMA, "users", "user_id")

    assert good_df.count() == 0
    assert bad_df.count() == 0


def test_add_date_column_parses_microsecond_timestamp(spark):
    df = spark.createDataFrame([("2024-01-15 10:30:45.123456",)], ["last_modified_ts"])

    result = add_date_column(df)

    assert str(result.collect()[0]["date"]) == "2024-01-15"


def test_add_date_column_is_null_for_unparseable_timestamp(spark):
    df = spark.createDataFrame([("not-a-timestamp",)], ["last_modified_ts"])

    result = add_date_column(df)

    assert result.collect()[0]["date"] is None


def test_to_kafka_kv_shapes_key_and_value(spark):
    df = spark.createDataFrame([("u1", "Alice")], ["user_id", "full_name"])

    result = to_kafka_kv(df, "user_id")

    assert result.columns == ["key", "value"]
    row = result.collect()[0]
    assert row["key"] == "u1"
    assert json.loads(row["value"]) == {"user_id": "u1", "full_name": "Alice"}
