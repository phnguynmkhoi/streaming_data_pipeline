curl -i -X PUT -H "Accept:application/json" \
    -H  "Content-Type:application/json" http://localhost:8083/connectors/transactions-connector/config \
    -d '{
          "connector.class": "io.debezium.connector.mysql.MySqlConnector",
          "database.hostname": "mysql",
          "database.port": "3306",
          "database.user": "mkhoi",
          "database.password": "minhkhoi",
          "database.server.id": "42",
          "database.allowPublicKeyRetrieval":"true",
          "database.server.name": "cdc",
          "table.whitelist": "cdc.transactions",
          "database.history.kafka.bootstrap.servers": "kafka:29092",
          "database.history.kafka.topic": "transactions" ,
          "include.schema.changes": "true"
    }'