from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructField,IntegerType,StringType,StructType,FloatType,TimestampType
import datetime
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


df = spark.read.parquet("s3a://transactions/warehouse/fact_transactions")
df.show(10)