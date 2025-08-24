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

def load_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)    
    return config

def get_aws_auth_headers(url, method='GET', body=''):
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
        request = AWSRequest(method=method, url=url, data=body)
        auth.add_auth(request)
        
        return dict(request.headers)
    except Exception as e:
        print(f"Error creating AWS auth headers: {e}")
        return None

def check_agent_runtime_status(agent_arn, region):
    """Check if we can access AWS services (simplified check)"""
    try:
        session = boto3.Session()
        
        # Test basic AWS connectivity with a simple service call
        try:
            sts_client = session.client('sts', region_name=region)
            identity = sts_client.get_caller_identity()
            print(f"AWS Identity verified: {identity.get('Arn', 'Unknown')}")
            return True
        except Exception as e:
            print(f"AWS connectivity test failed: {e}")
            return False
            
    except Exception as e:
        print(f"Error checking AWS connectivity: {e}")
        return False

def get_cognito_bearer_token(config):
    """Get a fresh bearer token from Cognito"""
    try:
        import boto3
        
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
        id_token = auth_result['IdToken']
        
        print("Successfully obtained fresh Cognito tokens")
        return access_token, id_token
        
    except Exception as e:
        print(f"Error getting Cognito token: {e}")
        return None, None

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

def test_basic_connection(url, headers):
    """Test basic HTTP connection before attempting MCP"""
    print(f"\n=== Basic Connection Test ===")
    print(f"URL: {url}")
    
    try:
        # Simple GET request to test connectivity
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Basic connection test response: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        if response.text:
            print(f"Response body (first 200 chars): {response.text[:200]}")
        return response.status_code < 500  # Accept 4xx errors as "connection successful"
    except requests.exceptions.Timeout:
        print("❌ Basic connection timeout (10s)")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Basic connection failed - network issue")
        return False
    except Exception as e:
        print(f"❌ Basic connection error: {e}")
        return False

agent_config = load_config()
agentRuntimeArn = agent_config['agent_runtime_arn']
print(f"agentRuntimeArn: {agentRuntimeArn}")

