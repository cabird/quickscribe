"""
Azure OpenAI client for making LLM requests.

This module provides a unified interface for calling Azure OpenAI models
with support for multiple deployment configurations (e.g., standard and mini models).
"""

import os
import time
import logging
import asyncio
import aiohttp
import requests
from typing import Dict, List, Optional


class AzureOpenAIClient:
    """
    Client for making requests to Azure OpenAI API.

    Supports both synchronous and asynchronous requests with timing and token metrics.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment_name: str,
        api_version: str = "2024-02-15-preview"
    ):
        """
        Initialize Azure OpenAI client.

        Args:
            endpoint: Azure OpenAI endpoint URL (e.g., https://xxx.openai.azure.com/)
            api_key: Azure OpenAI API key
            deployment_name: Name of the deployment to use
            api_version: API version string
        """
        self.endpoint = endpoint.rstrip('/')
        self.api_key = api_key
        self.deployment_name = deployment_name
        self.api_version = api_version

        # Construct full endpoint URL
        self.completion_url = (
            f"{self.endpoint}/openai/deployments/{self.deployment_name}/"
            f"chat/completions?api-version={self.api_version}"
        )

        # Request headers
        self.headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
        }

        self.logger = logging.getLogger(__name__)

    def _build_payload(
        self,
        prompt: str,
        system_message: str = "You are an AI assistant that helps people find information."
    ) -> Dict:
        """Build request payload for Azure OpenAI API."""
        return {
            "messages": [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system_message}]
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
        }

    def send_prompt(
        self,
        prompt: str,
        system_message: str = "You are an AI assistant that helps people find information."
    ) -> str:
        """
        Send a synchronous prompt to the LLM.

        Args:
            prompt: The user prompt to send
            system_message: System message to set context

        Returns:
            Response content from the LLM

        Raises:
            Exception: If the request fails
        """
        payload = self._build_payload(prompt, system_message)

        try:
            response = requests.post(
                self.completion_url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.RequestException as e:
            self.logger.error(f"LLM request failed: {e}")
            raise Exception(f"Failed to make LLM request: {e}")

    def send_prompt_with_timing(
        self,
        prompt: str,
        system_message: str = "You are an AI assistant that helps people find information."
    ) -> Dict:
        """
        Send a synchronous prompt with timing and token usage metrics.

        Args:
            prompt: The user prompt to send
            system_message: System message to set context

        Returns:
            Dict with keys: content, llmResponseTimeMs, promptTokens, responseTokens

        Raises:
            Exception: If the request fails
        """
        payload = self._build_payload(prompt, system_message)
        start_time = time.time()

        try:
            response = requests.post(
                self.completion_url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()

            end_time = time.time()
            llm_response_time_ms = int((end_time - start_time) * 1000)

            response_data = response.json()
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
            self.logger.error(f"LLM request failed after {llm_response_time_ms}ms: {e}")
            raise Exception(f"LLM request failed after {llm_response_time_ms}ms: {e}")

    async def send_prompt_async(
        self,
        prompt: str,
        system_message: str = "You are an AI assistant that helps people find information."
    ) -> str:
        """
        Send an asynchronous prompt to the LLM.

        Args:
            prompt: The user prompt to send
            system_message: System message to set context

        Returns:
            Response content from the LLM

        Raises:
            Exception: If the request fails
        """
        payload = self._build_payload(prompt, system_message)

        self.logger.debug(f"Starting async LLM request to: {self.completion_url}")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.completion_url,
                    headers=self.headers,
                    json=payload
                ) as response:
                    self.logger.debug(f"Received response with status: {response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        self.logger.error(
                            f"LLM request failed with status {response.status}: {error_text}"
                        )
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"HTTP {response.status}: {error_text}"
                        )

                    response.raise_for_status()
                    response_data = await response.json()
                    return response_data["choices"][0]["message"]["content"]

            except aiohttp.ClientError as e:
                self.logger.error(f"Async LLM request failed with aiohttp error: {e}")
                raise Exception(f"Async LLM request failed: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error in async LLM request: {e}")
                raise

    async def send_prompt_async_with_timing(
        self,
        prompt: str,
        system_message: str = "You are an AI assistant that helps people find information."
    ) -> Dict:
        """
        Send an asynchronous prompt with timing and token usage metrics.

        Args:
            prompt: The user prompt to send
            system_message: System message to set context

        Returns:
            Dict with keys: content, llmResponseTimeMs, promptTokens, responseTokens

        Raises:
            Exception: If the request fails
        """
        payload = self._build_payload(prompt, system_message)
        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.completion_url,
                    headers=self.headers,
                    json=payload
                ) as response:
                    response.raise_for_status()

                    end_time = time.time()
                    llm_response_time_ms = int((end_time - start_time) * 1000)

                    response_data = await response.json()
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
                self.logger.error(f"Async LLM request failed after {llm_response_time_ms}ms: {e}")
                raise Exception(f"Async LLM request failed after {llm_response_time_ms}ms: {e}")

    async def send_multiple_prompts_concurrent(
        self,
        prompts: List[str],
        system_message: str = "You are an AI assistant that helps people find information."
    ) -> List[str]:
        """
        Send multiple prompts concurrently and return results in the same order.

        Args:
            prompts: List of prompts to send
            system_message: System message to set context

        Returns:
            List of response content strings in the same order as prompts
        """
        tasks = [
            self.send_prompt_async(prompt, system_message)
            for prompt in prompts
        ]
        results = await asyncio.gather(*tasks)
        return results

    async def send_multiple_prompts_concurrent_with_timing(
        self,
        prompts: List[str],
        system_message: str = "You are an AI assistant that helps people find information."
    ) -> List[Dict]:
        """
        Send multiple prompts concurrently with timing metrics.

        Args:
            prompts: List of prompts to send
            system_message: System message to set context

        Returns:
            List of dicts with content, timing, and token usage in the same order as prompts
        """
        tasks = [
            self.send_prompt_async_with_timing(prompt, system_message)
            for prompt in prompts
        ]
        results = await asyncio.gather(*tasks)
        return results


# =============================================================================
# Factory Functions
# =============================================================================

def get_openai_client(model_type: str = "normal") -> AzureOpenAIClient:
    """
    Factory function to get an Azure OpenAI client for the specified model type.

    Args:
        model_type: Either "normal" (default, uses gpt-4o) or "mini" (uses gpt-4o-mini)

    Returns:
        Configured AzureOpenAIClient instance

    Raises:
        ValueError: If required environment variables are missing
        ValueError: If model_type is not recognized

    Environment Variables Required:
        AZURE_OPENAI_API_ENDPOINT: Azure OpenAI endpoint URL
        AZURE_OPENAI_API_KEY: Azure OpenAI API key
        AZURE_OPENAI_API_VERSION: API version (optional, defaults to 2024-02-15-preview)

        For normal model:
        AZURE_OPENAI_DEPLOYMENT_NAME: Deployment name for standard model (e.g., gpt-4o)

        For mini model:
        AZURE_OPENAI_MINI_DEPLOYMENT_NAME: Deployment name for mini model (e.g., gpt-4o-mini)
    """
    # Get common configuration
    endpoint = os.environ.get("AZURE_OPENAI_API_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    if not endpoint:
        raise ValueError("AZURE_OPENAI_API_ENDPOINT environment variable is required")
    if not api_key:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")

    # Get deployment name based on model type
    if model_type == "normal":
        deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        if not deployment_name:
            raise ValueError(
                "AZURE_OPENAI_DEPLOYMENT_NAME environment variable is required for normal model"
            )
    elif model_type == "mini":
        deployment_name = os.environ.get("AZURE_OPENAI_MINI_DEPLOYMENT_NAME")
        if not deployment_name:
            raise ValueError(
                "AZURE_OPENAI_MINI_DEPLOYMENT_NAME environment variable is required for mini model"
            )
    else:
        raise ValueError(f"Unknown model_type: {model_type}. Must be 'normal' or 'mini'")

    return AzureOpenAIClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment_name,
        api_version=api_version
    )


# =============================================================================
# Backward Compatibility Functions
# =============================================================================
# These maintain compatibility with existing code that uses llms.py

_default_client: Optional[AzureOpenAIClient] = None


def _get_default_client() -> AzureOpenAIClient:
    """Get or create the default client (normal model)."""
    global _default_client
    if _default_client is None:
        _default_client = get_openai_client("normal")
    return _default_client


def send_prompt_to_llm(prompt: str) -> str:
    """Backward compatible wrapper for send_prompt."""
    client = _get_default_client()
    return client.send_prompt(prompt)


def send_prompt_to_llm_with_timing(prompt: str) -> Dict:
    """Backward compatible wrapper for send_prompt_with_timing."""
    client = _get_default_client()
    return client.send_prompt_with_timing(prompt)


async def send_prompt_to_llm_async(prompt: str) -> str:
    """Backward compatible wrapper for send_prompt_async."""
    client = _get_default_client()
    return await client.send_prompt_async(prompt)


async def send_prompt_to_llm_async_with_timing(prompt: str) -> Dict:
    """Backward compatible wrapper for send_prompt_async_with_timing."""
    client = _get_default_client()
    return await client.send_prompt_async_with_timing(prompt)


async def send_multiple_prompts_concurrent(prompts: List[str]) -> List[str]:
    """Backward compatible wrapper for send_multiple_prompts_concurrent."""
    client = _get_default_client()
    return await client.send_multiple_prompts_concurrent(prompts)


async def send_multiple_prompts_concurrent_with_timing(prompts: List[str]) -> List[Dict]:
    """Backward compatible wrapper for send_multiple_prompts_concurrent_with_timing."""
    client = _get_default_client()
    return await client.send_multiple_prompts_concurrent_with_timing(prompts)
