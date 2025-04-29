# cdc_gateway/pipeline_manager.py
"""
Pipeline management module for CDC Gateway
"""
import os
import json
import uuid
import time
import logging
from datetime import datetime
from cdc_gateway.flink_client import FlinkClient

logger = logging.getLogger(__name__)

class PipelineManager:
    def __init__(self, flink_client, workspace, config):
        self.flink_client = flink_client
        self.workspace = workspace
        self.config = config
        self.pipelines = {}
        
        # Create workspace directory if it doesn't exist
        os.makedirs(self.workspace, exist_ok=True)
        
        # Load existing pipelines from workspace
        self._load_pipelines()

    def _load_pipelines(self):
        """Load all pipeline definitions from workspace"""
        logger.info(f"Loading pipelines from {self.workspace}")
        try:
            for filename in os.listdir(self.workspace):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.workspace, filename)
                    with open(filepath, 'r') as f:
                        try:
                            pipeline = json.load(f)
                            self.pipelines[pipeline['id']] = pipeline
                            logger.info(f"Loaded pipeline: {pipeline['name']} (ID: {pipeline['id']})")
                        except Exception as e:
                            logger.error(f"Failed to load pipeline from {filepath}: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to load pipelines from workspace: {str(e)}")

    def _save_pipeline(self, pipeline):
        """Save pipeline definition to workspace"""
        filepath = os.path.join(self.workspace, f"{pipeline['id']}.json")
        with open(filepath, 'w') as f:
            json.dump(pipeline, f, indent=2)
        logger.info(f"Saved pipeline {pipeline['name']} to {filepath}")

    def get_all_pipelines(self):
        """Get all registered pipelines"""
        return list(self.pipelines.values())

    def get_pipeline(self, pipeline_id):
        """Get a specific pipeline by ID"""
        if pipeline_id not in self.pipelines:
            raise KeyError(f"Pipeline {pipeline_id} not found")
        return self.pipelines[pipeline_id]

    def create_pipeline(self, pipeline_def):
        """Create a new pipeline"""
        # Validate pipeline definition
        required_fields = ['name']
        for field in required_fields:
            if field not in pipeline_def:
                raise ValueError(f"Missing required field: {field}")
        
        # Create pipeline object with defaults
        pipeline = {
            'id': str(uuid.uuid4()),
            'name': pipeline_def['name'],
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'status': 'CREATED',
            'source': pipeline_def.get('source', {}),
            'sink': pipeline_def.get('sink', {}),
            'options': pipeline_def.get('options', {}),
            'flink_job_id': None,
            'last_error': None
        }
        
        # Add to pipelines dict
        self.pipelines[pipeline['id']] = pipeline
        
        # Save to workspace
        self._save_pipeline(pipeline)
        
        logger.info(f"Created pipeline: {pipeline['name']} (ID: {pipeline['id']})")
        return pipeline

    def start_pipeline(self, pipeline_id):
        """Start a pipeline"""
        pipeline = self.get_pipeline(pipeline_id)
        
        # Check if pipeline is already running
        if pipeline['status'] == 'RUNNING':
            logger.info(f"Pipeline {pipeline['name']} is already running")
            return pipeline
        
        try:
            # Generate Flink SQL for the pipeline
            source_sql, sink_sql, pipeline_sql = self._generate_pipeline_sql(pipeline)
            
            # Deploy to Flink
            job_id = self.flink_client.deploy_sql_job(
                job_name=pipeline['name'],
                sql_statements=[source_sql, sink_sql, pipeline_sql],
                parallelism=pipeline['options'].get('parallelism', self.config['pipelines']['defaultParallelism'])
            )
            
            # Update pipeline status
            pipeline['status'] = 'RUNNING'
            pipeline['flink_job_id'] = job_id
            pipeline['updated_at'] = datetime.now().isoformat()
            pipeline['last_error'] = None
            
            # Save updated pipeline
            self._save_pipeline(pipeline)
            
            logger.info(f"Started pipeline: {pipeline['name']} (ID: {pipeline['id']}, Flink Job ID: {job_id})")
            return pipeline
        except Exception as e:
            logger.error(f"Failed to start pipeline {pipeline['name']}: {str(e)}")
            pipeline['status'] = 'FAILED'
            pipeline['last_error'] = str(e)
            pipeline['updated_at'] = datetime.now().isoformat()
            self._save_pipeline(pipeline)
            raise

    def stop_pipeline(self, pipeline_id):
        """Stop a pipeline"""
        pipeline = self.get_pipeline(pipeline_id)
        
        # Check if pipeline is running
        if pipeline['status'] != 'RUNNING' or not pipeline['flink_job_id']:
            logger.info(f"Pipeline {pipeline['name']} is not running")
            return pipeline
        
        try:
            # Cancel Flink job
            self.flink_client.cancel_job(
                job_id=pipeline['flink_job_id'], 
                savepoint=pipeline['options'].get('savepointOnCancel', 
                                                 self.config['flink']['defaultSavepointOnCancel'])
            )
            
            # Update pipeline status
            pipeline['status'] = 'STOPPED'
            pipeline['updated_at'] = datetime.now().isoformat()
            
            # Save updated pipeline
            self._save_pipeline(pipeline)
            
            logger.info(f"Stopped pipeline: {pipeline['name']} (ID: {pipeline['id']})")
            return pipeline
        except Exception as e:
            logger.error(f"Failed to stop pipeline {pipeline['name']}: {str(e)}")
            pipeline['last_error'] = str(e)
            pipeline['updated_at'] = datetime.now().isoformat()
            self._save_pipeline(pipeline)
            raise

    def delete_pipeline(self, pipeline_id):
        """Delete a pipeline"""
        pipeline = self.get_pipeline(pipeline_id)
        
        # Stop pipeline if running
        if pipeline['status'] == 'RUNNING' and pipeline['flink_job_id']:
            self.stop_pipeline(pipeline_id)
        
        # Remove from pipelines dict
        del self.pipelines[pipeline_id]
        
        # Remove from workspace
        filepath = os.path.join(self.workspace, f"{pipeline_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
        
        logger.info(f"Deleted pipeline: {pipeline['name']} (ID: {pipeline_id})")

    def get_pipeline_status(self, pipeline_id):
        """Get current status of a pipeline"""
        pipeline = self.get_pipeline(pipeline_id)
        
        # If pipeline has a Flink job ID, get current status from Flink
        if pipeline['status'] == 'RUNNING' and pipeline['flink_job_id']:
            try:
                flink_status = self.flink_client.get_job_status(pipeline['flink_job_id'])
                
                # Map Flink status to pipeline status
                status_mapping = {
                    'RUNNING': 'RUNNING',
                    'FINISHED': 'FINISHED',
                    'CANCELED': 'STOPPED',
                    'FAILED': 'FAILED',
                    'CREATED': 'CREATED',
                    'CANCELLING': 'STOPPING',
                    'FAILING': 'FAILING'
                }
                
                new_status = status_mapping.get(flink_status, pipeline['status'])
                
                # Update if status has changed
                if new_status != pipeline['status']:
                    pipeline['status'] = new_status
                    pipeline['updated_at'] = datetime.now().isoformat()
                    self._save_pipeline(pipeline)
                    logger.info(f"Updated pipeline {pipeline['name']} status to {new_status}")
                
                return {
                    'id': pipeline['id'],
                    'name': pipeline['name'],
                    'status': pipeline['status'],
                    'flink_job_id': pipeline['flink_job_id'],
                    'flink_status': flink_status,
                    'last_updated': pipeline['updated_at']
                }
            except Exception as e:
                logger.error(f"Failed to get status for pipeline {pipeline['name']}: {str(e)}")
                return {
                    'id': pipeline['id'],
                    'name': pipeline['name'],
                    'status': pipeline['status'],
                    'flink_job_id': pipeline['flink_job_id'],
                    'error': str(e),
                    'last_updated': pipeline['updated_at']
                }
        
        # Return basic status for non-running pipelines
        return {
            'id': pipeline['id'],
            'name': pipeline['name'],
            'status': pipeline['status'],
            'flink_job_id': pipeline['flink_job_id'],
            'last_updated': pipeline['updated_at']
        }

    def _generate_pipeline_sql(self, pipeline):
        """Generate Flink SQL statements for the pipeline"""
        # Get source configuration
        source = pipeline['source']
        source_type = source.get('type', '')
        source_config = source.get('config', {})
        
        # Get sink configuration
        sink = pipeline['sink']
        sink_type = sink.get('type', '')
        sink_config = sink.get('config', {})
        
        # Generate source table SQL
        source_table_name = f"{pipeline['name'].replace('-', '_')}_source"
        source_sql = self._generate_source_sql(source_type, source_config, source_table_name)
        
        # Generate sink table SQL
        sink_table_name = f"{pipeline['name'].replace('-', '_')}_sink"
        sink_sql = self._generate_sink_sql(sink_type, sink_config, sink_table_name)
        
        # Generate pipeline SQL (insert from source to sink)
        pipeline_sql = f"INSERT INTO {sink_table_name} SELECT * FROM {source_table_name}"
        
        return source_sql, sink_sql, pipeline_sql

    def _generate_source_sql(self, source_type, source_config, table_name):
        """Generate SQL for source table"""
        # SQL Server CDC source
        if source_type.lower() == 'sqlserver-cdc':
            # Extract required fields
            hostname = source_config.get('hostname', '')
            port = source_config.get('port', '1433')
            database = source_config.get('database-name', '')
            table = source_config.get('table-name', '')
            username = "${MSSQL_USERNAME}"  # Will be replaced by environment variable
            password = "${MSSQL_PASSWORD}"  # Will be replaced by environment variable
            
            # Split schema and table
            if '.' in table:
                schema, table_only = table.split('.', 1)
            else:
                schema = 'dbo'
                table_only = table
            
            # Basic table schema - in a real implementation, this would be fetched from the database
            sql = f"""
            CREATE TABLE {table_name} (
                id INT,
                data STRING,
                update_time TIMESTAMP(3),
                PRIMARY KEY (id) NOT ENFORCED
            ) WITH (
                'connector' = 'sqlserver-cdc',
                'hostname' = '{hostname}',
                'port' = '{port}',
                'username' = '{username}',
                'password' = '{password}',
                'database-name' = '{database}',
                'schema-name' = '{schema}',
                'table-name' = '{table_only}'
            """
            
            # Add additional options
            for key, value in source_config.items():
                if key not in ['hostname', 'port', 'database-name', 'table-name', 'username', 'password']:
                    sql += f",\n    '{key}' = '{value}'"
            
            # Add default SQL Server options from config
            for key, value in self.config['external']['sqlserver'].items():
                if key.startswith('default'):
                    option_key = key[7:].lower()
                    if option_key not in source_config:
                        sql += f",\n    '{option_key}' = '{value}'"
            
            sql += "\n)"
            return sql
        
        # Add support for other source types as needed
        
        raise ValueError(f"Unsupported source type: {source_type}")

    def _generate_sink_sql(self, sink_type, sink_config, table_name):
        """Generate SQL for sink table"""
        # Kafka sink
        if sink_type.lower() == 'kafka':
            # Extract required fields
            bootstrap_servers = sink_config.get('bootstrapServers', '')
            topic = sink_config.get('topic', '')
            format_type = sink_config.get('format', 'json')
            
            # Basic table schema - should match the source table
            sql = f"""
            CREATE TABLE {table_name} (
                id INT,
                data STRING,
                update_time TIMESTAMP(3),
                PRIMARY KEY (id) NOT ENFORCED
            ) WITH (
                'connector' = 'kafka',
                'topic' = '{topic}',
                'properties.bootstrap.servers' = '{bootstrap_servers}',
                'format' = '{format_type}'
            """
            
            # Add additional options
            for key, value in sink_config.items():
                if key not in ['bootstrapServers', 'topic', 'format']:
                    sql += f",\n    '{key}' = '{value}'"
            
            # Add default Kafka options from config
            for key, value in self.config['external']['kafka'].items():
                if key.startswith('default'):
                    option_key = key[7:].lower()
                    if option_key not in sink_config:
                        sql += f",\n    '{option_key}' = '{value}'"
            
            sql += "\n)"
            return sql
        
        # Add support for other sink types as needed
        
        raise ValueError(f"Unsupported sink type: {sink_type}")
