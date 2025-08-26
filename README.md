# MCP Tool Deployment


## Deployment

아래와 같이 IAM policy를 생성합니다. 생성된 policy의 이름은 BedrockAgentCoreMCPRoleFor에 project name을 합한 형태입니다.

```text
python create_iam_policies.py
```

MCP server 인증시 사용할 bearer token을 등록합니다. 여기서는 Cognito의 access token으로 bearer token을 생성하고 secret manager에 등록합니다.

```text
python create_bearer_token.py
```

MCP runtime을 생성합니다.

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

기본 Client의 실행은 아래와 같습니다. 아래 [mcp_client.py](./mcp_client.py)은 streamable http로 "http://localhost:8000/mcp"로 연결할 수 있는 MCP 서버의 정보를 가져와 사용할 수 있는 tool에 대한 정보를 제공합니다. 

```text
python mcp_client.py
```

### AgentCore Toolkit

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

왼쪽 메뉴의 MCP Config에서 "kb-retriever (remote)"을 선택한 후에 "보일러 에러 코드?"로 입력하면, Streamable HTTP를 지원하는 knowledge base MCP에 접속하여 관련된 문서를 아래와 같이 가져와서 답변할 수 있습니다.

<img width="1292" height="759" alt="image" src="https://github.com/user-attachments/assets/a58b5e92-a478-4120-b5ce-3f2116f662ca" />



## Reference 

[Hosting MCP Server on Amazon Bedrock AgentCore Runtime](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/02-hosting-MCP-server/hosting_mcp_server.ipynb)

[Bedrock AgentCore Starter Toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit)

[LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)

[Strands Agents](https://github.com/strands-agents/sdk-python)
