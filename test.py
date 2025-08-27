import boto3

client = boto3.client('bedrock-agentcore-control', region_name='us-west-2')

# Call the list_agent_runtimes method
response = client.list_agent_runtimes()

agentRuntimes = response['agentRuntimes']
for agentRuntime in agentRuntimes:
    if agentRuntime["agentRuntimeName"] == "mcp_kb_retriever":
        print(agentRuntime["agentRuntimeArn"])
        break

# print(response)