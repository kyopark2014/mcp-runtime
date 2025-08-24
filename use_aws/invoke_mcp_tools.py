import asyncio
import boto3
import json
import sys
import os
from boto3.session import Session
from datetime import timedelta

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

def load_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)    
    return config

async def main():
    # Load configuration
    agent_config = load_config()
    agent_arn = agent_config['agent_runtime_arn']
    region = agent_config['region']
    
    print(f"Using AWS region: {region}")
    print(f"Agent ARN: {agent_arn}")
    
    try:
        # Get bearer token from Secrets Manager
        secrets_client = boto3.client('secretsmanager', region_name=region)
        secret_name = 'mcp_server/cognito/credentials'
        response = secrets_client.get_secret_value(SecretId=secret_name)
        bearer_token_raw = response['SecretString']
        
        # Parse bearer token from JSON if needed
        try:
            bearer_token_data = json.loads(bearer_token_raw)
            if isinstance(bearer_token_data, dict):
                # Try access_token first (preferred for MCP), then bearer_token, then id_token
                if 'access_token' in bearer_token_data:
                    bearer_token = bearer_token_data['access_token']
                    print("Using Access Token for authentication")
                elif 'bearer_token' in bearer_token_data:
                    bearer_token = bearer_token_data['bearer_token']
                    print("Using Bearer Token for authentication")
                elif 'id_token' in bearer_token_data:
                    bearer_token = bearer_token_data['id_token']
                    print("Using ID Token for authentication")
                else:
                    bearer_token = bearer_token_raw
                    print("Using raw token for authentication")
            else:
                bearer_token = bearer_token_raw
                print("Using raw token for authentication")
        except json.JSONDecodeError:
            bearer_token = bearer_token_raw
            print("Using raw token for authentication")
        
        # Remove duplicate "Bearer " prefix if present
        if bearer_token.startswith('Bearer '):
            bearer_token = bearer_token[7:]  # Remove "Bearer " prefix
        
        print("✓ Retrieved bearer token from Secrets Manager")
        
    except Exception as e:
        print(f"Error retrieving credentials: {e}")
        sys.exit(1)
    
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    
    print(f"\nConnecting to: {mcp_url}")

    try:
        async with streamablehttp_client(mcp_url, headers, timeout=timedelta(seconds=120), terminate_on_close=False) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                print("\n🔄 Initializing MCP session...")
                await session.initialize()
                print("✓ MCP session initialized")
                
                print("\n🔄 Listing available tools...")
                tool_result = await session.list_tools()
                
                print("\n📋 Available MCP Tools:")
                print("=" * 50)
                for tool in tool_result.tools:
                    print(f"🔧 {tool.name}: {tool.description}")
                
                print("\n🧪 Testing MCP Tools:")
                print("=" * 50)
                
                try:
                    print("\n➕ Testing add_numbers(5, 3)...")
                    add_result = await session.call_tool(
                        name="add_numbers",
                        arguments={"a": 5, "b": 3}
                    )
                    print(f"   Result: {add_result.content[0].text}")
                except Exception as e:
                    print(f"   Error: {e}")
                
                try:
                    print("\n✖️  Testing multiply_numbers(4, 7)...")
                    multiply_result = await session.call_tool(
                        name="multiply_numbers",
                        arguments={"a": 4, "b": 7}
                    )
                    print(f"   Result: {multiply_result.content[0].text}")
                except Exception as e:
                    print(f"   Error: {e}")
                
                try:
                    print("\n👋 Testing greet_user('Alice')...")
                    greet_result = await session.call_tool(
                        name="greet_user",
                        arguments={"name": "Alice"}
                    )
                    print(f"   Result: {greet_result.content[0].text}")
                except Exception as e:
                    print(f"   Error: {e}")
                
                print("\n✅ MCP tool testing completed!")
                
    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")
        print("\nTroubleshooting tips:")
        print("1. Ensure BEARER_TOKEN environment variable is set")
        print("2. Check if the agent runtime ARN is correct")
        print("3. Verify you have permissions to access this agent runtime")
        print("4. Check if the agent runtime is active and running")
        print("5. Verify the Bearer token is valid and not expired")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())