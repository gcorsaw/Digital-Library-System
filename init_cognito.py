import os
import time
import boto3
from botocore.exceptions import EndpointConnectionError

COGNITO_ENDPOINT = os.getenv("AWS_COGNITO_ENDPOINT", "http://cognito-local:9229")
REGION = "local"

def init_local_cognito():
    # Target our local container endpoint
    client = boto3.client(
        "cognito-idp",
        region_name=REGION,
        endpoint_url=COGNITO_ENDPOINT,
        aws_access_key_id="mock_key",
        aws_secret_access_key="mock_secret"
    )

    print("Connecting to cognito-local...")
    # Wait for container to be completely responsive
    for _ in range(10):
        try:
            pools = client.list_user_pools(MaxResults=1)
            break
        except EndpointConnectionError:
            time.sleep(2)
    else:
        print("Could not connect to cognito-local container.")
        return

    # Check if a local pool already exists to prevent duplicate spamming
    existing_pools = client.list_user_pools(MaxResults=10).get("UserPools", [])
    local_pool = next((p for p in existing_pools if p["Name"] == "LocalLibraryPool"), None)

    if not local_pool:
        print("Creating fresh local User Pool...")
        pool_response = client.create_user_pool(
            PoolName="LocalLibraryPool",
            Policies={
                "PasswordPolicy": {
                    "MinimumLength": 8,
                    "RequireUppercase": False,
                    "RequireLowercase": False,
                    "RequireNumbers": False,
                    "RequireSymbols": False
                }
            }
        )
        user_pool_id = pool_response["UserPool"]["Id"]
    else:
        print("Found existing local User Pool.")
        user_pool_id = local_pool["Id"]

    # Ensure an App Client exists for your Frontend/Backend interaction
    clients = client.list_user_pool_clients(UserPoolId=user_pool_id).get("UserPoolClients", [])
    if not clients:
        print("Creating App Client...")
        client_response = client.create_user_pool_client(
            UserPoolId=user_pool_id,
            ClientName="LocalLibraryClient",
            GenerateSecret=False
        )
        client_id = client_response["UserPoolClient"]["ClientId"]
    else:
        client_id = clients[0]["ClientId"]

    print("\n" + "="*50)
    print("SUCCESS: COGNITO LOCAL CONFIGURATION READY")
    print(f"COGNITO_USER_POOL_ID={user_pool_id}")
    print(f"COGNITO_APP_CLIENT_ID={client_id}")
    print("="*50 + "\n")

if __name__ == "__main__":
    init_local_cognito()
