import boto3
import json
import os
import jwt
from datetime import datetime, timedelta

def load_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    return config

config = load_config()

def create_bearer_token_with_user_pool():
    """Create Bearer token using Cognito User Pool authentication"""
    try:
        user_pool_id = config['cognito']['user_pool_id']
        client_id = config['cognito']['client_id']
        region = config['region']
        
        print(f"Using User Pool ID: {user_pool_id}")
        print(f"Using Client ID: {client_id}")
        print(f"Using region: {region}")
        
        # Create Cognito Identity Provider client
        cognito_idp_client = boto3.client('cognito-idp', region_name=region)
        
        # For testing purposes, we'll use admin_initiate_auth
        # In production, you should use proper user authentication flow
        
        # Check if we have test credentials in config
        if 'test_username' in config['cognito'] and 'test_password' in config['cognito']:
            username = config['cognito']['test_username']
            password = config['cognito']['test_password']
            
            print(f"Attempting authentication with test user: {username}")
            
            # Authenticate user
            auth_response = cognito_idp_client.admin_initiate_auth(
                UserPoolId=user_pool_id,
                ClientId=client_id,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
            
            if 'AuthenticationResult' in auth_response:
                id_token = auth_response['AuthenticationResult']['IdToken']
                access_token = auth_response['AuthenticationResult']['AccessToken']
                
                print("✓ Authentication successful")
                print(f"ID Token: {id_token[:20]}...{id_token[-20:]}")
                print(f"Access Token: {access_token[:20]}...{access_token[-20:]}")
                
                # Use the ID token as bearer token
                bearer_token = f"Bearer {id_token}"
                return bearer_token
            else:
                print("Authentication failed - no authentication result")
                return None
        else:
            print("No test credentials found in config")
            print("Please add test_username and test_password to config.json")
            return None
            
    except Exception as e:
        print(f"Error creating bearer token with User Pool: {e}")
        return None

def create_bearer_token_with_identity_pool():
    """Create Bearer token using Cognito Identity Pool with User Pool authentication"""
    try:
        identity_pool_id = config['cognito']['identity_pool_id']
        user_pool_id = config['cognito']['user_pool_id']
        client_id = config['cognito']['client_id']
        region = config['region']
        
        print(f"Using Identity Pool ID: {identity_pool_id}")
        print(f"Using User Pool ID: {user_pool_id}")
        print(f"Using Client ID: {client_id}")
        print(f"Using region: {region}")
        
        # First, authenticate with User Pool
        cognito_idp_client = boto3.client('cognito-idp', region_name=region)
        
        if 'test_username' in config['cognito'] and 'test_password' in config['cognito']:
            username = config['cognito']['test_username']
            password = config['cognito']['test_password']
            
            print(f"Authenticating with User Pool: {username}")
            
            # Authenticate user
            auth_response = cognito_idp_client.admin_initiate_auth(
                UserPoolId=user_pool_id,
                ClientId=client_id,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
            
            if 'AuthenticationResult' in auth_response:
                id_token = auth_response['AuthenticationResult']['IdToken']
                
                # Now use the ID token with Identity Pool
                cognito_identity_client = boto3.client('cognito-identity', region_name=region)
                
                # Get identity ID using the authenticated token
                identity_response = cognito_identity_client.get_id(
                    IdentityPoolId=identity_pool_id,
                    Logins={
                        f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': id_token
                    }
                )
                
                identity_id = identity_response['IdentityId']
                print(f"✓ Got Identity ID: {identity_id}")
                
                # Get temporary credentials
                credentials_response = cognito_identity_client.get_credentials_for_identity(
                    IdentityId=identity_id,
                    Logins={
                        f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': id_token
                    }
                )
                
                credentials = credentials_response['Credentials']
                print("✓ Got temporary credentials")
                
                # Create a custom bearer token with the temporary credentials
                bearer_token = f"Bearer_{credentials['AccessKeyId']}_{credentials['SecretKey']}_{credentials['SessionToken']}"
                return bearer_token
            else:
                print("Authentication failed")
                return None
        else:
            print("No test credentials found in config")
            return None
            
    except Exception as e:
        print(f"Error creating bearer token with Identity Pool: {e}")
        return None

def setup_cognito_user_pool():
    """Set up Cognito User Pool and create Bearer token"""
    try:
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

def create_bearer_token():
    """Legacy method - Create Bearer token for AWS Bedrock AgentCore"""
    try:
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
        
        print("Bearer token created")
        return bearer_token
        
    except Exception as e:
        print(f"Error creating bearer token: {e}")
        return None

def main():
    print("Attempting to create Bearer token for AWS Bedrock AgentCore...")
    
    # Method 1: Using Cognito User Pool (Recommended)
    print("\nMethod 1: Using Cognito User Pool")
    token = create_bearer_token_with_user_pool()
    
    if not token:
        # Method 2: Using Cognito Identity Pool with User Pool authentication
        print("\nMethod 2: Using Cognito Identity Pool with User Pool authentication")
        token = create_bearer_token_with_identity_pool()
    
    if not token:
        # Method 3: Legacy method (will likely fail)
        print("\nMethod 3: Using Cognito Identity Pool (Legacy - likely to fail)")
        token = create_bearer_token()
    
    if token:
        print(f"\nBearer token created: {token[:20]}...{token[-20:] if len(token) > 40 else ''}")
        
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
        print("\nCould not create Bearer token")
        print("\nManual setup required:")
        print("1. Add test_username and test_password to config.json")
        print("2. Create a user in the Cognito User Pool")
        print("3. Or configure AWS Secrets Manager with secret 'mcp_server/cognito/credentials'")
        return None

if __name__ == "__main__":
    main()
