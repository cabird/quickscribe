

import os
import subprocess
import requests
import json
from dotenv import load_dotenv
import sys
import argparse
import tiktoken
import hashlib
from typing import List, Dict

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

class TokenCounter:
    def __init__(self):
        self.encoding = tiktoken.encoding_for_model("gpt-4o")
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0

        input_cost_per_million = 2.5
        output_cost_per_million = 10

    def count_input_tokens(self, prompt):
        token_count = len(self.encoding.encode(prompt))
        self.input_tokens += token_count
        self.total_tokens += token_count
        return token_count

    def count_output_tokens(self, response):
        token_count = len(self.encoding.encode(response))
        self.output_tokens += token_count
        self.total_tokens += token_count
        return token_count

    def total_cost(self):
        input_cost = self.input_tokens * 2.5 / 1000000
        output_cost = self.output_tokens * 10 / 1000000
        return input_cost + output_cost

    def total_cost_str(self):
        return f"${self.total_cost():.2f}"

token_counter = TokenCounter()

def send_prompt_to_llm(prompt):
    token_counter.count_input_tokens(prompt)
    payload["messages"][1]["content"][0]["text"] = prompt

    # Send request
    try:
        response = requests.post(ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.RequestException as e:
        raise SystemExit(f"Failed to make the request. Error: {e}")
    
    returned_content = response.json()["choices"][0]["message"]["content"]
    token_counter.count_output_tokens(returned_content)
    return returned_content

def read_file_content(filepath: str) -> str:
    """Reads and returns the content of the specified file."""
    with open(filepath, 'r') as file:
        return file.read()

def get_file_md5(content: str) -> str:
    """Calculate MD5 hash of file content."""
    return hashlib.md5(content.encode()).hexdigest()



skips = ["node_modules", "azure_speech", "venv", "pycache", ".git", "scratch"]
extensions = ["py", "html", "js", "ts", "css", "tsx", "tsconfig", "yaml"]
keep_files = ["Makefile", "package.json"]
def get_all_files_in_tree_rec(dir: str, files: List[str] = []) -> List[str]:
    for file in os.listdir(dir):
        if os.path.isfile(os.path.join(dir, file)):
            extension = file.split(".")[-1]
            if extension in extensions or file in keep_files:
                files.append(os.path.join(dir, file))
        else:
            if any(skip in file for skip in skips):
                continue
            get_all_files_in_tree_rec(os.path.join(dir, file))
    return files

def extract_json_from_llm_response(response: str):
    """ LLM responses are often wrapped in other text, so we need to extract the JSON """
    json_text = response[response.find('{'):response.rfind('}')+1]
    return json.loads(json_text)

def index_file(filepath: str, all_files: List[str]) -> dict:
    content = read_file_content(filepath)
    md5sum = get_file_md5(content)
    
    prompt = index_file_prompt.replace("__FILE_CONTENTS__", content)
    prompt = prompt.replace("__ALL_FILES__", "\n".join(all_files))
    value = send_prompt_to_llm(prompt)

    object = extract_json_from_llm_response(value)
    object["filepath"] = filepath
    object["md5sum"] = md5sum
    return object

def query_index(query: str, index: Dict[str, dict]) -> str:
    prompt = query_prompt.replace("__QUERY__", query)
    prompt = prompt.replace("__INDEX__", json.dumps(index, indent=2))
    return send_prompt_to_llm(prompt)

def load_index_file(filepath: str) -> Dict[str, dict]:
    with open(filepath, "r") as file:
        return json.load(file)

def save_index_file(filepath: str, index: Dict[str, dict]):
    with open(filepath, "w") as file:
        json.dump(index, file, indent=2)

def update_index(main_index_file: str):
    if os.path.exists(main_index_file):
        main_index = load_index_file(main_index_file)
    else:
        main_index = {}
    
    all_files = get_all_files_in_tree_rec(".")

    for file in all_files:
        content = read_file_content(file)
        current_md5 = get_file_md5(content)
        
        if file in main_index and main_index[file].get("md5sum") == current_md5:
            print(f"Skipping {file} - unchanged")
            continue
            
        print(f"Indexing file: {file}")
        info = index_file(file, all_files)
        main_index[file] = info
        print(f"Total tokens: {token_counter.total_tokens}")
        print(f"Input tokens: {token_counter.input_tokens}")
        print(f"Output tokens: {token_counter.output_tokens}")
        save_index_file(main_index_file, main_index)

def fixup_index(main_index_file: str):
    main_index = load_index_file(main_index_file)
    # add the md5sums to each file in the index because we forgot to the first time
    for file in main_index:
        print(f"Fixing up {file}")
        content = read_file_content(file)
        md5sum = get_file_md5(content)
        main_index[file]["md5sum"] = md5sum
    save_index_file(main_index_file, main_index)

def get_relevant_files(query: str, index: Dict[str, dict]) -> str:
    prompt = relevant_files_prompt.replace("__QUERY__", query)
    prompt = prompt.replace("__FILES__", json.dumps(index, indent=2))
    value = send_prompt_to_llm(prompt)
    relevant_files = extract_json_from_llm_response(value)
    print(f"Relevant files: {json.dumps(relevant_files, indent=2)}")
    return [file["file"] for file in relevant_files["files"]]


def answer_query(query: str, index_file: str) -> str:
    main_index = load_index_file(index_file)
    relevant_files = get_relevant_files(query, main_index)
    prompt = query_prompt.replace("__QUERY__", query)
    relevant_file_contents = "\n".join([f"\n\n*** CONTENTS OF {file} ***\n\n{read_file_content(file)}\n\n*** END OF {file} ***\n\n" for file in relevant_files])
    prompt = prompt.replace("__RELEVANT_FILES__", relevant_file_contents)
    return send_prompt_to_llm(prompt)


def main():
    parser = argparse.ArgumentParser(description='Project file indexer and query tool')
    parser.add_argument('--update', action='store_true', help='Update the project index')
    parser.add_argument('--query', type=str, help='Query the project index')
    parser.add_argument('--index-file', type=str, default="file_index.json", help='Path to index file')
    parser.add_argument('--fixup', action='store_true', help='Fixup the index file')
    
    args = parser.parse_args()
    
    if args.update:
        update_index(args.index_file)
    elif args.fixup:
        fixup_index(args.index_file)
    elif args.query:
        if not os.path.exists(args.index_file):
            print("Index file does not exist. Please run --update first.")
            return
        response = answer_query(args.query, args.index_file)
        print(response)

    else:
        parser.print_help()
    
    #output the token count
    print(f"Total tokens: {token_counter.total_tokens}")
    print(f"Input tokens: {token_counter.input_tokens}")
    print(f"Output tokens: {token_counter.output_tokens}")
    print(f"Total cost: {token_counter.total_cost_str()}")
index_file_prompt = """
You are an AI specialized in analyzing project files. I will provide the contents of a file, which 
may be in Python, HTML, JavaScript, Makefile, JSON, or another format. Please analyze the file and 
return the following information in JSON format, strictly adhering to the fields provided. Respond 
only with JSON, with no additional text.

1. **file_type**: The file's type (e.g., Python, HTML, JavaScript, Makefile, JSON).
2. **purpose**: A brief summary of the file's main purpose or functionality.
3. **core_elements**: Key elements in the file, such as:
   - **classes** (for code files): List of class names and their roles.
   - **functions** (for code files): List of function names and a brief purpose of each.
   - **structures** (for JSON or data files): Key data structures, if applicable.
4. **dependencies**: Other files or modules referenced or required for this file to function.
5. **related_files**: Other project files this file is related to or dependent on, with a brief explanation of each relationship.

Please return the information in the following JSON format:

{
    "file_type": "<file type>",
    "purpose": "<brief purpose of the file>",
    "core_elements": {
        "classes": [{"name": "<class name>", "description": "<role of the class>"}],
        "functions": [{"name": "<function name>", "description": "<role of the function>"}],
        "structures": [{"name": "<structure name>", "description": "<role of the structure>"}]
    },
    "dependencies": ["<other files/modules used>"],
    "related_files": [{"file": "<related file>", "relationship": "<brief explanation>"}]
}

Respond strictly in JSON format with nothing else.

Here are all of the files in the project, which may be helpful in identifying
which files are related to this one:

__ALL_FILES__

Here is the contents of the file:

__FILE_CONTENTS__
"""

query_prompt = """
You are an AI specialized in analyzing project files in order to answer questions about the project.  Here is a query that I need help answering:

__QUERY__

I've already determined that the following files are relevant to the question so I've included their contents below:

__RELEVANT_FILES__

Please respond with a concise answer to the question based on the information in the relevant files.

Again, the question is:

__QUERY__

"""

relevant_files_prompt = """
I need help answering the following query:

__QUERY__

It may be useful to include the content of files in my repository to help answer the question.
Here is a list of files in my project and information about them:

__FILES__

Please respond with a list of files that would be helpful in answering the question from 
highest relevance to lowest (don't include ALL files, just the most relevant ones). For each file
include the file path and a brief explanation of why it is relevant.

Again, the question is:

__QUERY__

Your response should be in JSON format with the following fields:
{
    "files": [
        {"file": "<file path>", "explanation": "<brief explanation>"}
    ]
}

Please respond strictly in JSON format with nothing else.
"""

if __name__ == "__main__":
    main()
