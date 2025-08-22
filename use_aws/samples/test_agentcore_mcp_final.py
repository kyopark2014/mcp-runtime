import boto3
import json
import asyncio
import requests
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

def test_agentcore_mcp_endpoint():
    """Test AgentCore MCP endpoint using various methods"""
    
    agent_arn = config['agent_runtime_arn']
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    
    # Test various endpoint URLs
    test_urls = [
        f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/mcp?qualifier=DEFAULT",
        f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT",
        f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/mcp",
        f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/invocations"
    ]
    
    # Test various authentication methods
    auth_methods = [
        # Bearer token
        {"authorization": "Bearer Bearer_NeYnJ3GJ83C6QLqvCLRO6WoE", "Content-Type": "application/json"},
        
        # AWS SigV4 authentication
        None,  # boto3 will handle automatically
        
        # Empty headers
        {"Content-Type": "application/json"}
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n=== Test {i}: {url} ===")
        
        for j, headers in enumerate(auth_methods, 1):
            print(f"  Auth method {j}: {headers}")
            
            try:
                if headers is None:
                    # Use AWS SigV4 authentication
                    session = boto3.Session()
                    credentials = session.get_credentials()
                    
                    if credentials:
                        # Authenticated request using boto3
                        client = boto3.client('bedrock-agentcore', region_name='us-west-2')
                        # Test with different method here
                        response = requests.get(url, timeout=10)
                    else:
                        response = requests.get(url, timeout=10)
                else:
                    response = requests.get(url, headers=headers, timeout=10)
                
                print(f"    Status code: {response.status_code}")
                print(f"    Response: {response.text[:200]}...")
                
                if response.status_code == 200:
                    print(f"    ✅ Success!")
                    return url, headers
                    
            except Exception as e:
                print(f"    ❌ Failed: {e}")
    
    return None, None

async def test_mcp_protocol():
    """Access AgentCore using MCP protocol"""
    
    # Read ARN from agentcore.json
    with open("agentcore.json", "r") as f:
        config = json.load(f)
    
    agent_arn = config['agent_runtime_arn']
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    
    # Find successful URL and headers
    success_url, success_headers = test_agentcore_mcp_endpoint()
    
    if not success_url:
        print("❌ All endpoint tests failed")
        return
    
    print(f"\nSuccessful endpoint: {success_url}")
    print(f"Successful headers: {success_headers}")
    
    # Test MCP protocol
    try:
        async with streamablehttp_client(success_url, success_headers or {}, timeout=120, terminate_on_close=False) as (
            read_stream, write_stream, _,):
            
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.list_tools()
                print("✅ MCP protocol connection successful!")
                print("Available tools:")
                print(json.dumps(tool_result, indent=2))
                
    except Exception as e:
        print(f"❌ MCP protocol connection failed: {e}")

def check_agentcore_capabilities():
    """Check AgentCore capabilities"""
    
    try:
        client = boto3.client('bedrock-agentcore', region_name='us-west-2')
        
        # Read ARN from agentcore.json
        with open("agentcore.json", "r") as f:
            config = json.load(f)
        
        agent_arn = config['agent_runtime_arn']
        
        print("=== AgentCore Capabilities Check ===")
        
        # Available operations
        print("Available operations:")
        for operation in client.meta.service_model.operation_names:
            print(f"  - {operation}")
        
        # Test specific operations
        print("\n=== Specific Operation Tests ===")
        
        # ListSessions test
        try:
            response = client.list_sessions(
                memoryId="test-memory",
                actorId="test-actor"
            )
            print("✅ ListSessions successful")
        except Exception as e:
            print(f"❌ ListSessions failed: {e}")
        
        # GetEvent test
        try:
            response = client.get_event(
                memoryId="test-memory",
                actorId="test-actor",
                eventId="test-event"
            )
            print("✅ GetEvent successful")
        except Exception as e:
            print(f"❌ GetEvent failed: {e}")
            
    except Exception as e:
        print(f"AgentCore capabilities check failed: {e}")

def main():
    print("=== AWS Bedrock AgentCore MCP Final Test ===\n")
    
    # Check AgentCore capabilities
    check_agentcore_capabilities()
    
    # Test MCP protocol
    print("\n=== MCP Protocol Test ===")
    asyncio.run(test_mcp_protocol())

if __name__ == "__main__":
    main()
