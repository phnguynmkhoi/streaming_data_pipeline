from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when,udf, lit
from pyspark.sql.types import StructField,IntegerType,StringType,StructType,FloatType
import datetime
import uuid

def get_full_datamart(datamart, schema):
    try:
        df = spark.read.parquet(f"s3a://transactions/warehouse/{datamart}")
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
    df.write.mode("overwrite").parquet(f"s3a://transactions/warehouse/{datamart}")


MINIO_ACCESS_KEY = "vTx7ykoKSJj8lHRB8VUJ"
MINIO_SECRET_KEY = "tl6sujLw3xTY8IFUe5dsy44VDCXzMiosZHM4wEVa"

spark = SparkSession\
        .builder\
        .appName("transactions_transforming")\
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")\
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .getOrCreate()

# spark.sql("REFRESH TABLE dim_user")
# spark.sql("REFRESH TABLE dim_address")
# spark.sql("REFRESH TABLE dim_shipping")
# spark.sql("REFRESH TABLE dim_product")
# spark.sql("REFRESH TABLE fact_transactions")
spark.catalog.refreshTable("dim_user")
spark.catalog.refreshTable("dim_product")
spark.catalog.refreshTable("dim_shipping")
spark.catalog.refreshTable("dim_payment")
spark.catalog.refreshTable("fact_transactions")


user_schema = StructType([
    StructField("user_id",StringType()),
    StructField("full_name",StringType()),
    StructField("phone_number",StringType()),
    StructField("sex",StringType()),
    StructField("address",StringType()),
    StructField("birthdate",StringType()),
    StructField("email",StringType()),
    StructField("job",StringType()),
])

product_schema = StructType([
    StructField("product_id",StringType()),
    StructField("product_name",StringType()),
    StructField("category",StringType()),
    StructField("unit_price",FloatType()),
    StructField("merchant_name",StringType()),
])

payment_schema = StructType([
    StructField("payment_id",StringType()),
    StructField("payment_method",StringType()),
    StructField("currency",StringType()),
])

shipping_schema = StructType([
    StructField("shipping_id",StringType()),
    StructField("shipping_address",StringType()),
])

today = datetime.datetime.now().strftime("%y%m%d")
df = spark.read.parquet(f"s3a://transactions/{today}")

user_df = df\
        .select(["name","sex","address","phone_number","birthdate","email","job"])\
        .withColumnRenamed("name", "full_name").distinct()

product_df = df\
            .select(["product_name","category","unit_price","merchant_name"]).distinct()

payment_df = df.select(["payment_method", "currency"]).distinct()

shipping_df = df.select(["shipping_address"]).distinct()

user_df = insert_new_data_into_datamart(user_df,"dim_user",user_schema,"user_id")
product_df = insert_new_data_into_datamart(product_df,"dim_product",product_schema,"product_id")
payment_df = insert_new_data_into_datamart(payment_df,"dim_payment",payment_schema,"payment_id")
shipping_df = insert_new_data_into_datamart(shipping_df,"dim_shipping",shipping_schema,"shipping_id")

transaction_df = df.withColumnRenamed("name","full_name")\
                .join(user_df,on=["full_name","sex","address","phone_number","birthdate","email","job"],how="inner")\
                .join(product_df,on=["product_name","category","unit_price","merchant_name"],how="inner")\
                .join(payment_df, on=["payment_method", "currency"], how="inner")\
                .join(shipping_df, on=["shipping_address"], how="inner")\
                .select(["transaction_id","user_id","product_id","payment_id","shipping_id","quantity","discount","shipping_cost","total","created_at"])

# user_df.printSchema()
write_dim_data(user_df,"dim_user")
write_dim_data(product_df,"dim_product")
write_dim_data(payment_df,"dim_payment")
write_dim_data(shipping_df,"dim_shipping")
transaction_df.printSchema()
transaction_df.show()
transaction_df.write.mode("append").parquet(f"s3a://transactions/warehouse/fact_transactions")