async def main():
    agent_arn = agentRuntimeArn
    region = agent_config['region']
    
    # Check basic AWS connectivity
    print("Checking AWS connectivity...")
    if not check_agent_runtime_status(agent_arn, region):
        print("AWS connectivity check failed. Please check your AWS credentials.")
        return
    
    # Try to get fresh bearer token from Cognito
    print("Getting fresh bearer token from Cognito...")
    access_token, id_token = get_cognito_bearer_token(agent_config)
    
    if not access_token:
        print("Failed to get fresh token from Cognito, trying stored token...")
        # Fallback to stored token
        try:
            secret_name = 'mcp_server/cognito/credentials'
            session = boto3.Session()
            client = session.client('secretsmanager', region_name=region)
            response = client.get_secret_value(SecretId=secret_name)
            bearer_token_raw = response['SecretString']
            
            # Parse bearer token from JSON if needed
            try:
                bearer_token_data = json.loads(bearer_token_raw)
                if isinstance(bearer_token_data, dict):
                    # Try access_token first (preferred for MCP), then bearer_token, then id_token
                    if 'access_token' in bearer_token_data:
                        bearer_token = bearer_token_data['access_token']
                        print("Using stored Access Token for authentication")
                    elif 'bearer_token' in bearer_token_data:
                        bearer_token = bearer_token_data['bearer_token']
                        print("Using stored Bearer Token for authentication")
                    elif 'id_token' in bearer_token_data:
                        bearer_token = bearer_token_data['id_token']
                        print("Using stored ID Token for authentication")
                    else:
                        bearer_token = bearer_token_raw
                        print("Using raw stored token for authentication")
                else:
                    bearer_token = bearer_token_raw
                    print("Using raw stored token for authentication")
            except json.JSONDecodeError:
                bearer_token = bearer_token_raw
                print("Using raw stored token for authentication")
        except Exception as e:
            print(f"Error getting stored token: {e}")
            print("Please ensure you have a valid bearer token configured")
            return
    else:
        bearer_token = access_token
        print("Using fresh Access Token for authentication")
    
    # Remove duplicate "Bearer " prefix if present
    if bearer_token.startswith('Bearer '):
        bearer_token = bearer_token[7:]  # Remove "Bearer " prefix
    
    if not bearer_token:
        print("Error: No bearer token available")
        print("Please configure Cognito credentials or set up AWS Secrets Manager")
        sys.exit(1)
    
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    
    # Try different endpoint URLs based on common patterns
    test_urls = [
        # Standard MCP endpoints
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/mcp",
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/mcp?qualifier=DEFAULT",
        # Alternative invocation endpoints
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations",
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT",
        # Try without encoding
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{agent_arn}/mcp",
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{agent_arn}/invocations",
    ]
    
    print(f"Testing endpoint URLs:")
    for i, url in enumerate(test_urls):
        print(f"  {i+1}. {url}")
    
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
    
    # Try different authentication methods
    auth_methods = [
        {
            "name": "Bearer Token (OAuth)",
            "headers": {
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        },
        {
            "name": "AWS SigV4",
            "headers": None  # Will be generated per request
        }
    ]
    
    successful_url = None
    successful_headers = None
    
    # Try each authentication method with each endpoint
    for auth_method in auth_methods:
        print(f"\n=== Testing {auth_method['name']} Authentication ===")
        
        for i, test_url in enumerate(test_urls):
            print(f"\nTest {i+1}: {test_url}")
            
            # Generate headers for this request
            if auth_method['name'] == "AWS SigV4":
                headers = get_aws_auth_headers(test_url, 'POST', request_body)
                if not headers:
                    print("Failed to generate SigV4 headers, skipping...")
                    continue
                headers.update({
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                })
            else:
                headers = auth_method['headers']
            
            try:
                test_response = requests.post(
                    test_url,
                    headers=headers,
                    data=request_body,
                    timeout=30
                )
                print(f"Response status: {test_response.status_code}")
                print(f"Response content: {test_response.text[:200]}...")
                
                if test_response.status_code == 200:
                    print("✓ Success!")
                    successful_url = test_url
                    successful_headers = headers
                    break
                elif test_response.status_code in [401, 403]:
                    print(f"⚠ Authentication error: {test_response.status_code}")
                elif test_response.status_code == 404:
                    print("⚠ Endpoint not found")
                else:
                    print(f"⚠ Error: {test_response.status_code}")
                    
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                continue
        
        if successful_url:
            break
    
    if not successful_url:
        print("\nAll endpoints and authentication methods failed.")
        print("\nTroubleshooting suggestions:")
        print("1. Verify the agent runtime ARN is correct")
        print("2. Check if the agent runtime is deployed and active")
        print("3. Ensure your AWS credentials have the necessary permissions")
        print("4. Verify the Cognito configuration is correct")
        print("5. Check if the bearer token is valid and not expired")
        print("6. Confirm the region is correct")
        return
    
    mcp_url = successful_url
    headers = successful_headers
    print(f"\nSuccessful endpoint: {mcp_url}")
    print(f"Using headers: {headers}")

    # Test basic connection first
    if not test_basic_connection(mcp_url, headers):
        print("Basic connection test failed. Not attempting MCP connection.")
        return

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
                    print("❌ session.initialize() timeout (30s)")
                    return
                except Exception as init_error:
                    print(f"❌ session.initialize() failed: {init_error}")
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
                    print("❌ session.list_tools() timeout (30s)")
                    return
                except Exception as tools_error:
                    print(f"❌ session.list_tools() failed: {tools_error}")
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
                
    except asyncio.TimeoutError:
        print("❌ MCP connection timeout (120s)")
        print("Possible causes:")
        print("- Network connectivity issues")
        print("- Agent Runtime not responding")
        print("- Authentication token expired")
    except Exception as e:
        print(f"❌ MCP connection failed:")
        print_exception_details(e)
        
        print("\nTroubleshooting tips:")
        print("1. Ensure bearer token is valid and not expired")
        print("2. Check if the agent runtime ARN is correct")
        print("3. Verify you have permissions to access this agent runtime")
        print("4. Check if the agent runtime is active and running")
        print("5. Verify AWS credentials and IAM permissions")
        print("6. Verify the agent runtime is in the correct region")
        print("7. Check network connectivity to AWS endpoints")

if __name__ == "__main__":
    asyncio.run(main())
