import boto3
import os
import json
from botocore.config import Config

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.json")

def load_config():    
    config = None 
    try:   
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)    
    except Exception as e:
        print(f"Error loading config: {e}")

        region = boto3.client('sts').meta.region_name
        projectName = "mcp"
        accountId = boto3.client('sts').get_caller_identity()['Account']

        current_path = os.path.basename(script_dir)
        current_folder_name = current_path.split('/')[-1]
        targetname = current_folder_name
        
        config = {
            "projectName": projectName,
            "region": region,
            "accountId": accountId,
            "targetname": targetname
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    return config

config = load_config()

projectName = config.get('projectName')
region = config.get('region')
accountId = config.get('accountId')
targetname = config.get('targetname')

def load_tavily_api_key():
    secretArn = config.get('secretArn', "")
    print(f"Secret ARN: {secretArn}")

    if secretArn:
        secretsmanager = boto3.client('secretsmanager', region_name=region)
        response = secretsmanager.get_secret_value(SecretId=secretArn)
        secret = json.loads(response['SecretString'])
        print(f"Secret: {secret}")
        tavily_api_key = secret.get('api_key_value', "")
    else:
        tavily_api_key = input("Enter the Tavily API key: ")
    
    return tavily_api_key

def create_credential_provider(api_key):
    name = f"{projectName}_tavily_search"
    credentialProviderArn = ""

    # check if credential provider already exists
    client = boto3.client('bedrock-agentcore-control', region_name=region)
    response = client.list_api_key_credential_providers()
    credentialProviders = response['credentialProviders']
    
    for credentialProvider in credentialProviders:
        if credentialProvider['name'] == name:
            print(f"API key credential provider already exists: {name}")
            credentialProviderArn = credentialProvider['credentialProviderArn']
            print(f"Credential provider ARN: {credentialProviderArn}")
            break

    # create credential provider if not exists
    if not credentialProviderArn: 
        print(f"Creating API key credential provider: {name}, {api_key}")
        response = client.create_api_key_credential_provider(
            name=name,
            apiKey=api_key
        )
        apiKeySecretArn = response['apiKeySecretArn']
        secretArn = apiKeySecretArn.get('secretArn')
        credentialProviderArn = response['credentialProviderArn']

        config['secretArn'] = secretArn
        config['credentialProviderArn'] = credentialProviderArn
        print(f"Secret ARN: {secretArn}")
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    return credentialProviderArn

def create_gateway_target(credentialProviderArn):
    global config

    credentialProviderConfigurations = [
        {
            'credentialProviderType': 'API_KEY',
            'credentialProvider': {
                'apiKeyCredentialProvider': {
                    'providerArn': 'arn:aws:bedrock-agentcore:us-west-2:262976740991:token-vault/default/apikeycredentialprovider/tavilykey_for_tools',
                    'credentialParameterName': 'api_key',
                    'credentialPrefix': '',  # e.g., 'Bearer' for Authorization header
                    'credentialLocation': 'HEADER'|'QUERY_PARAMETER'
                }
            }
        },
    ]

    gateway_client = boto3.client('bedrock-agentcore-control', region_name=region)
    inlinePayload = {
        "name": "tavily_search",
        "description": "search internet using tavily search engine",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to search for internet"
                }
            },
            "required": ["query"]
        }
    }
    
    gateway_name = config.get('gateway_name')
    if not gateway_name:
        gateway_name = config['projectName']
        print(f"No gateway name found in config, using default gateway name: {gateway_name}")
        config['gateway_name'] = gateway_name

    gateway_id = config.get('gateway_id')    
    if not gateway_id:
        print("No gateway id found in config, getting gateway id from list_gateways using gateway name: {gateway_name}")
        response = gateway_client.list_gateways(maxResults=60)
        for gateway in response['items']:
            if gateway['name'] == gateway_name:
                print(f"gateway: {gateway}")
                gateway_id = gateway.get('gatewayId')
                config['gateway_id'] = gateway_id
                break
        
    target_id = config.get('target_id', "")
    if not target_id:
        print(f"No target id found in config, getting target id from list_gateway_targets using gateway id: {gateway_id}")
        
        response = gateway_client.list_gateway_targets(
            gatewayIdentifier=gateway_id,
            maxResults=60
        )
        print(f"response: {response}")

        target_id = ""
        for target in response['items']:
            if target['name'] == targetname:
                print(f"Target already exists.")
                target_id = target['targetId']
                break
        
        if not target_id:       
            print("Creating lambda target...")
            targetConfiguration = {
                "mcp": {
                    "openApiSchema": {
                        "inlinePayload": inlinePayload
                    }
                }
            }

            credential_config = [ 
                {
                    "credentialProviderType" : "GATEWAY_IAM_ROLE"
                }
            ]
            response = gateway_client.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=targetname,
                description=f'{targetname} for {projectName}',
                targetConfiguration=targetConfiguration,
                credentialProviderConfigurations=credential_config)
            print(f"response: {response}")

            target_id = response["targetId"]        
            config['target_name'] = targetname
            config['target_id'] = target_id
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

    print(f"target_name: {targetname}, target_id: {target_id}")

# main
def main():
    print("=== Tavily API Key Setup ===")
    tavily_api_key = load_tavily_api_key()
    print(f"Tavily API key: {tavily_api_key}")

    print(f"=== Identity Provider Setup ===")
    print("Create Identity Provider...")
    credentialProviderArn = create_credential_provider(tavily_api_key)

    print(f"=== Tool Setup ===")
    print("Create Tool...")
    print("Integrations for tavily search is not supported yet as a target type based on documents from boto3.")
    print("ref: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agentcore-control/client/create_gateway_target.html")

if __name__ == "__main__":
    main()




        


