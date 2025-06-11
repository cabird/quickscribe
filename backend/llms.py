import os
import requests
import base64
import json
from config import config
import yaml
import logging
import asyncio
import aiohttp
from typing import Dict, List

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
get_speaker_summaries_prompt = prompts['prompts']['get_speaker_summaries']['prompt']

def get_speaker_mapping(transcript_text):
    prompt = infer_speaker_prompt.replace("__TRANSCRIPT__", transcript_text)
    payload["messages"][1]["content"][0]["text"] = prompt
    response = send_prompt_to_llm(prompt)
    updated_transcript_text = ""
    #extract the json portion and validate it
    try:
        logging.info(response)
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        response_json = json.loads(response[json_start:json_end])
        logging.info(json.dumps(response_json, indent=4))

        #now get the list of all speakers from the transcript_text. they look like this:
        # Speaker 1: some stuff
        # Speaker 2: I said another thing
        # Speaker 3: lots of stuff
        # Speaker 2: blah blah blah
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
        updated_transcript_text = transcript_text
        

    except json.JSONDecodeError:
        raise ValueError("Invalid JSON response from the LLM")
    return response_json, updated_transcript_text

def extract_json_from_response(response: str) -> Dict:
    """
    Extracts the JSON from the response string even if there are other parts in the response.
    """
    json_start = response.find("{")
    json_end = response.rfind("}") + 1
    return json.loads(response[json_start:json_end])


def get_speaker_summaries_via_llm(transcript_text: str) -> Dict[str, str]:
    prompt = get_speaker_summaries_prompt.replace("__TRANSCRIPT__", transcript_text)
    response = send_prompt_to_llm(prompt)
    # Parse the response to extract speaker summaries
    summaries = parse_speaker_summaries(response)
    return summaries


def parse_speaker_summaries(response: str) -> Dict[str, str]:
    """
    Parses the response to extract the speaker summaries.  Assumes the response is in the format specified in the prompts.yaml file.
    { "speaker_summaries": {
        "Speaker Name 1": "<one-sentence summary>",
        "Speaker Name 2": "<one-sentence summary>"
      }
    }
    """
    response_json = extract_json_from_response(response)
    return response_json["speaker_summaries"]

def send_prompt_to_llm(prompt):
    payload["messages"][1]["content"][0]["text"] = prompt

    # Send request
    try:
        response = requests.post(ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.RequestException as e:
        raise SystemExit(f"Failed to make the request. Error: {e}")

    return response.json()["choices"][0]["message"]["content"]

def send_prompt_to_llm_with_timing(prompt):
    """Enhanced LLM call that returns response content, timing, and token usage."""
    import time
    
    payload_copy = payload.copy()
    payload_copy["messages"] = payload["messages"].copy()
    payload_copy["messages"][1] = payload["messages"][1].copy()
    payload_copy["messages"][1]["content"] = payload["messages"][1]["content"].copy()
    payload_copy["messages"][1]["content"][0] = payload["messages"][1]["content"][0].copy()
    payload_copy["messages"][1]["content"][0]["text"] = prompt

    # Record start time
    start_time = time.time()
    
    try:
        response = requests.post(ENDPOINT, headers=headers, json=payload_copy)
        response.raise_for_status()
        
        # Record end time
        end_time = time.time()
        llm_response_time_ms = int((end_time - start_time) * 1000)
        
        response_data = response.json()
        
        # Extract content and usage information
        content = response_data["choices"][0]["message"]["content"]
        usage = response_data.get("usage", {})
        
        return {
            "content": content,
            "llmResponseTimeMs": llm_response_time_ms,
            "promptTokens": usage.get("prompt_tokens"),
            "responseTokens": usage.get("completion_tokens")
        }
        
    except requests.RequestException as e:
        end_time = time.time()
        llm_response_time_ms = int((end_time - start_time) * 1000)
        
        # Include timing even for errors
        raise Exception(f"LLM request failed after {llm_response_time_ms}ms: {e}")


# =============================================================================
# Async LLM Functions for Concurrent Processing
# =============================================================================

async def send_prompt_to_llm_async(prompt: str) -> str:
    """
    Async version of send_prompt_to_llm for concurrent processing.
    Returns just the content string.
    """
    async with aiohttp.ClientSession() as session:
        payload_copy = payload.copy()
        payload_copy["messages"] = payload["messages"].copy()
        payload_copy["messages"][1] = payload["messages"][1].copy()
        payload_copy["messages"][1]["content"] = payload["messages"][1]["content"].copy()
        payload_copy["messages"][1]["content"][0] = payload["messages"][1]["content"][0].copy()
        payload_copy["messages"][1]["content"][0]["text"] = prompt
        
        try:
            async with session.post(ENDPOINT, headers=headers, json=payload_copy) as response:
                response.raise_for_status()
                response_data = await response.json()
                return response_data["choices"][0]["message"]["content"]
                
        except aiohttp.ClientError as e:
            raise Exception(f"Async LLM request failed: {e}")


async def send_prompt_to_llm_async_with_timing(prompt: str) -> Dict:
    """
    Async version with timing metrics for concurrent processing.
    Returns dict with content, timing, and token usage.
    """
    import time
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        payload_copy = payload.copy()
        payload_copy["messages"] = payload["messages"].copy()
        payload_copy["messages"][1] = payload["messages"][1].copy()
        payload_copy["messages"][1]["content"] = payload["messages"][1]["content"].copy()
        payload_copy["messages"][1]["content"][0] = payload["messages"][1]["content"][0].copy()
        payload_copy["messages"][1]["content"][0]["text"] = prompt
        
        try:
            async with session.post(ENDPOINT, headers=headers, json=payload_copy) as response:
                response.raise_for_status()
                
                # Record end time
                end_time = time.time()
                llm_response_time_ms = int((end_time - start_time) * 1000)
                
                response_data = await response.json()
                
                # Extract content and usage information
                content = response_data["choices"][0]["message"]["content"]
                usage = response_data.get("usage", {})
                
                return {
                    "content": content,
                    "llmResponseTimeMs": llm_response_time_ms,
                    "promptTokens": usage.get("prompt_tokens"),
                    "responseTokens": usage.get("completion_tokens")
                }
                
        except aiohttp.ClientError as e:
            end_time = time.time()
            llm_response_time_ms = int((end_time - start_time) * 1000)
            raise Exception(f"Async LLM request failed after {llm_response_time_ms}ms: {e}")


async def send_multiple_prompts_concurrent(prompts: List[str]) -> List[str]:
    """
    Send multiple prompts concurrently and return results in the same order.
    Returns list of content strings.
    """
    tasks = [send_prompt_to_llm_async(prompt) for prompt in prompts]
    results = await asyncio.gather(*tasks)
    return results


async def send_multiple_prompts_concurrent_with_timing(prompts: List[str]) -> List[Dict]:
    """
    Send multiple prompts concurrently with timing metrics.
    Returns list of dicts with content, timing, and token usage.
    """
    tasks = [send_prompt_to_llm_async_with_timing(prompt) for prompt in prompts]
    results = await asyncio.gather(*tasks)
    return results



# Example usage
if __name__ == "__main__":
    prompt = "Tell me a joke about computers."
    response = send_prompt_to_llm(prompt)
    if response:
        print(f"LLM Response:\n{response}")
