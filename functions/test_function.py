import os
import requests
import click
from dotenv import load_dotenv

# Load the .env file that contains the FUNCTIONS_KEY
load_dotenv()

# Get the FUNCTIONS_KEY from the environment (for non-anonymous routes)
FUNCTIONS_KEY = os.getenv("FUNCTIONS_KEY")

# Define the base URL (this could be local or in the cloud)
LOCAL_URL = "http://localhost:7071/api"
CLOUD_URL = "http://quickscribefunctionapp.azurewebsites.net/api"

BASE_URL = ""

# Click group to define the base of our commands
@click.group()
@click.option('--env', default='local', help='Environment to use (local or cloud).')
def cli(env):
    """A CLI tool to interact with Azure Functions."""
    global BASE_URL
    BASE_URL = LOCAL_URL if env == "local" else CLOUD_URL

# Command to call the API version function
@cli.command()
def api_version():
    """Call the API version function."""
    url = f"{BASE_URL}/api_version"
    response = requests.get(url)
    click.echo(f"Status Code: {response.status_code}")
    click.echo(f"Response: {response.text}")

# Command to call the test function
@cli.command()
@click.option('--name', default=None, help='Name to send as a query parameter.')
def test(name):
    """Call the test function."""
    url = f"{BASE_URL}/test"
    payload = {"name": name} if name else {}
    response = requests.get(url, params=payload)
    click.echo(f"Status Code: {response.status_code}")
    click.echo(f"Response: {response.text}")

# Command to call the test function with authentication
@cli.command()
@click.option('--name', default=None, help='Name to send as a query parameter.')
def test_with_auth(name):
    """Call the test function with authentication."""
    url = f"{BASE_URL}/test_with_auth"
    headers = {"x-functions-key": FUNCTIONS_KEY} if FUNCTIONS_KEY else {}
    payload = {"name": name} if name else {}
    response = requests.get(url, params=payload, headers=headers)
    click.echo(f"Status Code: {response.status_code}")
    click.echo(f"Response: {response.text}")

# Command to call the Key Vault test function
@cli.command()
@click.option('--secret_name', default=None, help='Secret name to retrieve from Key Vault.')
def test_key_vault(secret_name):
    """Call the test Key Vault function."""
    url = f"{BASE_URL}/test_key_vault"
    headers = {"x-functions-key": FUNCTIONS_KEY} if FUNCTIONS_KEY else {}
    payload = {"secret_name": secret_name} if secret_name else {}
    response = requests.get(url, params=payload, headers=headers)
    click.echo(f"Status Code: {response.status_code}")
    click.echo(f"Response: {response.text}")

# Command to call the transcription function
@cli.command()
@click.argument('recording_id')
@click.argument('user_id')
def transcribe_recording(recording_id, user_id):
    """Call the transcribe recording function."""
    url = f"{BASE_URL}/transcribe_recording"
    click.echo(f"URL: {url}")
    click.echo(f"Recording ID: {recording_id}")
    click.echo(f"User ID: {user_id}")
    headers = {"x-functions-key": FUNCTIONS_KEY} if FUNCTIONS_KEY else {}
    payload = {"recording_id": recording_id, "user_id": user_id}
    response = requests.post(url, json=payload, headers=headers)
    click.echo(f"Status Code: {response.status_code}")
    click.echo(f"Response: {response.text}")

# Entry point
if __name__ == "__main__":
    cli()
