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
    """Check if the agent runtime is active and accessible"""
    try:
        session = boto3.Session()
        
        # Try to use bedrock-agent-runtime client
        try:
            client = session.client('bedrock-agent-runtime', region_name=region)
            print("Using bedrock-agent-runtime client")
        except:
            # Fallback to bedrock client
            client = session.client('bedrock', region_name=region)
            print("Using bedrock client")
        
        # Extract runtime name from ARN
        runtime_name = agent_arn.split('/')[-1]
        print(f"Checking runtime: {runtime_name}")
        
        # Try to describe the agent runtime
        try:
            # Try different API methods
            response = client.describe_agent_runtime(agentId=runtime_name)
            status = response.get('agentRuntime', {}).get('status')
            print(f"Agent Runtime Status: {status}")
            
            if status == 'ACTIVE':
                return True
            else:
                print(f"Warning: Agent Runtime is not active. Current status: {status}")
                return False
                
        except Exception as api_error:
            print(f"API error: {api_error}")
            # If we can't check status, assume it's available and continue
            print("Could not verify agent runtime status, proceeding anyway...")
            return True
            
    except Exception as e:
        print(f"Error checking agent runtime status: {e}")
        print("Proceeding without status check...")
        return True

def check_agent_runtime_oauth_config(agent_arn, region):
    """Check Agent Runtime OAuth configuration"""
    try:
        session = boto3.Session()
        client = session.client('bedrock-agentcore', region_name=region)
        
        # Extract runtime name from ARN
        runtime_name = agent_arn.split('/')[-1]
        print(f"Checking OAuth config for runtime: {runtime_name}")
        
        # Try to get agent runtime details
        try:
            # This might not work with current API, but worth trying
            response = client.describe_agent_runtime(agentId=runtime_name)
            print(f"Agent Runtime details: {response}")
            return response
        except Exception as e:
            print(f"Could not get agent runtime details: {e}")
            return None
            
    except Exception as e:
        print(f"Error checking agent runtime OAuth config: {e}")
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

def test_basic_connection(url, headers):
    """Test basic HTTP connection before attempting MCP"""
    print(f"\n=== 기본 연결 테스트 ===")
    print(f"URL: {url}")
    
    try:
        # Simple GET request to test connectivity
        response = requests.get(url, headers=headers, timeout=10)
        print(f"기본 연결 테스트 응답: {response.status_code}")
        print(f"응답 헤더: {dict(response.headers)}")
        return True
    except requests.exceptions.Timeout:
        print("❌ 기본 연결 타임아웃 (10초)")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 기본 연결 실패 - 네트워크 문제")
        return False
    except Exception as e:
        print(f"❌ 기본 연결 에러: {e}")
        return False

agent_config = load_config()
agentRuntimeArn = agent_config['agent_runtime_arn']
print(f"agentRuntimeArn: {agentRuntimeArn}")

