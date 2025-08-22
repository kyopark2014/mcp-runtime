import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def test_aws_operations():
    """Test AWS service operations using local MCP server"""
    
    mcp_url = "http://localhost:8000/mcp"
    headers = {}
    
    print("Testing local MCP server with AWS operations...")
    print(f"Connecting to: {mcp_url}")
    
    try:
        async with streamablehttp_client(mcp_url, headers, timeout=120, terminate_on_close=False) as (
            read_stream, write_stream, _,):
            
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # Get list of available tools
                tool_result = await session.list_tools()
                print(f"\nAvailable tools: {len(tool_result.tools)}")
                for tool in tool_result.tools:
                    print(f"  - {tool.name}: {tool.description[:100]}...")
                
                # Test AWS S3 bucket list retrieval
                print("\n=== Testing AWS S3 List Buckets ===")
                s3_params = {
                    "service_name": "s3",
                    "operation_name": "list_buckets",
                    "parameters": {},
                    "region": "us-west-2",
                    "label": "List S3 buckets"
                }
                
                result = await session.call_tool("use_aws", s3_params)
                print(f"Result: {result}")
                
                if hasattr(result, 'content') and result.content:
                    for content in result.content:
                        if hasattr(content, 'text'):
                            print(f"Content: {content.text}")
                
                # Test AWS EC2 instance list retrieval
                print("\n=== Testing AWS EC2 Describe Instances ===")
                ec2_params = {
                    "service_name": "ec2",
                    "operation_name": "describe_instances",
                    "parameters": {"MaxResults": 5},
                    "region": "us-west-2",
                    "label": "List EC2 instances"
                }
                
                result = await session.call_tool("use_aws", ec2_params)
                print(f"Result: {result}")
                
                if hasattr(result, 'content') and result.content:
                    for content in result.content:
                        if hasattr(content, 'text'):
                            print(f"Content: {content.text}")
                
    except Exception as e:
        print(f"Error testing MCP server: {e}")
        print(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(test_aws_operations())
