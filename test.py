import boto3

bedrock_region = "us-west-2"

input_text = "Hello, how can you assist me today?"

agent_core_client = boto3.client('bedrock-agentcore', region_name=bedrock_region)
response = agent_core_client.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:us-west-2:262976740991:runtime/use_aws-mNoWe4GlnB",
    qualifier="DEFAULT",
    payload=input_text
)

print(response)