import json
from unittest.mock import MagicMock, patch

from schema_registry import fetch_latest_schema

# Regression guard: a typo in the subject-naming convention here would
# silently 404 against a real registry (TopicNameStrategy: "<topic>-value"),
# the Avro-era equivalent of the old apps/schema.py field-name pinning tests.


def test_fetch_latest_schema_requests_correct_subject_url():
    response = MagicMock()
    response.read.return_value = json.dumps({"schema": '{"type":"record","name":"Value","fields":[]}'}).encode()
    response.__enter__.return_value = response

    with patch("schema_registry.urllib.request.urlopen", return_value=response) as mock_urlopen:
        schema_json = fetch_latest_schema("transactions_streaming.public.users")

    requested_url = mock_urlopen.call_args[0][0]
    assert requested_url == "http://schema-registry:8081/subjects/transactions_streaming.public.users-value/versions/latest"
    assert schema_json == '{"type":"record","name":"Value","fields":[]}'
