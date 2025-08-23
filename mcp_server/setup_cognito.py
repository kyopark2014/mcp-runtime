import time
import os
import json
import sys
import boto3
import json

from utils import setup_cognito_user_pool
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session

def load_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    return config

config = load_config()

# Get the current notebook's directory
current_dir = os.path.dirname(os.path.abspath('__file__' if '__file__' in globals() else '.'))

print("Setting up Amazon Cognito user pool...")
cognito_config = setup_cognito_user_pool()
print("Cognito setup completed ✓")
print(f"User Pool ID: {cognito_config.get('user_pool_id', 'N/A')}")
print(f"Client ID: {cognito_config.get('client_id', 'N/A')}")

boto_session = Session()
region = boto_session.region_name
print(f"Using AWS region: {region}")

# Configuring AgentCore Runtime Deployment
def configure_agentcore_runtime():    
    agentcore_runtime = Runtime()

    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [
                config['cognito']['client_id']
            ],
            "discoveryUrl": cognito_config['discovery_url'],
        }
    }

    print("Configuring AgentCore Runtime...")
    response = agentcore_runtime.configure(
        entrypoint="mcp_server.py",
        auto_create_execution_role=True,
        auto_create_ecr=True,
        requirements_file="requirements.txt",
        region=region,
        authorizer_configuration=auth_config,
        protocol="MCP",
        agent_name="mcp_server_agentcore"
    )
    print("Configuration completed ✓")

    return agentcore_runtime

# Launching MCP Server to AgentCore Runtime
def launch_mcp_server(agentcore_runtime):
    print("Launching MCP server to AgentCore Runtime...")
    print("This may take several minutes...")
    launch_result = agentcore_runtime.launch()
    print("Launch completed ✓")
    print(f"Agent ARN: {launch_result.agent_arn}")
    print(f"Agent ID: {launch_result.agent_id}")

    return launch_result

def check_agentcore_runtime_status(agentcore_runtime):
    print("Checking AgentCore Runtime status...")
    status_response = agentcore_runtime.status()
    status = status_response.endpoint['status']
    print(f"Initial status: {status}")

    end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
    while status not in end_status:
        print(f"Status: {status} - waiting...")
        time.sleep(10)
        status_response = agentcore_runtime.status()
        status = status_response.endpoint['status']

    if status == 'READY':
        print("✓ AgentCore Runtime is READY!")
    else:
        print(f"⚠ AgentCore Runtime status: {status}")
        
    print(f"Final status: {status}")

# Storing Configuration for Remote Access
def store_config_for_remote_access(launch_result):
    ssm_client = boto3.client('ssm', region_name=region)
    secrets_client = boto3.client('secretsmanager', region_name=region)

    try:
        cognito_credentials_response = secrets_client.create_secret(
            Name='mcp_server/cognito/credentials',
            Description='Cognito credentials for MCP server',
            SecretString=json.dumps(cognito_config)
        )
        print("✓ Cognito credentials stored in Secrets Manager")
    except secrets_client.exceptions.ResourceExistsException:
        secrets_client.update_secret(
            SecretId='mcp_server/cognito/credentials',
            SecretString=json.dumps(cognito_config)
        )
        print("✓ Cognito credentials updated in Secrets Manager")

    agent_arn_response = ssm_client.put_parameter(
        Name='/mcp_server/runtime/agent_arn',
        Value=launch_result.agent_arn,
        Type='String',
        Description='Agent ARN for MCP server',
        Overwrite=True
    )
    print("✓ Agent ARN stored in Parameter Store")

    print("\nConfiguration stored successfully!")
    print(f"Agent ARN: {launch_result.agent_arn}")

def main():
    agentcore_runtime = configure_agentcore_runtime()
    launch_result = launch_mcp_server(agentcore_runtime)
    check_agentcore_runtime_status(agentcore_runtime)
    store_config_for_remote_access(launch_result)

if __name__ == "__main__":
    main()