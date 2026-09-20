package pipeline

import scala.collection.mutable

import com.fasterxml.jackson.databind.ObjectMapper
import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.streaming.{StreamingQuery, StreamingQueryListener}

/** Scala port of apps/extract_data.py (PLAN.md 5.3).
  *
  * One behavioural difference from the Python job, in Scala's favour:
  * StreamingQueryListener exists on the JVM, so per-batch metrics come from
  * real callbacks instead of the 5s polling loop PySpark 3.1 forced (2.5).
  * Per-entity supervision is unchanged: one entity's decode failure must not
  * take down the other four (3.2).
  */
object ExtractData {

  private val mapper = new ObjectMapper()

  private def log(fields: (String, Any)*): Unit = {
    val node = mapper.createObjectNode()
    fields.foreach {
      case (k, v: Int)    => node.put(k, v)
      case (k, v: Long)   => node.put(k, v)
      case (k, v: Double) => node.put(k, v)
      case (k, null)      => node.putNull(k)
      case (k, v)         => node.put(k, String.valueOf(v))
    }
    println(mapper.writeValueAsString(node))
  }

  private class PipelineListener extends StreamingQueryListener {
    override def onQueryStarted(event: StreamingQueryListener.QueryStartedEvent): Unit =
      log("event" -> "started", "query" -> event.name, "id" -> event.id.toString)

    override def onQueryProgress(event: StreamingQueryListener.QueryProgressEvent): Unit = {
      val p = event.progress
      log(
        "event" -> "progress",
        "query" -> p.name,
        "batch_id" -> p.batchId,
        "input_rows" -> p.numInputRows,
        "rows_per_sec" -> p.processedRowsPerSecond,
        "batch_duration_ms" -> Option(p.durationMs.get("triggerExecution")).map(_.toLong).orNull)
    }

    override def onQueryTerminated(event: StreamingQueryListener.QueryTerminatedEvent): Unit =
      log("event" -> "terminated", "id" -> event.id.toString,
          "exception" -> event.exception.orNull)
  }

  /** Waits on one entity's queries under an isolated exception boundary. If
    * any fails, the entity's other queries are stopped so it fails as a unit,
    * while the other entities keep running.
    */
  private def superviseEntity(name: String, queries: Seq[StreamingQuery]): Unit = {
    val failure = new mutable.HashMap[String, Throwable]()
    val lock = new Object

    val watchers = queries.map { q =>
      val t = new Thread(() => {
        try q.awaitTermination()
        catch {
          case e: Throwable =>
            lock.synchronized {
              if (failure.isEmpty) {
                failure.put("exc", e)
                queries.filter(o => (o ne q) && o.isActive).foreach(_.stop())
              }
            }
        }
      })
      t.setDaemon(true)
      t.start()
      t
    }
    watchers.foreach(_.join())

    failure.get("exc").foreach { e =>
      log("event" -> "entity_failed", "entity" -> name, "exception" -> e.getMessage)
    }
  }

  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder()
      .appName("transactions_streaming_scala")
      .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
      .config("spark.hadoop.fs.s3a.access.key", sys.env("MINIO_ACCESS_KEY"))
      .config("spark.hadoop.fs.s3a.secret.key", sys.env("MINIO_SECRET_KEY"))
      .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
      .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
      .config("spark.hadoop.fs.s3a.path.style.access", "true")
      .getOrCreate()

    spark.streams.addListener(new PipelineListener)

    val entityThreads = CdcTransforms.Entities.map { case (name, pk) =>
      val avroSchemaJson = SchemaRegistry.fetchLatestSchema(s"transactions_streaming.public.$name")
      val rawDf = Sinks.readKafkaStream(spark, name)
      val (goodDf, badDf) = CdcTransforms.parseCdcStream(rawDf, avroSchemaJson, name, pk)

      val queries = Seq(
        Sinks.writeToKafka(CdcTransforms.addDateColumn(goodDf), name, pk),
        Sinks.writeToStaging(CdcTransforms.cdcChanges(rawDf, avroSchemaJson, pk), name),
        Sinks.writeToDlq(badDf, name))

      val t = new Thread(() => superviseEntity(name, queries))
      t.start()
      t
    }

    entityThreads.foreach(_.join())
    spark.stop()
  }
}
