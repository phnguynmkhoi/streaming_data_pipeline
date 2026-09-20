package pipeline

import org.apache.spark.sql.{DataFrame, SparkSession}
import org.apache.spark.sql.functions.current_date
import org.apache.spark.sql.streaming.StreamingQuery

/** Streaming sources and sinks -- the thin I/O layer around CdcTransforms,
  * mirroring the second half of apps/helper.py (PLAN.md 5.3).
  */
object Sinks {

  /** value stays binary (Avro); casting it to STRING corrupts the bytes. */
  def readKafkaStream(spark: SparkSession, name: String): DataFrame =
    spark.readStream
      .format("kafka")
      .option("kafka.bootstrap.servers", CdcTransforms.KafkaBootstrapServers)
      .option("subscribe", s"transactions_streaming.public.$name")
      .option("startingOffsets", "earliest")
      .load()
      .select("value", "offset")

  def writeToKafka(df: DataFrame, name: String, pk: String): StreamingQuery =
    CdcTransforms.toKafkaKv(df, pk).writeStream
      .queryName(s"kafka_$name")
      .format("kafka")
      .option("kafka.bootstrap.servers", CdcTransforms.KafkaBootstrapServers)
      .option("topic", s"streaming_$name")
      .option("checkpointLocation", s"s3a://checkpoints/kafka/$name")
      .start()

  /** Partitioned by processing date, not event date: a change arriving late
    * lands in an unmerged partition instead of one already merged. */
  def writeToStaging(df: DataFrame, name: String): StreamingQuery =
    df.withColumn("date", current_date()).writeStream
      .queryName(s"staging_$name")
      .format("parquet")
      .partitionBy("date")
      .option("path", s"s3a://staging/$name")
      .option("checkpointLocation", s"s3a://checkpoints/staging/$name")
      .start()

  def writeToDlq(df: DataFrame, name: String): StreamingQuery =
    df.writeStream
      .queryName(s"dlq_$name")
      .format("json")
      .option("path", s"s3a://dlq/$name")
      .option("checkpointLocation", s"s3a://checkpoints/dlq/$name")
      .start()
}
