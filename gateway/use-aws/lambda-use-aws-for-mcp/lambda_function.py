import json
import boto3
import os

def lambda_handler(event, context):
    print(f"event: {event}")
    print(f"context: {context}")

    toolName = context.client_context.custom['bedrockAgentCoreToolName']
    print(f"context.client_context: {context.client_context}")
    print(f"Original toolName: {toolName}")
    
    delimiter = "___"
    if delimiter in toolName:
        toolName = toolName[toolName.index(delimiter) + len(delimiter):]
    print(f"Converted toolName: {toolName}")

    keyword = event.get('keyword')
    print(f"keyword: {keyword}")

    if toolName == 'retrieve':
        return {
            'statusCode': 200, 
            'body': f"{toolName} is supported"
        }
    else:
        return {
            'statusCode': 200, 
            'body': f"{toolName} is not supported"
        }