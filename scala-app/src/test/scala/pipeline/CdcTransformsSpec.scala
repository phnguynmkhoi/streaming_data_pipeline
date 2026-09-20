package pipeline

import java.util.Base64

import org.apache.spark.sql.{Row, SparkSession}
import org.apache.spark.sql.avro.functions.to_avro
import org.apache.spark.sql.functions.{col, struct}
import org.apache.spark.sql.types._
import org.scalatest.BeforeAndAfterAll
import org.scalatest.funsuite.AnyFunSuite

/** Scala mirror of tests/test_helper.py (PLAN.md 5.3): the same cases, so the
  * two implementations can be compared while both exist.
  */
class CdcTransformsSpec extends AnyFunSuite with BeforeAndAfterAll {

  private var spark: SparkSession = _

  override def beforeAll(): Unit = {
    spark = SparkSession.builder()
      .appName("cdc-transforms-spec").master("local[1]")
      .config("spark.ui.enabled", "false")
      .config("spark.sql.shuffle.partitions", "1")
      .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
  }

  override def afterAll(): Unit = if (spark != null) spark.stop()

  private val valueSchema =
    """{"type":"record","name":"Value","namespace":"test","fields":[
      |{"name":"user_id","type":["null","string"],"default":null},
      |{"name":"full_name","type":["null","string"],"default":null}]}""".stripMargin

  private val envelopeSchema =
    s"""{"type":"record","name":"Envelope","namespace":"test","fields":[
       |{"name":"before","type":["null",$valueSchema],"default":null},
       |{"name":"after","type":["null","test.Value"],"default":null},
       |{"name":"op","type":"string"},
       |{"name":"source","type":{"type":"record","name":"Source","fields":[
       |{"name":"ts_ms","type":"long"}]}}]}""".stripMargin

  private val valueType = StructType(Seq(
    StructField("user_id", StringType, nullable = true),
    StructField("full_name", StringType, nullable = true)))

  private val envelopeType = StructType(Seq(
    StructField("before", valueType, nullable = true),
    StructField("after", valueType, nullable = true),
    StructField("op", StringType, nullable = false),
    StructField("source", StructType(Seq(StructField("ts_ms", LongType, nullable = false))), nullable = false)))

  private val kafkaRowType = StructType(Seq(
    StructField("value", BinaryType, nullable = true),
    StructField("offset", LongType, nullable = false)))

  /** magic byte + dummy 4-byte schema id -- stripped blindly, never validated */
  private val confluentHeader = Array[Byte](0, 0, 0, 0, 1)

  private def encodeEnvelope(after: Option[(String, String)], before: Option[(String, String)] = None,
                             op: String = "c", tsMs: Long = 1L): Array[Byte] = {
    def row(v: Option[(String, String)]): Row =
      v.map { case (a, b) => Row(a, b) }.orNull
    val df = spark.createDataFrame(
      java.util.Arrays.asList(Row(row(before), row(after), op, Row(tsMs))), envelopeType)
    val body = df.select(to_avro(struct(df.columns.map(col): _*), envelopeSchema).as("bytes"))
      .collect()(0).getAs[Array[Byte]]("bytes")
    confluentHeader ++ body
  }

  private def kafkaDf(rows: Seq[(Array[Byte], Long)]) =
    spark.createDataFrame(
      java.util.Arrays.asList(rows.map { case (v, o) => Row(v, o) }: _*), kafkaRowType)

  test("good row goes to good_df") {
    val df = kafkaDf(Seq((encodeEnvelope(Some(("u1", "Alice"))), 1L)))
    val (good, bad) = CdcTransforms.parseCdcStream(df, envelopeSchema, "users", "user_id")
    assert(bad.count() == 0)
    val rows = good.collect()
    assert(rows.length == 1)
    assert(rows(0).getAs[String]("user_id") == "u1")
    assert(rows(0).getAs[String]("full_name") == "Alice")
  }

