# cdc_gateway/app.py
"""
Main Flask application for CDC Gateway API
"""
import os
import json
import yaml
import logging
from flask import Flask, request, jsonify
from werkzeug.exceptions import HTTPException
from cdc_gateway.pipeline_manager import PipelineManager
from cdc_gateway.flink_client import FlinkClient

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

# Initialize components
flink_client = FlinkClient(
    jobmanager_host=os.environ.get('FLINK_JOBMANAGER_HOST', config['flink']['jobmanager']),
    jobmanager_port=int(os.environ.get('FLINK_JOBMANAGER_PORT', config['flink']['port'])),
    config=config['flink']
)

pipeline_manager = PipelineManager(
    flink_client=flink_client,
    workspace=config['pipelines']['workspace'],
    config=config
)

# Error handler
@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    return jsonify(error=str(e)), code

# Health check endpoint
@app.route('/api/v1/health', methods=['GET'])
def health():
    return jsonify(status="OK", service="CDC Gateway API")

# API Endpoints for Pipeline Management

@app.route('/api/v1/pipelines', methods=['GET'])
def get_all_pipelines():
    """Get all registered pipelines"""
    pipelines = pipeline_manager.get_all_pipelines()
    return jsonify(pipelines)

@app.route('/api/v1/pipelines/<pipeline_id>', methods=['GET'])
def get_pipeline(pipeline_id):
    """Get details for a specific pipeline"""
    try:
        pipeline = pipeline_manager.get_pipeline(pipeline_id)
        return jsonify(pipeline)
    except KeyError:
        return jsonify(error=f"Pipeline {pipeline_id} not found"), 404

@app.route('/api/v1/pipelines', methods=['POST'])
def create_pipeline():
    """Create a new pipeline"""
    try:
        pipeline_def = request.json
        pipeline = pipeline_manager.create_pipeline(pipeline_def)
        return jsonify(pipeline), 201
    except Exception as e:
        logger.error(f"Failed to create pipeline: {str(e)}")
        return jsonify(error=str(e)), 400

@app.route('/api/v1/pipelines/import', methods=['POST'])
def import_pipelines():
    """Import multiple pipelines"""
    try:
        request_data = request.json
        if 'pipelines' not in request_data:
            return jsonify(error="Missing 'pipelines' in request body"), 400
        
        results = []
        for pipeline_def in request_data['pipelines']:
            try:
                pipeline = pipeline_manager.create_pipeline(pipeline_def)
                results.append({"name": pipeline['name'], "id": pipeline['id'], "status": "created"})
            except Exception as e:
                results.append({"name": pipeline_def.get('name', 'unknown'), "error": str(e)})
        
        return jsonify(results), 201
    except Exception as e:
        logger.error(f"Failed to import pipelines: {str(e)}")
        return jsonify(error=str(e)), 400

@app.route('/api/v1/pipelines/<pipeline_id>/start', methods=['POST'])
def start_pipeline(pipeline_id):
    """Start a pipeline"""
    try:
        pipeline = pipeline_manager.start_pipeline(pipeline_id)
        return jsonify(pipeline)
    except KeyError:
        return jsonify(error=f"Pipeline {pipeline_id} not found"), 404
    except Exception as e:
        logger.error(f"Failed to start pipeline {pipeline_id}: {str(e)}")
        return jsonify(error=str(e)), 500

@app.route('/api/v1/pipelines/<pipeline_id>/stop', methods=['POST'])
def stop_pipeline(pipeline_id):
    """Stop a pipeline"""
    try:
        pipeline = pipeline_manager.stop_pipeline(pipeline_id)
        return jsonify(pipeline)
    except KeyError:
        return jsonify(error=f"Pipeline {pipeline_id} not found"), 404
    except Exception as e:
        logger.error(f"Failed to stop pipeline {pipeline_id}: {str(e)}")
        return jsonify(error=str(e)), 500

@app.route('/api/v1/pipelines/<pipeline_id>/status', methods=['GET'])
def get_pipeline_status(pipeline_id):
    """Get current status of a pipeline"""
    try:
        status = pipeline_manager.get_pipeline_status(pipeline_id)
        return jsonify(status)
    except KeyError:
        return jsonify(error=f"Pipeline {pipeline_id} not found"), 404
    except Exception as e:
        logger.error(f"Failed to get status for pipeline {pipeline_id}: {str(e)}")
        return jsonify(error=str(e)), 500

@app.route('/api/v1/pipelines/<pipeline_id>', methods=['DELETE'])
def delete_pipeline(pipeline_id):
    """Delete a pipeline"""
    try:
        pipeline_manager.delete_pipeline(pipeline_id)
        return '', 204
    except KeyError:
        return jsonify(error=f"Pipeline {pipeline_id} not found"), 404
    except Exception as e:
        logger.error(f"Failed to delete pipeline {pipeline_id}: {str(e)}")
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    port = int(os.environ.get('CDC_GATEWAY_PORT', config['api']['port']))
    app.run(host='0.0.0.0', port=port, debug=False)
