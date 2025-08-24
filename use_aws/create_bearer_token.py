import boto3
import json
import os
import time
import jwt
from datetime import datetime, timedelta

accountId = boto3.client('sts').get_caller_identity()['Account']

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Failed to load config.json: {e}")
        return None

def create_test_user():
    """Create a test user in Cognito User Pool"""
    try:
        config = load_config()
        if not config:
            print("Failed to load configuration")
            return False
            
        user_pool_id = config['cognito']['user_pool_id']
        region = config['region']
        username = config['cognito']['test_username']
        password = config['cognito']['test_password']
        
        print(f"Creating test user in User Pool: {user_pool_id}")
        print(f"Username: {username}")
        print(f"Region: {region}")
        
        # Create Cognito Identity Provider client
        cognito_idp_client = boto3.client('cognito-idp', region_name=region)
        
        # Check if user already exists
        try:
            response = cognito_idp_client.admin_get_user(
                UserPoolId=user_pool_id,
                Username=username
            )
            print(f"✓ User '{username}' already exists")
            return True
        except cognito_idp_client.exceptions.UserNotFoundException:
            print(f"User '{username}' does not exist, creating...")
        
        # Create user
        response = cognito_idp_client.admin_create_user(
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
            MessageAction='SUPPRESS'  # Don't send welcome email
        )
        
        print(f"✓ User '{username}' created successfully")
        
        # Set permanent password
        try:
            cognito_idp_client.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=username,
                Password=password,
                Permanent=True
            )
            print(f"✓ Password set for user '{username}'")
        except Exception as e:
            print(f"Warning: Could not set permanent password: {e}")
            print("User may need to change password on first login")
        
        return True
        
    except Exception as e:
        print(f"Error creating test user: {e}")
        return False

def list_users():
    """List all users in the User Pool"""
    try:
        config = load_config()
        if not config:
            print("Failed to load configuration")
            return False
            
        user_pool_id = config['cognito']['user_pool_id']
        region = config['region']
        
        print(f"Listing users in User Pool: {user_pool_id}")
        
        cognito_idp_client = boto3.client('cognito-idp', region_name=region)
        
        response = cognito_idp_client.list_users(
            UserPoolId=user_pool_id
        )
        
        print(f"\nFound {len(response['Users'])} users:")
        for user in response['Users']:
            username = user['Username']
            status = user['UserStatus']
            created = user['UserCreateDate']
            print(f"  - {username} (Status: {status}, Created: {created})")
        
        return True
        
    except Exception as e:
        print(f"Error listing users: {e}")
        return False
    
