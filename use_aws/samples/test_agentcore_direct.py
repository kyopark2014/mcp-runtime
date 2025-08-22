import boto3
import json
import uuid

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

def test_agentcore_direct():
    """Attempts direct access to AWS Bedrock AgentCore"""
    
    agent_arn = config['agent_runtime_arn']
    print(f"Agent ARN: {agent_arn}")

    # Create Bedrock AgentCore client
    client = boto3.client('bedrock-agentcore', region_name=config['region'])
    
    # Test with various payloads
    test_payloads = [
        # Basic text
        "Hello, test connection",
        
        # JSON format
        json.dumps({
            "prompt": "Hello, test connection",
            "model_name": "Claude 3.7 Sonnet"
        }),
        
        # MCP format
        json.dumps({
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
        })
    ]
    
    for i, payload in enumerate(test_payloads, 1):
        print(f"\n=== Test {i} ===")
        print(f"Payload: {payload[:100]}...")
        
        try:
            response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_arn,
                runtimeSessionId=str(uuid.uuid4()),
                payload=payload,
                qualifier="DEFAULT"
            )
            
            print(f"✅ Success!")
            print(f"Response type: {type(response)}")
            
            if 'response' in response:
                response_body = response['response'].read()
                print(f"Response content: {response_body[:200]}...")
            
        except Exception as e:
            print(f"Failed: {e}")
            print(f"Error type: {type(e).__name__}")

def test_agentcore_status():
    """Checks AgentCore runtime status"""
    try:
        client = boto3.client('bedrock-agentcore', region_name=config['region'])
        
        # Check AgentCore runtime information
        print("=== AgentCore Runtime Information ===")
        
        # Check available operations
        print("Available operations:")
        for operation in client.meta.service_model.operation_names:
            print(f"  - {operation}")
            
    except Exception as e:
        print(f"Status check failed: {e}")

if __name__ == "__main__":
    print("=== AWS Bedrock AgentCore Direct Test ===\n")
    
    # Check status
    test_agentcore_status()
    
    # Direct call test
    test_agentcore_direct()
