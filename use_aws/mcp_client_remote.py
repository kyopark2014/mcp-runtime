import asyncio
import os
import sys
import json
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import requests

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

def load_agent_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)    
    return config

def get_aws_auth_headers(url, method='GET'):
    """Generate AWS SigV4 authentication headers"""
    try:
        # Create AWS session
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if not credentials:
            print("Error: AWS credentials not found. Please configure AWS CLI or set environment variables.")
            return None
            
        # Generate SigV4 authentication headers
        auth = SigV4Auth(credentials, 'bedrock-agentcore', 'us-west-2')
        request = AWSRequest(method=method, url=url, data='')
        auth.add_auth(request)
        
        return dict(request.headers)
    except Exception as e:
        print(f"Error creating AWS auth headers: {e}")
        return None

def print_exception_details(e, level=0):
    """Recursively print all details of an exception"""
    indent = "  " * level
    print(f"{indent}Error type: {type(e).__name__}")
    print(f"{indent}Error message: {e}")
    
    # If it's an ExceptionGroup, also print sub-exceptions
    if hasattr(e, 'exceptions') and e.exceptions:
        print(f"{indent}Sub-exceptions ({len(e.exceptions)}):")
        for i, sub_exc in enumerate(e.exceptions):
            print(f"{indent}  {i+1}. ", end="")
            print_exception_details(sub_exc, level + 1)
    
    # If __cause__ exists
    if hasattr(e, '__cause__') and e.__cause__:
        print(f"{indent}Caused by: ", end="")
        print_exception_details(e.__cause__, level + 1)

agent_config = load_agent_config()
agentRuntimeArn = agent_config['agent_runtime_arn']
print(f"agentRuntimeArn: {agentRuntimeArn}")

async def main():
    agent_arn = agentRuntimeArn
    
    # Bearer token is required - get from environment variable or AWS Secrets Manager
    bearer_token = os.getenv('BEARER_TOKEN')
    
    if not bearer_token:
        print("Error: BEARER_TOKEN environment variable is required")
        print("Please set BEARER_TOKEN environment variable or configure AWS Secrets Manager")
        sys.exit(1)
    
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    # Use the correct endpoint URL
    mcp_url = f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    print("Using Bearer token authentication")
    
    print(f"Invoking: {mcp_url}")
    print(f"Headers: {headers}\n")

    try:
        async with streamablehttp_client(mcp_url, headers, timeout=120, terminate_on_close=False) as (
            read_stream, write_stream,_,):

            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.list_tools()
                print("Available tools:")
                print(json.dumps(tool_result, indent=2))
                
    except Exception as e:
        print(f"Error connecting to MCP server:")
        print_exception_details(e)
        
        print("\nTroubleshooting tips:")
        print("1. Ensure BEARER_TOKEN environment variable is set")
        print("2. Check if the agent runtime ARN is correct")
        print("3. Verify you have permissions to access this agent runtime")
        print("4. Check if the agent runtime is active and running")
        print("5. Verify the Bearer token is valid and not expired")

if __name__ == "__main__":
    asyncio.run(main())