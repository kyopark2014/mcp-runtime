import boto3

print("🗑️  Starting cleanup process...")

agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=region)
ecr_client = boto3.client('ecr', region_name=region)
iam_client = boto3.client('iam')
ssm_client = boto3.client('ssm', region_name=region)
secrets_client = boto3.client('secretsmanager', region_name=region)

try:
    print("Deleting AgentCore Runtime...")
    runtime_delete_response = agentcore_control_client.delete_agent_runtime(
        agentRuntimeId=launch_result.agent_id,
    )
    print("✓ AgentCore Runtime deletion initiated")

    print("Deleting ECR repository...")
    ecr_repo_name = launch_result.ecr_uri.split('/')[1]
    ecr_client.delete_repository(
        repositoryName=ecr_repo_name,
        force=True
    )
    print("✓ ECR repository deleted")

    print("Deleting IAM role policies...")
    policies = iam_client.list_role_policies(
        RoleName=agentcore_iam_role['Role']['RoleName'],
        MaxItems=100
    )

    for policy_name in policies['PolicyNames']:
        iam_client.delete_role_policy(
            RoleName=agentcore_iam_role['Role']['RoleName'],
            PolicyName=policy_name
        )
    
    iam_client.delete_role(
        RoleName=agentcore_iam_role['Role']['RoleName']
    )
    print("✓ IAM role deleted")

    try:
        ssm_client.delete_parameter(Name='/mcp_server/runtime/agent_arn')
        print("✓ Parameter Store parameter deleted")
    except ssm_client.exceptions.ParameterNotFound:
        print("ℹ️  Parameter Store parameter not found")

    try:
        secrets_client.delete_secret(
            SecretId='mcp_server/cognito/credentials',
            ForceDeleteWithoutRecovery=True
        )
        print("✓ Secrets Manager secret deleted")
    except secrets_client.exceptions.ResourceNotFoundException:
        print("ℹ️  Secrets Manager secret not found")

    print("\n✅ Cleanup completed successfully!")
    
except Exception as e:
    print(f"❌ Error during cleanup: {e}")
    print("You may need to manually clean up some resources.")