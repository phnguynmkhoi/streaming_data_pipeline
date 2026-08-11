import json

from helper import add_date_column, parse_cdc_stream, to_kafka_kv
from schema import streaming_schema, user_schema


def envelope(after):
    """Build a Debezium-style CDC envelope JSON string like Kafka would carry."""
    return json.dumps({"payload": {"after": after}})


def test_parse_cdc_stream_good_row_goes_to_good_df(spark):
    after = json.dumps({
        "user_id": "u1",
        "full_name": "Alice",
        "phone_number": "555-0100",
        "sex": "F",
        "address": "1 Main St",
        "birthdate": "1990-01-01",
        "email": "alice@example.com",
        "job": "engineer",
        "last_modified_ts": "2024-01-15 10:30:45.123456",
        "status": "active",
    })
    df = spark.createDataFrame([(envelope(after),)], ["value"])

    good_df, bad_df = parse_cdc_stream(df, streaming_schema, user_schema, "users", "user_id")

    assert bad_df.count() == 0
    rows = good_df.collect()
    assert len(rows) == 1
    assert rows[0]["user_id"] == "u1"
    assert rows[0]["email"] == "alice@example.com"


def test_parse_cdc_stream_schema_drift_missing_pk_goes_to_bad_df(spark):
    # "user_id" dropped/renamed upstream, but the rest of the JSON still
    # parses fine -- this is the case a plain `data IS NULL` check would miss.
    drifted_after = json.dumps({
        "full_name": "Bob",
        "last_modified_ts": "2024-01-15 10:30:45.123456",
        "status": "active",
    })
    df = spark.createDataFrame([(envelope(drifted_after),)], ["value"])

    good_df, bad_df = parse_cdc_stream(df, streaming_schema, user_schema, "users", "user_id")

    assert good_df.count() == 0
    rows = bad_df.collect()
    assert len(rows) == 1
    assert rows[0]["entity"] == "users"
    assert rows[0]["raw_value"] == drifted_after


def test_parse_cdc_stream_unparseable_json_goes_to_bad_df(spark):
    df = spark.createDataFrame([(envelope("{not valid json"),)], ["value"])

    good_df, bad_df = parse_cdc_stream(df, streaming_schema, user_schema, "users", "user_id")

    assert good_df.count() == 0
    rows = bad_df.collect()
    assert len(rows) == 1
    assert rows[0]["raw_value"] == "{not valid json"


def test_parse_cdc_stream_drops_delete_tombstones(spark):
    # payload.after is JSON null for DELETE events -- these must be dropped
    # entirely, not routed to either output (see PLAN.md 1.4).
    df = spark.createDataFrame([(envelope(None),)], ["value"])

    good_df, bad_df = parse_cdc_stream(df, streaming_schema, user_schema, "users", "user_id")

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