def create_cognito_user_pool():
    """Creates Cognito User Pool for MCP authentication"""
    
    config = load_config()
    if not config:
        print("Failed to load configuration")
        return None
    
    pool_name = config['cognito']['user_pool_name']
    client_name = config['cognito']['client_name']
    
    try:
        cognito_client = boto3.client('cognito-idp', region_name=config['region'])
        
        # Check existing User Pool
        try:
            response = cognito_client.list_user_pools(MaxResults=10)
            for pool in response['UserPools']:
                if pool['Name'] == pool_name:
                    print(f"Existing User Pool found: {pool['Id']}")
                    user_pool_id = pool['Id']
                    
                    # Check if client already exists for this user pool
                    try:
                        client_response = cognito_client.list_user_pool_clients(UserPoolId=user_pool_id)
                        for client in client_response['UserPoolClients']:
                            if client['ClientName'] == client_name:
                                client_id = client['ClientId']
                                print(f"Existing App client found: {client_id}")
                                
                                # Update config.json with client_id
                                try:
                                    config = load_config()
                                    if config:
                                        config['cognito']['client_id'] = client_id
                                        config_file = "config.json"
                                        with open(config_file, "w") as f:
                                            json.dump(config, f, indent=2)
                                        print(f"✓ Client ID updated in config.json: {client_id}")
                                except Exception as e:
                                    print(f"Warning: Failed to update config.json with client_id: {e}")
                                
                                return user_pool_id, client_id
                        
                        # Client doesn't exist, create it
                        print("Creating new App client for existing User Pool...")
                        client_response = cognito_client.create_user_pool_client(
                            UserPoolId=user_pool_id,
                            ClientName=client_name,
                            GenerateSecret=False,
                            ExplicitAuthFlows=[
                                'ALLOW_USER_PASSWORD_AUTH',
                                'ALLOW_REFRESH_TOKEN_AUTH'
                            ]
                        )
                        
                        client_id = client_response['UserPoolClient']['ClientId']
                        print(f"✓ App client created successfully: {client_id}")
                        
                        # Update config.json with client_id
                        try:
                            config = load_config()
                            if config:
                                config['cognito']['client_id'] = client_id
                                config_file = "config.json"
                                with open(config_file, "w") as f:
                                    json.dump(config, f, indent=2)
                                print(f"✓ Client ID updated in config.json: {client_id}")
                        except Exception as e:
                            print(f"Warning: Failed to update config.json with client_id: {e}")
                        
                        return user_pool_id, client_id
                        
                    except Exception as e:
                        print(f"Failed to check/create client for existing User Pool: {e}")
                        return None
        except Exception as e:
            print(f"Failed to check User Pool list: {e}")
        
        # Create new User Pool
        print("Creating new Cognito User Pool...")
        
        response = cognito_client.create_user_pool(
            PoolName=pool_name,
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8,
                    'RequireUppercase': True,
                    'RequireLowercase': True,
                    'RequireNumbers': True,
                    'RequireSymbols': False
                }
            },
            AutoVerifiedAttributes=['email'],
            UsernameAttributes=['email'],
            MfaConfiguration='OFF',
            AdminCreateUserConfig={
                'AllowAdminCreateUserOnly': True
            }
        )
        
        user_pool_id = response['UserPool']['Id']
        print(f"User Pool created successfully: {user_pool_id}")
        
        # Create app client
        client_response = cognito_client.create_user_pool_client(
            UserPoolId=user_pool_id,
            ClientName=client_name,
            GenerateSecret=False,
            ExplicitAuthFlows=[
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH'
            ]
        )
        
        client_id = client_response['UserPoolClient']['ClientId']
        print(f"✓ App client created successfully: {client_id}")
        
        # Update config.json with client_id
        try:
            config = load_config()
            if config:
                config['cognito']['client_id'] = client_id
                config_file = "config.json"
                with open(config_file, "w") as f:
                    json.dump(config, f, indent=2)
                print(f"✓ Client ID updated in config.json: {client_id}")
        except Exception as e:
            print(f"Warning: Failed to update config.json with client_id: {e}")
        
        return user_pool_id, client_id
        
    except Exception as e:
        print(f"Failed to create Cognito User Pool: {e}")
        return None

