import boto3
import json
import secrets
import string
import os
from datetime import datetime, timedelta

def generate_token():
    """Generate a simple Bearer token"""
    # Generate 24-character random string
    alphabet = string.ascii_letters + string.digits
    token_part = ''.join(secrets.choice(alphabet) for _ in range(24))
    return f"Bearer_{token_part}"

def save_to_secrets_manager(token):
    """Save token to AWS Secrets Manager"""
    try:
        secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
        
        secret_value = {
            "bearer_token": token,
            "created_at": datetime.utcnow().isoformat(),
            "description": "Bearer token for MCP server authentication"
        }
        
        # Create new secret or update existing one
        try:
            response = secrets_client.create_secret(
                Name='mcp_server/cognito/credentials',
                SecretString=json.dumps(secret_value),
                Description="Bearer token for MCP server authentication"
            )
            print(f"✓ New secret created: {response['ARN']}")
        except secrets_client.exceptions.ResourceExistsException:
            response = secrets_client.update_secret(
                SecretId='mcp_server/cognito/credentials',
                SecretString=json.dumps(secret_value)
            )
            print(f"✓ Existing secret updated: {response['ARN']}")
        
        return True
    except Exception as e:
        print(f"❌ Save failed: {e}")
        return False

def main():
    print("=== Quick Bearer Token Setup ===\n")
    
    # Generate token
    token = generate_token()
    print(f"Generated token: {token}")
    
    # Save to AWS Secrets Manager
    print("\nSaving to AWS Secrets Manager...")
    if save_to_secrets_manager(token):
        print("✓ Save successful!")
        
        # Set environment variable
        os.environ['BEARER_TOKEN'] = token
        print("✓ Environment variable set")
        
        print(f"\n=== Setup Complete ===")
        print("Token has been saved to AWS Secrets Manager.")
        print("Environment variable BEARER_TOKEN has also been set.")
        print("\nYou can now test with the following command:")
        print("python mcp_client_remote.py")
        
    else:
        print("❌ Save failed")
        print("Setting environment variable only...")
        os.environ['BEARER_TOKEN'] = token
        print("✓ Environment variable set")

if __name__ == "__main__":
    main()
