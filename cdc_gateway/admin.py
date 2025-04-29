# cdc_gateway/admin.py
"""
Flask application for CDC Gateway Admin API
"""
import os
import yaml
import psutil
import logging
from flask import Flask, jsonify
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Gauge
from werkzeug.exceptions import HTTPException

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
config_path = os.environ.get('CONFIG_PATH', '/opt/flink-cdc/config/cdc-gateway-config.yaml')
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Prometheus metrics
api_requests = Counter('cdc_gateway_api_requests_total', 'Total API requests', ['endpoint', 'method', 'status'])
active_pipelines = Gauge('cdc_gateway_active_pipelines', 'Number of active pipelines')
pipeline_operations = Counter('cdc_gateway_pipeline_operations_total', 'Pipeline operations', ['operation', 'status'])
system_memory_usage = Gauge('cdc_gateway_memory_usage_bytes', 'Memory usage in bytes')
system_cpu_usage = Gauge('cdc_gateway_cpu_usage_percent', 'CPU usage percentage')

# Error handler
@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    return jsonify(error=str(e)), code

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    # Update system metrics
    system_memory_usage.set(psutil.virtual_memory().used)
    system_cpu_usage.set(psutil.cpu_percent())
    
    return jsonify(status="UP", service="CDC Gateway Admin")

# Metrics endpoint
@app.route('/metrics', methods=['GET'])
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

# Info endpoint
@app.route('/info', methods=['GET'])
def info():
    # Get pipeline counts from workspace directory
    workspace = config['pipelines']['workspace']
    pipeline_count = 0
    if os.path.exists(workspace):
        pipeline_count = len([f for f in os.listdir(workspace) if f.endswith('.json')])
    
    active_pipelines.set(pipeline_count)
    
    return jsonify({
        "version": "0.7.0",
        "name": "Apache Flink CDC Gateway",
        "description": "Change Data Capture Gateway for Apache Flink",
        "pipelines": {
            "total": pipeline_count,
            "workspace": workspace
        },
        "flink": {
            "jobmanager": os.environ.get('FLINK_JOBMANAGER_HOST', config['flink']['jobmanager']),
            "port": os.environ.get('FLINK_JOBMANAGER_PORT', config['flink']['port'])
        },
        "system": {
            "memory_used_mb": round(psutil.virtual_memory().used / (1024 * 1024), 2),
            "cpu_percent": psutil.cpu_percent(),
            "hostname": os.uname().nodename
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('CDC_GATEWAY_ADMIN_PORT', config['admin']['port']))
    app.run(host='0.0.0.0', port=port, debug=False)