"""Merge every completed, not-yet-merged day of staging CDC data into Iceberg (PLAN.md 4.3)."""
import json
import logging
import sys

from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import col, current_date, lit, row_number
from pyspark.sql.functions import max as spark_max
from pyspark.sql.utils import AnalysisException

from credential import MINIO_ACCESS_KEY, MINIO_SECRET_KEY
from helper import ENTITIES

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("iceberg_merge")

CATALOG = "lakehouse"
NAMESPACE = f"{CATALOG}.cdc"
ICEBERG_REST_URI = "http://iceberg-rest:8181"
LAST_MERGED_PROPERTY = "cdc.last-merged-date"
STAGING_ONLY_COLUMNS = ("cdc_op", "kafka_offset", "date")


def latest_change_per_key(df, pk):
    """Keep only the newest change for each primary key: by source commit
    time, then Kafka offset for changes in the same millisecond."""
    window = Window.partitionBy(pk).orderBy(col("cdc_ts_ms").desc(), col("kafka_offset").desc())
    return df.withColumn("_rank", row_number().over(window))\
        .filter(col("_rank") == 1)\
        .drop("_rank")


def merge_sql(target, source_view, pk, columns):
    # `cdc_ts_ms >=` makes re-running the same days a no-op and stops an
    # older change from overwriting a newer one already merged.
    set_clause = ", ".join(f"t.{c} = s.{c}" for c in columns)
    insert_columns = ", ".join(columns)
    insert_values = ", ".join(f"s.{c}" for c in columns)
    return f"""
        MERGE INTO {target} t
        USING {source_view} s
        ON t.{pk} = s.{pk}
        WHEN MATCHED AND s.cdc_op = 'd' AND s.cdc_ts_ms >= t.cdc_ts_ms THEN DELETE
        WHEN MATCHED AND s.cdc_op != 'd' AND s.cdc_ts_ms >= t.cdc_ts_ms THEN UPDATE SET {set_clause}
        WHEN NOT MATCHED AND s.cdc_op != 'd' THEN INSERT ({insert_columns}) VALUES ({insert_values})
    """


def build_spark():
    # HadoopFileIO writes through S3A (the Spark image has no AWS SDK v2), but
    # the REST catalog hands out s3:// table locations -- hence fs.s3.impl.
    return SparkSession.builder\
        .appName("iceberg_merge")\
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")\
        .config(f"spark.sql.catalog.{CATALOG}", "org.apache.iceberg.spark.SparkCatalog")\
        .config(f"spark.sql.catalog.{CATALOG}.catalog-impl", "org.apache.iceberg.rest.RESTCatalog")\
        .config(f"spark.sql.catalog.{CATALOG}.uri", ICEBERG_REST_URI)\
        .config(f"spark.sql.catalog.{CATALOG}.io-impl", "org.apache.iceberg.hadoop.HadoopFileIO")\
        .config("spark.hadoop.fs.s3.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")\
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")\
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)\
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)\
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")\
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")\
        .config("spark.hadoop.fs.s3a.path.style.access", "true")\
        .getOrCreate()


def last_merged_date(spark, target):
    try:
        properties = spark.sql(f"SHOW TBLPROPERTIES {target}").collect()
    except AnalysisException:
        return None, False
    return {r.key: r.value for r in properties}.get(LAST_MERGED_PROPERTY), True


def merge_entity(spark, name, pk, include_today=False):
    target = f"{NAMESPACE}.{name}"
    try:
        staging = spark.read.parquet(f"s3a://staging/{name}")
    except AnalysisException:
        logger.info(json.dumps({"event": "skipped", "entity": name, "reason": "no staging data yet"}))
        return

    columns = [c for c in staging.columns if c not in STAGING_ONLY_COLUMNS]
    last_merged, table_exists = last_merged_date(spark, target)
    if not table_exists:
        staging.select(*columns).limit(0).writeTo(target).using("iceberg").create()

    unmerged = staging if last_merged is None else staging.filter(col("date") > lit(last_merged))
    completed = unmerged.filter(col("date") < current_date())
    # include_today merges the still-open partition too but never records it
    # as merged, so rows landing later today are picked up by the next run.
    pending = unmerged if include_today else completed

    if pending.agg(spark_max("date")).first()[0] is None:
        logger.info(json.dumps({"event": "skipped", "entity": name, "reason": "nothing new to merge",
                                "last_merged_date": last_merged}))
        return

    latest_change_per_key(pending, pk).createOrReplaceTempView("staged_changes")
    spark.sql(merge_sql(target, "staged_changes", pk, columns))

    newest_completed = completed.agg(spark_max("date")).first()[0]
    if newest_completed is not None:
        spark.sql(f"ALTER TABLE {target} SET TBLPROPERTIES ('{LAST_MERGED_PROPERTY}' = '{newest_completed}')")
    logger.info(json.dumps({"event": "merged", "entity": name, "after": last_merged,
                            "completed_through": newest_completed and str(newest_completed),
                            "include_today": include_today}))


def main():
    include_today = "--include-today" in sys.argv[1:]
    spark = build_spark()
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {NAMESPACE}")

    failed = []
    for name, pk in ENTITIES:
        try:
            merge_entity(spark, name, pk, include_today)
        except Exception as e:
            logger.error(json.dumps({"event": "merge_failed", "entity": name, "exception": str(e)}))
            failed.append(name)

    spark.stop()
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
