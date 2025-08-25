import asyncio
import os
import json
import boto3
import requests

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

def load_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)    
    return config

config = load_config()

projectName = config['projectName']
region = config['region']

def get_cognito_bearer_token(config):
    """Get a fresh bearer token from Cognito"""
    try:
        cognito_config = config['cognito']
        region = cognito_config['region']
        client_id = cognito_config['client_id']
        username = cognito_config['test_username']
        password = cognito_config['test_password']
        
        # Create Cognito client
        client = boto3.client('cognito-idp', region_name=region)
        
        # Authenticate and get tokens
        response = client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        
        auth_result = response['AuthenticationResult']
        access_token = auth_result['AccessToken']
        # id_token = auth_result['IdToken']
        
        print("Successfully obtained fresh Cognito tokens")
        return access_token
        
    except Exception as e:
        print(f"Error getting Cognito token: {e}")
        return None, None

def get_bearer_token():
    try:
        secret_name = f'{projectName}/cognito/credentials'
        session = boto3.Session()
        client = session.client('secretsmanager', region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        bearer_token_raw = response['SecretString']
        
        token_data = json.loads(bearer_token_raw)        
        if 'bearer_token' in token_data:
            bearer_token = token_data['bearer_token']
            return bearer_token
        else:
            print("No bearer token found in secret manager")
            return None
    
    except Exception as e:
        print(f"Error getting stored token: {e}")
        return None

def save_bearer_token(bearer_token):
    try:
        secret_name = f'{config["projectName"]}/cognito/credentials'

        session = boto3.Session()
        client = session.client('secretsmanager', region_name=region)
        
        # Create secret value with bearer_key 
        secret_value = {
            "bearer_key": "mcp_server_bearer_token",
            "bearer_token": bearer_token
        }
        
        # Convert to JSON string
        secret_string = json.dumps(secret_value)
        
        # Check if secret already exists
        try:
            client.describe_secret(SecretId=secret_name)
            # Secret exists, update it
            client.put_secret_value(
                SecretId=secret_name,
                SecretString=secret_string
            )
            print(f"Bearer token updated in secret manager with key: {secret_value['bearer_key']}")
        except client.exceptions.ResourceNotFoundException:
            # Secret doesn't exist, create it
            client.create_secret(
                Name=secret_name,
                SecretString=secret_string,
                Description="MCP Server Cognito credentials with bearer key and token"
            )
            print(f"Bearer token created in secret manager with key: {secret_value['bearer_key']}")
            
    except Exception as e:
        print(f"Error saving bearer token: {e}")

async def main():
    agent_arn = config['agent_runtime_arn']
    region = config['region']
    
    # Check basic AWS connectivity
    bearer_token = get_bearer_token()
    print(f"Bearer token from secret manager: {bearer_token}")

    if not bearer_token:    
        # Try to get fresh bearer token from Cognito
        print("No bearer token found in secret manager, getting fresh bearer token from Cognito...")
        bearer_token = get_cognito_bearer_token(config)
        print(f"Bearer token from cognito: {bearer_token}")
        
        save_bearer_token(bearer_token)
                
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    
    # Try different endpoint URLs based on common patterns
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    # Prepare the request body for MCP initialization
    request_body = json.dumps({
        "jsonrpc": "2.0",
        "id": "1",
        "method": "initialize", 
        "params": {
            "protocolVersion": "2024-11-05", 
            "capabilities": {}, 
            "clientInfo": {
                "name": "test-client", 
                "version": "1.0.0"
            }
        }
    })
    
    successful_url = None
    successful_headers = None
    
    # url test
    try:
        response = requests.post(
            mcp_url,
            headers=headers,
            data=request_body,
            timeout=30
        )
        
        if response.status_code == 200:
            print("Success!")
            successful_url = mcp_url
            successful_headers = headers            
        else:
            print(f"Error: {response.status_code}")            
    except Exception as e:
        print(f"Connection failed: {e}")

    mcp_url = successful_url
    headers = successful_headers

    try:
        print(f"\n=== Attempting MCP Connection ===")
        print(f"URL: {mcp_url}")
        print(f"Timeout: 120 seconds")
        
        # Now try the MCP connection with better error handling
        print("1. Attempting streamablehttp_client connection...")
        async with streamablehttp_client(mcp_url, headers, timeout=120, terminate_on_close=False) as (
            read_stream, write_stream, _):
            
            print("2. streamablehttp_client connection successful!")
            print("3. Creating ClientSession...")
            
            async with ClientSession(read_stream, write_stream) as session:
                print("4. ClientSession created successfully!")
                print("5. Calling session.initialize()...")
                
                # Add timeout for initialize
                try:
                    await asyncio.wait_for(session.initialize(), timeout=30)
                    print("6. session.initialize() successful!")
                except asyncio.TimeoutError:
                    print("session.initialize() timeout (30s)")
                    return
                except Exception as init_error:
                    print(f"session.initialize() failed: {init_error}")
                    return
                
                print("7. Calling session.list_tools()...")
                
                # Add timeout for list_tools
                try:
                    tool_result = await asyncio.wait_for(session.list_tools(), timeout=30)
                    print(f"8. session.list_tools() successful!")
                    print(f"\nAvailable tools: {len(tool_result.tools)}")
                    for tool in tool_result.tools:
                        print(f"  - {tool.name}: {tool.description[:100]}...")
                except asyncio.TimeoutError:
                    print("session.list_tools() timeout (30s)")
                    return
                except Exception as tools_error:
                    print(f"session.list_tools() failed: {tools_error}")
                    return
                                
                # Test add_numbers function
                print("\n=== Testing add_numbers function ===")
                params = {
                    "a": 15,
                    "b": 3
                }
                
                result = await session.call_tool("add_numbers", params)
                print(f"Add result: {result}")
                
                if hasattr(result, 'content') and result.content:
                    for content in result.content:
                        if hasattr(content, 'text'):
                            print(f"Content: {content.text}")
                
                # Test multiply_numbers function
                print("\n=== Testing multiply_numbers function ===")
                multiply_params = {
                    "a": 4,
                    "b": 7
                }
                
                multiply_result = await session.call_tool("multiply_numbers", multiply_params)
                print(f"Multiply result: {multiply_result}")
                
                if hasattr(multiply_result, 'content') and multiply_result.content:
                    for content in multiply_result.content:
                        if hasattr(content, 'text'):
                            print(f"Content: {content.text}")
                
                # Test greet_user function
                print("\n=== Testing greet_user function ===")
                greet_params = {
                    "name": "World"
                }
                
                greet_result = await session.call_tool("greet_user", greet_params)
                print(f"Greet result: {greet_result}")
                
                if hasattr(greet_result, 'content') and greet_result.content:
                    for content in greet_result.content:
                        if hasattr(content, 'text'):
                            print(f"Content: {content.text}")
                
                print("\n=== MCP Connection Test Complete ===")
                
    except Exception as e:
        print(f"MCP connection failed: {e}")
        
if __name__ == "__main__":
    asyncio.run(main())