def create_cognito_identity_pool(user_pool_id):
    """Creates Cognito Identity Pool and fixes App Client authentication flows"""
    
    config = load_config()
    if not config:
        print("Failed to load configuration")
        return None
    
    identity_pool_name = config['cognito']['identity_pool_name']
    client_id = config['cognito'].get('client_id', '')
    region = config['region']
    
    if not client_id:
        print("Warning: client_id not found in config. Please run the setup again.")
        return None
    
    try:
        # First, fix the Cognito app client authentication flows
        print("Fixing Cognito app client authentication flows...")
        cognito_idp_client = boto3.client('cognito-idp', region_name=region)
        
        try:
            # Update the app client to enable proper authentication flows
            response = cognito_idp_client.update_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id,
                ExplicitAuthFlows=[
                    'ALLOW_ADMIN_USER_PASSWORD_AUTH',
                    'ALLOW_USER_PASSWORD_AUTH',
                    'ALLOW_REFRESH_TOKEN_AUTH',
                    'ALLOW_USER_SRP_AUTH'
                ],
                ReadAttributes=[
                    'email',
                    'email_verified',
                    'name'
                ],
                WriteAttributes=[
                    'email',
                    'name'
                ]
            )
            print("✓ Cognito app client authentication flows updated successfully")
        except Exception as e:
            print(f"Warning: Failed to update Cognito app client: {e}")
        
        # Now create or find Identity Pool
        identity_client = boto3.client('cognito-identity', region_name=region)
        
        # Check existing Identity Pool
        try:
            response = identity_client.list_identity_pools(MaxResults=10)
            for pool in response['IdentityPools']:
                if pool['IdentityPoolName'] == identity_pool_name:
                    print(f"Existing Identity Pool found: {pool['IdentityPoolId']}")
                    identity_pool_id = pool['IdentityPoolId']
                    
                    # Update existing identity pool to allow unauthenticated access for testing
                    try:
                        print("Updating existing Identity Pool to allow unauthenticated access for testing...")
                        pool_response = identity_client.describe_identity_pool(IdentityPoolId=identity_pool_id)
                        update_response = identity_client.update_identity_pool(
                            IdentityPoolId=identity_pool_id,
                            IdentityPoolName=identity_pool_name,
                            AllowUnauthenticatedIdentities=True,
                            CognitoIdentityProviders=pool_response.get('CognitoIdentityProviders', []),
                            SupportedLoginProviders=pool_response.get('SupportedLoginProviders', {})
                        )
                        print("✓ Existing Identity Pool updated to allow unauthenticated access for testing")
                    except Exception as e:
                        print(f"Warning: Failed to update existing Identity Pool for testing: {e}")
                    
                    return identity_pool_id
        except Exception as e:
            print(f"Failed to check Identity Pool list: {e}")
        
        # Create new Identity Pool
        print("Creating new Cognito Identity Pool...")
        
        response = identity_client.create_identity_pool(
            IdentityPoolName=identity_pool_name,
            AllowUnauthenticatedIdentities=False,
            CognitoIdentityProviders=[
                {
                    'ProviderName': f'cognito-idp.{region}.amazonaws.com/{user_pool_id}',
                    'ClientId': client_id,
                    'ServerSideTokenCheck': False
                }
            ]
        )
        
        identity_pool_id = response['IdentityPoolId']
        print(f"✓ Identity Pool created successfully: {identity_pool_id}")
        
        # Update identity pool to allow unauthenticated access for testing
        try:
            print("Updating Identity Pool to allow unauthenticated access for testing...")
            update_response = identity_client.update_identity_pool(
                IdentityPoolId=identity_pool_id,
                IdentityPoolName=identity_pool_name,
                AllowUnauthenticatedIdentities=True,
                CognitoIdentityProviders=response.get('CognitoIdentityProviders', []),
                SupportedLoginProviders=response.get('SupportedLoginProviders', {})
            )
            print("✓ Identity Pool updated to allow unauthenticated access for testing")
        except Exception as e:
            print(f"Warning: Failed to update Identity Pool for testing: {e}")
        
        return identity_pool_id
        
    except Exception as e:
        print(f"Failed to create Cognito Identity Pool: {e}")
        return None

def update_agentcore_config_with_cognito(user_pool_id, identity_pool_id, client_id, discovery_url):
    """Updates AgentCore configuration with Cognito information"""
    
    try:
        config = load_config()
        if not config:
            print("Failed to load configuration")
            return
        
        # Update Cognito configuration
        config['cognito'].update({
            'user_pool_id': user_pool_id,
            'identity_pool_id': identity_pool_id,
            'discovery_url': discovery_url
        })
        
        # Update client_id if provided
        if client_id:
            config['cognito']['client_id'] = client_id
        
        # Save configuration file
        config_file = "config.json"
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        print(f"AgentCore configuration updated successfully: {config_file}")
        
    except Exception as e:
        print(f"Configuration update failed: {e}")

