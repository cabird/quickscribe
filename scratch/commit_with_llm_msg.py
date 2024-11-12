import os
import subprocess
import requests
import json
from dotenv import load_dotenv
import sys
import re

os.environ["GIT_EDITOR"] = "true"

def clean_output(output):
    # Remove non-printable characters
    return re.sub(r'[^\x20-\x7E]', '', output)

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



def get_current_diff():
    """Get the current diff for the repository."""
    result = subprocess.run(["git", "diff", "--cached", "--no-color"], capture_output=True, text=True, encoding="utf-8")
    diff = clean_output(result.stdout)
    result = subprocess.run(["git", "diff", "--no-color"], capture_output=True, text=True, encoding="utf-8")
    diff += "\n\n"
    diff += clean_output(result.stdout)
    return diff

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

    # Show the generated commit message and ask for confirmation
    print(f"Generated Commit Message:\n{new_commit_message}")
    user_input = input("Do you want to commit with this message? (yes/no): ").strip().lower()

    if user_input == 'yes':
        # Write the commit message to a temporary file
        with open("temp_commit_msg.txt", "w") as msg_file:
            msg_file.write(new_commit_message)
        
        # Run the git commit command using the generated message from the file
        subprocess.run(["git", "commit", "-a", "-F", "temp_commit_msg.txt"])

        # Optionally, remove the temporary commit message file after the commit
        os.remove("temp_commit_msg.txt")
        print("Changes have been committed.")
    else:
        print("Commit aborted.")

if __name__ == "__main__":
    main()
