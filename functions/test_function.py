import os
import sys
import requests
from dotenv import load_dotenv

# Load the .env file that contains the FUNCTIONS_KEY
load_dotenv()

# Get the FUNCTIONS_KEY from the environment (for non-anonymous routes)
FUNCTIONS_KEY = os.getenv("FUNCTIONS_KEY")

# Define the base URL (this could be local or in the cloud)
LOCAL_URL = "http://localhost:7071/api"
CLOUD_URL = "http://quickscribefunctionapp.azurewebsites.net/api"

BASE_URL = ""

def call_api_version_function():
    url = f"{BASE_URL}/api_version"
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

def call_test_function(name=None):
    url = f"{BASE_URL}/test"
    payload = {"name": name} if name else {}
    response = requests.get(url, params=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

def call_test_with_auth_function(name=None):
    url = f"{BASE_URL}/test_with_auth"
    headers = {"x-functions-key": FUNCTIONS_KEY} if FUNCTIONS_KEY else {}
    payload = {"name": name} if name else {}
    response = requests.get(url, params=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

def call_test_key_vault_function(secret_name=None):
    url = f"{BASE_URL}/test_key_vault"
    headers = {"x-functions-key": FUNCTIONS_KEY} if FUNCTIONS_KEY else {}
    payload = {"secret_name": secret_name} if secret_name else {}
    response = requests.get(url, params=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")


def call_transcribe_recording_function(recording_id, user_id):
    url = f"{BASE_URL}/transcribe_recording"
    headers = {"x-functions-key": FUNCTIONS_KEY} if FUNCTIONS_KEY else {}
    payload = {"recording_id": recording_id, "user_id": user_id}
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

# Main entry point for the script
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_functions.py {local|cloud} <function_name> [optional_args]")
        sys.exit(1)

    BASE_URL = LOCAL_URL if sys.argv[1] == "local" else CLOUD_URL

    function_name = sys.argv[2]

    if function_name == "test":
        name = sys.argv[3] if len(sys.argv) > 3 else None
        call_test_function(name)
    elif function_name == "test_with_auth":
        name = sys.argv[3] if len(sys.argv) > 3 else None
        call_test_with_auth_function(name)
    elif function_name == "test_key_vault":
        secret_name = sys.argv[3] if len(sys.argv) > 3 else None
        call_test_key_vault_function(secret_name)
    elif function_name == "api_version":
        call_api_version_function()
    elif function_name == "transcribe_recording":
        recording_id = sys.argv[3] if len(sys.argv) > 3 else None
        user_id = sys.argv[4] if len(sys.argv) > 4 else None
        call_transcribe_recording_function(recording_id, user_id)
    else:
        print(f"Unknown function: {function_name}")
