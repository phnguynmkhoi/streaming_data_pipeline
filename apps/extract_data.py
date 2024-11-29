from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when,udf, lit, from_json, to_timestamp, to_date, struct, to_json
from pyspark.sql.types import StructField,IntegerType,StringType,StructType,FloatType
import datetime
import uuid

today = datetime.datetime.now().strftime("%y%m%d")

def get_full_datamart(datamart, schema):
    try:
        df = spark.read.parquet(f"s3a://transactions/{today}/{datamart}")
    except:
        df = spark.createDataFrame([],schema=schema)
    return df

@udf(StringType())
def generate_uuid():
    return str(uuid.uuid4())

def insert_new_data_into_datamart(new_data_df, datamart, schema, table_id_name):
    field = field=[field.name for field in schema.fields]
    field = field.remove(table_id_name)
    current_data_mart_df = get_full_datamart(datamart,schema)

    new_data_df = new_data_df.withColumn(table_id_name, lit(None).cast(StringType()))

    updated_data_df = current_data_mart_df.unionByName(new_data_df)

    updated_data_df = updated_data_df.withColumn(table_id_name,
                                                 when(col(table_id_name).isNull(), generate_uuid()).otherwise(col(table_id_name))
                                                 )
    return updated_data_df

def write_dim_data(df, datamart):
    return df.writeStream\
            .format("parquet")\
            .option("path",f"s3a://transactions/{datamart}")\
            .option("checkpointLocation",f"s3a://checkpoints/{datamart}")\
            .start()

transaction_schema = StructType([
    StructField("transaction_id",StringType()),
    StructField("user_id",StringType()),
    StructField("product_id",StringType()),
    StructField("payment_id",StringType()),
    StructField("quantity",IntegerType()),
    StructField("discount",IntegerType()),
    StructField("shipping_address",StringType()),
    StructField("shipping_cost",FloatType()),
    StructField("created_at",StringType()),
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
    StructField("status", StringType())
])

product_schema = StructType([
    StructField("product_id",StringType()),
    StructField("product_name",StringType()),
    StructField("category",StringType()),
    StructField("unit_price",FloatType()),
    StructField("merchant_name",StringType()),
    StructField("rating", FloatType()),
    StructField("status",StringType())
])

payment_schema = StructType([
    StructField("payment_id",StringType()),
    StructField("payment_method",StringType()),
    StructField("currency",StringType()),
    StructField("status", StringType())
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

user_df = spark.readStream\
    .format("kafka")\
    .option("kafka.bootstrap.servers", "broker:29092") \
    .option("subscribe", "transactions_streaming.public.users") \
    .option("startingOffsets", "earliest") \
    .load()\
    .selectExpr("CAST(value AS STRING) as value")\
    .select(from_json(col("value"),streaming_schema).alias("value"))\
    .select("value.payload.after")\
    .select(from_json(col("after"),user_schema).alias("data"))\
    .selectExpr("data.*")

product_df = spark.readStream\
    .format("kafka")\
    .option("kafka.bootstrap.servers", "broker:29092") \
    .option("subscribe", "transactions_streaming.public.products") \
    .option("startingOffsets", "earliest") \
    .load()\
    .selectExpr("CAST(value AS STRING) as value")\
    .select(from_json(col("value"),streaming_schema).alias("value"))\
    .select("value.payload.after")\
    .select(from_json(col("after"),product_schema).alias("data"))\
    .selectExpr("data.*")

payment_df = spark.readStream\
    .format("kafka")\
    .option("kafka.bootstrap.servers", "broker:29092") \
    .option("subscribe", "transactions_streaming.public.payments") \
    .option("startingOffsets", "earliest") \
    .load()\
    .selectExpr("CAST(value AS STRING) as value")\
    .select(from_json(col("value"),streaming_schema).alias("value"))\
    .select("value.payload.after")\
    .select(from_json(col("after"),payment_schema).alias("data"))\
    .selectExpr("data.*")

transaction_df = spark.readStream\
    .format("kafka")\
    .option("kafka.bootstrap.servers", "broker:29092") \
    .option("subscribe", "transactions_streaming.public.transactions") \
    .option("startingOffsets", "earliest") \
    .load()\
    .selectExpr("CAST(value AS STRING) as value")\
    .select(from_json(col("value"),streaming_schema).alias("value"))\
    .select("value.payload.after")\
    .select(from_json(col("after"),transaction_schema).alias("data"))\
    .selectExpr("data.*")

transaction_df = transaction_df.withColumn("created_ts", to_timestamp(col("created_at")))
transaction_df = transaction_df.withColumn("created_date", to_date(col("created_at")))

def write_to_kafka(df, name):
    return df\
            .selectExpr("to_json(struct(*)) AS value")\
            .writeStream\
            .format("kafka")\
            .option("kafka.bootstrap.servers", "broker:29092") \
            .option("topic", f"streaming_{name}") \
            .option("checkpointLocation", f"s3a://checkpoints/kafka/{name}")\
            .start()

query5 = write_to_kafka(user_df,"users")
query6 = write_to_kafka(product_df,"products")
query7 = write_to_kafka(payment_df,"payments")
query8 = write_to_kafka(transaction_df,"transactions")

query1 = write_dim_data(user_df,"users")
query2 = write_dim_data(product_df,"products")
query3 = write_dim_data(payment_df,"payments")
query4 = transaction_df.writeStream\
            .format("parquet")\
            .option("path",f"s3a://transactions/transactions")\
            .option("checkpointLocation",f"s3a://checkpoints/transactions")\
            .outputMode("append")\
            .start()

query8.awaitTermination()

query4.awaitTermination()