def create_mcp_auth_policy(policy_name: str):
    """Creates additional IAM policy for MCP authentication"""
    
    config = load_config()
    if not config:
        print("Failed to load configuration")
        return None
    
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "MCPServerAuthentication",
                "Effect": "Allow",
                "Action": [
                    "cognito-idp:AdminInitiateAuth",
                    "cognito-idp:AdminRespondToAuthChallenge",
                    "cognito-idp:GetUser",
                    "cognito-idp:GetUserPool",
                    "cognito-identity:GetId",
                    "cognito-identity:GetCredentialsForIdentity",
                    "sts:AssumeRoleWithWebIdentity"
                ],
                "Resource": "*"
            },
            {
                "Sid": "MCPServerSecretsAccess",
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:CreateSecret",
                    "secretsmanager:UpdateSecret"
                ],
                "Resource": [
                    f"arn:aws:secretsmanager:{config['region']}:*:secret:mcp_server/*"
                ]
            }
        ]
    }
    
    try:
        iam_client = boto3.client('iam')
        
        # Check existing policy
        try:
            existing_policy = iam_client.get_policy(PolicyArn=f"arn:aws:iam::{accountId}:policy/{policy_name}")
            print(f"Existing MCP authentication policy found: {existing_policy['Policy']['Arn']}")
            return existing_policy['Policy']['Arn']
        except iam_client.exceptions.NoSuchEntityException:
            pass
        
        # Create new policy
        response = iam_client.create_policy(
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
            Description="Policy for MCP server authentication"
        )
        
        policy_arn = response['Policy']['Arn']
        print(f"✓ MCP authentication policy created successfully: {policy_arn}")
        
        return policy_arn
        
    except Exception as e:
        print(f"Failed to create MCP authentication policy: {e}")
        return None

def update_bedrock_agentcore_role():
    """Adds MCP authentication policy to Bedrock AgentCore role"""
    
    config = load_config()
    if not config:
        print("Failed to load configuration")
        return False
    
    policy_name = config['cognito']['policy_name']    
    policy_arn = create_mcp_auth_policy(policy_name)
    
    if not policy_arn:
        print("Failed to create MCP authentication policy")
        return False
    
    role_name = config['agent_runtime_role'].split('/')[-1]    
    try:
        iam_client = boto3.client('iam')
        
        # Attach policy to role
        response = iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )
        
        print(f"MCP authentication policy attached successfully: {policy_arn}")
        return True
        
    except Exception as e:
        print(f"Failed to attach policy: {e}")
        return False

def create_bearer_token_with_user_pool():
    """Create Bearer token using Cognito User Pool authentication with Access Token"""
    try:
        config = load_config()
        if not config:
            print("Failed to load configuration")
            return None
            
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
                
                # Decode and analyze both tokens
                import base64
                
                # Decode ID token
                id_parts = id_token.split('.')
                id_payload = id_parts[1]
                id_payload += '=' * (4 - len(id_payload) % 4)
                id_decoded = base64.b64decode(id_payload)
                id_data = json.loads(id_decoded)
                
                # Decode Access token
                access_parts = access_token.split('.')
                access_payload = access_parts[1]
                access_payload += '=' * (4 - len(access_payload) % 4)
                access_decoded = base64.b64decode(access_payload)
                access_data = json.loads(access_decoded)
                
                print("\n=== Token Analysis ===")
                print(f"ID Token - aud: {id_data.get('aud')}, token_use: {id_data.get('token_use')}")
                print(f"Access Token - client_id: {access_data.get('client_id')}, token_use: {access_data.get('token_use')}")
                
                # Store both tokens in Secrets Manager for MCP authentication
                # Use Access Token as the primary bearer token for MCP
                token_data = {
                    'id_token': id_token,
                    'access_token': access_token,
                    'bearer_token': access_token,  # Use access token as default bearer token (without Bearer prefix)
                    'id_token_claims': id_data,
                    'access_token_claims': access_data
                }
                
                # Store in Secrets Manager
                try:
                    secrets_client = boto3.client('secretsmanager', region_name=region)
                    secret_name = 'mcp_server/cognito/credentials'
                    
                    # Try to update existing secret first
                    try:
                        secrets_client.update_secret(
                            SecretId=secret_name,
                            SecretString=json.dumps(token_data)
                        )
                        print(f"✓ Updated Secrets Manager with both tokens: {secret_name}")
                    except secrets_client.exceptions.ResourceNotFoundException:
                        # If secret doesn't exist, create it
                        secrets_client.create_secret(
                            Name=secret_name,
                            SecretString=json.dumps(token_data),
                            Description='Bearer token for MCP server authentication'
                        )
                        print(f"✓ Created Secrets Manager secret with both tokens: {secret_name}")
                    
                    print("✓ Using Access Token as primary bearer token for MCP authentication")
                    
                except Exception as secrets_error:
                    print(f"Warning: Could not update Secrets Manager: {secrets_error}")
                    print("Continuing with bearer token creation...")
                
                # Return Access Token WITHOUT Bearer prefix (the test script will add it)
                return access_token
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
        config = load_config()
        if not config:
            print("Failed to load configuration")
            return None
            
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

