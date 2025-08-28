# MCP Tool Deployment

여기에서는 [streamable HTTP 방식](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http)의 MCP 서버를 서버리스 환경에서 배포하고 활용하는 방법에 대해 설명합니다. 전체적인 architecture는 아래와 같습니다. 사용자가 [streamlit](https://streamlit.io/)으로 구현된 생성형 AI application을 통해 질문을 입력하면, [LangGraph](https://langchain-ai.github.io/langgraph/) 또는 [Strands](https://strandsagents.com/latest/documentation/docs/) agent가 mutli step reasoning을 통해, Kubernetes로 된 중요한 workload를 조회하거나 관리할 수 있고, 사내의 중요한 데이터를 RAG를 이용해 활용할 수 있습니다. 여기에서는 Knowledge base를 조회하는 [kb-retriever](https://github.com/kyopark2014/mcp-tools/blob/main/kb-retriever/mcp_retrieve.py)와 AWS 인프라를 관리할 수 있는 [use-aws](https://github.com/kyopark2014/mcp-tools/blob/main/use_aws/use_aws.py)를 MCP tool로 제공하며, 이 tool들은 AgentCore에 runtime으로 배포됩니다.

<img width="800" alt="image" src="https://github.com/user-attachments/assets/62e33c60-543f-42bf-9962-33daf13c4c00" />



## Streamable HTTP 방식의 MCP Tool 배포 준비

AgentCore로 배포하기 위해서는 MCP 설정시 [mcp_server_retrieve.py](./kb-retriever/mcp_server_retrieve.py)와 같이 host를 "0.0.0.0"으로 설정하고 외부로는 [Dockerfile](./kb-retriever/Dockerfile)와 같이 8000 포트를 expose 합니다.

```python
mcp = FastMCP(
    name = "mcp-retrieve",
    instructions=(
        "You are a helpful assistant. "
        "You retrieve documents in RAG."
    ),
    host="0.0.0.0",
    stateless_http=True
)
```

AgentCore의 runtime으로 MCP를 배포한 후에 활용할 때에는 bearer token을 이용해 인증을 수행합니다. bearer token은 Cognito와 같은 서비스를 통해 생성할 수 있습니다. 아래와 같이 Cognito에 정의한 username/password를 이용해 access token를 생성합니다.

```python
client = boto3.client('cognito-idp', region_name=region)
response = client.initiate_auth(
    ClientId=client_id,
    AuthFlow='USER_PASSWORD_AUTH',
    AuthParameters={
        'USERNAME': username,
        'PASSWORD': password
    }
)
auth_result = response['AuthenticationResult']
access_token = auth_result['AccessToken']
```

AgentCore에 MCP runtime을 배포하면 agent_arn을 얻을 수 있습니다. 이 값은 AgentCore에서 생성할 때 알 수 있으며, 아래와 같이 agent_runtime_name을 가지고 검색할 수도 있습니다.

```python
client = boto3.client('bedrock-agentcore-control', region_name='us-west-2')
response = client.list_agent_runtimes()
agentRuntimes = response['agentRuntimes']
for agentRuntime in agentRuntimes:
    if agentRuntime["agentRuntimeName"] == agent_runtime_name:
        return agentRuntime["agentRuntimeArn"]
```    

Agent의 arn을 url encoding해서 아래와 같이 mcp_url을 생성합니다. 이때 header의 Authorization에 Cognito를 이용해 생성한 bearer token을 입력합니다.

```python
encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')    
mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
headers = {
    "Authorization": f"Bearer {bearer_token}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}
```

이제 mcp_url, headers는 아래와 같이 MCP server의 설정 정보로 활용됩니다.

```python
"mcpServers": {
    "kb-retriever": {
        "type": "streamable_http",
        "url": f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT",
        "headers": {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
    }
}
```




## Deployment

아래와 같이 IAM policy를 생성합니다. 생성된 policy의 이름은 BedrockAgentCoreMCPRoleFor에 project name을 합한 형태입니다.

```text
python create_iam_policies.py
```

MCP server 인증시 사용할 bearer token을 등록합니다. 여기서는 Cognito의 access token으로 bearer token을 생성하고 secret manager에 등록합니다.

```text
python create_bearer_token.py
```

MCP runtime을 생성하기 위해 ECR에 이미지를 푸쉬합니다.

```text
./push-to-ecr.sh
```

이제 AgentCore에 MCP runtime을 생성합니다.

```text
python create_mcp_runtime.py
```

배포가 정상적으로 되었는지 아래와 같이 확인할 수 있습니다.

```text
python test_mcp_remote.py
```

이때의 결과는 아래와 같습니다.

<img width="600" alt="noname" src="https://github.com/user-attachments/assets/5bc2ce14-5ad5-43b2-a6f4-2a359b76bfe4" />


## Local Test

MCP 서버는 아래와 같이 실행합니다.

```text
python mcp_server_use_aws.py
```

기본 Client의 실행은 아래와 같습니다. 아래 [mcp_client.py](./mcp_client.py)은 streamable http로 "http://localhost:8000/mcp" 로 연결할 수 있는 MCP 서버의 정보를 가져와 사용할 수 있는 tool에 대한 정보를 제공합니다. 

```text
python mcp_client.py
```

### AgentCore CLI

아래와 같이 [AgentCore Toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit)을 설치합니다. 

```text
pip install bedrock-agentcore-starter-toolkit
```

이후 아래와 설치를 준비합니다. 아래 명령어로 [Dockerfile](./Dockerfile)과 [.bedrock_agentcore.yaml](./.bedrock_agentcore.yaml)이 생성됩니다. 

```text
python setup.py
```

AgentCore의 상태는 아래 명령어로 확인할 수 있습니다.

```text
agentcore status
```

생성된 Docker 파일을 배포합니다.

```text
agentcore launch
```

이후 아래와 같이 동작을 확인할 수 있습니다.

```text
# Invoke your deployed agent
agentcore invoke '{"prompt": "Hello from Bedrock AgentCore!"}'
```

## 실행 결과

왼쪽 메뉴의 MCP Config에서 "use_aws (streamable)"을 선택한 후에 "내 EKS 현황은?"라고 질문하면, 아래와 같이 use-aws tool을 이용하여 EKS의 상황을 조회할 수 있습니다. 

<img width="655" alt="image" src="https://github.com/user-attachments/assets/d4d2548d-0e60-4e57-b390-53a2ee02bd03" />

또한, "kb-retriever (remote)"을 선택한 후에 "보일러 에러 코드?"로 입력하면, Streamable HTTP를 지원하는 knowledge base MCP에 접속하여 관련된 문서를 아래와 같이 가져와서 답변할 수 있습니다.

<img width="655" alt="image" src="https://github.com/user-attachments/assets/e499b049-9f93-4136-a330-0dc679389b6d" />





## Reference 

[Hosting MCP Server on Amazon Bedrock AgentCore Runtime](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/02-hosting-MCP-server/hosting_mcp_server.ipynb)

[Bedrock AgentCore Starter Toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit)

[LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)

[Strands Agents](https://github.com/strands-agents/sdk-python)
