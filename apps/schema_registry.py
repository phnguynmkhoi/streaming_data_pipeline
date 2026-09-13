import json
import urllib.request

SCHEMA_REGISTRY_URL = "http://schema-registry:8081"


def fetch_latest_schema(topic):
    """Fetch the current Avro value-schema for a Debezium CDC topic from the
    Schema Registry, as a JSON string for pyspark.sql.avro.functions.from_avro.

    Fetched once per entity at Spark job startup, not per-record. If the
    schema evolves while the job is running, messages written under the new
    schema either decode wrong/throw (incompatible change -- caught as a
    decode failure, see helper.parse_cdc_stream) or silently drop the new
    field (compatible/additive change) until the job is restarted to pick up
    the new schema -- a deliberate simplification over full per-record
    schema-ID resolution (e.g. ABRiS), accepted for this project's scale
    (PLAN.md 3.2).
    """
    subject = f"{topic}-value"
    url = f"{SCHEMA_REGISTRY_URL}/subjects/{subject}/versions/latest"
    with urllib.request.urlopen(url, timeout=10) as resp:
        body = json.loads(resp.read())
    return body["schema"]
