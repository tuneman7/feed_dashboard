import psycopg2
import boto3
import json
from typing import Optional

class PipelineDatabase:
    def __init__(self, environment: str):
        """
        Initialize database connection using AWS Secrets Manager.
        
        Args:
            environment (str): Environment ('dev', 'test', or 'prod')
        """
        self.environment = environment
        self.connection = None
        self._connect()
    
    def _get_secrets(self) -> dict:
        """Get database configuration from AWS Secrets Manager."""
        secret_name = f"dst-pipeline-db-config-{self.environment}"
        
        client = boto3.client('secretsmanager', region_name='us-east-1')
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    
    def _connect(self):
        """Create database connection."""
        config = self._get_secrets()
        
        self.connection = psycopg2.connect(
            host=config['DB_HOST'],
            port=config['DB_PORT'],
            database=config['DB_NAME'],
            user=config['DB_USER'],
            password=config['DB_PASSWORD']
        )
        self.connection.autocommit = True
    
    def start_pipeline_run(self, pipeline_tag: str) -> int:
        """
        Start a new pipeline run.
        
        Args:
            pipeline_tag (str): Pipeline tag identifier
            
        Returns:
            int: pipeline_run_id
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT start_pipeline_run(%s, %s)",
                (self.environment, pipeline_tag)
            )
            result = cursor.fetchone()
            return result[0]
    
    def complete_pipeline_run(self, pipeline_run_id: int, status: str) -> bool:
        """
        Complete a pipeline run.
        
        Args:
            pipeline_run_id (int): Pipeline run ID
            status (str): 'success' or 'failure'
            
        Returns:
            bool: True if successful
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT complete_pipeline_run(%s, %s)",
                (pipeline_run_id, status)
            )
            result = cursor.fetchone()
            return result[0]
    
    def add_pipeline_run_detail(self, pipeline_run_id: int, common_cd: str, 
                               detail_data: str, detail_desc: Optional[str] = None) -> int:
        """
        Add a detail record to a pipeline run.
        
        Args:
            pipeline_run_id (int): Pipeline run ID
            common_cd (str): Common code for detail type
            detail_data (str): Detail data (JSON string or text)
            detail_desc (str, optional): Detail description
            
        Returns:
            int: detail_id
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT add_pipeline_run_detail(%s, %s, %s, %s)",
                (pipeline_run_id, common_cd, detail_data, detail_desc)
            )
            result = cursor.fetchone()
            return result[0]
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Example usage
if __name__ == "__main__":
    with PipelineDatabase('dev') as db:
        # Start a pipeline run
        run_id = db.start_pipeline_run('test_pipeline_123')
        print(f"Started pipeline run: {run_id}")
        
        # Add some details
        detail_id = db.add_pipeline_run_detail(
            run_id, 
            'START', 
            '{"timestamp": "2025-01-01T00:00:00Z"}',
            'Pipeline execution started'
        )
        print(f"Added detail: {detail_id}")
        
        # Complete the run
        success = db.complete_pipeline_run(run_id, 'success')
        print(f"Completed pipeline run: {success}")