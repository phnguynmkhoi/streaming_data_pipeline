import base64
import json

import pytest
from pyspark.sql.avro.functions import to_avro
from pyspark.sql.functions import col, struct
from pyspark.sql.types import BinaryType, LongType, StringType, StructField, StructType

from helper import add_date_column, cdc_changes, parse_cdc_stream, to_kafka_kv

# Minimal stand-in for a Debezium Avro CDC envelope, keeping only the fields
# the pipeline reads: before/after row images, op, and source.ts_ms.
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
        {"name": "before", "type": ["null", VALUE_AVRO_SCHEMA], "default": None},
        {"name": "after", "type": ["null", "test.Value"], "default": None},
        {"name": "op", "type": "string"},
        {"name": "source", "type": {
            "type": "record", "name": "Source", "fields": [{"name": "ts_ms", "type": "long"}],
        }},
    ],
})

VALUE_STRUCT_TYPE = StructType([
    StructField("user_id", StringType(), True),
    StructField("full_name", StringType(), True),
])

ENVELOPE_STRUCT_TYPE = StructType([
    StructField("before", VALUE_STRUCT_TYPE, True),
    StructField("after", VALUE_STRUCT_TYPE, True),
    StructField("op", StringType(), False),
    StructField("source", StructType([StructField("ts_ms", LongType(), False)]), False),
])

KAFKA_ROW_TYPE = StructType([
    StructField("value", BinaryType(), True),
    StructField("offset", LongType(), False),
])

CONFLUENT_HEADER = b"\x00\x00\x00\x00\x01"  # magic byte + dummy 4-byte schema id -- stripped blindly, never validated


def _value_tuple(value):
    return None if value is None else tuple(value.get(f.name) for f in VALUE_STRUCT_TYPE)


def encode_envelope(spark, after=None, before=None, op="c", ts_ms=1):
    """Confluent-wire-format Avro bytes for an envelope matching ENVELOPE_AVRO_SCHEMA."""
    df = spark.createDataFrame(
        [(_value_tuple(before), _value_tuple(after), op, (ts_ms,))],
        ENVELOPE_STRUCT_TYPE,
    )
    body = df.select(to_avro(struct(*df.columns), ENVELOPE_AVRO_SCHEMA).alias("bytes"))\
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


def test_parse_cdc_stream_drops_delete_events(spark):
    # after is Avro-null for DELETE events -- these must be dropped
    # entirely, not routed to either output (see PLAN.md 1.4).
    value = encode_envelope(spark, before={"user_id": "u1", "full_name": "Alice"}, op="d")
    df = spark.createDataFrame([(value,)], ["value"])

    good_df, bad_df = parse_cdc_stream(df, ENVELOPE_AVRO_SCHEMA, "users", "user_id")

    assert good_df.count() == 0
    assert bad_df.count() == 0


def test_cdc_changes_keeps_upserts_from_after(spark):
    value = encode_envelope(spark, after={"user_id": "u1", "full_name": "Alice"}, op="u", ts_ms=42)
    df = spark.createDataFrame([(value, 7)], KAFKA_ROW_TYPE)

    rows = cdc_changes(df, ENVELOPE_AVRO_SCHEMA, "user_id").collect()

    assert [r.asDict() for r in rows] == [
        {"user_id": "u1", "full_name": "Alice", "cdc_op": "u", "cdc_ts_ms": 42, "kafka_offset": 7},
    ]


def test_cdc_changes_takes_delete_row_image_from_before(spark):
    value = encode_envelope(spark, before={"user_id": "u1", "full_name": None}, op="d", ts_ms=43)
    df = spark.createDataFrame([(value, 8)], KAFKA_ROW_TYPE)

    rows = cdc_changes(df, ENVELOPE_AVRO_SCHEMA, "user_id").collect()

    assert [(r.user_id, r.cdc_op, r.cdc_ts_ms) for r in rows] == [("u1", "d", 43)]


def test_cdc_changes_drops_kafka_tombstones_and_null_keys(spark):
    null_key = encode_envelope(spark, after={"user_id": None, "full_name": "Bob"})
    df = spark.createDataFrame([(None, 9), (null_key, 10)], KAFKA_ROW_TYPE)

    assert cdc_changes(df, ENVELOPE_AVRO_SCHEMA, "user_id").count() == 0


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
