"""
AI Post-processing module for audio recordings.

This module handles AI-generated content for recordings including:
- Title generation (concise, descriptive titles)
- Description generation (1-2 sentence summaries)
- Speaker inference coordination (using existing llms.py functionality)

All AI operations are coordinated here while keeping llms.py generic.
"""

import asyncio
import logging
import yaml
from typing import Dict, Optional, Tuple
from db_handlers.handler_factory import get_recording_handler, get_transcription_handler
from db_handlers.models import Recording, Transcription
from llms import (
    send_multiple_prompts_concurrent, 
    get_speaker_mapping,
    send_prompt_to_llm
)

# Load prompts
with open("prompts.yaml", 'r') as stream:
    prompts = yaml.safe_load(stream)

generate_title_prompt = prompts['prompts']['generate_title']['prompt']
generate_description_prompt = prompts['prompts']['generate_description']['prompt']

logger = logging.getLogger(__name__)


def generate_recording_title(transcript_text: str) -> str:
    """
    Generate a concise title for the recording using LLM.
    
    Args:
        transcript_text: The full transcript text
        
    Returns:
        Generated title (max 60 characters)
    """
    prompt = generate_title_prompt.replace("__TRANSCRIPT__", transcript_text)
    result = send_prompt_to_llm(prompt)
    return result.strip()


def generate_recording_description(transcript_text: str) -> str:
    """
    Generate a 1-2 sentence description of the recording using LLM.
    
    Args:
        transcript_text: The full transcript text
        
    Returns:
        Generated description
    """
    prompt = generate_description_prompt.replace("__TRANSCRIPT__", transcript_text)
    result = send_prompt_to_llm(prompt)
    return result.strip()


async def generate_title_and_description_concurrent(transcript_text: str) -> Dict[str, str]:
    """
    Generate title and description concurrently for efficiency.
    
    Args:
        transcript_text: The full transcript text
        
    Returns:
        Dict with 'title' and 'description' keys
    """
    # Prepare prompts
    title_prompt = generate_title_prompt.replace("__TRANSCRIPT__", transcript_text)
    description_prompt = generate_description_prompt.replace("__TRANSCRIPT__", transcript_text)
    
    # Run both prompts concurrently
    try:
        results = await send_multiple_prompts_concurrent([title_prompt, description_prompt])
        return {
            'title': results[0].strip(),
            'description': results[1].strip()
        }
    except Exception as e:
        logger.error(f"Error generating title and description concurrently: {e}")
        # Fallback to empty values on error
        return {
            'title': '',
            'description': ''
        }


def update_speaker_names(transcription_id: str, transcript_text: str) -> Optional[Dict]:
    """
    Update speaker names in a diarized transcript using existing LLM functionality.
    
    Args:
        transcription_id: ID of the transcription to update
        transcript_text: The diarized transcript text
        
    Returns:
        Dict with speaker mapping results or None if failed
    """
    try:
        # Use existing speaker inference functionality
        speaker_mapping, updated_transcript = get_speaker_mapping(transcript_text)
        
        # Update the transcription with new speaker mapping and transcript
        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription(transcription_id)
        
        if transcription:
            transcription.speaker_mapping = speaker_mapping
            transcription.diarized_transcript = updated_transcript
            transcription_handler.update_transcription(transcription)
            
            logger.info(f"Updated speaker names for transcription {transcription_id}")
            return {
                'speaker_mapping': speaker_mapping,
                'updated_transcript': updated_transcript
            }
    except Exception as e:
        logger.warning(f"Speaker inference failed for transcription {transcription_id}: {e}")
        return None


def get_transcript_text_for_processing(recording_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get the best available transcript text for AI processing.
    
    Args:
        recording_id: ID of the recording
        
    Returns:
        Tuple of (transcript_text, transcription_id) or (None, None) if not available
    """
    try:
        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription_by_recording(recording_id)
        
        if not transcription:
            logger.warning(f"No transcription found for recording {recording_id}")
            return None, None
            
        # Prefer diarized transcript, fall back to regular text
        transcript_text = transcription.diarized_transcript or transcription.text
        
        if not transcript_text:
            logger.warning(f"No transcript text available for recording {recording_id}")
            return None, None
            
        return transcript_text, transcription.id
        
    except Exception as e:
        logger.error(f"Error getting transcript for recording {recording_id}: {e}")
        return None, None


def truncate_transcript_for_processing(transcript_text: str, max_words: int = 2000) -> str:
    """
    Truncate transcript to fit within token limits while preserving meaning.
    
    Args:
        transcript_text: Full transcript text
        max_words: Maximum number of words to include
        
    Returns:
        Truncated transcript text
    """
    words = transcript_text.split()
    if len(words) <= max_words:
        return transcript_text
        
    # Take first portion and add indicator
    truncated = ' '.join(words[:max_words])
    return f"{truncated}\n\n[Transcript truncated for processing - showing first {max_words} words]"


def postprocess_recording_full(recording_id: str) -> Dict[str, any]:
    """
    Perform complete AI post-processing on a recording.
    
    This includes:
    1. Title generation
    2. Description generation  
    3. Speaker inference (if diarized transcript exists)
    
    Args:
        recording_id: ID of the recording to process
        
    Returns:
        Dict with results and status information
    """
    logger.info(f"Starting AI post-processing for recording {recording_id}")
    
    results = {
        'recording_id': recording_id,
        'title': None,
        'description': None,
        'speaker_update': None,
        'errors': []
    }
    
    try:
        # Get recording and transcript
        recording_handler = get_recording_handler()
        recording = recording_handler.get_recording(recording_id)
        
        if not recording:
            error_msg = f"Recording {recording_id} not found"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
            
        transcript_text, transcription_id = get_transcript_text_for_processing(recording_id)
        
        if not transcript_text:
            error_msg = f"No transcript available for recording {recording_id}"
            logger.warning(error_msg)
            results['errors'].append(error_msg)
            return results
            
        # Truncate transcript if too long
        processed_transcript = truncate_transcript_for_processing(transcript_text)
        
        # Generate title and description concurrently
        try:
            content_results = asyncio.run(generate_title_and_description_concurrent(processed_transcript))
            results['title'] = content_results['title']
            results['description'] = content_results['description']
            
            # Update recording with generated content
            if content_results['title']:
                recording.title = content_results['title']
            if content_results['description']:
                recording.description = content_results['description']
                
            recording_handler.update_recording(recording)
            logger.info(f"Updated recording {recording_id} with AI-generated title and description")
            
        except Exception as e:
            error_msg = f"Failed to generate title/description: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        # Update speaker names if we have a diarized transcript
        if transcription_id and "Speaker " in transcript_text:
            try:
                speaker_results = update_speaker_names(transcription_id, transcript_text)
                results['speaker_update'] = speaker_results
            except Exception as e:
                error_msg = f"Failed to update speaker names: {e}"
                logger.warning(error_msg)
                results['errors'].append(error_msg)
        
        success_count = sum([1 for key in ['title', 'description', 'speaker_update'] if results[key]])
        logger.info(f"AI post-processing completed for recording {recording_id}. "
                   f"Successful operations: {success_count}/3")
        
    except Exception as e:
        error_msg = f"Unexpected error in post-processing: {e}"
        logger.error(error_msg)
        results['errors'].append(error_msg)
    
    return results