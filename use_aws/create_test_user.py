import boto3
import json
import os

def load_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    return config

def create_test_user():
    """Create a test user in Cognito User Pool"""
    try:
        config = load_config()
        user_pool_id = config['cognito']['user_pool_id']
        region = config['region']
        username = config['cognito']['test_username']
        password = config['cognito']['test_password']
        
        print(f"Creating test user in User Pool: {user_pool_id}")
        print(f"Username: {username}")
        print(f"Region: {region}")
        
        # Create Cognito Identity Provider client
        cognito_idp_client = boto3.client('cognito-idp', region_name=region)
        
        # Check if user already exists
        try:
            response = cognito_idp_client.admin_get_user(
                UserPoolId=user_pool_id,
                Username=username
            )
            print(f"✓ User '{username}' already exists")
            return True
        except cognito_idp_client.exceptions.UserNotFoundException:
            print(f"User '{username}' does not exist, creating...")
        
        # Create user
        response = cognito_idp_client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=username,
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': username
                },
                {
                    'Name': 'email_verified',
                    'Value': 'true'
                }
            ],
            TemporaryPassword=password,
            MessageAction='SUPPRESS'  # Don't send welcome email
        )
        
        print(f"✓ User '{username}' created successfully")
        
        # Set permanent password
        try:
            cognito_idp_client.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=username,
                Password=password,
                Permanent=True
            )
            print(f"✓ Password set for user '{username}'")
        except Exception as e:
            print(f"Warning: Could not set permanent password: {e}")
            print("User may need to change password on first login")
        
        return True
        
    except Exception as e:
        print(f"Error creating test user: {e}")
        return False

def list_users():
    """List all users in the User Pool"""
    try:
        config = load_config()
        user_pool_id = config['cognito']['user_pool_id']
        region = config['region']
        
        print(f"Listing users in User Pool: {user_pool_id}")
        
        cognito_idp_client = boto3.client('cognito-idp', region_name=region)
        
        response = cognito_idp_client.list_users(
            UserPoolId=user_pool_id
        )
        
        print(f"\nFound {len(response['Users'])} users:")
        for user in response['Users']:
            username = user['Username']
            status = user['UserStatus']
            created = user['UserCreateDate']
            print(f"  - {username} (Status: {status}, Created: {created})")
        
        return True
        
    except Exception as e:
        print(f"Error listing users: {e}")
        return False

def main():
    print("Cognito User Pool Management")
    print("=" * 30)
    
    # List existing users
    print("\n1. Listing existing users...")
    list_users()
    
    # Create test user
    print("\n2. Creating test user...")
    success = create_test_user()
    
    if success:
        print("\n✓ Test user setup completed successfully")
        print("\nYou can now run create_bearer_token.py to generate a bearer token")
    else:
        print("\n✗ Failed to create test user")
        print("\nPlease check your AWS credentials and User Pool configuration")

if __name__ == "__main__":
    main()
