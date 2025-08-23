import boto3
import json
import os
from datetime import datetime

def load_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)    
    return config

config = load_config()
accountId = config['accountId']
agent_runtime_role_name = config['agent_runtime_role_name']

def get_current_role_arn():
    """Get the ARN of the currently used IAM role"""
    try:
        sts_client = boto3.client('sts')
        identity = sts_client.get_caller_identity()
        print(f"Current account: {identity['Account']}")
        print(f"Current user/role: {identity['Arn']}")
        return identity['Arn']
    except Exception as e:
        print(f"Failed to get current role information: {e}")
        return None

def create_bedrock_agentcore_policy():
    """Create IAM policy for Bedrock AgentCore MCP access"""
    
    policy_name = agent_runtime_role_name
    policy_description = "Policy for accessing Bedrock AgentCore MCP endpoints"
    
    # Comprehensive policy document for Bedrock AgentCore MCP access
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockAgentAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:*"
                ],
                "Resource": [
                    "*"
                ]
            },
            {
                "Sid": "SecretsManagerAccess",
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                "Resource": [
                    "arn:aws:secretsmanager:us-west-2:*:secret:mcp_server/cognito/credentials*"
                ]
            },
            {
                "Sid": "CognitoAccess",
                "Effect": "Allow",
                "Action": [
                    "cognito-idp:*"
                ],
                "Resource": "*"
            },
            {
                "Sid": "ECRAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:DescribeRepositories",
                    "ecr:ListImages",
                    "ecr:DescribeImages"
                ],
                "Resource": "*"
            },
            {
                "Sid": "LogsAccess",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams"
                ],
                "Resource": [
                    "arn:aws:logs:us-west-2:*:log-group:/aws/bedrock-agentcore/*",
                    "arn:aws:logs:us-west-2:*:log-group:/aws/bedrock-agentcore/*:log-stream:*"
                ]
            }
        ]
    }
    
    try:
        iam_client = boto3.client('iam')
        
        # Check if policy already exists
        try:
            existing_policy = iam_client.get_policy(PolicyArn=f"arn:aws:iam::{accountId}:policy/{policy_name}")
            print(f"Existing policy found: {existing_policy['Policy']['Arn']}")
            
            # List all policy versions
            versions_response = iam_client.list_policy_versions(PolicyArn=existing_policy['Policy']['Arn'])
            versions = versions_response['Versions']
            
            # If we have 5 versions, delete the oldest non-default version
            if len(versions) >= 5:
                print(f"Policy has {len(versions)} versions, cleaning up old versions...")
                
                # Find non-default versions to delete
                non_default_versions = [v for v in versions if not v['IsDefaultVersion']]
                
                if non_default_versions:
                    # Delete the oldest non-default version
                    oldest_version = non_default_versions[0]
                    iam_client.delete_policy_version(
                        PolicyArn=existing_policy['Policy']['Arn'],
                        VersionId=oldest_version['VersionId']
                    )
                    print(f"✓ Deleted old policy version: {oldest_version['VersionId']}")
                else:
                    # If all versions are default, we need to set a different version as default first
                    for version in versions[1:]:  # Skip the current default
                        try:
                            iam_client.set_default_policy_version(
                                PolicyArn=existing_policy['Policy']['Arn'],
                                VersionId=version['VersionId']
                            )
                            # Now delete the old default
                            iam_client.delete_policy_version(
                                PolicyArn=existing_policy['Policy']['Arn'],
                                VersionId=versions[0]['VersionId']
                            )
                            print(f"✓ Switched default version and deleted old version: {versions[0]['VersionId']}")
                            break
                        except Exception as e:
                            print(f"Failed to switch version {version['VersionId']}: {e}")
                            continue
            
            # Create policy version
            response = iam_client.create_policy_version(
                PolicyArn=existing_policy['Policy']['Arn'],
                PolicyDocument=json.dumps(policy_document),
                SetAsDefault=True
            )
            print(f"✓ Policy update completed: {response['PolicyVersion']['VersionId']}")
            return existing_policy['Policy']['Arn']
            
        except iam_client.exceptions.NoSuchEntityException:
            # Create new policy
            response = iam_client.create_policy(
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document),
                Description=policy_description
            )
            print(f"✓ New policy created: {response['Policy']['Arn']}")
            return response['Policy']['Arn']
            
    except Exception as e:
        print(f"Policy creation failed: {e}")
        return None

def attach_policy_to_role(role_name, policy_arn):
    """Attach policy to IAM role"""
    try:
        iam_client = boto3.client('iam')
        
        # Attach policy to role
        response = iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )
        print(f"✓ Policy attached successfully: {policy_arn}")
        return True
        
    except Exception as e:
        print(f"Policy attachment failed: {e}")
        return False

