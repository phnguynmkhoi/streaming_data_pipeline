import json
import logging

from pyspark.sql import SparkSession
from pyspark.sql.streaming import StreamingQueryListener

from credential import MINIO_ACCESS_KEY, MINIO_SECRET_KEY
from schema import (
    transaction_schema,
    user_schema,
    product_schema,
    payment_schema,
    shipping_schema,
    streaming_schema,
)
from helper import write_data_to_minio, write_to_kafka, write_to_dlq, read_kafka_stream, add_date_column

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("streaming_pipeline")


class PipelineListener(StreamingQueryListener):
    """Emits per-batch metrics as structured JSON so lag/stalls are visible
    without opening the Spark UI. `watermark` will always be null here since
    none of these queries use .withWatermark() (plain append streams, no
    windowed aggregation) -- left in the schema for parity with the metric
    Spark actually tracks, in case a future query adds one.
    """

    def onQueryStarted(self, event):
        logger.info(json.dumps({"event": "started", "query": event.name, "id": str(event.id)}))

    def onQueryProgress(self, event):
        progress = event.progress
        logger.info(json.dumps({
            "event": "progress",
            "query": progress.name,
            "batch_id": progress.batchId,
            "input_rows": progress.numInputRows,
            "rows_per_sec": progress.processedRowsPerSecond,
            "batch_duration_ms": (progress.durationMs or {}).get("triggerExecution"),
            "watermark": (progress.eventTime or {}).get("watermark"),
        }))

    def onQueryTerminated(self, event):
        logger.info(json.dumps({
            "event": "terminated",
            "id": str(event.id),
            "exception": event.exception,
        }))


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

spark.streams.addListener(PipelineListener())

user_df, user_bad_df = read_kafka_stream(spark, streaming_schema, user_schema, "users", "user_id")

product_df, product_bad_df = read_kafka_stream(spark, streaming_schema, product_schema, "products", "product_id")

payment_df, payment_bad_df = read_kafka_stream(spark, streaming_schema, payment_schema, "payments", "payment_id")

transaction_df, transaction_bad_df = read_kafka_stream(spark, streaming_schema, transaction_schema, "transactions", "transaction_id")

shipping_df, shipping_bad_df = read_kafka_stream(spark, streaming_schema, shipping_schema, "shippings", "shipping_id")

transaction_df = add_date_column(transaction_df)
user_df = add_date_column(user_df)
product_df = add_date_column(product_df)
payment_df = add_date_column(payment_df)
shipping_df = add_date_column(shipping_df)

query6 = write_to_kafka(user_df,"users","user_id")
query7 = write_to_kafka(product_df,"products","product_id")
query8 = write_to_kafka(payment_df,"payments","payment_id")
query9 = write_to_kafka(transaction_df,"transactions","transaction_id")
query10 = write_to_kafka(shipping_df,"shippings","shipping_id")

query1 = write_data_to_minio(user_df,"users")
query2 = write_data_to_minio(product_df,"products")
query3 = write_data_to_minio(payment_df,"payments")
query4 = write_data_to_minio(transaction_df,"transactions")
query5 = write_data_to_minio(shipping_df,"shippings")

query11 = write_to_dlq(user_bad_df, "users")
query12 = write_to_dlq(product_bad_df, "products")
query13 = write_to_dlq(payment_bad_df, "payments")
query14 = write_to_dlq(transaction_bad_df, "transactions")
query15 = write_to_dlq(shipping_bad_df, "shippings")

try:
    spark.streams.awaitAnyTermination()
except Exception as e:
    import traceback
    traceback.print_exc()
