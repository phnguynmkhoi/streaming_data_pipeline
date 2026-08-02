from pyspark.sql.types import StructField,IntegerType,StringType,StructType,FloatType

transaction_schema = StructType([
    StructField("transaction_id",StringType()),
    StructField("user_id",StringType()),
    StructField("product_id",StringType()),
    StructField("payment_id",StringType()),
    StructField("shipping_id",StringType()),
    StructField("quantity",IntegerType()),
    StructField("discount",IntegerType()),
    StructField("last_modified_ts",StringType()),
    StructField("status",StringType()),
])

user_schema = StructType([
    StructField("user_id",StringType()),
    StructField("full_name",StringType()),
    StructField("phone_number",StringType()),
    StructField("sex",StringType()),
    StructField("address",StringType()),
    StructField("birthdate",StringType()),
    StructField("email",StringType()),
    StructField("job",StringType()),
    StructField("last_modified_ts",StringType()),
    StructField("status", StringType())
])

product_schema = StructType([
    StructField("product_id",StringType()),
    StructField("product_name",StringType()),
    StructField("category",StringType()),
    StructField("unit_price",FloatType()),
    StructField("merchant_name",StringType()),
    StructField("rating", FloatType()),
    StructField("last_modified_ts",StringType()),
    StructField("status",StringType())
])

payment_schema = StructType([
    StructField("payment_id",StringType()),
    StructField("payment_method",StringType()),
    StructField("currency",StringType()),
    StructField("last_modified_ts",StringType()),
    StructField("status", StringType())
])

shipping_schema = StructType([
    StructField("shipping_id",StringType()),
    StructField("shipping_address",StringType()),
    StructField("shipping_cost",FloatType()),
    StructField("shipping_status",StringType()),
    StructField("status",StringType()),
    StructField("last_modified_ts",StringType()),
])

streaming_schema = StructType([
    StructField("payload", StructType([
        StructField("after",StringType()),
    ]))
])
