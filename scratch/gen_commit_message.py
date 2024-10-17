import os
import subprocess
import requests
import json
from dotenv import load_dotenv
import sys

load_dotenv()

# Configuration
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
ENDPOINT = os.getenv("AZURE_OPENAI_API_ENDPOINT")
DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

ENDPOINT = f"{ENDPOINT}/openai/deployments/{DEPLOYMENT_NAME}/chat/completions?api-version={API_VERSION}"
headers = {
    "Content-Type": "application/json",
    "api-key": API_KEY,
}

# Payload template for the request
payload = {
    "messages": [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are an AI assistant that helps generate clear and descriptive commit messages for Git changes."
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": ""
                }
            ]
        }
    ],
    "temperature": 0.1,
    "top_p": 0.95,
    "max_tokens": 150
}

def send_prompt_to_llm(prompt):
    payload["messages"][1]["content"][0]["text"] = prompt

    # Send request
    try:
        response = requests.post(ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.RequestException as e:
        raise SystemExit(f"Failed to make the request. Error: {e}")

    return response.json()["choices"][0]["message"]["content"]

def get_commit_hashes():
    """Get a list of all commit hashes in the repository."""
    result = subprocess.run(["git", "rev-list", "--reverse", "HEAD"], capture_output=True, text=True)
    return result.stdout.splitlines()

def get_patch(commit_hash):
    """Get the patch for a specific commit."""
    result = subprocess.run(["git", "show", commit_hash], capture_output=True, text=True)
    return result.stdout

def get_current_diff():
    """Get the current diff for the repository."""
    result = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True)
    diff = result.stdout
    result = subprocess.run(["git", "diff"], capture_output=True, text=True)
    diff += "\n\n"
    diff += result.stdout
    return diff

def main_old():
    # Get all commit hashes in the repository in reverse order (oldest to newest)
    commit_hashes = get_commit_hashes()
    commit_hashes.reverse()

    new_commit_messages = []

    for commit_hash in commit_hashes:
        # Get the patch for the current commit
        patch = get_patch(commit_hash)

        # Generate a prompt for the LLM
        prompt = f"""Based on the following git diff output, generate a concise, descriptive commit message:\n\n{patch}.
        Ignore changes to api versions such as changing the api version in api_version.py
        Only output the commit message, no other text."""

        # Send the patch to the LLM to get a new commit message
        new_commit_message = send_prompt_to_llm(prompt)
        new_commit_messages.append(new_commit_message)
        print(f"Old commit hash: {commit_hash}")
        print(f"New commit message:\n{new_commit_message}")
        print("\n\n")

    # write all of these to a file
    with open("commit_messages.txt", "w") as f:
        for commit_hash, new_commit_message in zip(commit_hashes, new_commit_messages):
            f.write(f"Old commit hash: {commit_hash}\n")
            f.write(f"New commit message:\n{new_commit_message}\n\n")   

    print("All commit messages have been updated.")

def main():
    current_diff = get_current_diff()
    prompt = f"""Based on the following git diff output, generate a concise, descriptive commit message:\n\n{current_diff}.
    Ignore changes to api versions such as changing the api version in api_version.py
    Only output the commit message, no other text or quotes.  Just one line for the description
    and a bullet list of the changes.  Example:  
    
    Added logging and authorization
    - Added feature X
    - Fixed bug Y
    - Changed API Z
    """

    new_commit_message = send_prompt_to_llm(prompt)
    #replace quotes, double quotes, and backticks with empty string
    new_commit_message = new_commit_message.replace('"', '').replace("'", '').replace("`", "")
    #remove leading and trailing newlines
    new_commit_message = new_commit_message.strip() + "\n"
    print(f"{new_commit_message}")

if __name__ == "__main__":
    main()
