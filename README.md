# Streamable MCP Tool

여기에서는 [streamable HTTP 방식](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http)의 MCP 서버를 서버리스 환경에서 배포하고 활용하는 방법에 대해 설명합니다. 전체적인 architecture는 아래와 같습니다. 사용자가 [streamlit](https://streamlit.io/)으로 구현된 생성형 AI application을 통해 질문을 입력하면, [LangGraph](https://langchain-ai.github.io/langgraph/) 또는 [Strands](https://strandsagents.com/latest/documentation/docs/) agent가 mutli step reasoning을 통해, Kubernetes로 된 중요한 workload를 조회하거나 관리할 수 있고, 사내의 중요한 데이터를 RAG를 이용해 활용할 수 있습니다. 여기에서는 Knowledge base를 조회하는 [kb-retriever](./runtime/kb-retriever/mcp_retrieve.py)와 AWS 인프라를 관리할 수 있는 [use-aws](./runtime/use-aws/use-aws.py)를 MCP tool로 제공하며, 이 tool들은 AgentCore에 runtime으로 배포됩니다.

<img width="800" alt="image" src="https://github.com/user-attachments/assets/62e33c60-543f-42bf-9962-33daf13c4c00" />

## MCP tool의 구현

### AWS 인프라 관리: use-aws

[mcp_server_use_aws.py](https://github.com/kyopark2014/mcp-tools/blob/main/runtime/use-aws/mcp_server_use_aws.py)에서는 아래와 같이 use_aws tool을 등록합니다. use_aws tool은 agent가 전달하는 service_name, operation_name, parameters를 받아서 실행하고 결과를 리턴합니다. service_name은 s3, ec2와 같은 서비스 명이며, operation_name은 list_buckets와 같은 AWS CLI 명령어 입니다. 또한, parameters는 이 명령어를 수행하는데 필요한 값입니다. 

```python
import use_aws as aws_utils

@mcp.tool()
def use_aws(service_name, operation_name, parameters, region, label, profile_name) -> Dict[str, Any]:
    console = aws_utils.create()
    available_operations = get_available_operations(service_name)

    client = get_boto3_client(service_name, region, profile_name)
    operation_method = getattr(client, operation_name)

    response = operation_method(**parameters)
    for key, value in response.items():
        if isinstance(value, StreamingBody):
            content = value.read()
            try:
                response[key] = json.loads(content.decode("utf-8"))
            except json.JSONDecodeError:
                response[key] = content.decode("utf-8")
    return {
        "status": "success",
        "content": [{"text": f"Success: {str(response)}"}],
    }
```

[use-aws](https://github.com/kyopark2014/mcp-tools/blob/main/runtime/use-aws/use_aws.py)은 [use_aws.py](https://github.com/strands-agents/tools/blob/main/src/strands_tools/use_aws.py)의 MCP 버전입니다. 

### RAG의 활용: kb-retriever

[kb-retriever](https://github.com/kyopark2014/mcp-tools/blob/main/runtime/kb-retriever/mcp_retrieve.py)를 이용해 완전관리형 RAG 서비스인 Knowledge base의 정보를 조회할 수 있습니다.[mcp_server_retrieve.py](https://github.com/kyopark2014/mcp-tools/blob/runtime/main/kb-retriever/mcp_server_retrieve.py)에서는 agent가 전달하는 keyword를 이용해 mcp_retrieve의 retrieve를 호출합니다. 

```python
@mcp.tool()
def retrieve(keyword: str) -> str:
    return mcp_retrieve.retrieve(keyword)    
```

[kb-retriever](https://github.com/kyopark2014/mcp-tools/blob/main/runtime/kb-retriever/mcp_retrieve.py)는 아래와 같이 bedrock-agent-runtime를 이용하여 Knowledge Base를 조회합니다. 이때, number_of_results의 결과를 얻은 후에 content와 reference 정보를 추출하여 활용합니다.

```python
bedrock_agent_runtime_client = boto3.client("bedrock-agent-runtime", region_name=bedrock_region)
response = bedrock_agent_runtime_client.retrieve(
    retrievalQuery={"text": query},
    knowledgeBaseId=knowledge_base_id,
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": number_of_results},
        },
    )
retrieval_results = response.get("retrievalResults", [])
json_docs = []
for result in retrieval_results:
    text = url = name = None
    if "content" in result:
        content = result["content"]
        if "text" in content:
            text = content["text"]
    if "location" in result:
        location = result["location"]
        if "s3Location" in location:
            uri = location["s3Location"]["uri"] if location["s3Location"]["uri"] is not None else ""            
            name = uri.split("/")[-1]
            url = uri # TODO: add path and doc_prefix            
        elif "webLocation" in location:
            url = location["webLocation"]["url"] if location["webLocation"]["url"] is not None else ""
            name = "WEB"
    json_docs.append({
        "contents": text,              
        "reference": {
            "url": url,                   
            "title": name,
            "from": "RAG"
        }
    })
```

## Streamable HTTP 방식의 MCP Tool 배포

AgentCore로 배포하기 위해서는 MCP 설정시 [mcp_server_retrieve.py](./runtime/kb-retriever/mcp_server_retrieve.py)와 같이 host를 "0.0.0.0"으로 설정하고 외부로는 [Dockerfile](./kb-retriever/Dockerfile)와 같이 8000 포트를 expose 합니다.

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

## Deployment 방법

AgentCore runtime으로 배포할 때에는 Boto3 API나, AgentCore CLI를 활용할 수 있습니다.

### Boto3 활용

생성된 policy의 이름은 BedrockAgentCoreMCPRoleFor에 project name을 합한 형태입니다. config.json.sample을 config.json으로 변경한 후에 필요한 값들을 채워줍니다. 이후 아래와 같이 IAM policy를 생성합니다.

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

### AgentCore CLI 활용 방법

Boto3를 이용한 API 이외에도 [AgentCore Toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit)을 이용해 배포할 수 있습니다.

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

### Local Test

MCP 서버는 아래와 같이 실행합니다.

```text
python mcp_server_use_aws.py
```

기본 Client의 실행은 아래와 같습니다. 아래 [mcp_client.py](./mcp_client.py)은 streamable http로 "http://localhost:8000/mcp" 로 연결할 수 있는 MCP 서버의 정보를 가져와 사용할 수 있는 tool에 대한 정보를 제공합니다. 

```text
python mcp_client.py
```

## 실행 결과

Streamlit app을 아래와 같이 실행합니다. 

```python
streamlit run application/app.py
```

이때 아래와 같이 LangGraph와 Strand agent를 선택할 수 있고, use-aws와 kb-retriever를 이용할 수 있습니다. Streamable HTTP 방식 MCP를 배포하기 전에 docker를 선택해서 로컬에서 테스트 할 수 있으며, 다양한 언어 모델을 선택할 수 있습니다.

<img width="343" height="471" alt="image" src="https://github.com/user-attachments/assets/ecbf3325-4b92-459f-a080-9c1ce297e8e3" />


왼쪽 메뉴의 MCP Config에서 "use_aws (streamable)"을 선택한 후에 "내 EKS 현황은?"라고 질문하면, 아래와 같이 use-aws tool을 이용하여 EKS의 상황을 조회할 수 있습니다. 

<img width="655" alt="image" src="https://github.com/user-attachments/assets/d4d2548d-0e60-4e57-b390-53a2ee02bd03" />

또한, "kb-retriever (remote)"을 선택한 후에 "보일러 에러 코드?"로 입력하면, Streamable HTTP를 지원하는 knowledge base MCP에 접속하여 관련된 문서를 아래와 같이 가져와서 답변할 수 있습니다.

<img width="655" alt="image" src="https://github.com/user-attachments/assets/e499b049-9f93-4136-a330-0dc679389b6d" />





## Reference 

[Hosting MCP Server on Amazon Bedrock AgentCore Runtime](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/02-hosting-MCP-server/hosting_mcp_server.ipynb)

[Bedrock AgentCore Starter Toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit)

[LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)

[Strands Agents](https://github.com/strands-agents/sdk-python)
