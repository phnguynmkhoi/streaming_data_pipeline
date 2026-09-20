package pipeline

import java.net.URI
import java.net.http.{HttpClient, HttpRequest, HttpResponse}
import java.time.Duration

import com.fasterxml.jackson.databind.ObjectMapper

/** Fetches Avro value-schemas from the Schema Registry -- the Scala port of
  * apps/schema_registry.py (PLAN.md 5.3). Java 11's HttpClient and the
  * Jackson that Spark already ships keep this dependency-free.
  */
object SchemaRegistry {

  val Url = "http://schema-registry:8081"

  private val client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build()
  private val mapper = new ObjectMapper()

  /** Fetched once per entity at job startup, not per record: a schema change
    * while running either decodes wrong and raises, or silently omits a new
    * field, until the job restarts (the tradeoff accepted in PLAN.md 3.2).
    */
  def fetchLatestSchema(topic: String): String = {
    val request = HttpRequest
      .newBuilder(URI.create(s"$Url/subjects/$topic-value/versions/latest"))
      .timeout(Duration.ofSeconds(10))
      .GET()
      .build()

    val response = client.send(request, HttpResponse.BodyHandlers.ofString())
    if (response.statusCode() != 200) {
      throw new RuntimeException(
        s"Schema Registry returned ${response.statusCode()} for $topic-value: ${response.body()}")
    }
    mapper.readTree(response.body()).get("schema").asText()
  }
}