def create_trust_policy_for_bedrock():
    """Create trust policy for Bedrock AgentCore"""
    
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            },
            {
                "Effect": "Allow",
                "Principal": {
                    "AWS": f"arn:aws:iam::{accountId}:root"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    return trust_policy

def create_bedrock_agentcore_role():
    """Create IAM role for Bedrock AgentCore MCP access"""
    
    role_name = "BedrockAgentCoreMCPRole"
    policy_arn = create_bedrock_agentcore_policy()
    
    if not policy_arn:
        print("Role creation aborted due to policy creation failure")
        return None
    
    try:
        iam_client = boto3.client('iam')
        
        # Check if role already exists
        try:
            existing_role = iam_client.get_role(RoleName=role_name)
            print(f"Existing role found: {existing_role['Role']['Arn']}")
            
            # Update trust policy
            trust_policy = create_trust_policy_for_bedrock()
            iam_client.update_assume_role_policy(
                RoleName=role_name,
                PolicyDocument=json.dumps(trust_policy)
            )
            print("✓ Trust policy updated successfully")
            
            # Attach policy
            attach_policy_to_role(role_name, policy_arn)
            
            return existing_role['Role']['Arn']
            
        except iam_client.exceptions.NoSuchEntityException:
            # Create new role
            trust_policy = create_trust_policy_for_bedrock()
            
            response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Role for Bedrock AgentCore MCP access"
            )
            print(f"✓ New role created: {response['Role']['Arn']}")
            
            # Attach policy
            attach_policy_to_role(role_name, policy_arn)
            
            return response['Role']['Arn']
            
    except Exception as e:
        print(f"Role creation failed: {e}")
        return None

def update_agentcore_config():
    """Update AgentCore configuration"""
    
    config_file = "config.json"
    
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        
        # Set new IAM role ARN
        role_arn = create_bedrock_agentcore_role()
        if role_arn:
            config['agent_runtime_role'] = role_arn
            print(f"✓ AgentCore configuration updated: {role_arn}")
        
        # Save configuration file
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        print(f"✓ Configuration file updated: {config_file}")
        
    except FileNotFoundError:
        print(f"Configuration file not found: {config_file}")
    except Exception as e:
        print(f"Configuration update failed: {e}")

def main():
    print("=== AWS Bedrock AgentCore IAM Setup ===\n")
    
    # Check current role information
    print("1. Checking current IAM information...")
    current_role = get_current_role_arn()
    
    # Create Bedrock AgentCore policy
    print("\n2. Creating Bedrock AgentCore policy...")
    policy_arn = create_bedrock_agentcore_policy()
    
    # Create Bedrock AgentCore role
    print("\n3. Creating Bedrock AgentCore role...")
    role_arn = create_bedrock_agentcore_role()
    
    # Update AgentCore configuration
    print("\n4. Updating AgentCore configuration...")
    update_agentcore_config()
    
    print("\n=== Setup Complete ===")
    if role_arn:
        print(f"Created role ARN: {role_arn}")
        print("\nYou can now redeploy AgentCore using the following command:")
        print("agentcore launch")
    else:
        print("Role creation failed")

if __name__ == "__main__":
    main()

# Alternative Policy Definitions (for reference and testing)
def get_updated_policy():
    """Get updated policy with workload identity support"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockAgentAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:*"
                ],
                "Resource": "*"
            },
            {
                "Sid": "SecretsManagerAccess",
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                "Resource": [
                    "arn:aws:secretsmanager:us-west-2:*:secret:mcp_server/cognito/credentials*"
                ]
            },
            {
                "Sid": "CognitoAccess",
                "Effect": "Allow",
                "Action": [
                    "cognito-idp:*"
                ],
                "Resource": "*"
            }
        ]
    }

def get_permissive_policy():
    """Get permissive policy with wildcard resources"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockAgentAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:*"
                ],
                "Resource": "*"
            },
            {
                "Sid": "SecretsManagerAccess",
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                "Resource": [
                    "arn:aws:secretsmanager:us-west-2:*:secret:mcp_server/cognito/credentials*"
                ]
            },
            {
                "Sid": "CognitoAccess",
                "Effect": "Allow",
                "Action": [
                    "cognito-idp:*"
                ],
                "Resource": "*"
            }
        ]
    }

def create_policy_from_json(policy_name, policy_document, description=None):
    """Create IAM policy from JSON document"""
    
    if description is None:
        description = f"Policy for {policy_name}"
    
    try:
        iam_client = boto3.client('iam')
        
        # Check if policy already exists
        try:
            existing_policy = iam_client.get_policy(PolicyArn=f"arn:aws:iam::{accountId}:policy/{policy_name}")
            print(f"Existing policy found: {existing_policy['Policy']['Arn']}")
            
            # Create policy version
            response = iam_client.create_policy_version(
                PolicyArn=existing_policy['Policy']['Arn'],
                PolicyDocument=json.dumps(policy_document),
                SetAsDefault=True
            )
            print(f"✓ Policy update completed: {response['PolicyVersion']['VersionId']}")
            return existing_policy['Policy']['Arn']
            
        except iam_client.exceptions.NoSuchEntityException:
            # Create new policy
            response = iam_client.create_policy(
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document),
                Description=description
            )
            print(f"✓ New policy created: {response['Policy']['Arn']}")
            return response['Policy']['Arn']
            
    except Exception as e:
        print(f"Policy creation failed: {e}")
        return None

def create_updated_policy():
    """Create updated policy for Bedrock AgentCore MCP access"""
    return create_policy_from_json(
        f"{agent_runtime_role_name}_updated",
        get_updated_policy(),
        "Updated policy for accessing Bedrock AgentCore MCP endpoints with workload identity"
    )

def create_permissive_policy():
    """Create permissive policy for Bedrock AgentCore MCP access"""
    return create_policy_from_json(
        f"{agent_runtime_role_name}_permissive",
        get_permissive_policy(),
        "Permissive policy for accessing Bedrock AgentCore MCP endpoints"
    )

def list_available_policies():
    """List all available policy types"""
    policies = {
        "comprehensive": "Comprehensive policy with all permissions (default)",
        "updated": "Updated policy with workload identity support",
        "permissive": "Permissive policy with wildcard resources"
    }
    
    print("Available policy types:")
    for key, description in policies.items():
        print(f"  - {key}: {description}")
    
    return policies
