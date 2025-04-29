# Flink CDC Gateway

![Apache Flink](https://img.shields.io/badge/powered%20by-Apache%20Flink-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Version](https://img.shields.io/pypi/v/flink-cdc-gateway)
![License](https://img.shields.io/github/license/yourusername/flink-cdc-gateway)

A Change Data Capture (CDC) Gateway for Apache Flink, designed for air-gapped OpenShift environments.

## Overview

Flink CDC Gateway provides a REST API to manage CDC pipelines from SQL Server to Kafka using Apache Flink CDC connectors. It's designed specifically for air-gapped OpenShift environments and integrates with Apache Flink's SQL API.

Key features:

- RESTful API for managing CDC pipelines
- Integration with Apache Flink CDC connectors
- Support for SQL Server CDC to Kafka
- Designed for OpenShift compatibility
- Monitoring and health-check endpoints
- Pipeline state management

## Installation

### Using pip

```bash
pip install flink-cdc-gateway
```

### Using Docker

```bash
docker pull yourusername/flink-cdc-gateway:latest
```

## Usage

### Start the Gateway Service

```bash
# Set required environment variables
export FLINK_JOBMANAGER_HOST=flink-jobmanager
export FLINK_JOBMANAGER_PORT=6123
export CDC_GATEWAY_PORT=8084
export CDC_GATEWAY_ADMIN_PORT=8085

# Start the CDC Gateway
cdc-gateway
```

### Managing CDC Pipelines

Create a new CDC pipeline:

```bash
curl -X POST http://localhost:8084/api/v1/pipelines -H "Content-Type: application/json" -d '{
  "name": "orders-cdc",
  "source": {
    "type": "sqlserver-cdc",
    "config": {
      "hostname": "mssql.example.com",
      "port": "1433",
      "database-name": "your_database",
      "table-name": "sales.orders",
      "scan.startup.mode": "initial"
    }
  },
  "sink": {
    "type": "kafka",
    "config": {
      "bootstrapServers": "kafka-broker-1.example.com:9092",
      "topic": "cdc.orders",
      "format": "json"
    }
  }
}'
```

Get all pipelines:

```bash
curl http://localhost:8084/api/v1/pipelines
```

Start a pipeline:

```bash
curl -X POST http://localhost:8084/api/v1/pipelines/PIPELINE_ID/start
```

Check pipeline status:

```bash
curl http://localhost:8084/api/v1/pipelines/PIPELINE_ID/status
```

Stop a pipeline:

```bash
curl -X POST http://localhost:8084/api/v1/pipelines/PIPELINE_ID/stop
```

Delete a pipeline:

```bash
curl -X DELETE http://localhost:8084/api/v1/pipelines/PIPELINE_ID
```

### Health and Monitoring

Check service health:

```bash
curl http://localhost:8085/health
```

Get service information:

```bash
curl http://localhost:8085/info
```

Get metrics:

```bash
curl http://localhost:8085/metrics
```

## Configuration

The gateway can be configured using environment variables or a YAML configuration file:

```yaml
# API Configuration
api:
  port: 8084
  threads: 4
  workers: 2

# Admin Interface Configuration
admin:
  port: 8085
  enableMetrics: true

# Pipeline Management
pipelines:
  workspace: /opt/flink-cdc/pipelines
  maxConcurrentJobs: 10
  defaultParallelism: 2

# Flink Configuration
flink:
  jobmanager: flink-jobmanager
  port: 6123
  restPort: 8081
```

## Docker Deployment

```bash
docker run -d \
  -p 8084:8084 \
  -p 8085:8085 \
  -e FLINK_JOBMANAGER_HOST=flink-jobmanager \
  -e FLINK_JOBMANAGER_PORT=6123 \
  -e MSSQL_USERNAME=sa \
  -e MSSQL_PASSWORD=YourPassword \
  -v /path/to/config:/opt/flink-cdc/config \
  -v /path/to/pipelines:/opt/flink-cdc/pipelines \
  yourusername/flink-cdc-gateway:latest
```

## OpenShift Deployment

For detailed deployment instructions with Helm on OpenShift, see our [deployment guide](https://github.com/mosiko1234/flink-cdc-gateway/blob/main/DEPLOYMENT.md).

## Development

### Prerequisites

- Python 3.8+
- Docker
- Apache Flink 1.17+

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/mosiko1234/flink-cdc-gateway.git
cd flink-cdc-gateway

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

## License

Apache License 2.0