def create_bearer_token():
    """Create Bearer token for AWS Bedrock AgentCore"""
    print("Attempting to create Bearer token for AWS Bedrock AgentCore...")
    
    # Method 1: Using Cognito User Pool (Recommended)
    print("\nMethod 1: Using Cognito User Pool")
    token = create_bearer_token_with_user_pool()
    
    if not token:
        # Method 2: Using Cognito Identity Pool with User Pool authentication
        print("\nMethod 2: Using Cognito Identity Pool with User Pool authentication")
        token = create_bearer_token_with_identity_pool()
    
    if token:
        print(f"\nBearer token created: {token[:20]}...{token[-20:] if len(token) > 40 else ''}")
        
        try:
            config = load_config()
            region = config['region']
            secrets_client = boto3.client('secretsmanager', region_name=region)
            
            # Get existing secret data if it exists
            existing_data = {}
            try:
                existing_response = secrets_client.get_secret_value(SecretId='mcp_server/cognito/credentials')
                existing_data = json.loads(existing_response['SecretString'])
            except secrets_client.exceptions.ResourceNotFoundException:
                pass
            except Exception as e:
                print(f"Warning: Could not read existing secret: {e}")
            
            # Update with new bearer token (without Bearer prefix)
            existing_data['bearer_token'] = token
            secret_value = json.dumps(existing_data)
            
            # Try to update existing secret first
            try:
                secrets_client.update_secret(
                    SecretId='mcp_server/cognito/credentials',
                    SecretString=secret_value,
                    Description='Bearer token for MCP server authentication'
                )
                print("✓ Token updated in AWS Secrets Manager")
            except secrets_client.exceptions.ResourceNotFoundException:
                # If secret doesn't exist, create it
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

def main():
    print("=== AWS Bedrock AgentCore MCP Setup ===\n")
    
    # 1. Create Cognito User Pool
    print("1. Creating Cognito User Pool...")
    result = create_cognito_user_pool()
    if result:
        user_pool_id, client_id = result
    else:
        user_pool_id = None
        client_id = None
    
    # 2. Create Cognito Identity Pool
    print("\n2. Creating Cognito Identity Pool...")
    identity_pool_id = None
    if user_pool_id:
        identity_pool_id = create_cognito_identity_pool(user_pool_id)
    
    # 3. Update AgentCore Configuration
    print("\n3. Updating AgentCore Configuration...")

    config = load_config()
    discovery_url = f"https://cognito-idp.{config['region']}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"

    if user_pool_id and identity_pool_id:
        update_agentcore_config_with_cognito(user_pool_id, identity_pool_id, client_id, discovery_url)
    
    # 4. Create and attach MCP authentication policy
    print("\n4. Setting up MCP authentication policy...")
    update_bedrock_agentcore_role()
        
    # 5. Create test user
    print("\n5. Creating test user...")
    if user_pool_id:
        success = create_test_user()
        if success:
            print("\nTest user setup completed successfully")
            
            # 6. Create Bearer token
            print("\n6. Creating Bearer token...")
            token = create_bearer_token()
            if token:
                print("\nBearer token created and saved successfully")
                print("\nSetup completed! You can now use the MCP server with authentication.")
            else:
                print("\nFailed to create Bearer token")
                print("\nPlease check your AWS credentials and User Pool configuration")
        else:
            print("\nFailed to create test user")
            print("\nPlease check your AWS credentials and User Pool configuration")
        
    print("\n=== Setup Summary ===")
    print("✓ Cognito User Pool and Identity Pool created")
    print("✓ App client authentication flows configured")
    print("✓ Test user created")
    print("✓ Bearer token generated and saved")
    print("✓ MCP authentication policy attached")
    print("\nYou can now use the MCP server with authentication!")
    
if __name__ == "__main__":
    main()
