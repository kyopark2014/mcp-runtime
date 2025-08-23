import boto3
import json
import os
import time
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
    """Creates Cognito Identity Pool"""
    
    config = load_config()
    if not config:
        print("Failed to load configuration")
        return None
    
    identity_pool_name = config['cognito']['identity_pool_name']
    
    try:
        identity_client = boto3.client('cognito-identity', region_name=config['region'])
        
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
        
        # Get client ID from config
        client_id = config['cognito'].get('client_id', '')
        if not client_id:
            print("Warning: client_id not found in config. Please run the setup again.")
            return None
        
        response = identity_client.create_identity_pool(
            IdentityPoolName=identity_pool_name,
            AllowUnauthenticatedIdentities=False,
            CognitoIdentityProviders=[
                {
                    'ProviderName': f'cognito-idp.{config["region"]}.amazonaws.com/{user_pool_id}',
                    'ClientId': client_id,
                    'ServerSideTokenCheck': False
                }
            ]
        )
        
        identity_pool_id = response['IdentityPoolId']
        print(f"✓ Identity Pool created successfully: {identity_pool_id}")
        
        return identity_pool_id
        
    except Exception as e:
        print(f"Failed to create Cognito Identity Pool: {e}")
        return None

def update_agentcore_config_with_cognito(user_pool_id, identity_pool_id, client_id=None):
    """Updates AgentCore configuration with Cognito information"""
    
    try:
        config = load_config()
        if not config:
            print("Failed to load configuration")
            return
        
        # Update Cognito configuration
        config['cognito'].update({
            'user_pool_id': user_pool_id,
            'identity_pool_id': identity_pool_id
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
    if user_pool_id and identity_pool_id:
        update_agentcore_config_with_cognito(user_pool_id, identity_pool_id, client_id)
    
    # 4. Create and attach MCP authentication policy
    print("\n4. Setting up MCP authentication policy...")
    update_bedrock_agentcore_role()
    
if __name__ == "__main__":
    main()
