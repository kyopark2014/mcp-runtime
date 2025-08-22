import boto3
import json
import os

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Failed to load config.json: {e}")
        return None

region = load_config()['region']

def get_bearer_token_from_secrets():
    """Retrieves Bearer token from AWS Secrets Manager"""
    try:
        secrets_client = boto3.client('secretsmanager', region_name=region)
        response = secrets_client.get_secret_value(SecretId='mcp_server/cognito/credentials')
        secret_value = response['SecretString']
        parsed_secret = json.loads(secret_value)
        bearer_token = parsed_secret['bearer_token']
        print("✓ Bearer token retrieved from Secrets Manager")
        return bearer_token
    except Exception as e:
        print(f"Error retrieving bearer token from Secrets Manager: {e}")
        return None

def get_bearer_token_from_env():
    """Retrieves Bearer token from environment variable"""
    bearer_token = os.getenv('BEARER_TOKEN')
    if bearer_token:
        print("✓ Bearer token found in environment variable")
        return bearer_token
    return None

def main():
    print("Attempting to get Bearer token...")
    
    # 1. First check environment variable
    token = get_bearer_token_from_env()
    
    # 2. If not in environment variable, get from Secrets Manager
    if not token:
        print("BEARER_TOKEN not found in environment, trying Secrets Manager...")
        token = get_bearer_token_from_secrets()
    
    if token:
        print(f"Bearer token: {token[:20]}...{token[-20:] if len(token) > 40 else ''}")
        return token
    else:
        print("Could not retrieve Bearer token")
        print("\nTo set up Bearer token:")
        print("1. Set BEARER_TOKEN environment variable:")
        print("   export BEARER_TOKEN='your_token_here'")
        print("2. Or configure AWS Secrets Manager with secret 'mcp_server/cognito/credentials'")
        return None

if __name__ == "__main__":
    main()
