# MCP Tool - AWS USE

## How to use

MCP 서버는 아래와 같이 실행합니다.

```text
python mcp_server_use_aws.py
```

기본 Client의 실행은 아래와 같습니다. 아래 [mcp_client.py](./mcp_client.py)은 streamable http로 "http://localhost:8000/mcp"로 연결할 수 있는 MCP 서버의 정보를 가져와 사용할 수 있는 tool에 대한 정보를 제공합니다. 

```text
python mcp_client.py
```

## Reference 

[Hosting MCP Server on Amazon Bedrock AgentCore Runtime](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/02-hosting-MCP-server/hosting_mcp_server.ipynb)