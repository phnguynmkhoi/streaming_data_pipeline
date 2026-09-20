package pipeline

import org.apache.spark.sql.DataFrame
import org.apache.spark.sql.avro.functions.from_avro
import org.apache.spark.sql.functions._

/** Pure DataFrame transformations -- the Scala port of apps/helper.py
  * (PLAN.md 5.3). No I/O, so these are unit-testable against static
  * DataFrames exactly like the Python versions are.
  */
object CdcTransforms {

  val KafkaBootstrapServers = "broker:29092"
  val LastModifiedTsFormat = "yyyy-MM-dd HH:mm:ss.SSSSSS"

  /** Kafka's Confluent wire format prefixes every Avro message with a 5-byte
    * header (magic byte + schema id) before the body. */
  val ConfluentWireHeaderBytes = 5

  val Entities: Seq[(String, String)] = Seq(
    ("users", "user_id"),
    ("products", "product_id"),
    ("payments", "payment_id"),
    ("transactions", "transaction_id"),
    ("shippings", "shipping_id")
  )

  /** Column expression decoding a raw Kafka `value` into Debezium's Avro
    * envelope. Null for Kafka tombstones (null value). */
  def decodeEnvelope(avroSchemaJson: String): org.apache.spark.sql.Column = {
    val avroBody = expr(s"substring(value, ${ConfluentWireHeaderBytes + 1}, length(value))")
    from_avro(avroBody, avroSchemaJson)
  }

  /** Splits decoded rows into (good, bad).
    *
    * A row that fails to decode is not routed to bad: from_avro runs in its
    * default FAILFAST mode, so an incompatible schema raises and fails the
    * entity's queries rather than being silently absorbed (PLAN.md 3.2).
    */
  def parseCdcStream(df: DataFrame, avroSchemaJson: String, name: String, pk: String)
      : (DataFrame, DataFrame) = {
    val afterDf = df
      .select(col("value").as("raw_value"), decodeEnvelope(avroSchemaJson)("after").as("after"))
      .filter(col("after").isNotNull)

    val isBad = col(s"after.$pk").isNull

    // raw_value is binary; base64 so the DLQ's JSON sink can write it.
    val badDf = afterDf.filter(isBad)
      .select(base64(col("raw_value")).as("raw_value"), lit(name).as("entity"))
    val goodDf = afterDf.filter(!isBad).selectExpr("after.*")

    (goodDf, badDf)
  }

  /** Flattens change events for the staging archive that feeds the Iceberg
    * merge (PLAN.md 4.3). Unlike parseCdcStream this keeps DELETEs, whose row
    * image comes from `before` since Debezium's `after` is null for them.
    */
  def cdcChanges(df: DataFrame, avroSchemaJson: String, pk: String): DataFrame = {
    val events = df
      .select(decodeEnvelope(avroSchemaJson).as("e"), col("offset").as("kafka_offset"))
      .filter(col("e").isNotNull)

    val row = when(col("e.op") === "d", col("e.before")).otherwise(col("e.after"))

    events
      .select(
        row.as("row"),
        col("e.op").as("cdc_op"),
        col("e.source.ts_ms").as("cdc_ts_ms"),
        col("kafka_offset"))
      .filter(col(s"row.$pk").isNotNull)
      .select(col("row.*"), col("cdc_op"), col("cdc_ts_ms"), col("kafka_offset"))
  }

  def addDateColumn(df: DataFrame, tsCol: String = "last_modified_ts",
                    tsFormat: String = LastModifiedTsFormat): DataFrame =
    df.withColumn("date", to_date(to_timestamp(col(tsCol), tsFormat)))

  /** Keying by primary key is required for Pinot FULL upsert correctness once
    * a topic has more than one partition (PLAN.md 1.7). */
  def toKafkaKv(df: DataFrame, pk: String): DataFrame =
    df.selectExpr(s"CAST($pk AS STRING) AS key", "to_json(struct(*)) AS value")
}