async def main():
    agent_arn = agentRuntimeArn
    region = agent_config['region']
    
    # Check agent runtime status first
    print("Checking Agent Runtime status...")
    if not check_agent_runtime_status(agent_arn, region):
        print("Agent Runtime is not active. Please check the runtime configuration.")
        return
    
    # Check OAuth configuration
    print("Checking Agent Runtime OAuth configuration...")
    oauth_config = check_agent_runtime_oauth_config(agent_arn, region)
    
    # Bearer token is required - get from AWS Secrets Manager
    # Use Access Token instead of ID Token for MCP authentication
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
    
    if not bearer_token:
        print("Error: BEARER_TOKEN environment variable is required")
        print("Please set BEARER_TOKEN environment variable or configure AWS Secrets Manager")
        sys.exit(1)
    
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    
    # Try different endpoint URLs
    test_urls = [
        f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/mcp?qualifier=DEFAULT",
        f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT",
        f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/mcp",
        f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/invocations"
    ]
    
    # Start with the default MCP endpoint
    mcp_url = test_urls[0]
    print(f"시도할 엔드포인트 URLs:")
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
    
    # Use OAuth (Bearer token only) authentication
    print("Using OAuth (Bearer token only) authentication...")
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    print(f"Using headers: {headers}\n")

    # Try different endpoints until one works
    successful_url = None
    for i, test_url in enumerate(test_urls):
        print(f"\n=== 테스트 {i+1}: {test_url} ===")
        try:
            test_response = requests.post(
                test_url,
                headers=headers,
                data=request_body,
                timeout=30
            )
            print(f"응답 상태: {test_response.status_code}")
            print(f"응답 내용: {test_response.text[:200]}...")
            
            if test_response.status_code == 200:
                print("✓ 성공!")
                successful_url = test_url
                break
            elif test_response.status_code == 403 and "OAuth authorization failed" not in test_response.text:
                # OAuth 에러가 아닌 다른 403 에러라면 엔드포인트가 잘못된 것일 수 있음
                continue
            elif test_response.status_code == 404:
                # 엔드포인트가 존재하지 않음
                continue
            else:
                print(f"⚠ 에러: {test_response.status_code}")
                
        except Exception as e:
            print(f"❌ 연결 실패: {e}")
            continue
    
    if not successful_url:
        print("\n모든 엔드포인트에서 인증이 실패했습니다.")
        return
    
    mcp_url = successful_url
    print(f"\n성공한 엔드포인트: {mcp_url}")

    # Test basic connection first
    if not test_basic_connection(mcp_url, headers):
        print("기본 연결 테스트 실패. MCP 연결을 시도하지 않습니다.")
        return

    try:
        print(f"\n=== MCP 연결 시도 중 ===")
        print(f"URL: {mcp_url}")
        print(f"Headers: {headers}")
        print(f"Timeout: 120초")
        
        # Now try the MCP connection with better error handling
        print("1. streamablehttp_client 연결 시도 중...")
        async with streamablehttp_client(mcp_url, headers, timeout=120, terminate_on_close=False) as (
            read_stream, write_stream,_,):
            
            print("2. streamablehttp_client 연결 성공!")
            print("3. ClientSession 생성 중...")
            
            async with ClientSession(read_stream, write_stream) as session:
                print("4. ClientSession 생성 성공!")
                print("5. session.initialize() 호출 중...")
                
                # Add timeout for initialize
                try:
                    await asyncio.wait_for(session.initialize(), timeout=30)
                    print("6. session.initialize() 성공!")
                except asyncio.TimeoutError:
                    print("❌ session.initialize() 타임아웃 (30초)")
                    return
                except Exception as init_error:
                    print(f"❌ session.initialize() 실패: {init_error}")
                    return
                
                print("7. session.list_tools() 호출 중...")
                
                # Add timeout for list_tools
                try:
                    tool_result = await asyncio.wait_for(session.list_tools(), timeout=30)
                    print(f"8. session.list_tools() 성공!")
                    print(f"\nAvailable tools: {len(tool_result.tools)}")
                    for tool in tool_result.tools:
                        print(f"  - {tool.name}: {tool.description[:100]}...")
                except asyncio.TimeoutError:
                    print("❌ session.list_tools() 타임아웃 (30초)")
                    return
                except Exception as tools_error:
                    print(f"❌ session.list_tools() 실패: {tools_error}")
                    return
                
                # Test AWS S3 bucket list retrieval
                print("\n=== Testing AWS S3 List Buckets ===")
                s3_params = {
                    "service_name": "s3",
                    "operation_name": "list_buckets",
                    "parameters": {},
                    "region": "us-west-2",
                    "label": "List S3 buckets"
                }
                
                print("9. S3 list_buckets 호출 중...")
                try:
                    result = await asyncio.wait_for(session.call_tool("use_aws", s3_params), timeout=60)
                    print(f"10. S3 list_buckets 성공!")
                    print(f"Result: {result}")
                    
                    if hasattr(result, 'content') and result.content:
                        for content in result.content:
                            if hasattr(content, 'text'):
                                print(f"Content: {content.text}")
                except asyncio.TimeoutError:
                    print("❌ S3 list_buckets 타임아웃 (60초)")
                except Exception as s3_error:
                    print(f"❌ S3 list_buckets 실패: {s3_error}")
                
                # Test AWS EC2 instance list retrieval
                print("\n=== Testing AWS EC2 Describe Instances ===")
                ec2_params = {
                    "service_name": "ec2",
                    "operation_name": "describe_instances",
                    "parameters": {"MaxResults": 5},
                    "region": "us-west-2",
                    "label": "List EC2 instances"
                }
                
                print("11. EC2 describe_instances 호출 중...")
                try:
                    result = await asyncio.wait_for(session.call_tool("use_aws", ec2_params), timeout=60)
                    print(f"12. EC2 describe_instances 성공!")
                    print(f"Result: {result}")
                    
                    if hasattr(result, 'content') and result.content:
                        for content in result.content:
                            if hasattr(content, 'text'):
                                print(f"Content: {content.text}")
                except asyncio.TimeoutError:
                    print("❌ EC2 describe_instances 타임아웃 (60초)")
                except Exception as ec2_error:
                    print(f"❌ EC2 describe_instances 실패: {ec2_error}")
                
                print("\n=== MCP 연결 테스트 완료 ===")
                
    except asyncio.TimeoutError:
        print("❌ MCP 연결 타임아웃 (120초)")
        print("가능한 원인:")
        print("- 네트워크 연결 문제")
        print("- Agent Runtime이 응답하지 않음")
        print("- 인증 토큰이 만료됨")
    except Exception as e:
        print(f"❌ MCP 연결 실패:")
        print_exception_details(e)
        
        print("\nTroubleshooting tips:")
        print("1. Ensure BEARER_TOKEN environment variable is set")
        print("2. Check if the agent runtime ARN is correct")
        print("3. Verify you have permissions to access this agent runtime")
        print("4. Check if the agent runtime is active and running")
        print("5. Verify the Bearer token is valid and not expired")
        print("6. Check AWS credentials and IAM permissions")
        print("7. Verify the agent runtime is in the correct region")
        print("8. Check network connectivity to AWS endpoints")

if __name__ == "__main__":
    asyncio.run(main())