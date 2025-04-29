# scripts/pipeline-utils.sh
#!/bin/bash

# Utility functions for managing CDC pipelines

# Import a pipeline definition from JSON file
import_pipeline() {
  local pipeline_file="$1"
  
  if [ ! -f "$pipeline_file" ]; then
    echo "Error: Pipeline file $pipeline_file not found"
    return 1
  fi
  
  echo "Importing pipeline from $pipeline_file"
  curl -s -X POST "http://localhost:${CDC_GATEWAY_PORT}/api/v1/pipelines/import" \
    -H "Content-Type: application/json" \
    -d @"$pipeline_file"
}

# List all pipelines
list_pipelines() {
  echo "Listing all pipelines:"
  curl -s "http://localhost:${CDC_GATEWAY_PORT}/api/v1/pipelines" | jq '.'
}

# Get status of a specific pipeline
get_pipeline_status() {
  local pipeline_name="$1"
  
  echo "Getting status for pipeline: $pipeline_name"
  curl -s "http://localhost:${CDC_GATEWAY_PORT}/api/v1/pipelines/$pipeline_name/status" | jq '.'
}

# Start a pipeline
start_pipeline() {
  local pipeline_name="$1"
  
  echo "Starting pipeline: $pipeline_name"
  curl -s -X POST "http://localhost:${CDC_GATEWAY_PORT}/api/v1/pipelines/$pipeline_name/start" | jq '.'
}

# Stop a pipeline
stop_pipeline() {
  local pipeline_name="$1"
  
  echo "Stopping pipeline: $pipeline_name"
  curl -s -X POST "http://localhost:${CDC_GATEWAY_PORT}/api/v1/pipelines/$pipeline_name/stop" | jq '.'
}

# Delete a pipeline
delete_pipeline() {
  local pipeline_name="$1"
  
  echo "Deleting pipeline: $pipeline_name"
  curl -s -X DELETE "http://localhost:${CDC_GATEWAY_PORT}/api/v1/pipelines/$pipeline_name" | jq '.'
}

# Create MSSQL CDC pipeline with JSON template
create_mssql_cdc_pipeline() {
  local pipeline_name="$1"
  local mssql_host="$2"
  local mssql_port="$3"
  local database_name="$4"
  local table_name="$5"
  local kafka_brokers="$6"
  local kafka_topic="$7"
  
  cat > /tmp/pipeline.json << EOF
{
  "name": "${pipeline_name}",
  "source": {
    "type": "sqlserver-cdc",
    "config": {
      "hostname": "${mssql_host}",
      "port": "${mssql_port}",
      "username": "${MSSQL_USERNAME}",
      "password": "${MSSQL_PASSWORD}",
      "database-name": "${database_name}",
      "table-name": "${table_name}",
      "scan.startup.mode": "initial"
    }
  },
  "sink": {
    "type": "kafka",
    "config": {
      "bootstrapServers": "${kafka_brokers}",
      "topic": "${kafka_topic}",
      "format": "json"
    }
  }
}
EOF

  import_pipeline /tmp/pipeline.json
  rm /tmp/pipeline.json
}