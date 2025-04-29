# tests/test_pipeline_manager.py
import os
import json
import pytest
import tempfile
import shutil
from unittest.mock import MagicMock, patch
from cdc_gateway.pipeline_manager import PipelineManager


class TestPipelineManager:
    @pytest.fixture
    def setup_workspace(self):
        # Create a temporary directory for testing
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Clean up after tests
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_flink_client(self):
        mock_client = MagicMock()
        mock_client.get_job_status.return_value = "RUNNING"
        mock_client.deploy_sql_job.return_value = "mock-job-id"
        return mock_client

    @pytest.fixture
    def pipeline_manager(self, setup_workspace, mock_flink_client):
        # Setup a basic config for tests
        config = {
            "pipelines": {
                "workspace": setup_workspace,
                "defaultParallelism": 1,
                "monitorIntervalSec": 5
            },
            "flink": {
                "defaultSavepointOnCancel": False
            },
            "external": {
                "sqlserver": {},
                "kafka": {}
            }
        }
        return PipelineManager(mock_flink_client, setup_workspace, config)

    def test_create_pipeline(self, pipeline_manager):
        # Test creating a new pipeline
        pipeline_def = {
            "name": "test-pipeline",
            "source": {
                "type": "sqlserver-cdc",
                "config": {
                    "hostname": "test-host",
                    "port": "1433",
                    "database-name": "test-db",
                    "table-name": "test-table"
                }
            },
            "sink": {
                "type": "kafka",
                "config": {
                    "bootstrapServers": "kafka:9092",
                    "topic": "test-topic",
                    "format": "json"
                }
            }
        }

        # Create the pipeline
        pipeline = pipeline_manager.create_pipeline(pipeline_def)

        # Check that the pipeline was created correctly
        assert pipeline["name"] == "test-pipeline"
        assert pipeline["status"] == "CREATED"
        assert pipeline["source"]["type"] == "sqlserver-cdc"
        assert pipeline["sink"]["type"] == "kafka"
        assert "id" in pipeline
        
        # Check that the pipeline was saved to the workspace
        pipeline_file = os.path.join(pipeline_manager.workspace, f"{pipeline['id']}.json")
        assert os.path.exists(pipeline_file)
        
        # Check that the pipeline is in the manager's pipelines dict
        assert pipeline["id"] in pipeline_manager.pipelines

    def test_get_all_pipelines(self, pipeline_manager):
        # Create a few test pipelines
        pipeline_manager.create_pipeline({"name": "pipeline1", "source": {}, "sink": {}})
        pipeline_manager.create_pipeline({"name": "pipeline2", "source": {}, "sink": {}})
        
        # Get all pipelines
        pipelines = pipeline_manager.get_all_pipelines()
        
        # Check that we got the correct number of pipelines
        assert len(pipelines) == 2
        
        # Check that the pipeline names are correct
        pipeline_names = [p["name"] for p in pipelines]
        assert "pipeline1" in pipeline_names
        assert "pipeline2" in pipeline_names

    def test_start_pipeline(self, pipeline_manager, mock_flink_client):
        # Create a test pipeline
        pipeline = pipeline_manager.create_pipeline({
            "name": "start-test",
            "source": {"type": "sqlserver-cdc", "config": {}},
            "sink": {"type": "kafka", "config": {}}
        })
        
        # Start the pipeline
        started_pipeline = pipeline_manager.start_pipeline(pipeline["id"])
        
        # Check that the pipeline was started
        assert started_pipeline["status"] == "RUNNING"
        assert started_pipeline["flink_job_id"] == "mock-job-id"
        
        # Verify that deploy_sql_job was called on the Flink client
        mock_flink_client.deploy_sql_job.assert_called_once()

    def test_stop_pipeline(self, pipeline_manager, mock_flink_client):
        # Create and start a test pipeline
        pipeline = pipeline_manager.create_pipeline({
            "name": "stop-test",
            "source": {"type": "sqlserver-cdc", "config": {}},
            "sink": {"type": "kafka", "config": {}}
        })
        started_pipeline = pipeline_manager.start_pipeline(pipeline["id"])
        
        # Stop the pipeline
        stopped_pipeline = pipeline_manager.stop_pipeline(pipeline["id"])
        
        # Check that the pipeline was stopped
        assert stopped_pipeline["status"] == "STOPPED"
        
        # Verify that cancel_job was called on the Flink client
        mock_flink_client.cancel_job.assert_called_once_with(
            job_id=started_pipeline["flink_job_id"], 
            savepoint=False
        )

    def test_delete_pipeline(self, pipeline_manager):
        # Create a test pipeline
        pipeline = pipeline_manager.create_pipeline({
            "name": "delete-test",
            "source": {"type": "sqlserver-cdc", "config": {}},
            "sink": {"type": "kafka", "config": {}}
        })
        
        # Check that the pipeline file exists
        pipeline_file = os.path.join(pipeline_manager.workspace, f"{pipeline['id']}.json")
        assert os.path.exists(pipeline_file)
        
        # Delete the pipeline
        pipeline_manager.delete_pipeline(pipeline["id"])
        
        # Check that the pipeline was removed from the manager's pipelines dict
        assert pipeline["id"] not in pipeline_manager.pipelines
        
        # Check that the pipeline file was deleted
        assert not os.path.exists(pipeline_file)

    def test_get_pipeline_status(self, pipeline_manager, mock_flink_client):
        # Create and start a test pipeline
        pipeline = pipeline_manager.create_pipeline({
            "name": "status-test",
            "source": {"type": "sqlserver-cdc", "config": {}},
            "sink": {"type": "kafka", "config": {}}
        })
        started_pipeline = pipeline_manager.start_pipeline(pipeline["id"])
        
        # Get the pipeline status
        status = pipeline_manager.get_pipeline_status(pipeline["id"])
        
        # Check the status
        assert status["id"] == pipeline["id"]
        assert status["name"] == "status-test"
        assert status["status"] == "RUNNING"
        assert status["flink_job_id"] == "mock-job-id"
        assert "flink_status" in status
        
        # Verify that get_job_status was called on the Flink client
        mock_flink_client.get_job_status.assert_called_once_with(started_pipeline["flink_job_id"])

    @pytest.mark.parametrize(
        "source_type,sink_type,expected_source_contains,expected_sink_contains",
        [
            (
                "sqlserver-cdc", 
                "kafka", 
                "'connector' = 'sqlserver-cdc'", 
                "'connector' = 'kafka'"
            )
        ]
    )
    def test_generate_pipeline_sql(
        self, pipeline_manager, source_type, sink_type, 
        expected_source_contains, expected_sink_contains
    ):
        # Create a pipeline with the specified source and sink types
        pipeline = {
            "id": "test-id",
            "name": "sql-test",
            "source": {
                "type": source_type,
                "config": {
                    "hostname": "test-host",
                    "port": "1433",
                    "database-name": "test-db",
                    "table-name": "test-table"
                }
            },
            "sink": {
                "type": sink_type,
                "config": {
                    "bootstrapServers": "kafka:9092",
                    "topic": "test-topic",
                    "format": "json"
                }
            },
            "options": {}
        }
        
        # Generate SQL statements
        source_sql, sink_sql, pipeline_sql = pipeline_manager._generate_pipeline_sql(pipeline)
        
        # Check that the generated SQL contains the expected parts
        assert expected_source_contains in source_sql
        assert expected_sink_contains in sink_sql
        assert "INSERT INTO" in pipeline_sql
        assert "SELECT * FROM" in pipeline_sql
