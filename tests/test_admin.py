# תיקון עבור tests/test_admin.py

import json
import pytest
from unittest.mock import patch, MagicMock
from cdc_gateway.admin import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@patch('cdc_gateway.admin.pipeline_manager')
def test_health_endpoint(mock_pipeline_manager, client):
    # Make request
    response = client.get('/health')
    
    # Check response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "UP"
    assert data["service"] == "CDC Gateway Admin"

@patch('cdc_gateway.admin.generate_latest')
def test_metrics_endpoint(mock_generate_latest, client):
    # Setup mock
    mock_generate_latest.return_value = b'metric_name{label="value"} 1.0'
    
    # Make request
    response = client.get('/metrics')
    
    # Check response
    assert response.status_code == 200
    assert response.data == b'metric_name{label="value"} 1.0'
    assert response.headers['Content-Type'] == 'text/plain; version=0.0.4; charset=utf-8'
    
    # Verify mock was called
    mock_generate_latest.assert_called_once()

@patch('cdc_gateway.admin.os.path.exists')
@patch('cdc_gateway.admin.os.listdir')
@patch('cdc_gateway.admin.psutil.virtual_memory')
@patch('cdc_gateway.admin.psutil.cpu_percent')
@patch('cdc_gateway.admin.os.uname')
@patch('cdc_gateway.admin.pipeline_manager', None)  # Explicitly set pipeline_manager to None for test
def test_info_endpoint(mock_uname, mock_cpu_percent, mock_virtual_memory, 
                     mock_listdir, mock_path_exists, client):
    # Setup mocks
    mock_path_exists.return_value = True
    mock_listdir.return_value = ["pipeline1.json", "pipeline2.json", "not-a-pipeline.txt"]
    
    mock_memory = MagicMock()
    mock_memory.used = 1024 * 1024 * 100  # 100 MB
    mock_virtual_memory.return_value = mock_memory
    
    mock_cpu_percent.return_value = 25.5
    
    mock_uname_result = MagicMock()
    mock_uname_result.nodename = "test-host"
    mock_uname.return_value = mock_uname_result
    
    # Make request
    response = client.get('/info')
    
    # Check response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["version"] == "0.7.0"
    assert data["name"] == "Apache Flink CDC Gateway"
    assert data["pipelines"]["total"] == 2  # Only counts .json files