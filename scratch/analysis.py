

import os
import subprocess
import requests
import json
from dotenv import load_dotenv
import sys
import argparse
import tiktoken
import hashlib
from typing import List, Dict, Tuple
from datetime import datetime
import logging
import io

log_buffer = io.StringIO()

# Clear any existing handlers on the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()  # Clears all existing handlers

# Set up new handlers
console = logging.StreamHandler(sys.stdout)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
file_handler = logging.FileHandler(f"analysis_{timestamp}.log")
string_io_handler = logging.StreamHandler(log_buffer)

# Add only one instance of each handler
root_logger.addHandler(console)
root_logger.addHandler(file_handler)
root_logger.addHandler(string_io_handler)

logging.info(f"Logging to log file {file_handler.baseFilename}")

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

def get_directory_md5(directory_path: str, index: Dict[str, dict]) -> str:
    #simply concatenate all the paths of the files in the index that are in this directory
    files = [index[file]["path"] for file in index if os.path.dirname(index[file]["path"]) == directory_path]
    files.sort()
    return hashlib.md5(("\n".join(files)).encode()).hexdigest()

skips = ["node_modules", "azure_speech", "venv", "pycache", 
    ".git", "scratch", "defunct", ".yarn", "dist"]
extensions = ["py", "html", "js", "ts", "css", "tsx", "tsconfig", "yaml", "mjs", "cjs"]
keep_files = ["Makefile", "package.json", "tsconfig.json"]
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
    object["path"] = filepath
    object["md5sum"] = md5sum
    object["kind"] = "file"
    return object

def index_directory(target_dir: str, index: Dict[str, dict]) -> dict:
    logging.info(f"Indexing directory: {target_dir}")
    #find all files and directories in the directory
    files = []
    for file in index:
        if os.path.dirname(file) != target_dir or index[file]["kind"] == "directory":
            continue
        files.append(index[file])

    directories = []
    for dir_name in index:
        if os.path.dirname(dir_name) != target_dir or index[dir_name]["kind"] == "file":
            continue
        directories.append(index[dir_name])
        
    elements = files + directories
    elements_str = json.dumps(elements, indent=2)
    logging.info(f"Elements:\n{elements_str}\n")
    prompt = index_directory_prompt.replace("__FILES__", elements_str).replace("__DIRECTORY__", target_dir)
    logging.info(f"Prompt:\n{prompt}\n")
    value = send_prompt_to_llm(prompt)
    object = extract_json_from_llm_response(value)
    logging.info(f"Response:\n{json.dumps(object, indent=2)}\n")
    object["path"] = target_dir
    object["kind"] = "directory"
    object["md5sum"] = get_directory_md5(target_dir, index)
    dir_items = []
    for file in files:
        dir_items.append(f"file:{file['path']} - {file['purpose']}")
    for directory in directories:
        dir_items.append(f"directory:{directory['path']} - {directory['description']}")
    object["elements"] = dir_items

    #output the object:
    logging.info(f"results for directory: {target_dir}\n{json.dumps(object, indent=2)}")
    #ask the user if they want to continue or stop
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

    # first index all of the files
    all_files = get_all_files_in_tree_rec(".")
    for file in all_files:
        content = read_file_content(file)
        current_md5 = get_file_md5(content)
        
        if file in main_index and main_index[file].get("md5sum") == current_md5:
            logging.info(f"Skipping {file} - unchanged")
            continue
            
        logging.info(f"Indexing file: {file}")
        info = index_file(file, all_files)
        main_index[file] = info
        logging.info(f"Total tokens: {token_counter.total_tokens}")
        logging.info(f"Input tokens: {token_counter.input_tokens}")
        logging.info(f"Output tokens: {token_counter.output_tokens}")
        save_index_file(main_index_file, main_index)

    
    # now index all of the directories
    directories = get_directories_sorted(all_files)
    for directory in directories:
        md5sum = get_directory_md5(directory, main_index)
        if directory in main_index and main_index[directory].get("md5sum", "") == md5sum:
            logging.info(f"Skipping directory {directory} - unchanged")
            continue
        info = index_directory(directory, main_index)
        main_index[directory] = info
        logging.info(f"Total tokens: {token_counter.total_tokens}")
        logging.info(f"Input tokens: {token_counter.input_tokens}")
        logging.info(f"Output tokens: {token_counter.output_tokens}")
        save_index_file(main_index_file, main_index)

