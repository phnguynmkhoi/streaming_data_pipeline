from schema import (
    payment_schema,
    product_schema,
    shipping_schema,
    streaming_schema,
    transaction_schema,
    user_schema,
)


# Regression guard: extract_data.py's read_kafka_stream() calls are keyed to
# these exact field names/pks (e.g. "user_id", "transaction_id"). A silent
# rename here would break Pinot ingestion without any other test catching it.

def test_transaction_schema_fields():
    assert transaction_schema.fieldNames() == [
        "transaction_id", "user_id", "product_id", "payment_id", "shipping_id",
        "quantity", "discount", "last_modified_ts", "status",
    ]


def test_user_schema_fields():
    assert user_schema.fieldNames() == [
        "user_id", "full_name", "phone_number", "sex", "address", "birthdate",
        "email", "job", "last_modified_ts", "status",
    ]


def test_product_schema_fields():
    assert product_schema.fieldNames() == [
        "product_id", "product_name", "category", "unit_price", "merchant_name",
        "rating", "last_modified_ts", "status",
    ]


def test_payment_schema_fields():
    assert payment_schema.fieldNames() == [
        "payment_id", "payment_method", "currency", "last_modified_ts", "status",
    ]


def test_shipping_schema_fields():
    assert shipping_schema.fieldNames() == [
        "shipping_id", "shipping_address", "shipping_cost", "shipping_status",
        "status", "last_modified_ts",
    ]


def test_streaming_schema_wraps_payload_after():
    assert streaming_schema["payload"].dataType.fieldNames() == ["after"]
