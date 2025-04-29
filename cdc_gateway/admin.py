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

# Define configuration loading with fallbacks
def load_config():
    # חפש את קובץ התצורה במספר מיקומים אפשריים
    config_paths = [
        os.environ.get('CONFIG_PATH'),  # אם הוגדר משתנה סביבה
        '/opt/flink-cdc/config/cdc-gateway-config.yaml',  # מיקום ברירת מחדל בהפעלה
        os.path.join(os.path.dirname(__file__), '..', 'config', 'cdc-gateway-config.yaml'),  # בתוך הפרויקט
        os.path.join(os.path.dirname(__file__), '..', 'tests', 'test-config.yaml'),  # קובץ בדיקות
    ]
    
    # נסה לקרוא מכל מיקום אפשרי
    for path in config_paths:
        if path and os.path.exists(path):
            logger.info(f"Loading configuration from: {path}")
            try:
                with open(path, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"Failed to load config from {path}: {str(e)}")
    
    # לא נמצא קובץ תצורה - השתמש בערכי ברירת מחדל בסיסיים
    logger.warning("No configuration file found, using default values")
    return {
        "api": {"port": 8084},
        "admin": {"port": 8085},
        "pipelines": {"workspace": "/tmp/pipelines"},
        "flink": {
            "jobmanager": "localhost",
            "port": 6123,
            "restPort": 8081
        },
        "external": {
            "sqlserver": {},
            "kafka": {},
            "s3": {}
        },
        "logging": {"level": "INFO"}
    }

# טען את קובץ התצורה
config = load_config()

# Mock PipelineManager for testing or initialize it in production
try:
    from cdc_gateway.pipeline_manager import PipelineManager
    from cdc_gateway.flink_client import FlinkClient
    
    # Initialize real components if imports succeeded
    flink_client = FlinkClient(
        jobmanager_host=os.environ.get('FLINK_JOBMANAGER_HOST', config.get('flink', {}).get('jobmanager', 'localhost')),
        jobmanager_port=int(os.environ.get('FLINK_JOBMANAGER_PORT', config.get('flink', {}).get('port', 6123))),
        config=config.get('flink', {})
    )
    
    pipeline_manager = PipelineManager(
        flink_client=flink_client,
        workspace=config.get('pipelines', {}).get('workspace', '/tmp/pipelines'),
        config=config
    )
except ImportError:
    # For testing, we might not have these components available
    # and they will be mocked in tests
    logger.warning("Failed to import PipelineManager or FlinkClient, using mocks")
    pipeline_manager = None

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
# תיקון לפונקציית info ב-admin.py

@app.route('/info', methods=['GET'])
def info():
    # Get pipeline counts from workspace or pipeline manager if available
    workspace = config.get('pipelines', {}).get('workspace', '/tmp/pipelines')
    pipeline_count = 0
    
    if pipeline_manager:
        try:
            pipelines = pipeline_manager.get_all_pipelines()
            pipeline_count = len(pipelines)
            running_count = sum(1 for p in pipelines if p.get('status') == 'RUNNING')
            active_pipelines.set(running_count)
        except Exception as e:
            logger.error(f"Error getting pipeline count: {str(e)}")
    elif os.path.exists(workspace):
        try:
            # ספירה של קבצי JSON בתיקיית העבודה
            pipeline_files = [f for f in os.listdir(workspace) if f.endswith('.json')]
            pipeline_count = len(pipeline_files)
            logger.debug(f"Found {pipeline_count} pipeline files in {workspace}: {pipeline_files}")
            active_pipelines.set(0)  # Not able to determine running count
        except Exception as e:
            logger.error(f"Error reading workspace: {str(e)}")
    
    return jsonify({
        "version": "0.7.0",
        "name": "Apache Flink CDC Gateway",
        "description": "Change Data Capture Gateway for Apache Flink",
        "pipelines": {
            "total": pipeline_count,
            "workspace": workspace
        },
        "flink": {
            "jobmanager": os.environ.get('FLINK_JOBMANAGER_HOST', config.get('flink', {}).get('jobmanager', 'localhost')),
            "port": os.environ.get('FLINK_JOBMANAGER_PORT', config.get('flink', {}).get('port', 6123))
        },
        "system": {
            "memory_used_mb": round(psutil.virtual_memory().used / (1024 * 1024), 2),
            "cpu_percent": psutil.cpu_percent(),
            "hostname": os.uname().nodename
        }
    })

def main():
    """Main entry point for the admin application"""
    port = int(os.environ.get('CDC_GATEWAY_ADMIN_PORT', config.get('admin', {}).get('port', 8085)))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()