def get_directories_sorted(file_paths: List[str]) -> List[str]:
    # Use a set to store unique directories
    directories = set()

    # Extract all directories from file paths
    for path in file_paths:
        # Get each directory in the path by iterating from the full path back to the root
        while path != "":
            path = os.path.dirname(path)  # Get the directory path
            if path and path != "/":  # Skip empty and root paths
                directories.add(path)

    # Sort directories by depth, ensuring subdirectories come before parent directories
    sorted_directories = sorted(directories, key=lambda d: d.count(os.sep), reverse=True)
    return sorted_directories

def fixup_index(main_index_file: str):
    main_index = load_index_file(main_index_file)
    # add the md5sums to each file in the index because we forgot to the first time
    to_remove = []
    for file in main_index.keys():
        logging.info(f"Fixing up {file}")
        if not os.path.exists(file):
            logging.warning(f"File {file} does not exist")
            to_remove.append(file)
            continue
        # check if the file is actually a file and not a directory
        if os.path.isfile(file):    
            content = read_file_content(file)
            md5sum = get_file_md5(content)
            main_index[file]["md5sum"] = md5sum
        if "filepath" in main_index[file]:
            main_index[file].pop("filepath")
        main_index[file]["path"] = file
        #if this is a file then set the kind to file
        if os.path.isfile(file):
            main_index[file]["kind"] = "file"
        else:
            main_index[file]["kind"] = "directory"
    for file in to_remove:
        main_index.pop(file)
    save_index_file(main_index_file, main_index)



def get_info_for_llm_relevance(item: Dict[str, str]) -> str:
    info = {}
    fields = ["path", "kind"]
    if item["kind"] == "directory":
        fields += ["description"]
    elif item["kind"] == "file":
        fields += ["type", "purpose", "elements"]
    for field in fields:
        info[field] = item[field]
    return info

def get_relevant_files_rec(query: str, cur_dir: str, index: Dict[str, dict], relevant_files: List[Tuple[str, str]] = []) -> List[Tuple[str, str]]:
    logging.info(f"Getting relevant files and directories for {cur_dir}")
    # get the files and subdirectories in the current directory from the index using dirname
    item_infos = [get_info_for_llm_relevance(index[item]) for item in index if os.path.dirname(item) == cur_dir]
    item_infos_str = json.dumps(item_infos, indent=2)

    #list the paths of the files and directories in the current directory
    paths = [index[item]["path"] for item in index if os.path.dirname(item) == cur_dir]
    paths_str = json.dumps(paths, indent=2)
    logging.info(f"Paths:\n{paths_str}")

    logging.info(f"Item infos:\n{item_infos_str}")

    prompt = relevant_items_prompt \
        .replace("__QUERY__", query) \
        .replace("__ITEMS__", item_infos_str) \
        .replace("__DIRECTORY__", cur_dir) \
        .replace("__PATHS__", paths_str) 

    logging.info(f"Prompt:\n{prompt}\n")
    
    relevant_files_paths = [f[0] for f in relevant_files]

    value = send_prompt_to_llm(prompt)
    response_json = extract_json_from_llm_response(value)
    logging.info(f"Relevant files and directories:\n{json.dumps(response_json, indent=2)}")
    for file in response_json["files"]:
        path, description = file["path"], file["explanation"]
        if not os.path.dirname(path) == cur_dir:
            logging.warning(f"File {path} is not in current directory {cur_dir}")
            continue
        if path not in relevant_files_paths:
            relevant_files.append((path, description))
    for directory in response_json["directories"]:
        path, description = directory["path"], directory["explanation"]
        if not os.path.dirname(path) == cur_dir:
            logging.warning(f"Directory {path} is not in current directory {cur_dir}")
            continue
        logging.info(f"*** Recursively getting relevant files for {path} with explanation: {description}")
        get_relevant_files_rec(query, path, index, relevant_files)
    return relevant_files