  test("schema drift with a missing primary key goes to bad_df") {
    val value = encodeEnvelope(Some((null, "Bob")))
    val (good, bad) = CdcTransforms.parseCdcStream(kafkaDf(Seq((value, 1L))), envelopeSchema, "users", "user_id")
    assert(good.count() == 0)
    val rows = bad.collect()
    assert(rows.length == 1)
    assert(rows(0).getAs[String]("entity") == "users")
    assert(rows(0).getAs[String]("raw_value") == Base64.getEncoder.encodeToString(value))
  }

  test("a record that cannot be decoded raises rather than reaching the DLQ") {
    val garbage = Array[Byte](-1, -1, -1, -1, -1, -1, -1, -1)
    val (_, bad) = CdcTransforms.parseCdcStream(kafkaDf(Seq((garbage, 1L))), envelopeSchema, "users", "user_id")
    assertThrows[Exception](bad.collect())
  }

  test("delete events are dropped by parseCdcStream") {
    val value = encodeEnvelope(after = None, before = Some(("u1", "Alice")), op = "d")
    val (good, bad) = CdcTransforms.parseCdcStream(kafkaDf(Seq((value, 1L))), envelopeSchema, "users", "user_id")
    assert(good.count() == 0 && bad.count() == 0)
  }

  test("cdcChanges keeps upserts from after") {
    val value = encodeEnvelope(Some(("u1", "Alice")), op = "u", tsMs = 42L)
    val rows = CdcTransforms.cdcChanges(kafkaDf(Seq((value, 7L))), envelopeSchema, "user_id").collect()
    assert(rows.length == 1)
    assert(rows(0).getAs[String]("user_id") == "u1")
    assert(rows(0).getAs[String]("cdc_op") == "u")
    assert(rows(0).getAs[Long]("cdc_ts_ms") == 42L)
    assert(rows(0).getAs[Long]("kafka_offset") == 7L)
  }

  test("cdcChanges takes the delete row image from before") {
    val value = encodeEnvelope(after = None, before = Some(("u1", null)), op = "d", tsMs = 43L)
    val rows = CdcTransforms.cdcChanges(kafkaDf(Seq((value, 8L))), envelopeSchema, "user_id").collect()
    assert(rows.length == 1)
    assert(rows(0).getAs[String]("user_id") == "u1")
    assert(rows(0).getAs[String]("cdc_op") == "d")
  }

  test("cdcChanges drops tombstones and null keys") {
    val nullKey = encodeEnvelope(Some((null, "Bob")))
    val df = kafkaDf(Seq((null.asInstanceOf[Array[Byte]], 9L), (nullKey, 10L)))
    assert(CdcTransforms.cdcChanges(df, envelopeSchema, "user_id").count() == 0)
  }

  test("addDateColumn parses a microsecond timestamp") {
    val df = spark.createDataFrame(
      java.util.Arrays.asList(Row("2024-01-15 10:30:45.123456")),
      StructType(Seq(StructField("last_modified_ts", StringType))))
    assert(CdcTransforms.addDateColumn(df).collect()(0).getAs[java.sql.Date]("date").toString == "2024-01-15")
  }

  test("addDateColumn is null for an unparseable timestamp") {
    val df = spark.createDataFrame(
      java.util.Arrays.asList(Row("not-a-timestamp")),
      StructType(Seq(StructField("last_modified_ts", StringType))))
    assert(CdcTransforms.addDateColumn(df).collect()(0).getAs[java.sql.Date]("date") == null)
  }

  test("toKafkaKv shapes key and value") {
    val df = spark.createDataFrame(
      java.util.Arrays.asList(Row("u1", "Alice")),
      StructType(Seq(StructField("user_id", StringType), StructField("full_name", StringType))))
    val result = CdcTransforms.toKafkaKv(df, "user_id")
    assert(result.columns.toSeq == Seq("key", "value"))
    val row = result.collect()(0)
    assert(row.getAs[String]("key") == "u1")
    assert(row.getAs[String]("value").contains("\"user_id\":\"u1\""))
  }
}
