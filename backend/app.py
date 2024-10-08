from flask import Flask, render_template
import os
import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Helper function to get secret from Azure Key Vault
def get_secret(secret_name):
    key_vault_name = os.environ["KEY_VAULT_NAME"]
    key_vault_uri = f"https://{key_vault_name}.vault.azure.net"

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=key_vault_uri, credential=credential)
    
    secret = client.get_secret(secret_name)
    return secret.value

# Landing page route
@app.route('/')
def index():
    return render_template('index.html')

# Route to call the Azure Functions app's test function
@app.route('/call-function')
def call_function():
    try:
        # Call the Azure Functions app's test function
        function_url = "https://quickscribefunctionapp.azurewebsites.net/api/test"
        response = requests.get(function_url, params={"name": "Chris"})
        
        if response.status_code == 200:
            return f"Function call successful! Response: {response.text}"
        else:
            return f"Failed to call function. Status code: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

# Route to call the Azure Functions app's test function
@app.route('/call-function-with-auth')
def call_function_with_auth():
    try:
        # Get the function key from Key Vault
        function_key = get_secret("AzureFunctionKey")
        
        # Call the Azure Functions app's test function
        function_url = "https://quickscribefunctionapp.azurewebsites.net/api/test_with_auth"
        headers = {"x-functions-key": function_key}
        params = {"name": "Chris"}
        response = requests.get(function_url, params=params, headers=headers)
        
        if response.status_code == 200:
            return f"Function call with auth successful! Response: {response.text}"
        else:
            return f"Failed to call function with auth. Status code: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)