def write_output_to_md_file(query: str, result: str):
    """Writes the result of a query to a uniquely named .md file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"query_result_{timestamp}.md"
    with open(filename, 'w') as file:
        file.write(f"# Query Result\n\n**Query:** {query}\n\n**Result:**\n\n{result}")
    logging.info(f"Results have been written to {filename}")


def answer_query(query: str, index_file: str) -> str:
    main_index = load_index_file(index_file)
    relevant_files = get_relevant_files_rec(query, ".", main_index, [])
    logging.info(f"Relevant files:\n{json.dumps(relevant_files, indent=2)}")

    #ask the user if they want to continue or stop

    response = input("Do you want to continue? (y/n)")
    if response.lower() == "y":
        prompt = query_prompt.replace("__QUERY__", query)
        relevant_file_content_list = []
        for file, description in relevant_files:
            relevant_file_content_list.append(f"\n\n*** CONTENTS OF {file} ***\n\n{read_file_content(file)}\n\n*** END OF {file} ***\n\n")
        relevant_file_contents = "\n".join(relevant_file_content_list)
        prompt = prompt.replace("__RELEVANT_FILES__", relevant_file_contents)
        # Write the result to a markdown file
        result = send_prompt_to_llm(prompt)
        session_name = get_session_name_using_llm(query, result)
        #get the log from the buffer
        log_contents = log_buffer.getvalue()
        session_log_file = f"{session_name}.md"
        write_output_to_md_file(query, result)
        #write the log to the session log file
        with open(session_log_file, "w") as file:
            file.write(log_contents)
        return result
    else:
        return "skipped"


def get_session_name_using_llm(query: str, response: str) -> str:
    prompt = get_session_name_prompt.replace("__QUERY__", query).replace("__RESPONSE__", response)
    logging.info(f"Prompt for getting the session name :\n{prompt}\n")
    value = send_prompt_to_llm(prompt)
    object = extract_json_from_llm_response(value)
    logging.info(f"Response for getting the session name:\n{json.dumps(object, indent=2)}\n")
    #get the json response
    session_name = object["session_name"].replace(" ", "_")
    return session_name

def main():
    parser = argparse.ArgumentParser(description='Project file indexer and query tool')
    parser.add_argument('--update', action='store_true', help='Update the project index')
    parser.add_argument('--query', type=str, help='Query the project index')
    parser.add_argument('--index-file', type=str, default="file_index.json", help='Path to index file')
    parser.add_argument('--fixup', action='store_true', help='Fixup the index file')
    # add an argument to show info about a file or directory
    parser.add_argument('--info', type=str, help='Show info about a file or directory') 
    
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
    elif args.info:
        item_path = args.info
        if item_path.endswith("/"):
            item_path = item_path[:-1]
        main_index = load_index_file(args.index_file)
        if item_path not in main_index:
            logging.error(f"Item {item_path} not found in index")
            return
        info = main_index[item_path]
        logging.info(f"Info about {item_path}:\n{json.dumps(info, indent=2)}\n")
    else:
        parser.print_help()
    
    #output the token count
    logging.info(f"Total tokens: {token_counter.total_tokens}")
    logging.info(f"Input tokens: {token_counter.input_tokens}")
    logging.info(f"Output tokens: {token_counter.output_tokens}")
    logging.info(f"Total cost: {token_counter.total_cost_str()}")


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
    "type": "<file type>",
    "purpose": "<brief purpose of the file>",
    "elements": [
        "class:<name1> - <description of the class>",
        "class:<name2> - <description of the class>",
        "function:<name1> - <description of the function>",
        "function:<name2> - <description of the function>",
        "structure:<name1> - <description of the structure>",
        "structure:<name2> - <description of the structure>"
    ],
    "deps": ["<other files/modules used>"],
    "related": [
        "<related file> - <brief explanation>",
        "<related file> - <brief explanation>"
    ]
}

Respond strictly in JSON format with nothing else.

Here are all of the files in the project, which may be helpful in identifying
which files are related to this one:

__ALL_FILES__

Here is the contents of the file:

__FILE_CONTENTS__
"""

index_directory_prompt = """
You are an AI specialized in analyzing software project structures. I will provide you with metadata about a directory in a project, 
including information about its files and any immediate subdirectories. Using this metadata, please summarize the directory’s purpose, 
main components, and its dependencies. Respond strictly in JSON format with only the specified fields.

purpose: A summary of the main purpose or function of this directory within the project.
description: A detailed description of the this directory within the project.  This description should include the purpose of the directory and should be helpful
in determining if the directory contains any files relevant to a given query.

The path of the directory is: __DIRECTORY__

Here are all of the files in the project, which may be helpful in identifying
which files are related to this one:

__FILES__

Your JSON response should follow this format:

{
    "purpose": "<description of the directory's purpose>",
    "description": "<detailed description of the directory>",
}

Please respond strictly in JSON format with nothing else.

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

relevant_items_prompt = """
I need help answering the following query:

__QUERY__

It may be useful to include the content of files in my repository to help answer the question.
Here is a list of files and directories in the directory named __DIRECTORY__ in my project and information about them:

