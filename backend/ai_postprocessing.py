"""
AI Post-processing module for audio recordings.

This module handles AI-generated content for recordings including:
- Title generation (concise, descriptive titles)
- Description generation (1-2 sentence summaries)
- Speaker inference coordination (using existing llms.py functionality)

All AI operations are coordinated here while keeping llms.py generic.
"""

import asyncio
import json
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
generate_title_and_description_prompt = prompts['prompts']['generate_title_and_description']['prompt']

logger = logging.getLogger("quickscribe.backend.ai_postprocessing")


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


async def generate_title_and_description_single_call(transcript_text: str) -> Dict[str, str]:
    """
    Generate title and description in a single LLM call with JSON output.
    
    Args:
        transcript_text: The full transcript text
        
    Returns:
        Dict with 'title' and 'description' keys
    """
    logger.info(f"Starting single LLM call for title and description generation for transcript of length {len(transcript_text)}")
    
    # Prepare combined prompt
    combined_prompt = generate_title_and_description_prompt.replace("__TRANSCRIPT__", transcript_text)
    
    logger.debug(f"Combined prompt prepared (length: {len(combined_prompt)})")
    
    try:
        logger.info("Sending single LLM request for title and description")
        from llms import send_prompt_to_llm_async
        result = await send_prompt_to_llm_async(combined_prompt)
        
        logger.debug(f"Raw LLM response: {result}")
        
        # Parse JSON response - extract JSON from any surrounding text
        try:
            # Find the first opening brace/bracket and last closing brace/bracket
            first_brace = result.find('{')
            first_bracket = result.find('[')
            
            # Determine which comes first (or if only one exists)
            start_pos = -1
            if first_brace != -1 and first_bracket != -1:
                start_pos = min(first_brace, first_bracket)
            elif first_brace != -1:
                start_pos = first_brace
            elif first_bracket != -1:
                start_pos = first_bracket
            
            if start_pos == -1:
                raise ValueError("No JSON object or array found in response")
            
            # Find the last closing brace/bracket
            last_brace = result.rfind('}')
            last_bracket = result.rfind(']')
            
            # Determine which comes last
            end_pos = -1
            if last_brace != -1 and last_bracket != -1:
                end_pos = max(last_brace, last_bracket)
            elif last_brace != -1:
                end_pos = last_brace
            elif last_bracket != -1:
                end_pos = last_bracket
            
            if end_pos == -1 or end_pos <= start_pos:
                raise ValueError("No valid JSON closing found in response")
            
            # Extract JSON substring
            json_content = result[start_pos:end_pos + 1]
            logger.debug(f"Extracted JSON content: {json_content}")
            
            parsed_result = json.loads(json_content)
            
            title = parsed_result.get('title', '').strip()
            description = parsed_result.get('description', '').strip()
            
            logger.info(f"Successfully generated title: '{title}' (length: {len(title)})")
            logger.info(f"Successfully generated description: '{description}' (length: {len(description)})")
            
            return {
                'title': title,
                'description': description
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response was: {result}")
            # Fallback to empty values on JSON parsing error
            return {
                'title': '',
                'description': ''
            }
            
    except Exception as e:
        logger.error(f"Error generating title and description in single call: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        # Fallback to empty values on error
        return {
            'title': '',
            'description': ''
        }


async def generate_title_and_description_concurrent(transcript_text: str) -> Dict[str, str]:
    """
    Generate title and description concurrently for efficiency.
    
    Args:
        transcript_text: The full transcript text
        
    Returns:
        Dict with 'title' and 'description' keys
    """
    logger.info(f"Starting concurrent title and description generation for transcript of length {len(transcript_text)}")
    
    # Prepare prompts
    title_prompt = generate_title_prompt.replace("__TRANSCRIPT__", transcript_text)
    description_prompt = generate_description_prompt.replace("__TRANSCRIPT__", transcript_text)
    
    logger.debug(f"Title prompt prepared (length: {len(title_prompt)})")
    logger.debug(f"Description prompt prepared (length: {len(description_prompt)})")
    
    # Run both prompts concurrently
    try:
        logger.info("Sending concurrent LLM requests for title and description")
        results = await send_multiple_prompts_concurrent([title_prompt, description_prompt])
        
        title = results[0].strip()
        description = results[1].strip()
        
        logger.info(f"Successfully generated title: '{title}' (length: {len(title)})")
        logger.info(f"Successfully generated description: '{description}' (length: {len(description)})")
        
        return {
            'title': title,
            'description': description
        }
    except Exception as e:
        logger.error(f"Error generating title and description concurrently: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
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
        raw_speaker_mapping, updated_transcript = get_speaker_mapping(transcript_text)
        
        # Convert raw dictionary to proper SpeakerMapping objects
        from db_handlers.models import SpeakerMapping
        formatted_speaker_mapping = {}
        
        for speaker_id, speaker_data in raw_speaker_mapping.items():
            # Convert the nested dict to SpeakerMapping object
            formatted_speaker_mapping[speaker_id] = SpeakerMapping(
                name=speaker_data["name"],
                reasoning=speaker_data["reasoning"]
            )
        
        logger.info(f"Converted speaker mapping for {len(formatted_speaker_mapping)} speakers")
        
        # Update the transcription with new speaker mapping and transcript
        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription(transcription_id)
        
        if transcription:
            transcription.speaker_mapping = formatted_speaker_mapping
            transcription.diarized_transcript = updated_transcript
            transcription_handler.update_transcription(transcription)
            
            logger.info(f"Updated speaker names for transcription {transcription_id}")
            return {
                'speaker_mapping': formatted_speaker_mapping,
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
        diarized_length = len(transcription.diarized_transcript) if transcription.diarized_transcript else 0
        regular_length = len(transcription.text) if transcription.text else 0
        
        logger.info(f"Transcript data available - diarized: {diarized_length} chars, regular: {regular_length} chars")
        
        transcript_text = transcription.diarized_transcript or transcription.text
        
        if not transcript_text:
            logger.warning(f"No transcript text available for recording {recording_id}")
            return None, None
        
        used_type = "diarized" if transcription.diarized_transcript else "regular"
        logger.info(f"Using {used_type} transcript: {len(transcript_text)} characters")
            
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
            
        # Use the full transcript for processing
        processed_transcript = transcript_text
        word_count = len(transcript_text.split())
        logger.info(f"Using full transcript for processing: {len(transcript_text)} characters, {word_count} words")
        
        # Generate title and description in single call
        try:
            logger.info("Starting title and description generation")
            content_results = asyncio.run(generate_title_and_description_single_call(processed_transcript))
            results['title'] = content_results['title']
            results['description'] = content_results['description']
            
            logger.info(f"Generation results - Title: '{content_results['title']}', Description: '{content_results['description']}'")
            
            # Update recording with generated content
            updated_fields = []
            if content_results['title']:
                recording.title = content_results['title']
                updated_fields.append('title')
            if content_results['description']:
                recording.description = content_results['description']
                updated_fields.append('description')
                
            if updated_fields:
                recording_handler.update_recording(recording)
                logger.info(f"Updated recording {recording_id} with AI-generated fields: {updated_fields}")
            else:
                logger.warning(f"No valid title or description generated for recording {recording_id}")
            
        except Exception as e:
            error_msg = f"Failed to generate title/description: {e}"
            logger.error(error_msg)
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
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
        
        # Add flag to indicate if speakers were updated (for frontend transcript reload)
        results['speakers_updated'] = bool(results['speaker_update'])
        
    except Exception as e:
        error_msg = f"Unexpected error in post-processing: {e}"
        logger.error(error_msg)
        results['errors'].append(error_msg)
    
    return results