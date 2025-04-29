# tests/test_flink_client.py
import pytest
import json
from unittest.mock import patch, MagicMock
from cdc_gateway.flink_client import FlinkClient

class TestFlinkClient:
    @pytest.fixture
    def flink_client(self):
        config = {
            "restPort": 8081,
            "savepointDir": "s3://test-bucket/savepoints"
        }
        return FlinkClient("localhost", 6123, config)
    
    @patch('cdc_gateway.flink_client.requests.request')
    def test_get_jobs(self, mock_request, flink_client):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.content = b''  # Empty response
        mock_response.json.return_value = None
        mock_request.return_value = mock_response
        
        # Call method
        result = flink_client.cancel_job("job-1", savepoint=False)
        
        # Check result
        assert result is None
        
        # Verify request was made correctly
        mock_request.assert_called_once_with(
            'DELETE', 
            'http://localhost:8081/v1/jobs/job-1', 
            timeout=30
        )
    
    @patch('cdc_gateway.flink_client.requests.request')
    @patch('cdc_gateway.flink_client.time.sleep')
    def test_deploy_sql_job(self, mock_sleep, mock_request, flink_client):
        # Setup mock responses for different API calls
        # 1. Create SQL session
        session_response = MagicMock()
        session_response.content = json.dumps({"session_handle": "session-123"}).encode()
        session_response.json.return_value = {"session_handle": "session-123"}
        
        # 2. Execute SQL statement
        operation_response = MagicMock()
        operation_response.content = json.dumps({"operation_handle": "op-123"}).encode()
        operation_response.json.return_value = {"operation_handle": "op-123"}
        
        # 3. Check operation status
        status_response = MagicMock()
        status_response.content = json.dumps({"status": "RUNNING"}).encode()
        status_response.json.return_value = {"status": "RUNNING"}
        
        # 4. Get jobs
        jobs_response = MagicMock()
        jobs_response.content = json.dumps({
            "jobs": [
                {"id": "job-123", "status": "RUNNING", "start-time": 1000}
            ]
        }).encode()
        jobs_response.json.return_value = {
            "jobs": [
                {"id": "job-123", "status": "RUNNING", "start-time": 1000}
            ]
        }
        
        # Set responses for different requests
        mock_request.side_effect = [
            session_response,    # Create session
            operation_response,  # Execute SQL 1
            status_response,     # Check status 1
            operation_response,  # Execute SQL 2
            status_response,     # Check status 2
            operation_response,  # Execute SQL 3
            status_response,     # Check status 3
            status_response,     # Final operation status
            jobs_response        # Get jobs
        ]
        
        # Call method with test SQL statements
        sql_statements = [
            "CREATE TABLE source (...)",
            "CREATE TABLE sink (...)",
            "INSERT INTO sink SELECT * FROM source"
        ]
        result = flink_client.deploy_sql_job("test-job", sql_statements)
        
        # Check result
        assert result == "job-123"
        
        # Verify requests were made correctly (can't check all detailed calls but can verify count)
        assert mock_request.call_count == 9