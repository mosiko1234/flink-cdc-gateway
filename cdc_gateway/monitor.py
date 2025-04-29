# cdc_gateway/monitor.py
"""
Monitor service for CDC pipelines
"""
import os
import yaml
import time
import logging
import signal
import sys
from datetime import datetime
from cdc_gateway.pipeline_manager import PipelineManager
from cdc_gateway.flink_client import FlinkClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    logger.info("Received shutdown signal, exiting...")
    sys.exit(0)

def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting CDC Pipeline Monitor")
    
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
    
    # Get monitor interval
    monitor_interval = config['pipelines'].get('monitorIntervalSec', 10)
    
    logger.info(f"Pipeline monitor started with interval of {monitor_interval} seconds")
    
    # Main monitoring loop
    while True:
        try:
            # Get all pipelines
            pipelines = pipeline_manager.get_all_pipelines()
            
            # Update status for running pipelines
            for pipeline in pipelines:
                if pipeline['status'] == 'RUNNING' and pipeline.get('flink_job_id'):
                    try:
                        pipeline_manager.get_pipeline_status(pipeline['id'])
                    except Exception as e:
                        logger.error(f"Error updating pipeline {pipeline['name']}: {str(e)}")
            
            # Log stats
            running_count = sum(1 for p in pipelines if p['status'] == 'RUNNING')
            failed_count = sum(1 for p in pipelines if p['status'] == 'FAILED')
            logger.debug(f"Monitoring {len(pipelines)} pipelines: {running_count} running, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Monitor iteration failed: {str(e)}")
        
        # Sleep until next iteration
        time.sleep(monitor_interval)

if __name__ == "__main__":
    main()
