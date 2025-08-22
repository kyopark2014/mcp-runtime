import boto3
import json
import os
from datetime import datetime, timedelta

def load_config():
    """Load configuration from config.json"""
    with open("config.json", "r") as f:
        return json.load(f)

def create_bearer_token():
    """Create Bearer token for AWS Bedrock AgentCore"""
    try:
        # Load configuration from config.json
        config = load_config()
        identity_pool_id = config['cognito']['identity_pool_id']
        region = config['region']
        
        # Create temporary credentials using AWS Cognito Identity Pool
        cognito_identity_client = boto3.client('cognito-identity', region_name=region)
        
        print(f"Using Identity Pool ID: {identity_pool_id}")
        print(f"Using region: {region}")
        
        # Get temporary credentials
        response = cognito_identity_client.get_id(
            IdentityPoolId=identity_pool_id
        )
        
        identity_id = response['IdentityId']
        
        # Get temporary credentials
        credentials_response = cognito_identity_client.get_credentials_for_identity(
            IdentityId=identity_id
        )
        
        credentials = credentials_response['Credentials']
        
        # Create Bearer token (should actually be a JWT token)
        # This is an example, actual implementation should use Cognito User Pool or other authentication service
        bearer_token = f"Bearer_{credentials['AccessKeyId']}_{credentials['SecretKey']}"
        
        print("✓ Bearer token created")
        return bearer_token
        
    except Exception as e:
        print(f"Error creating bearer token: {e}")
        return None

def setup_cognito_user_pool():
    """Set up Cognito User Pool and create Bearer token"""
    try:
        # Load configuration from config.json
        config = load_config()
        region = config['region']
        
        # Create Cognito User Pool (use existing if available)
        cognito_idp_client = boto3.client('cognito-idp', region_name=region)
        
        # Check User Pool list
        response = cognito_idp_client.list_user_pools(MaxResults=10)
        
        user_pool_id = None
        for pool in response['UserPools']:
            if 'mcp' in pool['Name'].lower() or 'agentcore' in pool['Name'].lower():
                user_pool_id = pool['Id']
                break
        
        if not user_pool_id:
            print("No existing User Pool found for MCP/AgentCore")
            print("You may need to create a User Pool manually")
            return None
        
        print(f"Using existing User Pool: {user_pool_id}")
        
        # Create app client or use existing client
        app_clients_response = cognito_idp_client.list_user_pool_clients(
            UserPoolId=user_pool_id
        )
        
        app_client_id = None
        for client in app_clients_response['UserPoolClients']:
            if 'mcp' in client['ClientName'].lower():
                app_client_id = client['ClientId']
                break
        
        if not app_client_id:
            print("No existing app client found for MCP")
            return None
        
        print(f"Using existing app client: {app_client_id}")
        
        # User authentication (username/password required in actual implementation)
        # This is an example, actual implementation requires proper authentication credentials
        print("Note: This is a placeholder. You need to implement proper authentication.")
        return None
        
    except Exception as e:
        print(f"Error setting up Cognito: {e}")
        return None

def main():
    print("Attempting to create Bearer token for AWS Bedrock AgentCore...")
    
    # Method 1: Using Cognito Identity Pool
    print("\nMethod 1: Using Cognito Identity Pool")
    token = create_bearer_token()
    
    if not token:
        # Method 2: Using Cognito User Pool
        print("\nMethod 2: Using Cognito User Pool")
        token = setup_cognito_user_pool()
    
    if token:
        print(f"\nBearer token created: {token[:20]}...{token[-20:] if len(token) > 40 else ''}")
        
        # Set as environment variable
        os.environ['BEARER_TOKEN'] = token
        print("✓ BEARER_TOKEN environment variable set")
        
        # Save to Secrets Manager (optional)
        save_to_secrets = input("\nSave token to AWS Secrets Manager? (y/n): ").lower().strip()
        if save_to_secrets == 'y':
            try:
                config = load_config()
                region = config['region']
                secrets_client = boto3.client('secretsmanager', region_name=region)
                secret_value = json.dumps({'bearer_token': token})
                
                secrets_client.create_secret(
                    Name='mcp_server/cognito/credentials',
                    SecretString=secret_value,
                    Description='Bearer token for MCP server authentication'
                )
                print("✓ Token saved to AWS Secrets Manager")
            except Exception as e:
                print(f"Error saving to Secrets Manager: {e}")
        
        return token
    else:
        print("\n❌ Could not create Bearer token")
        print("\nManual setup required:")
        print("1. Create a Cognito User Pool or Identity Pool")
        print("2. Generate a Bearer token manually")
        print("3. Set BEARER_TOKEN environment variable")
        print("4. Or configure AWS Secrets Manager with secret 'mcp_server/cognito/credentials'")
        return None

if __name__ == "__main__":
    main()
