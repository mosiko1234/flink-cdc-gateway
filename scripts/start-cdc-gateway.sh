# scripts/start-cdc-gateway.sh
#!/bin/bash
set -e

echo "Starting Flink CDC Gateway on port $CDC_GATEWAY_PORT"
echo "Admin interface on port $CDC_GATEWAY_ADMIN_PORT"

# Check if Flink JobManager is available
echo "Checking connection to Flink JobManager at $FLINK_JOBMANAGER_HOST:$FLINK_JOBMANAGER_PORT..."
timeout 60 bash -c 'until nc -z $FLINK_JOBMANAGER_HOST $FLINK_JOBMANAGER_PORT; do echo "Waiting for Flink JobManager..."; sleep 2; done'
echo "Flink JobManager is available."

# Start the CDC Gateway REST API service
echo "Starting CDC Gateway API service..."
cd /opt/flink-cdc
gunicorn \
  --bind 0.0.0.0:${CDC_GATEWAY_PORT} \
  --access-logfile - \
  --error-logfile - \
  --workers 2 \
  --threads 4 \
  cdc_gateway.app:app &

# Start the CDC Gateway Admin service
echo "Starting CDC Gateway Admin service..."
gunicorn \
  --bind 0.0.0.0:${CDC_GATEWAY_ADMIN_PORT} \
  --access-logfile - \
  --error-logfile - \
  --workers 1 \
  --threads 2 \
  cdc_gateway.admin:app &

# Start pipeline monitoring
echo "Starting CDC pipeline monitoring service..."
python3 -m cdc_gateway.monitor &

# Keep container running
echo "CDC Gateway started successfully"
tail -f /dev/null