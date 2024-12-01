from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when,udf, lit, from_json, to_timestamp, to_date, struct, to_json
from pyspark.sql.types import StructField,IntegerType,StringType,StructType,FloatType
import datetime
import uuid

today = datetime.datetime.now().strftime("%y%m%d")

# def get_full_datamart(datamart, schema):
#     try:
#         df = spark.read.parquet(f"s3a://transactions/{today}/{datamart}")
#     except:
#         df = spark.createDataFrame([],schema=schema)
#     return df

# @udf(StringType())
# def generate_uuid():
#     return str(uuid.uuid4())

# def insert_new_data_into_datamart(new_data_df, datamart, schema, table_id_name):
#     field = field=[field.name for field in schema.fields]
#     field = field.remove(table_id_name)
#     current_data_mart_df = get_full_datamart(datamart,schema)

#     new_data_df = new_data_df.withColumn(table_id_name, lit(None).cast(StringType()))

#     updated_data_df = current_data_mart_df.unionByName(new_data_df)

#     updated_data_df = updated_data_df.withColumn(table_id_name,
#                                                  when(col(table_id_name).isNull(), generate_uuid()).otherwise(col(table_id_name))
#                                                  )
#     return updated_data_df

def write_data_to_minio(df, datamart):
    return df.writeStream\
            .format("parquet")\
            .option("path",f"s3a://transactions/{datamart}")\
            .option("checkpointLocation",f"s3a://checkpoints/{datamart}")\
            .start()

def write_to_kafka(df, name):
    return df\
            .selectExpr("to_json(struct(*)) AS value")\
            .writeStream\
            .format("kafka")\
            .option("kafka.bootstrap.servers", "broker:29092") \
            .option("topic", f"streaming_{name}") \
            .option("checkpointLocation", f"s3a://checkpoints/kafka/{name}")\
            .start()

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
        .config("spark.sql.catalogImplementation", "hive") \
        .config("hive.metastore.uris", "thrift://hive-metastore:9083") \
        .enableHiveSupport() \
        .getOrCreate()

streaming_schema = StructType([
    StructField("payload", StructType([
        StructField("after",StringType()),
    ]))
])

def read_kafka_stream(streaming_schema,schema,name):
    return spark.readStream\
        .format("kafka")\
        .option("kafka.bootstrap.servers", "broker:29092") \
        .option("subscribe", f"transactions_streaming.public.{name}") \
        .option("startingOffsets", "earliest") \
        .load()\
        .selectExpr("CAST(value AS STRING) as value")\
        .select(from_json(col("value"),streaming_schema).alias("value"))\
        .select("value.payload.after")\
        .select(from_json(col("after"),schema).alias("data"))\
        .selectExpr("data.*")

user_df = read_kafka_stream(streaming_schema,user_schema,"users")

product_df = read_kafka_stream(streaming_schema,product_schema,"products")

payment_df = read_kafka_stream(streaming_schema,payment_schema,"payments")

transaction_df = read_kafka_stream(streaming_schema,transaction_schema,"transactions")

shipping_df = read_kafka_stream(streaming_schema, shipping_schema,"shippings")

transaction_df = transaction_df.withColumn("date", to_date(col("last_modified_ts")))
user_df = user_df.withColumn("date", to_date(col("last_modified_ts")))
product_df = product_df.withColumn("date", to_date(col("last_modified_ts")))
payment_df = payment_df.withColumn("date", to_date(col("last_modified_ts")))
shipping_df = shipping_df.withColumn("date", to_date(col("last_modified_ts")))

query6 = write_to_kafka(user_df,"users")
query7 = write_to_kafka(product_df,"products")
query8 = write_to_kafka(payment_df,"payments")
query9 = write_to_kafka(transaction_df,"transactions")
query10 = write_to_kafka(shipping_df,"shippings")

query1 = write_data_to_minio(user_df,"users")
query2 = write_data_to_minio(product_df,"products")
query3 = write_data_to_minio(payment_df,"payments")
query4 = write_data_to_minio(transaction_df,"transactions")
query5 = write_data_to_minio(shipping_df,"shippings")

query5.awaitTermination()

query10.awaitTermination()