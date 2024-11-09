curl -X POST -H "Content-Type: application/json" \
    --data @debezium-connector-postgres.json \
    http://localhost:8093/connectors
