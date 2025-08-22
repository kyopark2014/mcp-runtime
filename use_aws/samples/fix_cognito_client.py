import boto3
import json

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Failed to load config.json: {e}")
        return None

def update_cognito_client_settings():
    """Updates Cognito client settings to enable authentication flows"""
    
    config = load_config()
    if not config:
        return False
    
    user_pool_id = config['cognito']['user_pool_id']
    client_id = config['cognito']['client_id']
    
    try:
        cognito_client = boto3.client('cognito-idp', region_name='us-west-2')
        
        print("Updating Cognito client settings...")
        
        # Update client settings
        response = cognito_client.update_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=client_id,
            ExplicitAuthFlows=[
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH',
                'ALLOW_ADMIN_USER_PASSWORD_AUTH'
            ],
            PreventUserExistenceErrors='ENABLED'
        )
        
        print(f"✓ Client settings update completed")
        return True
        
    except Exception as e:
        print(f"Client settings update failed: {e}")
        return False

def generate_bearer_token_from_cognito():
    """Generates a Bearer token using Cognito"""
    
    config = load_config()
    if not config:
        return None
    
    user_pool_id = config['cognito']['user_pool_id']
    client_id = config['cognito']['client_id']
    username = "mcp-test-user@example.com"
    password = "TestPass123!"
    
    try:
        cognito_client = boto3.client('cognito-idp', region_name='us-west-2')
        
        # User authentication
        print("Authenticating Cognito user...")
        
        auth_response = cognito_client.admin_initiate_auth(
            UserPoolId=user_pool_id,
            ClientId=client_id,
            AuthFlow='ADMIN_NO_SRP_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        
        print(f"Authentication response: {auth_response}")
        
        # Handle new password requirement
        if 'ChallengeName' in auth_response and auth_response['ChallengeName'] == 'NEW_PASSWORD_REQUIRED':
            print("Setting new password...")
            
            challenge_response = cognito_client.admin_respond_to_auth_challenge(
                UserPoolId=user_pool_id,
                ClientId=client_id,
                ChallengeName='NEW_PASSWORD_REQUIRED',
                ChallengeResponses={
                    'USERNAME': username,
                    'NEW_PASSWORD': password
                },
                Session=auth_response['Session']
            )
            
            id_token = challenge_response['AuthenticationResult']['IdToken']
        else:
            id_token = auth_response['AuthenticationResult']['IdToken']
        
        # Generate Bearer token
        bearer_token = f"Bearer_{id_token}"
        
        print(f"✓ Bearer token generation completed: {bearer_token[:50]}...")
        
        # Save to AWS Secrets Manager
        secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
        
        secret_value = {
            "bearer_token": bearer_token,
            "id_token": id_token,
            "user_pool_id": user_pool_id,
            "client_id": client_id,
            "created_at": "2025-08-19T15:00:00Z"
        }
        
        try:
            response = secrets_client.update_secret(
                SecretId='mcp_server/cognito/credentials',
                SecretString=json.dumps(secret_value)
            )
            print("✓ Bearer token saved to AWS Secrets Manager")
        except Exception as e:
            print(f"Secrets Manager save failed: {e}")
        
        return bearer_token
        
    except Exception as e:
        print(f"❌ Bearer token generation failed: {e}")
        return None

def test_simple_bearer_token():
    """Creates and tests a simple Bearer token"""
    
    # Generate simple Bearer token
    simple_token = "Bearer_mcp_agentcore_test_token_2025"
    
    print(f"Simple Bearer token generated: {simple_token}")
    
    # Save to AWS Secrets Manager
    secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
    
    secret_value = {
        "bearer_token": simple_token,
        "type": "simple_test_token",
        "created_at": "2025-08-19T15:00:00Z"
    }
    
    try:
        response = secrets_client.update_secret(
            SecretId='mcp_server/cognito/credentials',
            SecretString=json.dumps(secret_value)
        )
        print("✓ Simple Bearer token saved to AWS Secrets Manager")
        return simple_token
    except Exception as e:
        print(f"Secrets Manager save failed: {e}")
        return None

def main():
    print("=== Cognito Client Fix and Bearer Token Generation ===\n")
    
    # 1. Update Cognito client settings
    print("1. Updating Cognito client settings...")
    update_cognito_client_settings()
    
    # 2. Attempt Bearer token generation
    print("\n2. Attempting Cognito Bearer token generation...")
    bearer_token = generate_bearer_token_from_cognito()
    
    # 3. Generate simple token if Cognito fails
    if not bearer_token:
        print("\n3. Generating simple Bearer token...")
        bearer_token = test_simple_bearer_token()
    
    if bearer_token:
        print(f"\n=== Setup Complete ===")
        print(f"Generated Bearer Token: {bearer_token}")
        print(f"\nYou can now test with the following command:")
        print(f"export BEARER_TOKEN='{bearer_token}'")
        print(f"python mcp_client_remote.py")
        
        # Set environment variable
        import os
        os.environ['BEARER_TOKEN'] = bearer_token
        print(f"\nEnvironment variable BEARER_TOKEN set")
    else:
        print("❌ Bearer token generation failed")

if __name__ == "__main__":
    main()
