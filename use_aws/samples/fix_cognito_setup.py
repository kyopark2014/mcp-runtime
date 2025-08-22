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

def create_cognito_identity_pool_with_correct_client_id():
    """Create Cognito Identity Pool with correct client ID"""
    
    # Load configuration from config.json
    config = load_config()
    if config is None:
        return None
    
    identity_pool_name = "mcp-agentcore-identity-pool"
    user_pool_id = config['cognito']['user_pool_id']
    client_id = config['cognito']['client_id']
    region = config['cognito']['region']
    
    try:
        identity_client = boto3.client('cognito-identity', region_name=region)
        
        # Check existing Identity Pool
        try:
            response = identity_client.list_identity_pools(MaxResults=10)
            for pool in response['IdentityPools']:
                if pool['IdentityPoolName'] == identity_pool_name:
                    print(f"Existing Identity Pool found: {pool['IdentityPoolId']}")
                    return pool['IdentityPoolId']
        except Exception as e:
            print(f"Failed to check Identity Pool list: {e}")
        
        # Create new Identity Pool
        print("Creating new Cognito Identity Pool...")
        print(f"User Pool ID: {user_pool_id}")
        print(f"Client ID: {client_id}")
        
        response = identity_client.create_identity_pool(
            IdentityPoolName=identity_pool_name,
            AllowUnauthenticatedIdentities=False,
            CognitoIdentityProviders=[
                {
                    'ProviderName': f'cognito-idp.us-west-2.amazonaws.com/{user_pool_id}',
                    'ClientId': client_id,
                    'ServerSideTokenCheck': False
                }
            ]
        )
        
        identity_pool_id = response['IdentityPoolId']
        print(f"✓ Identity Pool creation completed: {identity_pool_id}")
        
        return identity_pool_id
        
    except Exception as e:
        print(f"Failed to create Cognito Identity Pool: {e}")
        return None

def update_config_with_identity_pool(identity_pool_id):
    """Add Identity Pool ID to configuration file"""
    
    config_file = "config.json"
    
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        
        # Update Cognito configuration
        if 'cognito' not in config:
            config['cognito'] = {}
        
        config['cognito']['identity_pool_id'] = identity_pool_id
        
        # Save configuration file
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        print(f"✓ Configuration file updated successfully: {config_file}")
        
    except Exception as e:
        print(f"Configuration update failed: {e}")

def create_cognito_user():
    """Create a test user in Cognito User Pool"""
    
    # Load configuration from config.json
    config = load_config()
    if config is None:
        return None, None
    
    user_pool_id = config['cognito']['user_pool_id']
    region = config['cognito']['region']
    
    try:
        cognito_client = boto3.client('cognito-idp', region_name='us-west-2')
        
        # Create test user
        username = "mcp-test-user@example.com"
        password = "TestPass123!"
        
        print(f"Creating test user: {username}")
        
        response = cognito_client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=username,
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': username
                },
                {
                    'Name': 'email_verified',
                    'Value': 'true'
                }
            ],
            TemporaryPassword=password,
            MessageAction='SUPPRESS'
        )
        
        print(f"✓ Test user creation completed: {username}")
        print(f"Temporary password: {password}")
        
        return username, password
        
    except Exception as e:
        print(f"Failed to create test user: {e}")
        return None, None

def generate_bearer_token_from_cognito():
    """Generate Bearer token using Cognito"""
    
    # Load configuration from config.json
    config = load_config()
    if config is None:
        return None
    
    user_pool_id = config['cognito']['user_pool_id']
    client_id = config['cognito']['client_id']
    region = config['cognito']['region']
    username = "mcp-test-user@example.com"
    password = "TestPass123!"
    
    try:
        cognito_client = boto3.client('cognito-idp', region_name=region)
        
        # Authenticate user
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
        
        # If new password setup is required
        if auth_response['ChallengeName'] == 'NEW_PASSWORD_REQUIRED':
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
        
        # Store in AWS Secrets Manager
        secrets_client = boto3.client('secretsmanager', region_name=region)
        
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
            print("✓ Bearer token stored in AWS Secrets Manager successfully")
        except Exception as e:
            print(f"Secrets Manager storage failed: {e}")
        
        return bearer_token
        
    except Exception as e:
        print(f"Failed to generate Bearer token: {e}")
        return None

def main():
    print("=== Cognito Setup Fix and Bearer Token Generation ===\n")
    
    # 1. Create Identity Pool
    print("1. Creating Cognito Identity Pool...")
    identity_pool_id = create_cognito_identity_pool_with_correct_client_id()
    
    # 2. Update configuration file
    print("\n2. Updating configuration file...")
    if identity_pool_id:
        update_config_with_identity_pool(identity_pool_id)
    
    # 3. Create test user
    print("\n3. Creating test user...")
    username, password = create_cognito_user()
    
    # 4. Generate Bearer token
    print("\n4. Generating Bearer token...")
    if username and password:
        bearer_token = generate_bearer_token_from_cognito()
        
        if bearer_token:
            # Load config for display
            config = load_config()
            if config:
                print(f"\n=== Setup Complete ===")
                print(f"Created resources:")
                print(f"  User Pool ID: {config['cognito']['user_pool_id']}")
                print(f"  Client ID: {config['cognito']['client_id']}")
                print(f"  Identity Pool ID: {identity_pool_id}")
                print(f"  Bearer Token: {bearer_token[:50]}...")
                print(f"\nYou can now test with the following commands:")
                print(f"export BEARER_TOKEN='{bearer_token}'")
                print(f"python mcp_client_remote.py")
        else:
            print("Bearer token generation failed")

if __name__ == "__main__":
    main()
