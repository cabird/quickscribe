import os
import subprocess
import requests
import json
from dotenv import load_dotenv
import sys
import argparse
import tiktoken

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
                    "text": "You are an automated software engineer that can look at and understand code and make requested changes to it."
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
    "max_tokens": 4000
}

def count_tokens(prompt):
    encoding = tiktoken.encoding_for_model("gpt-4o")
    return len(encoding.encode(prompt))

def send_prompt_to_llm(prompt):
    payload["messages"][1]["content"][0]["text"] = prompt

    # Send request
    try:
        response = requests.post(ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.RequestException as e:
        raise SystemExit(f"Failed to make the request. Error: {e}")

    return response.json()["choices"][0]["message"]["content"]

def read_file_content(filepath: str) -> str:
    """Reads and returns the content of the specified file."""
    with open(filepath, 'r') as file:
        return file.read()

def construct_prompt(primary_file: str, context_files: list, request_text: str) -> str:
    """Constructs a detailed prompt for the LLM to generate code updates on the primary file.

    Args:
        primary_file (str): The main file to be modified.
        context_files (list): List of files providing additional context.
        request_text (str): Instructions detailing the modifications to apply to the primary file.

    Returns:
        str: The complete prompt to send to the LLM.
    """
    # Read primary file content
    primary_content = read_file_content(primary_file)
    
    # Collect context file contents with clear separation labels
    context_content = "\n\n".join(
        f"File: {os.path.basename(f)}\n---\n{read_file_content(f)}"
        for f in context_files
    )
    
    # Construct the prompt with clear instructions
    prompt = (
        f"You are an AI-based software engineer. I will provide you with code in a primary file that needs specific changes, "
        f"along with several context files to help you understand the structure and dependencies. Your task is to modify only "
        f"the code in the primary file to meet the given request. Please ensure that only the updated file text itself is returned, "
        f"without any additional explanations or notes.  Don't even put quotes or any kind of delimeter around it\n\n"
        
        f"Primary file:\n---\n{os.path.basename(primary_file)}\n{primary_content}\n\n"
        f"Context files:\n{context_content}\n\n"
        
        f"Modification request:\n{request_text}"
    )
    
    return prompt

def save_new_version(primary_file: str, new_code: str) -> None:
    """Saves the modified code to a new file with '.llm_update' appended to the original filename."""
    new_file_path = f"{primary_file}.llm_update"
    with open(new_file_path, 'w') as file:
        file.write(new_code)
    print(f"Updated file saved as: {new_file_path}")

def construct_query_prompt(primary_file: str, context_files: list, request_text: str) -> str:
    """Constructs a prompt for querying based on the primary file and context files.

    Args:
        primary_file (str): The main file to provide information for the query.
        context_files (list): List of files providing additional context.
        request_text (str): The question or query for the LLM to answer.

    Returns:
        str: The complete prompt to send to the LLM.
    """
    primary_content = read_file_content(primary_file)
    context_content = "\n\n".join(
        f"File: {os.path.basename(f)}\n---\n{read_file_content(f)}"
        for f in context_files
    )

    prompt = (
        f"You are an AI-based software assistant with expertise in understanding code and answering questions about it. "
        f"Using the provided primary file and any additional context files, please answer the following question.\n\n"
        
        f"Primary file:\n---\n{os.path.basename(primary_file)}\n{primary_content}\n\n"
        f"Context files:\n{context_content}\n\n"
        
        f"Question:\n{request_text}"
    )
    
    return prompt


def main():
    parser = argparse.ArgumentParser(
        description="Modify a primary file based on a given request or answer a question using optional context files."
    )
    parser.add_argument("primary_file", help="The main file to be modified or used for querying")
    parser.add_argument("context_files", nargs='*', help="Optional list of context files to provide additional information")
    parser.add_argument("--query", action="store_true", help="If set, the script will answer a question instead of modifying the primary file")
    # read the query or request text from a file if the user specifies a filename with "--request-file"
    parser.add_argument("--request-file", help="The filename of the file containing the request text")
    parser.add_argument("--request-text", help="The request text to be used instead of reading from a file")
    if parser.parse_args().request_file:
        request_text = read_file_content(parser.parse_args().request_file)
    else:
        request_text = parser.parse_args().request_text

    args = parser.parse_args()

    primary_file = args.primary_file
    request_text = args.request_text
    context_files = args.context_files
    # if the primary file is in the context files, remove it
    if primary_file in context_files:
        context_files.remove(primary_file)
    is_query = args.query

    # Construct prompt based on the mode
    if is_query:
        prompt = construct_query_prompt(primary_file, context_files, request_text)
    else:
        prompt = construct_prompt(primary_file, context_files, request_text)

    token_count = count_tokens(prompt)
    print(f"Token count: {token_count}")    

    # Confirm with the user
    confirm = input("Do you want to proceed with sending the prompt? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Operation canceled.")
        return

    # Send prompt to LLM and get response
    response = send_prompt_to_llm(prompt)

    # Handle output based on the mode
    if is_query:
        print("Answer to your query:\n", response)
    else:
        save_new_version(primary_file, response)



if __name__ == "__main__":
    main()