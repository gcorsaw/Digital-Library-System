import aws_encryption_sdk
import base64
import os

def lambda_handler(event, context):
    if event.get("triggerSource") == "CustomEmailSender_SignUp":
        client = aws_encryption_sdk.EncryptionSDKClient()
        
        kms_key_provider = aws_encryption_sdk.StrictAwsKmsMasterKeyProvider(
            key_ids=[os.environ["KMS_KEY_ARN"]]
        )
        
        decrypted_code, _ = client.decrypt(
            source=base64.b64decode(event["request"]["code"]),
            key_provider=kms_key_provider
        )
        
        code = decrypted_code.decode("utf-8")
        
        # TODO: Send code via SES or another email provider
        print(f"Code to send: {code}")
    
    return event
