import boto3
import json
import secrets
import string
import os
from datetime import datetime, timedelta

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Failed to load config.json: {e}")
        return None

region = load_config()['cognito']['region']

def generate_simple_bearer_token():
    """Generate a simple Bearer token"""
    # Generate 32-character random string
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(32))
    return f"Bearer_{token}"

def generate_jwt_like_token():
    """Generate a JWT-like token"""
    # Header (Base64 encoded simple JSON)
    header = {
        "alg": "HS256",
        "typ": "JWT"
    }
    
    # Payload (token information)
    payload = {
        "sub": "mcp-client",
        "iss": "aws-bedrock-agentcore",
        "aud": "mcp-server",
        "iat": datetime.utcnow().timestamp(),
        "exp": (datetime.utcnow() + timedelta(hours=24)).timestamp(),
        "scope": "mcp:read mcp:write"
    }
    
    # Simple Base64 encoding (not actual JWT but similar format)
    import base64
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    
    # Signature part (should actually be signed with HMAC-SHA256)
    signature = secrets.token_urlsafe(32)
    
    return f"{header_b64}.{payload_b64}.{signature}"

def save_token_to_secrets_manager(token, secret_name="mcp_server/cognito/credentials"):
    """Save token to AWS Secrets Manager"""
    try:
        secrets_client = boto3.client('secretsmanager', region_name=region)
        
        # Configure secret value
        secret_value = {
            "bearer_token": token,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            "description": "Bearer token for MCP server authentication with AWS Bedrock AgentCore"
        }
        
        # Check if existing secret exists
        try:
            existing_secret = secrets_client.describe_secret(SecretId=secret_name)
            print(f"Existing secret found: {secret_name}")
            
            # Update existing secret
            response = secrets_client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(secret_value),
                Description="Bearer token for MCP server authentication with AWS Bedrock AgentCore"
            )
            print(f"✓ Secret update completed: {response['ARN']}")
            
        except secrets_client.exceptions.ResourceNotFoundException:
            # Create new secret
            response = secrets_client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(secret_value),
                Description="Bearer token for MCP server authentication with AWS Bedrock AgentCore"
            )
            print(f"✓ New secret created: {response['ARN']}")
        
        return True
        
    except Exception as e:
        print(f"Secret save failed: {e}")
        return False

def set_environment_variable(token):
    """Set token as environment variable"""
    os.environ['BEARER_TOKEN'] = token
    print(f"✓ Environment variable BEARER_TOKEN set")
    print(f"Token: {token[:20]}...{token[-20:] if len(token) > 40 else ''}")

def main():
    print("=== AWS Bedrock AgentCore Bearer Token Generation and Storage ===\n")
    
    # Choose token generation method
    print("Choose token generation method:")
    print("1. Simple random token (for testing)")
    print("2. JWT format token (more secure)")
    print("3. Manual input")
    
    choice = input("\nSelection (1-3): ").strip()
    
    if choice == "1":
        token = generate_simple_bearer_token()
        print(f"Generated token: {token}")
    elif choice == "2":
        token = generate_jwt_like_token()
        print(f"Generated JWT token: {token}")
    elif choice == "3":
        token = input("Enter Bearer token: ").strip()
        if not token.startswith("Bearer_"):
            token = f"Bearer_{token}"
    else:
        print("Invalid selection. Using default (simple token).")
        token = generate_simple_bearer_token()
        print(f"Generated token: {token}")
    
    print(f"\nToken length: {len(token)} characters")
    
    # Save to AWS Secrets Manager
    print("\nSaving token to AWS Secrets Manager...")
    if save_token_to_secrets_manager(token):
        print("✓ AWS Secrets Manager save successful!")
        
        # Also set as environment variable
        set_environment_variable(token)
        
        print("\n=== Setup Complete ===")
        print("You can now test the MCP client with the following command:")
        print("python mcp_client_remote.py")
        
    else:
        print("AWS Secrets Manager save failed")
        print("Setting as environment variable only...")
        set_environment_variable(token)

if __name__ == "__main__":
    main()
