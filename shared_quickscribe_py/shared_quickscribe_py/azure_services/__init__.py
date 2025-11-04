"""
Azure service clients
"""
from .blob_storage import BlobStorageClient, QueueStorageClient, send_transcoding_job
from .speech_service import AzureSpeechClient
from .azure_openai import (
    AzureOpenAIClient,
    get_openai_client,
    send_prompt_to_llm,
    send_prompt_to_llm_with_timing,
    send_prompt_to_llm_async,
    send_prompt_to_llm_async_with_timing,
    send_multiple_prompts_concurrent,
    send_multiple_prompts_concurrent_with_timing,
)

__all__ = [
    "BlobStorageClient",
    "QueueStorageClient",
    "send_transcoding_job",
    "AzureSpeechClient",
    "AzureOpenAIClient",
    "get_openai_client",
    "send_prompt_to_llm",
    "send_prompt_to_llm_with_timing",
    "send_prompt_to_llm_async",
    "send_prompt_to_llm_async_with_timing",
    "send_multiple_prompts_concurrent",
    "send_multiple_prompts_concurrent_with_timing",
]
