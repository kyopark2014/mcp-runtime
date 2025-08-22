import requests
import json
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

def get_aws_auth_headers(url, method='GET'):
    """Generate AWS SigV4 authentication headers"""
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if not credentials:
            print("Error: AWS credentials not found.")
            return None
            
        auth = SigV4Auth(credentials, 'bedrock-agentcore', 'us-west-2')
        request = AWSRequest(method=method, url=url, data='')
        auth.add_auth(request)
        
        return dict(request.headers)
    except Exception as e:
        print(f"Error creating AWS auth headers: {e}")
        return None

def test_endpoint():
    # Read ARN from agentcore.json
    with open("agentcore.json", "r") as f:
        config = json.load(f)
    
    agent_arn = config['agent_runtime_arn']
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    
    # MCP endpoint URL
    mcp_url = f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/mcp?qualifier=DEFAULT"
    
    print(f"Testing endpoint: {mcp_url}")
    
    # Generate AWS authentication headers
    headers = get_aws_auth_headers(mcp_url)
    if not headers:
        print("Failed to create auth headers")
        return
    
    headers["Content-Type"] = "application/json"
    print(f"Headers: {headers}")
    
    try:
        # Test endpoint with simple GET request
        response = requests.get(mcp_url, headers=headers, timeout=30)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response body: {response.text[:500]}...")
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_endpoint()
