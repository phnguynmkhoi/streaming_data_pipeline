from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructField,IntegerType,StringType,StructType,FloatType,TimestampType

data_schema = StructType([
    StructField("transaction_id",StringType()),
    StructField("name",StringType()),
    StructField("sex",StringType()),
    StructField("address",StringType()),
    StructField("phone_number",StringType()),
    StructField("birthdate",StringType()),
    StructField("email",StringType()),
    StructField("job",StringType()),
    StructField("product_name",StringType()),
    StructField("category",StringType()),
    StructField("unit_price",FloatType()),
    StructField("quantity",IntegerType()),
    StructField("merchant_name",StringType()),
    StructField("payment_method",StringType()),
    StructField("discount",IntegerType()),
    StructField("shipping_address",StringType()),
    StructField("shipping_cost",FloatType()),
    StructField("total",FloatType()),
    StructField("currency",StringType()),
    StructField("created_at",TimestampType())
])

MINIO_ACCESS_KEY = "vTx7ykoKSJj8lHRB8VUJ"
MINIO_SECRET_KEY = "tl6sujLw3xTY8IFUe5dsy44VDCXzMiosZHM4wEVa"
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

spark.sparkContext.setLogLevel("WARN")

df = spark.readStream\
    .format("kafka")\
    .option("kafka.bootstrap.servers", "broker:29092") \
    .option("subscribe", "transactions_streaming.public.ecommerce_transactions") \
    .option("startingOffsets", "earliest") \
    .load()

# value_df = df.selectExpr("CAST(value as STRING)")
    
    # Write to console
# query = df \
#     .writeStream \
#     .outputMode("append") \
#     .format("csv") \
#     .option("checkpointLocation", "/opt/spark/spark-apps/checkpoint")\
#     .option("path", "/opt/spark/spark-apps")\
#     .start()

# query.awaitTermination()

streaming_schema = StructType([
    StructField("payload", StructType([
        StructField("after",StringType()),
    ]))
])

df = df.selectExpr("CAST(value AS STRING) as value")\
        .select(from_json(col("value"),streaming_schema).alias("value"))\
        .select("value.payload.after")\
        .select(from_json(col("after"),data_schema).alias("data"))\
        .selectExpr("data.*")

test_query = df.writeStream\
            .format("csv")\
            .option("checkpointLocation", "file:///opt/spark/spark-apps/checkpoint") \
            .option("path", "file:///opt/spark/spark-apps/") \
            .outputMode("append") \
            .start()
# df.show()
# query = df.writeStream \
#     .format("parquet") \
#     .option("checkpointLocation", "s3a://transactions/checkpoints") \
#     .option("path", "s3a://transactions/data") \
#     .outputMode("append") \
#     .start()

test_query.awaitTermination()

