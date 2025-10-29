#!/usr/bin/env python3
import json
import boto3
from botocore.exceptions import ClientError

SECRET_NAME = "/dmtalerts/emailcredentials"
AWS_REGION  = "us-east-1"  # change if needed

# REQUIRED: set the sender email you’ll send from
SENDER_EMAIL = "dmtalerts@shift4.com"

# # Your provided OAuth client JSON (desktop app)
# GOOGLE_CLIENT_JSON = {
#     "installed": {
#         "client_id": "392234495735-3q26q7nutav705q7ha0kut871bpke5v4.apps.googleusercontent.com",
#         "project_id": "dmt-dashboard-473803",
#         "auth_uri": "https://accounts.google.com/o/oauth2/auth",
#         "token_uri": "https://oauth2.googleapis.com/token",
#         "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
#         "client_secret": "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",
#         "redirect_uris": ["https://dmtdashboard.link"]
#     }
# }

# Your provided OAuth client JSON (desktop app)
GOOGLE_CLIENT_JSON = {
    "installed": {
        "client_id": "792555584447-eim6j4vno7jhdankmd664nleoraimona.apps.googleusercontent.com",
        "project_id": "dmt-alerts",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "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",
        "redirect_uris": ["https://dmtdashboard.link"]
    }
}


def upsert_secret(name: str, region: str, payload: dict):
    sm = boto3.client("secretsmanager", region_name=region)
    try:
        sm.create_secret(Name=name, SecretString=json.dumps(payload))
        print(f"Created secret: {name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceExistsException":
            sm.update_secret(SecretId=name, SecretString=json.dumps(payload))
            print(f"Updated secret: {name}")
        else:
            raise

if __name__ == "__main__":
    # We store email + client JSON. refresh_token will be added by the next script.
    secret_payload = {
        "email": SENDER_EMAIL,
        "installed": GOOGLE_CLIENT_JSON["installed"]
        # "refresh_token": "will be inserted automatically on first auth"
    }
    upsert_secret(SECRET_NAME, AWS_REGION, secret_payload)
