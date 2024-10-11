import azure.functions as func
import datetime
import json
import os
import logging
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import hashlib
from dotenv import load_dotenv
from api_version import API_VERSION

load_dotenv()
app = func.FunctionApp()


# Function to get secret from Key Vault
def get_secret(secret_name):
    #key_vault_name = os.environ["KEY_VAULT_NAME"]
    key_vault_name = "QuickScribeKeyVault"
    key_vault_uri = f"https://{key_vault_name}.vault.azure.net"
    
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=key_vault_uri, credential=credential)
    
    retrieved_secret = client.get_secret(secret_name)
    return retrieved_secret.value

# get the api version
@app.route(route="api_version", auth_level=func.AuthLevel.ANONYMOUS)
def api_version(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(API_VERSION, status_code=200)

@app.route(route="test_key_vault", auth_level=func.AuthLevel.FUNCTION)
def test_key_vault(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing request to retrieve secret from Key Vault.')

    # Retrieve secret name from query parameters or request body
    secret_name = req.params.get('secret_name')
    if not secret_name:
        try:
            req_body = req.get_json()
            secret_name = req_body.get('secret_name')
        except (ValueError, KeyError):
            pass

    if not secret_name:
        return func.HttpResponse(
            "Please pass a secret name in the query string or request body",
            status_code=400
        )

    try:
        # Retrieve the secret from Key Vault using the helper function
        secret_value = get_secret(secret_name)
        # share the md5sum of the secret value, but not the secret value itself
        md5sum = hashlib.md5(secret_value.encode()).hexdigest()
        return func.HttpResponse(f"md5sum of secret value: {md5sum}", status_code=200)
    except Exception as e:
        logging.error(f"Failed to retrieve secret: {e}")
        return func.HttpResponse(f"Failed to retrieve secret: {str(e)}", status_code=500)

@app.route(route="test", auth_level=func.AuthLevel.ANONYMOUS)
def test(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
            
@app.route(route="test_with_auth", auth_level=func.AuthLevel.FUNCTION)
def test_with_auth(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )