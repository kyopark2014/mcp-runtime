import boto3
import json
import uuid
import os

region_name = "us-west-2"

def load_agent_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "agentcore.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)    
    return config

def parse_sse_response(response_body):
    """Parse SSE (Server-Sent Events) response"""
    try:
        # Decode bytes to string
        if isinstance(response_body, bytes):
            response_text = response_body.decode('utf-8')
        else:
            response_text = response_body
            
        lines = response_text.strip().split('\n')
        results = []
        
        for line in lines:
            if line.startswith('data: '):
                json_str = line[6:]  # Remove 'data: ' prefix
                try:
                    data = json.loads(json_str)
                    results.append(data)
                except json.JSONDecodeError as e:
                    print(f"JSON parsing error: {e}")
                    print(f"Problematic line: {json_str}")
                    continue
        
        return results
    except Exception as e:
        print(f"SSE parsing error: {e}")
        return None

agent_config = load_agent_config()
agentRuntimeArn = agent_config['agent_runtime_arn']
print(f"agentRuntimeArn: {agentRuntimeArn}")

payload = {
    "prompt": "Hello. How are you?",
    "mcp_servers": ["basic"],
    "model_name": "Claude 3.7 Sonnet",
}

agent_core_client = boto3.client('bedrock-agentcore', region_name=region_name)

try:
    print(f"Sending payload: {payload}")
    response = agent_core_client.invoke_agent_runtime(
        agentRuntimeArn=agentRuntimeArn,
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps(payload),
        qualifier="DEFAULT"
    )

    response_body = response['response'].read()
    print(f"Raw response_body: {response_body}")

    # Parse SSE response
    parsed_results = parse_sse_response(response_body)
    
    if parsed_results:
        print("\n=== Parsed Response ===")
        for i, result in enumerate(parsed_results):
            print(f"\nResponse {i+1}:")
            
            # Check for errors
            if 'error' in result:
                print(f"Error occurred: {result['error']}")
                print(f"Error type: {result.get('error_type', 'Unknown')}")
                print(f"Message: {result.get('message', 'No message')}")
                continue
            
            # Output data
            if 'data' in result:
                print(f"Data: {result['data']}")
            if 'result' in result:
                print(f"Result: {result['result']}")
    else:
        print("Unable to parse response.")
        
        # Try to parse original response as JSON
        try:
            if isinstance(response_body, bytes):
                response_text = response_body.decode('utf-8')
            else:
                response_text = response_body
                
            response_data = json.loads(response_text)
            print("JSON response:", response_data)
        except json.JSONDecodeError:
            print("JSON parsing also failed.")

except Exception as e:
    print(f"Error occurred during agent invocation: {e}")
    import traceback
    traceback.print_exc()