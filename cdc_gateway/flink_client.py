"""
Client for interacting with Apache Flink REST API
"""
import os
import json
import time
import logging
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class FlinkClient:
    def __init__(self, jobmanager_host, jobmanager_port, config):
        self.jobmanager_host = jobmanager_host
        self.jobmanager_port = jobmanager_port
        self.config = config
        self.rest_port = config.get('restPort', 8081)
        # תיקון הנתיב הבסיסי ל-REST API - שינוי /v1 ל-/
        self.rest_base_url = f"http://{jobmanager_host}:{self.rest_port}"
        self.timeout = 30  # Default request timeout in seconds
        
        logger.info(f"Initialized Flink client with JobManager at {jobmanager_host}:{jobmanager_port}, "
                  f"REST API at {self.rest_base_url}")

    def _make_request(self, method, endpoint, **kwargs):
        """Make an HTTP request to Flink REST API"""
        url = urljoin(self.rest_base_url, endpoint)
        timeout = kwargs.pop('timeout', self.timeout)
        
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.RequestException as e:
            logger.error(f"Flink API request failed: {str(e)}")
            raise

    def get_jobs(self):
        """Get all jobs"""
        return self._make_request('GET', '/jobs')

    def get_job_details(self, job_id):
        """Get details for a specific job"""
        return self._make_request('GET', f'/jobs/{job_id}')

    def get_job_status(self, job_id):
        """Get status of a job"""
        response = self._make_request('GET', f'/jobs/{job_id}')
        return response.get('state', 'UNKNOWN')

    def cancel_job(self, job_id, savepoint=False):
        """Cancel a job"""
        if savepoint:
            # Cancel with savepoint
            data = {"targetDirectory": self.config.get('savepointDir', "s3://flink-savepoints/")}
            response = self._make_request('POST', f'/jobs/{job_id}/stop', json=data)
            logger.info(f"Cancelled job {job_id} with savepoint at {response.get('location')}")
            return response
        else:
            # Cancel without savepoint
            response = self._make_request('DELETE', f'/jobs/{job_id}')
            logger.info(f"Cancelled job {job_id} without savepoint")
            return response

    def deploy_sql_job(self, job_name, sql_statements, parallelism=1):
        """
        Deploy a Flink SQL job
        
        This is a simplified implementation. In a real-world scenario, you would use the
        Flink SQL REST API to submit SQL statements, but here we're simulating the process
        by creating a SQL script and deploying it using the Session API
        """
        logger.info(f"Deploying SQL job: {job_name}")
        
        try:
            # Create SQL session
            session_data = {"sessionName": job_name}
            session_response = self._make_request('POST', '/v1/sessions', json=session_data)
            session_handle = session_response.get('session_handle')
            logger.info(f"Created SQL session with handle: {session_handle}")
        
            # Execute SQL statements
            for i, sql in enumerate(sql_statements):
                logger.debug(f"Executing SQL statement {i+1}/{len(sql_statements)}")
                execute_data = {"statement": sql}
                operation_response = self._make_request(
                    'POST', 
                    f'/v1/sessions/{session_handle}/statements',
                    json=execute_data
                )
                operation_handle = operation_response.get('operation_handle')
                
                # Wait for statement execution to complete
                self._wait_for_operation_complete(session_handle, operation_handle)
        
            # Get last operation (pipeline) status - this should be the INSERT statement
            final_operation_handle = operation_handle
            status_response = self._make_request(
                'GET',
                f'/v1/sessions/{session_handle}/operations/{final_operation_handle}/status'
            )
            
            # Extract job ID from result
            if status_response.get('status') == 'RUNNING':
                # This is a bit of a hack - in a real implementation we would extract the job ID properly
                # For now, we'll simulate it by getting all running jobs
                jobs = self.get_jobs()
                running_jobs = jobs.get('jobs', [])
                # Find the most recently started job
                if running_jobs:
                    # Sort by start time (newest first)
                    latest_job = sorted(
                        [job for job in running_jobs if job.get('status') == 'RUNNING'],
                        key=lambda j: j.get('start-time', 0),
                        reverse=True
                    )
                    if latest_job:
                        job_id = latest_job[0].get('id')
                        logger.info(f"Deployed job {job_name} with job ID: {job_id}")
                        return job_id
            
            raise ValueError(f"Failed to deploy SQL job: {status_response}")
        except Exception as e:
            logger.error(f"Failed to deploy SQL job {job_name}: {str(e)}")
            # Clean up session
            try:
                if session_handle:
                    self._make_request('DELETE', f'/v1/sessions/{session_handle}')
            except:
                pass
            raise

    def _wait_for_operation_complete(self, session_handle, operation_handle, max_retries=30, retry_interval=1):
        """Wait for an operation to complete"""
        retries = 0
        while retries < max_retries:
            try:
                status_response = self._make_request(
                    'GET',
                    f'/v1/sessions/{session_handle}/operations/{operation_handle}/status'
                )
                
                status = status_response.get('status')
                
                if status in ['FINISHED', 'ERROR', 'CANCELED']:
                    if status == 'ERROR':
                        error = status_response.get('error', 'Unknown error')
                        raise ValueError(f"SQL operation failed: {error}")
                    return status_response
                
                time.sleep(retry_interval)
                retries += 1
            except Exception as e:
                logger.warning(f"Error checking operation status: {str(e)}")
                time.sleep(retry_interval)
                retries += 1
        
        raise TimeoutError(f"Operation timed out after {max_retries * retry_interval} seconds")