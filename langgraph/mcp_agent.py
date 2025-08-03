import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

client = MultiServerMCPClient(
    {
        "weather": {
            "transport": "streamable_http",
            "url": "http://localhost:8000/mcp",
            "headers": {
                "Authorization": "Bearer YOUR_TOKEN",
                "X-Custom-Header": "custom-value"
            },
        }
    }
)

async def run_agent():
    tools = await client.get_tools()
    agent = create_react_agent("model", tools)
    
    response = await agent.ainvoke({"messages": "what is the weather in nyc?"})

    return response

if __name__ == "__main__":    
    result = asyncio.run(run_agent())
    print(f"result: {result}")
