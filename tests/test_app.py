# tests/test_app.py
import json
import pytest
from unittest.mock import patch, MagicMock
from cdc_gateway.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@patch('cdc_gateway.app.pipeline_manager')
def test_get_all_pipelines(mock_pipeline_manager, client):
    # Setup mock
    mock_pipeline_manager.get_all_pipelines.return_value = [
        {"id": "1", "name": "test1", "status": "CREATED"},
        {"id": "2", "name": "test2", "status": "RUNNING"}
    ]
    
    # Make request
    response = client.get('/api/v1/pipelines')
    
    # Check response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 2
    assert data[0]["name"] == "test1"
    assert data[1]["name"] == "test2"
    
    # Verify mock was called
    mock_pipeline_manager.get_all_pipelines.assert_called_once()

@patch('cdc_gateway.app.pipeline_manager')
def test_create_pipeline(mock_pipeline_manager, client):
    # Setup mock
    mock_pipeline = {"id": "new-id", "name": "new-pipeline", "status": "CREATED"}
    mock_pipeline_manager.create_pipeline.return_value = mock_pipeline
    
    # Prepare request data
    pipeline_data = {
        "name": "new-pipeline",
        "source": {"type": "sqlserver-cdc", "config": {}},
        "sink": {"type": "kafka", "config": {}}
    }
    
    # Make request
    response = client.post(
        '/api/v1/pipelines',
        data=json.dumps(pipeline_data),
        content_type='application/json'
    )
    
    # Check response
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["name"] == "new-pipeline"
    assert data["status"] == "CREATED"
    assert data["id"] == "new-id"
    
    # Verify mock was called with correct data
    mock_pipeline_manager.create_pipeline.assert_called_once_with(pipeline_data)

@patch('cdc_gateway.app.pipeline_manager')
def test_start_pipeline(mock_pipeline_manager, client):
    # Setup mock
    pipeline_id = "test-id"
    mock_pipeline = {"id": pipeline_id, "name": "test", "status": "RUNNING", "flink_job_id": "job-123"}
    mock_pipeline_manager.start_pipeline.return_value = mock_pipeline
    
    # Make request
    response = client.post(f'/api/v1/pipelines/{pipeline_id}/start')
    
    # Check response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["id"] == pipeline_id
    assert data["status"] == "RUNNING"
    assert data["flink_job_id"] == "job-123"
    
    # Verify mock was called
    mock_pipeline_manager.start_pipeline.assert_called_once_with(pipeline_id)

@patch('cdc_gateway.app.pipeline_manager')
def test_pipeline_not_found(mock_pipeline_manager, client):
    # Setup mock to raise KeyError
    pipeline_id = "nonexistent-id"
    mock_pipeline_manager.get_pipeline.side_effect = KeyError(f"Pipeline {pipeline_id} not found")
    
    # Make request
    response = client.get(f'/api/v1/pipelines/{pipeline_id}')
    
    # Check response
    assert response.status_code == 404
    data = json.loads(response.data)
    assert "error" in data
    assert pipeline_id in data["error"]
