from merge_to_iceberg import latest_change_per_key


def test_latest_change_per_key_keeps_newest_change(spark):
    df = spark.createDataFrame([
        ("u1", "Alice", "c", 100, 1),
        ("u1", "Alice Updated", "u", 200, 2),
        ("u2", "Bob", "c", 150, 3),
        ("u2", None, "d", 300, 4),
    ], ["user_id", "full_name", "cdc_op", "cdc_ts_ms", "kafka_offset"])

    rows = latest_change_per_key(df, "user_id").orderBy("user_id").collect()

    assert [(r.user_id, r.full_name, r.cdc_op) for r in rows] == [("u1", "Alice Updated", "u"), ("u2", None, "d")]


def test_latest_change_per_key_breaks_same_millisecond_ties_by_offset(spark):
    df = spark.createDataFrame([
        ("u1", "second", "u", 100, 6),
        ("u1", "first", "u", 100, 5),
    ], ["user_id", "full_name", "cdc_op", "cdc_ts_ms", "kafka_offset"])

    rows = latest_change_per_key(df, "user_id").collect()

    assert [r.full_name for r in rows] == ["second"]
