import boto3
import json

def create_aws_secrets():
    """
    Creates three AWS Secrets Manager secrets for dev, test, and prod environments
    with the same database configuration.
    """
    
    # Database configuration
    db_config = {
        "DB_HOST": "dst-dashboard-database-fast.ckqboenmhdca.us-east-1.rds.amazonaws.com",
        "DB_PORT": "5432",
        "DB_NAME": "pipeline_management",
        "DB_USER": "postgres",
        "DB_PASSWORD": "Dashboard2025!$"
    }

    # Initialize AWS Secrets Manager client
    client = boto3.client('secretsmanager')

    # Create secrets for each environment
    environments = ["dev", "test", "prod"]

    for env in environments:
        secret_name = f"dst-pipeline-db-config-{env}"
        
        try:
            response = client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(db_config),
                Description=f"Database configuration for {env} environment"
            )
            print(f"Created secret: {secret_name}")
            
        except client.exceptions.ResourceExistsException:
            print(f"Secret {secret_name} already exists")
            
        except Exception as e:
            print(f"Failed to create {secret_name}: {e}")

# Run the function
if __name__ == "__main__":
    create_aws_secrets()