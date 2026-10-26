import os
import sys
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError

COGNITO_ENDPOINT = os.getenv("AWS_COGNITO_ENDPOINT", "http://cognito-local:9229")
REGION = os.getenv("AWS_REGION", "us-east-1")


def init_local_cognito():
    # Target the local cognito-local container, not real AWS
    client = boto3.client(
        "cognito-idp",
        region_name=REGION,
        endpoint_url=COGNITO_ENDPOINT,
        aws_access_key_id="mock_key",
        aws_secret_access_key="mock_secret",
    )

    print(f"Connecting to cognito-local at {COGNITO_ENDPOINT}...")
    # Wait for the container to be responsive (any connection-level error -> retry)
    for _ in range(15):
        try:
            client.list_user_pools(MaxResults=1)
            break
        except (BotoCoreError, ClientError, OSError):
            time.sleep(2)
    else:
        print("Could not connect to cognito-local container.", file=sys.stderr)
        sys.exit(1)  # non-zero so docker compose shows the failure

    existing_pools = client.list_user_pools(MaxResults=10).get("UserPools", [])
    local_pool = next((p for p in existing_pools if p["Name"] == "LocalLibraryPool"), None)

    if not local_pool:
        print("Creating fresh local User Pool...")
        pool_response = client.create_user_pool(
            PoolName="LocalLibraryPool",
            AutoVerifiedAttributes=["email"],
            Policies={
                "PasswordPolicy": {
                    "MinimumLength": 8,
                    "RequireUppercase": False,
                    "RequireLowercase": False,
                    "RequireNumbers": False,
                    "RequireSymbols": False,
                }
            },
        )
        user_pool_id = pool_response["UserPool"]["Id"]
    else:
        print("Found existing local User Pool.")
        user_pool_id = local_pool["Id"]

    clients = client.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=10).get(
        "UserPoolClients", []
    )
    if not clients:
        print("Creating App Client...")
        client_response = client.create_user_pool_client(
            UserPoolId=user_pool_id,
            ClientName="LocalLibraryClient",
            GenerateSecret=False,
            # The backend logs users in with USER_PASSWORD_AUTH
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        )
        client_id = client_response["UserPoolClient"]["ClientId"]
    else:
        client_id = clients[0]["ClientId"]

    print("\n" + "=" * 50)
    print("SUCCESS: COGNITO LOCAL CONFIGURATION READY")
    print("Copy these two lines into your .env file:")
    print(f"COGNITO_USER_POOL_ID={user_pool_id}")
    print(f"COGNITO_CLIENT_ID={client_id}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    init_local_cognito()