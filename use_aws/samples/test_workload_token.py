import boto3
import json
import asyncio
import time
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Failed to load config.json: {e}")
        return None

config = load_config()

def get_workload_access_token():
    """Get Workload Access Token from AWS Bedrock AgentCore"""
    try:
        region = config['region']
        
        client = boto3.client('bedrock-agentcore', region_name=region)
        
        # agentcore.json에서 ARN 읽기
        with open("agentcore.json", "r") as f:
            agent_config = json.load(f)
        
        agent_arn = agent_config['agent_runtime_arn']
        print(f"Agent ARN: {agent_arn}")
        
        # Extract workload name from ARN
        # arn:aws:bedrock-agentcore:us-west-2:262976740991:runtime/use_aws-mNoWe4GlnB
        # workload name is the "use_aws" part
        workload_name = agent_arn.split('/')[-1].split('-')[0]
        print(f"Workload Name: {workload_name}")
        
        # Request Workload Access Token
        response = client.get_workload_access_token(
            workloadName=workload_name
        )
        
        token = response['accessToken']
        print(f"✓ Workload Access Token obtained: {token[:20]}...{token[-20:] if len(token) > 40 else ''}")
        return token
        
    except Exception as e:
        print(f"❌ Failed to obtain Workload Access Token: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # Try different methods based on error message
        if "WorkloadIdentity is linked to a service" in str(e):
            print("⚠️  Workload is linked to a service, cannot get access token directly.")
            print("   Need to use different authentication method.")
        elif "AccessDeniedException" in str(e):
            print("⚠️  Access denied. Please check IAM permissions.")
        
        return None

def get_cognito_token():
    """Get authentication token using Cognito"""
    try:
        # Load settings from config.json
        with open("config.json", "r") as f:
            config = json.load(f)
        
        cognito_config = config['cognito']
        region = config['region']
        
        # Create temporary credentials using Cognito Identity Pool
        cognito_identity_client = boto3.client('cognito-identity', region_name=region)
        
        identity_pool_id = cognito_config['identity_pool_id']
        print(f"Using Cognito Identity Pool: {identity_pool_id}")
        
        # Get temporary credentials
        response = cognito_identity_client.get_id(
            IdentityPoolId=identity_pool_id
        )
        
        identity_id = response['IdentityId']
        print(f"Identity ID: {identity_id}")
        
        # Get temporary credentials
        credentials_response = cognito_identity_client.get_credentials_for_identity(
            IdentityId=identity_id
        )
        
        credentials = credentials_response['Credentials']
        
        # Create Bearer token (should be JWT token in practice)
        bearer_token = f"Bearer_{credentials['AccessKeyId']}_{credentials['SecretKey']}"
        
        print(f"✓ Cognito token created: {bearer_token[:20]}...{bearer_token[-20:] if len(bearer_token) > 40 else ''}")
        return bearer_token
        
    except Exception as e:
        print(f"❌ Failed to create Cognito token: {e}")
        print(f"Error type: {type(e).__name__}")
        return None

def test_with_iam_credentials():
    """Access AgentCore directly using AWS IAM credentials"""
    try:
        # Load settings from config.json
        with open("config.json", "r") as f:
            config = json.load(f)
        region = config['region']
        
        # Read ARN from agentcore.json
        with open("agentcore.json", "r") as f:
            agent_config = json.load(f)
        
        agent_arn = agent_config['agent_runtime_arn']
        print(f"Agent ARN: {agent_arn}")
        
        # Use AWS IAM credentials directly
        client = boto3.client('bedrock-agentcore', region_name=region)
        
        # MCP 초기화 메시지
        mcp_init_payload = {
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "mcp-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print("Attempting to call AgentCore with AWS IAM credentials...")
        session_id = f"test-session-iam-{int(time.time())}-{int(time.time() * 1000) % 1000000}"
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=json.dumps(mcp_init_payload)
        )
        
        print("✅ AgentCore call successful!")
        if 'response' in response:
            response_body = response['response'].read()
            print(f"Response: {response_body}")
            return True
            
    except Exception as e:
        print(f"❌ AgentCore call failed: {e}")
        print(f"Error type: {type(e).__name__}")
        return False

async def test_mcp_with_workload_token():
    """Access MCP using Workload Access Token or Cognito token"""
    
    # Get Workload Access Token
    token = get_workload_access_token()
    if not token:
        print("Cannot get Workload Access Token.")
        print("Trying Cognito token...")
        
        # Try Cognito token
        token = get_cognito_token()
        if not token:
            print("Cannot get Cognito token either.")
            return
    
    # Get region from config.json
    with open("config.json", "r") as f:
        config = json.load(f)
    region = config['region']
    
    # Read ARN from agentcore.json
    with open("agentcore.json", "r") as f:
        agent_config = json.load(f)
    
    agent_arn = agent_config['agent_runtime_arn']
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    
    # MCP endpoint URL (may be different path when using Workload Token)
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/mcp?qualifier=DEFAULT"
    
    headers = {
        "authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"Attempting MCP connection with Workload Token: {mcp_url}")
    print(f"Headers: {headers}")
    
    try:
        async with streamablehttp_client(mcp_url, headers, timeout=120, terminate_on_close=False) as (
            read_stream, write_stream, _,):
            
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.list_tools()
                print("✅ MCP connection successful!")
                print("Available tools:")
                print(json.dumps(tool_result, indent=2))
                
    except Exception as e:
        print(f"❌ MCP connection failed: {e}")
        print(f"Error type: {type(e).__name__}")

def test_agentcore_invoke_with_token():
    """Directly call AgentCore using Workload Token or Cognito token"""
    
    token = get_workload_access_token()
    if not token:
        print("Cannot get Workload Access Token.")
        print("Trying Cognito token...")
        
        # Try Cognito token
        token = get_cognito_token()
        if not token:
            print("Cannot get Cognito token either.")
            return
    
    try:
        # Get region from config.json
        with open("config.json", "r") as f:
            config = json.load(f)
        region = config['region']
        
        client = boto3.client('bedrock-agentcore', region_name=region)
        
        # Read ARN from agentcore.json
        with open("agentcore.json", "r") as f:
            agent_config = json.load(f)
        
        agent_arn = agent_config['agent_runtime_arn']
        
        # MCP initialization message
        mcp_init_payload = {
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "mcp-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print("Attempting to call AgentCore with Workload Token...")
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId="test-session-mcp",
            payload=json.dumps(mcp_init_payload),
            qualifier="DEFAULT"
        )
        
        print("✅ AgentCore call successful!")
        if 'response' in response:
            response_body = response['response'].read()
            print(f"Response: {response_body}")
            
    except Exception as e:
        print(f"❌ AgentCore call failed: {e}")

def main():
    print("=== AWS Bedrock AgentCore Workload Token Test ===\n")
    
    # Direct AgentCore call with Workload Token
    print("1. Direct AgentCore call with Workload Token...")
    test_agentcore_invoke_with_token()
    
    # MCP connection with Workload Token
    print("\n2. MCP connection with Workload Token...")
    asyncio.run(test_mcp_with_workload_token())
    
    # Direct call with AWS IAM credentials
    print("\n3. Direct call with AWS IAM credentials...")
    test_with_iam_credentials()

if __name__ == "__main__":
    main()
