# Real-Time Data Warehouse with Streaming Data Pipeline

This project demonstrates the implementation of a real-time data warehouse solution powered by a streaming data pipeline. It is designed to ingest, process, and store data in near real-time, enabling analytics and insights on up-to-the-moment data.

---

## Features

- **Real-Time Ingestion**: Ingest data from **postgres** using **Debezium** for capture all the data and push it to kafka broker
- **Scalable Processing**: Utilizes Apache Spark for distributed and fault-tolerant data processing.
- **Data Transformation**: Using **Apache Spark** for getting and transforming **Kafka** data and push back to **Kafka**
- **Data Storage**: Stores processed data in **MinIO** datalake for archived.
- **Analytics**: Utilizes Apache Pinot as Data Warehouse for realtime analysis 
- **Fault Tolerance**: Built-in resilience, **Kafka** checkpoint for handling data failures and reprocessing.

---

## Architecture

The data pipeline consists of the following components:

1. **Data Sources**: 
    - Event streams from **Debezium** connector which connect **Postgres**
2. **Ingestion Layer**: 
    - Using **Kafka** for data ingestion
3. **Processing Layer**: 
    - Using **Apache Spark** for transforming data and push it back to **Kafka** 
4. **Storage Layer**:
    - Using MinIO for data storage 

![Architecture Diagram](path-to-architecture-diagram.png)

---

## Prerequisites

- Docker and Docker Compose (for local development)

---

## Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/realtime-datawarehouse.git
cd realtime-datawarehouse
```

### 2. Install dependencies
- Install aws-java-sdk-bundle-1.11.375.jar, hadoop-aws-3.2.0.jar
- Copy above file and paste into jars folder

### 3. Start services
```bash 
docker compose up -d
```

### 4. Start Debezium connector
```bash
bash script/script.sh
```

### 5. Simulate transaction data using python
```bash
python src/main.py
```

### 6. Extract and Transform data using Spark
```bash
bash script/spark_extract_data_script.sh
```

### 7. Create schema and data warehouse table in Apache Pinot
```bash
bash script/create_all_schema.sh
bash script/create_all_table.sh
```

## Usage
- Visit <http://localhost:9000> for querying realtime data
- Visit <http://localhost:10001> for access to processed data that store in Parquet format inside the bucket you defined in apps/extract_data.py

## License

This project is licensed under the MIT License. See the LICENSE file for details.