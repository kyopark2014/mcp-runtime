import logging
import sys
import utils
import os
import boto3
import json

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("mcp-config")

config = utils.load_config()
print(f"config: {config}")

region = config["region"] if "region" in config else "us-west-2"
projectName = config["projectName"] if "projectName" in config else "mcp"
workingDir = os.path.dirname(os.path.abspath(__file__))
logger.info(f"workingDir: {workingDir}")

def get_bearer_token():
    try:
        secret_name = f'{projectName}/cognito/credentials'
        session = boto3.Session()
        client = session.client('secretsmanager', region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        bearer_token_raw = response['SecretString']
        
        token_data = json.loads(bearer_token_raw)        
        if 'bearer_token' in token_data:
            bearer_token = token_data['bearer_token']
            return bearer_token
        else:
            print("No bearer token found in secret manager")
            return None
    
    except Exception as e:
        print(f"Error getting stored token: {e}")
        return None

mcp_user_config = {}    
def load_config(mcp_type):
    if mcp_type == "kb-retriever (local)":
        mcp_type = "kb-retriever_local"
    elif mcp_type == "kb-retriever (remote)":        
        mcp_type = "kb-retriever_remote"

    if mcp_type == "basic":
        return {
            "mcpServers": {
                "search": {
                    "command": "python",
                    "args": [
                        f"{workingDir}/mcp_server_basic.py"
                    ]
                }
            }
        }
    elif mcp_type == "use_aws":
        return {
            "mcpServers": {
                "use_aws": {
                    "command": "python",
                    "args": [
                        f"{workingDir}/mcp_server_use_aws.py"
                    ]
                }
            }
        }
    elif mcp_type == "kb-retriever_local":
        return {
            "mcpServers": {
                "kb-retriever": {
                    "type": "streamable_http",
                    "url": "http://127.0.0.1:8000/mcp",
                    "headers": {
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"
                    }
                }
            }
        }
    elif mcp_type == "kb-retriever_remote":
        agent_arn = config['agent_runtime_arn']
        logger.info(f"agent_arn: {agent_arn}")
        encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')

        bearer_token = get_bearer_token()
        logger.info(f"Bearer token from secret manager: {bearer_token[:100] if bearer_token else 'None'}...")

        return {
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
        }
    elif mcp_type == "사용자 설정":
        return mcp_user_config

def load_selected_config(mcp_servers: dict):
    logger.info(f"mcp_servers: {mcp_servers}")
    
    loaded_config = {}
    for server in mcp_servers:
        config = load_config(server)        
        if config:
            loaded_config.update(config["mcpServers"])
    return {
        "mcpServers": loaded_config
    }
