import os
import requests
import base64
import json
from config import config
import yaml
import logging

# Configuration
API_KEY = config.AZURE_OPENAI_API_KEY
ENDPOINT = config.AZURE_OPENAI_API_ENDPOINT
DEPLOYMENT_NAME = config.AZURE_OPENAI_DEPLOYMENT_NAME
API_VERSION = config.AZURE_OPENAI_API_VERSION

ENDPOINT = f"{ENDPOINT}/openai/deployments/{DEPLOYMENT_NAME}/chat/completions?api-version={API_VERSION}"
headers = {
    "Content-Type": "application/json",
    "api-key": API_KEY,
}

# Payload for the request
payload = {
  "messages": [
    {
      "role": "system",
      "content": [
        {
          "type": "text",
          "text": "You are an AI assistant that helps people find information."
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "tell me a joke"
        }
      ]
    }
  ],
  "temperature": 0.1,
  "top_p": 0.95,
  "max_tokens": 800
}

with open("prompts.yaml", 'r') as stream:
    prompts = yaml.safe_load(stream)

infer_speaker_prompt = prompts['prompts']['infer_speaker_names']['prompt']

def get_speaker_mapping(transcript_text):
    prompt = infer_speaker_prompt.replace("__TRANSCRIPT__", transcript_text)
    payload["messages"][1]["content"][0]["text"] = prompt
    response = send_prompt_to_llm(prompt)
    #extract the json portion and validate it
    try:
        logging.info(response)
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        response_json = json.loads(response[json_start:json_end])
        logging.info(json.dumps(response_json, indent=4))

        #now get the list of all speakers from the transcript_text. they look like this:
        # Speaker A: some stuff
        # Speaker B: I said another thing
        # Speaker C: lots of stuff
        # Speaker D: etc.
        speakers = set()
        for line in transcript_text.split("\n"):
            if line.startswith("Speaker"):
                speaker_name = line.split(":")[0]
                speakers.add(speaker_name)
        # now check that each speaker in the transcript_text is in the response_json
        for speaker in speakers:
            if speaker not in response_json:
                raise ValueError(f"Speaker {speaker} not found in response_json")

        # now replace the speaker names in the transcript_text with the speaker mapping
        for speaker in speakers:
            transcript_text = transcript_text.replace(speaker, response_json[speaker]["name"])
        response_json["transcript_text"] = transcript_text

    except json.JSONDecodeError:
        raise ValueError("Invalid JSON response from the LLM")
    return response_json

def send_prompt_to_llm(prompt):
    payload["messages"][1]["content"][0]["text"] = prompt

    # Send request
    try:
        response = requests.post(ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.RequestException as e:
        raise SystemExit(f"Failed to make the request. Error: {e}")

    return response.json()["choices"][0]["message"]["content"]



# Example usage
if __name__ == "__main__":
    prompt = "Tell me a joke about computers."
    response = send_prompt_to_llm(prompt)
    if response:
        print(f"LLM Response:\n{response}")
