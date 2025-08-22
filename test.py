import boto3

print(boto3.client('sts').get_caller_identity()['Account'])