The list of paths and files I want you to look at an answer about is:

__PATHS__

Here is the information about these files and directories, including the elements, file, and directories in side of them
as well as the dependencies and related files:

__ITEMS__

Please respond with a list of files and directories that would be helpful in answering the question from 
highest relevance to lowest (don't include ALL files, just the most relevant ones). For each file
include the file path and a brief explanation of why it is relevant.  If you think a directory might include files that are relevant,
indicate them and I will include the contents of the directory in another query to you.

Again, ONLY list files and directories from the following list.  I will ask recursively about any directories you list.
*DO NOT* include any files or directories that are not in the following list (for instance, if they are inside of one of the directories listed).
If you list a directory, I will include the contents of the directory in another query to you, so ONLY include the directory and not any files that are inside of it.

__PATHS__

And the question I'm hoping that including these will help answer is:

__QUERY__

For each file in that list, if it is relevant, please include it in the list.
For each directory in that list, if it is relevant, please include it in the list.

Your response should be in JSON format with the following fields:
{
    "files": [
        {"path": "<file path>", "explanation": "<brief explanation>"},
        {"path": "<file path>", "explanation": "<brief explanation>"}
    ],
    "directories": [
        {"path": "<directory path>", "explanation": "<brief explanation>"},
        {"path": "<directory path>", "explanation": "<brief explanation>"}
    ]
}

Please respond strictly in JSON format with nothing else.
"""

get_session_name_prompt = """
I need help naming a session.  Here is the query that I'm trying to answer:

__QUERY__

And here is the response that I got:

__RESPONSE__

Please respond with a name for the session that captures the essence of the query and response.  this should be very short because I'm going to use it as a filename.  
Because of this, please replace spaces with underscores.

Please response in the following format:

{
    "query": "<summary of the query>",
    "response": "<summary of the response>",
    "session_name": "<name of the session>"
}
"""

example_index_file_contents = """
{
  "./backend/db_handlers/user_handler.py": {
    "type": "Python",
    "purpose": "This file defines a handler for managing user-related operations in a Cosmos DB, including creating, retrieving, updating, and deleting users, as well as fetching user-related recordings and transcriptions.",
    "elements": [
      "Class:UserHandler - Handles operations related to users in Cosmos DB, such as creating, retrieving, updating, and deleting users, and fetching user-related recordings and transcriptions.",
      "Func:__init__ - Initializes the UserHandler with Cosmos DB connection details.",
      "Func:create_user - Creates a new user in Cosmos DB and returns the user ID.",
      "Func:get_user - Retrieves a user by ID and returns it as a User model.",
      "Func:get_user_by_name - Retrieves users by name and returns them as a list of User models.",
      "Func:get_all_users - Retrieves all users and returns them as a list of User models.",
      "Func:update_user - Updates user details like email, name, and role, and returns the updated User model.",
      "Func:delete_user - Deletes a user from Cosmos DB.",
      "Func:get_user_files - Gets all recordings associated with the user and returns them as Recording models.",
      "Func:get_user_transcriptions - Gets all transcriptions associated with the user and returns them as Transcription models."
    ],
    "deps": [
      "azure.cosmos.CosmosClient",
      "datetime",
      "uuid",
      "db_handlers.models.User",
      "db_handlers.models.Recording",
      "db_handlers.models.Transcription",
      "db_handlers.util.filter_cosmos_fields",
      "typing.Optional",
      "typing.List"
    ],
    "related": [
      "./backend/db_handlers/models.py - Contains the User, Recording, and Transcription models used in this file.",
      "./backend/db_handlers/util.py - Provides the filter_cosmos_fields utility function used in this file."
    ],
    "md5sum": "6dfa52bad4ce28827f7d3cfe03b7fabe",
    "kind": "file",
    "path": "./backend/db_handlers/user_handler.py"
  },
  "./backend": {
    "purpose": "The './backend' directory serves as the core backend component of the application, providing functionalities for web application logic, database interactions, and integrations with Azure services.",
    "description": "The './backend' directory contains the main backend logic for the application, including a Flask web application, database handlers for Cosmos DB, and utilities for interacting with Azure services. Key components include 'app.py' for handling web routes and user interactions, 'llms.py' for processing speaker information using Azure OpenAI, and 'blob_util.py' for managing Azure Blob Storage. The directory also includes configuration files, utility scripts, and templates for rendering HTML pages. Dependencies span across Flask, Azure SDKs, and various Python libraries for handling web requests, authentication, and data processing. This directory is essential for managing the application's backend operations, including user authentication, file uploads, and data management.",
    "path": "./backend",
    "kind": "directory",
    "md5sum": "200be217932aa3780d430d1eeae7eb8a",
    "elements": [
      "file:./backend/llms.py - This file is used to interact with an Azure OpenAI deployment to process and analyze speaker information from transcripts.",
      "file:./backend/blob_util.py - This file provides utility functions for storing recordings in Azure Blob Storage and generating SAS URLs for accessing these recordings.",
      "file:./backend/app.py - This file is the main application script for a Flask web application, handling routes for user authentication, file uploads, and managing recordings and transcriptions.",
      "file:./backend/manage.py - A command-line tool to manage Azure Blob Storage and Cosmos DB, including operations like listing, showing, deleting entries, and checking consistency.",
      "file:./backend/util.py - This file provides utility functions for audio processing and text manipulation, including escaping JavaScript strings, calculating audio duration, formatting durations, elliding text, converting audio files to MP3, and updating speaker labels in transcripts.",
      "file:./backend/config.py - This file is used to configure environment variables for the application, primarily related to Azure services and authentication.",
      "file:./backend/user_util.py - This file defines a function to retrieve user information based on a request, either by user ID from cookies or by a default username.",
      "file:./backend/generate_example_env.py - This script generates an example environment file by redacting sensitive information from an existing .env file.",
      "file:./backend/generate_filelist.py - This script reads file inclusion and exclusion patterns from a '.fileinclude' file and generates a 'filelist.txt' containing the list of files that match the inclusion patterns but not the exclusion patterns.",
      "file:./backend/api_version.py - Defines the current version of the API.",
      "file:./backend/test.py - This script processes JSON data to generate and print a transcript from recognized phrases, grouping text by speaker.",
      "file:./backend/fixup_cosmos_data.py - This script is used to fix and update recording and transcription data in a database, ensuring consistency and correctness of the data.",
      "file:./backend/auth.py - Handles authentication with Azure AD using MSAL in a Flask application.",
      "file:./backend/__init__.py - This file imports the 'config' module from the current package.",
      "file:./backend/Makefile - Automates tasks such as building packages, generating code from schemas, version bumping, creating deployment packages, and deploying to Azure.",
      "file:./backend/prompts.yaml - This file contains prompts for inferring speaker names and summarizing speakers in a transcript.",
      "directory:./backend/routes - The './backend/routes' directory contains Python files that define the routes and API endpoints for the backend of the application. It includes 'az_transcription_routes.py', which handles routes related to Azure transcription services, and 'api.py', which manages endpoints for users, recordings, and transcriptions. These files interact with various dependencies such as Flask, database handlers, and utility modules to provide comprehensive API functionalities. The directory is crucial for managing the application's interaction with Azure services and handling user-related data operations.",
      "directory:./backend/static - The ./backend/static directory contains static assets that are used by the backend part of the project. This includes files like styles.css, which provides styling for various HTML elements. These static files are essential for the visual presentation of the web application and are likely served directly by the backend server to ensure consistent styling across different parts of the application. The presence of styles.css suggests that this directory is crucial for maintaining the look and feel of the application as rendered by the backend.",
      "directory:./backend/templates - The './backend/templates' directory is a collection of HTML files that serve as templates for different pages of the web application. These templates include 'base.html', which provides a common structure for other pages, and specific templates like 'upload.html', 'index.html', 'view_transcription.html', and 'recordings.html', each serving distinct purposes such as file uploads, displaying the main index page, showing transcription details, and listing recordings. The templates rely on shared dependencies like 'base.html' for consistent layout and styling, and they interact with server-side logic defined in various Python files within the backend, such as 'app.py' and route definitions in 'api.py' and 'az_transcription_routes.py'.",
      "directory:./backend/db_handlers - The ./backend/db_handlers directory contains various Python modules that handle database operations for a transcription application using Cosmos DB. It includes handlers for managing users, recordings, and transcriptions, as well as utility functions for filtering Cosmos DB fields. The directory also defines data models using Pydantic for users, recordings, and transcriptions. Additionally, it provides factory functions to create and retrieve handler instances using Flask's application context. Dependencies include Azure Cosmos DB client libraries, Pydantic for data modeling, and Flask for application context management."
    ]
  }
}
"""

if __name__ == "__main__":
    main()
